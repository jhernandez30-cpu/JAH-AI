from __future__ import annotations

import mimetypes
import os
import re
import uuid
import zipfile
from pathlib import Path
from typing import Any


ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".pdf", ".docx", ".csv", ".json", ".png", ".jpg", ".jpeg",
    ".webp", ".zip", ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css",
    ".scss", ".sql", ".cs", ".java", ".go", ".rs", ".php", ".rb", ".swift",
    ".kt", ".kts", ".sh", ".ps1", ".bat", ".cmd", ".yml", ".yaml", ".toml",
    ".ini", ".cfg", ".xml",
}
TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".py", ".js", ".jsx", ".ts", ".tsx",
    ".html", ".css", ".scss", ".sql", ".cs", ".java", ".go", ".rs", ".php",
    ".rb", ".swift", ".kt", ".kts", ".sh", ".ps1", ".bat", ".cmd", ".yml",
    ".yaml", ".toml", ".ini", ".cfg", ".xml",
}
BLOCKED_FILENAMES = {
    ".env", ".env.local", ".env.production", ".env.development", "id_rsa",
    "id_dsa", "id_ecdsa", "id_ed25519", "known_hosts", "credentials",
}
BLOCKED_NAME_PARTS = (
    "private_key", "secret", "token", "api_key", "apikey", "password",
    "service_role", "supabase_service_role", "aws_secret_access_key",
)
SECRET_SIGNATURES = (
    "BEGIN PRIVATE KEY",
    "BEGIN RSA PRIVATE KEY",
    "BEGIN OPENSSH PRIVATE KEY",
    "AWS_SECRET_ACCESS_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
)

MAX_UPLOAD_BYTES = int(os.getenv("TUTOR_IA_MAX_UPLOAD_BYTES", str(8 * 1024 * 1024)))
MAX_READ_BYTES = int(os.getenv("ODYSSEUS_MAX_READ_BYTES", str(512 * 1024)))
MAX_ZIP_ENTRIES = int(os.getenv("ODYSSEUS_MAX_ZIP_ENTRIES", "80"))
MAX_ZIP_TOTAL_BYTES = int(os.getenv("ODYSSEUS_MAX_ZIP_TOTAL_BYTES", str(24 * 1024 * 1024)))
UPLOAD_ROOT = Path(
    os.getenv("TUTOR_IA_UPLOAD_DIR", str(Path(__file__).resolve().parents[2] / "uploads"))
).resolve()


def ensure_upload_root() -> None:
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


def sanitize_session_id(session_id: str | None) -> str:
    raw = str(session_id or "guest").strip() or "guest"
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw).strip(".-")
    return safe[:80] or "guest"


def sanitize_filename(original_filename: str | None) -> str:
    raw = Path(str(original_filename or "file")).name
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "_", raw).strip(" .")
    return safe[:180] or "file"


def is_secret_like_name(name: str) -> bool:
    lower = Path(name).name.lower()
    if lower in BLOCKED_FILENAMES:
        return True
    return any(part in lower for part in BLOCKED_NAME_PARTS)


def _validate_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Extension no permitida: {ext or 'sin extension'}")
    return ext


def _validate_content(filename: str, content: bytes) -> None:
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("El archivo supera el tamano maximo permitido.")
    if is_secret_like_name(filename):
        raise ValueError("El nombre del archivo parece contener secretos. Subida denegada.")
    preview = content[:4096].decode("utf-8", errors="ignore")
    for signature in SECRET_SIGNATURES:
        if signature in preview:
            raise ValueError("Contenido del archivo parece contener secretos. Subida denegada.")


def _assert_inside_upload_root(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(UPLOAD_ROOT)
    except ValueError as exc:
        raise ValueError("Ruta fuera del directorio de uploads no permitida.") from exc
    return resolved


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(UPLOAD_ROOT)).replace("\\", "/")


def resolve_safe_path(rel_path: str) -> Path:
    ensure_upload_root()
    raw = str(rel_path or "").replace("\\", "/").strip()
    if not raw:
        raise ValueError("Falta ruta relativa del archivo.")
    candidate_rel = Path(raw)
    if candidate_rel.is_absolute() or ".." in candidate_rel.parts:
        raise ValueError("Ruta de archivo no permitida.")
    return _assert_inside_upload_root(UPLOAD_ROOT / candidate_rel)


def _write_unique(dest_dir: Path, filename: str, content: bytes) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe = sanitize_filename(filename)
    candidate = _assert_inside_upload_root(dest_dir / safe)
    stem = candidate.stem
    suffix = candidate.suffix
    counter = 1
    while candidate.exists():
        candidate = _assert_inside_upload_root(dest_dir / f"{stem}-{counter}{suffix}")
        counter += 1
    candidate.write_bytes(content)
    return candidate


def file_metadata(path: Path) -> dict[str, Any]:
    stat = path.stat()
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return {
        "name": path.name,
        "relative_path": _relative(path),
        "path": _relative(path),
        "size": stat.st_size,
        "content_type": content_type,
        "modified": int(stat.st_mtime),
    }


def list_uploads(session_id: str | None = None) -> list[dict[str, Any]]:
    ensure_upload_root()
    root = UPLOAD_ROOT / sanitize_session_id(session_id) if session_id else UPLOAD_ROOT
    if not root.exists():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            items.append(file_metadata(path))
    return items


def read_file(rel_path: str, max_bytes: int | None = None) -> bytes:
    path = resolve_safe_path(rel_path)
    if not path.exists() or not path.is_file():
        raise ValueError("Archivo no encontrado.")
    limit = max_bytes or MAX_READ_BYTES
    if path.stat().st_size > limit:
        return path.read_bytes()[:limit]
    return path.read_bytes()


def read_text(rel_path: str, max_chars: int = 20000) -> dict[str, Any]:
    path = resolve_safe_path(rel_path)
    data = read_file(rel_path)
    ext = path.suffix.lower()
    if ext not in TEXT_EXTENSIONS:
        return {
            "ok": True,
            "relative_path": _relative(path),
            "content": "",
            "binary": True,
            "message": "Archivo binario o no textual. Se permite inspeccion de metadatos, no lectura completa.",
            "truncated": path.stat().st_size > len(data),
            "metadata": file_metadata(path),
        }
    text = data.decode("utf-8", errors="ignore")
    return {
        "ok": True,
        "relative_path": _relative(path),
        "content": text[:max_chars],
        "binary": False,
        "truncated": len(text) > max_chars or path.stat().st_size > len(data),
        "metadata": file_metadata(path),
    }


def _safe_zip_parts(name: str) -> list[str]:
    normalized = str(name or "").replace("\\", "/").strip("/")
    rel = Path(normalized)
    if not normalized or rel.is_absolute() or ".." in rel.parts:
        raise ValueError("Entrada ZIP con ruta no permitida.")
    parts = [re.sub(r"[^A-Za-z0-9._ -]+", "_", part).strip(" .") for part in rel.parts]
    parts = [part for part in parts if part]
    if not parts:
        raise ValueError("Entrada ZIP sin nombre valido.")
    if is_secret_like_name(parts[-1]):
        raise ValueError("Entrada ZIP parece contener secretos.")
    _validate_extension(parts[-1])
    return parts


def inspect_zip(rel_path: str) -> dict[str, Any]:
    path = resolve_safe_path(rel_path)
    if path.suffix.lower() != ".zip":
        raise ValueError("El archivo no es un ZIP.")
    entries: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    total_size = 0
    try:
        with zipfile.ZipFile(path, "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                try:
                    _safe_zip_parts(info.filename)
                    total_size += int(info.file_size)
                    entries.append({"name": info.filename, "size": int(info.file_size)})
                except Exception as exc:
                    skipped.append({"name": info.filename, "reason": str(exc)})
    except zipfile.BadZipFile as exc:
        raise ValueError("ZIP corrupto o invalido.") from exc
    return {
        "ok": True,
        "count": len(entries),
        "total_size": total_size,
        "files": entries,
        "skipped": skipped,
    }


def extract_zip(rel_path: str) -> dict[str, Any]:
    zip_path = resolve_safe_path(rel_path)
    if zip_path.suffix.lower() != ".zip":
        raise ValueError("El archivo no es un ZIP.")
    extracted: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    total_size = 0
    dest_root = _assert_inside_upload_root(zip_path.parent / "extracted" / f"{zip_path.stem}-{uuid.uuid4().hex[:8]}")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            members = [info for info in zf.infolist() if not info.is_dir()]
            if len(members) > MAX_ZIP_ENTRIES:
                raise ValueError("El ZIP contiene demasiados archivos.")
            for info in members:
                try:
                    parts = _safe_zip_parts(info.filename)
                    total_size += int(info.file_size)
                    if total_size > MAX_ZIP_TOTAL_BYTES:
                        raise ValueError("El ZIP supera el tamano total permitido.")
                    if info.file_size > MAX_UPLOAD_BYTES:
                        raise ValueError("Entrada ZIP supera el tamano maximo por archivo.")
                    data = zf.read(info)
                    _validate_content(parts[-1], data)
                    dest_dir = dest_root
                    for folder in parts[:-1]:
                        dest_dir = _assert_inside_upload_root(dest_dir / folder)
                    saved = _write_unique(dest_dir, parts[-1], data)
                    extracted.append(file_metadata(saved))
                except Exception as exc:
                    skipped.append({"name": info.filename, "reason": str(exc)})
    except zipfile.BadZipFile as exc:
        raise ValueError("ZIP corrupto o invalido.") from exc
    return {
        "ok": True,
        "destination": _relative(dest_root),
        "files": extracted,
        "skipped": skipped,
        "count": len(extracted),
    }


def save_file_details(original_filename: str | None, content: bytes, session_id: str | None = None) -> dict[str, Any]:
    ensure_upload_root()
    filename = sanitize_filename(original_filename)
    _validate_extension(filename)
    _validate_content(filename, content)
    session_dir = _assert_inside_upload_root(UPLOAD_ROOT / sanitize_session_id(session_id))
    saved = _write_unique(session_dir, filename, content)
    metadata = file_metadata(saved)
    result: dict[str, Any] = {
        "ok": True,
        **metadata,
    }
    if saved.suffix.lower() == ".zip":
        result["zip"] = inspect_zip(metadata["relative_path"])
        result["extracted"] = extract_zip(metadata["relative_path"])
    return result


def save_file(original_filename: str | None, content: bytes, session_id: str | None = None) -> str:
    return str(save_file_details(original_filename, content, session_id=session_id)["relative_path"])


def search_files(query: str, session_id: str | None = None, max_results: int = 30) -> dict[str, Any]:
    q = str(query or "").strip().lower()
    files = list_uploads(session_id=session_id)
    if not q:
        return {"ok": True, "files": files[:max_results], "query": q}
    matches: list[dict[str, Any]] = []
    for item in files:
        haystack = f"{item.get('name', '')} {item.get('relative_path', '')}".lower()
        match = q in haystack
        snippet = ""
        path = resolve_safe_path(str(item.get("relative_path", "")))
        if not match and path.suffix.lower() in TEXT_EXTENSIONS and path.stat().st_size <= MAX_READ_BYTES:
            text = path.read_text(encoding="utf-8", errors="ignore")
            index = text.lower().find(q)
            if index >= 0:
                match = True
                start = max(0, index - 80)
                end = min(len(text), index + len(q) + 160)
                snippet = text[start:end].replace("\r", " ").replace("\n", " ")
        if match:
            item = {**item}
            if snippet:
                item["snippet"] = snippet
            matches.append(item)
        if len(matches) >= max_results:
            break
    return {"ok": True, "files": matches, "query": q}
