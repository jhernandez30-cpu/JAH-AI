from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any


DEFAULT_BRAIN_ROOT = Path(__file__).resolve().parents[2]
BRAIN_ROOT = Path(os.getenv("BRAIN_ROOT", str(DEFAULT_BRAIN_ROOT)))

USEFUL_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".html",
    ".css",
    ".js",
}
USEFUL_FILENAMES = {".env.example", "env.example"}
IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".notebooklm",
    ".cache",
    "vectores",
    "database",
    "_pdfs",
}
IGNORED_FILES = {".env", "storage_state.json"}

MAX_SCAN_FILES = int(os.getenv("LOCAL_BRAIN_MAX_FILES", "1500"))
MAX_FILE_BYTES = int(os.getenv("LOCAL_BRAIN_MAX_FILE_BYTES", "350000"))
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "12000"))
SCAN_CACHE_SECONDS = int(os.getenv("LOCAL_BRAIN_SCAN_CACHE_SECONDS", "45"))

TOKEN_RE = re.compile(r"[a-zA-Z0-9_#.+-]+")

INTENT_PATTERNS: list[tuple[str, str]] = [
    ("error_codigo", r"\b(error|traceback|exception|bug|debug|fallo|no funciona|stack trace)\b"),
    ("explicacion_codigo", r"\b(explica|explicame|como funciona|analiza este codigo|revisa este codigo)\b"),
    ("arquitectura", r"\b(arquitectura|diseno|modular|servicio|capa|patron|refactor)\b"),
    ("streamlit", r"\b(streamlit|st\.|chat_input|session_state)\b"),
    ("fastapi_flask", r"\b(fastapi|flask|uvicorn|endpoint|route|api rest)\b"),
    ("python", r"\b(python|pip|venv|pytest|py|langchain|ollama)\b"),
    ("csharp", r"\b(c#|csharp|\.net|asp\.net|blazor)\b"),
    ("html_css_js", r"\b(html|css|javascript|js|typescript|react|vue|frontend)\b"),
    ("base_datos", r"\b(sql|sqlite|postgres|mysql|database|base de datos|tabla|consulta)\b"),
    ("ciberseguridad", r"\b(ciberseguridad|seguridad|owasp|vulnerabilidad|hardening|xss|csrf|inyeccion)\b"),
    ("power_bi", r"\b(power bi|dax|power query|dashboard|medida)\b"),
    ("n8n", r"\b(n8n|workflow|automatizacion|rpa|webhook)\b"),
    ("inteligencia_artificial", r"\b(ia|ai|llm|rag|agente|anthropic|claude|openai|embedding|modelo)\b"),
    ("archivos", r"\b(archivo|fichero|carpeta|ruta|leer|guardar|file|path)\b"),
    ("configuracion_proyecto", r"\b(config|settings|env|requirements|instalar|puerto|servidor|bridge)\b"),
    ("programacion", r"\b(programacion|codigo|backend|frontend|funcion|clase|script)\b"),
]

INTENT_HINTS = {
    "programacion": ["programacion", "codigo", "conceptos", "receta", "snippet", ".py"],
    "error_codigo": ["errores", "excepciones", "depurar", "debug", "receta"],
    "explicacion_codigo": ["conceptos", "programacion", "prompts", "contrato"],
    "arquitectura": ["arquitectura", "pipeline", "decision", "servicio", "modular"],
    "python": ["python", "funciones", "modulos", "archivos", ".py"],
    "csharp": ["csharp", "c#", "asp", "blazor"],
    "html_css_js": ["web", "frontend", "html", "css", "javascript", ".html", ".css", ".js"],
    "streamlit": ["streamlit", "app.py", "session_state", "chat_input"],
    "fastapi_flask": ["fastapi", "flask", "api", "backend", "http", "rest"],
    "base_datos": ["sql", "bases de datos", "database", "consulta", "tabla"],
    "ciberseguridad": ["ciberseguridad", "owasp", "seguridad", "hardening"],
    "power_bi": ["power bi", "dax", "power query", "dashboard"],
    "n8n": ["n8n", "workflow", "automatizacion", "rpa"],
    "inteligencia_artificial": ["ia", "rag", "llm", "ollama", "agente", "embedding"],
    "archivos": ["archivo", "ruta", "workspace", "project_workspace"],
    "configuracion_proyecto": ["config", "settings", ".env.example", "requirements", "web_bridge"],
    "pregunta_general": ["indice", "bienvenido", "contrato", "programacion"],
}


def detect_intent(message: str) -> str:
    text = str(message or "").lower()
    for intent, pattern in INTENT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return intent
    return "pregunta_general"


class LocalBrainService:
    def __init__(self, brain_root: str | Path | None = None) -> None:
        self.root = Path(brain_root or os.getenv("BRAIN_ROOT", str(DEFAULT_BRAIN_ROOT)))
        self._scan_cache: tuple[float, list[dict[str, Any]]] | None = None

    def exists(self) -> bool:
        return self.root.exists() and self.root.is_dir()

    def get_root(self) -> Path:
        return self.root

    def scan_sources(self) -> list[dict[str, Any]]:
        cached = self._scan_cache
        if cached and time.monotonic() - cached[0] < SCAN_CACHE_SECONDS:
            return cached[1]

        sources: list[dict[str, Any]] = []
        if not self.exists():
            self._scan_cache = (time.monotonic(), sources)
            return sources

        stack = [self.root]
        while stack and len(sources) < MAX_SCAN_FILES:
            current = stack.pop()
            try:
                children = list(current.iterdir())
            except (OSError, PermissionError):
                continue

            for child in children:
                name = child.name
                if child.is_dir():
                    if name in IGNORED_DIRS:
                        continue
                    stack.append(child)
                    continue

                if not self._is_useful_file(child):
                    continue

                try:
                    size = child.stat().st_size
                except (OSError, PermissionError):
                    continue
                if size > MAX_FILE_BYTES:
                    continue

                sources.append(
                    {
                        "path": child,
                        "relative_path": self._relative(child),
                        "name": child.name,
                        "suffix": child.suffix.lower(),
                        "size": size,
                    }
                )

        self._scan_cache = (time.monotonic(), sources)
        return sources

    def read_relevant_files(
        self,
        message: str,
        max_files: int | None = None,
        max_chars_per_file: int | None = None,
    ) -> list[dict[str, Any]]:
        if not self.exists():
            return []

        intent = detect_intent(message)
        max_files = max_files or (8 if os.getenv("FAST_MODE", "true").lower() in {"1", "true", "yes"} else 14)
        max_chars_per_file = max_chars_per_file or 1800
        ranked = sorted(
            self.scan_sources(),
            key=lambda item: self._score_source(item, message, intent),
            reverse=True,
        )

        selected: list[dict[str, Any]] = []
        for item in ranked:
            score = self._score_source(item, message, intent)
            if score <= 0 and len(selected) >= 3:
                continue
            text = self._read_text(item["path"], max_chars=max_chars_per_file)
            if not text:
                continue
            selected.append(
                {
                    "path": str(item["path"]),
                    "relative_path": item["relative_path"],
                    "title": item["name"],
                    "content": text,
                    "score": score,
                    "intent": intent,
                }
            )
            if len(selected) >= max_files:
                break
        return selected

    def get_project_context(self, message: str) -> dict[str, Any]:
        return self.search_local_context(message)

    def search_local_context(self, message: str) -> dict[str, Any]:
        started = time.perf_counter()
        if not self.exists():
            return self._result(
                success=False,
                content="",
                confidence=0.0,
                latency_ms=self._latency(started),
                error=f"No se encontro el cerebro local en {self.root}",
            )

        files = self.read_relevant_files(message)
        if not files:
            return self._result(
                success=False,
                content="",
                confidence=0.0,
                latency_ms=self._latency(started),
                error="No se encontro contexto local relevante.",
            )

        chunks: list[str] = []
        used_chars = 0
        for item in files:
            header = f"Archivo: {item['relative_path']}\n"
            body = item["content"].strip()
            block = f"{header}{body}"
            remaining = MAX_CONTEXT_CHARS - used_chars
            if remaining <= 0:
                break
            if len(block) > remaining:
                block = block[: max(0, remaining - 3)].rstrip() + "..."
            chunks.append(block)
            used_chars += len(block)

        return self._result(
            success=True,
            content="\n\n---\n\n".join(chunks),
            confidence=0.72 if len(files) < 3 else 0.82,
            latency_ms=self._latency(started),
            error=None,
            metadata={
                "root": str(self.root),
                "intent": detect_intent(message),
                "files": [
                    {
                        "relative_path": item["relative_path"],
                        "score": item["score"],
                    }
                    for item in files
                ],
            },
        )

    def health_check(self) -> dict[str, Any]:
        started = time.perf_counter()
        sources = self.scan_sources() if self.exists() else []
        return {
            "source": "local_brain",
            "success": self.exists(),
            "content": str(self.root),
            "confidence": 1.0 if self.exists() else 0.0,
            "latency_ms": self._latency(started),
            "error": None if self.exists() else f"Ruta no encontrada: {self.root}",
            "metadata": {
                "root": str(self.root),
                "sources_found": len(sources),
            },
        }

    def _is_useful_file(self, path: Path) -> bool:
        name = path.name
        if name in IGNORED_FILES:
            return False
        if name.endswith(".log"):
            return False
        if name in USEFUL_FILENAMES:
            return True
        return path.suffix.lower() in USEFUL_EXTENSIONS

    def _score_source(self, item: dict[str, Any], message: str, intent: str) -> int:
        rel = str(item.get("relative_path", "")).lower()
        name = str(item.get("name", "")).lower()
        text = f"{rel} {name}"
        score = 0

        tokens = {token.lower() for token in TOKEN_RE.findall(str(message or ""))}
        for token in tokens:
            if len(token) >= 3 and token in text:
                score += 5

        for hint in INTENT_HINTS.get(intent, []):
            if hint.lower() in text:
                score += 12

        if item.get("suffix") == ".md":
            score += 4
        if item.get("suffix") == ".py":
            score += 5
        if "readme" in name or "indice" in name or "contrato" in name:
            score += 3
        return score

    def _read_text(self, path: Path, max_chars: int) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
        except (OSError, PermissionError, UnicodeError):
            return ""

    def _relative(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)

    def _result(
        self,
        *,
        success: bool,
        content: str,
        confidence: float,
        latency_ms: int,
        error: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "source": "local_brain",
            "success": success,
            "content": content,
            "confidence": confidence,
            "latency_ms": latency_ms,
            "error": error,
            "metadata": metadata or {"root": str(self.root), "intent": "pregunta_general", "files": []},
        }

    @staticmethod
    def _latency(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)
