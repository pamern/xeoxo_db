from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import psycopg
    from psycopg import sql
except ImportError as exc:  # pragma: no cover - dependency guard
    raise SystemExit(
        "Missing dependency 'psycopg'. Run `uv sync` before using this script."
    ) from exc

from src.utils.load_connection import (
    LOCAL_DB_URL,
    build_connection_kwargs,
    describe_connection,
)


MIGRATIONS_DIR = PROJECT_ROOT / "supabase" / "migrations"
LOAD_SCRIPT = PROJECT_ROOT / "scripts" / "load_all_master_data.py"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"

BUSINESS_SCHEMAS = (
    "support",
    "sales",
    "inventory",
    "customization",
    "catalog",
    "iam",
    "metadata",
    "util",
)

MIGRATION_HISTORY_CANDIDATES = (
    ("supabase_migrations", "schema_migrations"),
    ("auth", "schema_migrations"),
)

STORAGE_RELATED_LOAD_STEPS = {
    "material_media",
}


@dataclass(frozen=True)
class MigrationFile:
    version: str
    path: Path


@dataclass(frozen=True)
class AuthResyncStats:
    account_inserted: int
    customer_inserted: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reset business schemas while preserving Supabase-managed storage/auth, "
            "then re-apply migrations and reload master data."
        )
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help=f"Target local database at {LOCAL_DB_URL}.",
    )
    parser.add_argument(
        "--db-url",
        help="Override the target PostgreSQL connection URL.",
    )
    parser.add_argument(
        "--skip-load",
        action="store_true",
        help="Only reset schemas and apply migrations, do not load master data.",
    )
    parser.add_argument(
        "--skip-auth-resync",
        action="store_true",
        help=(
            "Do not backfill iam.account and iam.customer from auth.users after reset. "
            "By default the script re-syncs auth users into business tables."
        ),
    )
    parser.add_argument(
        "--skip-storage-loaders",
        action="store_true",
        help=(
            "Skip loader steps that may upload or sync Supabase Storage objects. "
            "Useful when storage is already populated and should remain untouched."
        ),
    )
    parser.add_argument(
        "--only",
        nargs="+",
        help="Run only specific loader steps after migrations.",
    )
    parser.add_argument(
        "--skip",
        nargs="+",
        default=[],
        help="Skip specific loader steps after migrations.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Bypass the destructive-action confirmation prompt.",
    )
    return parser.parse_args()


def require_confirmation(target: str, args: argparse.Namespace) -> None:
    if args.yes:
        return

    print("This will permanently DROP and recreate the business schemas:")
    print(", ".join(BUSINESS_SCHEMAS))
    print(f"Target database: {target}")
    print("Preserved schemas include managed Supabase namespaces such as storage/auth.")
    answer = input("Type 'reset' to continue: ").strip().lower()
    if answer != "reset":
        raise SystemExit("Aborted by user.")


def list_migration_files() -> list[MigrationFile]:
    migration_files: list[MigrationFile] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = path.name.split("_", 1)[0]
        migration_files.append(MigrationFile(version=version, path=path))
    if not migration_files:
        raise RuntimeError(f"No SQL migration files found in {MIGRATIONS_DIR}.")
    return migration_files


def drop_business_schemas(connection: psycopg.Connection) -> None:
    with connection.cursor() as cursor:
        for schema_name in BUSINESS_SCHEMAS:
            print(f"Dropping schema {schema_name} ...")
            cursor.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    sql.Identifier(schema_name)
                )
            )


def execute_migration_files(
    connection: psycopg.Connection,
    migration_files: list[MigrationFile],
) -> None:
    with connection.cursor() as cursor:
        for migration in migration_files:
            print(f"Applying migration {migration.path.name} ...")
            cursor.execute(migration.path.read_text(encoding="utf-8"))


def _find_history_table(
    connection: psycopg.Connection,
) -> tuple[str, str] | None:
    with connection.cursor() as cursor:
        for schema_name, table_name in MIGRATION_HISTORY_CANDIDATES:
            cursor.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_name = %s
                """,
                (schema_name, table_name),
            )
            if cursor.fetchone():
                return schema_name, table_name
    return None


def sync_migration_history(
    connection: psycopg.Connection,
    migration_files: list[MigrationFile],
) -> None:
    history_target = _find_history_table(connection)
    if history_target is None:
        print("Migration history table was not found. Skipping history sync.")
        return

    schema_name, table_name = history_target
    print(f"Syncing migration history in {schema_name}.{table_name} ...")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
            ORDER BY ordinal_position
            """,
            (schema_name, table_name),
        )
        columns = [row[0] for row in cursor.fetchall()]

        if "version" not in columns:
            print(
                "Migration history table does not expose a 'version' column. "
                "Skipping history sync."
            )
            return

        delete_stmt = sql.SQL("DELETE FROM {}.{} WHERE version = ANY(%s)").format(
            sql.Identifier(schema_name),
            sql.Identifier(table_name),
        )
        cursor.execute(delete_stmt, ([migration.version for migration in migration_files],))

        insert_columns = ["version"]
        for optional_column in ("name",):
            if optional_column in columns:
                insert_columns.append(optional_column)

        insert_stmt = sql.SQL("INSERT INTO {}.{} ({}) VALUES ({})").format(
            sql.Identifier(schema_name),
            sql.Identifier(table_name),
            sql.SQL(", ").join(sql.Identifier(column) for column in insert_columns),
            sql.SQL(", ").join(sql.Placeholder() for _ in insert_columns),
        )

        for migration in migration_files:
            values: list[str] = [migration.version]
            if "name" in insert_columns:
                values.append(migration.path.name)
            cursor.execute(insert_stmt, values)


def build_loader_command(args: argparse.Namespace) -> list[str]:
    python_executable = (
        str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
    )
    command = [python_executable, str(LOAD_SCRIPT), "--include-unsafe"]

    effective_skip = list(args.skip)
    if args.skip_storage_loaders:
        effective_skip.extend(
            sorted(step for step in STORAGE_RELATED_LOAD_STEPS if step not in effective_skip)
        )

    if args.only:
        command.append("--only")
        command.extend(args.only)

    if effective_skip:
        command.append("--skip")
        command.extend(effective_skip)

    return command


def run_master_data_load(args: argparse.Namespace) -> None:
    command = build_loader_command(args)
    env = dict(os.environ)
    if args.db_url:
        env["SUPABASE_DB_URL"] = args.db_url
    elif args.local:
        env["SUPABASE_DB_URL"] = LOCAL_DB_URL

    print("Running master-data loaders ...")
    print("Loader command prepared.")
    subprocess.run(command, cwd=PROJECT_ROOT, env=env, check=True)


def _extract_customer_name(raw_user_meta_data: object) -> str | None:
    if not isinstance(raw_user_meta_data, dict):
        return None

    for key in ("full_name", "name", "display_name"):
        value = raw_user_meta_data.get(key)
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
    return None


def resync_auth_profiles(connection: psycopg.Connection) -> AuthResyncStats:
    print("Re-syncing auth.users into iam.account and iam.customer ...")

    with connection.cursor(row_factory=psycopg.rows.dict_row) as cursor:
        cursor.execute(
            """
            SELECT
                u.id AS account_id,
                u.email,
                u.phone,
                u.raw_user_meta_data,
                u.created_at,
                u.updated_at
            FROM auth.users AS u
            LEFT JOIN iam.account AS a
                ON a.account_id = u.id
            WHERE a.account_id IS NULL
            ORDER BY u.created_at NULLS FIRST, u.id
            """
        )
        auth_users_to_backfill = cursor.fetchall()

    if not auth_users_to_backfill:
        print("No missing auth users found for resync.")
        return AuthResyncStats(account_inserted=0, customer_inserted=0)

    account_inserted = 0
    customer_inserted = 0

    with connection.cursor() as cursor:
        for row in auth_users_to_backfill:
            created_at = row.get("created_at")
            updated_at = row.get("updated_at")

            cursor.execute(
                """
                INSERT INTO iam.account (
                    account_id,
                    role,
                    is_active,
                    created_at,
                    updated_at
                )
                VALUES (
                    %(account_id)s,
                    'CUSTOMER',
                    TRUE,
                    COALESCE(%(created_at)s, NOW()),
                    %(updated_at)s
                )
                ON CONFLICT (account_id) DO NOTHING
                """,
                {
                    "account_id": row["account_id"],
                    "created_at": created_at,
                    "updated_at": updated_at,
                },
            )
            account_inserted += cursor.rowcount

            cursor.execute(
                """
                INSERT INTO iam.customer (
                    account_id,
                    customer_name,
                    email,
                    phone,
                    customer_type,
                    created_at,
                    updated_at
                )
                SELECT
                    %(account_id)s,
                    %(customer_name)s,
                    %(email)s,
                    %(phone)s,
                    'MEMBER',
                    COALESCE(%(created_at)s, NOW()),
                    %(updated_at)s
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM iam.customer AS c
                    WHERE c.account_id = %(account_id)s
                )
                AND EXISTS (
                    SELECT 1
                    FROM iam.account AS a
                    WHERE a.account_id = %(account_id)s
                      AND a.role = 'CUSTOMER'
                )
                """,
                {
                    "account_id": row["account_id"],
                    "customer_name": _extract_customer_name(
                        row.get("raw_user_meta_data")
                    ),
                    "email": row.get("email"),
                    "phone": row.get("phone"),
                    "created_at": created_at,
                    "updated_at": updated_at,
                },
            )
            customer_inserted += cursor.rowcount

    print(
        "Auth resync complete: "
        f"{account_inserted} iam.account row(s), "
        f"{customer_inserted} iam.customer row(s)."
    )
    return AuthResyncStats(
        account_inserted=account_inserted,
        customer_inserted=customer_inserted,
    )


def main() -> int:
    args = parse_args()
    connection_kwargs = build_connection_kwargs(args)
    target = describe_connection(connection_kwargs)
    require_confirmation(target, args)

    migration_files = list_migration_files()

    conn_kwargs = dict(connection_kwargs)
    conn_kwargs["autocommit"] = True

    print(f"Target database: {target}")
    print(f"Found {len(migration_files)} migrations.")

    with psycopg.connect(**conn_kwargs) as connection:
        drop_business_schemas(connection)
        execute_migration_files(connection, migration_files)
        sync_migration_history(connection, migration_files)

    if not args.skip_load:
        run_master_data_load(args)
    else:
        print("Skipping master-data load as requested.")

    if not args.skip_auth_resync:
        conn_kwargs = dict(connection_kwargs)
        conn_kwargs["autocommit"] = False
        with psycopg.connect(**conn_kwargs) as connection:
            resync_auth_profiles(connection)
            connection.commit()
    else:
        print("Skipping auth/profile resync as requested.")

    print("Database reset, migrations, and data load completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
