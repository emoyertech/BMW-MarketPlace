#!/usr/bin/env python3
"""One-time migration from SQLite to PostgreSQL for BMW Marketplace.

Usage:
    python3 scripts/migrate_sqlite_to_postgres.py
    python3 scripts/migrate_sqlite_to_postgres.py --sqlite-path data/marketplace.db
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

from marketplace_core import _load_psycopg, db_path_for, init_db

DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:5432/bmw_marketplace"


def _connection_error_message(database_url: str) -> str:
    return (
        "Could not connect to PostgreSQL.\n"
        f"DATABASE_URL: {database_url}\n\n"
        "Start PostgreSQL, then run migration again.\n"
        "If using Docker Compose: docker compose up -d db\n"
        "If using local PostgreSQL: make sure port 5432 is running and credentials match DATABASE_URL."
    )


def table_exists_sqlite(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def migrate_table(sqlite_conn: sqlite3.Connection, pg_conn, table: str, columns: list[str], conflict_key: str) -> int:
    if not table_exists_sqlite(sqlite_conn, table):
        return 0

    column_csv = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    query = f"SELECT {column_csv} FROM {table}"
    rows = sqlite_conn.execute(query).fetchall()
    if not rows:
        return 0

    insert_sql = (
        f"INSERT INTO {table} ({column_csv}) VALUES ({placeholders}) "
        f"ON CONFLICT ({conflict_key}) DO NOTHING"
    )
    with pg_conn.cursor() as cur:
        cur.executemany(insert_sql, rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate SQLite marketplace data into PostgreSQL")
    parser.add_argument("--sqlite-path", default="data/marketplace.db", help="Path to SQLite DB file")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL),
        help="PostgreSQL connection URL",
    )
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite_path)
    if not sqlite_path.exists():
        raise SystemExit(f"SQLite database not found: {sqlite_path}")

    try:
        psycopg = _load_psycopg()
    except RuntimeError as exc:
        raise SystemExit(
            "PostgreSQL driver not installed. Run: python3 -m pip install -r requirements.txt"
        ) from exc

    try:
        # Ensure PostgreSQL schema exists before inserting records.
        os.environ["DATABASE_URL"] = args.database_url
        init_db(db_path_for(Path("data")))

        with sqlite3.connect(sqlite_path) as sqlite_conn, psycopg.connect(args.database_url) as pg_conn:
            migrated_users = migrate_table(
                sqlite_conn,
                pg_conn,
                "app_users",
                ["user_id", "full_name", "email", "password_hash", "created_at"],
                "user_id",
            )
            migrated_sessions = migrate_table(
                sqlite_conn,
                pg_conn,
                "app_sessions",
                ["session_token", "user_id", "expires_at", "created_at"],
                "session_token",
            )
            migrated_listings = migrate_table(
                sqlite_conn,
                pg_conn,
                "user_listings",
                [
                    "listing_id",
                    "seller_user_id",
                    "seller_name",
                    "seller_email",
                    "seller_type",
                    "vin",
                    "model",
                    "trim",
                    "body_style",
                    "drive_type",
                    "title_type",
                    "image_url",
                    "gallery_images_json",
                    "description",
                    "year",
                    "mileage",
                    "price",
                    "location",
                    "status",
                    "created_at",
                    "updated_at",
                    "expires_at",
                    "reminder_24h_sent_at",
                    "reminder_1h_sent_at",
                    "reminder_5m_sent_at",
                ],
                "listing_id",
            )
            pg_conn.commit()
    except psycopg.OperationalError as exc:
        raise SystemExit(_connection_error_message(args.database_url)) from exc

    print("Migration complete")
    print(f"- app_users rows read: {migrated_users}")
    print(f"- app_sessions rows read: {migrated_sessions}")
    print(f"- user_listings rows read: {migrated_listings}")


if __name__ == "__main__":
    main()
