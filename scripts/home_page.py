#!/usr/bin/env python3
"""Serve a simple BMW Marketplace homepage from local seed JSON data.

Usage:
    python3 scripts/home_page.py
Then open http://127.0.0.1:8000
"""

from __future__ import annotations

from marketplace_core import (  # noqa: F401
    BASE_DIR,
    CSS_PATH,
    HTTPStatus,
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE_SECONDS,
    SEED_IMAGES_DIR_NAME,
    UPLOADS_DIR_NAME,
    BaseHTTPRequestHandler,
    BytesParser,
    default,
    Path,
    SimpleCookie,
    ThreadingHTTPServer,
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
    json,
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
    read_static_image,
    refresh_user_listing,
    update_user_listing,
)
from marketplace_render import (
    render_create_listing,
    render_edit_listing,
    render_home,
    render_listing_detail,
    render_login,
    render_register,
)


class AppHandler(BaseHTTPRequestHandler):
    data_dir = BASE_DIR.parent / "data"

    def _send_html(self, body: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_form_data(self) -> dict[str, str]:
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(content_length).decode("utf-8") if content_length else ""
        parsed = urllib.parse.parse_qs(raw, keep_blank_values=True)
        return {key: values[-1] if values else "" for key, values in parsed.items()}

    def _read_multipart_data(self) -> tuple[dict[str, str], dict[str, list[dict[str, object]]]]:
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(content_length) if content_length else b""
        content_type = self.headers.get("Content-Type", "")

        parser = BytesParser(policy=default)
        message = parser.parsebytes(
            b"Content-Type: " + content_type.encode("utf-8") + b"\r\n\r\n" + raw
        )

        values: dict[str, str] = {}
        files: dict[str, list[dict[str, object]]] = {}
        for part in message.iter_parts():
            content_disposition = part.get_content_disposition()
            if content_disposition != "form-data":
                continue
            name = part.get_param("name", header="content-disposition")
            if not name:
                continue

            filename = part.get_filename()
            body = part.get_payload(decode=True) or b""
            if filename:
                files.setdefault(name, []).append(
                    {
                        "filename": filename,
                        "content": body,
                        "content_type": part.get_content_type(),
                    }
                )
            else:
                values[name] = body.decode(part.get_content_charset() or "utf-8", errors="replace")
        return values, files

    def _redirect(self, location: str, set_cookie: str = "") -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()

    def _session_cookie(self, token: str, max_age: int = SESSION_MAX_AGE_SECONDS) -> str:
        return (
            f"{SESSION_COOKIE_NAME}={token}; Path=/; Max-Age={max_age}; HttpOnly; SameSite=Lax"
        )

    def _parse_cookies(self) -> SimpleCookie:
        raw_cookie = self.headers.get("Cookie", "")
        cookie = SimpleCookie()
        if raw_cookie:
            cookie.load(raw_cookie)
        return cookie

    def _current_user(self) -> dict[str, str] | None:
        cookie = self._parse_cookies()
        token = cookie.get(SESSION_COOKIE_NAME)
        if not token:
            return None
        user_id = get_user_id_for_session(db_path_for(self.data_dir), token.value)
        if not user_id:
            return None
        user = get_app_user_by_id(db_path_for(self.data_dir), user_id)
        return user if isinstance(user, dict) else None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        notice = query.get("notice", [""])[0]

        if parsed.path in {"/", "/index.html"}:
            filters = {
                "search": query.get("search", [""])[0],
                "chassis_code": query.get("chassis_code", [""])[0],
                "transmission_type": query.get("transmission_type", [""])[0],
                "package_name": query.get("package_name", [""])[0],
                "drive_type": query.get("drive_type", [""])[0],
                "doors": query.get("doors", [""])[0],
                "title_filter": query.get("title_filter", [""])[0],
                "sort_by": query.get("sort_by", ["newest"])[0],
            }
            self._send_html(render_home(self.data_dir, self._current_user(), filters, notice))
            return

        if parsed.path == "/create-listing":
            current_user = self._current_user()
            if not current_user:
                self._redirect("/login?next=/create-listing")
                return
            self._send_html(
                render_create_listing(
                    self.data_dir,
                    {
                        "seller_name": str(current_user.get("full_name", "")),
                        "seller_email": str(current_user.get("email", "")),
                    },
                )
            )
            return

        if parsed.path == "/vin-preview":
            vin = query.get("vin", [""])[0]
            listing = get_seed_listing_by_vin(self.data_dir, vin)
            clean_vin = sanitize_vin(vin)
            if not listing:
                self._send_json({"ok": False, "message": "No vehicle found for this VIN in the local catalog."})
                return
            self._send_json(
                {
                    "ok": True,
                    "vin": clean_vin,
                    "title": f'{listing.get("year", "")} BMW {listing.get("model", "")} {listing.get("trim", "")}'.strip(),
                    "summary": f'{listing.get("body_style", "Unknown")} | {listing.get("drive_type", "Unknown")} | Title: {listing.get("title_type", "Unknown")}',
                    "carfax_url": carfax_url_for_vin(clean_vin),
                    "nhtsa_url": nhtsa_url_for_vin(clean_vin),
                }
            )
            return

        if parsed.path == "/login":
            next_path = query.get("next", ["/"])[0]
            self._send_html(render_login({"next": next_path}))
            return

        if parsed.path == "/register":
            next_path = query.get("next", ["/"])[0]
            self._send_html(render_register({"next": next_path}))
            return

        if parsed.path == "/listing":
            listing_id = query.get("listing_id", [""])[0]
            if listing_id:
                self._send_html(render_listing_detail(self.data_dir, listing_id, self._current_user(), notice))
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Listing not found")
            return

        if parsed.path == "/edit-listing":
            current_user = self._current_user()
            if not current_user:
                self._redirect("/login?next=" + urllib.parse.quote(self.path))
                return
            listing_id = query.get("listing_id", [""])[0].strip()
            if not listing_id:
                self.send_error(HTTPStatus.BAD_REQUEST, "Missing listing_id")
                return
            listing = get_user_listing_for_owner(
                db_path_for(self.data_dir), listing_id, str(current_user.get("user_id", ""))
            )
            if not listing:
                self.send_error(HTTPStatus.NOT_FOUND, "Listing not found")
                return
            self._send_html(render_edit_listing(listing))
            return

        if parsed.path == "/styles.css":
            body = CSS_PATH.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path.startswith(f"/{UPLOADS_DIR_NAME}/"):
            file_name = parsed.path.split("/", 2)[-1]
            image = read_static_image(uploads_dir_for(self.data_dir), file_name)
            if image is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Image not found")
                return
            body, content_type = image
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path.startswith(f"/{SEED_IMAGES_DIR_NAME}/"):
            file_name = parsed.path.split("/", 2)[-1]
            image = read_static_image(seed_images_dir_for(self.data_dir), file_name)
            if image is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Image not found")
                return
            body, content_type = image
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/logout":
            token = self._parse_cookies().get(SESSION_COOKIE_NAME)
            if token:
                delete_app_session(db_path_for(self.data_dir), token.value)
            self._redirect("/", set_cookie=self._session_cookie("", max_age=0))
            return

        if parsed.path == "/refresh-listing":
            current_user = self._current_user()
            if not current_user:
                self._redirect("/login?next=/")
                return
            values = self._read_form_data()
            listing_id = values.get("listing_id", "").strip()
            if not listing_id:
                self.send_error(HTTPStatus.BAD_REQUEST, "Missing listing_id")
                return
            refresh_user_listing(db_path_for(self.data_dir), listing_id, str(current_user.get("user_id", "")))
            self._redirect("/listing?listing_id=" + urllib.parse.quote(listing_id) + "&notice=refreshed")
            return

        if parsed.path == "/listing-status":
            current_user = self._current_user()
            if not current_user:
                self._redirect("/login?next=/")
                return
            values = self._read_form_data()
            listing_id = values.get("listing_id", "").strip()
            status = values.get("status", "").strip().upper()
            if not listing_id or not status:
                self.send_error(HTTPStatus.BAD_REQUEST, "Missing listing action fields")
                return
            changed = set_user_listing_status(db_path_for(self.data_dir), listing_id, str(current_user.get("user_id", "")), status)
            notice_code = status.lower() if changed else "action_failed"
            self._redirect("/listing?listing_id=" + urllib.parse.quote(listing_id) + "&notice=" + urllib.parse.quote(notice_code))
            return

        if parsed.path == "/delete-listing":
            current_user = self._current_user()
            if not current_user:
                self._redirect("/login?next=/")
                return
            values = self._read_form_data()
            listing_id = values.get("listing_id", "").strip()
            if not listing_id:
                self.send_error(HTTPStatus.BAD_REQUEST, "Missing listing_id")
                return
            deleted = delete_user_listing(db_path_for(self.data_dir), listing_id, str(current_user.get("user_id", "")))
            self._redirect("/?notice=deleted" if deleted else "/listing?listing_id=" + urllib.parse.quote(listing_id) + "&notice=action_failed")
            return

        if parsed.path == "/edit-listing":
            current_user = self._current_user()
            if not current_user:
                self._redirect("/login?next=/")
                return

            content_type = self.headers.get("Content-Type", "")
            if content_type.startswith("multipart/form-data"):
                values, files = self._read_multipart_data()
            else:
                values = self._read_form_data()
                files = {}

            listing_id = values.get("listing_id", "").strip()
            if not listing_id:
                self.send_error(HTTPStatus.BAD_REQUEST, "Missing listing_id")
                return

            existing = get_user_listing_for_owner(db_path_for(self.data_dir), listing_id, str(current_user.get("user_id", "")))
            if not existing:
                self.send_error(HTTPStatus.NOT_FOUND, "Listing not found")
                return

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
            elif not values.get("image_url", "").strip():
                values["image_url"] = str(existing.get("image_url", ""))

            existing_gallery = [part.strip() for part in values.get("gallery_images", "").split(",") if part.strip()]
            if not existing_gallery:
                existing_gallery = [str(item).strip() for item in existing.get("gallery_images", []) if str(item).strip()]
            values["gallery_images"] = ",".join(list(dict.fromkeys(existing_gallery + uploaded_gallery)))

            required_fields = ["price", "mileage", "location"]
            missing = [field for field in required_fields if not values.get(field, "").strip()]
            if missing:
                merged = {**existing, **values}
                self._send_html(render_edit_listing(merged, "Please fill in required fields: " + ", ".join(missing)), status=HTTPStatus.BAD_REQUEST)
                return

            try:
                price = int(values.get("price", "0"))
                mileage = int(values.get("mileage", "0"))
            except ValueError:
                merged = {**existing, **values}
                self._send_html(render_edit_listing(merged, "Price and mileage must be numbers."), status=HTTPStatus.BAD_REQUEST)
                return

            if price < 1000 or mileage < 0:
                merged = {**existing, **values}
                self._send_html(render_edit_listing(merged, "Price must be at least 1000 and mileage cannot be negative."), status=HTTPStatus.BAD_REQUEST)
                return

            values["price"] = str(price)
            values["mileage"] = str(mileage)
            if not values.get("status", "").strip():
                values["status"] = str(existing.get("status", "ACTIVE"))

            updated = update_user_listing(db_path_for(self.data_dir), listing_id, str(current_user.get("user_id", "")), values)
            self._redirect(
                "/listing?listing_id=" + urllib.parse.quote(listing_id) + "&notice=saved"
                if updated
                else "/listing?listing_id=" + urllib.parse.quote(listing_id) + "&notice=action_failed"
            )
            return

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
            except Exception as exc:
                if _is_db_integrity_error(exc):
                    self._send_html(render_register(values, "An account with that email already exists."), status=HTTPStatus.BAD_REQUEST)
                    return
                raise

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

        if parsed.path == "/create-listing":
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

            values["seller_name"] = str(current_user.get("full_name", ""))
            values["seller_email"] = str(current_user.get("email", ""))

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
            if uploaded_primary:
                values["image_url"] = uploaded_primary

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

            existing_gallery = [part.strip() for part in values.get("gallery_images", "").split(",") if part.strip()]
            merged_gallery = list(dict.fromkeys(existing_gallery + uploaded_gallery))
            if values.get("image_url", "").strip() and values["image_url"] not in merged_gallery:
                merged_gallery.insert(0, values["image_url"])
            values["gallery_images"] = ",".join(merged_gallery)

            required_fields = ["selected_year", "selected_model", "selected_trim", "vin", "price", "mileage", "location"]
            missing = [field for field in required_fields if not values.get(field, "").strip()]
            if missing:
                self._send_html(render_create_listing(self.data_dir, values, "Please fill in required fields: " + ", ".join(missing)), status=HTTPStatus.BAD_REQUEST)
                return

            cleaned_vin = sanitize_vin(values.get("vin", ""))
            if not cleaned_vin:
                self._send_html(render_create_listing(self.data_dir, values, "VIN is required."), status=HTTPStatus.BAD_REQUEST)
                return
            values["vin"] = cleaned_vin

            values["year"] = values.get("selected_year", "").strip()
            values["model"] = values.get("selected_model", "").strip()
            values["trim"] = values.get("selected_trim", "").strip()

            seed_vehicle = get_seed_listing_by_vin(self.data_dir, cleaned_vin)
            if seed_vehicle:
                values["body_style"] = str(seed_vehicle.get("body_style", values.get("body_style", "Unknown")))
                values["drive_type"] = str(seed_vehicle.get("drive_type", values.get("drive_type", "Unknown")))
                values["title_type"] = str(seed_vehicle.get("title_type", values.get("title_type", "Clean")))
                if not values.get("description", "").strip():
                    values["description"] = str(seed_vehicle.get("description", ""))
                if not values.get("image_url", "").strip():
                    values["image_url"] = str(seed_vehicle.get("image_url", "")).strip()
                seed_gallery = [str(item).strip() for item in seed_vehicle.get("gallery_images", []) if str(item).strip()]
                if seed_gallery:
                    existing_gallery = [part.strip() for part in values.get("gallery_images", "").split(",") if part.strip()]
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
                self._send_html(render_create_listing(self.data_dir, values, "Price and mileage must be numbers."), status=HTTPStatus.BAD_REQUEST)
                return

            if year < 1970 or year > 2035:
                self._send_html(render_create_listing(self.data_dir, values, "Year must be between 1970 and 2035."), status=HTTPStatus.BAD_REQUEST)
                return
            if price < 1000 or mileage < 0:
                self._send_html(render_create_listing(self.data_dir, values, "Price must be at least 1000 and mileage cannot be negative."), status=HTTPStatus.BAD_REQUEST)
                return

            values["year"] = str(year)
            values["price"] = str(price)
            values["mileage"] = str(mileage)

            listing_id = create_user_listing(db_path_for(self.data_dir), values, current_user)
            target = "/listing?listing_id=" + urllib.parse.quote(listing_id) + "&notice=created"
            self._redirect(target)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

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

