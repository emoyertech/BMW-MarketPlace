from __future__ import annotations

import os
from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

try:
    from .marketplace_core import (
        SESSION_COOKIE_NAME,
        SESSION_MAX_AGE_SECONDS,
        db_path_for,
        get_app_user_by_id,
        get_user_id_for_session,
    )
except ImportError:
    from marketplace_core import (
        SESSION_COOKIE_NAME,
        SESSION_MAX_AGE_SECONDS,
        db_path_for,
        get_app_user_by_id,
        get_user_id_for_session,
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
