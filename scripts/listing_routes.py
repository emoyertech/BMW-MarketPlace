from __future__ import annotations

import urllib.parse
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

try:
    from .marketplace_core import (
        carfax_url_for_vin,
        create_listing_inquiry,
        create_user_listing,
        db_path_for,
        delete_user_listing,
        get_seed_listing_by_vin,
        get_user_listing_for_owner,
        nhtsa_url_for_vin,
        refresh_user_listing,
        sanitize_vin,
        save_uploaded_image,
        set_user_listing_status,
        update_user_listing,
    )
    from .marketplace_render import render_create_listing, render_edit_listing, render_listing_detail
    from .web_helpers import _current_user, _html, _redirect, _request_values_and_files
except ImportError:
    from marketplace_core import (
        carfax_url_for_vin,
        create_listing_inquiry,
        create_user_listing,
        db_path_for,
        delete_user_listing,
        get_seed_listing_by_vin,
        get_user_listing_for_owner,
        nhtsa_url_for_vin,
        refresh_user_listing,
        sanitize_vin,
        save_uploaded_image,
        set_user_listing_status,
        update_user_listing,
    )
    from marketplace_render import render_create_listing, render_edit_listing, render_listing_detail
    from web_helpers import _current_user, _html, _redirect, _request_values_and_files


def register_listing_routes(app: FastAPI, data_dir: Path) -> None:
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
        except ValueError:
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
