from __future__ import annotations

import argparse
import os
from pathlib import Path

from .schema import generate_staging_sql


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update the PostgreSQL STAGING views.")
    parser.add_argument("dataset_root", type=Path)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--check", action="store_true", help="Validate contracts without changing the database.")
    args = parser.parse_args()

    ddl, headers = generate_staging_sql(args.dataset_root.resolve())
    if args.check:
        print(f"STAGING contracts validated: {len(headers)} views and {sum(map(len, headers.values()))} source columns.")
        return
    if not args.database_url:
        raise SystemExit("Set DATABASE_URL before applying STAGING.")
    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("Install database/requirements.txt before applying STAGING.") from exc
    with psycopg.connect(args.database_url, autocommit=True) as connection:
        connection.execute(ddl)
    print(f"STAGING created or updated successfully: {len(headers)} views.")


if __name__ == "__main__":
    main()

