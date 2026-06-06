from __future__ import annotations

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, field
from typing import Any, Callable

try:
    from services.technical_intent_router import detect_technical_intent
except Exception:  # pragma: no cover - optional defensive import
    detect_technical_intent = None


LOGGER = logging.getLogger(__name__)


SOURCE_PRIORITY = {
    "uploaded_files": 100,
    "local_sources": 90,
    "notebooklm": 80,
    "agency": 70,
    "openjarvis": 60,
    "web_search": 50,
    "tools": 40,
    "model": 10,
}

DEFAULT_OPTIONS = {
    "fast_mode": True,
    "deep_thinking": False,
    "web_search": False,
    "notebooklm": False,
    "agency": True,
    "openjarvis": True,
    "local_sources": True,
    "tools": True,
}

SOURCE_TIMEOUTS = {
    "uploaded_files": 1.0,
    "local_sources": 5.0,
    "notebooklm": 8.0,
    "agency": 8.0,
    "openjarvis": 6.0,
    "web_search": 12.0,
    "tools": 5.0,
}

RECENT_INFO_RE = re.compile(
    r"\b(ultima|ultimo|actual|hoy|ayer|noticia|version reciente|precio|2026|latest|today|news|release)\b",
    re.IGNORECASE,
)
CALC_RE = re.compile(r"(\d+\s*[\+\-\*/]\s*\d+)|\b(calcula|porcentaje|promedio|suma|resta)\b", re.IGNORECASE)
FILE_READ_RE = re.compile(r"\b(lee|leer|abre|abrir|muestra).*\b(archivo|fichero|ruta)\b", re.IGNORECASE)
FILE_WRITE_RE = re.compile(r"\b(crea|crear|escribe|guardar|modifica|editar).*\b(archivo|fichero)\b", re.IGNORECASE)
SHELL_RE = re.compile(r"\b(ejecuta|comando|powershell|terminal|shell|cmd)\b", re.IGNORECASE)
DEEP_RE = re.compile(r"\b(profundo|analisis profundo|razona|think|arquitectura|estrategia|auditoria)\b", re.IGNORECASE)

INTENT_PATTERNS = {
    "depuracion_codigo": r"\b(error|traceback|bug|debug|fallo|exception|no funciona)\b",
    "programacion": r"\b(python|javascript|html|css|api|backend|frontend|flask|fastapi|streamlit|codigo|programacion)\b",
    "bases_de_datos": r"\b(sql|postgres|mysql|sqlite|tabla|consulta|database|base de datos)\b",
    "ciberseguridad": r"\b(ciberseguridad|seguridad|owasp|vulnerabilidad|hardening|auth|xss|csrf|inyeccion)\b",
    "power_bi": r"\b(power bi|dax|power query|dashboard|medida)\b",
    "sistemas_operativos": r"\b(windows|linux|powershell|bash|sistema operativo)\b",
    "n8n": r"\b(n8n|workflow|automatizacion|rpa)\b",
    "ia": r"\b(ia|llm|rag|agente|ollama|openai|modelo|embedding)\b",
    "documentos_fuentes": r"\b(documento|fuente|pdf|libro|notebooklm|segun mis documentos)\b",
    "academica": r"\b(tarea|examen|estudio|guia|quiz|flashcards|academico)\b",
    "legal_sensible": r"\b(legal|contrato|demanda|privacidad|datos personales|sensible)\b",
}


@dataclass
class BrainSourceContext:
    source: str
    enabled: bool = True
    success: bool = False
    confidence: float = 0.0
    content: str = ""
    references: list[Any] = field(default_factory=list)
    latency_ms: int = 0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "enabled": self.enabled,
            "success": self.success,
            "confidence": self.confidence,
            "content": self.content,
            "references": self.references,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "metadata": self.metadata,
        }


class UnifiedBrain:
    """Central coordinator for TUTOR_IA sources.

    The class is intentionally dependency-injected. `app.py` and `web_bridge.py`
    keep their existing functions and pass them as providers, so this layer can
    coordinate without replacing working code.
    """

    def __init__(
        self,
        *,
        providers: dict[str, Callable[..., Any]] | None = None,
        synthesize_callback: Callable[..., str] | None = None,
        fallback_callback: Callable[..., str] | None = None,
        status_provider: Callable[[], dict[str, Any]] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.providers = providers or {}
        self.synthesize_callback = synthesize_callback
        self.fallback_callback = fallback_callback
        self.status_provider = status_provider
        self.logger = logger or LOGGER
        self._cache: dict[str, tuple[float, list[BrainSourceContext]]] = {}

    def answer(self, message: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        route = self.route_question(message)
        resolved_options = self._resolve_options(options, route)
        contexts = self.collect_context(message, resolved_options, route)
        merged = self.merge_contexts(contexts)
        try:
            answer = self.synthesize_answer(message, merged, "deep" if resolved_options["deep_thinking"] else "fast", route, resolved_options)
        except Exception as exc:
            self.logger.warning("UnifiedBrain synthesis failed: %s", exc)
            answer = self.fallback_answer(message, contexts, resolved_options)
        return {
            "answer": answer,
            "route": route,
            "options": resolved_options,
            "contexts": [context.to_dict() for context in contexts],
            "merged_context": merged,
        }

    def route_question(self, message: str) -> dict[str, Any]:
        text = str(message or "").lower()
        intents = [
            intent
            for intent, pattern in INTENT_PATTERNS.items()
            if re.search(pattern, text, re.IGNORECASE)
        ]
        technical_intent = detect_technical_intent(message) if detect_technical_intent else {}
        technical_name = str(technical_intent.get("resolved_intent") or technical_intent.get("intent") or "")
        if technical_name and technical_name != "general_technical_question" and technical_name not in intents:
            intents.append(technical_name)
        if not intents:
            intents.append("pregunta_general")

        requires_web = bool(RECENT_INFO_RE.search(text))
        requires_calculation = bool(CALC_RE.search(text))
        requires_file_read = bool(FILE_READ_RE.search(text))
        requires_file_write = bool(FILE_WRITE_RE.search(text))
        requires_shell = bool(SHELL_RE.search(text))
        deep_requested = bool(DEEP_RE.search(text))

        return {
            "intents": intents,
            "requires_web": requires_web,
            "requires_calculation": requires_calculation,
            "requires_file_read": requires_file_read,
            "requires_file_write": requires_file_write,
            "requires_shell": requires_shell,
            "deep_requested": deep_requested,
            "is_programming": any(
                intent in intents
                for intent in {
                    "programacion",
                    "depuracion_codigo",
                    "bases_de_datos",
                    "database_design",
                    "sql",
                    "crud_generation",
                    "api_generation",
                    "code_generation",
                    "code_debugging",
                    "code_review",
                    "python",
                    "csharp",
                    "streamlit_help",
                    "fastapi_help",
                    "flask_help",
                }
            ),
            "is_sensitive": "legal_sensible" in intents,
            "technical_intent": technical_intent,
        }

    def collect_context(
        self,
        message: str,
        options: dict[str, Any] | None = None,
        route: dict[str, Any] | None = None,
    ) -> list[BrainSourceContext]:
        route = route or self.route_question(message)
        options = self._resolve_options(options, route)
        cache_key = self._cache_key(message, options)
        cached = self._cache.get(cache_key)
        if cached and time.time() - cached[0] < 45:
            return cached[1]

        tasks = []
        if options.get("local_sources"):
            tasks.append(("local_sources", self.query_local_sources))
        if options.get("notebooklm"):
            tasks.append(("notebooklm", self.query_notebooklm))
        if options.get("agency") and self._should_use_agency(route, options):
            tasks.append(("agency", self.query_agency))
        if options.get("openjarvis") and self._should_use_openjarvis(route, options):
            tasks.append(("openjarvis", self.query_openjarvis))
        if options.get("web_search") or route.get("requires_web"):
            tasks.append(("web_search", self.query_web))
        if options.get("tools") and self._should_use_tools(route):
            tasks.append(("tools", self.query_tools))

        contexts: list[BrainSourceContext] = []
        executor = ThreadPoolExecutor(max_workers=max(1, min(len(tasks), 6)))
        try:
            started_at = {}
            futures = {
                source: executor.submit(fn, message, options, route)
                for source, fn in tasks
            }
            for source in futures:
                started_at[source] = time.perf_counter()
            for source, future in futures.items():
                timeout = SOURCE_TIMEOUTS.get(source, 5.0)
                try:
                    normalized = self._normalize_result(source, future.result(timeout=timeout))
                    latency_ms = int((time.perf_counter() - started_at[source]) * 1000)
                    for context in normalized:
                        if not context.latency_ms:
                            context.latency_ms = latency_ms
                    contexts.extend(normalized)
                    self.logger.info("UnifiedBrain source consulted: %s in %sms", source, latency_ms)
                except TimeoutError:
                    future.cancel()
                    contexts.append(self._failed_context(source, f"{source} excedio {timeout:.0f}s"))
                except Exception as exc:
                    contexts.append(self._failed_context(source, str(exc)))
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        contexts.sort(key=lambda item: (SOURCE_PRIORITY.get(item.source, 0), item.confidence), reverse=True)
        self._cache[cache_key] = (time.time(), contexts)
        return contexts

    def query_local_sources(self, message: str, options: dict[str, Any] | None = None, route: dict[str, Any] | None = None):
        return self._run_provider("local_sources", message, options, route)

    def query_notebooklm(self, message: str, options: dict[str, Any] | None = None, route: dict[str, Any] | None = None):
        return self._run_provider("notebooklm", message, options, route)

    def query_agency(self, message: str, options: dict[str, Any] | None = None, route: dict[str, Any] | None = None):
        return self._run_provider("agency", message, options, route)

    def query_openjarvis(self, message: str, options: dict[str, Any] | None = None, route: dict[str, Any] | None = None):
        return self._run_provider("openjarvis", message, options, route)

    def query_web(self, message: str, options: dict[str, Any] | None = None, route: dict[str, Any] | None = None):
        return self._run_provider("web_search", message, options, route)

    def query_tools(self, message: str, options: dict[str, Any] | None = None, route: dict[str, Any] | None = None):
        return self._run_provider("tools", message, options, route)

    def synthesize_answer(
        self,
        message: str,
        contexts: list[BrainSourceContext],
        mode: str = "fast",
        route: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        if self.synthesize_callback:
            return self.synthesize_callback(message, contexts, mode, route or {}, options or {})
        merged = self.merge_contexts(contexts)
        useful = "\n\n".join(context.content for context in merged if context.success and context.content)
        return useful or self.fallback_answer(message, contexts, options or {})

    def fast_answer(self, message: str) -> dict[str, Any]:
        return self.answer(message, {"fast_mode": True, "deep_thinking": False})

    def deep_answer(self, message: str) -> dict[str, Any]:
        return self.answer(message, {"fast_mode": False, "deep_thinking": True, "agency": True, "notebooklm": True})

    def fallback_answer(self, message: str, contexts: list[BrainSourceContext] | None = None, options: dict[str, Any] | None = None) -> str:
        if self.fallback_callback:
            return self.fallback_callback(message, contexts or [], options or {})
        return "No pude consultar suficientes fuentes ahora, pero puedo ayudarte con el modelo principal."

    def get_status(self) -> dict[str, Any]:
        if self.status_provider:
            return self.status_provider()
        return {"mode": "local-first", "providers": sorted(self.providers)}

    def get_available_sources(self) -> list[str]:
        return sorted(self.providers)

    def get_active_sources(self, options: dict[str, Any] | None = None) -> list[str]:
        options = {**DEFAULT_OPTIONS, **(options or {})}
        return [source for source in self.get_available_sources() if options.get(source if source != "web_search" else "web_search", True)]

    def merge_contexts(self, contexts: list[BrainSourceContext], max_chars: int = 5000) -> list[BrainSourceContext]:
        seen = set()
        merged = []
        used_chars = 0
        for context in sorted(contexts, key=lambda item: (SOURCE_PRIORITY.get(item.source, 0), item.confidence), reverse=True):
            if not context.success or not context.content:
                continue
            key = self._dedupe_key(context.content)
            if key in seen:
                continue
            seen.add(key)
            remaining = max_chars - used_chars
            if remaining <= 0:
                break
            if len(context.content) > remaining:
                context = BrainSourceContext(
                    source=context.source,
                    enabled=context.enabled,
                    success=context.success,
                    confidence=context.confidence,
                    content=context.content[: max(0, remaining - 3)].rstrip() + "...",
                    references=context.references,
                    latency_ms=context.latency_ms,
                    error=context.error,
                    metadata=context.metadata,
                )
            used_chars += len(context.content)
            merged.append(context)
        return merged

    def _run_provider(self, source: str, message: str, options: dict[str, Any] | None, route: dict[str, Any] | None):
        provider = self.providers.get(source)
        if not provider:
            return self._failed_context(source, "Proveedor no configurado")
        return provider(message, options or {}, route or {})

    def _normalize_result(self, source: str, result: Any) -> list[BrainSourceContext]:
        if result is None:
            return []
        if isinstance(result, BrainSourceContext):
            return [result]
        if isinstance(result, list):
            normalized = []
            for item in result:
                normalized.extend(self._normalize_result(source, item))
            return normalized
        if isinstance(result, dict):
            return [
                BrainSourceContext(
                    source=result.get("source", source),
                    enabled=result.get("enabled", True),
                    success=result.get("success", bool(result.get("content"))),
                    confidence=float(result.get("confidence", 0.5)),
                    content=str(result.get("content", "") or ""),
                    references=result.get("references", []) or [],
                    latency_ms=int(result.get("latency_ms", 0) or 0),
                    error=result.get("error"),
                    metadata=result.get("metadata", {}) or {},
                )
            ]
        return [BrainSourceContext(source=source, success=True, confidence=0.4, content=str(result))]

    def _failed_context(self, source: str, error: str) -> BrainSourceContext:
        self.logger.info("UnifiedBrain source failed: %s - %s", source, error)
        return BrainSourceContext(source=source, enabled=True, success=False, confidence=0.0, error=error)

    def _resolve_options(self, options: dict[str, Any] | None, route: dict[str, Any]) -> dict[str, Any]:
        resolved = {**DEFAULT_OPTIONS, **(options or {})}
        if route.get("deep_requested"):
            resolved["deep_thinking"] = True
            resolved["fast_mode"] = False
        if route.get("requires_web"):
            resolved["web_search"] = bool(resolved.get("web_search"))
        return resolved

    def _should_use_agency(self, route: dict[str, Any], options: dict[str, Any]) -> bool:
        specialized = any(
            intent in route.get("intents", [])
            for intent in {
                "ciberseguridad",
                "power_bi",
                "bases_de_datos",
                "database_design",
                "sql",
                "cybersecurity_defensive",
                "cybersecurity_analysis",
                "powerbi_help",
                "legal_sensible",
                "academica",
            }
        )
        if options.get("fast_mode") and not options.get("deep_thinking"):
            return specialized
        return bool(
            options.get("deep_thinking")
            or route.get("is_programming")
            or specialized
        )

    def _should_use_openjarvis(self, route: dict[str, Any], options: dict[str, Any]) -> bool:
        if options.get("fast_mode") and not options.get("deep_thinking"):
            return bool(route.get("requires_shell") or route.get("requires_file_read") or route.get("requires_file_write"))
        return bool(options.get("deep_thinking") or route.get("requires_shell") or route.get("requires_file_read") or route.get("requires_file_write") or route.get("is_programming"))

    def _should_use_tools(self, route: dict[str, Any]) -> bool:
        return bool(route.get("requires_calculation") or route.get("requires_file_read") or route.get("requires_file_write") or route.get("requires_shell"))

    def _cache_key(self, message: str, options: dict[str, Any]) -> str:
        key_options = {key: options.get(key) for key in sorted(DEFAULT_OPTIONS)}
        return f"{self._dedupe_key(message)}|{key_options}"

    def _dedupe_key(self, text: str) -> str:
        return re.sub(r"\W+", " ", str(text or "").lower()).strip()[:220]
