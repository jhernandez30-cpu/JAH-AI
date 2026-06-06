from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException

try:
    from ..database import db_session, row_to_dict
    from ..security import create_access_token, hash_password, utc_now, verify_password
    from .history_service import create_chat_session
    from .user_service import get_preferences
except ImportError:  # pragma: no cover
    from database import db_session, row_to_dict  # type: ignore
    from security import create_access_token, hash_password, utc_now, verify_password  # type: ignore
    from services.history_service import create_chat_session  # type: ignore
    from services.user_service import get_preferences  # type: ignore


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def validate_email(email: str) -> bool:
    return bool(EMAIL_RE.fullmatch(normalize_email(email)))


def public_user(row: Any) -> dict[str, Any]:
    data = row_to_dict(row) or {}
    return {
        "id": data.get("id"),
        "name": data.get("name") or "",
        "email": data.get("email") or "",
        "google_id": data.get("google_id") or "",
        "auth_provider": data.get("auth_provider") or "local",
        "avatar_url": data.get("avatar_url") or "",
        "created_at": data.get("created_at") or "",
        "updated_at": data.get("updated_at") or "",
        "last_login": data.get("last_login") or "",
        "plan": "Gratis",
    }


def get_user_by_email(email: str) -> dict[str, Any] | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (normalize_email(email),)).fetchone()
        return row_to_dict(row)


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return row_to_dict(row)


def get_user_by_google_id(google_id: str) -> dict[str, Any] | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM users WHERE google_id = ?", (google_id,)).fetchone()
        return row_to_dict(row)


def create_local_user(name: str, email: str, password: str) -> dict[str, Any]:
    clean_name = str(name or "").strip()
    clean_email = normalize_email(email)
    if not clean_name:
        raise HTTPException(status_code=400, detail="El nombre es obligatorio.")
    if not validate_email(clean_email):
        raise HTTPException(status_code=400, detail="El correo electronico no es valido.")
    if len(password or "") < 8:
        raise HTTPException(status_code=400, detail="La contrasena debe tener minimo 8 caracteres.")
    if get_user_by_email(clean_email):
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese correo.")

    now = utc_now()
    with db_session() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users
            (name, email, password_hash, auth_provider, created_at, updated_at, last_login)
            VALUES (?, ?, ?, 'local', ?, ?, ?)
            """,
            (clean_name, clean_email, hash_password(password), now, now, now),
        )
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    user = row_to_dict(row) or {}
    get_preferences(int(user["id"]))
    return user


def authenticate_local_user(email: str, password: str) -> dict[str, Any]:
    clean_email = normalize_email(email)
    if not validate_email(clean_email):
        raise HTTPException(status_code=400, detail="El correo electronico no es valido.")
    user = get_user_by_email(clean_email)
    if not user or not verify_password(password or "", user.get("password_hash")):
        raise HTTPException(status_code=401, detail="Correo o contrasena incorrectos.")
    now = utc_now()
    with db_session() as conn:
        conn.execute("UPDATE users SET last_login = ?, updated_at = ? WHERE id = ?", (now, now, int(user["id"])))
        row = conn.execute("SELECT * FROM users WHERE id = ?", (int(user["id"]),)).fetchone()
    return row_to_dict(row) or user


def upsert_google_user(profile: dict[str, Any]) -> dict[str, Any]:
    email = normalize_email(str(profile.get("email") or ""))
    google_id = str(profile.get("sub") or profile.get("id") or profile.get("google_id") or "").strip()
    if not validate_email(email) or not google_id:
        raise HTTPException(status_code=400, detail="Google no devolvio un perfil valido.")

    name = str(profile.get("name") or email.split("@")[0]).strip()
    avatar_url = str(profile.get("picture") or profile.get("avatar_url") or "").strip()
    now = utc_now()
    existing = get_user_by_email(email) or get_user_by_google_id(google_id)

    with db_session() as conn:
        if existing:
            conn.execute(
                """
                UPDATE users
                SET name = COALESCE(NULLIF(?, ''), name),
                    google_id = COALESCE(NULLIF(?, ''), google_id),
                    auth_provider = 'google',
                    avatar_url = ?,
                    updated_at = ?,
                    last_login = ?
                WHERE id = ?
                """,
                (name, google_id, avatar_url, now, now, int(existing["id"])),
            )
            row = conn.execute("SELECT * FROM users WHERE id = ?", (int(existing["id"]),)).fetchone()
        else:
            cursor = conn.execute(
                """
                INSERT INTO users
                (name, email, google_id, auth_provider, avatar_url, created_at, updated_at, last_login)
                VALUES (?, ?, ?, 'google', ?, ?, ?, ?)
                """,
                (name, email, google_id, avatar_url, now, now, now),
            )
            row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    user = row_to_dict(row) or {}
    get_preferences(int(user["id"]))
    return user


def update_user_profile(user_id: int, name: str) -> dict[str, Any]:
    clean_name = str(name or "").strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="El nombre es obligatorio.")
    now = utc_now()
    with db_session() as conn:
        conn.execute("UPDATE users SET name = ?, updated_at = ? WHERE id = ?", (clean_name, now, user_id))
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return public_user(row)


def session_payload(user: dict[str, Any], session_id: str | None = None) -> dict[str, Any]:
    public = public_user(user)
    token = create_access_token(public)
    active_session_id = create_chat_session(int(public["id"]), title="Nueva conversación", session_id=session_id)
    return {
        "ok": True,
        "token": token,
        "access_token": token,
        "token_type": "bearer",
        "user": public,
        "preferences": get_preferences(int(public["id"])),
        "session_id": active_session_id,
    }
