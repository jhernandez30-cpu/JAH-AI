from __future__ import annotations

import json
import uuid
from typing import Any

try:
    from ..database import db_session, rows_to_dicts
    from ..security import utc_now
except ImportError:  # pragma: no cover
    from database import db_session, rows_to_dicts  # type: ignore
    from security import utc_now  # type: ignore


def normalize_session_id(session_id: str | None = None) -> str:
    clean = str(session_id or "").strip()[:120]
    return clean or str(uuid.uuid4())


def create_chat_session(user_id: int, title: str = "Nueva conversación", session_id: str | None = None) -> str:
    clean_session_id = normalize_session_id(session_id)
    clean_title = str(title or "Nueva conversación").strip()[:120] or "Nueva conversación"
    now = utc_now()

    with db_session() as conn:
        existing = conn.execute(
            "SELECT * FROM chat_sessions WHERE session_id = ? AND user_id = ?",
            (clean_session_id, user_id),
        ).fetchone()
        if existing:
            return clean_session_id

        collision = conn.execute("SELECT * FROM chat_sessions WHERE session_id = ?", (clean_session_id,)).fetchone()
        if collision:
            clean_session_id = str(uuid.uuid4())

        conn.execute(
            """
            INSERT INTO chat_sessions (user_id, session_id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, clean_session_id, clean_title, now, now),
        )
    return clean_session_id


def ensure_chat_session(user_id: int, session_id: str | None, title: str = "Nueva conversación") -> str:
    return create_chat_session(user_id, title=title, session_id=session_id)


def list_chat_sessions(user_id: int) -> list[dict[str, Any]]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, session_id, title, created_at, updated_at
            FROM chat_sessions
            WHERE user_id = ?
            ORDER BY datetime(updated_at) DESC
            """,
            (user_id,),
        ).fetchall()
    return rows_to_dicts(rows)


def add_chat_message(
    user_id: int,
    session_id: str,
    role: str,
    content: str,
    sources: list[dict[str, Any]] | None = None,
    mode: str | None = None,
) -> None:
    clean_role = str(role or "").strip().lower()
    if clean_role not in {"user", "assistant", "system"}:
        raise ValueError("role debe ser user, assistant o system")
    clean_content = str(content or "").strip()
    if not clean_content:
        return

    sources_json = json.dumps(sources or [], ensure_ascii=False)
    now = utc_now()
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO chat_messages (session_id, user_id, role, content, sources_json, mode, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, user_id, clean_role, clean_content, sources_json, mode, now),
        )
        if clean_role == "user":
            title = clean_content.replace("\n", " ").strip()
            if len(title) > 60:
                title = f"{title[:57].rstrip()}..."
            conn.execute(
                """
                UPDATE chat_sessions
                SET title = CASE WHEN title = 'Nueva conversación' THEN ? ELSE title END,
                    updated_at = ?
                WHERE user_id = ? AND session_id = ?
                """,
                (title or "Nueva conversación", now, user_id, session_id),
            )
        else:
            conn.execute(
                "UPDATE chat_sessions SET updated_at = ? WHERE user_id = ? AND session_id = ?",
                (now, user_id, session_id),
            )


def get_chat_history(user_id: int, session_id: str) -> list[dict[str, Any]]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT id, session_id, user_id, role, content, sources_json, mode, created_at
            FROM chat_messages
            WHERE user_id = ? AND session_id = ?
            ORDER BY datetime(created_at) ASC, id ASC
            """,
            (user_id, session_id),
        ).fetchall()

    messages = rows_to_dicts(rows)
    for message in messages:
        raw_sources = message.pop("sources_json", "") or "[]"
        try:
            message["sources"] = json.loads(raw_sources)
        except json.JSONDecodeError:
            message["sources"] = []
    return messages


def save_chat_exchange(
    user_id: int,
    session_id: str,
    message: str,
    answer: str,
    sources: list[dict[str, Any]] | None = None,
    mode: str | None = None,
) -> None:
    clean_session_id = ensure_chat_session(user_id, session_id)
    add_chat_message(user_id, clean_session_id, "user", message, mode=mode)
    add_chat_message(user_id, clean_session_id, "assistant", answer, sources=sources or [], mode=mode)
