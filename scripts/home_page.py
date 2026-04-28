#!/usr/bin/env python3
"""Serve BMW Marketplace with FastAPI.

Usage:
    python3 scripts/home_page.py
Then open http://127.0.0.1:8000
"""

from __future__ import annotations

import html
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
import uvicorn

try:
    from .marketplace_core import (  # noqa: F401
        CSS_PATH,
        SESSION_COOKIE_NAME,
        SESSION_MAX_AGE_SECONDS,
        SEED_IMAGES_DIR_NAME,
        UPLOADS_DIR_NAME,
        Path,
        argparse,
        carfax_url_for_vin,
        currency,
        create_app_session,
        create_app_user,
        create_dealer_application,
        approve_dealer_profile,
        reject_dealer_profile,
        suspend_dealer_profile,
        get_active_dealer_profile_for_user,
        get_dealer_membership_for_user,
        get_dealer_profile_by_id,
        get_dealer_profile_for_owner,
        list_all_dealer_profiles,
        list_app_users,
        load_all_listings,
        list_dealer_members,
        list_pending_dealers,
        notice_html,
        update_app_user_role,
        upsert_dealer_member_record,
        user_can_manage_dealer,
        user_can_respond_for_dealer,
        is_site_admin,
        admin_email_set,
        create_user_listing,
        create_listing_inquiry,
        get_inquiry_by_id,
        list_dealer_inquiries,
        add_inquiry_reply,
        set_dealer_inquiry_assignment,
        db_path_for,
        delete_app_session,
        delete_user_listing,
        get_app_user_by_email,
        get_app_user_by_id,
        get_seed_listing_by_selection,
        get_seed_listing_by_vin,
        get_user_id_for_session,
        get_user_listing_for_owner,
        init_db,
        ensure_default_admin,
        seed_demo_dealerships,
        nhtsa_url_for_vin,
        sanitize_vin,
        save_uploaded_image,
        seed_images_dir_for,
        set_user_listing_status,
        uploads_dir_for,
        urllib,
        vehicle_report_links_html,
        verify_password,
        _is_db_integrity_error,
        refresh_user_listing,
        update_app_user,
        update_user_listing,
    )
    from .marketplace_render import (
        render_create_listing,
        render_edit_listing,
        render_home,
        render_listing_detail,
        render_login,
        render_register,
        render_settings,
        render_dealership_settings,
        render_dealership_directory,
        render_dealership_detail,
        render_dealership_inbox,
        render_buyer_inbox,
    )
    from .listing_routes import register_listing_routes
    from .forum_routes import register_forum_routes
except ImportError:
    from marketplace_core import (  # noqa: F401
        CSS_PATH,
        SESSION_COOKIE_NAME,
        SESSION_MAX_AGE_SECONDS,
        SEED_IMAGES_DIR_NAME,
        UPLOADS_DIR_NAME,
        Path,
        argparse,
        carfax_url_for_vin,
        currency,
        create_app_session,
        create_app_user,
        create_dealer_application,
        approve_dealer_profile,
        reject_dealer_profile,
        suspend_dealer_profile,
        get_active_dealer_profile_for_user,
        get_dealer_membership_for_user,
        get_dealer_profile_by_id,
        get_dealer_profile_for_owner,
        list_all_dealer_profiles,
        list_app_users,
        load_all_listings,
        list_dealer_members,
        list_pending_dealers,
        notice_html,
        update_app_user_role,
        upsert_dealer_member_record,
        user_can_manage_dealer,
        user_can_respond_for_dealer,
        is_site_admin,
        admin_email_set,
        create_user_listing,
        create_listing_inquiry,
        get_inquiry_by_id,
        list_dealer_inquiries,
        add_inquiry_reply,
        set_dealer_inquiry_assignment,
        db_path_for,
        delete_app_session,
        delete_user_listing,
        get_app_user_by_email,
        get_app_user_by_id,
        get_seed_listing_by_selection,
        get_seed_listing_by_vin,
        get_user_id_for_session,
        get_user_listing_for_owner,
        init_db,
        ensure_default_admin,
        seed_demo_dealerships,
        nhtsa_url_for_vin,
        sanitize_vin,
        save_uploaded_image,
        seed_images_dir_for,
        set_user_listing_status,
        uploads_dir_for,
        urllib,
        vehicle_report_links_html,
        verify_password,
        _is_db_integrity_error,
        refresh_user_listing,
        update_app_user,
        update_user_listing,
    )
    from marketplace_render import (
        render_create_listing,
        render_edit_listing,
        render_home,
        render_listing_detail,
        render_login,
        render_register,
        render_settings,
        render_dealership_settings,
        render_dealership_directory,
        render_dealership_detail,
        render_dealership_inbox,
        render_buyer_inbox,
    )
    from listing_routes import register_listing_routes
    from forum_routes import register_forum_routes


def _current_user(request: Request, data_dir: Path) -> dict[str, str] | None:
    token = request.cookies.get(SESSION_COOKIE_NAME, "")
    if not token:
        return None
    user_id = get_user_id_for_session(db_path_for(data_dir), token)
    if not user_id:
        return None
    user = get_app_user_by_id(db_path_for(data_dir), user_id)
    return user if isinstance(user, dict) else None


def _html(body: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(content=body, status_code=status_code)


def _redirect(location: str) -> RedirectResponse:
    return RedirectResponse(url=location, status_code=303)


def _redirect_with_session(location: str, token: str) -> RedirectResponse:
    response = RedirectResponse(url=location, status_code=303)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="Lax",
        path="/",
    )
    return response


def _clear_session_redirect(location: str) -> RedirectResponse:
    response = RedirectResponse(url=location, status_code=303)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        "",
        max_age=0,
        httponly=True,
        samesite="Lax",
        path="/",
    )
    return response


async def _request_values_and_files(request: Request) -> tuple[dict[str, str], dict[str, list[dict[str, object]]]]:
    form_data = await request.form()
    values = {key: str(value) for key, value in form_data.multi_items() if not hasattr(value, "filename")}
    files: dict[str, list[dict[str, object]]] = {}
    for key, value in form_data.multi_items():
        if not hasattr(value, "filename"):
            continue
        content = await value.read()
        files.setdefault(key, []).append(
            {
                "filename": value.filename or "",
                "content": content,
                "content_type": value.content_type or "application/octet-stream",
            }
        )
    return values, files


def _resolved_data_dir(data_dir: Path | str | None = None) -> Path:
    if isinstance(data_dir, Path):
        return data_dir
    if isinstance(data_dir, str) and data_dir.strip():
        return Path(data_dir)
    return Path(os.getenv("BMW_MARKETPLACE_DATA_DIR", "data"))


def _community_landing_html(
    page_title: str,
    eyebrow: str,
    heading: str,
    subtitle: str,
    current_user_html: str,
    cards_html: str,
) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8" />'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />'
        f'<title>{html.escape(page_title)}</title><link rel="stylesheet" href="/styles.css" />'
        '<style>'
        '.community-landing .page-hero{display:flex;flex-direction:column;gap:0.75rem;}'
        '.community-landing__grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1rem;margin-top:1.5rem;}'
        '.community-landing__card{border:1px solid rgba(148,163,184,0.35);border-radius:18px;padding:1.25rem;background:#fff;box-shadow:0 1px 2px rgba(15,23,42,0.05);display:flex;flex-direction:column;gap:0.75rem;}'
        '.community-landing__card h2{margin:0;font-size:1.2rem;}'
        '.community-landing__card p{margin:0;color:#334155;}'
        '</style></head><body><main class="page-shell community-landing">'
        '<header class="page-hero">'
        f'<p class="eyebrow">{html.escape(eyebrow)}</p>'
        f'<h1>{html.escape(heading)}</h1>'
        f'<p>{html.escape(subtitle)}</p>'
        f'<p>{current_user_html}</p>'
        '</header>'
        f'<section class="community-landing__grid">{cards_html}</section>'
        '</main></body></html>'
    )


def _admin_dashboard_html(data_dir: Path, current_user: dict[str, str], notice_code: str = "") -> str:
    db = db_path_for(data_dir)
    users = list_app_users(db)
    users_by_id = {str(user.get("user_id", "")): user for user in users}
    dealers = list_all_dealer_profiles(db)
    listings = load_all_listings(data_dir)
    pending_dealers = [dealer for dealer in dealers if str(dealer.get("status", "")).strip().upper() == "PENDING"]
    dealer_listings = [listing for listing in listings if str(listing.get("seller_type", "")).strip().upper() == "DEALER"]

    def user_role_label(role: str) -> str:
        normalized = role.strip().upper()
        if normalized in {"SITE_ADMIN", "ADMIN"}:
            return "Site Admin"
        if normalized == "BUYER":
            return "Buyer"
        if normalized == "DEALER":
            return "Dealer"
        return normalized.replace("_", " ").title() if normalized else "Buyer"

    def dealer_status_label(status: str) -> str:
        cleaned = status.strip().replace("_", " ").lower()
        return cleaned.title() if cleaned else "Unknown"

    def admin_card(title: str, value: str, subtitle: str = "") -> str:
        subtitle_html = f'<p class="admin-card__subtitle">{html.escape(subtitle)}</p>' if subtitle else ""
        return (
            '<article class="admin-card">'
            f'<p class="admin-card__label">{html.escape(title)}</p>'
            f'<strong class="admin-card__value">{html.escape(value)}</strong>'
            f"{subtitle_html}"
            "</article>"
        )

    dealer_rows: list[str] = []
    for dealer in dealers:
        dealer_id = str(dealer.get("dealer_id", ""))
        owner_user = users_by_id.get(str(dealer.get("owner_user_id", "")), {})
        approved_by_user = users_by_id.get(str(dealer.get("approved_by_admin_id", "")), {})
        status = str(dealer.get("status", "")).strip().upper()
        action_html = ""
        if status == "PENDING":
            action_html = (
                '<form class="admin-inline-form" method="post" action="/admin/dealerships/approve">'
                f'<input type="hidden" name="dealer_id" value="{html.escape(dealer_id)}" />'
                '<button class="button primary" type="submit">Approve</button>'
                "</form>"
                '<form class="admin-inline-form" method="post" action="/admin/dealerships/reject">'
                f'<input type="hidden" name="dealer_id" value="{html.escape(dealer_id)}" />'
                '<input type="text" name="reason" placeholder="Reason for rejection" />'
                '<button class="button secondary" type="submit">Reject</button>'
                "</form>"
            )
        elif status == "APPROVED":
            action_html = (
                '<form class="admin-inline-form" method="post" action="/admin/dealerships/suspend">'
                f'<input type="hidden" name="dealer_id" value="{html.escape(dealer_id)}" />'
                '<input type="text" name="reason" placeholder="Reason for suspension" />'
                '<button class="button secondary" type="submit">Suspend</button>'
                "</form>"
            )
        else:
            action_html = (
                '<form class="admin-inline-form" method="post" action="/admin/dealerships/approve">'
                f'<input type="hidden" name="dealer_id" value="{html.escape(dealer_id)}" />'
                '<button class="button primary" type="submit">Approve</button>'
                "</form>"
            )
        dealer_rows.append(
            "<tr>"
            f"<td><strong>{html.escape(str(dealer.get('display_name', '')))}</strong><br />{html.escape(str(dealer.get('legal_name', '')))}</td>"
            f"<td>{html.escape(dealer_status_label(status))}</td>"
            f"<td>{html.escape(str(owner_user.get('full_name', 'Unknown User')))}<br />{html.escape(str(owner_user.get('email', '')))}</td>"
            f"<td>{html.escape(str(dealer.get('website_url', '')) or '—')}</td>"
            f"<td>{html.escape(str(dealer.get('license_number', '')) or '—')}</td>"
            f"<td>{html.escape(str(approved_by_user.get('full_name', '')) or '—')}</td>"
            f"<td>{html.escape(str(dealer.get('approved_at', '')) or '—')}</td>"
            f"<td>{action_html}</td>"
            "</tr>"
        )

    user_rows: list[str] = []
    for user in users:
        user_id = str(user.get("user_id", ""))
        role = str(user.get("role", "BUYER")).strip().upper()
        is_current_user = user_id == str(current_user.get("user_id", ""))
        target_role = "BUYER" if role == "SITE_ADMIN" else "SITE_ADMIN"
        action_label = "Remove admin" if role == "SITE_ADMIN" else "Make admin"
        action_html = (
            '<span class="admin-muted">Current account</span>'
            if is_current_user
            else (
                '<form class="admin-inline-form" method="post" action="/admin/users/role">'
                f'<input type="hidden" name="user_id" value="{html.escape(user_id)}" />'
                f'<input type="hidden" name="target_role" value="{html.escape(target_role)}" />'
                f'<button class="button {"secondary" if role == "SITE_ADMIN" else "primary"}" type="submit">{html.escape(action_label)}</button>'
                "</form>"
            )
        )
        user_rows.append(
            "<tr>"
            f"<td>{html.escape(str(user.get('full_name', '')))}</td>"
            f"<td>{html.escape(str(user.get('email', '')))}</td>"
            f"<td>{html.escape(user_role_label(role))}</td>"
            f"<td>{html.escape(str(user.get('created_at', '')))}</td>"
            f"<td>{action_html}</td>"
            "</tr>"
        )

    listing_rows: list[str] = []
    for listing in listings:
        listing_id = str(listing.get("listing_id", ""))
        listing_url = "/listing?listing_id=" + urllib.parse.quote(listing_id)
        seller_type = str(listing.get("seller_type", "")).strip().upper() or "BUYER"
        listing_rows.append(
            "<tr>"
            f"<td><a href=\"{html.escape(listing_url)}\">{html.escape(str(listing.get('year', '')))} BMW {html.escape(str(listing.get('model', '')))} {html.escape(str(listing.get('trim', '')))}</a></td>"
            f"<td>{html.escape(str(listing.get('seller_name', 'Unknown Seller')))}</td>"
            f"<td>{html.escape(user_role_label(seller_type))}</td>"
            f"<td>{html.escape(str(listing.get('status', '')))}</td>"
            f"<td>{html.escape(currency(int(listing.get('price', 0) or 0)))}</td>"
            f"<td>{html.escape(str(listing.get('location', '')))}</td>"
            f"<td>{html.escape(str(listing.get('dealer_id', '')) or '—')}</td>"
            "</tr>"
        )

    pending_rows_html = "".join(
        [
            "<tr>"
            f"<td><strong>{html.escape(str(dealer.get('display_name', '')))}</strong><br />{html.escape(str(dealer.get('legal_name', '')))}</td>"
            f"<td>{html.escape(str(users_by_id.get(str(dealer.get('owner_user_id', '')), {}).get('email', '')))}</td>"
            f"<td>{html.escape(str(dealer.get('created_at', '')))}</td>"
            "<td>"
            '<form class="admin-inline-form" method="post" action="/admin/dealerships/approve">'
            f'<input type="hidden" name="dealer_id" value="{html.escape(str(dealer.get("dealer_id", "")))}" />'
            '<button class="button primary" type="submit">Approve</button>'
            "</form>"
            '<form class="admin-inline-form" method="post" action="/admin/dealerships/reject">'
            f'<input type="hidden" name="dealer_id" value="{html.escape(str(dealer.get("dealer_id", "")))}" />'
            '<input type="text" name="reason" placeholder="Reason for rejection" />'
            '<button class="button secondary" type="submit">Reject</button>'
            "</form>"
            "</td>"
            "</tr>"
            for dealer in pending_dealers
        ]
    )

    notice_block = notice_html(notice_code)
    if not pending_rows_html:
        pending_rows_html = '<tr><td colspan="4" class="empty-state">No pending dealership applications.</td></tr>'
    dealer_rows_html = "".join(dealer_rows) if dealer_rows else '<tr><td colspan="8" class="empty-state">No dealerships found.</td></tr>'
    user_rows_html = "".join(user_rows) if user_rows else '<tr><td colspan="5" class="empty-state">No users found.</td></tr>'
    listing_rows_html = "".join(listing_rows) if listing_rows else '<tr><td colspan="7" class="empty-state">No listings found.</td></tr>'

    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8" />'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />'
        '<title>Admin dashboard</title><link rel="stylesheet" href="/styles.css" />'
        '<style>'
        '.admin-dashboard .admin-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1rem;margin:1.5rem 0;}'
        '.admin-card{border:1px solid rgba(148,163,184,0.35);border-radius:14px;padding:1rem;background:#fff;box-shadow:0 1px 2px rgba(15,23,42,0.05);}'
        '.admin-card__label{margin:0;color:#64748b;font-size:0.9rem;text-transform:uppercase;letter-spacing:0.04em;}'
        '.admin-card__value{display:block;font-size:1.6rem;margin-top:0.35rem;}'
        '.admin-card__subtitle{margin:0.35rem 0 0;color:#64748b;font-size:0.9rem;}'
        '.admin-section{margin-top:1.75rem;}'
        '.admin-table{width:100%;border-collapse:collapse;margin-top:0.75rem;background:#fff;}'
        '.admin-table th,.admin-table td{border-bottom:1px solid rgba(148,163,184,0.25);padding:0.75rem;text-align:left;vertical-align:top;}'
        '.admin-table th{font-size:0.85rem;text-transform:uppercase;letter-spacing:0.04em;color:#64748b;}'
        '.admin-inline-form{display:inline-flex;gap:0.5rem;align-items:center;flex-wrap:wrap;margin:0 0.25rem 0.25rem 0;}'
        '.admin-inline-form input[type="text"]{min-width:180px;padding:0.45rem 0.65rem;border:1px solid #cbd5e1;border-radius:999px;}'
        '.admin-muted{color:#64748b;}'
        '</style></head><body><main class="page-shell admin-dashboard">'
        '<header class="page-hero">'
        '<p class="eyebrow">Administration</p>'
        '<h1>Admin dashboard</h1>'
        '<p>Review dealerships, listings, and user permissions from one place.</p>'
        f'<p class="admin-muted">Signed in as {html.escape(str(current_user.get("full_name", "")))} · {html.escape(str(current_user.get("email", "")))} · {html.escape(user_role_label(str(current_user.get("role", ""))))}</p>'
        '<p>'
        '<a class="button secondary" href="/">Home</a> '
        '<a class="button secondary" href="/settings">Settings</a> '
        '<a class="button secondary" href="/logout">Log out</a>'
        '</p>'
        '</header>'
        f'{notice_block}'
        '<section class="admin-stats">'
        f'{admin_card("Users", str(len(users)), f"{sum(1 for user in users if str(user.get('role', '')).strip().upper() == 'SITE_ADMIN')} admins")} '
        f'{admin_card("Dealerships", str(len(dealers)), f"{len(pending_dealers)} pending approvals")} '
        f'{admin_card("Listings", str(len(listings)), f"{len(dealer_listings)} dealer listings")} '
        f'{admin_card("Pending dealers", str(len(pending_dealers)), "Awaiting review")} '
        '</section>'
        '<section class="admin-section">'
        '<h2>Pending dealership approvals</h2>'
        '<table class="admin-table">'
        '<thead><tr><th>Dealership</th><th>Owner email</th><th>Submitted</th><th>Actions</th></tr></thead>'
        f'<tbody>{pending_rows_html}</tbody>'
        '</table>'
        '</section>'
        '<section class="admin-section">'
        '<h2>All dealerships</h2>'
        '<table class="admin-table">'
        '<thead><tr><th>Dealership</th><th>Status</th><th>Owner</th><th>Website</th><th>License</th><th>Approved by</th><th>Approved at</th><th>Actions</th></tr></thead>'
        f'<tbody>{dealer_rows_html}</tbody>'
        '</table>'
        '</section>'
        '<section class="admin-section">'
        '<h2>Listings by sellers</h2>'
        '<table class="admin-table">'
        '<thead><tr><th>Vehicle</th><th>Seller</th><th>Seller type</th><th>Status</th><th>Price</th><th>Location</th><th>Dealer ID</th></tr></thead>'
        f'<tbody>{listing_rows_html}</tbody>'
        '</table>'
        '</section>'
        '<section class="admin-section">'
        '<h2>Users and admin access</h2>'
        '<table class="admin-table">'
        '<thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Created</th><th>Actions</th></tr></thead>'
        f'<tbody>{user_rows_html}</tbody>'
        '</table>'
        '</section>'
        '</main></body></html>'
    )


def create_app(data_dir: Path) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    register_listing_routes(app, data_dir)
    register_forum_routes(app, data_dir)

    @app.on_event("startup")
    def startup() -> None:
        db = db_path_for(data_dir)
        init_db(db)
        ensure_default_admin(db)
        seed_demo_dealerships(db)

    @app.get("/")
    @app.get("/index.html")
    def home(request: Request) -> HTMLResponse:
        filters = {
            "search": request.query_params.get("search", ""),
            "chassis_code": request.query_params.get("chassis_code", ""),
            "transmission_type": request.query_params.get("transmission_type", ""),
            "package_name": request.query_params.get("package_name", ""),
            "drive_type": request.query_params.get("drive_type", ""),
            "doors": request.query_params.get("doors", ""),
            "title_filter": request.query_params.get("title_filter", ""),
            "sort_by": request.query_params.get("sort_by", "newest"),
        }
        notice = request.query_params.get("notice", "")
        return _html(render_home(data_dir, _current_user(request, data_dir), filters, notice))

    @app.get("/listings")
    def listings_get(request: Request) -> HTMLResponse:
        filters = {
            "search": request.query_params.get("search", ""),
            "chassis_code": request.query_params.get("chassis_code", ""),
            "transmission_type": request.query_params.get("transmission_type", ""),
            "package_name": request.query_params.get("package_name", ""),
            "drive_type": request.query_params.get("drive_type", ""),
            "doors": request.query_params.get("doors", ""),
            "title_filter": request.query_params.get("title_filter", ""),
            "sort_by": request.query_params.get("sort_by", "newest"),
        }
        notice = request.query_params.get("notice", "")
        return _html(render_home(data_dir, _current_user(request, data_dir), filters, notice))

    @app.get("/dealerships")
    def dealerships_get(request: Request) -> HTMLResponse:
        notice = request.query_params.get("notice", "")
        return _html(render_dealership_directory(data_dir, _current_user(request, data_dir), notice))

    @app.get("/dealerships/{dealer_id}")
    def dealership_detail_get(request: Request, dealer_id: str) -> HTMLResponse:
        notice = request.query_params.get("notice", "")
        return _html(render_dealership_detail(data_dir, dealer_id, _current_user(request, data_dir), notice))

    @app.get("/dealerships/{dealer_id}/inbox")
    def dealership_inbox_get(request: Request, dealer_id: str) -> HTMLResponse:
        notice = request.query_params.get("notice", "")
        return _html(render_dealership_inbox(data_dir, dealer_id, _current_user(request, data_dir), notice))

    @app.get("/inbox")
    def buyer_inbox_get(request: Request) -> HTMLResponse:
        notice = request.query_params.get("notice", "")
        return _html(render_buyer_inbox(data_dir, _current_user(request, data_dir), notice))

    @app.get("/parts")
    def parts_get(request: Request) -> HTMLResponse:
        current_user = _current_user(request, data_dir)
        if current_user:
            current_user_html = (
                f'<span class="auth-welcome">Signed in as {html.escape(current_user.get("full_name", ""))}</span>'
                '<a class="button secondary auth-btn" href="/">Home</a>'
                '<a class="button secondary auth-btn" href="/forums">Forums</a>'
                '<a class="button secondary auth-btn" href="/logout">Log out</a>'
            )
        else:
            current_user_html = (
                '<a class="button secondary auth-btn" href="/">Home</a>'
                '<a class="button secondary auth-btn" href="/login?next=/parts">Log in</a>'
                '<a class="button secondary auth-btn" href="/register?next=/parts">Create account</a>'
            )

        cards_html = "".join(
            [
                '<article class="community-landing__card">',
                '<h2>Browse listings</h2>',
                '<p>Jump back to the main marketplace inventory and compare live vehicles.</p>',
                '<a class="button secondary" href="/">View inventory</a>',
                '</article>',
                '<article class="community-landing__card">',
                '<h2>OEM replacements</h2>',
                '<p>Plan a future catalog for factory-correct parts, trim pieces, and maintenance items.</p>',
                '<a class="button secondary" href="/forums">Open forums</a>',
                '</article>',
                '<article class="community-landing__card">',
                '<h2>Performance upgrades</h2>',
                '<p>Reserve space for wheels, suspension, exhaust, and detailing accessories.</p>',
                '<a class="button secondary" href="/dealerships">Browse dealerships</a>',
                '</article>',
            ]
        )

        return _html(
            _community_landing_html(
                "Parts Marketplace",
                "Parts marketplace",
                "BMW parts and accessories",
                "Use this landing page to route shoppers toward parts, upgrades, and marketplace browsing while the catalog grows.",
                current_user_html,
                cards_html,
            )
        )

    @app.post("/inbox/reply")
    async def buyer_inbox_reply_post(request: Request) -> Response:
        current_user = _current_user(request, data_dir)
        if not current_user:
            return _redirect("/login?next=/inbox")
        values, _ = await _request_values_and_files(request)
        inquiry_id = values.get("inquiry_id", "").strip()
        body = values.get("body", "").strip()
        if not inquiry_id:
            raise HTTPException(status_code=400, detail="Missing inquiry_id")
        if not body:
            return _redirect("/inbox?notice=action_failed")
        try:
            add_inquiry_reply(data_dir, inquiry_id, current_user, body)
        except LookupError:
            raise HTTPException(status_code=404, detail="Inquiry not found")
        except ValueError:
            return _redirect("/inbox?notice=action_failed")
        return _redirect("/inbox?notice=buyer_reply_sent")

    @app.post("/dealerships/{dealer_id}/inbox/reply")
    async def dealership_inbox_reply_post(request: Request, dealer_id: str) -> Response:
        current_user = _current_user(request, data_dir)
        if not current_user:
            return _redirect("/login?next=/dealerships/" + urllib.parse.quote(dealer_id) + "/inbox")
        values, _ = await _request_values_and_files(request)
        values["dealer_id"] = dealer_id
        inquiry_id = values.get("inquiry_id", "").strip()
        body = values.get("body", "").strip()
        if not inquiry_id:
            raise HTTPException(status_code=400, detail="Missing inquiry_id")
        if not body:
            return _redirect("/dealerships/" + urllib.parse.quote(dealer_id) + "/inbox?notice=action_failed")
        db = db_path_for(data_dir)
        if not user_can_respond_for_dealer(db, str(current_user.get("user_id", "")), dealer_id):
            raise HTTPException(status_code=403, detail="Not authorized to reply for this dealership")
        try:
            add_inquiry_reply(data_dir, inquiry_id, current_user, body)
        except LookupError:
            raise HTTPException(status_code=404, detail="Inquiry not found")
        except ValueError:
            return _redirect("/dealerships/" + urllib.parse.quote(dealer_id) + "/inbox?notice=action_failed")
        return _redirect("/dealerships/" + urllib.parse.quote(dealer_id) + "/inbox?notice=dealer_reply_sent")

    @app.post("/dealerships/{dealer_id}/inbox/assign")
    async def dealership_inbox_assign_post(request: Request, dealer_id: str) -> Response:
        current_user = _current_user(request, data_dir)
        if not current_user:
            return _redirect("/login?next=/dealerships/" + urllib.parse.quote(dealer_id) + "/inbox")
        values, _ = await _request_values_and_files(request)
        inquiry_id = values.get("inquiry_id", "").strip()
        assigned_user_id = values.get("assigned_user_id", "").strip()
        if not inquiry_id:
            raise HTTPException(status_code=400, detail="Missing inquiry_id")
        db = db_path_for(data_dir)
        if not user_can_manage_dealer(db, str(current_user.get("user_id", "")), dealer_id):
            raise HTTPException(status_code=403, detail="Not authorized to manage this dealership")
        try:
            set_dealer_inquiry_assignment(data_dir, inquiry_id, dealer_id, assigned_user_id)
        except ValueError:
            return _redirect("/dealerships/" + urllib.parse.quote(dealer_id) + "/inbox?notice=action_failed")
        return _redirect("/dealerships/" + urllib.parse.quote(dealer_id) + "/inbox?notice=dealer_assignment_saved")



    return app


FAVICON_PATH = Path(__file__).with_name("favicon.ico")


def build_app(data_dir: Path | str | None = None) -> FastAPI:
    return create_app(_resolved_data_dir(data_dir))


app = build_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local BMW Marketplace homepage")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind")
    parser.add_argument("--data-dir", default="data", help="Directory containing seed JSON")
    args = parser.parse_args()

    data_dir = _resolved_data_dir(args.data_dir)
    os.environ["BMW_MARKETPLACE_DATA_DIR"] = str(data_dir)
    local_app = build_app(data_dir)
    print(f"Serving homepage on http://{args.host}:{args.port}")
    print(f"Using seed data from: {data_dir.resolve()}")
    uvicorn.run(local_app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
