from __future__ import annotations

from typing import Any

from . import analyzer, security, storage
from ..services.llm_orchestrator import get_orchestrator


SAFE_ACTIONS = {"analyze", "code", "debug", "plan"}


def odysseus_status() -> dict[str, Any]:
    orchestrator = get_orchestrator()
    llm = orchestrator.status() if hasattr(orchestrator, "status") else {
        "configured": bool(orchestrator.is_configured()),
        "provider": "unknown",
    }
    source = analyzer.odysseus_source_status()
    return {
        "ok": True,
        "odysseus": "ready",
        "safe_mode": True,
        "source_loaded": bool(source.get("exists")),
        "source": source,
        "llm": llm,
        "tools": [
            "status",
            "analyze",
            "code",
            "debug",
            "plan",
            "list_files",
            "search_files",
            "read_file",
            "inspect_zip",
        ],
        "storage": {
            "root": "backend/uploads",
            "max_upload_bytes": storage.MAX_UPLOAD_BYTES,
            "allowed_extensions": sorted(storage.ALLOWED_EXTENSIONS),
        },
    }


def _llm_context(static_result: dict[str, Any]) -> str:
    upload = static_result.get("upload_analysis") or {}
    preview = upload.get("preview") or ""
    summary = static_result.get("summary") or ""
    findings = static_result.get("findings") or []
    return (
        f"Resumen estatico:\n{summary}\n\n"
        f"Hallazgos:\n{findings}\n\n"
        f"Preview de archivo:\n{preview[:6000]}"
    )


def _system_prompt_for(action: str) -> str:
    prompts = {
        "analyze": "Analiza el contexto de forma tecnica, concreta y segura.",
        "code": "Propón cambios de codigo acotados, sin romper identidad visual ni estructura existente.",
        "debug": "Encuentra causa probable, evidencia y validaciones concretas.",
        "plan": "Ordena un plan ejecutable por fases, validaciones y riesgos.",
    }
    return prompts.get(action, prompts["analyze"])


def analyze(
    message: str,
    upload_path: str | None = None,
    model: str | None = None,
    options: dict[str, Any] | None = None,
    action: str = "analyze",
) -> dict[str, Any]:
    action = str(action or "analyze").lower()
    if action not in SAFE_ACTIONS:
        action = "analyze"
    security.ensure_tool_allowed(action)
    options = options or {}

    try:
        static_result = analyzer.build_static_analysis(message, upload_path=upload_path, action=action, options=options)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "message": "No se pudo analizar el archivo solicitado."}

    orchestrator = get_orchestrator()
    llm_status = orchestrator.status() if hasattr(orchestrator, "status") else {"configured": orchestrator.is_configured()}
    result: dict[str, Any] = {
        **static_result,
        "llm": {
            **llm_status,
            "error": None if llm_status.get("configured") else "MODEL_PROVIDER_NOT_CONFIGURED",
            "message": None if llm_status.get("configured") else "Proveedor LLM no configurado; se devuelve analisis estatico seguro.",
        },
    }

    if options.get("use_llm", True) and orchestrator.is_configured():
        prompt = (
            f"{_system_prompt_for(action)}\n\n"
            f"Solicitud del usuario:\n{message or '(sin mensaje)'}"
        )
        generated = orchestrator.generate(
            prompt,
            context=_llm_context(static_result),
            options={**options, "model": model or options.get("model")},
        )
        result["llm_result"] = generated
        if generated.get("success") and generated.get("answer"):
            result["summary"] = str(generated["answer"])[:6000]

    return {
        "ok": True,
        "action": action,
        "result": result,
        "safe_mode": True,
    }


def save_uploaded(original_filename: str | None, content: bytes, session_id: str | None = None) -> dict[str, Any]:
    try:
        return storage.save_file_details(original_filename, content, session_id=session_id)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def list_files(session_id: str | None = None) -> dict[str, Any]:
    return {"ok": True, "files": storage.list_uploads(session_id=session_id)}


def search_files(query: str, session_id: str | None = None, max_results: int = 30) -> dict[str, Any]:
    return storage.search_files(query, session_id=session_id, max_results=max_results)


def read_file(path: str, max_chars: int = 20000) -> dict[str, Any]:
    return storage.read_text(path, max_chars=max_chars)


def inspect_zip(path: str) -> dict[str, Any]:
    return storage.inspect_zip(path)


def run_tool(tool: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    args = args or {}
    security.ensure_tool_allowed(tool)
    if tool == "status":
        return odysseus_status()
    if tool in SAFE_ACTIONS:
        return analyze(
            str(args.get("message") or ""),
            upload_path=args.get("upload_path"),
            model=args.get("model"),
            options=args.get("options") or {},
            action=tool,
        )
    if tool == "list_files":
        return list_files(session_id=args.get("session_id"))
    if tool == "search_files":
        return search_files(
            str(args.get("query") or ""),
            session_id=args.get("session_id"),
            max_results=int(args.get("max_results") or 30),
        )
    if tool == "read_file":
        return read_file(str(args.get("path") or ""), max_chars=int(args.get("max_chars") or 20000))
    if tool == "inspect_zip":
        return inspect_zip(str(args.get("path") or ""))
    return {"ok": False, "error": "TOOL_NOT_SUPPORTED"}
