from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RegisterPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8)


class LoginPayload(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1)


class ProfilePayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class PreferencesPayload(BaseModel):
    theme: str | None = None
    use_rag: bool | None = None
    use_web: bool | None = None
    deep_thinking: bool | None = None
    jarvis_voice: bool | None = None
    language: str | None = None
    response_style: str | None = None
    assistant_preference: str | None = None
    visible_name: str | None = None
    direct_answers: bool | None = None
    chat_history_enabled: bool | None = None


class ChatSessionPayload(BaseModel):
    title: str = "Nueva conversación"
    session_id: str | None = None


class ChatHistoryPayload(BaseModel):
    session_id: str
    role: str
    content: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    mode: str | None = None
