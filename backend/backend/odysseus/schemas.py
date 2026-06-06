from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    message: str = ""
    upload_path: str | None = None
    model: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class FileSearchRequest(BaseModel):
    query: str = ""
    session_id: str | None = None
    max_results: int = 30


class FileReadRequest(BaseModel):
    path: str
    max_chars: int = 20000


class ZipInspectRequest(BaseModel):
    path: str


class ToolRunRequest(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
