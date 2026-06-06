from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
import zipfile
import uuid

try:
    from ..database import db_session, rows_to_dicts
except ImportError:  # pragma: no cover
    from database import db_session, rows_to_dicts  # type: ignore


BACKEND_DIR = Path(__file__).resolve().parents[1]
# Default upload root inside the backend folder to avoid accessing host home directories
TUTOR_ROOT = Path(os.getenv("TUTOR_IA_ROOT", str(BACKEND_DIR))).expanduser()
# Uploads are stored under backend/uploads by default unless TUTOR_IA_UPLOAD_DIR is explicitly set
KNOWLEDGE_DIR = Path(os.getenv("TUTOR_IA_UPLOAD_DIR", str(BACKEND_DIR / "uploads"))).expanduser()

ALLOWED_UPLOAD_EXTENSIONS = {
    ".txt",
    ".md",
    ".pdf",
    ".docx",
    ".csv",
    ".json",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}

# Allow zip projects explicitly
ALLOWED_UPLOAD_EXTENSIONS.add(".zip")


def sanitize_filename(filename: str | None) -> str:
    safe = Path(filename or "archivo").name
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "_", safe).strip(" .")
    return safe or "archivo"


def next_available_path(directory: Path, filename: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem or "archivo"
    suffix = candidate.suffix
    counter = 2
    while True:
        next_candidate = directory / f"{stem}-{counter}{suffix}"
        if not next_candidate.exists():
            return next_candidate
        counter += 1


def validate_upload(filename: str, max_bytes: int, content_size: int) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ValueError(f"Extension no permitida: {extension or 'sin extension'}")
    if content_size > max_bytes:
        raise ValueError("El archivo supera el tamano maximo permitido.")
    return extension


def save_uploaded_bytes(
    original_filename: str | None,
    content: bytes,
    content_type: str | None,
    max_bytes: int,
) -> dict[str, Any]:
    safe_name = sanitize_filename(original_filename)
    extension = validate_upload(safe_name, max_bytes, len(content))
    # Basic content safety checks: avoid saving files that look like keys or env files
    text_preview = None
    try:
        text_preview = content.decode("utf-8", errors="ignore")[:1024]
    except Exception:
        text_preview = None
    risky_signals = ["BEGIN PRIVATE KEY", "PRIVATE KEY", "AWS_SECRET_ACCESS_KEY", "OPENAI_API_KEY", ".env"]
    if text_preview:
        for sig in risky_signals:
            if sig in text_preview:
                raise ValueError("El contenido del archivo parece contener secretos o claves y no puede ser subido.")

    # Ensure uploads directory exists inside project and do not allow path traversal
    saved_path = next_available_path(KNOWLEDGE_DIR, safe_name)
    saved_path.parent.mkdir(parents=True, exist_ok=True)
    saved_path.write_bytes(content)
    return {
        "filename": saved_path.name,
        "original_filename": original_filename or saved_path.name,
        "file_path": str(saved_path),
        "file_type": content_type or extension.lstrip("."),
        "file_size": len(content),
        "indexed": 0,
    }


def record_uploaded_file(user_id: int, file_info: dict[str, Any], indexed: bool = False) -> dict[str, Any]:
    with db_session() as conn:
        cursor = conn.execute(
            """
            INSERT INTO uploaded_files
            (user_id, filename, original_filename, file_path, file_type, file_size, indexed)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                file_info["filename"],
                file_info.get("original_filename") or file_info["filename"],
                file_info["file_path"],
                file_info.get("file_type") or "",
                int(file_info.get("file_size") or 0),
                int(indexed),
            ),
        )
        row = conn.execute("SELECT * FROM uploaded_files WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row) if row else {}


def list_uploaded_files(user_id: int) -> list[dict[str, Any]]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, filename, original_filename, file_path, file_type,
                   file_size, indexed, created_at
            FROM uploaded_files
            WHERE user_id = ?
            ORDER BY datetime(created_at) DESC, id DESC
            """,
            (user_id,),
        ).fetchall()
    files = rows_to_dicts(rows)
    for item in files:
        item["indexed"] = bool(item.get("indexed"))
    return files


def inspect_zip_contents(file_path: str) -> dict[str, Any]:
    p = Path(file_path)
    if not p.exists():
        raise ValueError("Archivo no encontrado.")
    if p.suffix.lower() != ".zip":
        raise ValueError("El archivo no es un ZIP.")
    entries = []
    try:
        with zipfile.ZipFile(p, "r") as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                entries.append({"name": info.filename, "size": info.file_size})
    except zipfile.BadZipFile as exc:
        raise ValueError("ZIP corrupto o invalido.") from exc
    return {"ok": True, "count": len(entries), "files": entries}


def extract_zip_to_dir(file_path: str, dest_dir: str) -> str:
    p = Path(file_path)
    if not p.exists() or p.suffix.lower() != ".zip":
        raise ValueError("Archivo no encontrado o no es ZIP.")
    uid = uuid.uuid4().hex
    target = Path(dest_dir) / uid
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(p, "r") as z:
        # Prevent Zip Slip by validating filenames
        for member in z.namelist():
            member_path = Path(member)
            if member_path.is_absolute() or ".." in member_path.parts:
                continue
        z.extractall(path=target)
    return str(target)
