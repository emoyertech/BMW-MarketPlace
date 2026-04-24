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
    )
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
    )


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


def _resolved_data_dir(data_dir: Path | str | None = None) -> Path:
    if isinstance(data_dir, Path):
        return data_dir
    if isinstance(data_dir, str) and data_dir.strip():
        return Path(data_dir)
    return Path(os.getenv("BMW_MARKETPLACE_DATA_DIR", "data"))


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
    site_admin_count = sum(1 for user in users if str(user.get("role", "")).strip().upper() == "SITE_ADMIN")
    pending_count = len(pending_dealers)
    dealer_listing_count = len(dealer_listings)

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
        f'{admin_card("Users", str(len(users)), f"{site_admin_count} admins")} '
        f'{admin_card("Dealerships", str(len(dealers)), f"{pending_count} pending approvals")} '
        f'{admin_card("Listings", str(len(listings)), f"{dealer_listing_count} dealer listings")} '
        f'{admin_card("Pending dealers", str(pending_count), "Awaiting review")} '
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

    @app.on_event("startup")
    def startup() -> None:
        init_db(db_path_for(data_dir))
        ensure_default_admin(db_path_for(data_dir))

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

    @app.get("/create-listing")
    def create_listing_get(request: Request) -> Response:
        current_user = _current_user(request, data_dir)
        if not current_user:
            return _redirect("/login?next=/create-listing")
        return _html(
            render_create_listing(
                data_dir,
                {
                    "seller_name": str(current_user.get("full_name", "")),
                    "seller_email": str(current_user.get("email", "")),
                },
            )
        )

    @app.get("/vin-preview")
    def vin_preview(request: Request) -> JSONResponse:
        vin = request.query_params.get("vin", "")
        listing = get_seed_listing_by_vin(data_dir, vin)
        clean_vin = sanitize_vin(vin)
        if not listing:
            return JSONResponse({"ok": False, "message": "No vehicle found for this VIN in the local catalog."})
        return JSONResponse(
            {
                "ok": True,
                "vin": clean_vin,
                "title": f'{listing.get("year", "")} BMW {listing.get("model", "")} {listing.get("trim", "")}'.strip(),
                "summary": f'{listing.get("body_style", "Unknown")} | {listing.get("drive_type", "Unknown")} | Title: {listing.get("title_type", "Unknown")}',
                "carfax_url": carfax_url_for_vin(clean_vin),
                "nhtsa_url": nhtsa_url_for_vin(clean_vin),
            }
        )

    @app.get("/login")
    def login_get(request: Request) -> HTMLResponse:
        return _html(render_login({"next": request.query_params.get("next", "/")}))

    @app.get("/register")
    def register_get(request: Request) -> HTMLResponse:
        return _html(render_register({"next": request.query_params.get("next", "/")}))

    @app.get("/settings")
    def settings_get(request: Request) -> Response:
        current_user = _current_user(request, data_dir)
        if not current_user:
            return _redirect("/login?next=/settings")
        notice = request.query_params.get("notice", "")
        dealership_html = render_dealership_settings(data_dir, current_user)
        return _html(render_settings(current_user, notice_code=notice, dealership_html=dealership_html))

    @app.post("/settings/dealership/apply")
    async def dealership_apply_post(request: Request) -> Response:
        current_user = _current_user(request, data_dir)
        if not current_user:
            return _redirect("/login?next=/settings")
        values, _ = await _request_values_and_files(request)
        db = db_path_for(data_dir)
        user_id = str(current_user.get("user_id", ""))
        legal_name = values.get("legal_name", "").strip()
        display_name = values.get("display_name", "").strip()
        website_url = values.get("website_url", "").strip()
        license_number = values.get("license_number", "").strip()
        if not legal_name or not display_name:
            return _html(
                render_settings(
                    current_user,
                    values,
                    "Legal name and display name are required.",
                    dealership_html=render_dealership_settings(data_dir, current_user, values),
                ),
                400,
            )
        if get_active_dealer_profile_for_user(db, user_id):
            return _html(
                render_settings(
                    current_user,
                    values,
                    "You already belong to an approved dealership.",
                    dealership_html=render_dealership_settings(data_dir, current_user, values),
                ),
                400,
            )
        try:
            create_dealer_application(db, user_id, legal_name, display_name, website_url, license_number)
        except ValueError as exc:
            return _html(
                render_settings(
                    current_user,
                    values,
                    str(exc),
                    dealership_html=render_dealership_settings(data_dir, current_user, values),
                ),
                400,
            )
        return _redirect("/settings?notice=dealer_application_submitted")

    @app.post("/settings/dealership/members")
    async def dealership_members_post(request: Request) -> Response:
        current_user = _current_user(request, data_dir)
        if not current_user:
            return _redirect("/login?next=/settings")
        values, _ = await _request_values_and_files(request)
        db = db_path_for(data_dir)
        dealer_id = values.get("dealer_id", "").strip()
        member_email = values.get("member_email", "").strip().lower()
        member_user_id = values.get("member_user_id", "").strip()
        member_role = values.get("member_role", "SALESPERSON").strip().upper()
        member_status = values.get("member_status", "ACTIVE").strip().upper()
        if not dealer_id:
            return _html(
                render_settings(
                    current_user,
                    values,
                    "Missing dealer_id.",
                    dealership_html=render_dealership_settings(data_dir, current_user, values),
                ),
                400,
            )
        if not user_can_manage_dealer(db, str(current_user.get("user_id", "")), dealer_id):
            return _html(
                render_settings(
                    current_user,
                    values,
                    "Not authorized to manage this dealership.",
                    dealership_html=render_dealership_settings(data_dir, current_user, values),
                ),
                403,
            )
        member_user = get_app_user_by_id(db, member_user_id) if member_user_id else None
        if not member_user and member_email:
            member_user = get_app_user_by_email(db, member_email)
        if not member_user:
            return _html(
                render_settings(
                    current_user,
                    values,
                    "Member user not found.",
                    dealership_html=render_dealership_settings(data_dir, current_user, values),
                ),
                404,
            )
        upsert_dealer_member_record(
            db,
            dealer_id,
            str(member_user.get("user_id", "")),
            member_role,
            member_status,
            str(current_user.get("user_id", "")),
        )
        return _redirect("/settings?notice=dealer_member_saved")

    @app.get("/listing")
    def listing_detail(request: Request) -> HTMLResponse:
        listing_id = request.query_params.get("listing_id", "").strip()
        if not listing_id:
            raise HTTPException(status_code=404, detail="Listing not found")
        notice = request.query_params.get("notice", "")
        return _html(render_listing_detail(data_dir, listing_id, _current_user(request, data_dir), notice))

    @app.get("/edit-listing")
    def edit_listing_get(request: Request) -> Response:
        current_user = _current_user(request, data_dir)
        if not current_user:
            quoted_path = urllib.parse.quote(str(request.url.path + ("?" + str(request.url.query) if request.url.query else "")))
            return _redirect("/login?next=" + quoted_path)
        listing_id = request.query_params.get("listing_id", "").strip()
        if not listing_id:
            raise HTTPException(status_code=400, detail="Missing listing_id")
        listing = get_user_listing_for_owner(
            db_path_for(data_dir), listing_id, str(current_user.get("user_id", ""))
        )
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")
        return _html(render_edit_listing(listing))

    @app.get("/styles.css")
    def styles_css() -> FileResponse:
        return FileResponse(CSS_PATH, media_type="text/css")

    @app.get("/favicon.ico")
    def favicon() -> FileResponse:
        if not FAVICON_PATH.exists() or not FAVICON_PATH.is_file():
            raise HTTPException(status_code=404, detail="Favicon not found")
        return FileResponse(FAVICON_PATH, media_type="image/svg+xml")

    @app.get(f"/{UPLOADS_DIR_NAME}/{{file_name:path}}")
    def uploads_file(file_name: str) -> FileResponse:
        file_path = uploads_dir_for(data_dir) / file_name
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail="Image not found")
        return FileResponse(file_path)

    @app.get(f"/{SEED_IMAGES_DIR_NAME}/{{file_name:path}}")
    def seed_image_file(file_name: str) -> FileResponse:
        file_path = seed_images_dir_for(data_dir) / file_name
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail="Image not found")
        return FileResponse(file_path)

    @app.post("/logout")
    def logout_post(request: Request) -> RedirectResponse:
        token = request.cookies.get(SESSION_COOKIE_NAME, "")
        if token:
            delete_app_session(db_path_for(data_dir), token)
        return _clear_session_redirect("/")

    @app.post("/refresh-listing")
    async def refresh_listing_post(request: Request) -> Response:
        current_user = _current_user(request, data_dir)
        if not current_user:
            return _redirect("/login?next=/")
        values, _ = await _request_values_and_files(request)
        listing_id = values.get("listing_id", "").strip()
        if not listing_id:
            raise HTTPException(status_code=400, detail="Missing listing_id")
        refresh_user_listing(db_path_for(data_dir), listing_id, str(current_user.get("user_id", "")))
        return _redirect("/listing?listing_id=" + urllib.parse.quote(listing_id) + "&notice=refreshed")

    @app.post("/listing-status")
    async def listing_status_post(request: Request) -> Response:
        current_user = _current_user(request, data_dir)
        if not current_user:
            return _redirect("/login?next=/")
        values, _ = await _request_values_and_files(request)
        listing_id = values.get("listing_id", "").strip()
        status = values.get("status", "").strip().upper()
        if not listing_id or not status:
            raise HTTPException(status_code=400, detail="Missing listing action fields")
        changed = set_user_listing_status(
            db_path_for(data_dir), listing_id, str(current_user.get("user_id", "")), status
        )
        notice_code = status.lower() if changed else "action_failed"
        return _redirect(
            "/listing?listing_id="
            + urllib.parse.quote(listing_id)
            + "&notice="
            + urllib.parse.quote(notice_code)
        )

    @app.post("/delete-listing")
    async def delete_listing_post(request: Request) -> Response:
        current_user = _current_user(request, data_dir)
        if not current_user:
            return _redirect("/login?next=/")
        values, _ = await _request_values_and_files(request)
        listing_id = values.get("listing_id", "").strip()
        if not listing_id:
            raise HTTPException(status_code=400, detail="Missing listing_id")
        deleted = delete_user_listing(
            db_path_for(data_dir), listing_id, str(current_user.get("user_id", ""))
        )
        if deleted:
            return _redirect("/?notice=deleted")
        return _redirect(
            "/listing?listing_id=" + urllib.parse.quote(listing_id) + "&notice=action_failed"
        )

    @app.post("/inquiries")
    async def inquiries_post(request: Request) -> Response:
        current_user = _current_user(request, data_dir)
        if not current_user:
            return _redirect("/login?next=/")
        values, _ = await _request_values_and_files(request)
        listing_id = values.get("listing_id", "").strip()
        body = values.get("body", "").strip()
        if not listing_id:
            raise HTTPException(status_code=400, detail="Missing listing_id")
        try:
            create_listing_inquiry(data_dir, listing_id, current_user, body)
        except LookupError:
            raise HTTPException(status_code=404, detail="Listing not found")
        except ValueError as exc:
            return _redirect(
                "/listing?listing_id=" + urllib.parse.quote(listing_id) + "&notice=" + urllib.parse.quote("action_failed")
            )
        return _redirect(
            "/listing?listing_id=" + urllib.parse.quote(listing_id) + "&notice=inquiry_submitted"
        )

    @app.post("/edit-listing")
    async def edit_listing_post(request: Request) -> Response:
        current_user = _current_user(request, data_dir)
        if not current_user:
            return _redirect("/login?next=/")

        values, files = await _request_values_and_files(request)

        listing_id = values.get("listing_id", "").strip()
        if not listing_id:
            raise HTTPException(status_code=400, detail="Missing listing_id")

        existing = get_user_listing_for_owner(
            db_path_for(data_dir), listing_id, str(current_user.get("user_id", ""))
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Listing not found")

        uploaded_primary = ""
        for item in files.get("primary_image", []):
            uploaded_primary = save_uploaded_image(
                data_dir,
                str(item.get("filename", "")),
                bytes(item.get("content", b"")),
                str(item.get("content_type", "application/octet-stream")),
            )
            if uploaded_primary:
                break

        uploaded_gallery: list[str] = []
        for item in files.get("gallery_images_files", []):
            url = save_uploaded_image(
                data_dir,
                str(item.get("filename", "")),
                bytes(item.get("content", b"")),
                str(item.get("content_type", "application/octet-stream")),
            )
            if url:
                uploaded_gallery.append(url)

        if uploaded_primary:
            values["image_url"] = uploaded_primary
        elif not values.get("image_url", "").strip():
            values["image_url"] = str(existing.get("image_url", ""))

        existing_gallery = [part.strip() for part in values.get("gallery_images", "").split(",") if part.strip()]
        if not existing_gallery:
            existing_gallery = [
                str(item).strip() for item in existing.get("gallery_images", []) if str(item).strip()
            ]
        values["gallery_images"] = ",".join(list(dict.fromkeys(existing_gallery + uploaded_gallery)))

        required_fields = ["price", "mileage", "location"]
        missing = [field for field in required_fields if not values.get(field, "").strip()]
        if missing:
            merged = {**existing, **values}
            return _html(render_edit_listing(merged, "Please fill in required fields: " + ", ".join(missing)), 400)

        try:
            price = int(values.get("price", "0"))
            mileage = int(values.get("mileage", "0"))
        except ValueError:
            merged = {**existing, **values}
            return _html(render_edit_listing(merged, "Price and mileage must be numbers."), 400)

        if price < 1000 or mileage < 0:
            merged = {**existing, **values}
            return _html(
                render_edit_listing(
                    merged,
                    "Price must be at least 1000 and mileage cannot be negative.",
                ),
                400,
            )

        values["price"] = str(price)
        values["mileage"] = str(mileage)
        if not values.get("status", "").strip():
            values["status"] = str(existing.get("status", "ACTIVE"))

        updated = update_user_listing(
            db_path_for(data_dir), listing_id, str(current_user.get("user_id", "")), values
        )
        if updated:
            return _redirect("/listing?listing_id=" + urllib.parse.quote(listing_id) + "&notice=saved")
        return _redirect(
            "/listing?listing_id=" + urllib.parse.quote(listing_id) + "&notice=action_failed"
        )

    @app.post("/register")
    async def register_post(request: Request) -> Response:
        values, _ = await _request_values_and_files(request)
        full_name = values.get("full_name", "").strip()
        email = values.get("email", "").strip().lower()
        password = values.get("password", "")
        next_path = values.get("next", "/")
        if not full_name or not email or not password:
            return _html(render_register(values, "Name, email, and password are required."), 400)
        if len(password) < 8:
            return _html(render_register(values, "Password must be at least 8 characters."), 400)
        user_role = "SITE_ADMIN" if email in admin_email_set() else "BUYER"
        try:
            user = create_app_user(db_path_for(data_dir), full_name, email, password, user_role)
        except Exception as exc:
            if _is_db_integrity_error(exc):
                return _html(render_register(values, "An account with that email already exists."), 400)
            raise

        token = create_app_session(db_path_for(data_dir), str(user["user_id"]))
        return _redirect_with_session(next_path or "/", token)

    @app.post("/login")
    async def login_post(request: Request) -> Response:
        values, _ = await _request_values_and_files(request)
        email = values.get("email", "").strip().lower()
        password = values.get("password", "")
        next_path = values.get("next", "/")
        user = get_app_user_by_email(db_path_for(data_dir), email) if email else None
        if not user or not verify_password(password, str(user.get("password_hash", ""))):
            return _html(render_login(values, "Invalid email or password."), 400)
        token = create_app_session(db_path_for(data_dir), str(user["user_id"]))
        return _redirect_with_session(next_path or "/", token)

    @app.post("/settings")
    async def settings_post(request: Request) -> Response:
        current_user = _current_user(request, data_dir)
        if not current_user:
            return _redirect("/login?next=/settings")

        values, _ = await _request_values_and_files(request)
        full_name = values.get("full_name", "").strip()
        email = values.get("email", "").strip().lower()
        current_password = values.get("current_password", "")
        new_password = values.get("new_password", "")
        confirm_password = values.get("confirm_password", "")

        if not full_name or not email or not current_password:
            return _html(
                render_settings(
                    current_user,
                    values,
                    "Name, email, and current password are required.",
                    dealership_html=render_dealership_settings(data_dir, current_user, values),
                ),
                400,
            )

        if not verify_password(current_password, str(current_user.get("password_hash", ""))):
            return _html(
                render_settings(
                    current_user,
                    values,
                    "Current password is incorrect.",
                    dealership_html=render_dealership_settings(data_dir, current_user, values),
                ),
                400,
            )

        if new_password or confirm_password:
            if len(new_password) < 8:
                return _html(
                    render_settings(
                        current_user,
                        values,
                        "New password must be at least 8 characters.",
                        dealership_html=render_dealership_settings(data_dir, current_user, values),
                    ),
                    400,
                )
            if new_password != confirm_password:
                return _html(
                    render_settings(
                        current_user,
                        values,
                        "New password and confirmation must match.",
                        dealership_html=render_dealership_settings(data_dir, current_user, values),
                    ),
                    400,
                )

        try:
            updated = update_app_user(
                db_path_for(data_dir),
                str(current_user.get("user_id", "")),
                full_name,
                email,
                new_password,
            )
        except Exception as exc:
            if _is_db_integrity_error(exc):
                return _html(
                    render_settings(
                        current_user,
                        values,
                        "An account with that email already exists.",
                        dealership_html=render_dealership_settings(data_dir, current_user, values),
                    ),
                    400,
                )
            raise

        if not updated:
            return _html(
                render_settings(
                    current_user,
                    values,
                    "We could not save your settings.",
                    dealership_html=render_dealership_settings(data_dir, current_user, values),
                ),
                400,
            )

        return _redirect("/settings?notice=settings_saved")

    @app.post("/create-listing")
    async def create_listing_post(request: Request) -> Response:
        current_user = _current_user(request, data_dir)
        if not current_user:
            return _redirect("/login?next=/create-listing")

        values, files = await _request_values_and_files(request)

        values["seller_name"] = str(current_user.get("full_name", ""))
        values["seller_email"] = str(current_user.get("email", ""))

        uploaded_primary = ""
        for item in files.get("primary_image", []):
            uploaded_primary = save_uploaded_image(
                data_dir,
                str(item.get("filename", "")),
                bytes(item.get("content", b"")),
                str(item.get("content_type", "application/octet-stream")),
            )
            if uploaded_primary:
                break
        if uploaded_primary:
            values["image_url"] = uploaded_primary

        uploaded_gallery: list[str] = []
        for item in files.get("gallery_images_files", []):
            url = save_uploaded_image(
                data_dir,
                str(item.get("filename", "")),
                bytes(item.get("content", b"")),
                str(item.get("content_type", "application/octet-stream")),
            )
            if url:
                uploaded_gallery.append(url)

        existing_gallery = [part.strip() for part in values.get("gallery_images", "").split(",") if part.strip()]
        merged_gallery = list(dict.fromkeys(existing_gallery + uploaded_gallery))
        if values.get("image_url", "").strip() and values["image_url"] not in merged_gallery:
            merged_gallery.insert(0, values["image_url"])
        values["gallery_images"] = ",".join(merged_gallery)

        required_fields = [
            "selected_year",
            "selected_model",
            "selected_trim",
            "vin",
            "price",
            "mileage",
            "location",
        ]
        missing = [field for field in required_fields if not values.get(field, "").strip()]
        if missing:
            return _html(
                render_create_listing(
                    data_dir,
                    values,
                    "Please fill in required fields: " + ", ".join(missing),
                ),
                400,
            )

        cleaned_vin = sanitize_vin(values.get("vin", ""))
        if not cleaned_vin:
            return _html(render_create_listing(data_dir, values, "VIN is required."), 400)
        values["vin"] = cleaned_vin

        values["year"] = values.get("selected_year", "").strip()
        values["model"] = values.get("selected_model", "").strip()
        values["trim"] = values.get("selected_trim", "").strip()

        seed_vehicle = get_seed_listing_by_vin(data_dir, cleaned_vin)
        if seed_vehicle:
            values["body_style"] = str(seed_vehicle.get("body_style", values.get("body_style", "Unknown")))
            values["drive_type"] = str(seed_vehicle.get("drive_type", values.get("drive_type", "Unknown")))
            values["title_type"] = str(seed_vehicle.get("title_type", values.get("title_type", "Clean")))
            if not values.get("description", "").strip():
                values["description"] = str(seed_vehicle.get("description", ""))
            if not values.get("image_url", "").strip():
                values["image_url"] = str(seed_vehicle.get("image_url", "")).strip()
            seed_gallery = [
                str(item).strip() for item in seed_vehicle.get("gallery_images", []) if str(item).strip()
            ]
            if seed_gallery:
                existing_gallery = [
                    part.strip() for part in values.get("gallery_images", "").split(",") if part.strip()
                ]
                values["gallery_images"] = ",".join(list(dict.fromkeys(existing_gallery + seed_gallery)))
        else:
            values["body_style"] = values.get("body_style", "Unknown")
            values["drive_type"] = values.get("drive_type", "Unknown")
            values["title_type"] = values.get("title_type", "Clean")

        try:
            price = int(values.get("price", "0"))
            mileage = int(values.get("mileage", "0"))
            year = int(values.get("year", "0"))
        except ValueError:
            return _html(render_create_listing(data_dir, values, "Price and mileage must be numbers."), 400)

        if year < 1970 or year > 2035:
            return _html(render_create_listing(data_dir, values, "Year must be between 1970 and 2035."), 400)
        if price < 1000 or mileage < 0:
            return _html(
                render_create_listing(
                    data_dir,
                    values,
                    "Price must be at least 1000 and mileage cannot be negative.",
                ),
                400,
            )

        values["year"] = str(year)
        values["price"] = str(price)
        values["mileage"] = str(mileage)

        listing_id = create_user_listing(db_path_for(data_dir), values, current_user)
        target = "/listing?listing_id=" + urllib.parse.quote(listing_id) + "&notice=created"
        return _redirect(target)

    @app.get("/admin")
    def admin_dashboard(request: Request) -> Response:
        current_user = _current_user(request, data_dir)
        if not current_user:
            return _redirect("/login?next=/admin")
        if not is_site_admin(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")
        notice = request.query_params.get("notice", "")
        return _html(_admin_dashboard_html(data_dir, current_user, notice))

    @app.post("/admin/dealerships/approve")
    async def admin_dealership_approve_post(request: Request) -> Response:
        current_user = _current_user(request, data_dir)
        if not current_user:
            return _redirect("/login?next=/admin")
        if not is_site_admin(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")
        values, _ = await _request_values_and_files(request)
        dealer_id = values.get("dealer_id", "").strip()
        if not dealer_id:
            return _redirect("/admin?notice=action_failed")
        profile = approve_dealer_profile(db_path_for(data_dir), dealer_id, str(current_user.get("user_id", "")))
        if not profile:
            return _redirect("/admin?notice=action_failed")
        return _redirect("/admin?notice=dealer_approved")

    @app.post("/admin/dealerships/reject")
    async def admin_dealership_reject_post(request: Request) -> Response:
        current_user = _current_user(request, data_dir)
        if not current_user:
            return _redirect("/login?next=/admin")
        if not is_site_admin(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")
        values, _ = await _request_values_and_files(request)
        dealer_id = values.get("dealer_id", "").strip()
        reason = values.get("reason", "").strip()
        if not dealer_id:
            return _redirect("/admin?notice=action_failed")
        profile = reject_dealer_profile(db_path_for(data_dir), dealer_id, str(current_user.get("user_id", "")), reason)
        if not profile:
            return _redirect("/admin?notice=action_failed")
        return _redirect("/admin?notice=dealer_rejected")

    @app.post("/admin/dealerships/suspend")
    async def admin_dealership_suspend_post(request: Request) -> Response:
        current_user = _current_user(request, data_dir)
        if not current_user:
            return _redirect("/login?next=/admin")
        if not is_site_admin(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")
        values, _ = await _request_values_and_files(request)
        dealer_id = values.get("dealer_id", "").strip()
        reason = values.get("reason", "").strip()
        if not dealer_id:
            return _redirect("/admin?notice=action_failed")
        profile = suspend_dealer_profile(db_path_for(data_dir), dealer_id, str(current_user.get("user_id", "")), reason)
        if not profile:
            return _redirect("/admin?notice=action_failed")
        return _redirect("/admin?notice=dealer_suspended")

    @app.post("/admin/users/role")
    async def admin_user_role_post(request: Request) -> Response:
        current_user = _current_user(request, data_dir)
        if not current_user:
            return _redirect("/login?next=/admin")
        if not is_site_admin(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")
        values, _ = await _request_values_and_files(request)
        target_user_id = values.get("user_id", "").strip()
        target_role = values.get("target_role", "BUYER").strip().upper()
        if not target_user_id or target_role not in {"BUYER", "SITE_ADMIN"}:
            return _redirect("/admin?notice=action_failed")
        if target_user_id == str(current_user.get("user_id", "")) and target_role != "SITE_ADMIN":
            return _redirect("/admin?notice=action_failed")
        if not update_app_user_role(db_path_for(data_dir), target_user_id, target_role):
            return _redirect("/admin?notice=action_failed")
        return _redirect("/admin?notice=admin_role_updated")

    @app.get("/api/dealership/me")
    def dealership_me(request: Request) -> JSONResponse:
        current_user = _current_user(request, data_dir)
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        db = db_path_for(data_dir)
        user_id = str(current_user.get("user_id", ""))
        active_profile = get_active_dealer_profile_for_user(db, user_id)
        application_profile = get_dealer_profile_for_owner(db, user_id)
        membership = None
        if active_profile:
            membership = get_dealer_membership_for_user(db, str(active_profile.get("dealer_id", "")), user_id)
        can_manage = bool(active_profile and user_can_manage_dealer(db, user_id, str(active_profile.get("dealer_id", ""))))
        can_respond = bool(active_profile and user_can_respond_for_dealer(db, user_id, str(active_profile.get("dealer_id", ""))))
        return JSONResponse(
            {
                "ok": True,
                "user": {
                    "user_id": user_id,
                    "full_name": str(current_user.get("full_name", "")),
                    "email": str(current_user.get("email", "")),
                    "role": str(current_user.get("role", "BUYER")),
                },
                "dealer_profile": active_profile,
                "application_profile": application_profile,
                "membership": membership,
                "can_manage": can_manage,
                "can_respond": can_respond,
                "is_admin": is_site_admin(current_user),
            }
        )

    @app.post("/api/dealership/apply")
    async def dealership_apply_post(request: Request) -> JSONResponse:
        current_user = _current_user(request, data_dir)
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        db = db_path_for(data_dir)
        user_id = str(current_user.get("user_id", ""))
        if get_active_dealer_profile_for_user(db, user_id):
            raise HTTPException(status_code=400, detail="This user already belongs to an approved dealership.")
        values, _ = await _request_values_and_files(request)
        legal_name = values.get("legal_name", "").strip()
        display_name = values.get("display_name", "").strip()
        website_url = values.get("website_url", "").strip()
        license_number = values.get("license_number", "").strip()
        if not legal_name or not display_name:
            raise HTTPException(status_code=400, detail="legal_name and display_name are required")
        try:
            profile = create_dealer_application(db, user_id, legal_name, display_name, website_url, license_number)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return JSONResponse({"ok": True, "dealer_profile": profile, "notice": "dealer_application_submitted"})

    @app.get("/api/dealership/members")
    def dealership_members_get(request: Request) -> JSONResponse:
        current_user = _current_user(request, data_dir)
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        db = db_path_for(data_dir)
        dealer_id = request.query_params.get("dealer_id", "").strip()
        if not dealer_id:
            raise HTTPException(status_code=400, detail="Missing dealer_id")
        if not user_can_manage_dealer(db, str(current_user.get("user_id", "")), dealer_id):
            raise HTTPException(status_code=403, detail="Not authorized to manage this dealership")
        return JSONResponse({"ok": True, "dealer_id": dealer_id, "members": list_dealer_members(db, dealer_id)})

    @app.post("/api/dealership/members")
    async def dealership_members_post(request: Request) -> JSONResponse:
        current_user = _current_user(request, data_dir)
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        db = db_path_for(data_dir)
        values, _ = await _request_values_and_files(request)
        dealer_id = values.get("dealer_id", "").strip()
        member_email = values.get("member_email", "").strip().lower()
        member_user_id = values.get("member_user_id", "").strip()
        member_role = values.get("member_role", "SALESPERSON").strip().upper()
        member_status = values.get("member_status", "ACTIVE").strip().upper()
        if not dealer_id:
            raise HTTPException(status_code=400, detail="Missing dealer_id")
        if not user_can_manage_dealer(db, str(current_user.get("user_id", "")), dealer_id):
            raise HTTPException(status_code=403, detail="Not authorized to manage this dealership")
        member_user = get_app_user_by_id(db, member_user_id) if member_user_id else None
        if not member_user and member_email:
            member_user = get_app_user_by_email(db, member_email)
        if not member_user:
            raise HTTPException(status_code=404, detail="Member user not found")
        membership = upsert_dealer_member_record(
            db,
            dealer_id,
            str(member_user.get("user_id", "")),
            member_role,
            member_status,
            str(current_user.get("user_id", "")),
        )
        return JSONResponse({"ok": True, "dealer_id": dealer_id, "membership": membership, "notice": "dealer_member_added"})

    @app.get("/api/admin/dealerships/pending")
    def admin_pending_dealerships(request: Request) -> JSONResponse:
        current_user = _current_user(request, data_dir)
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        if not is_site_admin(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")
        db = db_path_for(data_dir)
        return JSONResponse({"ok": True, "pending_dealerships": list_pending_dealers(db)})

    @app.post("/api/admin/dealerships/approve")
    async def admin_approve_dealership(request: Request) -> JSONResponse:
        current_user = _current_user(request, data_dir)
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        if not is_site_admin(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")
        values, _ = await _request_values_and_files(request)
        dealer_id = values.get("dealer_id", "").strip()
        if not dealer_id:
            raise HTTPException(status_code=400, detail="Missing dealer_id")
        profile = approve_dealer_profile(db_path_for(data_dir), dealer_id, str(current_user.get("user_id", "")))
        if not profile:
            raise HTTPException(status_code=404, detail="Dealer not found")
        return JSONResponse({"ok": True, "dealer_profile": profile, "notice": "dealer_approved"})

    @app.post("/api/admin/dealerships/reject")
    async def admin_reject_dealership(request: Request) -> JSONResponse:
        current_user = _current_user(request, data_dir)
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        if not is_site_admin(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")
        values, _ = await _request_values_and_files(request)
        dealer_id = values.get("dealer_id", "").strip()
        reason = values.get("reason", "").strip()
        if not dealer_id:
            raise HTTPException(status_code=400, detail="Missing dealer_id")
        profile = reject_dealer_profile(db_path_for(data_dir), dealer_id, str(current_user.get("user_id", "")), reason)
        if not profile:
            raise HTTPException(status_code=404, detail="Dealer not found")
        return JSONResponse({"ok": True, "dealer_profile": profile, "notice": "dealer_rejected"})

    @app.post("/api/admin/dealerships/suspend")
    async def admin_suspend_dealership(request: Request) -> JSONResponse:
        current_user = _current_user(request, data_dir)
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        if not is_site_admin(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")
        values, _ = await _request_values_and_files(request)
        dealer_id = values.get("dealer_id", "").strip()
        reason = values.get("reason", "").strip()
        if not dealer_id:
            raise HTTPException(status_code=400, detail="Missing dealer_id")
        profile = suspend_dealer_profile(db_path_for(data_dir), dealer_id, str(current_user.get("user_id", "")), reason)
        if not profile:
            raise HTTPException(status_code=404, detail="Dealer not found")
        return JSONResponse({"ok": True, "dealer_profile": profile, "notice": "dealer_suspended"})

    @app.get("/api/dealership/inquiries")
    def dealership_inquiries(request: Request) -> JSONResponse:
        current_user = _current_user(request, data_dir)
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        db = db_path_for(data_dir)
        user_id = str(current_user.get("user_id", ""))
        dealer_id = request.query_params.get("dealer_id", "").strip()
        active_profile = get_active_dealer_profile_for_user(db, user_id)
        if not dealer_id and active_profile:
            dealer_id = str(active_profile.get("dealer_id", "")).strip()
        if not dealer_id:
            raise HTTPException(status_code=400, detail="Missing dealer_id")
        if not (user_can_manage_dealer(db, user_id, dealer_id) or user_can_respond_for_dealer(db, user_id, dealer_id)):
            raise HTTPException(status_code=403, detail="Not authorized to view this dealership inbox")
        profile = get_dealer_profile_by_id(db, dealer_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Dealer not found")
        return JSONResponse(
            {
                "ok": True,
                "dealer_profile": profile,
                "can_manage": user_can_manage_dealer(db, user_id, dealer_id),
                "can_respond": user_can_respond_for_dealer(db, user_id, dealer_id),
                "inquiries": list_dealer_inquiries(data_dir, dealer_id),
            }
        )

    @app.post("/api/dealership/reply")
    async def dealership_reply_post(request: Request) -> JSONResponse:
        current_user = _current_user(request, data_dir)
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        db = db_path_for(data_dir)
        values, _ = await _request_values_and_files(request)
        inquiry_id = values.get("inquiry_id", "").strip()
        body = values.get("body", "").strip()
        dealer_id = values.get("dealer_id", "").strip()
        if not inquiry_id:
            raise HTTPException(status_code=400, detail="Missing inquiry_id")
        if not body:
            raise HTTPException(status_code=400, detail="Message body is required")
        inquiry = get_inquiry_by_id(data_dir, inquiry_id)
        if not inquiry:
            raise HTTPException(status_code=404, detail="Inquiry not found")
        if not dealer_id:
            dealer_id = str(inquiry.get("dealer_id", "")).strip()
        if not dealer_id:
            listing_id = str(inquiry.get("listing_id", "")).strip()
            listing = next((item for item in load_all_listings(data_dir) if str(item.get("listing_id", "")) == listing_id), {})
            dealer_id = str(listing.get("dealer_id", "")).strip()
        if not dealer_id:
            raise HTTPException(status_code=400, detail="Inquiry is not associated with a dealership")
        if not user_can_respond_for_dealer(db, str(current_user.get("user_id", "")), dealer_id):
            raise HTTPException(status_code=403, detail="Not authorized to reply for this dealership")
        result = add_inquiry_reply(data_dir, inquiry_id, current_user, body)
        return JSONResponse(
            {
                "ok": True,
                "notice": "dealer_reply_sent",
                "dealer_id": dealer_id,
                "inquiry": result["inquiry"],
                "message": result["message"],
            }
        )

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
