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
TEMPLATE_PATH = BASE_DIR / "home_page.html"
CSS_PATH = BASE_DIR / "home_page.css"
CARD_TEMPLATE_PATH = BASE_DIR / "home_page_card.html"
DETAIL_TEMPLATE_PATH = BASE_DIR / "listing_detail.html"
FORM_TEMPLATE_PATH = BASE_DIR / "listing_form.html"
EDIT_TEMPLATE_PATH = BASE_DIR / "listing_edit.html"
LOGIN_TEMPLATE_PATH = BASE_DIR / "login.html"
REGISTER_TEMPLATE_PATH = BASE_DIR / "register.html"
UPLOADS_DIR_NAME = "uploads"
SEED_IMAGES_DIR_NAME = "seed-images"
IMAGE_PLACEHOLDER_URL = "https://placehold.co/1200x800?text=BMW+Listing"
CARFAX_BASE_URL = "https://www.carfax.com/VehicleHistory/p/Report.cfx?vin="
NHTSA_RECALLS_BASE_URL = "https://www.nhtsa.gov/recalls?vymm="
NHTSA_RECALLS_GENERIC_URL = "https://www.nhtsa.gov/recalls"
DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:5432/bmw_marketplace"
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
    "action_failed": "We could not complete that action.",
}


def load_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


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
        "vin": row[5] or "",
        "model": row[6],
        "trim": row[7],
        "body_style": row[8],
        "drive_type": row[9],
        "title_type": row[10],
        "image_url": row[11],
        "gallery_images": gallery_images,
        "description": row[13],
        "year": row[14],
        "mileage": row[15],
        "price": row[16],
        "location": row[17],
        "status": row[18],
        "created_at": row[19],
        "updated_at": row[20],
        "expires_at": row[21],
        "reminder_24h_sent_at": row[22],
        "reminder_1h_sent_at": row[23],
        "reminder_5m_sent_at": row[24],
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


def create_app_user(db_path: Path, full_name: str, email: str, password: str) -> dict:
    init_db(db_path)
    created_at = datetime.now(timezone.utc).isoformat()
    user = {
        "user_id": f"app-{uuid.uuid4().hex}",
        "full_name": full_name.strip(),
        "email": email.strip().lower(),
        "password_hash": hash_password(password),
        "created_at": created_at,
    }
    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO app_users (user_id, full_name, email, password_hash, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user["user_id"], user["full_name"], user["email"], user["password_hash"], user["created_at"]),
        )
    return user


def get_app_user_by_email(db_path: Path, email: str) -> dict | None:
    init_db(db_path)
    with db_connect() as conn:
        row = conn.execute(
            """
            SELECT user_id, full_name, email, password_hash, created_at
            FROM app_users
            WHERE email = ?
            """,
            (email.strip().lower(),),
        ).fetchone()
    if not row:
        return None
    return {"user_id": row[0], "full_name": row[1], "email": row[2], "password_hash": row[3], "created_at": row[4]}


def get_app_user_by_id(db_path: Path, user_id: str) -> dict | None:
    init_db(db_path)
    with db_connect() as conn:
        row = conn.execute(
            """
            SELECT user_id, full_name, email, password_hash, created_at
            FROM app_users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return {"user_id": row[0], "full_name": row[1], "email": row[2], "password_hash": row[3], "created_at": row[4]}


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

    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO user_listings (
                listing_id, seller_user_id, seller_name, seller_email, seller_type, vin, model, trim,
                body_style, drive_type, title_type, image_url, gallery_images_json,
                description, year, mileage, price, location, status, created_at, updated_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                listing_id,
                current_user.get("user_id", ""),
                current_user.get("full_name", "Unknown Seller"),
                current_user.get("email", ""),
                values.get("seller_type", "PRIVATE_SELLER"),
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


