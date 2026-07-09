from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.file_path import PROVINCE_SQL_FILE
from src.utils.load_connection import (
    add_loader_connection_args,
    build_connection_kwargs,
    describe_connection,
)

try:
    import psycopg
except ImportError as exc:  # pragma: no cover - runtime dependency guard
    raise ImportError(
        "Missing dependency 'psycopg'. Run `uv sync` after updating pyproject.toml."
    ) from exc


INSERT_PATTERN = re.compile(
    r"(INSERT\s+INTO\s+iam\.province\s*\(.*?ON\s+CONFLICT\s*\(province_id\)\s*DO\s+UPDATE\s+SET.*?;)",
    re.IGNORECASE | re.DOTALL,
)


def extract_province_upsert_sql(input_file: Path) -> str:
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    content = input_file.read_text(encoding="utf-8")
    match = INSERT_PATTERN.search(content)
    if not match:
        raise ValueError(
            f"Could not find province upsert statement in {input_file}"
        )

    return match.group(1).strip()


def sync_provinces(
    province_sql: str,
    connection_kwargs: dict[str, str | int],
) -> tuple[int, int]:
    with psycopg.connect(**connection_kwargs) as connection:
        with connection.cursor() as cursor:
            cursor.execute(province_sql)
            affected_count = cursor.rowcount
            cursor.execute("SELECT COUNT(*) FROM iam.province")
            total_count = int(cursor.fetchone()[0])

        connection.commit()

    return affected_count, total_count


def print_summary(
    connection_label: str,
    affected_count: int,
    total_count: int,
) -> None:
    print(f"Target database: {connection_label}")
    print(f"Input file: {PROVINCE_SQL_FILE}")
    print(
        "Executed province upsert from SQL seed file "
        "(INSERT ... ON CONFLICT DO UPDATE)."
    )
    print(f"Affected rows: {affected_count}")
    print(f"Total provinces in iam.province: {total_count}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Execute province seed SQL into iam.province."
    )
    add_loader_connection_args(parser)
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()
    connection_kwargs = build_connection_kwargs(args)
    province_sql = extract_province_upsert_sql(PROVINCE_SQL_FILE)
    affected_count, total_count = sync_provinces(province_sql, connection_kwargs)
    print_summary(
        connection_label=describe_connection(connection_kwargs),
        affected_count=affected_count,
        total_count=total_count,
    )


if __name__ == "__main__":
    main()
