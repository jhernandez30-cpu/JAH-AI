from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from . import storage


SOURCE_ROOT = Path(__file__).resolve().parents[2] / "odysseus-src"
IMPORTANT_FILES = {
    "README.md", "package.json", "requirements.txt", "pyproject.toml", "Dockerfile",
    "docker-compose.yml", ".env.example", "app.py", "main.py", "routes", "services",
    "src", "static",
}
LANG_BY_EXT = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "React JSX",
    ".ts": "TypeScript",
    ".tsx": "React TSX",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".json": "JSON",
    ".md": "Markdown",
    ".sql": "SQL",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".toml": "TOML",
    ".sh": "Shell",
    ".ps1": "PowerShell",
}
DANGER_PATTERNS = {
    "shell_exec": re.compile(r"\b(exec|eval|subprocess|create_subprocess_shell|os\.system)\b", re.I),
    "hardcoded_secret": re.compile(r"(api[_-]?key|secret|token|password)\s*[:=]", re.I),
    "path_traversal": re.compile(r"\.\.[/\\]"),
    "wildcard_cors": re.compile(r"allow_origins\s*=\s*\[[^\]]*['\"]\*['\"]", re.I | re.S),
}


def odysseus_source_status() -> dict[str, Any]:
    exists = SOURCE_ROOT.exists()
    files = 0
    dirs: list[str] = []
    if exists:
        try:
            files = sum(1 for item in SOURCE_ROOT.rglob("*") if item.is_file())
            dirs = [item.name for item in SOURCE_ROOT.iterdir() if item.is_dir()]
        except Exception:
            files = 0
            dirs = []
    return {
        "exists": exists,
        "path": "backend/odysseus-src" if exists else "",
        "files": files,
        "modules": sorted(dirs)[:24],
    }


def _language_for(path: str) -> str:
    return LANG_BY_EXT.get(Path(path).suffix.lower(), Path(path).suffix.lower().lstrip(".") or "archivo")


def _stats_for_text(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    non_empty = [line for line in lines if line.strip()]
    return {
        "chars": len(text),
        "lines": len(lines),
        "non_empty_lines": len(non_empty),
    }


def _extract_findings(text: str, rel_path: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for name, pattern in DANGER_PATTERNS.items():
        if pattern.search(text):
            findings.append({
                "type": name,
                "file": rel_path,
                "message": {
                    "shell_exec": "El archivo contiene llamadas que pueden ejecutar comandos; revisar permisos y entradas.",
                    "hardcoded_secret": "Hay nombres de variables que parecen secretos; verificar que no haya credenciales reales.",
                    "path_traversal": "Se detecto patron de traversal; validar rutas antes de leer o escribir.",
                    "wildcard_cors": "CORS parece permitir cualquier origen; limitar dominios en produccion.",
                }.get(name, "Hallazgo de seguridad para revisar."),
            })
    if re.search(r"\bTODO\b|\bFIXME\b", text, re.I):
        findings.append({
            "type": "todo",
            "file": rel_path,
            "message": "Hay TODO/FIXME pendientes en el archivo.",
        })
    return findings


def _recommendations_for_action(action: str, has_upload: bool) -> list[str]:
    if action == "code":
        return [
            "Mantener cambios acotados al archivo o modulo analizado.",
            "Agregar pruebas solo donde cubran riesgo real de comportamiento.",
            "Evitar tocar identidad visual de JAH AI salvo que el cambio lo pida.",
        ]
    if action == "debug":
        return [
            "Reproducir primero el fallo con el endpoint o archivo implicado.",
            "Confirmar causa concreta antes de parchear.",
            "Validar con smoke test del flujo completo despues del cambio.",
        ]
    if action == "plan":
        return [
            "Ordenar el trabajo por backend, frontend, pruebas y despliegue.",
            "Separar pendientes externos de pendientes de codigo.",
            "No publicar secretos ni rutas absolutas de uploads.",
        ]
    return [
        "Revisar hallazgos de seguridad antes de ejecutar cambios.",
        "Usar los endpoints Odysseus para leer, buscar y analizar archivos subidos.",
        "Configurar un proveedor LLM solo en backend si se necesita razonamiento generativo.",
    ] if has_upload else [
        "Subir un archivo o ZIP para analisis contextual mas preciso.",
        "Usar busqueda/lectura segura antes de pedir cambios de codigo.",
        "Mantener safe_mode activo para evitar acciones destructivas.",
    ]


def analyze_upload(upload_path: str | None) -> dict[str, Any]:
    if not upload_path:
        files = storage.list_uploads()
        ext_counts = Counter(Path(item["relative_path"]).suffix.lower() or "sin_extension" for item in files)
        return {
            "scope": "uploads",
            "file_count": len(files),
            "languages": dict(ext_counts.most_common(12)),
            "files": files[:25],
            "findings": [],
        }

    path = storage.resolve_safe_path(upload_path)
    metadata = storage.file_metadata(path)
    if path.suffix.lower() == ".zip":
        inspection = storage.inspect_zip(upload_path)
        return {
            "scope": "zip",
            "metadata": metadata,
            "file_count": inspection.get("count", 0),
            "files": inspection.get("files", [])[:40],
            "skipped": inspection.get("skipped", []),
            "findings": [],
        }
    if path.suffix.lower() not in storage.TEXT_EXTENSIONS:
        return {
            "scope": "file",
            "metadata": metadata,
            "language": _language_for(upload_path),
            "binary": True,
            "findings": [],
        }

    text_result = storage.read_text(upload_path)
    text = str(text_result.get("content") or "")
    findings = _extract_findings(text, upload_path)
    return {
        "scope": "file",
        "metadata": metadata,
        "language": _language_for(upload_path),
        "stats": _stats_for_text(text),
        "preview": text[:2200],
        "truncated": bool(text_result.get("truncated")),
        "findings": findings,
    }


def build_static_analysis(
    message: str,
    upload_path: str | None = None,
    action: str = "analyze",
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    options = options or {}
    upload = analyze_upload(upload_path)
    source = odysseus_source_status()
    findings = list(upload.get("findings") or [])
    title_by_action = {
        "analyze": "Analisis seguro Odysseus integrado en JAH AI.",
        "code": "Asistencia de codigo con contexto Odysseus.",
        "debug": "Diagnostico guiado con contexto Odysseus.",
        "plan": "Plan tecnico generado con contexto Odysseus.",
    }
    summary_parts = [title_by_action.get(action, title_by_action["analyze"])]
    if upload_path:
        summary_parts.append(f"Archivo analizado: {upload_path}.")
    else:
        summary_parts.append(f"Uploads disponibles: {upload.get('file_count', 0)}.")
    if findings:
        summary_parts.append(f"Hallazgos: {len(findings)} para revisar.")
    else:
        summary_parts.append("Sin hallazgos criticos en el analisis estatico.")

    result = {
        "source": "jah_ai_odysseus_static",
        "action": action,
        "safe_mode": True,
        "summary": " ".join(summary_parts),
        "request": {
            "message": str(message or "")[:2000],
            "upload_path": upload_path,
            "options": {key: value for key, value in options.items() if key not in {"api_key", "token", "password"}},
        },
        "odysseus_source": source,
        "upload_analysis": upload,
        "findings": findings,
        "recommendations": _recommendations_for_action(action, bool(upload_path)),
    }
    try:
        json.dumps(result)
    except TypeError:
        result["upload_analysis"] = {"error": "No se pudo serializar el analisis de archivo."}
    return result
