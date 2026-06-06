from __future__ import annotations

from fastapi import HTTPException


SAFE_TOOL_WHITELIST = {
    "status",
    "analyze",
    "code",
    "debug",
    "plan",
    "list_files",
    "search_files",
    "read_file",
    "inspect_zip",
}

DANGEROUS_PATTERNS = (
    "rm -rf",
    "del /s",
    "format ",
    "shutdown",
    "powershell -",
    "cmd /c",
    "bash -c",
    "curl ",
    "wget ",
    "Invoke-WebRequest",
    "Start-Process",
)


def ensure_tool_allowed(tool_name: str) -> None:
    if str(tool_name or "").strip() not in SAFE_TOOL_WHITELIST:
        raise HTTPException(status_code=403, detail="Tool no permitida en modo seguro.")


def validate_command_safety(command: str) -> None:
    lower = str(command or "").lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern.lower() in lower:
            raise HTTPException(status_code=400, detail="Comando peligroso bloqueado.")
