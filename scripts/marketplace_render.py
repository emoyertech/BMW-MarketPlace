try:
    from .marketplace_core import *
except ImportError:
    from marketplace_core import *

def render_create_listing(data_dir: Path, values: dict[str, str] | None = None, error: str = "") -> str:
    values = values or {}
    template = FORM_TEMPLATE_PATH.read_text(encoding="utf-8")
    error_html = f'<p class="form-error">{html.escape(error)}</p>' if error else ""

    def field(name: str, default: str = "") -> str:
        return html.escape(values.get(name, default))

    seller_type = values.get("seller_type", "PRIVATE_SELLER")
    status = values.get("status", "ACTIVE")
    vin = sanitize_vin(values.get("vin", ""))
    selected_vehicle_vin = sanitize_vin(values.get("selected_vehicle_vin", ""))
    selected_seed = get_seed_listing_by_vin(data_dir, selected_vehicle_vin or vin)
    selected_year = values.get("selected_year", "")
    selected_model = values.get("selected_model", "")
    selected_trim = values.get("selected_trim", "")
    if selected_seed:
        selected_year = selected_year or str(selected_seed.get("year", ""))
        selected_model = selected_model or str(selected_seed.get("model", ""))
        selected_trim = selected_trim or str(selected_seed.get("trim", ""))

    vehicle_catalog: list[dict[str, str]] = []
    seen_vins: set[str] = set()
    for listing in load_json(data_dir / "listings.json"):
        option_vin = sanitize_vin(str(listing.get("vin", "")))
        if len(option_vin) != 17 or option_vin in seen_vins:
            continue
        seen_vins.add(option_vin)
        vehicle_catalog.append(
            {
                "vin": option_vin,
                "year": str(listing.get("year", "")),
                "model": str(listing.get("model", "")),
                "trim": str(listing.get("trim", "")),
            }
        )
    preview_listing = get_seed_listing_by_vin(data_dir, vin) if vin else None
    if preview_listing:
        preview_html = (
            '<section class="vin-preview">'
            '<h2>VIN preview</h2>'
            f'<p><strong>{html.escape(str(preview_listing.get("year", "")))} BMW {html.escape(str(preview_listing.get("model", "")))} {html.escape(str(preview_listing.get("trim", "")))}</strong></p>'
            f'<p>{html.escape(str(preview_listing.get("body_style", "")))} | {html.escape(str(preview_listing.get("drive_type", "")))} | Title: {html.escape(str(preview_listing.get("title_type", "")))}</p>'
            f'<div class="vin-preview-links">{vehicle_report_links_html(vin, compact=True)}</div>'
            "</section>"
        )
    else:
        preview_html = '<section class="vin-preview"><h2>VIN preview</h2><p>Enter a VIN to preview matched vehicle details when a local catalog match exists. Shorter international VINs can still be saved.</p><div class="vin-preview-links" id="vin-preview-links"></div></section>'

    return (
        template.replace("{{ERROR_HTML}}", error_html)
        .replace("{{SELLER_NAME}}", field("seller_name"))
        .replace("{{SELLER_EMAIL}}", field("seller_email"))
        .replace("{{VIN}}", field("vin"))
        .replace("{{SELECTED_VEHICLE_VIN}}", field("selected_vehicle_vin"))
        .replace("{{SELECTED_YEAR}}", html.escape(selected_year))
        .replace("{{SELECTED_MODEL}}", html.escape(selected_model))
        .replace("{{SELECTED_TRIM}}", html.escape(selected_trim))
        .replace("{{VEHICLE_CATALOG_JSON}}", html.escape(json.dumps(vehicle_catalog)))
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
        .replace("{{VIN_PREVIEW_HTML}}", preview_html)
    )


def render_edit_listing(listing: dict, error: str = "") -> str:
    template = EDIT_TEMPLATE_PATH.read_text(encoding="utf-8")
    error_html = f'<p class="form-error">{html.escape(error)}</p>' if error else ""

    status = str(listing.get("status", "ACTIVE")).upper()
    seller_type = str(listing.get("seller_type", "PRIVATE_SELLER")).upper()

    gallery_raw = listing.get("gallery_images", [])
    if isinstance(gallery_raw, str):
        gallery_images = [part.strip() for part in gallery_raw.split(",") if part.strip()]
    else:
        gallery_images = [str(item).strip() for item in gallery_raw if str(item).strip()]
    gallery_csv = ", ".join(gallery_images)

    return (
        template.replace("{{ERROR_HTML}}", error_html)
        .replace("{{LISTING_ID}}", html.escape(str(listing.get("listing_id", ""))))
        .replace("{{YEAR}}", html.escape(str(listing.get("year", ""))))
        .replace("{{MODEL}}", html.escape(str(listing.get("model", ""))))
        .replace("{{TRIM}}", html.escape(str(listing.get("trim", ""))))
        .replace("{{VIN}}", html.escape(str(listing.get("vin", ""))))
        .replace("{{PRICE}}", html.escape(str(listing.get("price", ""))))
        .replace("{{MILEAGE}}", html.escape(str(listing.get("mileage", ""))))
        .replace("{{LOCATION}}", html.escape(str(listing.get("location", ""))))
        .replace("{{BODY_STYLE}}", html.escape(str(listing.get("body_style", ""))))
        .replace("{{DRIVE_TYPE}}", html.escape(str(listing.get("drive_type", ""))))
        .replace("{{TITLE_TYPE}}", html.escape(str(listing.get("title_type", ""))))
        .replace("{{DESCRIPTION}}", html.escape(str(listing.get("description", ""))))
        .replace("{{GALLERY_IMAGES}}", html.escape(gallery_csv))
        .replace("{{PRIVATE_SELECTED}}", "selected" if seller_type == "PRIVATE_SELLER" else "")
        .replace("{{DEALER_SELECTED}}", "selected" if seller_type == "DEALER" else "")
        .replace("{{ACTIVE_SELECTED}}", "selected" if status == "ACTIVE" else "")
        .replace("{{PAUSED_SELECTED}}", "selected" if status == "PAUSED" else "")
        .replace("{{PENDING_SELECTED}}", "selected" if status == "PENDING" else "")
        .replace("{{SOLD_SELECTED}}", "selected" if status == "SOLD" else "")
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


def render_settings(
    current_user: dict[str, str],
    values: dict[str, str] | None = None,
    error: str = "",
    notice_code: str = "",
    dealership_html: str = "",
) -> str:
    values = values or {}
    template = SETTINGS_TEMPLATE_PATH.read_text(encoding="utf-8")
    error_html = f'<p class="form-error">{html.escape(error)}</p>' if error else ""
    notice_html_value = notice_html(notice_code)
    full_name = values.get("full_name", str(current_user.get("full_name", "")))
    email = values.get("email", str(current_user.get("email", "")))
    return (
        template.replace("{{NOTICE_HTML}}", notice_html_value)
        .replace("{{ERROR_HTML}}", error_html)
        .replace("{{FULL_NAME}}", html.escape(full_name))
        .replace("{{EMAIL}}", html.escape(email))
        .replace("{{DEALERSHIP_HTML}}", dealership_html)
    )


def render_dealership_settings(data_dir: Path, current_user: dict[str, str], values: dict[str, str] | None = None) -> str:
    values = values or {}
    db = db_path_for(data_dir)
    user_id = str(current_user.get("user_id", ""))
    active_profile = get_active_dealer_profile_for_user(db, user_id)
    application_profile = get_dealer_profile_for_owner(db, user_id)
    membership = None
    dealer_id = ""
    if active_profile:
        dealer_id = str(active_profile.get("dealer_id", ""))
        membership = get_dealer_membership_for_user(db, dealer_id, user_id)

    can_manage = bool(active_profile and user_can_manage_dealer(db, user_id, dealer_id))
    can_respond = bool(active_profile and user_can_respond_for_dealer(db, user_id, dealer_id))
    is_admin = is_site_admin(current_user)
    pending_count = len(list_pending_dealers(db)) if is_admin else 0
    members = list_dealer_members(db, dealer_id) if dealer_id and can_manage else []
    users_by_id = {str(user.get("user_id", "")): user for user in list_app_users(db)}

    def member_role_label(role: str) -> str:
        normalized = role.strip().upper()
        if normalized == "OWNER":
            return "Owner"
        if normalized == "SALES_MANAGER":
            return "Sales manager"
        if normalized == "SALESPERSON":
            return "Salesperson"
        return normalized.replace("_", " ").title() if normalized else "Member"

    def member_status_label(status: str) -> str:
        normalized = status.strip().upper()
        if normalized == "ACTIVE":
            return "Active"
        if normalized == "INVITED":
            return "Invited"
        if normalized == "SUSPENDED":
            return "Suspended"
        return normalized.replace("_", " ").title() if normalized else "Unknown"

    def option_html(value: str, label: str, selected_value: str) -> str:
        selected_attr = " selected" if value == selected_value else ""
        return f'<option value="{html.escape(value)}"{selected_attr}>{html.escape(label)}</option>'

    profile = active_profile or application_profile or {}
    profile_name = str(profile.get("display_name", "")).strip()
    legal_name = str(profile.get("legal_name", "")).strip()
    website_url = str(profile.get("website_url", "")).strip()
    license_number = str(profile.get("license_number", "")).strip()
    status = str(profile.get("status", "")).strip().upper()
    rejected_reason = str(profile.get("rejected_reason", "")).strip()

    app_display_name = values.get("display_name", profile_name or str(current_user.get("full_name", "")))
    app_legal_name = values.get("legal_name", legal_name or str(current_user.get("full_name", "")))
    app_website_url = values.get("website_url", website_url)
    app_license_number = values.get("license_number", license_number)
    member_email = values.get("member_email", "")
    member_user_id = values.get("member_user_id", "")
    member_role = values.get("member_role", "SALESPERSON").strip().upper() or "SALESPERSON"
    member_status = values.get("member_status", "ACTIVE").strip().upper() or "ACTIVE"
    application_status_text = member_status_label(status) if status else "Not submitted yet"
    current_role_text = member_role_label(str((membership or {}).get("member_role", "OWNER")))
    admin_notice_html = ""
    if is_admin:
        admin_notice_html = (
            '<p><a class="button secondary" href="/admin">Review pending dealerships</a></p>'
            f'<p class="auth-hint">Pending dealership approvals: {pending_count}</p>'
        )

    application_form_html = "".join(
        [
            '<section class="settings-section dealership-panel">',
            '<p class="eyebrow">Dealership</p>',
            '<h2>Apply to become an approved dealership</h2>',
            '<p>Approved dealerships can list inventory, manage staff, and let salespeople respond to buyer messages.</p>',
            '<form class="listing-form auth-form" method="post" action="/settings/dealership/apply">',
            f'<label>Legal name<input type="text" name="legal_name" value="{html.escape(app_legal_name)}" required /></label>',
            f'<label>Display name<input type="text" name="display_name" value="{html.escape(app_display_name)}" required /></label>',
            f'<label>Website URL<input type="url" name="website_url" value="{html.escape(app_website_url)}" /></label>',
            f'<label>License number<input type="text" name="license_number" value="{html.escape(app_license_number)}" /></label>',
            '<button class="button primary" type="submit">Submit dealership application</button>',
            '</form>',
            f'<p class="auth-hint">Your current dealership status is {html.escape(application_status_text)}.</p>',
            '</section>',
        ]
    )

    member_rows_html = '<tr><td colspan="4" class="empty-state">No staff members have been added yet.</td></tr>'
    if members:
        rows: list[str] = []
        for member in members:
            member_user = users_by_id.get(str(member.get("user_id", "")), {})
            rows.append(
                "".join(
                    [
                        "<tr>",
                        f"<td>{html.escape(str(member_user.get('full_name', 'Unknown user')))}<br />{html.escape(str(member_user.get('email', '')) or str(member.get('user_id', '')))}</td>",
                        f"<td>{html.escape(member_role_label(str(member.get('member_role', ''))))}</td>",
                        f"<td>{html.escape(member_status_label(str(member.get('member_status', ''))))}</td>",
                        f"<td>{html.escape(str(member.get('created_at', '')))}</td>",
                        "</tr>",
                    ]
                )
            )
        member_rows_html = "".join(rows)

    if active_profile:
        active_dealership_html = "".join(
            [
                '<section class="settings-section dealership-panel">',
                '<p class="eyebrow">Dealership</p>',
                f'<h2>{html.escape(profile_name or "Approved dealership")}</h2>',
                f'<p>Your dealership is approved and can manage staff. Message reply access is currently <strong>{"enabled" if can_respond else "disabled"}</strong>.</p>',
                '<ul class="detail-list">',
                f'<li><strong>Status:</strong> {html.escape(member_status_label(status) if status else "Approved")}</li>',
                f'<li><strong>Legal name:</strong> {html.escape(legal_name or "—")}</li>',
                f'<li><strong>Website:</strong> {html.escape(website_url or "—")}</li>',
                f'<li><strong>License:</strong> {html.escape(license_number or "—")}</li>',
                f'<li><strong>Your role:</strong> {html.escape(current_role_text)}</li>',
                '</ul>',
                '<p class="auth-hint">Only approved dealerships with active owner, sales manager, or salesperson memberships can respond to buyer messages.</p>',
                admin_notice_html,
                '</section>',
            ]
        )

        staff_management_html = ""
        if can_manage:
            staff_management_html = "".join(
                [
                    '<section class="settings-section dealership-panel">',
                    '<p class="eyebrow">Staff</p>',
                    '<h2>Manage dealership members</h2>',
                    '<p>Add an existing user by email or user ID, then choose their dealership role and access state.</p>',
                    '<form class="listing-form auth-form" method="post" action="/settings/dealership/members">',
                    f'<input type="hidden" name="dealer_id" value="{html.escape(dealer_id)}" />',
                    f'<label>User email<input type="email" name="member_email" value="{html.escape(member_email)}" /></label>',
                    f'<label>User ID<input type="text" name="member_user_id" value="{html.escape(member_user_id)}" /></label>',
                    '<label>Role<select name="member_role">',
                    option_html("OWNER", "Owner", member_role),
                    option_html("SALES_MANAGER", "Sales manager", member_role),
                    option_html("SALESPERSON", "Salesperson", member_role),
                    '</select></label>',
                    '<label>Status<select name="member_status">',
                    option_html("ACTIVE", "Active", member_status),
                    option_html("INVITED", "Invited", member_status),
                    option_html("SUSPENDED", "Suspended", member_status),
                    '</select></label>',
                    '<button class="button primary" type="submit">Save member</button>',
                    '</form>',
                    '<div class="dealership-members">',
                    '<h3>Current members</h3>',
                    '<table class="admin-table">',
                    '<thead><tr><th>Member</th><th>Role</th><th>Status</th><th>Joined</th></tr></thead>',
                    f'<tbody>{member_rows_html}</tbody>',
                    '</table>',
                    '</div>',
                    '</section>',
                ]
            )
        else:
            staff_management_html = "".join(
                [
                    '<section class="settings-section dealership-panel">',
                    '<p class="eyebrow">Staff</p>',
                    '<h2>Staff access</h2>',
                    '<p>Your dealership is approved, but only owners and sales managers can manage staff.</p>',
                    '<div class="dealership-members">',
                    '<h3>Current members</h3>',
                    '<table class="admin-table">',
                    '<thead><tr><th>Member</th><th>Role</th><th>Status</th><th>Joined</th></tr></thead>',
                    f'<tbody>{member_rows_html}</tbody>',
                    '</table>',
                    '</div>',
                    '</section>',
                ]
            )

        return active_dealership_html + staff_management_html

    if application_profile:
        application_block = "".join(
            [
                '<section class="settings-section dealership-panel">',
                '<p class="eyebrow">Dealership</p>',
                f'<h2>Application status: {html.escape(application_status_text)}</h2>',
                f'<p>{html.escape(rejected_reason) if rejected_reason else "Your dealership application is waiting for review by a site admin."}</p>',
                '</section>',
            ]
        )
    else:
        application_block = ""

    return application_block + application_form_html




def render_card(listing: dict, seller_name: str, card_template: str, seller: dict | None = None) -> str:
    year = html.escape(str(listing.get("year", "")))
    model = html.escape(str(listing.get("model", "")))
    trim = html.escape(str(listing.get("trim", "")))
    body_style = html.escape(str(listing.get("body_style", "")))
    drive_type = html.escape(str(listing.get("drive_type", "")))
    title_type = html.escape(str(listing.get("title_type", "")))
    image_url_value = str(listing.get("image_url", "")).strip() or IMAGE_PLACEHOLDER_URL
    image_url = html.escape(image_url_value)
    model_label = f"{year} BMW {model}".strip()
    vin = sanitize_vin(str(listing.get("vin", "")))
    reports_html = vehicle_report_links_html(vin)
    seller_badge_html = verification_badge_html(compact=True) if seller_is_verified(listing, seller) else ""
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
        .replace("{{IMAGE_FALLBACK_URL}}", IMAGE_PLACEHOLDER_URL)
        .replace("{{IMAGE_ALT}}", model_label)
        .replace("{{MODEL_LABEL}}", model_label)
        .replace("{{PRICE}}", currency(int(listing.get("price", 0))))
        .replace("{{LOCATION}}", html.escape(str(listing.get("location", ""))))
        .replace("{{MILEAGE}}", f"{int(listing.get('mileage', 0)):,}")
        .replace("{{SELLER_NAME}}", html.escape(seller_name))
        .replace("{{SELLER_BADGE_HTML}}", seller_badge_html)
        .replace("{{SELLER_TYPE}}", html.escape(role_label(str(listing.get("seller_type", "")))))
        .replace("{{STATUS}}", html.escape(str(listing.get("status", ""))))
        .replace("{{LISTING_ID}}", html.escape(str(listing.get("listing_id", ""))))
        .replace("{{VIN}}", html.escape(vin))
        .replace("{{VEHICLE_REPORTS_HTML}}", reports_html)
    )


def render_spec_item(label: str, value: str) -> str:
    return f'<div class="spec-card"><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong></div>'


def render_listing_detail(data_dir: Path, listing_id: str, current_user: dict | None = None, notice_code: str = "") -> str:
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
    vin = sanitize_vin(str(listing.get("vin", "")))
    reports_html = vehicle_report_links_html(vin)
    seller_badge_html = verification_badge_html(compact=True) if seller_is_verified(listing, seller) else ""
    inquiry_html = ""
    listing_id_value = str(listing.get("listing_id", ""))
    seller_user_id = str(listing.get("seller_user_id", ""))
    current_user_id = str(current_user.get("user_id", "")) if current_user else ""
    if not current_user:
        login_next = "/login?next=" + urllib.parse.quote("/listing?listing_id=" + listing_id_value)
        inquiry_html = (
            '<section class="inquiry-panel">'
            '<h2>Contact seller</h2>'
            '<p>Log in to send a message to the seller.</p>'
            f'<p><a class="button primary" href="{html.escape(login_next)}">Log in to contact seller</a></p>'
            '</section>'
        )
    elif current_user_id != seller_user_id:
        inquiry_html = (
            '<section class="inquiry-panel">'
            '<h2>Contact seller</h2>'
            '<form class="listing-form inquiry-form" method="post" action="/inquiries">'
            f'<input type="hidden" name="listing_id" value="{html.escape(listing_id_value)}" />'
            '<label>Your message<textarea name="body" rows="5" required>Hi, is this still available?</textarea></label>'
            '<button class="button primary" type="submit">Send inquiry</button>'
            '</form>'
            '<p class="auth-hint">The seller will see your message in their inquiry queue.</p>'
            '</section>'
        )
    owner_controls_html = ""
    if current_user and str(current_user.get("user_id", "")) == str(listing.get("seller_user_id", "")):
        notice = format_expiry_notice(listing)
        expiry_notice_html = f'<p class="listing-expiry-note">{html.escape(notice)}</p>' if notice else ""
        owner_controls_html = (
            '<section class="owner-controls">'
            "<h3>Owner actions</h3>"
            f"{expiry_notice_html}"
            '<form method="post" action="/refresh-listing">'
            f'<input type="hidden" name="listing_id" value="{html.escape(str(listing.get("listing_id", "")))}" />'
            '<button class="button primary" type="submit">Keep listing active</button>'
            "</form>"
            f'<p><a class="button secondary" href="/edit-listing?listing_id={urllib.parse.quote(str(listing.get("listing_id", "")))}">Edit listing</a></p>'
            '<form method="post" action="/listing-status">'
            f'<input type="hidden" name="listing_id" value="{html.escape(str(listing.get("listing_id", "")))}" />'
            '<input type="hidden" name="status" value="PENDING" />'
            '<button class="button secondary" type="submit">Mark pending</button>'
            '</form>'
            '<form method="post" action="/listing-status">'
            f'<input type="hidden" name="listing_id" value="{html.escape(str(listing.get("listing_id", "")))}" />'
            '<input type="hidden" name="status" value="SOLD" />'
            '<button class="button secondary" type="submit">Mark sold</button>'
            '</form>'
            '<form method="post" action="/delete-listing" onsubmit="return confirm(\'Delete this listing permanently?\');">'
            f'<input type="hidden" name="listing_id" value="{html.escape(str(listing.get("listing_id", "")))}" />'
            '<button class="button danger" type="submit">Delete listing</button>'
            '</form>'
            "</section>"
        )

    return (
        template.replace("{{PAGE_TITLE}}", html.escape(title))
        .replace("{{NOTICE_HTML}}", notice_html(notice_code))
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
        .replace("{{SELLER_BADGE_HTML}}", seller_badge_html)
        .replace("{{SELLER_EMAIL}}", html.escape(seller_email))
        .replace("{{SELLER_TYPE}}", html.escape(role_label(str(listing.get("seller_type", "")))))
        .replace("{{VIN}}", html.escape(vin or "N/A"))
        .replace("{{VEHICLE_REPORTS_HTML}}", reports_html)
        .replace("{{INQUIRY_HTML}}", inquiry_html)
        .replace("{{OWNER_CONTROLS_HTML}}", owner_controls_html)
    )


def render_dealership_directory(data_dir: Path, current_user: dict[str, str] | None = None, notice_code: str = "") -> str:
    db = db_path_for(data_dir)
    users = load_json(data_dir / "users.json")
    users_by_id = {str(user.get("user_id", "")): user for user in users}
    listings = load_all_listings(data_dir)
    dealers = [
        dealer
        for dealer in list_all_dealer_profiles(db)
        if str(dealer.get("status", "")).strip().upper() == "APPROVED"
    ]
    active_inventory_counts: dict[str, int] = {}
    for listing in listings:
        if str(listing.get("status", "")).strip().upper() != "ACTIVE":
            continue
        dealer_ref = str(listing.get("dealer_id", "")).strip()
        if not dealer_ref:
            continue
        active_inventory_counts[dealer_ref] = active_inventory_counts.get(dealer_ref, 0) + 1

    def dealership_sort_key(dealer: dict) -> tuple[int, str]:
        dealer_id = str(dealer.get("dealer_id", ""))
        name = str(dealer.get("display_name", "")).strip().lower()
        return (-active_inventory_counts.get(dealer_id, 0), name)

    card_template = CARD_TEMPLATE_PATH.read_text(encoding="utf-8")
    dealer_cards: list[str] = []
    for dealer in sorted(dealers, key=dealership_sort_key):
        dealer_id = str(dealer.get("dealer_id", ""))
        owner_user = users_by_id.get(str(dealer.get("owner_user_id", "")), {})
        display_name = str(dealer.get("display_name", "")).strip() or "Approved dealership"
        legal_name = str(dealer.get("legal_name", "")).strip()
        website_url = str(dealer.get("website_url", "")).strip()
        license_number = str(dealer.get("license_number", "")).strip()
        inventory_count = active_inventory_counts.get(dealer_id, 0)
        detail_url = "/dealerships/" + urllib.parse.quote(dealer_id)
        website_link = (
            f'<a href="{html.escape(website_url)}" target="_blank" rel="noreferrer">{html.escape(website_url)}</a>'
            if website_url
            else "—"
        )
        dealer_cards.append(
            "".join(
                [
                    '<article class="dealership-card">',
                    '<p class="eyebrow">Approved dealership</p>',
                    f'<h2>{html.escape(display_name)}</h2>',
                    f'<p class="dealership-card__legal">{html.escape(legal_name or "Legal name not listed")}</p>',
                    '<ul class="detail-list">',
                    f'<li><strong>Active inventory:</strong> {inventory_count}</li>',
                    f'<li><strong>Owner:</strong> {html.escape(str(owner_user.get("full_name", "Unknown User")))}</li>',
                    f'<li><strong>Website:</strong> {website_link}</li>',
                    f'<li><strong>License:</strong> {html.escape(license_number or "—")}</li>',
                    '</ul>',
                    f'<p><a class="button secondary" href="{html.escape(detail_url)}">View dealership</a></p>',
                    '</article>',
                ]
            )
        )

    notice_block = notice_html(notice_code)
    dealer_cards_html = (
        "".join(dealer_cards)
        if dealer_cards
        else '<p class="empty-state">No approved dealerships are available yet.</p>'
    )
    current_user_html = ""
    if current_user:
        current_user_html = (
            f'<span class="auth-welcome">Signed in as {html.escape(current_user.get("full_name", ""))}</span>'
            '<a class="button secondary auth-btn" href="/">Home</a>'
            '<a class="button secondary auth-btn" href="/settings">Settings</a>'
            '<a class="button secondary auth-btn" href="/logout">Log out</a>'
        )
    else:
        current_user_html = (
            '<a class="button secondary auth-btn" href="/">Home</a>'
            '<a class="button secondary auth-btn" href="/login?next=/dealerships">Log in</a>'
            '<a class="button secondary auth-btn" href="/register?next=/dealerships">Create account</a>'
        )

    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8" />'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />'
        '<title>Dealerships</title><link rel="stylesheet" href="/styles.css" />'
        '<style>'
        '.dealership-directory .page-hero{display:flex;flex-direction:column;gap:0.75rem;}'
        '.dealership-directory__grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem;margin-top:1.5rem;}'
        '.dealership-card{border:1px solid rgba(148,163,184,0.35);border-radius:18px;padding:1.25rem;background:#fff;box-shadow:0 1px 2px rgba(15,23,42,0.05);display:flex;flex-direction:column;gap:0.75rem;}'
        '.dealership-card h2{margin:0;font-size:1.3rem;}'
        '.dealership-card__legal{margin:0;color:#64748b;}'
        '.dealership-card .detail-list{margin:0;padding-left:1.1rem;display:grid;gap:0.4rem;}'
        '.dealership-card .detail-list li{line-height:1.4;}'
        '</style></head><body><main class="page-shell dealership-directory">'
        '<header class="page-hero">'
        '<p class="eyebrow">Dealerships</p>'
        '<h1>Browse approved dealerships</h1>'
        '<p>View every approved dealership, check their active inventory, and open a dealership profile for more information.</p>'
        f'<p>{current_user_html}</p>'
        '</header>'
        f'{notice_block}'
        f'<section class="dealership-directory__grid">{dealer_cards_html}</section>'
        '</main></body></html>'
    )


def render_dealership_detail(data_dir: Path, dealer_id: str, current_user: dict[str, str] | None = None, notice_code: str = "") -> str:
    db = db_path_for(data_dir)
    users = load_json(data_dir / "users.json")
    users_by_id = {str(user.get("user_id", "")): user for user in users}
    dealer = get_dealer_profile_by_id(db, dealer_id)
    if not dealer or str(dealer.get("status", "")).strip().upper() != "APPROVED":
        return (
            '<!doctype html><html lang="en"><head><meta charset="utf-8" />'
            '<meta name="viewport" content="width=device-width, initial-scale=1" />'
            '<title>Dealership not found</title><link rel="stylesheet" href="/styles.css" />'
            '</head><body><main class="page-shell"><p class="empty-state">Dealership not found.</p>'
            '<p><a class="button secondary" href="/dealerships">Return to dealerships</a></p></main></body></html>'
        )

    all_listings = load_all_listings(data_dir)
    active_listings = [
        listing
        for listing in all_listings
        if str(listing.get("dealer_id", "")).strip() == dealer_id and str(listing.get("status", "")).strip().upper() == "ACTIVE"
    ]
    active_listings = sorted(active_listings, key=lambda item: str(item.get("created_at", "")), reverse=True)

    owner_user = users_by_id.get(str(dealer.get("owner_user_id", "")), {})
    display_name = str(dealer.get("display_name", "")).strip() or "Approved dealership"
    legal_name = str(dealer.get("legal_name", "")).strip()
    website_url = str(dealer.get("website_url", "")).strip()
    license_number = str(dealer.get("license_number", "")).strip()
    approved_at = str(dealer.get("approved_at", "")).strip()
    approved_by_user = users_by_id.get(str(dealer.get("approved_by_admin_id", "")), {})
    website_link = (
        f'<a href="{html.escape(website_url)}" target="_blank" rel="noreferrer">{html.escape(website_url)}</a>'
        if website_url
        else "—"
    )
    card_template = CARD_TEMPLATE_PATH.read_text(encoding="utf-8")
    inventory_cards = []
    for listing in active_listings:
        seller = users_by_id.get(str(listing.get("seller_user_id", "")), {})
        seller_name = str(listing.get("seller_name", "")).strip() or display_name
        inventory_cards.append(render_card(listing, seller_name, card_template, seller))

    user_id = str(current_user.get("user_id", "")) if current_user else ""
    can_manage = bool(current_user and user_can_manage_dealer(db, user_id, dealer_id))
    can_respond = bool(current_user and user_can_respond_for_dealer(db, user_id, dealer_id))
    members = list_dealer_members(db, dealer_id) if (can_manage or (current_user and is_site_admin(current_user))) else []
    member_rows_html = '<tr><td colspan="4" class="empty-state">No staff members found.</td></tr>'
    if members:
        rows: list[str] = []
        for member in members:
            member_user = users_by_id.get(str(member.get("user_id", "")), {})
            rows.append(
                "".join(
                    [
                        "<tr>",
                        f"<td>{html.escape(str(member_user.get('full_name', 'Unknown user')))}<br />{html.escape(str(member_user.get('email', '')) or str(member.get('user_id', '')))}</td>",
                        f"<td>{html.escape(str(member.get('member_role', '')) or '—')}</td>",
                        f"<td>{html.escape(str(member.get('member_status', '')) or '—')}</td>",
                        f"<td>{html.escape(str(member.get('created_at', '')) or '—')}</td>",
                        "</tr>",
                    ]
                )
            )
        member_rows_html = "".join(rows)

    inventory_cards_html = (
        "".join(inventory_cards)
        if inventory_cards
        else '<p class="empty-state">This dealership does not have any active inventory listed yet.</p>'
    )
    notice_block = notice_html(notice_code)
    current_user_html = ""
    if current_user:
        current_user_html = (
            f'<span class="auth-welcome">Signed in as {html.escape(current_user.get("full_name", ""))}</span>'
            '<a class="button secondary auth-btn" href="/dealerships">Back to dealerships</a>'
            '<a class="button secondary auth-btn" href="/settings">Settings</a>'
            '<a class="button secondary auth-btn" href="/logout">Log out</a>'
        )
    else:
        current_user_html = (
            '<a class="button secondary auth-btn" href="/dealerships">Back to dealerships</a>'
            '<a class="button secondary auth-btn" href="/login?next=/dealerships">Log in</a>'
            '<a class="button secondary auth-btn" href="/register?next=/dealerships">Create account</a>'
        )

    info_rows = [
        f'<li><strong>Owner:</strong> {html.escape(str(owner_user.get("full_name", "Unknown User")))}</li>',
        f'<li><strong>Website:</strong> {website_link}</li>',
        f'<li><strong>License:</strong> {html.escape(license_number or "—")}</li>',
        f'<li><strong>Approved at:</strong> {html.escape(approved_at or "—")}</li>',
        f'<li><strong>Approved by:</strong> {html.escape(str(approved_by_user.get("full_name", "")) or "—")}</li>',
        f'<li><strong>Active inventory:</strong> {len(active_listings)}</li>',
        f'<li><strong>Can respond to messages:</strong> {"Yes" if can_respond else "No"}</li>',
    ]
    manage_block = ""
    if can_manage or (current_user and is_site_admin(current_user)):
        manage_block = "".join(
            [
                '<section class="admin-section">',
                '<h2>Staff</h2>',
                '<table class="admin-table">',
                '<thead><tr><th>Member</th><th>Role</th><th>Status</th><th>Joined</th></tr></thead>',
                f'<tbody>{member_rows_html}</tbody>',
                '</table>',
                '</section>',
            ]
        )

    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8" />'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />'
        f'<title>{html.escape(display_name)}</title><link rel="stylesheet" href="/styles.css" />'
        '<style>'
        '.dealership-detail .page-hero{display:flex;flex-direction:column;gap:0.75rem;}'
        '.dealership-detail__summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem;margin:1.5rem 0;}'
        '.dealership-detail__panel{border:1px solid rgba(148,163,184,0.35);border-radius:18px;padding:1.25rem;background:#fff;box-shadow:0 1px 2px rgba(15,23,42,0.05);}'
        '.dealership-detail__panel .detail-list{margin:0;padding-left:1.1rem;display:grid;gap:0.4rem;}'
        '.dealership-detail__inventory{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1rem;margin-top:1.5rem;}'
        '.dealership-detail__section{margin-top:1.75rem;}'
        '</style></head><body><main class="page-shell dealership-detail">'
        '<header class="page-hero">'
        '<p class="eyebrow">Dealership profile</p>'
        f'<h1>{html.escape(display_name)}</h1>'
        f'<p>{html.escape(legal_name or "Legal name not listed")}</p>'
        f'<p>{current_user_html}</p>'
        '</header>'
        f'{notice_block}'
        '<section class="dealership-detail__summary">'
        '<article class="dealership-detail__panel">'
        '<h2>Dealership information</h2>'
        f'<ul class="detail-list">{"".join(info_rows)}</ul>'
        '</article>'
        '<article class="dealership-detail__panel">'
        '<h2>About this dealership</h2>'
        f'<p>{html.escape(display_name)} currently has {len(active_listings)} active BMW listings available in the marketplace.</p>'
        '<p>Browse the inventory below to view vehicle details, pricing, mileage, and seller information.</p>'
        '</article>'
        '</section>'
        f'<section class="dealership-detail__section"><h2>Inventory</h2><div class="dealership-detail__inventory">{inventory_cards_html}</div></section>'
        f'{manage_block}'
        '</main></body></html>'
    )


def render_home(
    data_dir: Path,
    current_user: dict[str, str] | None = None,
    filters: dict[str, str] | None = None,
    notice_code: str = "",
) -> str:
    filters = filters or {}
    users = load_json(data_dir / "users.json")
    listings = load_all_listings(data_dir)
    inquiries = load_json(data_dir / "inquiries.json")

    users_by_id = {u["user_id"]: u for u in users}
    active = [l for l in listings if l.get("status") == "ACTIVE"]
    search = filters.get("search", "").strip()
    chassis = filters.get("chassis_code", "").strip().upper()
    transmission = filters.get("transmission_type", "").strip()
    package = filters.get("package_name", "").strip()
    drive_type = filters.get("drive_type", "").strip()
    doors = filters.get("doors", "").strip()
    title_filter = filters.get("title_filter", "").strip()
    sort_by = filters.get("sort_by", "newest").strip() or "newest"

    filtered_active: list[dict] = []
    for listing in active:
        if not listing_matches_search(listing, search):
            continue
        if chassis and extract_chassis_code(listing) != chassis:
            continue
        if transmission and extract_transmission_type(listing) != transmission:
            continue
        if package and extract_package_name(listing) != package:
            continue
        if drive_type and str(listing.get("drive_type", "")).strip() != drive_type:
            continue
        if doors and extract_doors(listing) != doors:
            continue
        if title_filter and title_bucket(listing) != title_filter:
            continue
        filtered_active.append(listing)

    if sort_by == "price_desc":
        filtered_active = sorted(filtered_active, key=lambda x: int(x.get("price", 0) or 0), reverse=True)
    elif sort_by == "price_asc":
        filtered_active = sorted(filtered_active, key=lambda x: int(x.get("price", 0) or 0))
    elif sort_by == "year_desc":
        filtered_active = sorted(filtered_active, key=lambda x: int(x.get("year", 0) or 0), reverse=True)
    elif sort_by == "year_asc":
        filtered_active = sorted(filtered_active, key=lambda x: int(x.get("year", 0) or 0))
    else:
        filtered_active = sorted(filtered_active, key=lambda x: x.get("created_at", ""), reverse=True)

    card_template = CARD_TEMPLATE_PATH.read_text(encoding="utf-8")

    dealer_listings = [listing for listing in filtered_active if listing.get("seller_type") == "DEALER"]
    private_listings = [listing for listing in filtered_active if listing.get("seller_type") == "PRIVATE_SELLER"]

    # Keep the featured strip compact, but let the inventory sections show
    # the full filtered dealer/private results.
    featured_listings = filtered_active[:4]
    dealer_showcase = dealer_listings
    private_showcase = private_listings

    cards = []
    for listing in featured_listings:
        seller = users_by_id.get(listing.get("seller_user_id", ""), {})
        seller_name = str(listing.get("seller_name", "")).strip() or seller.get("full_name", "Unknown Seller")
        cards.append(render_card(listing, seller_name, card_template, seller))

    dealer_cards = []
    for listing in dealer_showcase:
        seller = users_by_id.get(listing.get("seller_user_id", ""), {})
        seller_name = str(listing.get("seller_name", "")).strip() or seller.get("full_name", "Unknown Seller")
        dealer_cards.append(render_card(listing, seller_name, card_template, seller))

    private_cards = []
    for listing in private_showcase:
        seller = users_by_id.get(listing.get("seller_user_id", ""), {})
        seller_name = str(listing.get("seller_name", "")).strip() or seller.get("full_name", "Unknown Seller")
        private_cards.append(render_card(listing, seller_name, card_template, seller))

    cards_html = "\n".join(cards) if cards else "<p class=\"empty-state\">No active listings found. Run seed_data.py first.</p>"
    dealer_html = "\n".join(dealer_cards) if dealer_cards else "<p class=\"empty-state\">No dealer listings available yet.</p>"
    private_html = "\n".join(private_cards) if private_cards else "<p class=\"empty-state\">No private seller listings available yet.</p>"

    avg_price = 0
    if filtered_active:
        avg_price = round(sum(int(listing.get("price", 0)) for listing in filtered_active) / len(filtered_active))

    recently_active = filtered_active[0] if filtered_active else {}
    featured_image = str(recently_active.get("image_url", "")).strip() or IMAGE_PLACEHOLDER_URL
    featured_seller = users_by_id.get(recently_active.get("seller_user_id", ""), {})
    featured_seller_name = str(recently_active.get("seller_name", "")).strip() or featured_seller.get("full_name", "Unknown Seller")
    featured_seller_type = role_label(str(recently_active.get("seller_type", "")))
    featured_seller_badge_html = verification_badge_html(compact=True) if seller_is_verified(recently_active, featured_seller) else ""
    hero_title = "Marketplace-ready BMW inventory from dealers and private sellers."
    hero_subtitle = (
        "A catalog-backed homepage that mixes dealer stock and individual listings, "
        "with real image URLs, mileage, titles, and vehicle details."
    )

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    reminder_html = notice_html(notice_code)
    if current_user:
        owned_active = [
            listing
            for listing in filtered_active
            if str(listing.get("seller_user_id", "")) == str(current_user.get("user_id", ""))
        ]
        reminder_items: list[str] = []
        for listing in owned_active:
            if listing.get("reminder_24h_sent_at") or listing.get("reminder_1h_sent_at") or listing.get("reminder_5m_sent_at"):
                notice = format_expiry_notice(listing)
                if notice:
                    listing_url = "/listing?listing_id=" + urllib.parse.quote(str(listing.get("listing_id", "")))
                    reminder_items.append(
                        f'<li><a href="{listing_url}">{html.escape(str(listing.get("year", "")))} BMW {html.escape(str(listing.get("model", "")))}</a>: {html.escape(notice)}</li>'
                    )
        if reminder_items:
            reminder_panel = (
                '<section class="alert-panel">'
                '<h2>Listing expiry alerts</h2>'
                '<p>These listings are close to expiration. Open each one and refresh to keep it active.</p>'
                "<ul>"
                + "".join(reminder_items[:5])
                + "</ul>"
                "</section>"
            )
            reminder_html += reminder_panel
    if current_user:
        auth_header_html = (
            f'<span class="auth-welcome">Signed in as {html.escape(current_user.get("full_name", ""))}</span>'
            '<a class="button secondary auth-btn" href="/create-listing">Create listing</a>'
            '<a class="button secondary auth-btn" href="/settings">Settings</a>'
            '<a class="button secondary auth-btn" href="/logout">Log out</a>'
        )
    else:
        auth_header_html = (
            '<a class="button secondary auth-btn" href="/login?next=/create-listing">Log in</a>'
            '<a class="button secondary auth-btn" href="/register?next=/create-listing">Create account</a>'
        )

    chassis_options = sorted({extract_chassis_code(item) for item in active if extract_chassis_code(item)})
    transmission_options = sorted({extract_transmission_type(item) for item in active if extract_transmission_type(item) != "Unknown"})
    package_options = sorted({extract_package_name(item) for item in active if extract_package_name(item) != "None"})
    drive_options = sorted({str(item.get("drive_type", "")).strip() for item in active if str(item.get("drive_type", "")).strip()})
    door_options = sorted({extract_doors(item) for item in active if extract_doors(item) != "Unknown"}, key=lambda x: int(x))

    def options_html(options: list[str], selected: str, empty_label: str) -> str:
        html_bits = [f'<option value="">{html.escape(empty_label)}</option>']
        for value in options:
            selected_attr = " selected" if value == selected else ""
            html_bits.append(f'<option value="{html.escape(value)}"{selected_attr}>{html.escape(value)}</option>')
        return "".join(html_bits)

    sort_options = {
        "newest": "Newest",
        "price_desc": "Price high to low",
        "year_desc": "Year high to low",
        "price_asc": "Price low to high",
        "year_asc": "Year low to high",
    }
    sort_html = "".join(
        [
            f'<option value="{key}"{" selected" if sort_by == key else ""}>{label}</option>'
            for key, label in sort_options.items()
        ]
    )

    return (
        template.replace("{{ACTIVE_COUNT}}", str(len(filtered_active)))
        .replace("{{LISTINGS_COUNT}}", str(len(listings)))
        .replace("{{USERS_COUNT}}", str(len(users)))
        .replace("{{INQUIRIES_COUNT}}", str(len(inquiries)))
        .replace("{{DEALER_COUNT}}", str(len(dealer_listings)))
        .replace("{{PRIVATE_COUNT}}", str(len(private_listings)))
        .replace("{{AVG_PRICE}}", currency(avg_price))
        .replace("{{FEATURED_YEAR}}", html.escape(str(recently_active.get("year", ""))))
        .replace("{{FEATURED_MODEL}}", html.escape(str(recently_active.get("model", ""))))
        .replace("{{FEATURED_TRIM}}", html.escape(str(recently_active.get("trim", ""))))
        .replace("{{FEATURED_IMAGE}}", html.escape(featured_image))
        .replace("{{FEATURED_IMAGE_FALLBACK_URL}}", IMAGE_PLACEHOLDER_URL)
        .replace("{{FEATURED_PRICE}}", currency(int(recently_active.get("price", 0) or 0)))
        .replace("{{FEATURED_BODY_STYLE}}", html.escape(str(recently_active.get("body_style", "")) or "Unknown"))
        .replace("{{FEATURED_DRIVE_TYPE}}", html.escape(str(recently_active.get("drive_type", "")) or "Unknown"))
        .replace("{{FEATURED_LOCATION}}", html.escape(str(recently_active.get("location", ""))))
        .replace("{{FEATURED_MILEAGE}}", f"{int(recently_active.get('mileage', 0)):,}")
        .replace("{{FEATURED_SELLER_NAME}}", html.escape(str(featured_seller_name)))
        .replace("{{FEATURED_SELLER_BADGE_HTML}}", featured_seller_badge_html)
        .replace("{{FEATURED_SELLER_TYPE}}", html.escape(str(featured_seller_type)))
        .replace("{{FEATURED_STATUS}}", html.escape(str(recently_active.get("status", ""))))
        .replace("{{FEATURED_TITLE_TYPE}}", html.escape(str(recently_active.get("title_type", ""))))
        .replace("{{HERO_TITLE}}", hero_title)
        .replace("{{HERO_SUBTITLE}}", hero_subtitle)
        .replace("{{FEATURED_CARDS_HTML}}", cards_html)
        .replace("{{DEALER_CARDS_HTML}}", dealer_html)
        .replace("{{PRIVATE_CARDS_HTML}}", private_html)
        .replace("{{AUTH_HEADER_HTML}}", auth_header_html)
        .replace("{{REMINDER_PANEL_HTML}}", reminder_html)
        .replace("{{SEARCH_VALUE}}", html.escape(search))
        .replace("{{CHASSIS_OPTIONS_HTML}}", options_html(chassis_options, chassis, "All chassis codes"))
        .replace("{{TRANSMISSION_OPTIONS_HTML}}", options_html(transmission_options, transmission, "All transmissions"))
        .replace("{{PACKAGE_OPTIONS_HTML}}", options_html(package_options, package, "All packages"))
        .replace("{{DRIVE_OPTIONS_HTML}}", options_html(drive_options, drive_type, "All drive types"))
        .replace("{{DOOR_OPTIONS_HTML}}", options_html(door_options, doors, "All door counts"))
        .replace(
            "{{TITLE_OPTIONS_HTML}}",
            (
                '<option value="">All title statuses</option>'
                + f'<option value="clean"{" selected" if title_filter == "clean" else ""}>Clean</option>'
                + f'<option value="salvage_or_rebuilt"{" selected" if title_filter == "salvage_or_rebuilt" else ""}>Salvage/Rebuilt</option>'
            ),
        )
        .replace("{{SORT_OPTIONS_HTML}}", sort_html)
    )
