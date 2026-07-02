from __future__ import annotations

import argparse
from urllib.parse import urlparse

from src.utils.connection_db import get_postgres_connection_kwargs


LOCAL_DB_URL = "postgresql://postgres:postgres@127.0.0.1:15432/postgres"


def describe_connection(connection_kwargs: dict[str, str | int]) -> str:
    conninfo = connection_kwargs.get("conninfo")
    if isinstance(conninfo, str):
        parsed = urlparse(conninfo)
        host = parsed.hostname or "unknown-host"
        port = parsed.port or "default-port"
        database = parsed.path.lstrip("/") or "unknown-db"
        return f"{host}:{port}/{database}"

    host = connection_kwargs.get("host", "unknown-host")
    port = connection_kwargs.get("port", "default-port")
    database = connection_kwargs.get("dbname", "unknown-db")
    return f"{host}:{port}/{database}"


def add_loader_connection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--local",
        action="store_true",
        help=f"Insert into local Supabase Postgres ({LOCAL_DB_URL}).",
    )
    parser.add_argument(
        "--db-url",
        help=(
            "Override target database URL. Takes precedence over --local "
            "and .env settings."
        ),
    )


def build_connection_kwargs(args: argparse.Namespace) -> dict[str, str | int]:
    if args.db_url:
        return {"conninfo": args.db_url}

    if args.local:
        return {"conninfo": LOCAL_DB_URL}

    return get_postgres_connection_kwargs()
