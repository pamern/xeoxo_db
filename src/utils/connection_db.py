import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import Client, create_client


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
ENV_LOCAL_FILE = PROJECT_ROOT / ".env.local"
DEFAULT_BUCKET_NAME = "product-media"


def load_env() -> None:
    load_dotenv(ENV_FILE)
    load_dotenv(ENV_LOCAL_FILE, override=True)


def _infer_project_ref() -> str | None:
    project_ref = os.getenv("SUPABASE_PROJECT_REF")
    if project_ref:
        return project_ref

    supabase_user = os.getenv("SUPABASE_USER")
    if supabase_user and "." in supabase_user:
        _, ref = supabase_user.split(".", 1)
        return ref or None

    return None


def get_supabase_url() -> str:
    load_env()

    supabase_url = os.getenv("SUPABASE_URL")
    if supabase_url:
        return supabase_url

    project_ref = _infer_project_ref()
    if project_ref:
        return f"https://{project_ref}.supabase.co"

    raise ValueError(
        "Missing SUPABASE_URL in .env and cannot infer project ref. "
        "Set SUPABASE_URL or SUPABASE_PROJECT_REF."
    )


def get_supabase_key() -> str:
    load_env()

    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if service_role_key:
        return service_role_key

    secret_key = os.getenv("SUPABASE_SECRET_KEY")
    if secret_key:
        return secret_key

    anon_key = os.getenv("SUPABASE_ANON_KEY")
    if anon_key:
        return anon_key

    publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY")
    if publishable_key:
        return publishable_key

    raise ValueError(
        "Missing Supabase API key in .env. Expected one of: "
        "SUPABASE_SERVICE_ROLE_KEY, SUPABASE_SECRET_KEY, "
        "SUPABASE_ANON_KEY, SUPABASE_PUBLISHABLE_KEY."
    )


def get_supabase_client() -> Client:
    return create_client(get_supabase_url(), get_supabase_key())


def get_postgres_connection_kwargs() -> dict[str, str | int]:
    load_env()

    database_url = os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL")
    if database_url:
        return {"conninfo": database_url}

    host = os.getenv("SUPABASE_HOST")
    port = os.getenv("SUPABASE_PORT")
    dbname = os.getenv("SUPABASE_NAME")
    user = os.getenv("SUPABASE_USER")
    password = os.getenv("SUPABASE_PASSWORD")
    sslmode = os.getenv("SUPABASE_DB_SSLMODE", "require")

    missing = [
        name
        for name, value in {
            "SUPABASE_HOST": host,
            "SUPABASE_PORT": port,
            "SUPABASE_NAME": dbname,
            "SUPABASE_USER": user,
            "SUPABASE_PASSWORD": password,
        }.items()
        if not value
    ]

    if missing:
        raise ValueError(
            "Missing PostgreSQL connection settings in .env: "
            f"{', '.join(missing)}"
        )

    return {
        "host": host,
        "port": int(port),
        "dbname": dbname,
        "user": user,
        "password": password,
        "sslmode": sslmode,
    }


def get_bucket_name(default: str = DEFAULT_BUCKET_NAME) -> str:
    load_env()
    return (
        os.getenv("SUPABASE_BUCKET_NAME")
        or os.getenv("SUPABASE_BUCKET")
        or default
    )


def get_overwrite_flag(default: bool = False) -> bool:
    load_env()
    return os.getenv("OVERWRITE", str(default)).lower() == "true"


def test_connection() -> None:
    client = get_supabase_client()
    bucket_name = get_bucket_name()

    buckets = client.storage.list_buckets()
    bucket_names = [
        bucket.get("name") if isinstance(bucket, dict) else getattr(bucket, "name", None)
        for bucket in buckets
    ]

    print("Connected to Supabase successfully")
    print("Supabase URL:", get_supabase_url())
    print("Configured bucket:", bucket_name)
    print("Available buckets:", [name for name in bucket_names if name])
