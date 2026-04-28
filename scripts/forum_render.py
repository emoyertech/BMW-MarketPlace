from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote


def _forum_helpers():
    try:
        from .forum_core import get_forum_reply, get_forum_thread, list_forum_categories, list_forum_reports, list_forum_replies, list_forum_threads
    except ImportError:
        from forum_core import get_forum_reply, get_forum_thread, list_forum_categories, list_forum_reports, list_forum_replies, list_forum_threads

    return get_forum_thread, list_forum_categories, list_forum_replies, list_forum_threads


def _t(value: Any) -> str:
    return escape("" if value is None else str(value), quote=True)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _value(values: dict[str, str] | None, key: str, default: str = "") -> str:
    if not values:
        return default
    return values.get(key, default) or default


def _current_name(current_user: dict[str, str] | None) -> str:
    if not current_user:
        return "Guest"
    for key in ("display_name", "full_name", "name", "username"):
        value = current_user.get(key)
        if value:
            return str(value)
    return "Guest"


def _current_role(current_user: dict[str, str] | None) -> str:
    if not current_user:
        return "Guest"
    for key in ("role", "account_type", "title"):
        value = current_user.get(key)
        if value:
            return str(value)
    return "Member"


def _sorted_categories(categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        categories,
        key=lambda row: (
            _as_int(row.get("sort_order")),
            str(row.get("name", "")).lower(),
            str(row.get("slug", "")),
        ),
    )


def _sorted_threads(threads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = list(threads)
    rows = sorted(rows, key=lambda row: str(row.get("thread_id", "")))
    rows = sorted(rows, key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""), reverse=True)
    rows = sorted(rows, key=lambda row: not _as_bool(row.get("pinned")))
    return rows


def _sorted_replies(replies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = list(replies)
    rows = sorted(rows, key=lambda row: str(row.get("reply_id", "")))
    return sorted(rows, key=lambda row: str(row.get("created_at", "")))


def _notice_html(notice_code: str) -> str:
    if not notice_code:
        return ""
    notices = {
        "created": ("success", "Your discussion was posted successfully."),
        "thread_created": ("success", "Your discussion was posted successfully."),
        "reply_added": ("success", "Your reply was added."),
        "report_created": ("success", "Your report was submitted for review."),
        "report_resolved": ("success", "The report was resolved."),
        "report_dismissed": ("success", "The report was dismissed."),
        "updated": ("success", "Your forum post was updated."),
        "locked": ("warning", "This discussion is locked. Replies are not available."),
        "missing": ("error", "That forum item could not be found."),
        "missing_category": ("error", "That category could not be found."),
        "missing_thread": ("error", "That thread could not be found."),
        "missing_report": ("error", "That report could not be found."),
        "forbidden": ("error", "You are not allowed to perform that action."),
    }
    kind, message = notices.get(
        notice_code,
        ("success", notice_code.replace("_", " ").strip().capitalize() or "Update saved."),
    )
    return (
        f'<section class="forum-notice forum-notice--{_t(kind)}" aria-live="polite">'
        f'<p class="forum-notice__body">{_t(message)}</p>'
        "</section>"
    )


def _error_html(error: str) -> str:
    if not error:
        return ""
    return (
        '<section class="forum-notice forum-notice--error" role="alert">'
        f'<p class="forum-notice__body">{_t(error)}</p>'
        "</section>"
    )


def _category_nav(categories: list[dict[str, Any]], active_slug: str = "") -> str:
    if not categories:
        return '<div class="forum-empty">No forum categories have been published yet.</div>'

    items = [
        (
            '<a class="forum-category-nav__item '
            f'{"forum-category-nav__item--active" if not active_slug else ""}" href="/forums">'
            "<span>"
            '<span class="forum-category-nav__name">All discussions</span>'
            '<span class="forum-category-nav__description">Browse every discussion in the forum.</span>'
            "</span>"
            "</a>"
        )
    ]
    for category in _sorted_categories(categories):
        slug = str(category.get("slug", ""))
        active = "forum-category-nav__item--active" if slug == active_slug else ""
        items.append(
            (
                f'<a class="forum-category-nav__item {active}" href="/forums/categories/{_t(slug)}">'
                "<span>"
                f'<span class="forum-category-nav__name">{_t(category.get("name", slug))}</span>'
                f'<span class="forum-category-nav__description">{_t(category.get("description", ""))}</span>'
                "</span>"
                "</a>"
            )
        )
    return '<nav class="forum-category-nav" aria-label="Forum categories">' + "".join(items) + "</nav>"


def _thread_badges(thread: dict[str, Any]) -> str:
    badges: list[str] = []
    if _as_bool(thread.get("pinned")):
        badges.append('<span class="forum-badge">Pinned</span>')
    if _as_bool(thread.get("locked")):
        badges.append('<span class="forum-badge forum-badge--warning">Locked</span>')
    reply_count = _as_int(thread.get("reply_count"))
    view_count = _as_int(thread.get("view_count"))
    badges.append(f'<span class="forum-badge forum-badge--muted">{reply_count} repl{"y" if reply_count == 1 else "ies"}</span>')
    badges.append(f'<span class="forum-badge forum-badge--muted">{view_count} view{"s" if view_count != 1 else ""}</span>')
    return "".join(badges)


def _thread_card(thread: dict[str, Any], category_name: str = "", category_slug: str = "") -> str:
    thread_id = str(thread.get("thread_id", ""))
    tags = [str(tag).strip() for tag in thread.get("tags", []) if str(tag).strip()]
    tag_html = _tag_badges(tags, category_slug)
    category_html = f'<span class="forum-badge">{_t(category_name)}</span>' if category_name else ""
    excerpt = str(thread.get("excerpt", "")).strip() or str(thread.get("body", "")).strip()[:180]
    return (
        '<article class="forum-thread-card">'
        f'<h2 class="forum-thread-card__title"><a href="/forums/threads/{_t(thread_id)}">{_t(thread.get("title", "Untitled discussion"))}</a></h2>'
        '<div class="forum-thread-card__meta">'
        f'<span>By {_t(thread.get("author_name", "Unknown"))} · {_t(thread.get("author_role", "Member"))}</span>'
        f'<span>Updated {_t(thread.get("updated_at", thread.get("created_at", "")))}</span>'
        f"{category_html}"
        f"{_thread_badges(thread)}"
        "</div>"
        f'<p class="forum-thread-card__excerpt">{_t(excerpt)}</p>'
        f'<div class="forum-thread-card__meta" aria-label="Thread tags">{tag_html}</div>'
        "</article>"
    )


def _reply_card(reply: dict[str, Any]) -> str:
    return (
        '<article class="forum-reply">'
        '<div class="forum-reply__meta">'
        f'<span>{_t(reply.get("author_name", "Unknown"))}</span>'
        f'<span>{_t(reply.get("author_role", "Member"))}</span>'
        f'<span>{_t(reply.get("created_at", ""))}</span>'
        "</div>"
        f'<div class="forum-reply__body">{_t(reply.get("body", ""))}</div>'
        "</article>"
    )


def _reply_card_with_report(reply: dict[str, Any], thread_id: str) -> str:
    reply_id = str(reply.get("reply_id", ""))
    return (
        _reply_card(reply)
        + '<div class="forum-form__actions" style="margin-top: 0.75rem;">'
        + _report_form(
            "reply",
            reply_id,
            thread_id,
            button_label="Report reply",
            details_label="Additional context for this reply",
        )
        + "</div>"
    )


def _thread_search_blob(thread: dict[str, Any], category_name: str = "") -> str:
    tags = " ".join(str(tag).strip() for tag in thread.get("tags", []) if str(tag).strip())
    return " ".join(
        [
            str(thread.get("title", "")),
            str(thread.get("excerpt", "")),
            str(thread.get("body", "")),
            str(thread.get("author_name", "")),
            str(thread.get("author_role", "")),
            str(thread.get("created_at", "")),
            str(thread.get("updated_at", "")),
            category_name,
            tags,
        ]
    ).lower()


def _thread_matches_filters(thread: dict[str, Any], category_name: str, filters: dict[str, str] | None = None) -> bool:
    filters = filters or {}
    search = str(filters.get("search", "")).strip().lower()
    tag = str(filters.get("tag", "")).strip().lower()
    sort_by = str(filters.get("sort_by", "")).strip().lower()
    if search and search not in _thread_search_blob(thread, category_name):
        return False
    if tag:
        thread_tags = {str(item).strip().lower() for item in thread.get("tags", []) if str(item).strip()}
        if tag not in thread_tags:
            return False
    if sort_by and sort_by not in {"newest", "active", "replies", "views"}:
        return False
    return True


def _normalized_filters(filters: dict[str, str] | None = None) -> dict[str, str]:
    filters = filters or {}
    sort_by = str(filters.get("sort_by", "active")).strip().lower() or "active"
    if sort_by not in {"newest", "active", "replies", "views"}:
        sort_by = "active"
    return {
        "search": str(filters.get("search", "")).strip(),
        "tag": str(filters.get("tag", "")).strip(),
        "sort_by": sort_by,
    }


def _sorted_threads_for_filters(threads: list[dict[str, Any]], filters: dict[str, str] | None = None) -> list[dict[str, Any]]:
    rows = list(threads)
    sort_by = _normalized_filters(filters).get("sort_by", "active")
    rows = sorted(rows, key=lambda row: str(row.get("thread_id", "")))
    if sort_by == "newest":
        rows = sorted(rows, key=lambda row: str(row.get("created_at") or ""), reverse=True)
    elif sort_by == "replies":
        rows = sorted(rows, key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""), reverse=True)
        rows = sorted(rows, key=lambda row: _as_int(row.get("reply_count")), reverse=True)
    elif sort_by == "views":
        rows = sorted(rows, key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""), reverse=True)
        rows = sorted(rows, key=lambda row: _as_int(row.get("view_count")), reverse=True)
    else:
        rows = sorted(rows, key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""), reverse=True)
    return sorted(rows, key=lambda row: not _as_bool(row.get("pinned")))


def _available_tags(threads: list[dict[str, Any]]) -> list[str]:
    values: dict[str, str] = {}
    for thread in threads:
        for raw_tag in thread.get("tags", []):
            tag = str(raw_tag).strip()
            if not tag:
                continue
            values.setdefault(tag.lower(), tag)
    return sorted(values.values(), key=lambda value: value.lower())


def _tag_badges(tags: list[str], category_slug: str = "") -> str:
    if not tags:
        return ""
    base_path = f"/forums/categories/{quote(category_slug)}" if category_slug else "/forums"
    return "".join(
        f'<a class="forum-badge forum-badge--muted" href="{base_path}?tag={quote(tag)}">{_t(tag)}</a>'
        for tag in tags
    )


def _filter_form(action: str, filters: dict[str, str] | None, available_tags: list[str]) -> str:
    normalized = _normalized_filters(filters)
    search = normalized.get("search", "")
    selected_tag = normalized.get("tag", "").lower()
    sort_by = normalized.get("sort_by", "active")

    tag_options = ['<option value="">All tags</option>']
    for tag in available_tags:
        selected = " selected" if tag.lower() == selected_tag else ""
        tag_options.append(f'<option value="{_t(tag)}"{selected}>{_t(tag)}</option>')

    sort_options: list[str] = []
    for value, label in (
        ("active", "Most active"),
        ("newest", "Newest"),
        ("replies", "Most replies"),
        ("views", "Most views"),
    ):
        selected = " selected" if value == sort_by else ""
        sort_options.append(f'<option value="{value}"{selected}>{_t(label)}</option>')

    active_filters: list[str] = []
    if search:
        active_filters.append(f'Search “{_t(search)}”')
    if normalized.get("tag"):
        active_filters.append(f'Tag “{_t(normalized.get("tag", ""))}”')
    helper_html = ""
    if active_filters:
        helper_html = '<p class="forum-form__help">Active filters: ' + " · ".join(active_filters) + "</p>"

    return (
        '<section class="forum-reply-form">'
        '<h2>Find discussions</h2>'
        '<form class="forum-form" method="get" action="'
        + _t(action)
        + '">'
        '<div class="forum-form__row">'
        '<label class="forum-form__label" for="forum-search">Search</label>'
        f'<input class="forum-form__input" id="forum-search" name="search" type="search" value="{_t(search)}" placeholder="Search titles, tags, authors, and content">'
        '</div>'
        '<div class="forum-form__row">'
        '<label class="forum-form__label" for="forum-tag">Tag</label>'
        f'<select class="forum-form__select" id="forum-tag" name="tag">{"".join(tag_options)}</select>'
        '</div>'
        '<div class="forum-form__row">'
        '<label class="forum-form__label" for="forum-sort">Sort by</label>'
        f'<select class="forum-form__select" id="forum-sort" name="sort_by">{"".join(sort_options)}</select>'
        '</div>'
        '<div class="forum-form__actions">'
        '<button class="forum-button forum-button--primary" type="submit">Apply filters</button>'
        f'<a class="forum-button" href="{_t(action)}">Reset</a>'
        '</div>'
        f"{helper_html}"
        '</form>'
        '</section>'
    )


def _report_form(target_type: str, target_id: str, thread_id: str, button_label: str = "Report", details_label: str = "Why are you reporting this?") -> str:
    return (
        '<form class="forum-report-form" method="post" action="/forums/reports">'
        f'<input type="hidden" name="target_type" value="{_t(target_type)}" />'
        f'<input type="hidden" name="target_id" value="{_t(target_id)}" />'
        f'<input type="hidden" name="thread_id" value="{_t(thread_id)}" />'
        '<div class="forum-form__row">'
        f'<label class="forum-form__label" for="{_t(target_type)}-{_t(target_id)}-reason">Reason</label>'
        f'<select class="forum-form__select" id="{_t(target_type)}-{_t(target_id)}-reason" name="reason" required>'
        '<option value="">Choose a reason</option>'
        '<option value="spam">Spam</option>'
        '<option value="harassment">Harassment</option>'
        '<option value="hate_speech">Hate speech</option>'
        '<option value="inappropriate">Inappropriate content</option>'
        '<option value="other">Other</option>'
        '</select>'
        '</div>'
        '<div class="forum-form__row">'
        f'<label class="forum-form__label" for="{_t(target_type)}-{_t(target_id)}-details">{_t(details_label)}</label>'
        f'<textarea class="forum-form__textarea" id="{_t(target_type)}-{_t(target_id)}-details" name="details" rows="3" placeholder="Add any context or links you want the moderators to see."></textarea>'
        '</div>'
        '<div class="forum-form__actions">'
        f'<button class="forum-button" type="submit">{_t(button_label)}</button>'
        '</div>'
        '</form>'
    )


def _report_badge(target_type: str, status: str) -> str:
    status = status.strip().upper()
    classes = "forum-badge forum-badge--danger" if status == "OPEN" else "forum-badge forum-badge--warning"
    return f'<span class="{classes}">{_t(target_type.title())} report · {_t(status.title())}</span>'


def _report_reason_label(reason: str) -> str:
    normalized = reason.strip().lower()
    mapping = {
        "spam": "Spam",
        "harassment": "Harassment",
        "hate_speech": "Hate speech",
        "inappropriate": "Inappropriate content",
        "other": "Other",
    }
    return mapping.get(normalized, reason.replace("_", " ").title() or "Other")


def _styles() -> str:
    return """
    <style>
      :root {
        color-scheme: light;
        --forum-bg: #f5f7fb;
        --forum-surface: #ffffff;
        --forum-surface-alt: #f8fafc;
        --forum-border: #d8e0ea;
        --forum-text: #1f2937;
        --forum-muted: #64748b;
        --forum-accent: #0b57d0;
        --forum-accent-soft: #e8f0fe;
        --forum-danger: #b42318;
        --forum-warning: #9a3412;
        --forum-shadow: 0 8px 28px rgba(15, 23, 42, 0.08);
      }

      * {
        box-sizing: border-box;
      }

      body {
        margin: 0;
        font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background: var(--forum-bg);
        color: var(--forum-text);
        line-height: 1.5;
      }

      a {
        color: var(--forum-accent);
        text-decoration: none;
      }

      a:hover {
        text-decoration: underline;
      }

      .forum-shell {
        max-width: 1200px;
        margin: 0 auto;
        padding: 24px 20px 48px;
      }

      .forum-shell__header {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 20px;
      }

      .forum-shell__eyebrow {
        margin: 0 0 6px;
        color: var(--forum-muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-size: 0.78rem;
        font-weight: 700;
      }

      .forum-shell__title {
        margin: 0;
        font-size: clamp(1.8rem, 3vw, 2.6rem);
        line-height: 1.1;
      }

      .forum-shell__summary {
        margin: 8px 0 0;
        color: var(--forum-muted);
        max-width: 68ch;
      }

      .forum-shell__actions {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }

      .forum-button {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 0.4rem;
        border: 1px solid var(--forum-border);
        border-radius: 999px;
        padding: 0.7rem 1rem;
        background: var(--forum-surface);
        color: var(--forum-text);
        font-weight: 600;
        box-shadow: var(--forum-shadow);
      }

      .forum-button--primary {
        background: var(--forum-accent);
        color: #fff;
        border-color: var(--forum-accent);
      }

      .forum-button:hover {
        text-decoration: none;
        transform: translateY(-1px);
      }

      .forum-notice {
        margin: 0 0 18px;
        border-radius: 14px;
        padding: 14px 16px;
        background: var(--forum-accent-soft);
        border: 1px solid rgba(11, 87, 208, 0.15);
      }

      .forum-notice--error {
        background: #fff1f0;
        border-color: rgba(180, 35, 24, 0.18);
        color: var(--forum-danger);
      }

      .forum-notice--warning {
        background: #fff7ed;
        border-color: rgba(154, 52, 18, 0.18);
        color: var(--forum-warning);
      }

      .forum-notice__body {
        margin: 0;
      }

      .forum-layout {
        display: grid;
        grid-template-columns: 280px minmax(0, 1fr);
        gap: 24px;
        align-items: start;
      }

      @media (max-width: 900px) {
        .forum-layout {
          grid-template-columns: 1fr;
        }
      }

      .forum-layout__sidebar,
      .forum-layout__content {
        min-width: 0;
      }

      .forum-layout__sidebar {
        position: sticky;
        top: 18px;
      }

      @media (max-width: 900px) {
        .forum-layout__sidebar {
          position: static;
        }
      }

      .forum-category-nav {
        display: grid;
        gap: 10px;
        padding: 16px;
        border: 1px solid var(--forum-border);
        border-radius: 18px;
        background: var(--forum-surface);
        box-shadow: var(--forum-shadow);
      }

      .forum-category-nav__item {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
        padding: 12px 14px;
        border-radius: 14px;
        border: 1px solid transparent;
        color: inherit;
      }

      .forum-category-nav__item:hover {
        text-decoration: none;
        background: var(--forum-surface-alt);
      }

      .forum-category-nav__item--active {
        background: var(--forum-accent-soft);
        border-color: rgba(11, 87, 208, 0.18);
      }

      .forum-category-nav__name {
        display: block;
        font-weight: 700;
        margin-bottom: 2px;
      }

      .forum-category-nav__description {
        display: block;
        color: var(--forum-muted);
        font-size: 0.92rem;
      }

      .forum-thread-list {
        display: grid;
        gap: 14px;
      }

      .forum-thread-card {
        padding: 18px;
        border: 1px solid var(--forum-border);
        border-radius: 18px;
        background: var(--forum-surface);
        box-shadow: var(--forum-shadow);
      }

      .forum-thread-card__title {
        margin: 0 0 8px;
        font-size: 1.12rem;
        line-height: 1.3;
      }

      .forum-thread-card__meta {
        display: flex;
        flex-wrap: wrap;
        gap: 8px 12px;
        color: var(--forum-muted);
        font-size: 0.92rem;
        margin-bottom: 10px;
      }

      .forum-thread-card__excerpt {
        margin: 0;
        color: var(--forum-text);
        white-space: pre-wrap;
      }

      .forum-thread-detail {
        padding: 20px;
        border: 1px solid var(--forum-border);
        border-radius: 20px;
        background: var(--forum-surface);
        box-shadow: var(--forum-shadow);
      }

      .forum-thread-detail__header {
        display: grid;
        gap: 10px;
        margin-bottom: 16px;
        padding-bottom: 16px;
        border-bottom: 1px solid var(--forum-border);
      }

      .forum-thread-detail__title {
        margin: 0;
        font-size: clamp(1.5rem, 3vw, 2.2rem);
        line-height: 1.15;
      }

      .forum-thread-detail__meta {
        display: flex;
        flex-wrap: wrap;
        gap: 8px 12px;
        color: var(--forum-muted);
        font-size: 0.95rem;
      }

      .forum-thread-detail__body {
        margin-bottom: 18px;
        white-space: pre-wrap;
        font-size: 1rem;
      }

      .forum-reply-list {
        display: grid;
        gap: 12px;
        margin: 0 0 18px;
      }

      .forum-reply {
        padding: 16px;
        border-radius: 16px;
        border: 1px solid var(--forum-border);
        background: var(--forum-surface-alt);
      }

      .forum-reply__meta {
        display: flex;
        flex-wrap: wrap;
        gap: 8px 10px;
        color: var(--forum-muted);
        font-size: 0.92rem;
        margin-bottom: 8px;
      }

      .forum-reply__body {
        white-space: pre-wrap;
      }

      .forum-reply-form,
      .forum-compose {
        padding: 20px;
        border: 1px solid var(--forum-border);
        border-radius: 18px;
        background: var(--forum-surface);
        box-shadow: var(--forum-shadow);
      }

      .forum-compose {
        margin-top: 18px;
      }

      .forum-form {
        display: grid;
        gap: 14px;
      }

      .forum-form__row {
        display: grid;
        gap: 8px;
      }

      .forum-form__label {
        font-weight: 700;
        font-size: 0.96rem;
      }

      .forum-form__input,
      .forum-form__select,
      .forum-form__textarea {
        width: 100%;
        border: 1px solid var(--forum-border);
        border-radius: 12px;
        padding: 0.85rem 0.95rem;
        font: inherit;
        background: #fff;
        color: inherit;
      }

      .forum-form__textarea {
        min-height: 160px;
        resize: vertical;
      }

      .forum-form__help {
        color: var(--forum-muted);
        font-size: 0.9rem;
        margin: -2px 0 0;
      }

      .forum-form__actions {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        align-items: center;
      }

      .forum-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        border-radius: 999px;
        padding: 0.25rem 0.6rem;
        background: #eef2ff;
        color: #3730a3;
        font-size: 0.8rem;
        font-weight: 700;
        line-height: 1.2;
      }

      .forum-badge--muted {
        background: #eef2f7;
        color: var(--forum-muted);
      }

      .forum-badge--warning {
        background: #fff7ed;
        color: var(--forum-warning);
      }

      .forum-badge--danger {
        background: #fff1f0;
        color: var(--forum-danger);
      }

      .forum-empty {
        padding: 22px;
        border: 1px dashed var(--forum-border);
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.7);
        color: var(--forum-muted);
        text-align: center;
      }
    </style>
    """


def _document(title: str, body: str, description: str = "") -> str:
    meta = f'<meta name="description" content="{_t(description)}">' if description else ""
    return (
        "<!doctype html>"
        '<html lang="en">'
        "<head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{_t(title)}</title>"
        f"{meta}"
        '<link rel="stylesheet" href="/html_css/forum.css">'
        f"{_styles()}"
        "</head>"
        "<body>"
        '<main class="forum-shell">'
        f"{body}"
        "</main>"
        "</body>"
        "</html>"
    )


def _header(title: str, summary: str, actions_html: str = "") -> str:
    actions = f'<div class="forum-shell__actions">{actions_html}</div>' if actions_html else ""
    return (
        '<header class="forum-shell__header">'
        "<div>"
        '<p class="forum-shell__eyebrow">BMW MarketPlace Forum</p>'
        f'<h1 class="forum-shell__title">{_t(title)}</h1>'
        f'<p class="forum-shell__summary">{_t(summary)}</p>'
        "</div>"
        f"{actions}"
        "</header>"
    )


def _layout(sidebar_html: str, content_html: str) -> str:
    return (
        '<section class="forum-layout">'
        f'<aside class="forum-layout__sidebar">{sidebar_html}</aside>'
        f'<div class="forum-layout__content">{content_html}</div>'
        "</section>"
    )


def render_forum_index(
    data_dir: Path,
    current_user: dict[str, str] | None = None,
    notice_code: str = "",
    filters: dict[str, str] | None = None,
) -> str:
    _get_forum_thread, list_forum_categories, _list_forum_replies, list_forum_threads = _forum_helpers()
    categories = list_forum_categories(data_dir)
    category_names = {str(category.get("category_id", "")): str(category.get("name", "")) for category in categories}
    category_slugs = {str(category.get("category_id", "")): str(category.get("slug", "")) for category in categories}
    normalized_filters = _normalized_filters(filters)
    all_threads = list_forum_threads(data_dir)
    filtered_threads = [
        thread
        for thread in all_threads
        if _thread_matches_filters(thread, category_names.get(str(thread.get("category_id", "")), ""), normalized_filters)
    ]
    threads = _sorted_threads_for_filters(filtered_threads, normalized_filters)[:24]
    available_tags = _available_tags(all_threads)

    if threads:
        thread_list = '<section class="forum-thread-list">' + "".join(
            _thread_card(
                thread,
                category_names.get(str(thread.get("category_id", "")), ""),
                category_slugs.get(str(thread.get("category_id", "")), ""),
            )
            for thread in threads
        ) + "</section>"
    else:
        empty_message = (
            "No forum discussions matched your current filters."
            if normalized_filters.get("search") or normalized_filters.get("tag")
            else "No forum discussions have been posted yet."
        )
        thread_list = f'<div class="forum-empty">{_t(empty_message)}</div>'

    shown_count = len(threads)
    total_count = len(filtered_threads)
    results_message = (
        f"Showing {shown_count} of {total_count} matching discussions."
        if total_count > shown_count
        else f"Showing {shown_count} discussion{'s' if shown_count != 1 else ''}."
    )
    filters_html = _filter_form("/forums", normalized_filters, available_tags)
    actions_html = '<a class="forum-button forum-button--primary" href="/forums/new">Start a discussion</a>'
    body = _header(
        "BMW Forum",
        "Ask questions, share project updates, compare parts, and talk through the details that matter to BMW owners and shoppers.",
        actions_html,
    ) + _notice_html(notice_code) + _layout(
        _category_nav(categories),
        filters_html + f'<p class="forum-form__help">{_t(results_message)}</p>' + thread_list,
    )
    return _document("BMW Forum", body, "BMW Forum discussions, categories, and recent threads.")


def render_forum_category(
    data_dir: Path,
    slug: str,
    current_user: dict[str, str] | None = None,
    notice_code: str = "",
    filters: dict[str, str] | None = None,
) -> str:
    _get_forum_thread, list_forum_categories, _list_forum_replies, list_forum_threads = _forum_helpers()
    categories = list_forum_categories(data_dir)
    category = next((row for row in categories if str(row.get("slug", "")) == slug), None)
    if not category:
        actions_html = '<a class="forum-button" href="/forums">Back to all discussions</a>'
        body = (
            _header("Forum category not found", "The category you requested does not exist or has been removed.", actions_html)
            + _notice_html("missing_category")
            + _layout(_category_nav(categories, slug), '<div class="forum-empty">That category could not be found.</div>')
        )
        return _document("Forum category not found", body, "Forum category not found.")

    normalized_filters = _normalized_filters(filters)
    all_threads = list_forum_threads(data_dir, category_slug=slug)
    category_name = str(category.get("name", ""))
    filtered_threads = [
        thread for thread in all_threads if _thread_matches_filters(thread, category_name, normalized_filters)
    ]
    threads = _sorted_threads_for_filters(filtered_threads, normalized_filters)
    available_tags = _available_tags(all_threads)

    if threads:
        thread_list = '<section class="forum-thread-list">' + "".join(
            _thread_card(thread, category_name, slug) for thread in threads
        ) + "</section>"
    else:
        empty_message = (
            "No discussions in this category matched your current filters."
            if normalized_filters.get("search") or normalized_filters.get("tag")
            else "No discussions have been posted in this category yet."
        )
        thread_list = f'<div class="forum-empty">{_t(empty_message)}</div>'

    results_message = f"Showing {len(threads)} discussion{'s' if len(threads) != 1 else ''}."
    filters_html = _filter_form(f"/forums/categories/{quote(slug)}", normalized_filters, available_tags)
    actions_html = '<a class="forum-button forum-button--primary" href="/forums/new">Start a discussion</a>'
    body = (
        _header(category_name or "Forum category", str(category.get("description", "")), actions_html)
        + _notice_html(notice_code)
        + _layout(
            _category_nav(categories, str(category.get("slug", ""))),
            filters_html + f'<p class="forum-form__help">{_t(results_message)}</p>' + thread_list,
        )
    )
    return _document(str(category.get("name", "Forum category")), body, str(category.get("description", "")))


def render_forum_thread(data_dir: Path, thread_id: str, current_user: dict[str, str] | None = None, notice_code: str = "") -> str:
    get_forum_thread, list_forum_categories, list_forum_replies, _list_forum_threads = _forum_helpers()
    categories = list_forum_categories(data_dir)
    thread = get_forum_thread(data_dir, thread_id)
    if not thread:
        actions_html = '<a class="forum-button" href="/forums">Back to the forum</a>'
        body = (
            _header("Discussion not found", "We could not find the discussion you requested.", actions_html)
            + _notice_html("missing_thread")
            + _layout(_category_nav(categories), '<div class="forum-empty">That thread could not be found.</div>')
        )
        return _document("Discussion not found", body, "Discussion not found.")

    category = next((row for row in categories if str(row.get("category_id", "")) == str(thread.get("category_id", ""))), {})
    replies = _sorted_replies(list_forum_replies(data_dir, thread_id))
    if replies:
        reply_list = '<section class="forum-reply-list">' + "".join(_reply_card_with_report(reply, thread_id) for reply in replies) + "</section>"
    else:
        reply_list = '<div class="forum-empty">Be the first to reply to this discussion.</div>'

    if _as_bool(thread.get("locked")):
        reply_panel = '<div class="forum-empty">This discussion is locked. Replies are disabled.</div>'
    else:
        reply_panel = (
            '<section class="forum-reply-form">'
            '<h2>Reply to this discussion</h2>'
            f'<p class="forum-form__help">Posting as {_t(_current_name(current_user))} · {_t(_current_role(current_user))}</p>'
            f'<form class="forum-form" method="post" action="/forums/threads/{_t(thread_id)}/replies">'
            '<div class="forum-form__row">'
            '<label class="forum-form__label" for="body">Your reply</label>'
            '<textarea class="forum-form__textarea" id="body" name="body" required></textarea>'
            '</div>'
            '<div class="forum-form__actions">'
            '<button class="forum-button forum-button--primary" type="submit">Post reply</button>'
            '<a class="forum-button" href="/forums">Back to forum</a>'
            '</div>'
            '</form>'
            '</section>'
        )

    tags = [str(tag).strip() for tag in thread.get("tags", []) if str(tag).strip()]
    tag_html = _tag_badges(tags, str(category.get("slug", "")))
    detail = (
        '<article class="forum-thread-detail">'
        '<header class="forum-thread-detail__header">'
        f'<div class="forum-thread-card__meta"><a href="/forums/categories/{_t(str(category.get("slug", "")))}">{_t(str(category.get("name", "Forum")))}</a>{_thread_badges(thread)}</div>'
        f'<h1 class="forum-thread-detail__title">{_t(str(thread.get("title", "Untitled discussion")))}</h1>'
        '<div class="forum-thread-detail__meta">'
        f'<span>By {_t(str(thread.get("author_name", "Unknown")))} · {_t(str(thread.get("author_role", "Member")))}</span>'
        f'<span>Created {_t(str(thread.get("created_at", "")))}</span>'
        f'<span>Updated {_t(str(thread.get("updated_at", thread.get("created_at", ""))))}</span>'
        "</div>"
        f'<div class="forum-thread-detail__meta">{tag_html}</div>'
        '</header>'
        f'<div class="forum-thread-detail__body">{_t(str(thread.get("body", "")))}</div>'
        '<section class="forum-reply-form" aria-labelledby="forum-report-thread-heading">'
        '<h2 id="forum-report-thread-heading">Report this discussion</h2>'
        '<p class="forum-form__help">If this discussion breaks community guidelines, submit a report for moderator review.</p>'
        f'{_report_form("thread", thread_id, thread_id, button_label="Submit report", details_label="Additional context")}'
        '</section>'
        '<section aria-labelledby="forum-replies-heading">'
        '<h2 id="forum-replies-heading">Replies</h2>'
        f"{reply_list}"
        '</section>'
        f'<div class="forum-compose">{reply_panel}</div>'
        '</article>'
    )
    actions_html = '<a class="forum-button" href="/forums/new">Start a new discussion</a>'
    body = (
        _header(str(category.get("name", "Forum")), "Thread details, replies, and a quick reply form.", actions_html)
        + _notice_html(notice_code)
        + _layout(_category_nav(categories, str(category.get("slug", ""))), detail)
    )
    return _document(str(thread.get("title", "Discussion")), body, str(thread.get("excerpt", thread.get("title", "Discussion"))))


def render_forum_new_thread(
    data_dir: Path,
    current_user: dict[str, str] | None = None,
    values: dict[str, str] | None = None,
    error: str = "",
) -> str:
    _get_forum_thread, list_forum_categories, _list_forum_replies, _list_forum_threads = _forum_helpers()
    categories = list_forum_categories(data_dir)
    values = values or {}
    category_id = _value(values, "category_id")
    title = _value(values, "title")
    excerpt = _value(values, "excerpt")
    body_value = _value(values, "body")
    tags = _value(values, "tags")

    options = ['<option value="">Choose a category</option>']
    for category in _sorted_categories(categories):
        option_value = str(category.get("category_id", ""))
        selected = " selected" if option_value == category_id else ""
        options.append(f'<option value="{_t(option_value)}"{selected}>{_t(category.get("name", ""))}</option>')
    if len(options) == 1:
        options.append('<option value="" disabled>No categories available</option>')

    form = (
        '<section class="forum-reply-form">'
        '<h2>Create a new thread</h2>'
        f'<p class="forum-form__help">Posting as {_t(_current_name(current_user))} · {_t(_current_role(current_user))}</p>'
        '<form class="forum-form" method="post" action="/forums/new">'
        '<div class="forum-form__row">'
        '<label class="forum-form__label" for="category_id">Category</label>'
        f'<select class="forum-form__select" id="category_id" name="category_id" required>{"".join(options)}</select>'
        '</div>'
        '<div class="forum-form__row">'
        '<label class="forum-form__label" for="title">Title</label>'
        f'<input class="forum-form__input" id="title" name="title" type="text" value="{_t(title)}" required>'
        '</div>'
        '<div class="forum-form__row">'
        '<label class="forum-form__label" for="excerpt">Excerpt</label>'
        f'<textarea class="forum-form__textarea" id="excerpt" name="excerpt" rows="3" placeholder="Short summary for the forum list.">{_t(excerpt)}</textarea>'
        '</div>'
        '<div class="forum-form__row">'
        '<label class="forum-form__label" for="body">Body</label>'
        f'<textarea class="forum-form__textarea" id="body" name="body" required placeholder="Tell the community what you are working on.">{_t(body_value)}</textarea>'
        '</div>'
        '<div class="forum-form__row">'
        '<label class="forum-form__label" for="tags">Tags</label>'
        f'<input class="forum-form__input" id="tags" name="tags" type="text" value="{_t(tags)}" placeholder="E39, maintenance, DIY">'
        '<p class="forum-form__help">Separate tags with commas.</p>'
        '</div>'
        '<div class="forum-form__actions">'
        '<button class="forum-button forum-button--primary" type="submit">Publish thread</button>'
        '<a class="forum-button" href="/forums">Cancel</a>'
        '</div>'
        '</form>'
        '</section>'
    )
    actions_html = '<a class="forum-button" href="/forums">Back to the forum</a>'
    body = (
        _header("Start a discussion", "Share a project update, maintenance question, parts recommendation, or dealership experience with the community.", actions_html)
        + _error_html(error)
        + _layout(_category_nav(categories), form)
    )
    return _document("Start a discussion", body, "Create a new forum discussion.")


def render_forum_reports(
    data_dir: Path,
    current_user: dict[str, str] | None = None,
    notice_code: str = "",
) -> str:
    try:
        from .forum_core import get_forum_reply, get_forum_thread, list_forum_categories, list_forum_reports
    except ImportError:
        from forum_core import get_forum_reply, get_forum_thread, list_forum_categories, list_forum_reports

    reports = list_forum_reports(data_dir)
    categories = list_forum_categories(data_dir)
    category_map = {str(category.get("category_id", "")): str(category.get("name", "")) for category in categories}
    current_role = _current_role(current_user).strip().upper()
    can_moderate = current_role in {"ADMIN", "SITE_ADMIN", "MODERATOR"}

    def _target_label(report: dict[str, Any]) -> str:
        return "Thread" if str(report.get("target_type", "")).strip().lower() == "thread" else "Reply"

    def _target_context(report: dict[str, Any]) -> str:
        target_type = str(report.get("target_type", "")).strip().lower()
        if target_type == "thread":
            thread = get_forum_thread(data_dir, str(report.get("thread_id", "")))
            if thread:
                category_name = category_map.get(str(thread.get("category_id", "")), "")
                prefix = f"{category_name} · " if category_name else ""
                return f"{prefix}{str(thread.get('title', 'Untitled discussion'))}"
            return str(report.get("thread_id", ""))
        reply = get_forum_reply(data_dir, str(report.get("target_id", "")))
        if reply:
            body = str(reply.get("body", "")).strip()
            return f"Reply by {str(reply.get('author_name', 'Unknown'))}: {body[:120]}"
        return str(report.get("target_id", ""))

    cards: list[str] = []
    for report in reports:
        status = str(report.get("status", "OPEN")).strip().upper() or "OPEN"
        report_id = str(report.get("report_id", ""))
        action_html = ""
        if can_moderate and status == "OPEN":
            action_html = (
                '<div class="forum-form__actions">'
                f'<form class="forum-form" method="post" action="/forums/moderation/reports/{_t(report_id)}/resolve">'
                '<input type="hidden" name="action_taken" value="Resolved after review" />'
                '<button class="forum-button forum-button--primary" type="submit">Resolve</button>'
                '</form>'
                f'<form class="forum-form" method="post" action="/forums/moderation/reports/{_t(report_id)}/dismiss">'
                '<input type="hidden" name="action_taken" value="Dismissed after review" />'
                '<button class="forum-button" type="submit">Dismiss</button>'
                '</form>'
                '</div>'
            )
        cards.append(
            '<article class="forum-thread-card">'
            f'<div class="forum-thread-card__meta">{_report_badge(str(report.get("target_type", "thread")), status)}</div>'
            f'<h2 class="forum-thread-card__title">{_t(_target_label(report))}: {_t(_report_reason_label(str(report.get("reason", ""))))}</h2>'
            f'<div class="forum-thread-card__meta"><span>Target: {_t(_target_context(report))}</span><span>Reported by {_t(str(report.get("reporter_name", "Unknown")))} · {_t(str(report.get("created_at", "")))}</span><span>Status: {_t(status.title())}</span></div>'
            f'<p class="forum-thread-card__excerpt">{_t(str(report.get("details", "")) or "No extra details provided.")}</p>'
            f"{action_html}"
            '</article>'
        )

    if not cards:
        report_list_html = '<div class="forum-empty">No forum reports have been filed yet.</div>'
    else:
        report_list_html = '<section class="forum-thread-list">' + "".join(cards) + "</section>"

    actions_html = '<a class="forum-button" href="/forums">Back to the forum</a>'
    body = (
        _header("Forum reports", "Review reported threads and replies from one place.", actions_html)
        + _notice_html(notice_code)
        + _layout(
            '<div class="forum-empty">Moderation queue</div>',
            (
                '<section class="forum-reply-form">'
                '<h2>Open reports</h2>'
                f'<p class="forum-form__help">Current role: {_t(current_role or "GUEST")}</p>'
                + (
                    report_list_html
                    if can_moderate
                    else '<div class="forum-empty">You do not have permission to review reports.</div>'
                )
                + '</section>'
            ),
        )
    )
    return _document("Forum reports", body, "Forum moderation and reporting queue.")
