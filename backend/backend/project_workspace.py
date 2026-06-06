from __future__ import annotations

import hashlib
import os
import re
import unicodedata
from pathlib import Path


ALLOWED_CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".html",
    ".css",
    ".scss",
    ".json",
    ".md",
    ".sql",
    ".cs",
    ".java",
    ".php",
    ".go",
    ".rs",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".env.example",
}

IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".streamlit",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "brain_db",
    "vectores",
    "database",
    "conocimiento",
}

IMPORTANT_FILENAMES = {
    "README.md",
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "vite.config.ts",
    "next.config.js",
    "tsconfig.json",
    "Dockerfile",
    "docker-compose.yml",
    "app.py",
    "agency_brain.py",
    "asistente-programacion.html",
    "connected_brain.py",
    "jarvis_brain.py",
    "local_model_router.py",
    "main.py",
    "programming-assistant.css",
    "programming-assistant.js",
    "programming_skills.py",
    "project_workspace.py",
    "run_app.py",
    "start_bridge.ps1",
    "web_bridge.py",
}

CODE_SOURCE_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".html",
    ".css",
    ".scss",
    ".sql",
    ".cs",
    ".java",
    ".php",
    ".go",
    ".rs",
}

PROGRAMMING_QUERY_TOKENS = {
    "app",
    "api",
    "arquitectura",
    "asistente",
    "backend",
    "bug",
    "cerebro",
    "codigo",
    "conecta",
    "conectar",
    "conecte",
    "conexion",
    "debug",
    "frontend",
    "integracion",
    "mejora",
    "mejorar",
    "modulo",
    "modulos",
    "programacion",
    "programador",
    "software",
}

TOKEN_RE = re.compile(r"[a-z0-9_#+.-]+", re.IGNORECASE)


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_workspace_path(path: str | os.PathLike | None) -> Path | None:
    if not path:
        return None
    try:
        resolved = Path(path).expanduser().resolve()
    except OSError:
        return None
    return resolved if resolved.exists() and resolved.is_dir() else None


def _is_allowed_file(path: Path) -> bool:
    if path.name in IMPORTANT_FILENAMES:
        return True
    if path.suffix.lower() in ALLOWED_CODE_EXTENSIONS:
        return True
    if path.name.lower().endswith(".env.example"):
        return True
    return False


def _tokens(text: str) -> set[str]:
    normalized = _strip_accents(text).lower()
    return {token.lower() for token in TOKEN_RE.findall(normalized)}


def _safe_read(path: Path, max_chars: int) -> str:
    try:
        raw = path.read_bytes()
    except OSError:
        return ""
    if b"\x00" in raw[:2048]:
        return ""
    text = raw[: max_chars * 4].decode("utf-8", errors="replace")
    return text[:max_chars]


def _excerpt_for_tokens(text: str, query_tokens: set[str], max_chars: int) -> str:
    cleaned = re.sub(r"\n{3,}", "\n\n", str(text or "")).strip()
    if len(cleaned) <= max_chars:
        return cleaned

    normalized = _strip_accents(cleaned).lower()
    positions = [
        normalized.find(token)
        for token in sorted(query_tokens, key=len, reverse=True)
        if len(token) >= 3 and normalized.find(token) >= 0
    ]
    if not positions:
        return cleaned[:max_chars].rstrip() + "..."

    center = min(positions)
    start = max(0, center - max_chars // 3)
    end = min(len(cleaned), start + max_chars)
    start = max(0, end - max_chars)
    excerpt = cleaned[start:end].strip()
    if start > 0:
        excerpt = "..." + excerpt
    if end < len(cleaned):
        excerpt = excerpt.rstrip() + "..."
    return excerpt


def iter_workspace_files(root: Path, max_files: int = 600) -> list[Path]:
    files: list[Path] = []
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if dirname not in IGNORED_DIRS and not dirname.startswith(".cache")
        ]
        current = Path(current_root)
        for filename in filenames:
            path = current / filename
            if _is_allowed_file(path):
                files.append(path)
                if len(files) >= max_files:
                    return files
    return files


def summarize_workspace(root_path: str | os.PathLike | None, max_files: int = 160) -> dict:
    root = normalize_workspace_path(root_path)
    if not root:
        return {
            "available": False,
            "path": str(root_path or ""),
            "message": "No hay carpeta de proyecto valida.",
            "files": [],
            "tree": "",
            "languages": {},
        }

    files = iter_workspace_files(root, max_files=max_files)
    languages: dict[str, int] = {}
    rel_files = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        rel_files.append(rel)
        suffix = path.suffix.lower() or path.name
        languages[suffix] = languages.get(suffix, 0) + 1

    tree_limit = 45
    tree = "\n".join(f"- {rel}" for rel in rel_files[:tree_limit])
    if len(rel_files) > tree_limit:
        tree += f"\n- ... {len(rel_files) - tree_limit} archivos mas"

    return {
        "available": True,
        "path": str(root),
        "message": f"{len(rel_files)} archivos de codigo detectados.",
        "files": rel_files,
        "tree": tree,
        "languages": languages,
    }


def retrieve_workspace_context(
    question: str,
    root_path: str | os.PathLike | None,
    max_files: int = 4,
    max_chars_per_file: int = 1400,
) -> list[dict]:
    root = normalize_workspace_path(root_path)
    if not root:
        return []

    query_tokens = _tokens(question)
    code_intent = bool(query_tokens & PROGRAMMING_QUERY_TOKENS)
    candidates = []
    for path in iter_workspace_files(root, max_files=800):
        rel = path.relative_to(root).as_posix()
        rel_tokens = _tokens(rel.replace("/", " "))
        important = 6 if code_intent and path.name in IMPORTANT_FILENAMES else 3 if path.name in IMPORTANT_FILENAMES else 0
        code_file_boost = 4 if code_intent and path.suffix.lower() in CODE_SOURCE_EXTENSIONS else 0
        root_file_boost = 2 if code_intent and path.parent == root else 0
        overlap = len(query_tokens & rel_tokens)
        text = _safe_read(path, max_chars_per_file)
        content_tokens = _tokens(text)
        content_overlap = len(query_tokens & content_tokens)
        score = important + code_file_boost + root_file_boost + overlap + min(content_overlap, 6)
        if any(part.lower() in {"test", "tests"} for part in path.parts):
            score += 1 if {"test", "tests", "prueba", "validar"} & query_tokens else 0
        if score > 0:
            candidates.append((score, path, text))

    if not candidates:
        important_files = [path for path in iter_workspace_files(root, max_files=120) if path.name in IMPORTANT_FILENAMES]
        candidates = [
            (2, path, _safe_read(path, max_chars_per_file))
            for path in important_files[:max_files]
        ]

    candidates.sort(key=lambda item: (item[0], -len(str(item[1]))), reverse=True)
    docs = []
    seen = set()
    for _, path, text in candidates:
        if path in seen:
            continue
        seen.add(path)
        if not text.strip():
            continue
        rel = path.relative_to(root).as_posix()
        digest = hashlib.sha1(f"{root}|{rel}".encode("utf-8")).hexdigest()[:12]
        excerpt = _excerpt_for_tokens(text, query_tokens, max_chars_per_file)
        docs.append(
            {
                "text": excerpt,
                "metadata": {
                    "source": f"workspace:{digest}:{rel}",
                    "title": rel,
                    "type": "code",
                    "workspace": str(root),
                },
            }
        )
        if len(docs) >= max_files:
            break
    return docs


def build_workspace_brain_context(root_path: str | os.PathLike | None) -> str:
    summary = summarize_workspace(root_path)
    if not summary.get("available"):
        return ""
    languages = ", ".join(f"{key}:{value}" for key, value in sorted(summary["languages"].items()))
    return "\n".join(
        [
            "Workspace de programacion conectado.",
            f"Ruta: {summary['path']}",
            f"Resumen: {summary['message']}",
            f"Lenguajes/formatos: {languages or 'no detectado'}",
            "Arbol relevante:",
            summary.get("tree", ""),
            "Reglas del workspace:",
            "- Usa estos archivos como contexto vivo del proyecto.",
            "- No asumas que puedes modificar archivos desde la respuesta; propone cambios por archivo o pide confirmacion si se requiere ejecutar.",
            "- Si recomiendas una estructura nueva, respeta primero lo que ya existe en el workspace.",
        ]
    )
