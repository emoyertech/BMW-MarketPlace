#!/usr/bin/env python3
"""One-command launcher for local development.

This script keeps setup beginner-friendly:
1. Ensures Python dependencies are installed.
2. Uses Docker to start PostgreSQL if it is not already running.
3. Migrates legacy SQLite data once (if present).
4. Starts the web app.

Usage:
    python3 scripts/easy_start.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:5432/bmw_marketplace"


def run_command(cmd: list[str], root: Path, check: bool = True) -> subprocess.CompletedProcess:
    print("$", " ".join(cmd))
    return subprocess.run(cmd, cwd=root, check=check)


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def ensure_dependencies(root: Path) -> None:
    try:
        import psycopg  # noqa: F401
    except ModuleNotFoundError:
        print("Installing Python dependencies...")
        run_command([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], root)


def postgres_ready(database_url: str) -> bool:
    try:
        import psycopg

        with psycopg.connect(database_url, connect_timeout=2):
            return True
    except Exception:
        return False


def ensure_postgres(root: Path, database_url: str) -> bool:
    if postgres_ready(database_url):
        return True

    if not command_exists("docker"):
        return False

    print("PostgreSQL not reachable yet. Trying to start Docker database service...")
    run_command(["docker", "compose", "up", "-d", "--force-recreate", "db"], root, check=False)

    for _ in range(60):
        if postgres_ready(database_url):
            return True
        time.sleep(1)
    return False


def maybe_migrate(root: Path) -> None:
    sqlite_path = root / "data" / "marketplace.db"
    marker = root / "data" / ".postgres_migrated"

    if not sqlite_path.exists() or marker.exists():
        return

    print("Found legacy SQLite data. Running one-time migration...")
    result = run_command([sys.executable, "scripts/migrate_sqlite_to_postgres.py"], root, check=False)
    if result.returncode == 0:
        marker.write_text("ok\n", encoding="utf-8")


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    os.environ.setdefault("DATABASE_URL", database_url)

    ensure_dependencies(root)

    if not ensure_postgres(root, database_url):
        print("\nCould not connect to PostgreSQL.")
        print("- Start Docker Desktop, then run: docker compose up -d --force-recreate db")
        print("- Or start local PostgreSQL and set DATABASE_URL")
        raise SystemExit(1)

    maybe_migrate(root)

    print("\nStarting app at http://127.0.0.1:8000")
    os.environ["BMW_MARKETPLACE_DATA_DIR"] = "data"
    os.execv(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "scripts.home_page:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
    )


if __name__ == "__main__":
    main()
