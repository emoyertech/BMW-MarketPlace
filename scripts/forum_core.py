from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def forum_data_paths(data_dir: Path) -> dict[str, Path]:
    return {
        "categories": data_dir / "forum_categories.json",
        "threads": data_dir / "forum_threads.json",
        "replies": data_dir / "forum_replies.json",
        "reports": data_dir / "forum_reports.json",
    }


def write_json(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_json_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _next_numeric_id(prefix: str, existing_ids: list[str]) -> str:
    max_number = 0
    prefix_with_dash = f"{prefix}-"
    for value in existing_ids:
        if not isinstance(value, str):
            continue
        if not value.startswith(prefix_with_dash):
            continue
        suffix = value[len(prefix_with_dash) :]
        if suffix.isdigit():
            max_number = max(max_number, int(suffix))
    return f"{prefix}-{max_number + 1}"


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _current_user_id(current_user: dict[str, str]) -> str:
    for key in ("user_id", "id", "username", "email"):
        value = _normalize_text(current_user.get(key))
        if value:
            return value
    return "unknown-user"


def _current_user_name(current_user: dict[str, str]) -> str:
    for key in ("name", "full_name", "display_name", "username"):
        value = _normalize_text(current_user.get(key))
        if value:
            return value
    first_name = _normalize_text(current_user.get("first_name"))
    last_name = _normalize_text(current_user.get("last_name"))
    combined = " ".join(part for part in (first_name, last_name) if part)
    if combined:
        return combined
    return "Forum Member"


def _current_user_role(current_user: dict[str, str]) -> str:
    for key in ("role", "role_label", "account_type", "member_type"):
        value = _normalize_text(current_user.get(key))
        if value:
            return value
    return "member"


def _parse_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        tags = [str(item).strip() for item in value]
    else:
        tags = [part.strip() for part in str(value).split(",")]
    return [tag for tag in tags if tag]


def _category_id_from_slug(categories: list[dict], slug: str) -> str | None:
    slug = slug.strip()
    for category in categories:
        if category.get("slug") == slug:
            category_id = category.get("category_id")
            if isinstance(category_id, str) and category_id:
                return category_id
    return None


def _category_by_id(categories: list[dict], category_id: str) -> dict | None:
    for category in categories:
        if category.get("category_id") == category_id:
            return category
    return None


def _timestamp_score(value: Any) -> float:
    if not isinstance(value, str) or not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def load_forum_categories(data_dir: Path) -> list[dict]:
    return _load_json_rows(forum_data_paths(data_dir)["categories"])


def load_forum_threads(data_dir: Path) -> list[dict]:
    return _load_json_rows(forum_data_paths(data_dir)["threads"])


def load_forum_replies(data_dir: Path) -> list[dict]:
    return _load_json_rows(forum_data_paths(data_dir)["replies"])


def load_forum_reports(data_dir: Path) -> list[dict]:
    return _load_json_rows(forum_data_paths(data_dir)["reports"])


def list_forum_reports(
    data_dir: Path,
    status: str | None = None,
    target_type: str | None = None,
) -> list[dict]:
    reports = load_forum_reports(data_dir)
    if status:
        normalized_status = status.strip().upper()
        reports = [report for report in reports if str(report.get("status", "")).strip().upper() == normalized_status]
    if target_type:
        normalized_target_type = target_type.strip().lower()
        reports = [report for report in reports if str(report.get("target_type", "")).strip().lower() == normalized_target_type]
    return sorted(
        reports,
        key=lambda item: (
            -_timestamp_score(item.get("created_at")),
            str(item.get("report_id", "")).lower(),
        ),
    )


def get_forum_report(data_dir: Path, report_id: str) -> dict | None:
    for report in load_forum_reports(data_dir):
        if report.get("report_id") == report_id:
            return report
    return None


def list_forum_categories(data_dir: Path) -> list[dict]:
    categories = load_forum_categories(data_dir)
    return sorted(
        categories,
        key=lambda item: (
            _safe_int(item.get("sort_order", 0)),
            str(item.get("name", "")).lower(),
        ),
    )


def list_forum_threads(data_dir: Path, category_slug: str | None = None) -> list[dict]:
    threads = load_forum_threads(data_dir)
    if category_slug:
        categories = load_forum_categories(data_dir)
        category_id = _category_id_from_slug(categories, category_slug)
        if not category_id:
            return []
        threads = [thread for thread in threads if thread.get("category_id") == category_id]

    return sorted(
        threads,
        key=lambda item: (
            0 if item.get("pinned") else 1,
            -_timestamp_score(item.get("updated_at")),
            -_timestamp_score(item.get("created_at")),
            str(item.get("title", "")).lower(),
        ),
    )


def get_forum_thread(data_dir: Path, thread_id: str) -> dict | None:
    for thread in load_forum_threads(data_dir):
        if thread.get("thread_id") == thread_id:
            return thread
    return None


def get_forum_reply(data_dir: Path, reply_id: str) -> dict | None:
    for reply in load_forum_replies(data_dir):
        if reply.get("reply_id") == reply_id:
            return reply
    return None


def list_forum_replies(data_dir: Path, thread_id: str) -> list[dict]:
    replies = [reply for reply in load_forum_replies(data_dir) if reply.get("thread_id") == thread_id]
    return sorted(
        replies,
        key=lambda item: (
            _timestamp_score(item.get("created_at")),
            str(item.get("reply_id", "")).lower(),
        ),
    )


def create_forum_thread(data_dir: Path, values: dict[str, str], current_user: dict[str, str]) -> dict:
    categories = load_forum_categories(data_dir)
    threads = load_forum_threads(data_dir)

    category_id = _normalize_text(values.get("category_id"))
    if not category_id:
        category_slug = _normalize_text(values.get("category_slug"))
        if category_slug:
            category_id = _category_id_from_slug(categories, category_slug) or ""

    category = _category_by_id(categories, category_id) if category_id else None
    if not category:
        raise ValueError("Forum category not found")

    title = _normalize_text(values.get("title"))
    body = _normalize_text(values.get("body"))
    if not title:
        raise ValueError("Thread title is required")
    if not body:
        raise ValueError("Thread body is required")

    excerpt = _normalize_text(values.get("excerpt"))
    if not excerpt:
        excerpt = body[:180]
        if len(body) > 180:
            excerpt = excerpt.rstrip() + "..."

    tags = _parse_tags(values.get("tags"))

    now = _now_iso()
    thread = {
        "thread_id": _next_numeric_id("thread", [str(item.get("thread_id", "")) for item in threads]),
        "category_id": category_id,
        "title": title,
        "excerpt": excerpt,
        "body": body,
        "author_user_id": _current_user_id(current_user),
        "author_name": _current_user_name(current_user),
        "author_role": _current_user_role(current_user),
        "tags": tags,
        "created_at": now,
        "updated_at": now,
        "reply_count": 0,
        "view_count": 0,
        "pinned": False,
        "locked": False,
    }

    threads.append(thread)
    write_json(forum_data_paths(data_dir)["threads"], threads)
    return thread


def add_forum_reply(data_dir: Path, thread_id: str, values: dict[str, str], current_user: dict[str, str]) -> dict:
    threads = load_forum_threads(data_dir)
    replies = load_forum_replies(data_dir)

    thread = None
    for candidate in threads:
        if candidate.get("thread_id") == thread_id:
            thread = candidate
            break
    if thread is None:
        raise ValueError("Forum thread not found")
    if thread.get("locked"):
        raise ValueError("Forum thread is locked")

    body = _normalize_text(values.get("body"))
    if not body:
        raise ValueError("Reply body is required")

    now = _now_iso()
    reply = {
        "reply_id": _next_numeric_id("reply", [str(item.get("reply_id", "")) for item in replies]),
        "thread_id": thread_id,
        "author_user_id": _current_user_id(current_user),
        "author_name": _current_user_name(current_user),
        "author_role": _current_user_role(current_user),
        "body": body,
        "created_at": now,
    }

    replies.append(reply)
    thread["reply_count"] = _safe_int(thread.get("reply_count", 0)) + 1
    thread["updated_at"] = now

    write_json(forum_data_paths(data_dir)["replies"], replies)
    write_json(forum_data_paths(data_dir)["threads"], threads)
    return reply


def increment_forum_thread_view_count(data_dir: Path, thread_id: str) -> bool:
    threads = load_forum_threads(data_dir)
    updated = False
    for thread in threads:
        if thread.get("thread_id") == thread_id:
            thread["view_count"] = _safe_int(thread.get("view_count", 0)) + 1
            updated = True
            break
    if updated:
        write_json(forum_data_paths(data_dir)["threads"], threads)
    return updated


def set_forum_thread_locked(data_dir: Path, thread_id: str, locked: bool) -> bool:
    threads = load_forum_threads(data_dir)
    updated = False
    for thread in threads:
        if thread.get("thread_id") == thread_id:
            thread["locked"] = bool(locked)
            thread["updated_at"] = _now_iso()
            updated = True
            break
    if updated:
        write_json(forum_data_paths(data_dir)["threads"], threads)
    return updated


def create_forum_report(
    data_dir: Path,
    target_type: str,
    target_id: str,
    thread_id: str,
    values: dict[str, str],
    current_user: dict[str, str],
) -> dict:
    target_type = _normalize_text(target_type).lower()
    if target_type not in {"thread", "reply"}:
        raise ValueError("Unsupported report target")
    target_id = _normalize_text(target_id)
    thread_id = _normalize_text(thread_id)
    if not target_id or not thread_id:
        raise ValueError("Report target is required")

    reason = _normalize_text(values.get("reason"))
    details = _normalize_text(values.get("details"))
    if not reason:
        raise ValueError("Report reason is required")

    reports = load_forum_reports(data_dir)
    now = _now_iso()
    report = {
        "report_id": _next_numeric_id("report", [str(item.get("report_id", "")) for item in reports]),
        "target_type": target_type,
        "target_id": target_id,
        "thread_id": thread_id,
        "reporter_user_id": _current_user_id(current_user),
        "reporter_name": _current_user_name(current_user),
        "reporter_role": _current_user_role(current_user),
        "reason": reason,
        "details": details,
        "status": "OPEN",
        "created_at": now,
        "reviewed_at": "",
        "reviewed_by_user_id": "",
        "reviewed_by_name": "",
        "action_taken": "",
    }
    reports.append(report)
    write_json(forum_data_paths(data_dir)["reports"], reports)
    return report


def resolve_forum_report(
    data_dir: Path,
    report_id: str,
    current_user: dict[str, str],
    status: str = "RESOLVED",
    action_taken: str = "",
) -> dict:
    reports = load_forum_reports(data_dir)
    updated_report = None
    now = _now_iso()
    normalized_status = _normalize_text(status).upper() or "RESOLVED"
    for report in reports:
        if report.get("report_id") != report_id:
            continue
        report["status"] = normalized_status
        report["reviewed_at"] = now
        report["reviewed_by_user_id"] = _current_user_id(current_user)
        report["reviewed_by_name"] = _current_user_name(current_user)
        report["action_taken"] = _normalize_text(action_taken) or normalized_status.title()
        updated_report = report
        break
    if updated_report is None:
        raise ValueError("Forum report not found")
    write_json(forum_data_paths(data_dir)["reports"], reports)
    return updated_report
