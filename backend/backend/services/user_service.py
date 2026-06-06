from __future__ import annotations

from typing import Any

try:
    from ..database import db_session, row_to_dict
    from ..security import utc_now
except ImportError:  # pragma: no cover
    from database import db_session, row_to_dict  # type: ignore
    from security import utc_now  # type: ignore


THEMES = {"light", "dark", "system"}
LANGUAGES = {"es"}
RESPONSE_STYLES = {"directo", "explicativo", "tutor_paso_a_paso", "tecnico_avanzado"}
ASSISTANT_PREFERENCES = {"respuestas_cortas", "respuestas_completas", "respuestas_con_ejemplos"}

DEFAULT_PREFERENCES: dict[str, Any] = {
    "theme": "dark",
    "use_rag": True,
    "use_web": False,
    "deep_thinking": False,
    "jarvis_voice": False,
    "language": "es",
    "response_style": "explicativo",
    "assistant_preference": "respuestas_completas",
    "visible_name": "",
    "direct_answers": False,
    "chat_history_enabled": True,
}


def as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"", "0", "false", "no", "off"}


def normalize_preferences(data: dict[str, Any] | None, current: dict[str, Any] | None = None) -> dict[str, Any]:
    source = data or {}
    prefs = {**DEFAULT_PREFERENCES, **(current or {})}

    if source.get("theme") in THEMES:
        prefs["theme"] = source["theme"]
    if source.get("language") in LANGUAGES:
        prefs["language"] = source["language"]
    if source.get("response_style") in RESPONSE_STYLES:
        prefs["response_style"] = source["response_style"]
    if source.get("assistant_preference") in ASSISTANT_PREFERENCES:
        prefs["assistant_preference"] = source["assistant_preference"]
    if "visible_name" in source:
        prefs["visible_name"] = str(source.get("visible_name") or "").strip()[:80]

    for key in ("use_rag", "use_web", "deep_thinking", "jarvis_voice", "direct_answers", "chat_history_enabled"):
        if key in source and source[key] is not None:
            prefs[key] = as_bool(source[key], bool(prefs[key]))

    return prefs


def preferences_from_row(row: Any | None) -> dict[str, Any]:
    data = row_to_dict(row) if row else None
    if not data:
        return dict(DEFAULT_PREFERENCES)
    return {
        "theme": data.get("theme") or DEFAULT_PREFERENCES["theme"],
        "use_rag": as_bool(data.get("use_rag"), True),
        "use_web": as_bool(data.get("use_web"), False),
        "deep_thinking": as_bool(data.get("deep_thinking"), False),
        "jarvis_voice": as_bool(data.get("jarvis_voice"), False),
        "language": data.get("language") or "es",
        "response_style": data.get("response_style") or "explicativo",
        "assistant_preference": data.get("assistant_preference") or "respuestas_completas",
        "visible_name": data.get("visible_name") or "",
        "direct_answers": as_bool(data.get("direct_answers"), False),
        "chat_history_enabled": as_bool(data.get("chat_history_enabled"), True),
    }


def get_preferences(user_id: int) -> dict[str, Any]:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,)).fetchone()
        if row:
            return preferences_from_row(row)
        now = utc_now()
        prefs = dict(DEFAULT_PREFERENCES)
        conn.execute(
            """
            INSERT INTO user_preferences
            (user_id, theme, use_rag, use_web, deep_thinking, jarvis_voice, language,
             response_style, assistant_preference, visible_name, direct_answers,
             chat_history_enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                prefs["theme"],
                int(prefs["use_rag"]),
                int(prefs["use_web"]),
                int(prefs["deep_thinking"]),
                int(prefs["jarvis_voice"]),
                prefs["language"],
                prefs["response_style"],
                prefs["assistant_preference"],
                prefs["visible_name"],
                int(prefs["direct_answers"]),
                int(prefs["chat_history_enabled"]),
                now,
                now,
            ),
        )
        return prefs


def update_preferences(user_id: int, patch: dict[str, Any]) -> dict[str, Any]:
    current = get_preferences(user_id)
    prefs = normalize_preferences(patch, current)
    now = utc_now()
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO user_preferences
            (user_id, theme, use_rag, use_web, deep_thinking, jarvis_voice, language,
             response_style, assistant_preference, visible_name, direct_answers,
             chat_history_enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                theme=excluded.theme,
                use_rag=excluded.use_rag,
                use_web=excluded.use_web,
                deep_thinking=excluded.deep_thinking,
                jarvis_voice=excluded.jarvis_voice,
                language=excluded.language,
                response_style=excluded.response_style,
                assistant_preference=excluded.assistant_preference,
                visible_name=excluded.visible_name,
                direct_answers=excluded.direct_answers,
                chat_history_enabled=excluded.chat_history_enabled,
                updated_at=excluded.updated_at
            """,
            (
                user_id,
                prefs["theme"],
                int(prefs["use_rag"]),
                int(prefs["use_web"]),
                int(prefs["deep_thinking"]),
                int(prefs["jarvis_voice"]),
                prefs["language"],
                prefs["response_style"],
                prefs["assistant_preference"],
                prefs["visible_name"],
                int(prefs["direct_answers"]),
                int(prefs["chat_history_enabled"]),
                now,
                now,
            ),
        )
    return prefs
