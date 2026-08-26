from __future__ import annotations

import argparse
import os

from .schema import DIMENSIONS, FACTS, generate_marts_sql


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or rebuild the PostgreSQL MARTS layer.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--check", action="store_true", help="Compile the dimensional SQL without changing the database.")
    args = parser.parse_args()

    ddl = generate_marts_sql()
    if args.check:
        print(f"MARTS contracts compiled: {len(DIMENSIONS)} dimensions and {len(FACTS)} facts.")
        return
    if not args.database_url:
        raise SystemExit("Set DATABASE_URL before applying MARTS.")
    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("Install database/requirements.txt before applying MARTS.") from exc

    with psycopg.connect(args.database_url) as connection:
        connection.execute(ddl)
        connection.commit()

    print(f"MARTS created successfully: {len(DIMENSIONS)} dimensions and {len(FACTS)} facts materialized.")


if __name__ == "__main__":
    main()
