from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status

try:
    from jose import JWTError, jwt
except Exception:  # pragma: no cover - fallback for local envs before pip install
    JWTError = Exception
    jwt = None  # type: ignore[assignment]

try:
    from passlib.context import CryptContext
except Exception:  # pragma: no cover
    CryptContext = None  # type: ignore[assignment]

try:
    import bcrypt
except Exception:  # pragma: no cover
    bcrypt = None  # type: ignore[assignment]


_ENVIRONMENT = (os.getenv("ENVIRONMENT") or os.getenv("RAILWAY_ENVIRONMENT") or "development").strip().lower()
JWT_SECRET = (os.getenv("TUTOR_IA_JWT_SECRET") or "").strip()
JWT_SECRET_CONFIGURED = bool(JWT_SECRET)
if not JWT_SECRET:
    JWT_SECRET = "local-dev-token-key-jah-ai" if _ENVIRONMENT != "production" else "unconfigured-production-token-key-jah-ai"
JWT_ALGORITHM = os.getenv("TUTOR_IA_JWT_ALGORITHM", "HS256")
JWT_EXPIRES_MINUTES = int(os.getenv("TUTOR_IA_JWT_EXPIRES_MINUTES", str(60 * 24 * 7)))
JWT_ISSUER = os.getenv("TUTOR_IA_JWT_ISSUER", "tutor_ia")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto") if CryptContext else None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def hash_password(password: str) -> str:
    if pwd_context:
        return pwd_context.hash(password)
    if not bcrypt:
        raise RuntimeError("Instala passlib[bcrypt] o bcrypt para cifrar contrasenas.")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password or not password_hash:
        return False
    try:
        if pwd_context:
            return bool(pwd_context.verify(password, password_hash))
        if not bcrypt:
            return False
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def _fallback_encode(payload: dict[str, Any]) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    encoded_header = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{encoded_header}.{encoded_payload}.{_b64url_encode(signature)}"


def _fallback_decode(token: str) -> dict[str, Any]:
    header_part, payload_part, signature_part = token.split(".", 2)
    signing_input = f"{header_part}.{payload_part}".encode("ascii")
    expected = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    provided = _b64url_decode(signature_part)
    if not hmac.compare_digest(expected, provided):
        raise ValueError("Firma invalida")
    payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
    if payload.get("iss") != JWT_ISSUER:
        raise ValueError("Emisor invalido")
    if int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("Token vencido")
    return payload


def _require_jwt_secret() -> None:
    if _ENVIRONMENT == "production" and not JWT_SECRET_CONFIGURED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autenticacion local no configurada. Define TUTOR_IA_JWT_SECRET en Railway o usa Supabase Auth.",
        )


def create_access_token(user: dict[str, Any]) -> str:
    _require_jwt_secret()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=JWT_EXPIRES_MINUTES)
    payload = {
        "iss": JWT_ISSUER,
        "sub": str(user["id"]),
        "email": user["email"],
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    if jwt:
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return _fallback_encode(payload)


def decode_access_token(token: str) -> dict[str, Any]:
    _require_jwt_secret()
    try:
        if jwt:
            payload = jwt.decode(
                token,
                JWT_SECRET,
                algorithms=[JWT_ALGORITHM],
                issuer=JWT_ISSUER,
                options={"verify_aud": False},
            )
        else:
            payload = _fallback_decode(token)
        return dict(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion invalida o vencida.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def bearer_token_from_header(authorization: str | None) -> str:
    if not authorization:
        return ""
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return ""
    return parts[1].strip()
