from __future__ import annotations

from typing import Any

from services.conversation_resolver import resolve_follow_up_message


def resolve_user_request(current_message: str, history: list[dict[str, Any]] | None) -> str:
    """
    Convierte mensajes incompletos en solicitudes completas usando el historial.
    Si no existe historial suficiente, devuelve el mensaje original para que el
    router pida una aclaracion breve en vez de producir un rechazo falso.
    """
    return resolve_follow_up_message(current_message, history)
