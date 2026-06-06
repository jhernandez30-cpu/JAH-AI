from __future__ import annotations

import asyncio
import ipaddress
import inspect
import logging
import mimetypes
import os
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


LOGGER = logging.getLogger(__name__)

DEFAULT_NOTEBOOKLM_TIMEOUT = float(os.getenv("NOTEBOOKLM_TIMEOUT", "30"))
DEFAULT_SOURCE_WAIT_TIMEOUT = float(os.getenv("NOTEBOOKLM_SOURCE_WAIT_TIMEOUT", "120"))
SAFE_FILE_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".md",
    ".docx",
    ".csv",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".mp3",
    ".mp4",
    ".wav",
    ".m4a",
}


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off", ""}


def _set_windows_event_loop_policy() -> None:
    if sys.platform != "win32":
        return
    policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
    if policy:
        try:
            asyncio.set_event_loop_policy(policy())
        except RuntimeError:
            pass


_set_windows_event_loop_policy()


@dataclass
class NotebookLMResult:
    ok: bool
    answer: str = ""
    data: Any = None
    message: str = ""
    error_type: str = ""
    references: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "answer": self.answer,
            "data": self.data,
            "message": self.message,
            "error_type": self.error_type,
            "references": self.references,
        }


class NotebookLMService:
    """Small sync facade around notebooklm-py's async client.

    The rest of TUTOR_IA is synchronous (Streamlit and a small HTTP bridge), so
    this class keeps the NotebookLM async API isolated and gives callers safe
    dictionaries/results. It never exposes cookies or storage paths to the UI.
    """

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        profile: str | None = None,
        active_notebook_id: str | None = None,
        timeout: float = DEFAULT_NOTEBOOKLM_TIMEOUT,
    ) -> None:
        self.enabled = _env_bool("NOTEBOOKLM_ENABLED", False) if enabled is None else enabled
        self.profile = profile or os.getenv("NOTEBOOKLM_PROFILE") or "default"
        self.active_notebook_id = active_notebook_id or os.getenv("NOTEBOOKLM_ACTIVE_ID", "").strip()
        self.timeout = timeout

    def is_available(self) -> bool:
        try:
            import notebooklm  # noqa: F401
        except Exception:
            return False
        return True

    def get_status(self, *, check_auth: bool = False) -> dict[str, Any]:
        installed = self.is_available()
        status = {
            "enabled": self.enabled,
            "installed": installed,
            "authenticated": False,
            "profile": self.profile,
            "active_notebook_id": self.active_notebook_id,
            "message": "",
        }
        if not installed:
            status["message"] = "notebooklm-py no esta instalado."
            return status
        if not self.enabled:
            status["message"] = "Cerebro NotebookLM desactivado."
            return status

        if not check_auth:
            status["message"] = "Cerebro NotebookLM disponible; autenticacion no verificada."
            return status

        notebooks = self.list_notebooks()
        status["authenticated"] = notebooks.ok
        if notebooks.ok:
            status["notebooks_count"] = len(notebooks.data or [])
            status["message"] = "NotebookLM autenticado."
        else:
            status["message"] = notebooks.message
            status["error_type"] = notebooks.error_type
        return status

    def set_active_notebook(self, notebook_id: str) -> NotebookLMResult:
        notebook_id = str(notebook_id or "").strip()
        if not notebook_id:
            return NotebookLMResult(False, message="Selecciona un notebook valido.", error_type="validation")
        self.active_notebook_id = notebook_id
        return NotebookLMResult(True, data={"active_notebook_id": notebook_id})

    def get_active_notebook(self) -> str:
        return self.active_notebook_id

    def list_notebooks(self) -> NotebookLMResult:
        return self._safe_run(self._list_notebooks())

    def ask(self, question: str, notebook_id: str | None = None) -> NotebookLMResult:
        question = str(question or "").strip()
        if not question:
            return NotebookLMResult(False, message="La pregunta esta vacia.", error_type="validation")
        resolved_id = self._resolve_notebook_id(notebook_id)
        if not resolved_id:
            return NotebookLMResult(
                False,
                message="Configura un notebook activo antes de usar Cerebro NotebookLM.",
                error_type="not_configured",
            )
        return self._safe_run(self._ask(resolved_id, question))

    def add_url_source(self, notebook_id: str | None, url: str) -> NotebookLMResult:
        resolved_id = self._resolve_notebook_id(notebook_id)
        if not resolved_id:
            return NotebookLMResult(False, message="Configura un notebook activo.", error_type="not_configured")
        ok, message = validate_notebooklm_url(url)
        if not ok:
            return NotebookLMResult(False, message=message, error_type="validation")
        return self._safe_run(self._add_url_source(resolved_id, url.strip()))

    def add_file_source(self, notebook_id: str | None, file_path: str | Path) -> NotebookLMResult:
        resolved_id = self._resolve_notebook_id(notebook_id)
        if not resolved_id:
            return NotebookLMResult(False, message="Configura un notebook activo.", error_type="not_configured")
        ok, message, safe_path = validate_notebooklm_file_path(file_path)
        if not ok or safe_path is None:
            return NotebookLMResult(False, message=message, error_type="validation")
        return self._safe_run(self._add_file_source(resolved_id, safe_path))

    def summarize_notebook(self, notebook_id: str | None = None) -> NotebookLMResult:
        resolved_id = self._resolve_notebook_id(notebook_id)
        if not resolved_id:
            return NotebookLMResult(False, message="Configura un notebook activo.", error_type="not_configured")
        return self._safe_run(self._summarize_notebook(resolved_id))

    def generate_study_guide(self, notebook_id: str | None = None) -> NotebookLMResult:
        resolved_id = self._resolve_notebook_id(notebook_id)
        if not resolved_id:
            return NotebookLMResult(False, message="Configura un notebook activo.", error_type="not_configured")
        return self._safe_run(self._generate_study_guide(resolved_id))

    def generate_quiz(self, notebook_id: str | None = None) -> NotebookLMResult:
        resolved_id = self._resolve_notebook_id(notebook_id)
        if not resolved_id:
            return NotebookLMResult(False, message="Configura un notebook activo.", error_type="not_configured")
        return self._safe_run(self._generate_quiz(resolved_id))

    def _resolve_notebook_id(self, notebook_id: str | None = None) -> str:
        return str(notebook_id or self.active_notebook_id or "").strip()

    async def _client(self):
        from notebooklm import NotebookLMClient

        kwargs = {"timeout": self.timeout}
        if "profile" in inspect.signature(NotebookLMClient.from_storage).parameters:
            kwargs["profile"] = self.profile
        return await NotebookLMClient.from_storage(**kwargs)

    async def _list_notebooks(self) -> NotebookLMResult:
        async with await self._client() as client:
            notebooks = await client.notebooks.list()
        return NotebookLMResult(True, data=[_notebook_to_dict(notebook) for notebook in notebooks])

    async def _ask(self, notebook_id: str, question: str) -> NotebookLMResult:
        async with await self._client() as client:
            result = await client.chat.ask(notebook_id, question)
        references = [_reference_to_dict(ref) for ref in getattr(result, "references", []) or []]
        return NotebookLMResult(
            True,
            answer=str(getattr(result, "answer", "") or "").strip(),
            data={
                "notebook_id": notebook_id,
                "conversation_id": getattr(result, "conversation_id", None),
                "turn_number": getattr(result, "turn_number", None),
            },
            references=references,
        )

    async def _add_url_source(self, notebook_id: str, url: str) -> NotebookLMResult:
        async with await self._client() as client:
            source = await client.sources.add_url(
                notebook_id,
                url,
                wait=True,
                wait_timeout=DEFAULT_SOURCE_WAIT_TIMEOUT,
            )
        return NotebookLMResult(True, data=_source_to_dict(source), message="Fuente URL agregada a NotebookLM.")

    async def _add_file_source(self, notebook_id: str, file_path: Path) -> NotebookLMResult:
        mime_type = mimetypes.guess_type(file_path.name)[0]
        async with await self._client() as client:
            source = await client.sources.add_file(notebook_id, file_path, mime_type=mime_type)
        return NotebookLMResult(True, data=_source_to_dict(source), message="Archivo agregado a NotebookLM.")

    async def _summarize_notebook(self, notebook_id: str) -> NotebookLMResult:
        async with await self._client() as client:
            summary = await client.notebooks.get_summary(notebook_id)
        return NotebookLMResult(True, answer=str(summary or "").strip(), data={"notebook_id": notebook_id})

    async def _generate_study_guide(self, notebook_id: str) -> NotebookLMResult:
        async with await self._client() as client:
            status = await client.artifacts.generate_study_guide(notebook_id, language="es")
        return NotebookLMResult(True, data=_generation_status_to_dict(status), message="Guia de estudio iniciada.")

    async def _generate_quiz(self, notebook_id: str) -> NotebookLMResult:
        async with await self._client() as client:
            status = await client.artifacts.generate_quiz(notebook_id)
        return NotebookLMResult(True, data=_generation_status_to_dict(status), message="Quiz iniciado.")

    def _safe_run(self, coroutine) -> NotebookLMResult:
        if not self.enabled:
            _close_coroutine(coroutine)
            return NotebookLMResult(False, message="Cerebro NotebookLM desactivado.", error_type="disabled")
        if not self.is_available():
            _close_coroutine(coroutine)
            return NotebookLMResult(
                False,
                message="notebooklm-py no esta instalado. Ejecuta pip install notebooklm-py.",
                error_type="not_installed",
            )
        try:
            return _run_async(coroutine)
        except Exception as exc:
            result = _error_result(exc)
            LOGGER.warning("NotebookLM operation failed (%s): %s", result.error_type, result.message)
            return result


def _close_coroutine(coroutine) -> None:
    close = getattr(coroutine, "close", None)
    if close:
        close()


def _run_async(coroutine) -> NotebookLMResult:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)

    result: dict[str, Any] = {}

    def runner() -> None:
        try:
            result["value"] = asyncio.run(coroutine)
        except Exception as exc:  # pragma: no cover - defensive path for embedded runtimes
            result["error"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()
    if "error" in result:
        raise result["error"]
    return result["value"]


def validate_notebooklm_url(url: str) -> tuple[bool, str]:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False, "URL invalida. Usa http o https."
    hostname = parsed.hostname or ""
    if hostname.lower() in {"localhost", "127.0.0.1", "::1"}:
        return False, "No se permiten URLs locales para NotebookLM."
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            return False, "No se permiten IPs privadas o locales para NotebookLM."
    except ValueError:
        pass
    return True, ""


def validate_notebooklm_file_path(file_path: str | Path) -> tuple[bool, str, Path | None]:
    try:
        path = Path(file_path).expanduser().resolve()
    except OSError:
        return False, "Ruta de archivo invalida.", None
    if not path.exists() or not path.is_file():
        return False, "El archivo no existe o no es un archivo valido.", None
    if path.suffix.lower() not in SAFE_FILE_EXTENSIONS:
        return False, f"Extension no permitida para NotebookLM: {path.suffix}", None

    allowed_roots = _allowed_file_roots()
    if allowed_roots and not any(_is_relative_to(path, root) for root in allowed_roots):
        return False, "La ruta del archivo no esta dentro de una carpeta permitida.", None
    return True, "", path


def _allowed_file_roots() -> list[Path]:
    raw_roots = os.getenv("NOTEBOOKLM_ALLOWED_FILE_ROOTS", "")
    candidates = [item for item in raw_roots.split(os.pathsep) if item.strip()]
    roots = [Path.cwd(), Path(tempfile.gettempdir())]
    roots.extend(Path(item).expanduser() for item in candidates)
    resolved = []
    for root in roots:
        try:
            resolved.append(root.resolve())
        except OSError:
            continue
    return resolved


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _notebook_to_dict(notebook: Any) -> dict[str, Any]:
    return {
        "id": getattr(notebook, "id", ""),
        "title": getattr(notebook, "title", ""),
        "sources_count": getattr(notebook, "sources_count", 0),
        "created_at": _date_to_text(getattr(notebook, "created_at", None)),
        "is_owner": getattr(notebook, "is_owner", True),
    }


def _source_to_dict(source: Any) -> dict[str, Any]:
    kind = getattr(source, "kind", "")
    return {
        "id": getattr(source, "id", ""),
        "title": getattr(source, "title", ""),
        "url": getattr(source, "url", None),
        "kind": getattr(kind, "value", str(kind)),
        "status": getattr(source, "status", None),
        "is_ready": getattr(source, "is_ready", None),
    }


def _reference_to_dict(reference: Any) -> dict[str, Any]:
    return {
        "source_id": getattr(reference, "source_id", None),
        "source_title": getattr(reference, "source_title", None),
        "text": getattr(reference, "text", None),
    }


def _generation_status_to_dict(status: Any) -> dict[str, Any]:
    return {
        "task_id": getattr(status, "task_id", None),
        "status": getattr(status, "status", None),
        "error": getattr(status, "error", None),
        "is_complete": getattr(status, "is_complete", None),
        "is_in_progress": getattr(status, "is_in_progress", None),
    }


def _date_to_text(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


def _error_result(exc: Exception) -> NotebookLMResult:
    detail = str(exc)
    lowered = detail.lower()
    if "auth not found" in lowered or "auth_required" in lowered or "login" in lowered:
        return NotebookLMResult(
            False,
            message="NotebookLM no esta autenticado. Ejecuta notebooklm login para activar esta funcion.",
            error_type="auth",
        )
    if "rate" in lowered or "quota" in lowered or "429" in lowered:
        return NotebookLMResult(
            False,
            message="NotebookLM limito la solicitud. Espera un momento y vuelve a intentar.",
            error_type="rate_limit",
        )
    if "timeout" in lowered or "timed out" in lowered:
        return NotebookLMResult(
            False,
            message="NotebookLM tardo demasiado en responder. El asistente seguira con el cerebro local.",
            error_type="timeout",
        )
    return NotebookLMResult(
        False,
        message="NotebookLM no pudo responder ahora. El asistente seguira con el cerebro local.",
        error_type="runtime",
    )
