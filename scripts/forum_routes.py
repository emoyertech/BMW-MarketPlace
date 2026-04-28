from __future__ import annotations

from html import escape
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import Response

try:
    from .forum_core import (
        add_forum_reply,
        create_forum_report,
        create_forum_thread,
        get_forum_reply,
        get_forum_report,
        get_forum_thread,
        increment_forum_thread_view_count,
        list_forum_categories,
        list_forum_replies,
        list_forum_threads,
        resolve_forum_report,
    )
    from .web_helpers import _current_user, _html, _redirect, _request_values_and_files
    try:
        from . import marketplace_render as _marketplace_render
    except ImportError:
        import marketplace_render as _marketplace_render
except ImportError:
    from forum_core import (
        add_forum_reply,
        create_forum_report,
        create_forum_thread,
        get_forum_reply,
        get_forum_report,
        get_forum_thread,
        increment_forum_thread_view_count,
        list_forum_categories,
        list_forum_replies,
        list_forum_threads,
        resolve_forum_report,
    )
    from web_helpers import _current_user, _html, _redirect, _request_values_and_files
    try:
        import marketplace_render as _marketplace_render
    except ImportError:
        from . import marketplace_render as _marketplace_render  # type: ignore[no-redef]


def _posting_user(current_user: dict[str, str] | None) -> dict[str, str]:
    if current_user is not None:
        return current_user
    return {
        "user_id": "guest",
        "name": "Guest",
        "full_name": "Guest",
        "display_name": "Guest",
        "role": "Guest",
    }


def _can_moderate(current_user: dict[str, str] | None) -> bool:
    if not current_user:
        return False
    role = str(current_user.get("role", "")).strip().upper()
    return role in {"ADMIN", "SITE_ADMIN", "MODERATOR"}


def _forum_filters(request: Request) -> dict[str, str]:
    return {
        "search": request.query_params.get("search", ""),
        "tag": request.query_params.get("tag", ""),
        "sort_by": request.query_params.get("sort_by", "active"),
    }


def _not_found_html(title: str, message: str) -> str:
    safe_title = escape(title)
    safe_message = escape(message)
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<title>{safe_title} | BMW Marketplace</title>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<link rel='stylesheet' href='/styles.css' />"
        "</head><body>"
        "<main class='forum-layout'>"
        "<section class='forum-layout__content'>"
        "<div class='forum-empty'>"
        f"<h1>{safe_title}</h1>"
        f"<p>{safe_message}</p>"
        "<p><a class='button secondary' href='/forums'>Back to forums</a></p>"
        "</div>"
        "</section>"
        "</main>"
        "</body></html>"
    )


def _notice_block(notice_code: str) -> str:
    notice_code = notice_code.strip()
    if not notice_code:
        return ""
    return f"<div class='forum-notice'>{escape(notice_code.replace('_', ' ').title())}</div>"


def _forum_shell(title: str, body_html: str) -> str:
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{escape(title)} | BMW Marketplace</title>"
        "<link rel='stylesheet' href='/styles.css' />"
        "<style>"
        ".forum-layout{display:grid;grid-template-columns:minmax(220px,280px) 1fr;gap:1.5rem;align-items:start;}"
        ".forum-layout__sidebar,.forum-layout__content,.forum-thread-detail,.forum-thread-card,.forum-reply,.forum-compose{border:1px solid rgba(148,163,184,0.35);border-radius:18px;background:#fff;box-shadow:0 1px 2px rgba(15,23,42,0.05);}"
        ".forum-layout__sidebar,.forum-layout__content{padding:1.25rem;}"
        ".forum-category-nav{display:grid;gap:0.5rem;margin:0;padding:0;list-style:none;}"
        ".forum-category-nav__item{display:block;padding:0.7rem 0.85rem;border-radius:12px;text-decoration:none;color:#0f172a;background:#f8fafc;}"
        ".forum-category-nav__item--active{background:#dbeafe;color:#1d4ed8;font-weight:700;}"
        ".forum-thread-list{display:grid;gap:1rem;margin:1rem 0 0;padding:0;list-style:none;}"
        ".forum-thread-card,.forum-thread-detail,.forum-reply,.forum-compose{padding:1.1rem;}"
        ".forum-thread-card__title,.forum-thread-detail__header h1{margin:0;}"
        ".forum-thread-card__meta,.forum-reply__meta{color:#64748b;font-size:0.9rem;display:flex;gap:0.6rem;flex-wrap:wrap;}"
        ".forum-thread-card__excerpt,.forum-thread-detail__body,.forum-reply__body{margin-top:0.75rem;color:#334155;line-height:1.55;}"
        ".forum-reply-list{display:grid;gap:1rem;margin:1rem 0 0;padding:0;list-style:none;}"
        ".forum-badge{display:inline-flex;align-items:center;padding:0.2rem 0.55rem;border-radius:999px;background:#eef2ff;color:#3730a3;font-size:0.8rem;font-weight:700;}"
        ".forum-empty{padding:1rem;border:1px dashed rgba(148,163,184,0.55);border-radius:14px;background:#f8fafc;color:#475569;}"
        ".forum-reply-form{display:grid;gap:0.8rem;margin-top:1rem;}"
        ".forum-reply-form textarea,.forum-compose input,.forum-compose textarea,.forum-compose select{width:100%;padding:0.75rem 0.85rem;border:1px solid #cbd5e1;border-radius:12px;font:inherit;box-sizing:border-box;}"
        ".forum-compose{display:grid;gap:1rem;}"
        ".forum-layout__content{display:grid;gap:1rem;}"
        ".forum-thread-detail__header{display:grid;gap:0.5rem;}"
        ".forum-thread-detail__body{white-space:pre-wrap;}"
        "@media (max-width: 860px){.forum-layout{grid-template-columns:1fr;}}"
        "</style></head><body><main class='page-shell forum-layout'>"
        f"{body_html}"
        "</main></body></html>"
    )


def _forum_categories_by_id(categories: list[dict]) -> dict[str, dict]:
    return {str(category.get("category_id", "")).strip(): category for category in categories if str(category.get("category_id", "")).strip()}


def _forum_category_name(category: dict | None) -> str:
    if not category:
        return "Forum"
    name = str(category.get("name", "")).strip()
    return name or "Forum"


def _forum_category_nav(categories: list[dict], active_slug: str | None = None) -> str:
    items: list[str] = []
    for category in categories:
        slug = str(category.get("slug", "")).strip()
        category_name = escape(str(category.get("name", "")).strip() or "Forum category")
        description = escape(str(category.get("description", "")).strip())
        active_class = " forum-category-nav__item--active" if active_slug and slug == active_slug else ""
        items.append(
            "<li>"
            f"<a class='forum-category-nav__item{active_class}' href='/forums/categories/{escape(slug)}'>"
            f"{category_name}<br><small>{description}</small>"
            "</a>"
            "</li>"
        )
    if not items:
        items.append("<li class='forum-empty'>No forum categories have been published yet.</li>")
    return "<ul class='forum-category-nav'>" + "".join(items) + "</ul>"


def _forum_thread_card_html(thread: dict, category_name: str) -> str:
    thread_id = escape(str(thread.get("thread_id", "")).strip())
    title = escape(str(thread.get("title", "")).strip() or "Untitled thread")
    excerpt = escape(str(thread.get("excerpt", "")).strip())
    author_name = escape(str(thread.get("author_name", "")).strip() or "Forum Member")
    author_role = escape(str(thread.get("author_role", "")).strip() or "member")
    reply_count = escape(str(thread.get("reply_count", 0)))
    view_count = escape(str(thread.get("view_count", 0)))
    tags = thread.get("tags", [])
    tag_html = "".join(
        f"<span class='forum-badge'>{escape(str(tag).strip())}</span>" for tag in tags if str(tag).strip()
    )
    return (
        "<article class='forum-thread-card'>"
        f"<h2 class='forum-thread-card__title'><a href='/forums/threads/{thread_id}'>{title}</a></h2>"
        f"<div class='forum-thread-card__meta'><span>{escape(category_name)}</span><span>{author_name}</span><span>{author_role}</span><span>{reply_count} replies</span><span>{view_count} views</span></div>"
        f"<div class='forum-thread-card__excerpt'>{excerpt}</div>"
        f"<div style='display:flex;gap:0.5rem;flex-wrap:wrap;margin-top:0.75rem'>{tag_html}</div>"
        "</article>"
    )


def _forum_reply_html(reply: dict) -> str:
    author_name = escape(str(reply.get("author_name", "")).strip() or "Forum Member")
    author_role = escape(str(reply.get("author_role", "")).strip() or "member")
    created_at = escape(str(reply.get("created_at", "")).strip())
    body = escape(str(reply.get("body", "")).strip())
    return (
        "<li class='forum-reply'>"
        f"<div class='forum-reply__meta'><strong>{author_name}</strong><span>{author_role}</span><span>{created_at}</span></div>"
        f"<div class='forum-reply__body'>{body}</div>"
        "</li>"
    )


def _fallback_render_forum_index(data_dir: Path, current_user: dict[str, str] | None = None, notice_code: str = "") -> str:
    categories = list_forum_categories(data_dir)
    threads = list_forum_threads(data_dir)
    category_map = _forum_categories_by_id(categories)
    sidebar = _forum_category_nav(categories)
    cards = [
        _forum_thread_card_html(thread, _forum_category_name(category_map.get(str(thread.get("category_id", "")).strip())))
        for thread in threads[:10]
    ]
    if not cards:
        cards_html = "<div class='forum-empty'>No threads have been posted yet.</div>"
    else:
        cards_html = "<div class='forum-thread-list'>" + "".join(cards) + "</div>"

    user_note = ""
    if current_user:
        user_note = f"<p>Signed in as {escape(str(current_user.get('full_name', '')).strip() or 'Forum Member')}.</p>"

    content = (
        "<aside class='forum-layout__sidebar'>"
        "<p class='eyebrow'>Categories</p>"
        f"{sidebar}"
        "</aside>"
        "<section class='forum-layout__content'>"
        f"{_notice_block(notice_code)}"
        "<header class='forum-thread-detail__header'>"
        "<p class='eyebrow'>Community</p>"
        "<h1>BMW Marketplace forums</h1>"
        "<p>Browse community categories, recent discussions, build threads, maintenance questions, and marketplace chatter.</p>"
        f"{user_note}"
        "<p><a class='button primary' href='/forums/new'>Start a new thread</a></p>"
        "</header>"
        f"{cards_html}"
        "</section>"
    )
    return _forum_shell("Forums", content)


def _fallback_render_forum_category(data_dir: Path, slug: str, current_user: dict[str, str] | None = None, notice_code: str = "") -> str:
    categories = list_forum_categories(data_dir)
    category = next((item for item in categories if str(item.get("slug", "")).strip() == slug), None)
    if category is None:
        return _not_found_html("Forum category not found", f"No forum category matches “{slug}”.")
    threads = list_forum_threads(data_dir, slug)
    sidebar = _forum_category_nav(categories, active_slug=slug)
    category_name = _forum_category_name(category)
    description = escape(str(category.get("description", "")).strip())
    cards = [
        _forum_thread_card_html(thread, category_name)
        for thread in threads
    ]
    if not cards:
        cards_html = "<div class='forum-empty'>No threads in this category yet.</div>"
    else:
        cards_html = "<div class='forum-thread-list'>" + "".join(cards) + "</div>"

    content = (
        "<aside class='forum-layout__sidebar'>"
        "<p class='eyebrow'>Categories</p>"
        f"{sidebar}"
        "</aside>"
        "<section class='forum-layout__content'>"
        f"{_notice_block(notice_code)}"
        "<header class='forum-thread-detail__header'>"
        f"<p class='eyebrow'>{escape(category_name)}</p>"
        f"<h1>{escape(category_name)}</h1>"
        f"<p>{description}</p>"
        "<p><a class='button primary' href='/forums/new'>Start a new thread</a></p>"
        "</header>"
        f"{cards_html}"
        "</section>"
    )
    return _forum_shell(category_name, content)


def _fallback_render_forum_thread(data_dir: Path, thread_id: str, current_user: dict[str, str] | None = None, notice_code: str = "") -> str:
    thread = get_forum_thread(data_dir, thread_id)
    if thread is None:
        return _not_found_html("Forum thread not found", f"No forum thread matches “{thread_id}”.")
    categories = list_forum_categories(data_dir)
    category = next((item for item in categories if str(item.get("category_id", "")).strip() == str(thread.get("category_id", "")).strip()), None)
    sidebar = _forum_category_nav(categories, active_slug=str(category.get("slug", "")).strip() if category else None)
    replies = list_forum_replies(data_dir, thread_id)
    tag_html = "".join(
        f"<span class='forum-badge'>{escape(str(tag).strip())}</span>" for tag in thread.get("tags", []) if str(tag).strip()
    )
    reply_list_html = "".join(_forum_reply_html(reply) for reply in replies)
    if not reply_list_html:
        reply_list_html = "<li class='forum-empty'>No replies yet. Be the first to answer.</li>"

    reply_form_html = ""
    if not bool(thread.get("locked")):
        reply_form_html = (
            "<form class='forum-reply-form' method='post' action='/forums/threads/"
            f"{escape(thread_id)}/replies'>"
            "<label>Reply<textarea name='body' rows='5' placeholder='Write your reply here...' required></textarea></label>"
            "<button class='button primary' type='submit'>Post reply</button>"
            "</form>"
        )
    else:
        reply_form_html = "<div class='forum-empty'>This thread is locked and new replies are disabled.</div>"

    content = (
        "<aside class='forum-layout__sidebar'>"
        "<p class='eyebrow'>Categories</p>"
        f"{sidebar}"
        "</aside>"
        "<section class='forum-layout__content'>"
        f"{_notice_block(notice_code)}"
        "<article class='forum-thread-detail'>"
        "<header class='forum-thread-detail__header'>"
        f"<p class='eyebrow'>{escape(_forum_category_name(category))}</p>"
        f"<h1>{escape(str(thread.get('title', '')).strip() or 'Untitled thread')}</h1>"
        f"<div class='forum-thread-detail__header forum-thread-card__meta'><span>{escape(str(thread.get('author_name', '')).strip() or 'Forum Member')}</span><span>{escape(str(thread.get('author_role', '')).strip() or 'member')}</span><span>{escape(str(thread.get('created_at', '')).strip())}</span><span>{escape(str(thread.get('reply_count', 0)))} replies</span><span>{escape(str(thread.get('view_count', 0)))} views</span></div>"
        "</header>"
        f"<div class='forum-thread-detail__body'>{escape(str(thread.get('body', '')).strip())}</div>"
        f"<div style='display:flex;gap:0.5rem;flex-wrap:wrap;margin-top:0.75rem'>{tag_html}</div>"
        "</article>"
        "<section>"
        "<h2>Replies</h2>"
        f"<ul class='forum-reply-list'>{reply_list_html}</ul>"
        "</section>"
        "<section class='forum-compose'>"
        "<h2>Join the discussion</h2>"
        f"{reply_form_html}"
        "</section>"
        "</section>"
    )
    return _forum_shell(str(thread.get("title", "")).strip() or "Forum thread", content)


def _fallback_render_forum_new_thread(
    data_dir: Path,
    current_user: dict[str, str] | None = None,
    values: dict[str, str] | None = None,
    error: str = "",
) -> str:
    values = values or {}
    categories = list_forum_categories(data_dir)
    options: list[str] = ["<option value=''>Choose a category</option>"]
    selected_category_id = str(values.get("category_id", "")).strip()
    selected_category_slug = str(values.get("category_slug", "")).strip()
    for category in categories:
        category_id = str(category.get("category_id", "")).strip()
        slug = str(category.get("slug", "")).strip()
        selected = category_id == selected_category_id or slug == selected_category_slug
        options.append(
            f"<option value='{escape(category_id)}'{(' selected' if selected else '')}>{escape(str(category.get('name', '')).strip() or 'Forum category')}</option>"
        )

    user_note = ""
    if current_user:
        user_note = f"<p>Posting as {escape(str(current_user.get('full_name', '')).strip() or 'Forum Member')}.</p>"

    content = (
        "<aside class='forum-layout__sidebar'>"
        "<p class='eyebrow'>Categories</p>"
        f"{_forum_category_nav(categories)}"
        "</aside>"
        "<section class='forum-layout__content'>"
        "<article class='forum-compose'>"
        "<header class='forum-thread-detail__header'>"
        "<p class='eyebrow'>New thread</p>"
        "<h1>Start a forum discussion</h1>"
        "<p>Ask a question, start a project log, or share a marketplace topic with the community.</p>"
        f"{user_note}"
        "</header>"
        f"{('<div class="forum-empty">' + escape(error) + '</div>') if error else ''}"
        "<form class='forum-compose' method='post' action='/forums/new'>"
        f"<label>Category<select name='category_id' required>{''.join(options)}</select></label>"
        f"<label>Title<input type='text' name='title' value='{escape(values.get('title', ''))}' required /></label>"
        f"<label>Excerpt<input type='text' name='excerpt' value='{escape(values.get('excerpt', ''))}' placeholder='Short summary for the thread list' /></label>"
        f"<label>Tags<input type='text' name='tags' value='{escape(values.get('tags', ''))}' placeholder='e46, maintenance, build-log' /></label>"
        f"<label>Message<textarea name='body' rows='8' required>{escape(values.get('body', ''))}</textarea></label>"
        "<button class='button primary' type='submit'>Post thread</button>"
        "</form>"
        "</article>"
        "</section>"
    )
    return _forum_shell("Start a new thread", content)


render_forum_index = getattr(_marketplace_render, "render_forum_index", None) or _fallback_render_forum_index
render_forum_category = getattr(_marketplace_render, "render_forum_category", None) or _fallback_render_forum_category
render_forum_thread = getattr(_marketplace_render, "render_forum_thread", None) or _fallback_render_forum_thread
render_forum_new_thread = getattr(_marketplace_render, "render_forum_new_thread", None) or _fallback_render_forum_new_thread
render_forum_reports = getattr(_marketplace_render, "render_forum_reports", None)


def register_forum_routes(app: FastAPI, data_dir: Path) -> None:
    @app.get("/forums")
    def forums_index(request: Request, notice_code: str = "") -> Response:
        current_user = _current_user(request, data_dir)
        return _html(
            render_forum_index(
                data_dir,
                current_user=current_user,
                notice_code=notice_code,
                filters=_forum_filters(request),
            )
        )

    @app.get("/forums/categories/{slug}")
    def forum_category(request: Request, slug: str, notice_code: str = "") -> Response:
        categories = list_forum_categories(data_dir)
        if not any(str(category.get("slug", "")).strip() == slug for category in categories):
            return _html(
                _not_found_html("Forum category not found", f"No forum category matches “{slug}”."),
                status_code=404,
            )

        current_user = _current_user(request, data_dir)
        return _html(
            render_forum_category(
                data_dir,
                slug,
                current_user=current_user,
                notice_code=notice_code,
                filters=_forum_filters(request),
            )
        )

    @app.get("/forums/threads/{thread_id}")
    def forum_thread(request: Request, thread_id: str, notice_code: str = "") -> Response:
        if not increment_forum_thread_view_count(data_dir, thread_id):
            return _html(
                _not_found_html("Forum thread not found", f"No forum thread matches “{thread_id}”."),
                status_code=404,
            )

        thread = get_forum_thread(data_dir, thread_id)
        if thread is None:
            return _html(
                _not_found_html("Forum thread not found", f"No forum thread matches “{thread_id}”."),
                status_code=404,
            )

        current_user = _current_user(request, data_dir)
        return _html(
            render_forum_thread(
                data_dir,
                thread_id,
                current_user=current_user,
                notice_code=notice_code,
            )
        )

    @app.get("/forums/reports")
    def forum_reports(request: Request, notice_code: str = "") -> Response:
        current_user = _current_user(request, data_dir)
        if render_forum_reports is None:
            return _html(_not_found_html("Forum reports unavailable", "Forum reports are not available right now."), status_code=404)
        return _html(render_forum_reports(data_dir, current_user=current_user, notice_code=notice_code))

    @app.get("/forums/new")
    def forum_new_thread_form(request: Request, notice_code: str = "") -> Response:
        current_user = _current_user(request, data_dir)
        return _html(
            render_forum_new_thread(
                data_dir,
                current_user=current_user,
                values={},
                error="",
            )
        )

    @app.post("/forums/new")
    async def forum_create_thread(request: Request) -> Response:
        values, _ = await _request_values_and_files(request)
        current_user = _posting_user(_current_user(request, data_dir))

        title = values.get("title", "").strip()
        body = values.get("body", "").strip()
        category_id = values.get("category_id", "").strip() or values.get("category_slug", "").strip()

        categories = list_forum_categories(data_dir)
        matched_category = None
        for category in categories:
            category_value = str(category.get("category_id", "")).strip()
            category_slug = str(category.get("slug", "")).strip()
            if category_id == category_value or category_id == category_slug:
                matched_category = category
                break
        if matched_category is not None:
            category_id = str(matched_category.get("category_id", "")).strip()
            values["category_id"] = category_id

        if not category_id or not title or not body:
            return _html(
                render_forum_new_thread(
                    data_dir,
                    current_user=_current_user(request, data_dir),
                    values=values,
                    error="Choose a category and add both a title and message before posting.",
                ),
                status_code=400,
            )

        try:
            thread = create_forum_thread(data_dir, values, current_user)
        except ValueError:
            return _html(
                render_forum_new_thread(
                    data_dir,
                    current_user=_current_user(request, data_dir),
                    values=values,
                    error="We could not create that thread. Please try again.",
                ),
                status_code=400,
            )

        thread_id = str(thread.get("thread_id", "")).strip()
        if not thread_id:
            return _html(
                render_forum_new_thread(
                    data_dir,
                    current_user=_current_user(request, data_dir),
                    values=values,
                    error="We could not create that thread. Please try again.",
                ),
                status_code=400,
            )

        return _redirect(f"/forums/threads/{thread_id}")

    @app.post("/forums/reports")
    async def forum_create_report(request: Request) -> Response:
        values, _ = await _request_values_and_files(request)
        current_user = _posting_user(_current_user(request, data_dir))
        target_type = values.get("target_type", "").strip().lower()
        target_id = values.get("target_id", "").strip()
        thread_id = values.get("thread_id", "").strip()

        if target_type == "thread":
            thread = get_forum_thread(data_dir, target_id)
            if thread is None:
                return _redirect("/forums?notice_code=missing_thread")
            thread_id = target_id
        elif target_type == "reply":
            reply = get_forum_reply(data_dir, target_id)
            if reply is None:
                if thread_id:
                    return _redirect(f"/forums/threads/{thread_id}?notice_code=missing")
                return _redirect("/forums?notice_code=missing")
            if not thread_id:
                thread_id = str(reply.get("thread_id", "")).strip()
        else:
            if thread_id:
                return _redirect(f"/forums/threads/{thread_id}?notice_code=missing")
            return _redirect("/forums?notice_code=missing")

        try:
            create_forum_report(data_dir, target_type, target_id, thread_id, values, current_user)
        except ValueError:
            return _redirect(f"/forums/threads/{thread_id}?notice_code=missing")

        return _redirect(f"/forums/threads/{thread_id}?notice_code=report_created")

    @app.post("/forums/moderation/reports/{report_id}/resolve")
    async def forum_resolve_report(report_id: str, request: Request) -> Response:
        current_user = _current_user(request, data_dir)
        if current_user is None:
            return _redirect("/login?next=/forums/reports")
        if not _can_moderate(current_user):
            return _redirect("/forums/reports?notice_code=forbidden")
        if get_forum_report(data_dir, report_id) is None:
            return _redirect("/forums/reports?notice_code=missing_report")

        values, _ = await _request_values_and_files(request)
        try:
            resolve_forum_report(
                data_dir,
                report_id,
                current_user,
                status="RESOLVED",
                action_taken=values.get("action_taken", "").strip() or "Resolved after review",
            )
        except ValueError:
            return _redirect("/forums/reports?notice_code=missing_report")

        return _redirect("/forums/reports?notice_code=report_resolved")

    @app.post("/forums/moderation/reports/{report_id}/dismiss")
    async def forum_dismiss_report(report_id: str, request: Request) -> Response:
        current_user = _current_user(request, data_dir)
        if current_user is None:
            return _redirect("/login?next=/forums/reports")
        if not _can_moderate(current_user):
            return _redirect("/forums/reports?notice_code=forbidden")
        if get_forum_report(data_dir, report_id) is None:
            return _redirect("/forums/reports?notice_code=missing_report")

        values, _ = await _request_values_and_files(request)
        try:
            resolve_forum_report(
                data_dir,
                report_id,
                current_user,
                status="DISMISSED",
                action_taken=values.get("action_taken", "").strip() or "Dismissed after review",
            )
        except ValueError:
            return _redirect("/forums/reports?notice_code=missing_report")

        return _redirect("/forums/reports?notice_code=report_dismissed")

    @app.post("/forums/threads/{thread_id}/replies")
    async def forum_add_reply(thread_id: str, request: Request) -> Response:
        thread = get_forum_thread(data_dir, thread_id)
        if thread is None:
            return _html(
                _not_found_html("Forum thread not found", f"No forum thread matches “{thread_id}”."),
                status_code=404,
            )

        values, _ = await _request_values_and_files(request)
        body = values.get("body", "").strip()
        if not body:
            return _html(
                _not_found_html("Reply not saved", "Please enter a reply before posting."),
                status_code=400,
            )

        current_user = _posting_user(_current_user(request, data_dir))
        try:
            reply = add_forum_reply(data_dir, thread_id, values, current_user)
        except ValueError:
            return _html(
                _not_found_html("Reply not saved", "We could not save that reply. Please try again."),
                status_code=400,
            )

        reply_id = str(reply.get("reply_id", "")).strip()
        if not reply_id:
            return _html(
                _not_found_html("Reply not saved", "We could not save that reply. Please try again."),
                status_code=400,
            )

        return _redirect(f"/forums/threads/{thread_id}")
