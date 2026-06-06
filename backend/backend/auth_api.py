from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request, status

try:
    import httpx
except Exception:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

try:
    from .schemas import LoginPayload, PreferencesPayload, ProfilePayload, RegisterPayload
    from .security import bearer_token_from_header, decode_access_token
    from .services.auth_service import (
        authenticate_local_user,
        create_local_user,
        get_user_by_id,
        public_user,
        session_payload,
        update_user_profile,
        upsert_google_user,
    )
    from .services.history_service import save_chat_exchange
    from .services.user_service import get_preferences, update_preferences
except ImportError:  # pragma: no cover
    from schemas import LoginPayload, PreferencesPayload, ProfilePayload, RegisterPayload  # type: ignore
    from security import bearer_token_from_header, decode_access_token  # type: ignore
    from services.auth_service import (  # type: ignore
        authenticate_local_user,
        create_local_user,
        get_user_by_id,
        public_user,
        session_payload,
        update_user_profile,
        upsert_google_user,
    )
    from services.history_service import save_chat_exchange  # type: ignore
    from services.user_service import get_preferences, update_preferences  # type: ignore


auth_router = APIRouter()

GOOGLE_UNCONFIGURED_MESSAGE = (
    "Google Login todavia no esta configurado. Agrega GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET en el archivo .env."
)
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def current_user_from_authorization(authorization: str | None) -> dict[str, Any] | None:
    token = bearer_token_from_header(authorization)
    if not token:
        return None
    payload = decode_access_token(token)
    user = get_user_by_id(int(payload["sub"]))
    return public_user(user) if user else None


def require_user(request: Request) -> dict[str, Any]:
    user = current_user_from_authorization(request.headers.get("authorization"))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Debes iniciar sesion.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def save_chat_history(user_id: int, message: str, response: str) -> None:
    if not user_id or not message or not response:
        return
    save_chat_exchange(user_id, "legacy", message, response, sources=[], mode="chat")


def _env_enabled(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() not in {"0", "false", "no", "off", ""}


@auth_router.get("/api/auth/providers")
def auth_providers() -> dict[str, Any]:
    supabase_configured = bool(
        os.getenv("SUPABASE_URL", "").strip()
        and os.getenv("SUPABASE_ANON_KEY", "").strip()
    )
    google_configured = bool(
        _env_enabled("SUPABASE_GOOGLE_ENABLED", False)
        or (
            os.getenv("GOOGLE_CLIENT_ID", "").strip()
            and os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
        )
    )
    apple_configured = bool(
        _env_enabled("SUPABASE_APPLE_ENABLED", False)
        or os.getenv("APPLE_CLIENT_ID", "").strip()
    )
    return {
        "ok": True,
        "local": True,
        "email_password": True,
        "supabase": supabase_configured,
        "google": google_configured,
        "apple": apple_configured,
    }


@auth_router.post("/api/auth/register")
def register(payload: RegisterPayload) -> dict[str, Any]:
    user = create_local_user(payload.name, payload.email, payload.password)
    return session_payload(user)


@auth_router.post("/api/auth/login")
def login(payload: LoginPayload) -> dict[str, Any]:
    user = authenticate_local_user(payload.email, payload.password)
    return session_payload(user)


@auth_router.get("/api/auth/me")
def me(request: Request) -> dict[str, Any]:
    user = require_user(request)
    return {
        "ok": True,
        "user": user,
        "preferences": get_preferences(int(user["id"])),
    }


@auth_router.post("/api/auth/logout")
def logout() -> dict[str, Any]:
    return {"ok": True, "message": "Sesion cerrada."}


@auth_router.get("/api/auth/google/login")
def google_login() -> dict[str, Any]:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8787/api/auth/google/callback").strip()
    if not client_id or not client_secret:
        return {"ok": False, "configured": False, "message": GOOGLE_UNCONFIGURED_MESSAGE}

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    return {"ok": True, "configured": True, "auth_url": f"{GOOGLE_AUTH_URL}?{urlencode(params)}"}


@auth_router.get("/api/auth/google/callback")
async def google_callback(code: str | None = None) -> dict[str, Any]:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8787/api/auth/google/callback").strip()
    if not client_id or not client_secret:
        return {"ok": False, "configured": False, "message": GOOGLE_UNCONFIGURED_MESSAGE}
    if not code:
        raise HTTPException(status_code=400, detail="Falta el codigo de Google.")
    if httpx is None:
        raise HTTPException(status_code=500, detail="Instala httpx para completar Google OAuth.")

    async with httpx.AsyncClient(timeout=20) as client:
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_response.raise_for_status()
        access_token = token_response.json().get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="Google no devolvio access_token.")
        profile_response = await client.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        profile_response.raise_for_status()
        profile = profile_response.json()

    user = upsert_google_user(profile)
    return session_payload(user)


@auth_router.get("/api/user/profile")
def profile(request: Request) -> dict[str, Any]:
    user = require_user(request)
    return {"ok": True, "user": user}


@auth_router.put("/api/user/profile")
def put_profile(payload: ProfilePayload, request: Request) -> dict[str, Any]:
    user = require_user(request)
    updated = update_user_profile(int(user["id"]), payload.name)
    return {"ok": True, "user": updated}


@auth_router.get("/api/user/preferences")
def user_preferences(request: Request) -> dict[str, Any]:
    user = require_user(request)
    return {"ok": True, "preferences": get_preferences(int(user["id"]))}


@auth_router.put("/api/user/preferences")
def put_user_preferences(payload: PreferencesPayload, request: Request) -> dict[str, Any]:
    user = require_user(request)
    preferences = update_preferences(int(user["id"]), payload.model_dump(exclude_unset=True))
    return {"ok": True, "preferences": preferences}
