#!/usr/bin/env python3
"""Serve BMW Marketplace with FastAPI.

Usage:
    python3 scripts/home_page.py
Then open http://127.0.0.1:8000
"""

from __future__ import annotations

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
        create_app_session,
        create_app_user,
        create_user_listing,
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
        create_app_session,
        create_app_user,
        create_user_listing,
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


def create_app(data_dir: Path) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.on_event("startup")
    def startup() -> None:
        init_db(db_path_for(data_dir))

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
        return _html(render_settings(current_user, notice_code=notice))

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
        try:
            user = create_app_user(db_path_for(data_dir), full_name, email, password)
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
            return _html(render_settings(current_user, values, "Name, email, and current password are required."), 400)

        if not verify_password(current_password, str(current_user.get("password_hash", ""))):
            return _html(render_settings(current_user, values, "Current password is incorrect."), 400)

        if new_password or confirm_password:
            if len(new_password) < 8:
                return _html(render_settings(current_user, values, "New password must be at least 8 characters."), 400)
            if new_password != confirm_password:
                return _html(render_settings(current_user, values, "New password and confirmation must match."), 400)

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
                return _html(render_settings(current_user, values, "An account with that email already exists."), 400)
            raise

        if not updated:
            return _html(render_settings(current_user, values, "We could not save your settings."), 400)

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
