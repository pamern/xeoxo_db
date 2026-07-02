from __future__ import annotations

import argparse
from pathlib import PurePosixPath
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.connection_db import get_bucket_name, get_supabase_client


LIST_LIMIT = 100
REMOVE_BATCH_SIZE = 100


def normalize_prefix(value: str) -> str:
    prefix = str(PurePosixPath(value.strip()))
    if prefix in {".", "/"}:
        raise ValueError("Prefix must not be empty or root.")
    return prefix.strip("/")


def join_prefix(prefix: str, name: str) -> str:
    return f"{prefix}/{name}" if prefix else name


def is_file_object(item: dict) -> bool:
    return bool(item.get("id")) or isinstance(item.get("metadata"), dict)


def list_objects_recursive(client, bucket_name: str, prefix: str) -> list[str]:
    paths: list[str] = []
    subfolders: list[str] = []
    offset = 0

    while True:
        items = client.storage.from_(bucket_name).list(
            prefix,
            {
                "limit": LIST_LIMIT,
                "offset": offset,
                "sortBy": {"column": "name", "order": "asc"},
            },
        )

        if not isinstance(items, list):
            raise ValueError(f"Unexpected list response for prefix {prefix!r}: {items!r}")

        if not items:
            break

        for item in items:
            name = item.get("name")
            if not name:
                continue

            child_prefix = join_prefix(prefix, name)
            if is_file_object(item):
                paths.append(child_prefix)
            else:
                subfolders.append(child_prefix)

        if len(items) < LIST_LIMIT:
            break

        offset += LIST_LIMIT

    for subfolder in subfolders:
        paths.extend(list_objects_recursive(client, bucket_name, subfolder))

    return paths


def chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def remove_objects(client, bucket_name: str, paths: list[str]) -> int:
    removed_count = 0

    for batch in chunked(paths, REMOVE_BATCH_SIZE):
        result = client.storage.from_(bucket_name).remove(batch)
        if isinstance(result, list):
            removed_count += len(batch)
            continue

        raise ValueError(f"Unexpected remove response for batch {batch!r}: {result!r}")

    return removed_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Delete all Supabase Storage objects under a prefix."
    )
    parser.add_argument(
        "prefix",
        help="Storage prefix to reset, for example: product-lines/ao-dai-vu-lang",
    )
    parser.add_argument(
        "--bucket",
        default=get_bucket_name(),
        help="Bucket name. Defaults to configured Supabase bucket.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete objects. Without this flag, the script only previews.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prefix = normalize_prefix(args.prefix)
    client = get_supabase_client()

    print(f"Bucket: {args.bucket}")
    print(f"Prefix: {prefix}")
    print("Listing objects...")

    paths = sorted(set(list_objects_recursive(client, args.bucket, prefix)))
    print(f"Found {len(paths)} object(s).")

    if not paths:
        return 0

    preview_count = min(20, len(paths))
    print("Preview:")
    for path in paths[:preview_count]:
        print(f"- {path}")
    if len(paths) > preview_count:
        print(f"... and {len(paths) - preview_count} more")

    if not args.execute:
        print("\nDry run only. Re-run with --execute to delete these objects.")
        return 0

    print("\nDeleting objects...")
    removed_count = remove_objects(client, args.bucket, paths)
    print(f"Deleted {removed_count} object(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
