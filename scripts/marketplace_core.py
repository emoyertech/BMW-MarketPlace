#!/usr/bin/env python3
"""Serve a simple BMW Marketplace homepage from local seed JSON data.

Usage:
    python3 scripts/home_page.py
Then open http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import html
import hashlib
import hmac
import importlib
import json
import mimetypes
import os
import re
import secrets
import urllib.parse
import uuid
from http.cookies import SimpleCookie
from email.parser import BytesParser
from email.policy import default
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime, timedelta, timezone


BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "html_css"
TEMPLATE_PATH = TEMPLATE_DIR / "home_page.html"
CSS_PATH = TEMPLATE_DIR / "home_page.css"
CARD_TEMPLATE_PATH = TEMPLATE_DIR / "home_page_card.html"
DETAIL_TEMPLATE_PATH = TEMPLATE_DIR / "listing_detail.html"
FORM_TEMPLATE_PATH = TEMPLATE_DIR / "listing_form.html"
EDIT_TEMPLATE_PATH = TEMPLATE_DIR / "listing_edit.html"
LOGIN_TEMPLATE_PATH = TEMPLATE_DIR / "login.html"
REGISTER_TEMPLATE_PATH = TEMPLATE_DIR / "register.html"
SETTINGS_TEMPLATE_PATH = TEMPLATE_DIR / "settings.html"
UPLOADS_DIR_NAME = "uploads"
SEED_IMAGES_DIR_NAME = "seed-images"
IMAGE_PLACEHOLDER_URL = (
    "data:image/svg+xml;utf8,"
    "%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20viewBox%3D%270%200%201200%20800%27%3E"
    "%3Cdefs%3E%3ClinearGradient%20id%3D%27bg%27%20x1%3D%270%27%20y1%3D%270%27%20x2%3D%271%27%20y2%3D%271%27%3E"
    "%3Cstop%20offset%3D%270%25%27%20stop-color%3D%27%2308111f%27/%3E"
    "%3Cstop%20offset%3D%27100%25%27%20stop-color%3D%27%231d4ed8%27/%3E"
    "%3C/linearGradient%3E%3C/defs%3E"
    "%3Crect%20width%3D%271200%27%20height%3D%27800%27%20fill%3D%27url%28%23bg%29%27/%3E"
    "%3Ccircle%20cx%3D%27180%27%20cy%3D%27150%27%20r%3D%27100%27%20fill%3D%27rgba%28255%2C255%2C255%2C0.08%29%27/%3E"
    "%3Ccircle%20cx%3D%271000%27%20cy%3D%27160%27%20r%3D%27140%27%20fill%3D%27rgba%28255%2C255%2C255%2C0.08%29%27/%3E"
    "%3Ccircle%20cx%3D%27980%27%20cy%3D%27640%27%20r%3D%27160%27%20fill%3D%27rgba%28255%2C255%2C255%2C0.08%29%27/%3E"
    "%3Ctext%20x%3D%2760%27%20y%3D%27110%27%20fill%3D%27white%27%20font-size%3D%2754%27%20font-family%3D%27Segoe%20UI%2C%20Arial%2C%20sans-serif%27%20font-weight%3D%27700%27%3EBMW%20Listing%3C/text%3E"
    "%3Ctext%20x%3D%2760%27%20y%3D%27162%27%20fill%3D%27%23dbeafe%27%20font-size%3D%2730%27%20font-family%3D%27Segoe%20UI%2C%20Arial%2C%20sans-serif%27%3EImage%20unavailable%3C/text%3E"
    "%3Crect%20x%3D%27170%27%20y%3D%27360%27%20width%3D%27860%27%20height%3D%27150%27%20rx%3D%2732%27%20fill%3D%27rgba%28255%2C255%2C255%2C0.92%29%27/%3E"
    "%3Crect%20x%3D%27330%27%20y%3D%27300%27%20width%3D%27420%27%20height%3D%27110%27%20rx%3D%2728%27%20fill%3D%27rgba%28255%2C255%2C255%2C0.88%29%27/%3E"
    "%3Ccircle%20cx%3D%27330%27%20cy%3D%27560%27%20r%3D%2764%27%20fill%3D%27%23111827%27/%3E"
    "%3Ccircle%20cx%3D%27330%27%20cy%3D%27560%27%20r%3D%2728%27%20fill%3D%27%239ca3af%27/%3E"
    "%3Ccircle%20cx%3D%27870%27%20cy%3D%27560%27%20r%3D%2764%27%20fill%3D%27%23111827%27/%3E"
    "%3Ccircle%20cx%3D%27870%27%20cy%3D%27560%27%20r%3D%2728%27%20fill%3D%27%239ca3af%27/%3E"
    "%3C/svg%3E"
)
CARFAX_BASE_URL = "https://www.carfax.com/VehicleHistory/p/Report.cfx?vin="
NHTSA_RECALLS_BASE_URL = "https://www.nhtsa.gov/recalls?vymm="
NHTSA_RECALLS_GENERIC_URL = "https://www.nhtsa.gov/recalls"
DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:5432/bmw_marketplace"
ADMIN_EMAILS_ENV_VAR = "BMW_MARKETPLACE_ADMIN_EMAILS"
SESSION_COOKIE_NAME = "bmw_marketplace_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 14
LISTING_TTL_SECONDS = 60 * 60 * 24 * 7
LISTING_REMINDER_INTERVALS_SECONDS = [60 * 60 * 24, 60 * 60, 5 * 60]

NOTICE_MESSAGES = {
    "created": "Listing created successfully.",
    "saved": "Listing updated successfully.",
    "refreshed": "Listing kept active.",
    "pending": "Listing marked as pending.",
    "sold": "Listing marked as sold.",
    "paused": "Listing paused.",
    "active": "Listing marked as active.",
    "deleted": "Listing deleted.",
    "settings_saved": "Account settings updated successfully.",
    "dealer_application_submitted": "Dealer application submitted.",
    "dealer_approved": "Dealer approved.",
    "dealer_rejected": "Dealer rejected.",
    "dealer_suspended": "Dealer suspended.",
    "dealer_member_added": "Dealer member added.",
    "dealer_reply_sent": "Reply sent to the buyer.",
    "inquiry_submitted": "Your message was sent to the seller.",
    "action_failed": "We could not complete that action.",
}


def load_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_inquiries(data_dir: Path) -> list[dict]:
    return load_json(data_dir / "inquiries.json")


def load_messages(data_dir: Path) -> list[dict]:
    return load_json(data_dir / "messages.json")


def write_json(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)


def db_path_for(data_dir: Path) -> Path:
    return data_dir


class DbConnection:
    def __init__(self, inner):
        self._inner = inner

    def __enter__(self) -> "DbConnection":
        self._inner.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._inner.__exit__(exc_type, exc, tb)

    def execute(self, query: str, params: tuple | list | None = None):
        # Keep SQL in app code beginner-friendly by supporting sqlite-style placeholders.
        normalized_query = query.replace("?", "%s")
        if params is None:
            return self._inner.execute(normalized_query)
        return self._inner.execute(normalized_query, params)


def _database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def _load_psycopg():
    try:
        return importlib.import_module("psycopg")
    except ModuleNotFoundError as exc:
        raise RuntimeError("Missing dependency: install requirements.txt to use PostgreSQL") from exc


def db_connect() -> DbConnection:
    return DbConnection(_load_psycopg().connect(_database_url()))


def _is_db_integrity_error(exc: Exception) -> bool:
    return exc.__class__.__name__ == "IntegrityError"


def uploads_dir_for(data_dir: Path) -> Path:
    return data_dir / UPLOADS_DIR_NAME


def seed_images_dir_for(data_dir: Path) -> Path:
    return data_dir / SEED_IMAGES_DIR_NAME


def sanitize_filename(value: str) -> str:
    base = os.path.basename(value or "")
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    return cleaned or "upload"


def save_uploaded_image(data_dir: Path, filename: str, content: bytes, content_type: str) -> str:
    if not content:
        return ""
    if not content_type.startswith("image/"):
        return ""

    uploads_dir = uploads_dir_for(data_dir)
    uploads_dir.mkdir(parents=True, exist_ok=True)

    source_name = sanitize_filename(filename)
    suffix = Path(source_name).suffix.lower()
    if not suffix:
        guessed = mimetypes.guess_extension(content_type) or ".img"
        suffix = guessed.lower()

    final_name = f"{uuid.uuid4().hex}{suffix}"
    output_path = uploads_dir / final_name
    output_path.write_bytes(content)
    return f"/{UPLOADS_DIR_NAME}/{final_name}"


def read_static_image(image_dir: Path, file_name: str) -> tuple[bytes, str] | None:
    file_path = image_dir / file_name
    if not file_path.exists() or not file_path.is_file():
        return None

    body = file_path.read_bytes()
    content_type, _ = mimetypes.guess_type(file_path.name)
    return body, content_type or "application/octet-stream"


def _ensure_column(conn, table_name: str, column_name: str, column_definition: str) -> None:
    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_name} {column_definition}")


def init_db(db_path: Path) -> None:
    del db_path
    with db_connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_listings (
                listing_id TEXT PRIMARY KEY,
                seller_user_id TEXT,
                seller_name TEXT NOT NULL,
                seller_email TEXT NOT NULL,
                seller_type TEXT NOT NULL,
                dealer_id TEXT,
                seller_verified BOOLEAN NOT NULL DEFAULT FALSE,
                vin TEXT,
                model TEXT NOT NULL,
                trim TEXT,
                body_style TEXT,
                drive_type TEXT,
                title_type TEXT,
                image_url TEXT,
                gallery_images_json TEXT,
                description TEXT,
                year INTEGER NOT NULL,
                mileage INTEGER NOT NULL,
                price INTEGER NOT NULL,
                location TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                expires_at TEXT,
                reminder_24h_sent_at TEXT,
                reminder_1h_sent_at TEXT,
                reminder_5m_sent_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_users (
                user_id TEXT PRIMARY KEY,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'BUYER',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_sessions (
                session_token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES app_users(user_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dealer_profiles (
                dealer_id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL UNIQUE,
                legal_name TEXT NOT NULL,
                display_name TEXT NOT NULL,
                website_url TEXT NOT NULL DEFAULT '',
                license_number TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                rejected_reason TEXT NOT NULL DEFAULT '',
                approved_by_admin_id TEXT,
                approved_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(owner_user_id) REFERENCES app_users(user_id),
                FOREIGN KEY(approved_by_admin_id) REFERENCES app_users(user_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dealer_members (
                membership_id TEXT PRIMARY KEY,
                dealer_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                member_role TEXT NOT NULL,
                member_status TEXT NOT NULL,
                created_by_user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(dealer_id) REFERENCES dealer_profiles(dealer_id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES app_users(user_id),
                FOREIGN KEY(created_by_user_id) REFERENCES app_users(user_id),
                UNIQUE(dealer_id, user_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS verification_events (
                event_id TEXT PRIMARY KEY,
                subject_type TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                actor_user_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_status TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(actor_user_id) REFERENCES app_users(user_id)
            )
            """
        )
        _ensure_column(conn, "app_users", "role", "TEXT NOT NULL DEFAULT 'BUYER'")
        _ensure_column(conn, "user_listings", "dealer_id", "TEXT")
        _ensure_column(conn, "user_listings", "seller_verified", "BOOLEAN NOT NULL DEFAULT FALSE")
        conn.execute("UPDATE app_users SET role = COALESCE(NULLIF(role, ''), 'BUYER')")
        conn.execute("UPDATE user_listings SET seller_verified = COALESCE(seller_verified, FALSE)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dealer_inbox_state (
                inquiry_id TEXT PRIMARY KEY,
                dealer_id TEXT NOT NULL,
                assigned_user_id TEXT NOT NULL DEFAULT '',
                last_viewed_by_user_id TEXT NOT NULL DEFAULT '',
                last_viewed_at TEXT NOT NULL DEFAULT '',
                last_responded_by_user_id TEXT NOT NULL DEFAULT '',
                last_responded_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                FOREIGN KEY(dealer_id) REFERENCES dealer_profiles(dealer_id) ON DELETE CASCADE
            )
            """)


def _parse_iso_utc(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_expiry(base_time: datetime) -> str:
    return (base_time + timedelta(seconds=LISTING_TTL_SECONDS)).isoformat()


def sanitize_vin(vin: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", vin or "").upper()
    return cleaned[:17]


def carfax_url_for_vin(vin: str) -> str:
    clean_vin = sanitize_vin(vin)
    if len(clean_vin) != 17:
        return ""
    return CARFAX_BASE_URL + urllib.parse.quote(clean_vin)


def nhtsa_url_for_vin(vin: str) -> str:
    clean_vin = sanitize_vin(vin)
    if len(clean_vin) == 17:
        return NHTSA_RECALLS_BASE_URL + urllib.parse.quote(clean_vin)
    return NHTSA_RECALLS_GENERIC_URL


def vehicle_report_links_html(vin: str, compact: bool = False) -> str:
    clean_vin = sanitize_vin(vin)
    carfax = carfax_url_for_vin(clean_vin)
    nhtsa = nhtsa_url_for_vin(clean_vin)
    if compact:
        links = []
        if carfax:
            links.append(
                f'<a class="carfax-link" href="{html.escape(carfax)}" target="_blank" rel="noopener noreferrer">Carfax report</a>'
            )
        if nhtsa:
            links.append(
                f'<a class="carfax-link" href="{html.escape(nhtsa)}" target="_blank" rel="noopener noreferrer">NHTSA recalls</a>'
            )
        return " · ".join(links)
    links = []
    if carfax:
        links.append(
            f'<a class="button secondary" href="{html.escape(carfax)}" target="_blank" rel="noopener noreferrer">View Carfax report</a>'
        )
    if nhtsa:
        links.append(
            f'<a class="button secondary" href="{html.escape(nhtsa)}" target="_blank" rel="noopener noreferrer">View NHTSA recalls</a>'
        )
    return "".join(links)


def get_seed_listing_by_vin(data_dir: Path, vin: str) -> dict | None:
    target = sanitize_vin(vin)
    if len(target) != 17:
        return None
    for listing in load_json(data_dir / "listings.json"):
        candidate = sanitize_vin(str(listing.get("vin", "")))
        if candidate == target:
            return listing
    return None


def get_seed_listing_by_selection(data_dir: Path, year: str, model: str, trim: str) -> dict | None:
    y = (year or "").strip()
    m = (model or "").strip().lower()
    t = (trim or "").strip().lower()
    if not y or not m or not t:
        return None
    for listing in load_json(data_dir / "listings.json"):
        if (
            str(listing.get("year", "")).strip() == y
            and str(listing.get("model", "")).strip().lower() == m
            and str(listing.get("trim", "")).strip().lower() == t
        ):
            return listing
    return None


def expire_and_track_listing_reminders(db_path: Path) -> None:
    init_db(db_path)
    now = datetime.now(timezone.utc)
    with db_connect() as conn:
        rows = conn.execute(
            """
            SELECT listing_id, status, created_at, updated_at, expires_at,
                   reminder_24h_sent_at, reminder_1h_sent_at, reminder_5m_sent_at
            FROM user_listings
            """
        ).fetchall()
        for row in rows:
            listing_id = str(row[0])
            status = str(row[1] or "ACTIVE")
            created_at = _parse_iso_utc(str(row[2] or ""))
            updated_at = _parse_iso_utc(str(row[3] or ""))
            expires_at = _parse_iso_utc(str(row[4] or ""))
            base_time = updated_at or created_at or now
            target_expiry = expires_at or _parse_iso_utc(_compute_expiry(base_time))
            if target_expiry is None:
                target_expiry = now + timedelta(seconds=LISTING_TTL_SECONDS)
            if row[4] is None:
                conn.execute(
                    "UPDATE user_listings SET updated_at = COALESCE(updated_at, created_at), expires_at = ? WHERE listing_id = ?",
                    (target_expiry.isoformat(), listing_id),
                )

            if status == "ACTIVE" and now >= target_expiry:
                conn.execute("UPDATE user_listings SET status = 'EXPIRED' WHERE listing_id = ?", (listing_id,))
                continue

            if status != "ACTIVE":
                continue

            seconds_left = int((target_expiry - now).total_seconds())
            reminders = [
                ("reminder_24h_sent_at", 60 * 60 * 24, row[5]),
                ("reminder_1h_sent_at", 60 * 60, row[6]),
                ("reminder_5m_sent_at", 5 * 60, row[7]),
            ]
            for column_name, threshold_seconds, sent_marker in reminders:
                if sent_marker:
                    continue
                if 0 < seconds_left <= threshold_seconds:
                    conn.execute(
                        f"UPDATE user_listings SET {column_name} = ? WHERE listing_id = ?",
                        (_iso_now(), listing_id),
                    )


def _dict_from_row(row: tuple) -> dict:
    gallery_images: list[str] = []
    if row[12]:
        try:
            parsed = json.loads(row[12])
            if isinstance(parsed, list):
                gallery_images = [str(item) for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            gallery_images = []

    return {
        "listing_id": row[0],
        "seller_user_id": row[1] or "",
        "seller_name": row[2],
        "seller_email": row[3],
        "seller_type": row[4],
        "dealer_id": row[5] or "",
        "seller_verified": bool(row[6]),
        "vin": row[7] or "",
        "model": row[8],
        "trim": row[9],
        "body_style": row[10],
        "drive_type": row[11],
        "title_type": row[12],
        "image_url": row[13],
        "gallery_images": gallery_images,
        "description": row[15],
        "year": row[16],
        "mileage": row[17],
        "price": row[18],
        "location": row[19],
        "status": row[20],
        "created_at": row[21],
        "updated_at": row[22],
        "expires_at": row[23],
        "reminder_24h_sent_at": row[24],
        "reminder_1h_sent_at": row[25],
        "reminder_5m_sent_at": row[26],
    }


def load_user_listings(db_path: Path) -> list[dict]:
    init_db(db_path)
    expire_and_track_listing_reminders(db_path)
    with db_connect() as conn:
        rows = conn.execute(
            """
            SELECT
                listing_id,
                seller_user_id,
                seller_name,
                seller_email,
                seller_type,
                dealer_id,
                seller_verified,
                vin,
                model,
                trim,
                body_style,
                drive_type,
                title_type,
                image_url,
                gallery_images_json,
                description,
                year,
                mileage,
                price,
                location,
                status,
                created_at,
                updated_at,
                expires_at,
                reminder_24h_sent_at,
                reminder_1h_sent_at,
                reminder_5m_sent_at
            FROM user_listings
            ORDER BY created_at DESC
            """
        ).fetchall()
    return [_dict_from_row(row) for row in rows]


def load_all_listings(data_dir: Path) -> list[dict]:
    seed_listings = load_json(data_dir / "listings.json")
    db_listings = load_user_listings(db_path_for(data_dir))
    combined = seed_listings + db_listings
    return sorted(combined, key=lambda item: item.get("created_at", ""), reverse=True)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    parts = password_hash.split("$", 1)
    if len(parts) != 2:
        return False
    salt, expected_hex = parts
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return hmac.compare_digest(digest.hex(), expected_hex)


def create_app_user(db_path: Path, full_name: str, email: str, password: str, role: str = "BUYER") -> dict:
    init_db(db_path)
    created_at = datetime.now(timezone.utc).isoformat()
    normalized_role = str(role or "BUYER").strip().upper() or "BUYER"
    user = {
        "user_id": f"app-{uuid.uuid4().hex}",
        "full_name": full_name.strip(),
        "email": email.strip().lower(),
        "password_hash": hash_password(password),
        "role": normalized_role,
        "created_at": created_at,
    }
    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO app_users (user_id, full_name, email, password_hash, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user["user_id"],
                user["full_name"],
                user["email"],
                user["password_hash"],
                user["role"],
                user["created_at"],
            ),
        )
    return user


def create_app_user_with_id(db_path: Path, user_id: str, full_name: str, email: str, password: str, role: str = "BUYER") -> dict:
    init_db(db_path)
    clean_user_id = str(user_id or "").strip()
    if not clean_user_id:
        raise ValueError("user_id is required")
    created_at = datetime.now(timezone.utc).isoformat()
    normalized_role = str(role or "BUYER").strip().upper() or "BUYER"
    user = {
        "user_id": clean_user_id,
        "full_name": full_name.strip(),
        "email": email.strip().lower(),
        "password_hash": hash_password(password),
        "role": normalized_role,
        "created_at": created_at,
    }
    with db_connect() as conn:
        row = conn.execute(
            """
            INSERT INTO app_users (user_id, full_name, email, password_hash, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                full_name = excluded.full_name,
                email = excluded.email,
                password_hash = excluded.password_hash,
                role = excluded.role
            RETURNING user_id, full_name, email, password_hash, role, created_at
            """,
            (
                user["user_id"],
                user["full_name"],
                user["email"],
                user["password_hash"],
                user["role"],
                user["created_at"],
            ),
        ).fetchone()
    if not row:
        return user
    return {
        "user_id": row[0],
        "full_name": row[1],
        "email": row[2],
        "password_hash": row[3],
        "role": row[4],
        "created_at": row[5],
    }


def get_app_user_by_email(db_path: Path, email: str) -> dict | None:
    init_db(db_path)
    with db_connect() as conn:
        row = conn.execute(
            """
            SELECT user_id, full_name, email, password_hash, role, created_at
            FROM app_users
            WHERE email = ?
            """,
            (email.strip().lower(),),
        ).fetchone()
    if not row:
        return None
    return {
        "user_id": row[0],
        "full_name": row[1],
        "email": row[2],
        "password_hash": row[3],
        "role": row[4],
        "created_at": row[5],
    }


def get_app_user_by_id(db_path: Path, user_id: str) -> dict | None:
    init_db(db_path)
    with db_connect() as conn:
        row = conn.execute(
            """
            SELECT user_id, full_name, email, password_hash, role, created_at
            FROM app_users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "user_id": row[0],
        "full_name": row[1],
        "email": row[2],
        "password_hash": row[3],
        "role": row[4],
        "created_at": row[5],
    }


def update_app_user(db_path: Path, user_id: str, full_name: str, email: str, new_password: str = "") -> bool:
    init_db(db_path)
    clean_name = full_name.strip()
    clean_email = email.strip().lower()
    if not clean_name or not clean_email:
        return False

    with db_connect() as conn:
        if new_password:
            result = conn.execute(
                """
                UPDATE app_users
                SET full_name = ?, email = ?, password_hash = ?
                WHERE user_id = ?
                """,
                (clean_name, clean_email, hash_password(new_password), user_id),
            )
        else:
            result = conn.execute(
                """
                UPDATE app_users
                SET full_name = ?, email = ?
                WHERE user_id = ?
                """,
                (clean_name, clean_email, user_id),
            )

        if result.rowcount > 0:
            conn.execute(
                """
                UPDATE user_listings
                SET seller_name = ?, seller_email = ?
                WHERE seller_user_id = ?
                """,
                (clean_name, clean_email, user_id),
            )

    return result.rowcount > 0


def list_app_users(db_path: Path) -> list[dict]:
    init_db(db_path)
    with db_connect() as conn:
        rows = conn.execute(
            """
            SELECT user_id, full_name, email, password_hash, role, created_at
            FROM app_users
            ORDER BY created_at DESC
            """
        ).fetchall()
    return [
        {
            "user_id": row[0],
            "full_name": row[1],
            "email": row[2],
            "password_hash": row[3],
            "role": row[4],
            "created_at": row[5],
        }
        for row in rows
        if row
    ]


def update_app_user_role(db_path: Path, user_id: str, role: str) -> bool:
    init_db(db_path)
    clean_role = str(role or "BUYER").strip().upper() or "BUYER"
    with db_connect() as conn:
        result = conn.execute(
            """
            UPDATE app_users
            SET role = ?
            WHERE user_id = ?
            """,
            (clean_role, user_id),
        )
    return result.rowcount > 0


def ensure_default_admin(db_path: Path) -> dict:
    init_db(db_path)
    admin_email = os.getenv("BMW_MARKETPLACE_DEFAULT_ADMIN_EMAIL", "admin@bmw-marketplace.local").strip().lower()
    admin_password = os.getenv("BMW_MARKETPLACE_DEFAULT_ADMIN_PASSWORD", "ChangeMe123!").strip() or "ChangeMe123!"
    admin_name = os.getenv("BMW_MARKETPLACE_DEFAULT_ADMIN_NAME", "Site Admin").strip() or "Site Admin"
    existing = get_app_user_by_email(db_path, admin_email)
    if existing:
        if str(existing.get("role", "")).strip().upper() != "SITE_ADMIN":
            update_app_user_role(db_path, str(existing.get("user_id", "")), "SITE_ADMIN")
            existing["role"] = "SITE_ADMIN"
        return existing
    return create_app_user(db_path, admin_name, admin_email, admin_password, "SITE_ADMIN")


def create_user_listing(db_path: Path, values: dict[str, str], current_user: dict[str, str]) -> str:
    init_db(db_path)
    now = datetime.now(timezone.utc)
    listing_id = f"user-{int(now.timestamp() * 1000)}"
    created_at = now.isoformat()
    expires_at = _compute_expiry(now)

    gallery_values = [part.strip() for part in values.get("gallery_images", "").split(",") if part.strip()]
    image_url = values.get("image_url", "").strip()
    if image_url and image_url not in gallery_values:
        gallery_values.insert(0, image_url)
    seller_context = resolve_listing_seller_context(db_path, current_user, values)

    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO user_listings (
                listing_id, seller_user_id, seller_name, seller_email, seller_type, dealer_id, seller_verified,
                vin, model, trim, body_style, drive_type, title_type, image_url, gallery_images_json,
                description, year, mileage, price, location, status, created_at, updated_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                listing_id,
                current_user.get("user_id", ""),
                str(seller_context.get("seller_name", "Unknown Seller")),
                str(seller_context.get("seller_email", "")).lower(),
                str(seller_context.get("seller_type", "PRIVATE_SELLER")),
                str(seller_context.get("dealer_id", "")),
                bool(seller_context.get("seller_verified", False)),
                sanitize_vin(values.get("vin", "")),
                values.get("model", "BMW"),
                values.get("trim", "Base"),
                values.get("body_style", "Unknown"),
                values.get("drive_type", "Unknown"),
                values.get("title_type", "Clean"),
                image_url,
                json.dumps(gallery_values),
                values.get("description", ""),
                int(values.get("year", "0") or 0),
                int(values.get("mileage", "0") or 0),
                int(values.get("price", "0") or 0),
                values.get("location", ""),
                values.get("status", "ACTIVE"),
                created_at,
                created_at,
                expires_at,
            ),
        )

    return listing_id


def refresh_user_listing(db_path: Path, listing_id: str, owner_user_id: str) -> bool:
    init_db(db_path)
    now = datetime.now(timezone.utc)
    with db_connect() as conn:
        result = conn.execute(
            """
            UPDATE user_listings
            SET updated_at = ?, expires_at = ?, status = 'ACTIVE',
                reminder_24h_sent_at = NULL, reminder_1h_sent_at = NULL, reminder_5m_sent_at = NULL
            WHERE listing_id = ? AND seller_user_id = ?
            """,
            (now.isoformat(), _compute_expiry(now), listing_id, owner_user_id),
        )
    return result.rowcount > 0


def get_user_listing_for_owner(db_path: Path, listing_id: str, owner_user_id: str) -> dict | None:
    init_db(db_path)
    with db_connect() as conn:
        row = conn.execute(
            """
            SELECT
                listing_id,
                seller_user_id,
                seller_name,
                seller_email,
                seller_type,
                dealer_id,
                seller_verified,
                vin,
                model,
                trim,
                body_style,
                drive_type,
                title_type,
                image_url,
                gallery_images_json,
                description,
                year,
                mileage,
                price,
                location,
                status,
                created_at,
                updated_at,
                expires_at,
                reminder_24h_sent_at,
                reminder_1h_sent_at,
                reminder_5m_sent_at
            FROM user_listings
            WHERE listing_id = ? AND seller_user_id = ?
            """,
            (listing_id, owner_user_id),
        ).fetchone()
    return _dict_from_row(row) if row else None


def update_user_listing(db_path: Path, listing_id: str, owner_user_id: str, values: dict[str, str]) -> bool:
    init_db(db_path)
    now = datetime.now(timezone.utc)
    expires_at = _compute_expiry(now)
    year_value = values.get("year", "").strip()
    model_value = values.get("model", "").strip()
    trim_value = values.get("trim", "").strip()
    vin_value = sanitize_vin(values.get("vin", ""))
    gallery_values = [part.strip() for part in values.get("gallery_images", "").split(",") if part.strip()]
    image_url = values.get("image_url", "").strip()
    if image_url and image_url not in gallery_values:
        gallery_values.insert(0, image_url)

    if year_value:
        try:
            year_int = int(year_value)
        except ValueError:
            return False
        if year_int < 1970 or year_int > 2035:
            return False
    else:
        year_int = 0

    if not vin_value:
        return False
    if len(vin_value) > 17:
        return False

    with db_connect() as conn:
        result = conn.execute(
            """
            UPDATE user_listings
            SET
                year = CASE WHEN ? <> '' THEN ? ELSE year END,
                model = CASE WHEN ? <> '' THEN ? ELSE model END,
                trim = CASE WHEN ? <> '' THEN ? ELSE trim END,
                vin = CASE WHEN ? <> '' THEN ? ELSE vin END,
                seller_type = ?,
                body_style = ?,
                drive_type = ?,
                title_type = ?,
                image_url = ?,
                gallery_images_json = ?,
                description = ?,
                mileage = ?,
                price = ?,
                location = ?,
                status = ?,
                updated_at = ?,
                expires_at = ?,
                reminder_24h_sent_at = NULL,
                reminder_1h_sent_at = NULL,
                reminder_5m_sent_at = NULL
            WHERE listing_id = ? AND seller_user_id = ?
            """,
            (
                year_value,
                year_int,
                model_value,
                model_value,
                trim_value,
                trim_value,
                vin_value,
                vin_value,
                values.get("seller_type", "PRIVATE_SELLER"),
                values.get("body_style", "Unknown"),
                values.get("drive_type", "Unknown"),
                values.get("title_type", "Clean"),
                image_url,
                json.dumps(gallery_values),
                values.get("description", ""),
                int(values.get("mileage", "0") or 0),
                int(values.get("price", "0") or 0),
                values.get("location", ""),
                values.get("status", "ACTIVE"),
                now.isoformat(),
                expires_at,
                listing_id,
                owner_user_id,
            ),
        )
    return result.rowcount > 0


def set_user_listing_status(db_path: Path, listing_id: str, owner_user_id: str, status: str) -> bool:
    init_db(db_path)
    allowed = {"ACTIVE", "PAUSED", "PENDING", "SOLD"}
    target_status = status.strip().upper()
    if target_status not in allowed:
        return False

    now = datetime.now(timezone.utc)
    with db_connect() as conn:
        result = conn.execute(
            """
            UPDATE user_listings
            SET status = ?, updated_at = ?,
                reminder_24h_sent_at = CASE WHEN ? = 'ACTIVE' THEN NULL ELSE reminder_24h_sent_at END,
                reminder_1h_sent_at = CASE WHEN ? = 'ACTIVE' THEN NULL ELSE reminder_1h_sent_at END,
                reminder_5m_sent_at = CASE WHEN ? = 'ACTIVE' THEN NULL ELSE reminder_5m_sent_at END
            WHERE listing_id = ? AND seller_user_id = ?
            """,
            (target_status, now.isoformat(), target_status, target_status, target_status, listing_id, owner_user_id),
        )
    return result.rowcount > 0


def delete_user_listing(db_path: Path, listing_id: str, owner_user_id: str) -> bool:
    init_db(db_path)
    with db_connect() as conn:
        result = conn.execute(
            "DELETE FROM user_listings WHERE listing_id = ? AND seller_user_id = ?",
            (listing_id, owner_user_id),
        )
    return result.rowcount > 0


def create_listing_inquiry(data_dir: Path, listing_id: str, buyer_user: dict, body: str) -> dict:
    listing_id = listing_id.strip()
    message_body = body.strip()
    buyer_user_id = str(buyer_user.get("user_id", "")).strip()
    if not listing_id:
        raise ValueError("Missing listing_id")
    if not buyer_user_id:
        raise ValueError("Buyer account is required")
    if not message_body:
        raise ValueError("Please enter a message")

    listings = load_all_listings(data_dir)
    listing = next((item for item in listings if str(item.get("listing_id", "")) == listing_id), None)
    if not listing:
        raise LookupError("Listing not found")

    seller_user_id = str(listing.get("seller_user_id", "")).strip()
    if not seller_user_id:
        raise ValueError("Listing is missing a seller")
    if buyer_user_id == seller_user_id:
        raise ValueError("You cannot contact your own listing")

    dealer_id = str(listing.get("dealer_id", "")).strip()
    if not dealer_id:
        dealer_profile = get_active_dealer_profile_for_user(db_path_for(data_dir), seller_user_id)
        if dealer_profile:
            dealer_id = str(dealer_profile.get("dealer_id", "")).strip()
    inquiries = load_inquiries(data_dir)
    messages = load_messages(data_dir)
    now = _iso_now()
    inquiry = {
        "inquiry_id": f"inquiry-{uuid.uuid4().hex}",
        "listing_id": listing_id,
        "dealer_id": dealer_id,
        "assigned_user_id": "",
        "buyer_user_id": buyer_user_id,
        "seller_user_id": seller_user_id,
        "status": "NEW",
        "created_at": now,
        "updated_at": now,
    }
    message = {
        "message_id": f"message-{uuid.uuid4().hex}",
        "inquiry_id": inquiry["inquiry_id"],
        "sender_user_id": buyer_user_id,
        "body": message_body,
        "sent_at": now,
    }

    inquiries.append(inquiry)
    messages.append(message)
    write_json(data_dir / "inquiries.json", inquiries)
    write_json(data_dir / "messages.json", messages)
    return {"inquiry": inquiry, "message": message, "listing": listing}


def get_inquiry_by_id(data_dir: Path, inquiry_id: str) -> dict | None:
    target_id = inquiry_id.strip()
    if not target_id:
        return None
    for inquiry in load_inquiries(data_dir):
        if str(inquiry.get("inquiry_id", "")) == target_id:
            return inquiry
    return None


def list_dealer_inquiries(data_dir: Path, dealer_id: str) -> list[dict]:
    clean_dealer_id = dealer_id.strip()
    if not clean_dealer_id:
        return []
    listings_by_id = {str(listing.get("listing_id", "")): listing for listing in load_all_listings(data_dir)}
    messages = load_messages(data_dir)
    message_counts: dict[str, int] = {}
    latest_messages: dict[str, dict] = {}
    for message in messages:
        inquiry_key = str(message.get("inquiry_id", ""))
        if not inquiry_key:
            continue
        message_counts[inquiry_key] = message_counts.get(inquiry_key, 0) + 1
        latest_messages[inquiry_key] = message

    results: list[dict] = []
    for inquiry in load_inquiries(data_dir):
        inquiry_dealer_id = str(inquiry.get("dealer_id", "")).strip()
        listing = listings_by_id.get(str(inquiry.get("listing_id", "")), {})
        if not inquiry_dealer_id:
            inquiry_dealer_id = str(listing.get("dealer_id", "")).strip()
        if inquiry_dealer_id != clean_dealer_id:
            continue
        inquiry_copy = dict(inquiry)
        inquiry_copy["dealer_id"] = inquiry_dealer_id
        inquiry_copy["message_count"] = message_counts.get(str(inquiry.get("inquiry_id", "")), 0)
        inquiry_copy["latest_message"] = latest_messages.get(str(inquiry.get("inquiry_id", "")), {})
        inquiry_copy["listing"] = listing
        results.append(inquiry_copy)

    return sorted(results, key=lambda item: str(item.get("updated_at", item.get("created_at", ""))), reverse=True)


def add_inquiry_reply(data_dir: Path, inquiry_id: str, sender_user: dict, body: str) -> dict:
    clean_inquiry_id = inquiry_id.strip()
    message_body = body.strip()
    sender_user_id = str(sender_user.get("user_id", "")).strip()
    if not clean_inquiry_id:
        raise ValueError("Missing inquiry_id")
    if not sender_user_id:
        raise ValueError("Sender account is required")
    if not message_body:
        raise ValueError("Please enter a message")

    inquiries = load_inquiries(data_dir)
    messages = load_messages(data_dir)
    inquiry_index = next((index for index, inquiry in enumerate(inquiries) if str(inquiry.get("inquiry_id", "")) == clean_inquiry_id), -1)
    if inquiry_index < 0:
        raise LookupError("Inquiry not found")

    inquiry = inquiries[inquiry_index]
    listing = next((item for item in load_all_listings(data_dir) if str(item.get("listing_id", "")) == str(inquiry.get("listing_id", ""))), {})
    dealer_id = str(inquiry.get("dealer_id", "")).strip() or str(listing.get("dealer_id", "")).strip()
    if not dealer_id:
        raise ValueError("Inquiry is not associated with a dealership")

    now = _iso_now()
    message = {
        "message_id": f"message-{uuid.uuid4().hex}",
        "inquiry_id": clean_inquiry_id,
        "sender_user_id": sender_user_id,
        "body": message_body,
        "sent_at": now,
    }

    inquiries[inquiry_index] = {
        **inquiry,
        "dealer_id": dealer_id,
        "status": "RESPONDED",
        "updated_at": now,
    }
    messages.append(message)
    write_json(data_dir / "inquiries.json", inquiries)
    write_json(data_dir / "messages.json", messages)
    return {"inquiry": inquiries[inquiry_index], "message": message, "listing": listing}


def format_expiry_notice(listing: dict) -> str:
    expires_at = _parse_iso_utc(str(listing.get("expires_at", "")))
    if not expires_at:
        return ""
    seconds_left = int((expires_at - datetime.now(timezone.utc)).total_seconds())
    if seconds_left <= 0:
        return "This listing expired due to inactivity."
    minutes_left = seconds_left // 60
    if minutes_left < 60:
        return f"Update required: this listing expires in about {minutes_left} minute(s)."
    hours_left = minutes_left // 60
    if hours_left < 24:
        return f"Update required: this listing expires in about {hours_left} hour(s)."
    days_left = hours_left // 24
    return f"Update required: this listing expires in about {days_left} day(s)."


def create_app_session(db_path: Path, user_id: str, max_age_seconds: int = SESSION_MAX_AGE_SECONDS) -> str:
    init_db(db_path)
    now = datetime.now(timezone.utc)
    token = secrets.token_urlsafe(32)
    expires_at = (now + timedelta(seconds=max_age_seconds)).isoformat()
    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO app_sessions (session_token, user_id, expires_at, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (token, user_id, expires_at, now.isoformat()),
        )
    return token


def get_user_id_for_session(db_path: Path, token: str) -> str:
    if not token:
        return ""
    init_db(db_path)
    with db_connect() as conn:
        row = conn.execute(
            """
            SELECT user_id, expires_at
            FROM app_sessions
            WHERE session_token = ?
            """,
            (token,),
        ).fetchone()
        if not row:
            return ""
        user_id = str(row[0])
        try:
            expires_at = datetime.fromisoformat(str(row[1]))
        except ValueError:
            conn.execute("DELETE FROM app_sessions WHERE session_token = ?", (token,))
            return ""
        if expires_at <= datetime.now(timezone.utc):
            conn.execute("DELETE FROM app_sessions WHERE session_token = ?", (token,))
            return ""
    return user_id


def delete_app_session(db_path: Path, token: str) -> None:
    if not token:
        return
    init_db(db_path)
    with db_connect() as conn:
        conn.execute("DELETE FROM app_sessions WHERE session_token = ?", (token,))


def currency(value: int) -> str:
    return f"${value:,.0f}"


def role_label(role: str) -> str:
    if role == "DEALER":
        return "Dealer"
    if role == "PRIVATE_SELLER":
        return "Private Seller"
    return role.title()


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def seller_is_verified(listing: dict | None = None, seller: dict | None = None) -> bool:
    listing = listing or {}
    seller = seller or {}
    if _coerce_bool(listing.get("seller_verified", False)):
        return True
    if _coerce_bool(listing.get("verified", False)):
        return True
    if _coerce_bool(seller.get("verified", False)):
        return True
    seller_type = str(listing.get("seller_type", seller.get("role", ""))).strip().upper()
    return seller_type == "DEALER"


def verification_badge_html(compact: bool = False) -> str:
    classes = "seller-badge seller-badge--compact" if compact else "seller-badge"
    return (
        f'<span class="{classes}" aria-label="Verified seller" title="Verified seller">'
        '<span class="seller-badge__icon" aria-hidden="true">✓</span>'
        '<span class="seller-badge__text">Verified</span>'
        '</span>'
    )


def notice_html(notice_code: str) -> str:
    message = NOTICE_MESSAGES.get(notice_code.strip().lower(), "") if notice_code else ""
    if not message:
        return ""
    return f'<section class="notice-panel"><p>{html.escape(message)}</p></section>'


def extract_chassis_code(listing: dict) -> str:
    text = " ".join(
        [
            str(listing.get("model", "")),
            str(listing.get("trim", "")),
            str(listing.get("description", "")),
        ]
    ).upper()
    match = re.search(r"\b([EFG]\d{2})\b", text)
    return match.group(1) if match else ""


def extract_transmission_type(listing: dict) -> str:
    raw = str(listing.get("transmission", "")).strip()
    if raw:
        return raw
    text = " ".join([str(listing.get("trim", "")), str(listing.get("description", ""))]).lower()
    if "manual" in text:
        return "Manual"
    if "dct" in text or "dual-clutch" in text:
        return "DCT"
    if "automatic" in text:
        return "Automatic"
    return "Unknown"


def extract_package_name(listing: dict) -> str:
    raw = str(listing.get("package", "") or listing.get("packages", "")).strip()
    if raw:
        return raw
    text = " ".join([str(listing.get("trim", "")), str(listing.get("description", ""))]).lower()
    if "m sport" in text or "m-sport" in text:
        return "M-Sport"
    if "executive" in text:
        return "Executive"
    return "None"


def extract_doors(listing: dict) -> str:
    raw = str(listing.get("doors", "")).strip()
    if raw:
        return raw
    text = " ".join([str(listing.get("model", "")), str(listing.get("description", ""))]).lower()
    match = re.search(r"\b([2-5])\s*doors?\b", text)
    if match:
        return match.group(1)
    if "coupe" in text or "roadster" in text or "convertible" in text:
        return "2"
    if "sedan" in text:
        return "4"
    return "Unknown"


def title_bucket(listing: dict) -> str:
    value = str(listing.get("title_type", "")).strip().lower()
    if "clean" in value:
        return "clean"
    if any(token in value for token in ["salvage", "rebuilt", "lemon", "buyback"]):
        return "salvage_or_rebuilt"
    return "other"


def listing_matches_search(listing: dict, search: str) -> bool:
    if not search:
        return True
    haystack = " ".join(
        [
            str(listing.get("year", "")),
            str(listing.get("model", "")),
            str(listing.get("trim", "")),
            str(listing.get("location", "")),
            str(listing.get("title_type", "")),
            str(listing.get("description", "")),
            extract_chassis_code(listing),
            extract_transmission_type(listing),
            extract_package_name(listing),
            extract_doors(listing),
        ]
    ).lower()
    return search.lower() in haystack


def admin_email_set() -> set[str]:
    raw = os.getenv(ADMIN_EMAILS_ENV_VAR, "")
    return {part.strip().lower() for part in re.split(r"[,\s]+", raw) if part.strip()}


def get_user_role(user: dict | None) -> str:
    if not user:
        return ""
    return str(user.get("role", "")).strip().upper()


def is_site_admin(user: dict | None) -> bool:
    if not user:
        return False
    role = get_user_role(user)
    if role in {"ADMIN", "SITE_ADMIN"}:
        return True
    email = str(user.get("email", "")).strip().lower()
    return email in admin_email_set()


def normalize_dealer_profile_status(status: str) -> str:
    normalized = str(status or "").strip().upper()
    if normalized in {"PENDING", "APPROVED", "REJECTED", "SUSPENDED"}:
        return normalized
    return "PENDING"


def normalize_dealer_member_role(role: str) -> str:
    normalized = str(role or "").strip().upper()
    if normalized in {"OWNER", "SALES_MANAGER", "SALESPERSON"}:
        return normalized
    return "SALESPERSON"


def normalize_dealer_member_status(status: str) -> str:
    normalized = str(status or "").strip().upper()
    if normalized in {"INVITED", "ACTIVE", "SUSPENDED"}:
        return normalized
    return "INVITED"


def _dealer_profile_from_row(row: tuple | None) -> dict | None:
    if not row:
        return None
    return {
        "dealer_id": row[0],
        "owner_user_id": row[1],
        "legal_name": row[2],
        "display_name": row[3],
        "website_url": row[4],
        "license_number": row[5],
        "status": row[6],
        "rejected_reason": row[7],
        "approved_by_admin_id": row[8],
        "approved_at": row[9],
        "created_at": row[10],
        "updated_at": row[11],
    }


def _dealer_member_from_row(row: tuple | None) -> dict | None:
    if not row:
        return None
    return {
        "membership_id": row[0],
        "dealer_id": row[1],
        "user_id": row[2],
        "member_role": row[3],
        "member_status": row[4],
        "created_by_user_id": row[5],
        "created_at": row[6],
        "updated_at": row[7],
    }


def record_verification_event(
    db_path: Path,
    subject_type: str,
    subject_id: str,
    actor_user_id: str,
    event_type: str,
    event_status: str,
    notes: str = "",
    metadata: dict | None = None,
) -> None:
    init_db(db_path)
    payload = json.dumps(metadata or {}, separators=(",", ":"))
    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO verification_events (
                event_id, subject_type, subject_id, actor_user_id, event_type, event_status,
                notes, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"event-{uuid.uuid4().hex}",
                subject_type,
                subject_id,
                actor_user_id,
                event_type,
                event_status,
                notes,
                payload,
                _iso_now(),
            ),
        )


def get_dealer_profile_by_id(db_path: Path, dealer_id: str) -> dict | None:
    init_db(db_path)
    with db_connect() as conn:
        row = conn.execute(
            """
            SELECT dealer_id, owner_user_id, legal_name, display_name, website_url, license_number,
                   status, rejected_reason, approved_by_admin_id, approved_at, created_at, updated_at
            FROM dealer_profiles
            WHERE dealer_id = ?
            """,
            (dealer_id,),
        ).fetchone()
    return _dealer_profile_from_row(row)


def get_dealer_profile_for_owner(db_path: Path, owner_user_id: str) -> dict | None:
    init_db(db_path)
    with db_connect() as conn:
        row = conn.execute(
            """
            SELECT dealer_id, owner_user_id, legal_name, display_name, website_url, license_number,
                   status, rejected_reason, approved_by_admin_id, approved_at, created_at, updated_at
            FROM dealer_profiles
            WHERE owner_user_id = ?
            """,
            (owner_user_id,),
        ).fetchone()
    return _dealer_profile_from_row(row)


def get_active_dealer_profile_for_user(db_path: Path, user_id: str) -> dict | None:
    init_db(db_path)
    with db_connect() as conn:
        row = conn.execute(
            """
            SELECT p.dealer_id, p.owner_user_id, p.legal_name, p.display_name, p.website_url, p.license_number,
                   p.status, p.rejected_reason, p.approved_by_admin_id, p.approved_at, p.created_at, p.updated_at
            FROM dealer_profiles p
            LEFT JOIN dealer_members m
              ON m.dealer_id = p.dealer_id
             AND m.user_id = ?
            WHERE p.status = 'APPROVED'
              AND (
                    p.owner_user_id = ?
                    OR (m.member_status = 'ACTIVE' AND m.member_role IN ('OWNER', 'SALES_MANAGER', 'SALESPERSON'))
                  )
            ORDER BY CASE WHEN p.owner_user_id = ? THEN 0 ELSE 1 END, p.created_at DESC
            LIMIT 1
            """,
            (user_id, user_id, user_id),
        ).fetchone()
    return _dealer_profile_from_row(row)


def get_dealer_membership_for_user(db_path: Path, dealer_id: str, user_id: str) -> dict | None:
    init_db(db_path)
    with db_connect() as conn:
        row = conn.execute(
            """
            SELECT membership_id, dealer_id, user_id, member_role, member_status, created_by_user_id, created_at, updated_at
            FROM dealer_members
            WHERE dealer_id = ? AND user_id = ?
            """,
            (dealer_id, user_id),
        ).fetchone()
    return _dealer_member_from_row(row)


def list_dealer_members(db_path: Path, dealer_id: str) -> list[dict]:
    init_db(db_path)
    with db_connect() as conn:
        rows = conn.execute(
            """
            SELECT membership_id, dealer_id, user_id, member_role, member_status, created_by_user_id, created_at, updated_at
            FROM dealer_members
            WHERE dealer_id = ?
            ORDER BY created_at ASC
            """,
            (dealer_id,),
        ).fetchall()
    return [_dealer_member_from_row(row) for row in rows if row]


def list_pending_dealers(db_path: Path) -> list[dict]:
    init_db(db_path)
    with db_connect() as conn:
        rows = conn.execute(
            """
            SELECT dealer_id, owner_user_id, legal_name, display_name, website_url, license_number,
                   status, rejected_reason, approved_by_admin_id, approved_at, created_at, updated_at
            FROM dealer_profiles
            WHERE status = 'PENDING'
            ORDER BY created_at ASC
            """
        ).fetchall()
    return [_dealer_profile_from_row(row) for row in rows if row]


def list_all_dealer_profiles(db_path: Path) -> list[dict]:
    init_db(db_path)
    with db_connect() as conn:
        rows = conn.execute(
            """
            SELECT dealer_id, owner_user_id, legal_name, display_name, website_url, license_number,
                   status, rejected_reason, approved_by_admin_id, approved_at, created_at, updated_at
            FROM dealer_profiles
            ORDER BY created_at DESC
            """
        ).fetchall()
    return [_dealer_profile_from_row(row) for row in rows if row]


def _sync_dealer_listings(db_path: Path, dealer_id: str, owner_user_id: str, seller_name: str, seller_email: str) -> None:
    with db_connect() as conn:
        conn.execute(
            """
            UPDATE user_listings
            SET seller_name = ?, seller_email = ?, seller_type = 'DEALER', seller_verified = TRUE, dealer_id = ?
            WHERE dealer_id = ? OR seller_user_id = ?
            """,
            (seller_name, seller_email, dealer_id, dealer_id, owner_user_id),
        )


def upsert_dealer_membership(
    db_path: Path,
    dealer_id: str,
    user_id: str,
    member_role: str,
    member_status: str,
    created_by_user_id: str,
) -> dict:
    init_db(db_path)
    now = _iso_now()
    membership_id = f"member-{uuid.uuid4().hex}"
    normalized_role = normalize_dealer_member_role(member_role)
    normalized_status = normalize_dealer_member_status(member_status)
    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO dealer_members (
                membership_id, dealer_id, user_id, member_role, member_status, created_by_user_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(dealer_id, user_id) DO UPDATE SET
                member_role = excluded.member_role,
                member_status = excluded.member_status,
                created_by_user_id = excluded.created_by_user_id,
                updated_at = excluded.updated_at
            """,
            (membership_id, dealer_id, user_id, normalized_role, normalized_status, created_by_user_id, now, now),
        )
        row = conn.execute(
            """
            SELECT membership_id, dealer_id, user_id, member_role, member_status, created_by_user_id, created_at, updated_at
            FROM dealer_members
            WHERE dealer_id = ? AND user_id = ?
            """,
            (dealer_id, user_id),
        ).fetchone()
    return _dealer_member_from_row(row) or {
        "membership_id": membership_id,
        "dealer_id": dealer_id,
        "user_id": user_id,
        "member_role": normalized_role,
        "member_status": normalized_status,
        "created_by_user_id": created_by_user_id,
        "created_at": now,
        "updated_at": now,
    }


def user_can_manage_dealer(db_path: Path, user_id: str, dealer_id: str) -> bool:
    if not user_id or not dealer_id:
        return False
    user = get_app_user_by_id(db_path, user_id)
    if is_site_admin(user):
        return True
    dealer_profile = get_dealer_profile_by_id(db_path, dealer_id)
    if not dealer_profile or dealer_profile.get("status") != "APPROVED":
        return False
    if str(dealer_profile.get("owner_user_id", "")) == user_id:
        return True
    membership = get_dealer_membership_for_user(db_path, dealer_id, user_id)
    if not membership:
        return False
    return membership.get("member_status") == "ACTIVE" and membership.get("member_role") in {"OWNER", "SALES_MANAGER"}


def user_can_respond_for_dealer(db_path: Path, user_id: str, dealer_id: str) -> bool:
    if not user_id or not dealer_id:
        return False
    user = get_app_user_by_id(db_path, user_id)
    if is_site_admin(user):
        return True
    dealer_profile = get_dealer_profile_by_id(db_path, dealer_id)
    if not dealer_profile or dealer_profile.get("status") != "APPROVED":
        return False
    membership = get_dealer_membership_for_user(db_path, dealer_id, user_id)
    if not membership:
        return str(dealer_profile.get("owner_user_id", "")) == user_id
    return membership.get("member_status") == "ACTIVE" and membership.get("member_role") in {
        "OWNER",
        "SALES_MANAGER",
        "SALESPERSON",
    }


def resolve_listing_seller_context(db_path: Path, current_user: dict[str, str], values: dict[str, str] | None = None) -> dict[str, object]:
    values = values or {}
    dealer_profile = get_active_dealer_profile_for_user(db_path, str(current_user.get("user_id", "")))
    if dealer_profile:
        return {
            "seller_name": str(dealer_profile.get("display_name", "")).strip()
            or str(current_user.get("full_name", "Unknown Seller")),
            "seller_email": str(current_user.get("email", "")).strip().lower(),
            "seller_type": "DEALER",
            "dealer_id": str(dealer_profile.get("dealer_id", "")),
            "seller_verified": True,
        }
    return {
        "seller_name": str(current_user.get("full_name", "Unknown Seller")),
        "seller_email": str(current_user.get("email", "")).strip().lower(),
        "seller_type": "PRIVATE_SELLER",
        "dealer_id": "",
        "seller_verified": False,
    }


def create_dealer_application(
    db_path: Path,
    owner_user_id: str,
    legal_name: str,
    display_name: str,
    website_url: str = "",
    license_number: str = "",
) -> dict:
    init_db(db_path)
    now = _iso_now()
    dealer_id = f"dealer-{uuid.uuid4().hex}"
    clean_legal_name = legal_name.strip()
    clean_display_name = display_name.strip() or clean_legal_name
    clean_website_url = website_url.strip()
    clean_license_number = license_number.strip()
    if not clean_legal_name or not clean_display_name:
        raise ValueError("legal_name and display_name are required")
    with db_connect() as conn:
        row = conn.execute(
            """
            INSERT INTO dealer_profiles (
                dealer_id, owner_user_id, legal_name, display_name, website_url, license_number,
                status, rejected_reason, approved_by_admin_id, approved_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'PENDING', '', NULL, NULL, ?, ?)
            ON CONFLICT(owner_user_id) DO UPDATE SET
                legal_name = excluded.legal_name,
                display_name = excluded.display_name,
                website_url = excluded.website_url,
                license_number = excluded.license_number,
                status = 'PENDING',
                rejected_reason = '',
                approved_by_admin_id = NULL,
                approved_at = NULL,
                updated_at = excluded.updated_at
            RETURNING dealer_id, owner_user_id, legal_name, display_name, website_url, license_number,
                      status, rejected_reason, approved_by_admin_id, approved_at, created_at, updated_at
            """,
            (
                dealer_id,
                owner_user_id,
                clean_legal_name,
                clean_display_name,
                clean_website_url,
                clean_license_number,
                now,
                now,
            ),
        ).fetchone()
    profile = _dealer_profile_from_row(row)
    if profile:
        upsert_dealer_membership(db_path, str(profile["dealer_id"]), owner_user_id, "OWNER", "ACTIVE", owner_user_id)
        record_verification_event(
            db_path,
            "dealer_profile",
            str(profile["dealer_id"]),
            owner_user_id,
            "application_submitted",
            "PENDING",
            "Dealer application submitted",
            {
                "legal_name": clean_legal_name,
                "display_name": clean_display_name,
                "website_url": clean_website_url,
                "license_number": clean_license_number,
            },
        )
    return profile or {}


def approve_dealer_profile(db_path: Path, dealer_id: str, admin_user_id: str) -> dict | None:
    init_db(db_path)
    now = _iso_now()
    with db_connect() as conn:
        row = conn.execute(
            """
            UPDATE dealer_profiles
            SET status = 'APPROVED',
                rejected_reason = '',
                approved_by_admin_id = ?,
                approved_at = ?,
                updated_at = ?
            WHERE dealer_id = ?
            RETURNING dealer_id, owner_user_id, legal_name, display_name, website_url, license_number,
                      status, rejected_reason, approved_by_admin_id, approved_at, created_at, updated_at
            """,
            (admin_user_id, now, now, dealer_id),
        ).fetchone()
    profile = _dealer_profile_from_row(row)
    if profile:
        owner = get_app_user_by_id(db_path, str(profile.get("owner_user_id", "")))
        owner_email = str(owner.get("email", "")) if owner else ""
        _sync_dealer_listings(
            db_path,
            dealer_id,
            str(profile.get("owner_user_id", "")),
            str(profile.get("display_name", "")),
            owner_email,
        )
        record_verification_event(
            db_path,
            "dealer_profile",
            dealer_id,
            admin_user_id,
            "approval",
            "APPROVED",
            "Dealer approved",
            {"approved_by_admin_id": admin_user_id},
        )
    return profile


def reject_dealer_profile(db_path: Path, dealer_id: str, admin_user_id: str, reason: str = "") -> dict | None:
    init_db(db_path)
    now = _iso_now()
    clean_reason = reason.strip()
    with db_connect() as conn:
        row = conn.execute(
            """
            UPDATE dealer_profiles
            SET status = 'REJECTED',
                rejected_reason = ?,
                approved_by_admin_id = NULL,
                approved_at = NULL,
                updated_at = ?
            WHERE dealer_id = ?
            RETURNING dealer_id, owner_user_id, legal_name, display_name, website_url, license_number,
                      status, rejected_reason, approved_by_admin_id, approved_at, created_at, updated_at
            """,
            (clean_reason, now, dealer_id),
        ).fetchone()
    profile = _dealer_profile_from_row(row)
    if profile:
        record_verification_event(
            db_path,
            "dealer_profile",
            dealer_id,
            admin_user_id,
            "rejection",
            "REJECTED",
            "Dealer rejected",
            {"reason": clean_reason},
        )
    return profile


def suspend_dealer_profile(db_path: Path, dealer_id: str, admin_user_id: str, reason: str = "") -> dict | None:
    init_db(db_path)
    now = _iso_now()
    clean_reason = reason.strip()
    with db_connect() as conn:
        row = conn.execute(
            """
            UPDATE dealer_profiles
            SET status = 'SUSPENDED',
                rejected_reason = ?,
                approved_at = COALESCE(approved_at, ?),
                updated_at = ?
            WHERE dealer_id = ?
            RETURNING dealer_id, owner_user_id, legal_name, display_name, website_url, license_number,
                      status, rejected_reason, approved_by_admin_id, approved_at, created_at, updated_at
            """,
            (clean_reason, now, now, dealer_id),
        ).fetchone()
    profile = _dealer_profile_from_row(row)
    if profile:
        record_verification_event(
            db_path,
            "dealer_profile",
            dealer_id,
            admin_user_id,
            "suspension",
            "SUSPENDED",
            "Dealer suspended",
            {"reason": clean_reason},
        )
    return profile


def upsert_dealer_member_record(
    db_path: Path,
    dealer_id: str,
    user_id: str,
    member_role: str,
    member_status: str,
    created_by_user_id: str,
) -> dict:
    init_db(db_path)
    now = _iso_now()
    membership = upsert_dealer_membership(db_path, dealer_id, user_id, member_role, member_status, created_by_user_id)
    record_verification_event(
        db_path,
        "dealer_member",
        membership["membership_id"],
        created_by_user_id,
        "member_upserted",
        membership["member_status"],
        "Dealer member updated",
        {
            "dealer_id": dealer_id,
            "user_id": user_id,
            "member_role": membership["member_role"],
            "member_status": membership["member_status"],
            "updated_at": now,
        },
    )
    return membership


def seed_demo_dealerships(db_path: Path) -> list[dict]:
    init_db(db_path)

    demo_dealerships = [
        {
            "owner_user_id": "dealer-1",
            "full_name": "North Shore BMW Owner",
            "email": "dealer1@bmw-marketplace.local",
            "password": "Dealer123!",
            "legal_name": "North Shore Automotive Group LLC",
            "display_name": "North Shore BMW",
            "website_url": "https://northshorebmw.example.com",
            "license_number": "NS-BMW-1001",
            "members": [
                ("dealer-1-manager", "North Shore BMW Manager", "north.manager@bmw-marketplace.local", "SALES_MANAGER", "ACTIVE"),
                ("dealer-1-sales", "North Shore BMW Sales", "north.sales@bmw-marketplace.local", "SALESPERSON", "ACTIVE"),
            ],
        },
        {
            "owner_user_id": "dealer-2",
            "full_name": "Metro BMW Owner",
            "email": "dealer2@bmw-marketplace.local",
            "password": "Dealer123!",
            "legal_name": "Metro BMW Retail LLC",
            "display_name": "Metro BMW",
            "website_url": "https://metrobmw.example.com",
            "license_number": "METRO-BMW-2048",
            "members": [
                ("dealer-2-manager", "Metro BMW Manager", "metro.manager@bmw-marketplace.local", "SALES_MANAGER", "ACTIVE"),
                ("dealer-2-sales", "Metro BMW Sales", "metro.sales@bmw-marketplace.local", "SALESPERSON", "ACTIVE"),
            ],
        },
        {
            "owner_user_id": "dealer-3",
            "full_name": "Bay BMW Owner",
            "email": "dealer3@bmw-marketplace.local",
            "password": "Dealer123!",
            "legal_name": "Bay Area BMW Holdings LLC",
            "display_name": "Bay BMW",
            "website_url": "https://baybmw.example.com",
            "license_number": "BAY-BMW-7781",
            "members": [
                ("dealer-3-sales", "Bay BMW Sales", "bay.sales@bmw-marketplace.local", "SALESPERSON", "ACTIVE"),
            ],
        },
        {
            "owner_user_id": "dealer-4",
            "full_name": "Valley BMW Owner",
            "email": "dealer4@bmw-marketplace.local",
            "password": "Dealer123!",
            "legal_name": "Valley BMW Group LLC",
            "display_name": "Valley BMW",
            "website_url": "https://valleybmw.example.com",
            "license_number": "VAL-BMW-4422",
            "members": [],
        },
        {
            "owner_user_id": "dealer-5",
            "full_name": "Lakeside BMW Owner",
            "email": "dealer5@bmw-marketplace.local",
            "password": "Dealer123!",
            "legal_name": "Lakeside BMW Sales LLC",
            "display_name": "Lakeside BMW",
            "website_url": "https://lakesidebmw.example.com",
            "license_number": "LAKE-BMW-9012",
            "members": [],
        },
    ]

    profiles: list[dict] = []
    for dealership in demo_dealerships:
        create_app_user_with_id(
            db_path,
            dealership["owner_user_id"],
            dealership["full_name"],
            dealership["email"],
            dealership["password"],
            "DEALER",
        )
        profile = create_dealer_application(
            db_path,
            dealership["owner_user_id"],
            dealership["legal_name"],
            dealership["display_name"],
            dealership["website_url"],
            dealership["license_number"],
        )
        if profile:
            approve_dealer_profile(db_path, str(profile.get("dealer_id", "")), dealership["owner_user_id"])
            for member_user_id, member_name, member_email, member_role, member_status in dealership["members"]:
                create_app_user_with_id(db_path, member_user_id, member_name, member_email, "Dealer123!", "DEALER")
                upsert_dealer_member_record(
                    db_path,
                    str(profile.get("dealer_id", "")),
                    member_user_id,
                    member_role,
                    member_status,
                    dealership["owner_user_id"],
                )
            profiles.append(profile)

    return profiles
