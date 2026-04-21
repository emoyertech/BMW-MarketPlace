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
import json
import mimetypes
import os
import re
import secrets
import sqlite3
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
LOGIN_TEMPLATE_PATH = BASE_DIR / "login.html"
REGISTER_TEMPLATE_PATH = BASE_DIR / "register.html"
DB_NAME = "marketplace.db"
UPLOADS_DIR_NAME = "uploads"
SEED_IMAGES_DIR_NAME = "seed-images"
IMAGE_PLACEHOLDER_URL = "https://placehold.co/1200x800?text=BMW+Listing"
SESSION_COOKIE_NAME = "bmw_marketplace_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 14


def load_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def db_path_for(data_dir: Path) -> Path:
    return data_dir / DB_NAME


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
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_listings (
                listing_id TEXT PRIMARY KEY,
                seller_user_id TEXT,
                seller_name TEXT NOT NULL,
                seller_email TEXT NOT NULL,
                seller_type TEXT NOT NULL,
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
                created_at TEXT NOT NULL
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
        columns = conn.execute("PRAGMA table_info(user_listings)").fetchall()
        column_names = {row[1] for row in columns}
        if "seller_user_id" not in column_names:
            conn.execute("ALTER TABLE user_listings ADD COLUMN seller_user_id TEXT")


def _dict_from_row(row: tuple) -> dict:
    gallery_images: list[str] = []
    if row[11]:
        try:
            parsed = json.loads(row[11])
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
        "model": row[5],
        "trim": row[6],
        "body_style": row[7],
        "drive_type": row[8],
        "title_type": row[9],
        "image_url": row[10],
        "gallery_images": gallery_images,
        "description": row[12],
        "year": row[13],
        "mileage": row[14],
        "price": row[15],
        "location": row[16],
        "status": row[17],
        "created_at": row[18],
    }


def load_user_listings(db_path: Path) -> list[dict]:
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                listing_id,
                seller_user_id,
                seller_name,
                seller_email,
                seller_type,
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
                created_at
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
    with sqlite3.connect(db_path) as conn:
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
    with sqlite3.connect(db_path) as conn:
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
    with sqlite3.connect(db_path) as conn:
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
    listing_id = f"user-{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    created_at = datetime.now(timezone.utc).isoformat()

    gallery_values = [part.strip() for part in values.get("gallery_images", "").split(",") if part.strip()]
    image_url = values.get("image_url", "").strip()
    if image_url and image_url not in gallery_values:
        gallery_values.insert(0, image_url)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO user_listings (
                listing_id, seller_user_id, seller_name, seller_email, seller_type, model, trim,
                body_style, drive_type, title_type, image_url, gallery_images_json,
                description, year, mileage, price, location, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                listing_id,
                current_user.get("user_id", ""),
                current_user.get("full_name", "Unknown Seller"),
                current_user.get("email", ""),
                values.get("seller_type", "PRIVATE_SELLER"),
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
            ),
        )

    return listing_id


def create_app_session(db_path: Path, user_id: str, max_age_seconds: int = SESSION_MAX_AGE_SECONDS) -> str:
    init_db(db_path)
    now = datetime.now(timezone.utc)
    token = secrets.token_urlsafe(32)
    expires_at = (now + timedelta(seconds=max_age_seconds)).isoformat()
    with sqlite3.connect(db_path) as conn:
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
    with sqlite3.connect(db_path) as conn:
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
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM app_sessions WHERE session_token = ?", (token,))


def currency(value: int) -> str:
    return f"${value:,.0f}"


def role_label(role: str) -> str:
    if role == "DEALER":
        return "Dealer"
    if role == "PRIVATE_SELLER":
        return "Private Seller"
    return role.title()


def render_create_listing(values: dict[str, str] | None = None, error: str = "") -> str:
    values = values or {}
    template = FORM_TEMPLATE_PATH.read_text(encoding="utf-8")
    error_html = f'<p class="form-error">{html.escape(error)}</p>' if error else ""

    def field(name: str, default: str = "") -> str:
        return html.escape(values.get(name, default))

    seller_type = values.get("seller_type", "PRIVATE_SELLER")
    status = values.get("status", "ACTIVE")

    return (
        template.replace("{{ERROR_HTML}}", error_html)
        .replace("{{SELLER_NAME}}", field("seller_name"))
        .replace("{{SELLER_EMAIL}}", field("seller_email"))
        .replace("{{MODEL}}", field("model"))
        .replace("{{TRIM}}", field("trim"))
        .replace("{{YEAR}}", field("year"))
        .replace("{{PRICE}}", field("price"))
        .replace("{{MILEAGE}}", field("mileage"))
        .replace("{{LOCATION}}", field("location"))
        .replace("{{BODY_STYLE}}", field("body_style"))
        .replace("{{DRIVE_TYPE}}", field("drive_type"))
        .replace("{{TITLE_TYPE}}", field("title_type", "Clean"))
        .replace("{{DESCRIPTION}}", field("description"))
        .replace("{{PRIVATE_SELECTED}}", "selected" if seller_type == "PRIVATE_SELLER" else "")
        .replace("{{DEALER_SELECTED}}", "selected" if seller_type == "DEALER" else "")
        .replace("{{ACTIVE_SELECTED}}", "selected" if status == "ACTIVE" else "")
        .replace("{{PAUSED_SELECTED}}", "selected" if status == "PAUSED" else "")
    )


def render_login(values: dict[str, str] | None = None, error: str = "") -> str:
    values = values or {}
    template = LOGIN_TEMPLATE_PATH.read_text(encoding="utf-8")
    error_html = f'<p class="form-error">{html.escape(error)}</p>' if error else ""
    return (
        template.replace("{{ERROR_HTML}}", error_html)
        .replace("{{EMAIL}}", html.escape(values.get("email", "")))
        .replace("{{NEXT}}", html.escape(values.get("next", "/")))
    )


def render_register(values: dict[str, str] | None = None, error: str = "") -> str:
    values = values or {}
    template = REGISTER_TEMPLATE_PATH.read_text(encoding="utf-8")
    error_html = f'<p class="form-error">{html.escape(error)}</p>' if error else ""
    return (
        template.replace("{{ERROR_HTML}}", error_html)
        .replace("{{FULL_NAME}}", html.escape(values.get("full_name", "")))
        .replace("{{EMAIL}}", html.escape(values.get("email", "")))
        .replace("{{NEXT}}", html.escape(values.get("next", "/")))
    )


def render_card(listing: dict, seller_name: str, card_template: str) -> str:
    year = html.escape(str(listing.get("year", "")))
    model = html.escape(str(listing.get("model", "")))
    trim = html.escape(str(listing.get("trim", "")))
    body_style = html.escape(str(listing.get("body_style", "")))
    drive_type = html.escape(str(listing.get("drive_type", "")))
    title_type = html.escape(str(listing.get("title_type", "")))
    image_url_value = str(listing.get("image_url", "")).strip() or IMAGE_PLACEHOLDER_URL
    image_url = html.escape(image_url_value)
    model_label = f"{year} BMW {model}".strip()
    if trim:
        model_label = f"{model_label} · {trim}"

    listing_url = "/listing?listing_id=" + urllib.parse.quote(str(listing.get("listing_id", "")))

    return (
        card_template.replace("{{LISTING_URL}}", listing_url)
        .replace("{{YEAR}}", year)
        .replace("{{MODEL}}", model)
        .replace("{{TRIM}}", trim)
        .replace("{{BODY_STYLE}}", body_style or "Unknown")
        .replace("{{DRIVE_TYPE}}", drive_type or "Unknown")
        .replace("{{TITLE_TYPE}}", title_type or "Unknown")
        .replace("{{IMAGE_URL}}", image_url)
        .replace("{{IMAGE_ALT}}", model_label)
        .replace("{{MODEL_LABEL}}", model_label)
        .replace("{{PRICE}}", currency(int(listing.get("price", 0))))
        .replace("{{LOCATION}}", html.escape(str(listing.get("location", ""))))
        .replace("{{MILEAGE}}", f"{int(listing.get('mileage', 0)):,}")
        .replace("{{SELLER_NAME}}", html.escape(seller_name))
        .replace("{{SELLER_TYPE}}", html.escape(role_label(str(listing.get("seller_type", "")))))
        .replace("{{STATUS}}", html.escape(str(listing.get("status", ""))))
        .replace("{{LISTING_ID}}", html.escape(str(listing.get("listing_id", ""))))
    )


def render_spec_item(label: str, value: str) -> str:
    return f'<div class="spec-card"><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong></div>'


def render_listing_detail(data_dir: Path, listing_id: str) -> str:
    users = load_json(data_dir / "users.json")
    listings = load_all_listings(data_dir)
    users_by_id = {u["user_id"]: u for u in users}
    listing = next((item for item in listings if item.get("listing_id") == listing_id), None)
    template = DETAIL_TEMPLATE_PATH.read_text(encoding="utf-8")

    if not listing:
        return (
            '<!doctype html><html lang="en"><head><meta charset="utf-8" />'
            '<meta name="viewport" content="width=device-width, initial-scale=1" />'
            '<title>Listing not found</title><link rel="stylesheet" href="/styles.css" />'
            '</head><body><main class="page-shell"><p class="empty-state">Listing not found.</p>'
            '<p><a class="button secondary" href="/">Return home</a></p></main></body></html>'
        )

    seller = users_by_id.get(listing.get("seller_user_id", ""), {})
    seller_name = str(listing.get("seller_name", "")).strip() or str(seller.get("full_name", "Unknown Seller"))
    seller_email = str(listing.get("seller_email", "")).strip() or str(seller.get("email", ""))
    gallery_images = [str(item).strip() for item in list(dict.fromkeys(listing.get("gallery_images") or [])) if str(item).strip()]
    primary_image = str(listing.get("image_url", "")).strip()
    if not primary_image and gallery_images:
        primary_image = gallery_images[0]
    if not primary_image:
        primary_image = IMAGE_PLACEHOLDER_URL

    thumb_images = [image_url for image_url in gallery_images if image_url != primary_image][:5]

    gallery_html = [
        f'<img class="detail-main-image" src="{html.escape(primary_image)}" alt="{html.escape(str(listing.get("year", "")))} BMW {html.escape(str(listing.get("model", "")))}" loading="eager" onerror="this.onerror=null;this.src=\'{IMAGE_PLACEHOLDER_URL}\';" />'
    ]
    if thumb_images:
        gallery_html.append('<div class="detail-thumb-grid">')
        for image_url in thumb_images:
            gallery_html.append(
                f'<img class="detail-thumb" src="{html.escape(image_url)}" alt="{html.escape(str(listing.get("year", "")))} BMW {html.escape(str(listing.get("model", "")))} gallery image" loading="lazy" onerror="this.onerror=null;this.src=\'{IMAGE_PLACEHOLDER_URL}\';" />'
            )
        gallery_html.append("</div>")

    description = str(listing.get("description", "")).strip()
    if not description:
        description = f"{listing.get('year', '')} BMW {listing.get('model', '')} with {listing.get('trim', '')}."

    title = f"{listing.get('year', '')} BMW {listing.get('model', '')}"
    detail_spec_html = "".join(
        [
            render_spec_item("Year", str(listing.get("year", ""))),
            render_spec_item("Model", str(listing.get("model", ""))),
            render_spec_item("Trim", str(listing.get("trim", "")) or "Unknown"),
            render_spec_item("Body style", str(listing.get("body_style", "")) or "Unknown"),
            render_spec_item("Drive type", str(listing.get("drive_type", "")) or "Unknown"),
            render_spec_item("Mileage", f"{int(listing.get('mileage', 0)):,} miles"),
            render_spec_item("Title status", str(listing.get("title_type", "")) or "Unknown"),
            render_spec_item("Location", str(listing.get("location", "")) or "Unknown"),
        ]
    )

    gallery_count = len(thumb_images) + (1 if primary_image else 0)
    gallery_notice = f"{gallery_count} images available" if gallery_count > 1 else "Single image available"

    return (
        template.replace("{{PAGE_TITLE}}", html.escape(title))
        .replace("{{DETAIL_TITLE}}", html.escape(title))
        .replace("{{DETAIL_SUBTITLE}}", html.escape(description))
        .replace("{{PRIMARY_IMAGE}}", html.escape(primary_image))
        .replace("{{GALLERY_NOTICE}}", html.escape(gallery_notice))
        .replace("{{GALLERY_HTML}}", "".join(gallery_html))
        .replace("{{DETAIL_SPEC_HTML}}", detail_spec_html)
        .replace("{{PRICE}}", currency(int(listing.get("price", 0) or 0)))
        .replace("{{YEAR}}", html.escape(str(listing.get("year", ""))))
        .replace("{{MODEL}}", html.escape(str(listing.get("model", ""))))
        .replace("{{TRIM}}", html.escape(str(listing.get("trim", ""))))
        .replace("{{BODY_STYLE}}", html.escape(str(listing.get("body_style", ""))))
        .replace("{{DRIVE_TYPE}}", html.escape(str(listing.get("drive_type", ""))))
        .replace("{{TITLE_TYPE}}", html.escape(str(listing.get("title_type", ""))))
        .replace("{{LOCATION}}", html.escape(str(listing.get("location", ""))))
        .replace("{{MILEAGE}}", f"{int(listing.get('mileage', 0)):,}")
        .replace("{{STATUS}}", html.escape(str(listing.get("status", ""))))
        .replace("{{LISTING_ID}}", html.escape(str(listing.get("listing_id", ""))))
        .replace("{{SELLER_NAME}}", html.escape(seller_name))
        .replace("{{SELLER_EMAIL}}", html.escape(seller_email))
        .replace("{{SELLER_TYPE}}", html.escape(role_label(str(listing.get("seller_type", "")))))
    )


def render_home(data_dir: Path, current_user: dict[str, str] | None = None) -> str:
    users = load_json(data_dir / "users.json")
    listings = load_all_listings(data_dir)
    inquiries = load_json(data_dir / "inquiries.json")

    users_by_id = {u["user_id"]: u for u in users}
    active = [l for l in listings if l.get("status") == "ACTIVE"]
    active = sorted(active, key=lambda x: x.get("created_at", ""), reverse=True)
    card_template = CARD_TEMPLATE_PATH.read_text(encoding="utf-8")

    dealer_listings = [listing for listing in active if listing.get("seller_type") == "DEALER"]
    private_listings = [listing for listing in active if listing.get("seller_type") == "PRIVATE_SELLER"]
    featured_listings = active[:6]
    dealer_showcase = dealer_listings[:4]
    private_showcase = private_listings[:4]

    cards = []
    for listing in featured_listings:
        seller = users_by_id.get(listing.get("seller_user_id", ""), {})
        seller_name = str(listing.get("seller_name", "")).strip() or seller.get("full_name", "Unknown Seller")
        cards.append(render_card(listing, seller_name, card_template))

    dealer_cards = []
    for listing in dealer_showcase:
        seller = users_by_id.get(listing.get("seller_user_id", ""), {})
        seller_name = str(listing.get("seller_name", "")).strip() or seller.get("full_name", "Unknown Seller")
        dealer_cards.append(render_card(listing, seller_name, card_template))

    private_cards = []
    for listing in private_showcase:
        seller = users_by_id.get(listing.get("seller_user_id", ""), {})
        seller_name = str(listing.get("seller_name", "")).strip() or seller.get("full_name", "Unknown Seller")
        private_cards.append(render_card(listing, seller_name, card_template))

    cards_html = "\n".join(cards) if cards else "<p class=\"empty-state\">No active listings found. Run seed_data.py first.</p>"
    dealer_html = "\n".join(dealer_cards) if dealer_cards else "<p class=\"empty-state\">No dealer listings available yet.</p>"
    private_html = "\n".join(private_cards) if private_cards else "<p class=\"empty-state\">No private seller listings available yet.</p>"

    avg_price = 0
    if active:
        avg_price = round(sum(int(listing.get("price", 0)) for listing in active) / len(active))

    recently_active = active[0] if active else {}
    hero_title = "Marketplace-ready BMW inventory from dealers and private sellers."
    hero_subtitle = (
        "A catalog-backed homepage that mixes dealer stock and individual listings, "
        "with real image URLs, mileage, titles, and vehicle details."
    )

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    if current_user:
        auth_header_html = (
            f'<span class="auth-welcome">Signed in as {html.escape(current_user.get("full_name", ""))}</span>'
            '<a class="button secondary auth-btn" href="/create-listing">Create listing</a>'
            '<a class="button secondary auth-btn" href="/logout">Log out</a>'
        )
    else:
        auth_header_html = (
            '<a class="button secondary auth-btn" href="/login?next=/create-listing">Log in</a>'
            '<a class="button secondary auth-btn" href="/register?next=/create-listing">Create account</a>'
        )

    return (
        template.replace("{{ACTIVE_COUNT}}", str(len(active)))
        .replace("{{LISTINGS_COUNT}}", str(len(listings)))
        .replace("{{USERS_COUNT}}", str(len(users)))
        .replace("{{INQUIRIES_COUNT}}", str(len(inquiries)))
        .replace("{{DEALER_COUNT}}", str(len(dealer_listings)))
        .replace("{{PRIVATE_COUNT}}", str(len(private_listings)))
        .replace("{{AVG_PRICE}}", currency(avg_price))
        .replace("{{FEATURED_YEAR}}", html.escape(str(recently_active.get("year", ""))))
        .replace("{{FEATURED_MODEL}}", html.escape(str(recently_active.get("model", ""))))
        .replace("{{FEATURED_TRIM}}", html.escape(str(recently_active.get("trim", ""))))
        .replace("{{FEATURED_IMAGE}}", html.escape(str(recently_active.get("image_url", ""))))
        .replace("{{FEATURED_PRICE}}", currency(int(recently_active.get("price", 0) or 0)))
        .replace("{{FEATURED_LOCATION}}", html.escape(str(recently_active.get("location", ""))))
        .replace("{{FEATURED_STATUS}}", html.escape(str(recently_active.get("status", ""))))
        .replace("{{FEATURED_TITLE_TYPE}}", html.escape(str(recently_active.get("title_type", ""))))
        .replace("{{HERO_TITLE}}", hero_title)
        .replace("{{HERO_SUBTITLE}}", hero_subtitle)
        .replace("{{FEATURED_CARDS_HTML}}", cards_html)
        .replace("{{DEALER_CARDS_HTML}}", dealer_html)
        .replace("{{PRIVATE_CARDS_HTML}}", private_html)
        .replace("{{AUTH_HEADER_HTML}}", auth_header_html)
    )


class AppHandler(BaseHTTPRequestHandler):
    def _parse_cookie(self, name: str) -> str:
        raw = self.headers.get("Cookie", "")
        if not raw:
            return ""
        cookie = SimpleCookie()
        cookie.load(raw)
        morsel = cookie.get(name)
        return morsel.value if morsel else ""

    def _current_user(self) -> dict | None:
        token = self._parse_cookie(SESSION_COOKIE_NAME)
        if not token:
            return None
        user_id = get_user_id_for_session(db_path_for(self.data_dir), token)
        if not user_id:
            return None
        return get_app_user_by_id(db_path_for(self.data_dir), user_id)

    def _redirect(self, target: str, set_cookie: str = "") -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", target)
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()

    def _session_cookie(self, token: str, max_age: int = SESSION_MAX_AGE_SECONDS) -> str:
        return f"{SESSION_COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={max_age}"

    def _clear_session_cookie(self) -> str:
        return f"{SESSION_COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"

    data_dir = Path("data")

    def _send_html(self, content: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_form_data(self) -> dict[str, str]:
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(content_length).decode("utf-8") if content_length else ""
        parsed = urllib.parse.parse_qs(raw, keep_blank_values=True)
        return {key: values[0].strip() if values else "" for key, values in parsed.items()}

    def _read_multipart_data(self) -> tuple[dict[str, str], dict[str, list[dict[str, object]]]]:
        content_type = self.headers.get("Content-Type", "")
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(content_length) if content_length else b""
        if not content_type.startswith("multipart/form-data"):
            return ({}, {})

        envelope = (
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body
        )
        message = BytesParser(policy=default).parsebytes(envelope)
        values: dict[str, str] = {}
        files: dict[str, list[dict[str, object]]] = {}

        if not message.is_multipart():
            return (values, files)

        for part in message.iter_parts():
            field_name = part.get_param("name", header="content-disposition")
            if not field_name:
                continue

            filename = part.get_filename()
            payload = part.get_payload(decode=True) or b""
            if filename:
                files.setdefault(field_name, []).append(
                    {
                        "filename": filename,
                        "content": payload,
                        "content_type": part.get_content_type(),
                    }
                )
                continue

            charset = part.get_content_charset() or "utf-8"
            values[field_name] = payload.decode(charset, errors="ignore").strip()

        return (values, files)

    def do_GET(self) -> None:  # noqa: N802 (HTTP verb naming)
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)

        if parsed.path in {"/", "/index.html"}:
            self._send_html(render_home(self.data_dir, self._current_user()))
            return

        if parsed.path == "/create-listing":
            current_user = self._current_user()
            if not current_user:
                self._redirect("/login?next=/create-listing")
                return
            self._send_html(render_create_listing({"seller_name": current_user["full_name"], "seller_email": current_user["email"]}))
            return

        if parsed.path == "/login":
            next_path = query.get("next", ["/"])[0]
            self._send_html(render_login({"next": next_path}))
            return

        if parsed.path == "/register":
            next_path = query.get("next", ["/"])[0]
            self._send_html(render_register({"next": next_path}))
            return

        if parsed.path == "/logout":
            token = self._parse_cookie(SESSION_COOKIE_NAME)
            if token:
                delete_app_session(db_path_for(self.data_dir), token)
            self._redirect("/", set_cookie=self._clear_session_cookie())
            return

        if parsed.path == "/listing":
            listing_id = query.get("listing_id", [""])[0]
            if listing_id:
                self._send_html(render_listing_detail(self.data_dir, listing_id))
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Listing not found")
            return

        if parsed.path == "/styles.css":
            body = CSS_PATH.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path.startswith(f"/{UPLOADS_DIR_NAME}/") or parsed.path.startswith(f"/{SEED_IMAGES_DIR_NAME}/"):
            image_dir = uploads_dir_for(self.data_dir) if parsed.path.startswith(f"/{UPLOADS_DIR_NAME}/") else seed_images_dir_for(self.data_dir)
            file_name = Path(parsed.path).name
            static_image = read_static_image(image_dir, file_name)
            if static_image is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Image not found")
                return

            body, content_type = static_image
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/health":
            body = b'{"status":"ok"}'
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:  # noqa: N802 (HTTP verb naming)
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/register":
            values = self._read_form_data()
            full_name = values.get("full_name", "").strip()
            email = values.get("email", "").strip().lower()
            password = values.get("password", "")
            next_path = values.get("next", "/")
            if not full_name or not email or not password:
                self._send_html(render_register(values, "Name, email, and password are required."), status=HTTPStatus.BAD_REQUEST)
                return
            if len(password) < 8:
                self._send_html(render_register(values, "Password must be at least 8 characters."), status=HTTPStatus.BAD_REQUEST)
                return
            try:
                user = create_app_user(db_path_for(self.data_dir), full_name, email, password)
            except sqlite3.IntegrityError:
                self._send_html(render_register(values, "An account with that email already exists."), status=HTTPStatus.BAD_REQUEST)
                return

            token = create_app_session(db_path_for(self.data_dir), str(user["user_id"]))
            self._redirect(next_path or "/", set_cookie=self._session_cookie(token))
            return

        if parsed.path == "/login":
            values = self._read_form_data()
            email = values.get("email", "").strip().lower()
            password = values.get("password", "")
            next_path = values.get("next", "/")
            user = get_app_user_by_email(db_path_for(self.data_dir), email) if email else None
            if not user or not verify_password(password, str(user.get("password_hash", ""))):
                self._send_html(render_login(values, "Invalid email or password."), status=HTTPStatus.BAD_REQUEST)
                return

            token = create_app_session(db_path_for(self.data_dir), str(user["user_id"]))
            self._redirect(next_path or "/", set_cookie=self._session_cookie(token))
            return

        if parsed.path != "/create-listing":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        current_user = self._current_user()
        if not current_user:
            self._redirect("/login?next=/create-listing")
            return

        content_type = self.headers.get("Content-Type", "")
        if content_type.startswith("multipart/form-data"):
            values, files = self._read_multipart_data()
        else:
            values = self._read_form_data()
            files = {}

        uploaded_primary = ""
        for item in files.get("primary_image", []):
            uploaded_primary = save_uploaded_image(
                self.data_dir,
                str(item.get("filename", "")),
                bytes(item.get("content", b"")),
                str(item.get("content_type", "application/octet-stream")),
            )
            if uploaded_primary:
                break

        uploaded_gallery: list[str] = []
        for item in files.get("gallery_images_files", []):
            url = save_uploaded_image(
                self.data_dir,
                str(item.get("filename", "")),
                bytes(item.get("content", b"")),
                str(item.get("content_type", "application/octet-stream")),
            )
            if url:
                uploaded_gallery.append(url)

        if uploaded_primary:
            values["image_url"] = uploaded_primary

        existing_gallery = [part.strip() for part in values.get("gallery_images", "").split(",") if part.strip()]
        merged_gallery = list(dict.fromkeys(existing_gallery + uploaded_gallery))
        if values.get("image_url", "") and values["image_url"] not in merged_gallery:
            merged_gallery.insert(0, values["image_url"])
        values["gallery_images"] = ",".join(merged_gallery)

        required_fields = ["model", "year", "price", "mileage", "location"]
        missing = [field for field in required_fields if not values.get(field, "").strip()]
        if missing:
            message = "Please fill in required fields: " + ", ".join(missing)
            values["seller_name"] = str(current_user.get("full_name", ""))
            values["seller_email"] = str(current_user.get("email", ""))
            self._send_html(render_create_listing(values, message), status=HTTPStatus.BAD_REQUEST)
            return

        try:
            year = int(values.get("year", "0"))
            price = int(values.get("price", "0"))
            mileage = int(values.get("mileage", "0"))
        except ValueError:
            values["seller_name"] = str(current_user.get("full_name", ""))
            values["seller_email"] = str(current_user.get("email", ""))
            self._send_html(render_create_listing(values, "Year, price, and mileage must be numbers."), status=HTTPStatus.BAD_REQUEST)
            return

        if year < 1970 or year > 2035:
            values["seller_name"] = str(current_user.get("full_name", ""))
            values["seller_email"] = str(current_user.get("email", ""))
            self._send_html(render_create_listing(values, "Year must be between 1970 and 2035."), status=HTTPStatus.BAD_REQUEST)
            return

        if price < 1000 or mileage < 0:
            values["seller_name"] = str(current_user.get("full_name", ""))
            values["seller_email"] = str(current_user.get("email", ""))
            self._send_html(render_create_listing(values, "Price must be at least 1000 and mileage cannot be negative."), status=HTTPStatus.BAD_REQUEST)
            return

        values["year"] = str(year)
        values["price"] = str(price)
        values["mileage"] = str(mileage)

        listing_id = create_user_listing(db_path_for(self.data_dir), values, current_user)
        target = "/listing?listing_id=" + urllib.parse.quote(listing_id)
        self._redirect(target)

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local BMW Marketplace homepage")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind")
    parser.add_argument("--data-dir", default="data", help="Directory containing seed JSON")
    args = parser.parse_args()

    AppHandler.data_dir = Path(args.data_dir)
    init_db(db_path_for(AppHandler.data_dir))
    server = ThreadingHTTPServer((args.host, args.port), AppHandler)
    print(f"Serving homepage on http://{args.host}:{args.port}")
    print(f"Using seed data from: {AppHandler.data_dir.resolve()}")
    server.serve_forever()


if __name__ == "__main__":
    main()
