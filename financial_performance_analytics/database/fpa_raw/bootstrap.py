from __future__ import annotations

import argparse
import os
from pathlib import Path

from .schema import generate_schema_sql


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create the PostgreSQL schemas and typed RAW tables.")
    parser.add_argument("dataset_root", type=Path)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--print-ddl", action="store_true")
    parser.add_argument("--check", action="store_true", help="Validate files and DDL generation without a database.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ddl, _ = generate_schema_sql(args.dataset_root.resolve())
    if args.check:
        print(f"Source headers validated; generated {ddl.count('CREATE TABLE')} tables and {ddl.count('CREATE OR REPLACE VIEW')} views.")
    if args.print_ddl:
        print(ddl)
    if not args.database_url:
        if not args.print_ddl and not args.check:
            raise SystemExit("Set DATABASE_URL, pass --check, or pass --print-ddl.")
        return
    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("Install database/requirements.txt before applying the schema.") from exc
    with psycopg.connect(args.database_url, autocommit=True) as connection:
        connection.execute(ddl)
    print("RAW schema created or verified successfully.")


if __name__ == "__main__":
    main()
