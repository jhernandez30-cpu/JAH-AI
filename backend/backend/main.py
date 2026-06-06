from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore[assignment]

if load_dotenv:
    BACKEND_DIR = Path(__file__).resolve().parent
    load_dotenv(BACKEND_DIR / ".env")
    load_dotenv(BACKEND_DIR.parent / ".env")

try:
    from . import web_bridge
    from .auth_api import auth_router, current_user_from_authorization, save_chat_history
    from .rag.rag_chain import query_rag
    from .services.file_service import list_uploaded_files, record_uploaded_file, save_uploaded_bytes
    from .services.llm_orchestrator import get_orchestrator
    from .services.history_service import add_chat_message, create_chat_session, ensure_chat_session, get_chat_history, list_chat_sessions
    from .services.jarvis_service import get_jarvis_status, launch_mark_xxxix, mark_xxxix_status, read_mark_log
    from .services.web_search import WEB_SEARCH_UNCONFIGURED_MESSAGE, search_web, web_search_configured
except ImportError:  # pragma: no cover - allows running from backend/ directly
    import web_bridge  # type: ignore
    from auth_api import auth_router, current_user_from_authorization, save_chat_history  # type: ignore
    from rag.rag_chain import query_rag  # type: ignore
    from services.file_service import list_uploaded_files, record_uploaded_file, save_uploaded_bytes  # type: ignore
    from services.llm_orchestrator import get_orchestrator  # type: ignore
    from services.history_service import add_chat_message, create_chat_session, ensure_chat_session, get_chat_history, list_chat_sessions  # type: ignore
    from services.jarvis_service import get_jarvis_status, launch_mark_xxxix, mark_xxxix_status, read_mark_log  # type: ignore
    from services.web_search import WEB_SEARCH_UNCONFIGURED_MESSAGE, search_web, web_search_configured  # type: ignore


app = FastAPI(
    title="JAH AI Bridge",
    description="API local para el cerebro JAH AI / TUTOR_IA.",
    version="0.1.0",
)


def _csv_env(name: str) -> list[str]:
    raw = os.getenv(name, "")
    return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]


def _runtime_environment() -> str:
    return (
        os.getenv("ENVIRONMENT")
        or os.getenv("RAILWAY_ENVIRONMENT")
        or os.getenv("RAILWAY_ENVIRONMENT_NAME")
        or "development"
    ).strip().lower()


def _cors_allowed_origins() -> list[str]:
    origins = _csv_env("CORS_ALLOWED_ORIGINS")
    frontend_url = os.getenv("FRONTEND_URL", "").strip().rstrip("/")
    if frontend_url:
        origins.append(frontend_url)
    if _runtime_environment() != "production":
        origins.extend(
            [
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:5500",
                "http://127.0.0.1:5500",
                "http://localhost:8787",
                "http://127.0.0.1:8787",
                "null",
            ]
        )
    return list(dict.fromkeys(origin for origin in origins if origin))


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allowed_origins(),
    allow_origin_regex=os.getenv("CORS_ALLOWED_ORIGIN_REGEX", "").strip() or None,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Session-Id"],
)

app.include_router(auth_router)
DEFAULT_CHAT_RESPONSE_TIMEOUT_SECONDS = 45.0
try:
    # Import the APIRouter object explicitly from the odysseus submodule
    from .odysseus.router import router as odysseus_router
    app.include_router(odysseus_router)
except Exception:
    # If adapter not available, skip silently
    pass


# Backwards-compatible upload endpoint used by some frontends / integrations.
try:
    # prefer odysseus storage when available (session-based, safer)
    from .odysseus import storage as _odysseus_storage  # type: ignore
except Exception:
    _odysseus_storage = None  # type: ignore


@app.post("/api/upload")
async def api_upload(request: Request) -> dict[str, Any]:
    """Store one or more files safely and return only relative upload tokens."""
    user = _optional_auth_user(request)
    session_id = request.headers.get("x-session-id") or (str(user["id"]) if user else "guest")
    form = await request.form()
    upload_files: list[Any] = [
        value for _, value in form.multi_items()
        if hasattr(value, "filename") and hasattr(value, "read")
    ]
    if not upload_files:
        raise HTTPException(status_code=400, detail="No se proporciono archivo.")

    saved_files: list[dict[str, Any]] = []
    indexed_total = 0
    for upload_file in upload_files:
        content = await upload_file.read()
        filename = getattr(upload_file, "filename", None)
        content_type = getattr(upload_file, "content_type", None)
        if _odysseus_storage:
            try:
                saved = _odysseus_storage.save_file_details(filename, content, session_id=session_id)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        else:
            try:
                fallback = await run_in_threadpool(
                    save_uploaded_bytes,
                    filename,
                    content,
                    content_type,
                    8 * 1024 * 1024,
                )
                saved = {
                    "ok": True,
                    "name": fallback.get("filename") or filename,
                    "relative_path": fallback.get("filename") or filename,
                    "path": fallback.get("filename") or filename,
                    "size": fallback.get("file_size") or len(content),
                    "content_type": fallback.get("file_type") or content_type,
                }
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            normalized_upload = web_bridge.normalize_uploaded_file(filename, content_type, content)
            indexed_chunks = await run_in_threadpool(web_bridge.index_uploaded_files, [normalized_upload], session_id)
            indexed_total += int(indexed_chunks or 0)
        except Exception:
            indexed_chunks = 0

        if user and not _odysseus_storage:
            try:
                file_info = {
                    "filename": saved.get("name"),
                    "original_filename": filename,
                    "file_path": saved.get("relative_path"),
                    "file_size": saved.get("size"),
                    "file_type": saved.get("content_type"),
                }
                saved["record"] = await run_in_threadpool(record_uploaded_file, int(user["id"]), file_info, indexed_chunks > 0)
            except Exception:
                saved["record"] = None

        saved["indexed"] = indexed_chunks > 0
        saved["indexed_chunks"] = int(indexed_chunks or 0)
        saved_files.append(saved)

    first = saved_files[0]
    return {
        "ok": True,
        "files": saved_files,
        "count": len(saved_files),
        "filename": first.get("name"),
        "original_filename": upload_files[0].filename,
        "relative_path": first.get("relative_path"),
        "path": first.get("relative_path"),
        "size": first.get("size"),
        "content_type": first.get("content_type"),
        "indexed": indexed_total > 0,
        "indexed_chunks": indexed_total,
        "message": "Archivo cargado correctamente al cerebro tutor_ia y Odysseus.",
    }

frontend_history_store: dict[str, list[dict[str, Any]]] = {}
frontend_collection_store: dict[str, dict[str, list[dict[str, Any]]]] = {
    "spaces": {},
    "projects": {},
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_configured(*names: str) -> bool:
    return all(bool(os.getenv(name, "").strip()) for name in names)


def _database_state() -> tuple[str, bool, bool, str]:
    """Return (label, configured, connected, error_message).

    Attempts a real TCP-level connection to the PostgreSQL DATABASE_URL so
    /api/health can report 'connected' vs 'connection_error' instead of the
    vague 'configured_not_checked'.  Falls back gracefully: if neither
    psycopg2 nor sqlalchemy is installed the function returns
    'configured_not_checked' without crashing the service.
    """
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        return "not_configured", False, False, ""

    # --- try psycopg2 first (lightweight, no ORM overhead) ---
    try:
        import psycopg2  # type: ignore
        conn = psycopg2.connect(db_url, connect_timeout=5)
        conn.close()
        return "connected", True, True, ""
    except ImportError:
        pass  # psycopg2 not installed, try next
    except Exception as exc:
        return "connection_error", True, False, str(exc)

    # --- fallback: sqlalchemy create_engine + connect ---
    try:
        from sqlalchemy import create_engine, text  # type: ignore
        engine = create_engine(db_url, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "connected", True, True, ""
    except ImportError:
        pass  # sqlalchemy not installed either
    except Exception as exc:
        return "connection_error", True, False, str(exc)

    # Neither driver is available — report URL is set but we can't verify
    return "configured_not_checked", True, False, "psycopg2/sqlalchemy not available"


def _health_payload() -> dict[str, Any]:
    fragments = 0
    brain_error = ""
    try:
        fragments = web_bridge.get_collection().count()
    except Exception as exc:
        brain_error = str(exc)

    tutor_connected = fragments > 0 and not brain_error
    tutor_status = "CONNECTED" if tutor_connected else "DEGRADED"
    supabase_configured = _env_configured("SUPABASE_URL", "SUPABASE_ANON_KEY")
    database_label, database_configured, database_connected, db_error = _database_state()
    cors_origins = _cors_allowed_origins()
    llm_status = get_orchestrator().status()
    odysseus_info: dict[str, Any] = {"ok": False, "odysseus": "unavailable", "llm": llm_status}
    try:
        try:
            from .odysseus.service import odysseus_status
        except ImportError:  # pragma: no cover
            from odysseus.service import odysseus_status  # type: ignore
        odysseus_info = odysseus_status()
    except Exception as exc:
        odysseus_info["error"] = str(exc)[:200]

    payload: dict[str, Any] = {
        "ok": True,
        "success": True,
        "status": "ok",
        "message": "JAH AI Bridge disponible",
        "service": "jah-ai-bridge",
        "name": "JAH AI Bridge",
        "backend": "available",
        "tutor_ia": "ready" if tutor_connected else "degraded",
        "tutor_ia_status": tutor_status,
        "tutor_ia_connected": tutor_connected,
        "supabase": "configured" if supabase_configured else "not_configured",
        "supabase_configured": supabase_configured,
        "supabase_auth_configured": supabase_configured,
        "database": database_label,
        "database_configured": database_configured,
        "database_connected": database_connected,
        "cors": "configured",
        "cors_allowed_origins": cors_origins,
        "llm": llm_status,
        "odysseus": odysseus_info.get("odysseus", "unavailable"),
        "odysseus_status": odysseus_info,
        "mode": "fastapi-ubuntu-compatible",
        "root_dir": str(web_bridge.TUTOR_ROOT),
        "persist_dir": str(web_bridge.PERSIST_DIR),
        "knowledge_dir": str(web_bridge.OBSIDIAN_VAULT_DIR),
        "fragments": fragments,
        "brain_error": brain_error,
        "jarvis": get_jarvis_status(),
    }
    # Only include db_error when present (avoid leaking connection strings)
    if db_error:
        payload["database_error"] = db_error[:200]
    return payload


async def _payload_and_uploads(request: Request) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    content_type = request.headers.get("content-type", "").lower()
    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        payload: dict[str, Any] = {}
        uploaded_files: list[dict[str, Any]] = []
        for key, value in form.multi_items():
            if hasattr(value, "filename") and hasattr(value, "read"):
                file = value
                content = await file.read()
                uploaded_files.append(
                    web_bridge.normalize_uploaded_file(file.filename, file.content_type, content)
                )
            else:
                payload[key] = str(value)
        return payload, uploaded_files

    if "application/json" in content_type:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="El cuerpo JSON debe ser un objeto.")
        return payload, []

    raw = await request.body()
    if not raw:
        return {}, []
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Envia JSON o form-data valido.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="El cuerpo JSON debe ser un objeto.")
    return payload, []


def _optional_auth_user(request: Request) -> dict[str, Any] | None:
    try:
        return current_user_from_authorization(request.headers.get("authorization"))
    except HTTPException:
        return None


def _frontend_owner_key(request: Request) -> str:
    user = _optional_auth_user(request)
    if user and user.get("id"):
        return f"user:{user['id']}"
    return "guest"


def _collection_items(kind: str, owner_key: str) -> list[dict[str, Any]]:
    return frontend_collection_store.setdefault(kind, {}).setdefault(owner_key, [])


def _normalize_collection_item(payload: dict[str, Any]) -> dict[str, Any]:
    now = _utc_now()
    item_id = str(payload.get("id") or uuid.uuid4())
    name = str(payload.get("name") or payload.get("title") or "Sin nombre").strip() or "Sin nombre"
    chat_ids = payload.get("chatIds") if isinstance(payload.get("chatIds"), list) else payload.get("chat_ids")
    return {
        **payload,
        "id": item_id,
        "name": name,
        "description": str(payload.get("description") or "").strip(),
        "chatIds": chat_ids if isinstance(chat_ids, list) else [],
        "createdAt": str(payload.get("createdAt") or payload.get("created_at") or now),
        "updatedAt": now,
    }


def _upsert_collection_item(kind: str, owner_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    item = _normalize_collection_item(payload)
    items = _collection_items(kind, owner_key)
    for index, existing in enumerate(items):
        if existing.get("id") == item["id"]:
            items[index] = {**existing, **item}
            return items[index]
    items.insert(0, item)
    return item


def _require_auth_user(request: Request) -> dict[str, Any]:
    user = _optional_auth_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Debes iniciar sesion.")
    return user


def _payload_bool(payload: dict[str, Any], key: str, default: bool = False) -> bool:
    if key not in payload:
        return default
    value = payload.get(key)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off", ""}


def _message_from_payload(payload: dict[str, Any]) -> str:
    return str(payload.get("message") or payload.get("question") or "").strip()


def _answer_from_result(result: dict[str, Any]) -> str:
    return str(result.get("answer") or result.get("response") or result.get("message") or "").strip()


def _chat_timeout_seconds(payload: dict[str, Any]) -> float:
    raw = payload.get("backend_timeout_seconds") or os.getenv(
        "CHAT_RESPONSE_TIMEOUT_SECONDS",
        str(DEFAULT_CHAT_RESPONSE_TIMEOUT_SECONDS),
    )
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = DEFAULT_CHAT_RESPONSE_TIMEOUT_SECONDS
    return max(5.0, min(value, 120.0))


def _chat_timeout_response(payload: dict[str, Any], message: str, timeout_seconds: float) -> dict[str, Any]:
    answer = (
        "JAH AI recibio tu mensaje, pero el motor principal tardo demasiado en responder "
        f"({int(timeout_seconds)}s). El chat sigue listo; intenta una pregunta mas concreta, "
        "desactiva pensamiento profundo o revisa el proveedor IA/Ollama si vuelve a ocurrir."
    )
    return {
        "ok": False,
        "success": False,
        "answer": answer,
        "response": answer,
        "error": answer,
        "code": "CHAT_TIMEOUT_RECOVERY",
        "service": "jah-ai-bridge",
        "session_id": str(payload.get("session_id") or "default"),
        "sources": [],
        "mode": payload.get("mode") or "chat",
        "message": message,
    }


def _attach_user_context(payload: dict[str, Any], user: dict[str, Any] | None) -> None:
    if not user:
        return
    payload.setdefault("user_id", str(user["id"]))
    payload.setdefault("user_email", user["email"])
    payload.setdefault("user_name", user["name"])


def _normalize_chat_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    use_rag = _payload_bool(normalized, "use_rag", _payload_bool(normalized, "tutorIA", True))
    use_web = _payload_bool(normalized, "use_web", _payload_bool(normalized, "smartSearch", False))
    deep_thinking = _payload_bool(normalized, "deep_thinking", use_rag)
    use_jarvis = _payload_bool(normalized, "use_jarvis", _payload_bool(normalized, "jarvis_voice", False))

    normalized["tutorIA"] = use_rag
    normalized["tutor_ia"] = use_rag
    normalized["smartSearch"] = use_web
    normalized["smart_search"] = use_web
    normalized["deep_thinking"] = deep_thinking
    normalized["use_jarvis"] = use_jarvis
    normalized["jarvis_voice"] = use_jarvis
    normalized["fast_mode"] = not deep_thinking
    normalized.setdefault("response_profile", "balanced" if deep_thinking else "web_fast")
    normalized.setdefault("mode", "Cerebro Unificado")
    normalized.setdefault("client", "abraham-programming-assistant")
    normalized.setdefault("include_obsidian", use_rag)
    normalized.setdefault("agency_enabled", use_rag)
    normalized.setdefault("show_sources", use_rag)
    normalized.setdefault("k", 4)
    normalized.setdefault("top_k", 3 if use_rag else 1)
    normalized.setdefault("obsidian_top_k", 2 if use_rag else 1)
    normalized.setdefault("jarvis_profile", "unified")
    normalized.setdefault("session_id", "default")
    return normalized


def _title_from_message(message: str) -> str:
    clean = " ".join(str(message or "").split())
    if not clean:
        return "Nueva conversación"
    return clean[:57].rstrip() + "..." if len(clean) > 60 else clean


def _web_context_from_results(results: list[dict[str, Any]]) -> str:
    if not results:
        return ""
    lines = [
        "Resultados de Busqueda inteligente. Usa primero documentos locales y complementa con web cuando haga falta."
    ]
    for index, item in enumerate(results[:5], start=1):
        title = str(item.get("title") or "Resultado web").strip()
        url = str(item.get("url") or "").strip()
        snippet = str(item.get("snippet") or "").strip()
        lines.append(f"{index}. {title}\nURL: {url}\nResumen: {snippet}")
    return "\n\n".join(lines)


async def _prepare_web_search(payload: dict[str, Any], message: str) -> tuple[list[dict[str, Any]], str]:
    requested = _payload_bool(payload, "use_web", _payload_bool(payload, "smartSearch", False))
    payload["_use_web_requested"] = requested
    if not requested:
        return [], ""

    results = await search_web(message, max_results=int(payload.get("web_top_k") or 5))
    if results:
        current_context = str(payload.get("quick_code_context") or payload.get("code_context") or "").strip()
        web_context = _web_context_from_results(results)
        payload["quick_code_context"] = "\n\n".join(part for part in [current_context, web_context] if part)
        payload["smartSearch"] = False
        payload["smart_search"] = False
        return results, ""

    payload["smartSearch"] = False
    payload["smart_search"] = False
    if not web_search_configured():
        return [], WEB_SEARCH_UNCONFIGURED_MESSAGE
    return [], "La Busqueda inteligente no encontro resultados suficientes para complementar esta respuesta."


def _source_file(metadata: dict[str, Any]) -> str:
    raw_source = str(metadata.get("source") or metadata.get("title") or "documento")
    if raw_source.startswith("upload:"):
        raw_source = raw_source.replace("upload:", "", 1)
    return Path(raw_source.replace("\\", "/")).name or raw_source


def _normalize_sources(sources: Any) -> list[dict[str, Any]]:
    normalized_sources: list[dict[str, Any]] = []
    if not isinstance(sources, list):
        return normalized_sources
    for source in sources[:4]:
        if not isinstance(source, dict):
            continue
        if source.get("type") == "web" or source.get("source") == "web":
            normalized_sources.append(
                {
                    "type": "web",
                    "title": source.get("title") or source.get("file") or "Resultado web",
                    "url": source.get("url") or "",
                    "chunk": source.get("chunk") or source.get("snippet") or "",
                    "score": source.get("score") if source.get("score") is not None else source.get("relevance", ""),
                }
            )
            continue
        metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
        normalized_sources.append(
            {
                "type": source.get("type") or "local",
                "file": source.get("file") or _source_file(metadata),
                "chunk": source.get("chunk") or source.get("snippet") or source.get("text") or "",
                "score": source.get("score") if source.get("score") is not None else source.get("relevance", ""),
            }
        )
    return normalized_sources


def _web_sources(web_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "web",
            "title": item.get("title") or "Resultado web",
            "url": item.get("url") or "",
            "chunk": item.get("snippet") or "",
            "score": item.get("score", ""),
        }
        for item in web_results[:3]
    ]


def _chat_response(
    payload: dict[str, Any],
    result: dict[str, Any],
    web_results: list[dict[str, Any]] | None = None,
    web_notice: str = "",
) -> dict[str, Any]:
    use_rag = _payload_bool(payload, "use_rag", _payload_bool(payload, "tutorIA", True))
    use_web = bool(payload.get("_use_web_requested"))
    response = dict(result)
    answer = _answer_from_result(result)
    if web_notice and web_notice not in answer:
        answer = f"{answer}\n\n{web_notice}" if answer else web_notice
    sources = _normalize_sources(result.get("sources", [])) + _web_sources(web_results or [])
    response["answer"] = answer
    response["sources"] = sources[:6]
    response["mode"] = "rag+web" if use_rag and use_web else ("web" if use_web else (result.get("mode") or ("rag" if use_rag else "chat")))
    response["session_id"] = str(payload.get("session_id") or "default")
    response["web_search"] = {
        "requested": use_web,
        "configured": web_search_configured(),
        "results_count": len(web_results or []),
    }
    response["use_jarvis"] = _payload_bool(payload, "use_jarvis", False)
    response["jarvis"] = {
        "provider": "browser",
        "advanced_configured": False,
    }
    return response


def _store_chat_history_if_needed(payload: dict[str, Any], result: dict[str, Any], user: dict[str, Any] | None) -> None:
    if not user or not _payload_bool(payload, "chat_history_enabled", True):
        return
    message = _message_from_payload(payload)
    answer = _answer_from_result(result)
    save_chat_history(int(user["id"]), message, answer)


@app.get("/api/health")
@app.get("/health")
async def health() -> dict[str, Any]:
    return _health_payload()


@app.get("/api/status")
@app.get("/status")
async def status() -> dict[str, Any]:
    return {
        "ok": True,
        "success": True,
        "health": _health_payload(),
        "brain": await run_in_threadpool(web_bridge.unified_brain_status_payload),
    }


@app.get("/api/jarvis/health")
async def jarvis_health() -> dict[str, Any]:
    return get_jarvis_status()


@app.get("/api/jarvis/mark/status")
async def jarvis_mark_status() -> dict[str, Any]:
    return {"ok": True, "mark_xxxix": mark_xxxix_status(include_audio=True)}


@app.post("/api/jarvis/mark/launch")
async def jarvis_mark_launch() -> dict[str, Any]:
    return launch_mark_xxxix()


@app.get("/api/jarvis/mark/log")
async def jarvis_mark_log() -> dict[str, Any]:
    return read_mark_log()


@app.get("/api/sources")
async def sources() -> dict[str, Any]:
    status_payload = await run_in_threadpool(web_bridge.unified_brain_status_payload)
    knowledge_dir = Path(web_bridge.OBSIDIAN_VAULT_DIR)
    files = []
    if knowledge_dir.exists():
        for path in sorted(knowledge_dir.rglob("*")):
            if path.is_file():
                files.append(
                    {
                        "name": path.name,
                        "path": str(path),
                        "relative_path": path.relative_to(knowledge_dir).as_posix(),
                        "extension": path.suffix.lower(),
                        "size": path.stat().st_size,
                    }
                )
    return {
        "ok": True,
        "root": str(knowledge_dir),
        "count": len(files),
        "files": files,
        "brain": status_payload,
    }


@app.post("/api/search")
async def search(payload: dict[str, Any]) -> dict[str, Any]:
    query = str(payload.get("query") or payload.get("message") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Falta el campo query.")
    k = int(payload.get("k") or payload.get("top_k") or web_bridge.RESPONSE_TOP_K)
    docs = await run_in_threadpool(web_bridge.retrieve, query, ["admin", "public"], None, k)
    results = [
        {
            "source": item.get("metadata", {}).get("source", ""),
            "title": item.get("metadata", {}).get("title", ""),
            "type": item.get("metadata", {}).get("type", "document"),
            "text": item.get("text", ""),
            "metadata": item.get("metadata", {}),
        }
        for item in docs
    ]
    return {"ok": True, "query": query, "results": results, "count": len(results)}


@app.post("/api/rag/query")
async def rag_query(payload: dict[str, Any]) -> dict[str, Any]:
    message = str(payload.get("message") or payload.get("question") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Falta el campo message.")
    top_k = int(payload.get("top_k") or payload.get("k") or 4)
    return await run_in_threadpool(query_rag, message, top_k)


@app.post("/api/chat")
@app.post("/api/ask")
@app.post("/ask")
async def chat(request: Request) -> dict[str, Any]:
    user = _optional_auth_user(request)
    payload, uploaded_files = await _payload_and_uploads(request)
    payload = _normalize_chat_payload(payload)
    message = _message_from_payload(payload)
    if not message:
        raise HTTPException(status_code=400, detail="Falta el campo message.")

    _attach_user_context(payload, user)
    if user:
        session_id = ensure_chat_session(int(user["id"]), str(payload.get("session_id") or ""), title=_title_from_message(message))
        payload["session_id"] = session_id
        if _payload_bool(payload, "chat_history_enabled", True):
            await run_in_threadpool(
                add_chat_message,
                int(user["id"]),
                session_id,
                "user",
                message,
                None,
                payload.get("mode"),
            )

    try:
        web_results, web_notice = await _prepare_web_search(payload, message)
    except Exception as exc:
        web_results = []
        web_notice = f"Busqueda inteligente no disponible temporalmente: {exc}"
    chat_timeout = _chat_timeout_seconds(payload)
    use_rag = _payload_bool(payload, "use_rag", _payload_bool(payload, "tutorIA", True))
    use_web = _payload_bool(payload, "use_web", _payload_bool(payload, "smartSearch", False))
    if not use_rag and not use_web and not uploaded_files:
        try:
            orchestrator = get_orchestrator()
            if orchestrator.is_configured():
                llm_result = await asyncio.wait_for(
                    run_in_threadpool(
                        orchestrator.generate,
                        message,
                        None,
                        {
                            "timeout": min(chat_timeout, 30.0),
                            "max_tokens": 700,
                        },
                    ),
                    timeout=min(chat_timeout, 35.0),
                )
                if llm_result.get("success") and _answer_from_result(llm_result):
                    response = _chat_response(
                        payload,
                        {
                            "ok": True,
                            "success": True,
                            "answer": _answer_from_result(llm_result),
                            "mode": "chat",
                            "sources": [],
                            "llm": llm_result,
                        },
                        web_results=web_results,
                        web_notice=web_notice,
                    )
                    if user and _payload_bool(payload, "chat_history_enabled", True):
                        await run_in_threadpool(
                            add_chat_message,
                            int(user["id"]),
                            str(response.get("session_id") or payload.get("session_id") or "default"),
                            "assistant",
                            _answer_from_result(response),
                            response.get("sources") if isinstance(response.get("sources"), list) else [],
                            response.get("mode"),
                        )
                    return response
        except Exception:
            pass
    try:
        result = await asyncio.wait_for(
            run_in_threadpool(web_bridge.answer_from_brain, payload, uploaded_files),
            timeout=chat_timeout,
        )
    except asyncio.TimeoutError:
        response = _chat_timeout_response(payload, message, chat_timeout)
        if user and _payload_bool(payload, "chat_history_enabled", True):
            await run_in_threadpool(
                add_chat_message,
                int(user["id"]),
                str(response["session_id"]),
                "assistant",
                _answer_from_result(response),
                [],
                response.get("mode"),
            )
        return response
    except Exception as exc:
        answer = (
            "El backend jah-ai-bridge recibio el mensaje, pero tutor_ia o el proveedor IA "
            f"no esta disponible ahora. Detalle: {exc}"
        )
        response = {
            "ok": False,
            "success": False,
            "answer": answer,
            "error": answer,
            "code": "TUTOR_IA_PROVIDER_UNAVAILABLE",
            "service": "jah-ai-bridge",
            "session_id": str(payload.get("session_id") or "default"),
            "sources": [],
            "mode": payload.get("mode") or "chat",
        }
        if user and _payload_bool(payload, "chat_history_enabled", True):
            await run_in_threadpool(
                add_chat_message,
                int(user["id"]),
                str(response["session_id"]),
                "assistant",
                answer,
                [],
                response.get("mode"),
            )
        return response
    response = _chat_response(payload, result, web_results=web_results, web_notice=web_notice)
    if user and _payload_bool(payload, "chat_history_enabled", True):
        await run_in_threadpool(
            add_chat_message,
            int(user["id"]),
            str(response.get("session_id") or payload.get("session_id") or "default"),
            "assistant",
            _answer_from_result(response),
            response.get("sources") if isinstance(response.get("sources"), list) else [],
            response.get("mode"),
        )
    return response


@app.get("/api/chat/sessions")
async def chat_sessions(request: Request) -> dict[str, Any]:
    user = _require_auth_user(request)
    sessions = await run_in_threadpool(list_chat_sessions, int(user["id"]))
    return {"ok": True, "sessions": sessions}


@app.post("/api/chat/sessions")
async def create_session(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    user = _require_auth_user(request)
    title = str(payload.get("title") or "Nueva conversación").strip() or "Nueva conversación"
    requested_session_id = str(payload.get("session_id") or "").strip() or None
    session_id = await run_in_threadpool(create_chat_session, int(user["id"]), title, requested_session_id)
    return {"ok": True, "session_id": session_id, "title": title}


@app.get("/api/chat/history/{session_id}")
async def chat_history(session_id: str, request: Request) -> dict[str, Any]:
    user = _require_auth_user(request)
    messages = await run_in_threadpool(get_chat_history, int(user["id"]), session_id)
    return {"ok": True, "session_id": session_id, "messages": messages}


@app.post("/api/chat/history")
async def post_chat_history(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    user = _require_auth_user(request)
    session_id = await run_in_threadpool(
        ensure_chat_session,
        int(user["id"]),
        str(payload.get("session_id") or ""),
        "Nueva conversación",
    )
    role = str(payload.get("role") or "").strip().lower()
    content = str(payload.get("content") or "").strip()
    if not role or not content:
        raise HTTPException(status_code=400, detail="Faltan role o content.")
    sources = payload.get("sources") if isinstance(payload.get("sources"), list) else []
    await run_in_threadpool(
        add_chat_message,
        int(user["id"]),
        session_id,
        role,
        content,
        sources,
        payload.get("mode"),
    )
    return {"ok": True, "session_id": session_id}


@app.post("/api/unified-brain/ask")
async def unified_brain_ask(request: Request) -> dict[str, Any]:
    user = _optional_auth_user(request)
    payload, uploaded_files = await _payload_and_uploads(request)
    _attach_user_context(payload, user)
    payload["response_profile"] = payload.get("response_profile") or "balanced"
    result = await run_in_threadpool(web_bridge.answer_from_brain, payload, uploaded_files)
    await run_in_threadpool(_store_chat_history_if_needed, payload, result, user)
    return result


@app.get("/api/unified-brain/health")
async def unified_brain_health() -> dict[str, Any]:
    return _health_payload()


@app.get("/api/unified-brain/status")
async def unified_brain_status() -> dict[str, Any]:
    return {
        "ok": True,
        "success": True,
        "brain": await run_in_threadpool(web_bridge.unified_brain_status_payload),
    }


@app.get("/api/history")
async def list_history(request: Request) -> dict[str, Any]:
    user = _optional_auth_user(request)
    if user:
        sessions = await run_in_threadpool(list_chat_sessions, int(user["id"]))
        return {
            "ok": True,
            "history": sessions,
            "chats": sessions,
            "source": "auth-database",
        }

    history = [
        {
            "id": f"memory-{session_id}",
            "session_id": session_id,
            "title": "Historial local backend",
            "created_at": messages[0].get("createdAt") if messages else _utc_now(),
            "updated_at": messages[-1].get("createdAt") if messages else _utc_now(),
            "messages": messages,
        }
        for session_id, messages in frontend_history_store.items()
    ]
    return {
        "ok": True,
        "history": history,
        "chats": history,
        "source": "memory-placeholder",
    }


@app.get("/api/history/{session_id}")
async def get_history(session_id: str) -> dict[str, Any]:
    clean_session_id = str(session_id or "default")[:120]
    return {
        "ok": True,
        "session_id": clean_session_id,
        "messages": frontend_history_store.get(clean_session_id, []),
        "source": "memory-placeholder",
    }


@app.post("/api/history")
async def save_history(payload: dict[str, Any]) -> dict[str, Any]:
    session_id = str(payload.get("session_id") or "default")[:120]
    messages = payload.get("messages") or []
    if not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="messages debe ser una lista.")
    frontend_history_store[session_id] = messages[-80:]
    return {"ok": True, "session_id": session_id, "count": len(frontend_history_store[session_id])}


@app.get("/api/spaces")
async def list_spaces(request: Request) -> dict[str, Any]:
    owner_key = _frontend_owner_key(request)
    items = _collection_items("spaces", owner_key)
    return {"ok": True, "spaces": items, "items": items, "source": "memory-placeholder"}


@app.post("/api/spaces")
async def save_space(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    owner_key = _frontend_owner_key(request)
    item = _upsert_collection_item("spaces", owner_key, payload)
    return {"ok": True, "space": item, "item": item, "source": "memory-placeholder"}


@app.get("/api/projects")
async def list_projects(request: Request) -> dict[str, Any]:
    owner_key = _frontend_owner_key(request)
    items = _collection_items("projects", owner_key)
    return {"ok": True, "projects": items, "items": items, "source": "memory-placeholder"}


@app.post("/api/projects")
async def save_project(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    owner_key = _frontend_owner_key(request)
    item = _upsert_collection_item("projects", owner_key, payload)
    return {"ok": True, "project": item, "item": item, "source": "memory-placeholder"}


@app.get("/api/files")
async def files(request: Request) -> dict[str, Any]:
    user = _require_auth_user(request)
    items = await run_in_threadpool(list_uploaded_files, int(user["id"]))
    return {"ok": True, "files": items}
