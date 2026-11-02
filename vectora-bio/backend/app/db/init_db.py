"""Create the application tables: ``python -m app.db.init_db``."""

import sys

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_engine, init_db, safe_database_url


def main() -> int:
    print(f"Database: {safe_database_url()}")
    try:
        init_db()
        tables = sorted(inspect(get_engine()).get_table_names())
    except SQLAlchemyError as exc:
        print(f"Could not create tables: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 1
    print("Tables: " + ", ".join(tables))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
