#!/usr/bin/env python3
"""Smoke tests for dealership authorization and approval flows.

This script avoids external test dependencies and prints a concise report that
can be redirected into `smoke tests/results.txt`.
"""

from __future__ import annotations

import os
import sys
import traceback
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import marketplace_core as mc  # noqa: E402

try:
    from scripts import home_page as hp  # noqa: E402
except Exception as exc:  # pragma: no cover - captured in smoke output
    hp = None
    HOME_PAGE_IMPORT_ERROR = exc
else:
    HOME_PAGE_IMPORT_ERROR = None


@contextmanager
def patched(module, **replacements):
    originals = {}
    for name, replacement in replacements.items():
        originals[name] = getattr(module, name)
        setattr(module, name, replacement)
    try:
        yield
    finally:
        for name, original in originals.items():
            setattr(module, name, original)


@contextmanager
def temp_env(**updates):
    sentinel = object()
    originals = {key: os.environ.get(key, sentinel) for key in updates}
    try:
        for key, value in updates.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, original in originals.items():
            if original is sentinel:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original


class FakeConn:
    def __init__(self, script):
        self.script = script
        self.row = None
        self.rows = []
        self.rowcount = 1
        self.queries: list[tuple[str, tuple | list | None]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query: str, params: tuple | list | None = None):
        normalized = " ".join(query.split())
        self.queries.append((normalized, params))
        self.row = None
        self.rows = []
        self.rowcount = 1
        self.script(self, normalized, params)
        return self

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class FakeDbConnect:
    def __init__(self, script):
        self.script = script
        self.connections: list[FakeConn] = []

    def __call__(self):
        conn = FakeConn(self.script)
        self.connections.append(conn)
        return conn


TEST_RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, fn):
    try:
        fn()
    except Exception as exc:
        TEST_RESULTS.append((name, False, f"{exc}\n{traceback.format_exc()}"))
    else:
        TEST_RESULTS.append((name, True, "ok"))


def assert_true(condition: bool, message: str = "expected condition to be true"):
    if not condition:
        raise AssertionError(message)


def assert_equal(actual, expected, message: str = ""):
    if actual != expected:
        raise AssertionError(message or f"expected {expected!r}, got {actual!r}")


def test_admin_helpers():
    with temp_env(
        BMW_MARKETPLACE_ADMIN_EMAILS="boss@example.com,  lead@example.com ",
        BMW_MARKETPLACE_DEFAULT_ADMIN_EMAIL="admin@example.com",
        BMW_MARKETPLACE_DEFAULT_ADMIN_PASSWORD="Secret123!",
        BMW_MARKETPLACE_DEFAULT_ADMIN_NAME="Platform Admin",
    ):
        assert_equal(mc.admin_email_set(), {"boss@example.com", "lead@example.com"})
        assert_true(mc.is_site_admin({"role": "SITE_ADMIN", "email": "nobody@example.com"}))
        assert_true(mc.is_site_admin({"role": "buyer", "email": "boss@example.com"}))
        assert_true(not mc.is_site_admin({"role": "BUYER", "email": "buyer@example.com"}))

        created = {}

        def fake_init_db(db_path):
            created["init_db_called"] = True

        def fake_get_user_by_email(db_path, email):
            return None

        def fake_create_user(db_path, full_name, email, password, role):
            created["args"] = (db_path, full_name, email, password, role)
            return {
                "user_id": "user-1",
                "full_name": full_name,
                "email": email,
                "password_hash": "hash",
                "role": role,
                "created_at": "2026-04-23T00:00:00+00:00",
            }

        def fake_update_role(db_path, user_id, role):
            created["update_role"] = (db_path, user_id, role)
            return True

        with patched(
            mc,
            init_db=fake_init_db,
            get_app_user_by_email=fake_get_user_by_email,
            create_app_user=fake_create_user,
            update_app_user_role=fake_update_role,
        ):
            admin = mc.ensure_default_admin(Path("data"))
            assert_equal(admin["role"], "SITE_ADMIN")
            assert_equal(created["args"][1:], ("Platform Admin", "admin@example.com", "Secret123!", "SITE_ADMIN"))

        existing = {
            "user_id": "user-2",
            "full_name": "Existing Admin",
            "email": "admin@example.com",
            "password_hash": "hash",
            "role": "BUYER",
            "created_at": "2026-04-23T00:00:00+00:00",
        }

        def fake_get_existing(db_path, email):
            return existing if email == "admin@example.com" else None

        with patched(
            mc,
            init_db=fake_init_db,
            get_app_user_by_email=fake_get_existing,
            create_app_user=fake_create_user,
            update_app_user_role=fake_update_role,
        ):
            admin = mc.ensure_default_admin(Path("data"))
            assert_equal(admin["role"], "SITE_ADMIN")
            assert_equal(created["update_role"], (Path("data"), "user-2", "SITE_ADMIN"))


def test_permission_helpers():
    owner = {"user_id": "owner-1", "email": "owner@example.com", "role": "BUYER"}
    admin = {"user_id": "admin-1", "email": "admin@example.com", "role": "SITE_ADMIN"}
    active_manager = {
        "membership_id": "mem-1",
        "dealer_id": "dealer-1",
        "user_id": "manager-1",
        "member_role": "SALES_MANAGER",
        "member_status": "ACTIVE",
        "created_by_user_id": "owner-1",
        "created_at": "2026-04-23T00:00:00+00:00",
        "updated_at": "2026-04-23T00:00:00+00:00",
    }
    active_salesperson = {
        "membership_id": "mem-2",
        "dealer_id": "dealer-1",
        "user_id": "sales-1",
        "member_role": "SALESPERSON",
        "member_status": "ACTIVE",
        "created_by_user_id": "owner-1",
        "created_at": "2026-04-23T00:00:00+00:00",
        "updated_at": "2026-04-23T00:00:00+00:00",
    }
    suspended_member = {**active_salesperson, "member_status": "SUSPENDED"}
    approved_dealer = {
        "dealer_id": "dealer-1",
        "owner_user_id": "owner-1",
        "legal_name": "BMW of Example",
        "display_name": "BMW Example",
        "website_url": "https://example.com",
        "license_number": "LIC-1",
        "status": "APPROVED",
        "rejected_reason": "",
        "approved_by_admin_id": "admin-1",
        "approved_at": "2026-04-23T00:00:00+00:00",
        "created_at": "2026-04-23T00:00:00+00:00",
        "updated_at": "2026-04-23T00:00:00+00:00",
    }
    pending_dealer = {**approved_dealer, "status": "PENDING"}

    with patched(
        mc,
        get_app_user_by_id=lambda db_path, user_id: admin if user_id == "admin-1" else owner,
        get_dealer_profile_by_id=lambda db_path, dealer_id: approved_dealer if dealer_id == "dealer-1" else None,
        get_dealer_membership_for_user=lambda db_path, dealer_id, user_id: (
            active_manager
            if user_id == "manager-1"
            else active_salesperson
            if user_id == "sales-1"
            else suspended_member
            if user_id == "sales-suspended"
            else None
        ),
        admin_email_set=lambda: set(),
    ):
        assert_true(mc.user_can_manage_dealer(Path("data"), "admin-1", "dealer-1"))
        assert_true(mc.user_can_manage_dealer(Path("data"), "owner-1", "dealer-1"))
        assert_true(mc.user_can_manage_dealer(Path("data"), "manager-1", "dealer-1"))
        assert_true(not mc.user_can_manage_dealer(Path("data"), "sales-1", "dealer-1"))
        assert_true(mc.user_can_respond_for_dealer(Path("data"), "admin-1", "dealer-1"))
        assert_true(mc.user_can_respond_for_dealer(Path("data"), "owner-1", "dealer-1"))
        assert_true(mc.user_can_respond_for_dealer(Path("data"), "manager-1", "dealer-1"))
        assert_true(mc.user_can_respond_for_dealer(Path("data"), "sales-1", "dealer-1"))
        assert_true(not mc.user_can_respond_for_dealer(Path("data"), "sales-suspended", "dealer-1"))

    with patched(
        mc,
        get_app_user_by_id=lambda db_path, user_id: owner,
        get_dealer_profile_by_id=lambda db_path, dealer_id: pending_dealer,
        get_dealer_membership_for_user=lambda db_path, dealer_id, user_id: None,
        admin_email_set=lambda: set(),
    ):
        assert_true(not mc.user_can_respond_for_dealer(Path("data"), "owner-1", "dealer-1"))


def test_dealer_database_helpers():
    dealer_row = (
        "dealer-1",
        "owner-1",
        "BMW of Example LLC",
        "BMW Example",
        "https://example.com",
        "LIC-1",
        "PENDING",
        "",
        None,
        None,
        "2026-04-23T00:00:00+00:00",
        "2026-04-23T00:00:00+00:00",
    )
    approved_row = (
        "dealer-1",
        "owner-1",
        "BMW of Example LLC",
        "BMW Example",
        "https://example.com",
        "LIC-1",
        "APPROVED",
        "",
        "admin-1",
        "2026-04-23T00:00:00+00:00",
        "2026-04-23T00:00:00+00:00",
        "2026-04-23T00:00:00+00:00",
    )
    member_row = (
        "member-1",
        "dealer-1",
        "sales-1",
        "SALESPERSON",
        "ACTIVE",
        "owner-1",
        "2026-04-23T00:00:00+00:00",
        "2026-04-23T00:00:00+00:00",
    )
    event_log: list[tuple] = []

    def script(conn: FakeConn, query: str, params):
        if "INSERT INTO dealer_profiles" in query and "RETURNING dealer_id" in query:
            conn.row = dealer_row
        elif "UPDATE dealer_profiles" in query and "SET status = 'APPROVED'" in query:
            conn.row = approved_row
        elif "UPDATE dealer_profiles" in query and "SET status = 'REJECTED'" in query:
            conn.row = (
                "dealer-1",
                "owner-1",
                "BMW of Example LLC",
                "BMW Example",
                "https://example.com",
                "LIC-1",
                "REJECTED",
                "application incomplete",
                None,
                None,
                "2026-04-23T00:00:00+00:00",
                "2026-04-23T00:00:00+00:00",
            )
        elif "UPDATE dealer_profiles" in query and "SET status = 'SUSPENDED'" in query:
            conn.row = (
                "dealer-1",
                "owner-1",
                "BMW of Example LLC",
                "BMW Example",
                "https://example.com",
                "LIC-1",
                "SUSPENDED",
                "policy issue",
                "admin-1",
                "2026-04-23T00:00:00+00:00",
                "2026-04-23T00:00:00+00:00",
                "2026-04-23T00:00:00+00:00",
            )
        elif "FROM dealer_profiles" in query and "WHERE dealer_id = ?" in query and "SELECT dealer_id, owner_user_id" in query:
            conn.row = dealer_row
        elif "FROM dealer_profiles" in query and "WHERE owner_user_id = ?" in query:
            conn.row = dealer_row
        elif "FROM dealer_profiles p" in query and "LEFT JOIN dealer_members" in query:
            conn.row = approved_row
        elif "FROM dealer_members" in query and "WHERE dealer_id = ? AND user_id = ?" in query:
            conn.row = member_row
        elif "FROM dealer_members" in query and "WHERE dealer_id = ?" in query and "ORDER BY created_at ASC" in query:
            conn.rows = [member_row]
        elif "FROM dealer_profiles" in query and "WHERE status = 'PENDING'" in query:
            conn.rows = [dealer_row]
        elif "FROM dealer_profiles" in query and "ORDER BY created_at DESC" in query:
            conn.rows = [approved_row, dealer_row]

    fake_db = FakeDbConnect(script)
    captured_events: list[tuple] = []

    def fake_init_db(db_path):
        return None

    def fake_upsert_member(*args, **kwargs):
        return {
            "membership_id": "member-1",
            "dealer_id": "dealer-1",
            "user_id": "owner-1",
            "member_role": "OWNER",
            "member_status": "ACTIVE",
            "created_by_user_id": "owner-1",
            "created_at": "2026-04-23T00:00:00+00:00",
            "updated_at": "2026-04-23T00:00:00+00:00",
        }

    def fake_record_event(*args, **kwargs):
        captured_events.append((args, kwargs))

    def fake_sync_listings(*args, **kwargs):
        return None

    def fake_get_user(db_path, user_id):
        return {"user_id": "owner-1", "email": "owner@example.com", "full_name": "Owner User", "role": "BUYER"}

    with patched(
        mc,
        init_db=fake_init_db,
        db_connect=fake_db,
        upsert_dealer_membership=fake_upsert_member,
        record_verification_event=fake_record_event,
        _sync_dealer_listings=fake_sync_listings,
        get_app_user_by_id=fake_get_user,
    ):
        created = mc.create_dealer_application(
            Path("data"),
            "owner-1",
            "BMW of Example LLC",
            "BMW Example",
            "https://example.com",
            "LIC-1",
        )
        assert_equal(created["status"], "PENDING")
        assert_equal(created["dealer_id"], "dealer-1")

        fetched = mc.get_dealer_profile_by_id(Path("data"), "dealer-1")
        assert_equal(fetched["display_name"], "BMW Example")

        owner_profile = mc.get_dealer_profile_for_owner(Path("data"), "owner-1")
        assert_equal(owner_profile["dealer_id"], "dealer-1")

        active_profile = mc.get_active_dealer_profile_for_user(Path("data"), "owner-1")
        assert_equal(active_profile["dealer_id"], "dealer-1")

        membership = mc.get_dealer_membership_for_user(Path("data"), "dealer-1", "sales-1")
        assert_equal(membership["member_role"], "SALESPERSON")

        members = mc.list_dealer_members(Path("data"), "dealer-1")
        assert_equal(len(members), 1)

        pending = mc.list_pending_dealers(Path("data"))
        assert_equal(len(pending), 1)

        all_profiles = mc.list_all_dealer_profiles(Path("data"))
        assert_equal(len(all_profiles), 2)

        approved = mc.approve_dealer_profile(Path("data"), "dealer-1", "admin-1")
        assert_equal(approved["status"], "APPROVED")

        rejected = mc.reject_dealer_profile(Path("data"), "dealer-1", "admin-1", "application incomplete")
        assert_equal(rejected["status"], "REJECTED")

        suspended = mc.suspend_dealer_profile(Path("data"), "dealer-1", "admin-1", "policy issue")
        assert_equal(suspended["status"], "SUSPENDED")

        updated_member = mc.upsert_dealer_member_record(
            Path("data"),
            "dealer-1",
            "owner-1",
            "OWNER",
            "ACTIVE",
            "admin-1",
        )
        assert_equal(updated_member["member_role"], "OWNER")
        assert_true(len(captured_events) >= 2)


def test_homepage_community_links():
    if hp is None:
        raise AssertionError(f"home_page import failed: {HOME_PAGE_IMPORT_ERROR}")

    html_output = hp.render_home(
        Path("data"),
        None,
        {
            "search": "",
            "chassis_code": "",
            "transmission_type": "",
            "package_name": "",
            "drive_type": "",
            "doors": "",
            "title_filter": "",
            "sort_by": "newest",
        },
        "",
    )
    assert_true('href="/forums"' in html_output, "homepage should link to /forums")
    assert_true('href="/parts"' in html_output, "homepage should link to /parts")
    assert_true("Open forums" in html_output, "homepage should label the forums CTA")
    assert_true("Browse parts marketplace" in html_output, "homepage should label the parts CTA")


def test_route_registration():
    if hp is None:
        raise AssertionError(f"home_page import failed: {HOME_PAGE_IMPORT_ERROR}")

    app = hp.build_app(Path("data"))
    routes = {getattr(route, "path", "") for route in app.routes}

    expected_routes = {
        "/admin",
        "/api/dealership/me",
        "/api/dealership/apply",
        "/api/dealership/members",
        "/api/dealership/inquiries",
        "/api/dealership/reply",
        "/api/admin/dealerships/pending",
        "/api/admin/dealerships/approve",
        "/api/admin/dealerships/reject",
        "/api/admin/dealerships/suspend",
        "/admin/users/role",
        "/dealerships/{dealer_id}",
        "/dealerships/{dealer_id}/inbox",
        "/dealerships/{dealer_id}/inbox/reply",
        "/dealerships/{dealer_id}/inbox/assign",
        "/forums",
        "/parts",
        "/inbox",
        "/inbox/reply",
        "/logout",
    }
    missing = sorted(expected_routes - routes)
    assert_true(not missing, f"missing routes: {missing}")


def main() -> int:
    record("admin helpers", test_admin_helpers)
    record("permission helpers", test_permission_helpers)
    record("dealer database helpers", test_dealer_database_helpers)
    record("route registration", test_route_registration)

    passed = sum(1 for _, ok, _ in TEST_RESULTS if ok)
    failed = len(TEST_RESULTS) - passed

    print("Smoke test report")
    print("=================")
    for name, ok, message in TEST_RESULTS:
        status = "PASS" if ok else "FAIL"
        print(f"{status}: {name}")
        if not ok:
            print(message.rstrip())
            print("-" * 80)
    print(f"Summary: {passed} passed, {failed} failed")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
