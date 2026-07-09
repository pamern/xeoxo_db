from __future__ import annotations

import argparse
from pathlib import Path
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import UUID, uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.load_connection import (
    add_loader_connection_args,
    build_connection_kwargs,
    describe_connection,
)

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Json
except ImportError as exc:  # pragma: no cover - runtime dependency guard
    raise ImportError(
        "Missing dependency 'psycopg'. Run `uv sync` after updating pyproject.toml."
    ) from exc


DEFAULT_STAFF_NAME = "Linh Nguyen"
DEFAULT_POSITION = "Stylist"
PLACEHOLDER_PASSWORD_HASH = (
    "$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy"
)


def normalize_text(value: object) -> str | None:
    if value is None:
        return None

    text = " ".join(str(value).split()).strip()
    if not text:
        return None

    if text.lower() in {"null", "n/a", "na", "none"}:
        return None

    return text


def fetch_active_branch(connection: psycopg.Connection, branch_id: int | None) -> dict:
    with connection.cursor(row_factory=dict_row) as cursor:
        if branch_id is None:
            cursor.execute(
                """
                SELECT
                    branch_id,
                    branch_name,
                    is_active
                FROM iam.branch
                WHERE is_active = TRUE
                ORDER BY branch_id
                LIMIT 1
                """
            )
        else:
            cursor.execute(
                """
                SELECT
                    branch_id,
                    branch_name,
                    is_active
                FROM iam.branch
                WHERE branch_id = %(branch_id)s
                  AND is_active = TRUE
                ORDER BY branch_id
                LIMIT 1
                """,
                {"branch_id": branch_id},
            )
        branch = cursor.fetchone()

    if branch is None:
        if branch_id is not None:
            raise ValueError(
                f"Active branch with branch_id={branch_id} was not found in iam.branch."
            )
        raise ValueError(
            "No active branch found in iam.branch. Seed branch data before loading staff."
        )

    return branch


def fetch_or_create_staff_account(
    connection: psycopg.Connection,
    account_id: UUID | None,
    staff_name: str,
    allow_placeholder_auth_user: bool,
) -> tuple[UUID, bool]:
    if account_id is not None:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    u.id AS account_id,
                    a.role,
                    a.is_active
                FROM auth.users AS u
                LEFT JOIN iam.account AS a
                    ON a.account_id = u.id
                WHERE u.id = %(account_id)s
                LIMIT 1
                """,
                {"account_id": account_id},
            )
            row = cursor.fetchone()

        if row is None:
            raise ValueError(
                f"auth.users does not contain account_id={account_id}."
            )

        if row["role"] is None:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO iam.account (
                        account_id,
                        role,
                        is_active
                    )
                    VALUES (
                        %(account_id)s,
                        'STAFF',
                        TRUE
                    )
                    """,
                    {"account_id": account_id},
                )
            return account_id, True

        if row["role"] != "STAFF":
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE iam.account
                    SET role = 'STAFF', is_active = TRUE, updated_at = NOW()
                    WHERE account_id = %(account_id)s
                    """,
                    {"account_id": account_id},
                )

        return account_id, False

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT u.id AS account_id
            FROM auth.users AS u
            LEFT JOIN iam.account AS a
                ON a.account_id = u.id
            WHERE a.account_id IS NULL
            ORDER BY u.created_at, u.id
            LIMIT 1
            """
        )
        unused_auth_user = cursor.fetchone()

    if unused_auth_user is not None:
        new_account_id = unused_auth_user["account_id"]
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO iam.account (
                    account_id,
                    role,
                    is_active
                )
                VALUES (
                    %(account_id)s,
                    'STAFF',
                    TRUE
                )
                """,
                {"account_id": new_account_id},
            )
        return new_account_id, True

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT
                a.account_id
            FROM iam.account AS a
            LEFT JOIN iam.staff AS s
                ON s.account_id = a.account_id
            WHERE a.role = 'STAFF'
              AND s.staff_id IS NULL
            ORDER BY a.account_id
            LIMIT 1
            """
        )
        reusable_staff_account = cursor.fetchone()

    if reusable_staff_account is not None:
        return reusable_staff_account["account_id"], False

    if allow_placeholder_auth_user:
        placeholder_account_id = create_placeholder_auth_user(
            connection,
            staff_name=staff_name,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO iam.account (
                    account_id,
                    role,
                    is_active
                )
                VALUES (
                    %(account_id)s,
                    'STAFF',
                    TRUE
                )
                """,
                {"account_id": placeholder_account_id},
            )
        return placeholder_account_id, True

    raise ValueError(
        "No suitable auth.users record was found to seed staff. "
        "Create at least one auth user first, or pass --account-id for an existing auth.users.id."
    )


def create_placeholder_auth_user(
    connection: psycopg.Connection,
    staff_name: str,
) -> UUID:
    now = datetime.now(timezone.utc)
    user_id = uuid4()
    instance_id = uuid4()
    email = f"staff.seed.{str(user_id)[:8]}@xeoxo.local"

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT
                column_name,
                data_type,
                udt_name,
                is_nullable,
                column_default,
                is_identity,
                is_generated
            FROM information_schema.columns
            WHERE table_schema = 'auth'
              AND table_name = 'users'
            ORDER BY ordinal_position
            """
        )
        columns = cursor.fetchall()

    def build_value(column_name: str, data_type: str, udt_name: str):
        if column_name == "id":
            return user_id
        if column_name == "instance_id":
            return instance_id
        if column_name in {"aud", "role"}:
            return "authenticated"
        if column_name == "email":
            return email
        if column_name == "encrypted_password":
            return PLACEHOLDER_PASSWORD_HASH
        if column_name in {"confirmation_token", "recovery_token"}:
            return ""
        if column_name in {
            "email_change",
            "email_change_token_new",
            "email_change_token_current",
            "phone",
            "phone_change",
            "phone_change_token",
            "reauthentication_token",
        }:
            return ""
        if column_name in {"email_confirmed_at", "confirmed_at", "created_at", "updated_at"}:
            return now
        if column_name in {
            "confirmation_sent_at",
            "recovery_sent_at",
            "email_change_sent_at",
            "phone_change_sent_at",
            "reauthentication_sent_at",
            "last_sign_in_at",
            "invited_at",
            "banned_until",
            "deleted_at",
            "phone_confirmed_at",
        }:
            return now
        if column_name == "raw_app_meta_data":
            return Json({"provider": "email", "providers": ["email"]})
        if column_name == "raw_user_meta_data":
            return Json(
                {
                    "full_name": staff_name,
                    "seeded_by": "src.load.load_staff",
                }
            )
        if column_name in {"is_super_admin", "is_sso_user", "is_anonymous"}:
            return False
        if column_name == "email_change_confirm_status":
            return 0

        if data_type == "uuid":
            return uuid4()
        if data_type in {"json", "jsonb"}:
            return Json({})
        if data_type == "boolean":
            return False
        if "timestamp" in data_type:
            return now
        if data_type == "date":
            return now.date()
        if data_type == "time without time zone":
            return now.time()
        if data_type in {"smallint", "integer", "bigint"}:
            return 0
        if data_type in {"numeric", "real", "double precision"}:
            return 0
        if udt_name.endswith("[]"):
            return []
        if data_type in {"character varying", "character", "text"}:
            return ""

        raise ValueError(
            "Cannot build placeholder auth.users row because an unsupported "
            f"required column was found: {column_name} ({data_type}/{udt_name})."
        )

    insert_columns: list[str] = []
    insert_values: dict[str, object] = {}
    for column in columns:
        if column["is_identity"] == "YES" or column["is_generated"] != "NEVER":
            continue

        column_name = column["column_name"]
        should_include = column["is_nullable"] == "NO" and column["column_default"] is None
        if column_name in {
            "id",
            "instance_id",
            "aud",
            "role",
            "email",
            "encrypted_password",
            "email_confirmed_at",
            "confirmed_at",
            "raw_app_meta_data",
            "raw_user_meta_data",
            "created_at",
            "updated_at",
        }:
            should_include = True

        if not should_include:
            continue

        insert_columns.append(column_name)
        insert_values[column_name] = build_value(
            column_name=column_name,
            data_type=column["data_type"],
            udt_name=column["udt_name"],
        )

    column_sql = ", ".join(insert_columns)
    value_sql = ", ".join(f"%({column})s" for column in insert_columns)

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            INSERT INTO auth.users ({column_sql})
            VALUES ({value_sql})
            """,
            insert_values,
        )

    return user_id


def fetch_existing_staff_by_account(
    connection: psycopg.Connection,
    account_id: UUID,
) -> dict | None:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT
                staff_id,
                account_id,
                branch_id,
                staff_name,
                position,
                is_active
            FROM iam.staff
            WHERE account_id = %(account_id)s
            LIMIT 1
            """,
            {"account_id": account_id},
        )
        return cursor.fetchone()


def insert_staff(
    connection: psycopg.Connection,
    account_id: UUID,
    branch_id: int,
    staff_name: str,
    position: str,
) -> int:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            INSERT INTO iam.staff (
                account_id,
                branch_id,
                staff_name,
                position,
                is_active
            )
            VALUES (
                %(account_id)s,
                %(branch_id)s,
                %(staff_name)s,
                %(position)s,
                TRUE
            )
            RETURNING staff_id
            """,
            {
                "account_id": account_id,
                "branch_id": branch_id,
                "staff_name": staff_name,
                "position": position,
            },
        )
        row = cursor.fetchone()

    return int(row["staff_id"])


def update_staff(
    connection: psycopg.Connection,
    staff_id: int,
    branch_id: int,
    staff_name: str,
    position: str,
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE iam.staff
            SET
                branch_id = %(branch_id)s,
                staff_name = %(staff_name)s,
                position = %(position)s,
                is_active = TRUE,
                updated_at = NOW()
            WHERE staff_id = %(staff_id)s
            """,
            {
                "staff_id": staff_id,
                "branch_id": branch_id,
                "staff_name": staff_name,
                "position": position,
            },
        )


def seed_staff(
    connection_kwargs: dict[str, str | int],
    branch_id: int | None,
    account_id: UUID | None,
    staff_name: str,
    position: str,
) -> dict[str, object]:
    conninfo = connection_kwargs.get("conninfo")
    if isinstance(conninfo, str):
        parsed = urlparse(conninfo)
        host = parsed.hostname or ""
    else:
        host = str(connection_kwargs.get("host", ""))

    allow_placeholder_auth_user = host in {"127.0.0.1", "localhost"}

    with psycopg.connect(**connection_kwargs) as connection:
        branch = fetch_active_branch(connection, branch_id)
        resolved_account_id, account_created = fetch_or_create_staff_account(
            connection,
            account_id,
            staff_name=staff_name,
            allow_placeholder_auth_user=allow_placeholder_auth_user,
        )
        existing_staff = fetch_existing_staff_by_account(connection, resolved_account_id)

        action: str
        staff_id: int
        if existing_staff is None:
            staff_id = insert_staff(
                connection=connection,
                account_id=resolved_account_id,
                branch_id=int(branch["branch_id"]),
                staff_name=staff_name,
                position=position,
            )
            action = "inserted"
        else:
            staff_id = int(existing_staff["staff_id"])
            update_staff(
                connection=connection,
                staff_id=staff_id,
                branch_id=int(branch["branch_id"]),
                staff_name=staff_name,
                position=position,
            )
            action = "updated"

        connection.commit()

    return {
        "action": action,
        "staff_id": staff_id,
        "account_id": str(resolved_account_id),
        "branch_id": int(branch["branch_id"]),
        "branch_name": branch["branch_name"],
        "staff_name": staff_name,
        "position": position,
        "account_created": account_created,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed one sample staff into iam.staff."
    )
    add_loader_connection_args(parser)
    parser.add_argument(
        "--branch-id",
        type=int,
        help="Optional active branch_id to attach the staff to.",
    )
    parser.add_argument(
        "--account-id",
        type=UUID,
        help="Optional auth.users.id to promote/create as STAFF account.",
    )
    parser.add_argument(
        "--staff-name",
        default=DEFAULT_STAFF_NAME,
        help=f"Staff display name. Default: {DEFAULT_STAFF_NAME}",
    )
    parser.add_argument(
        "--position",
        default=DEFAULT_POSITION,
        help=f"Staff position. Default: {DEFAULT_POSITION}",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()
    connection_kwargs = build_connection_kwargs(args)
    result = seed_staff(
        connection_kwargs=connection_kwargs,
        branch_id=args.branch_id,
        account_id=args.account_id,
        staff_name=normalize_text(args.staff_name) or DEFAULT_STAFF_NAME,
        position=normalize_text(args.position) or DEFAULT_POSITION,
    )

    print(f"Target database: {describe_connection(connection_kwargs)}")
    print(f"Action: {result['action']}")
    print(f"Staff ID: {result['staff_id']}")
    print(f"Account ID: {result['account_id']}")
    print(f"Branch: {result['branch_name']} (ID={result['branch_id']})")
    print(f"Staff name: {result['staff_name']}")
    print(f"Position: {result['position']}")
    print(f"Created iam.account: {result['account_created']}")


if __name__ == "__main__":
    main()
