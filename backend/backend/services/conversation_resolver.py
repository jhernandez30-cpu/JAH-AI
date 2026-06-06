from __future__ import annotations

import re
import unicodedata
from typing import Any


AMBIGUOUS_FOLLOW_UP_RE = re.compile(
    r"^\s*(si|sí|ok|dale|hazlo|hagalo|hazmelo|hazmela|crealo|créalo|creala|créala|"
    r"corrigelo|corrígelo|arreglalo|arréglalo|revisalo|revísalo|explicalo|explícalo|"
    r"quiero que me la crees|quiero que me lo crees|damela completa|dámela completa|"
    r"completa|completo|ahora en sql|en sql|con tablas|con relaciones|con llaves|"
    r"agrega\s+[\w\s]+|añade\s+[\w\s]+)\s*[.!?]*\s*$",
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    text = str(text or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


def is_ambiguous_follow_up(message: str) -> bool:
    text = normalize_text(message)
    if not text:
        return False
    if AMBIGUOUS_FOLLOW_UP_RE.match(str(message or "")):
        return True
    if len(text.split()) <= 5 and re.search(r"\b(la|lo|eso|esa|ese|hacer|crear|completa|tablas|sql)\b", text):
        return True
    return False


def resolve_follow_up_message(current_message: str, history: list[dict[str, Any]] | None) -> str:
    """
    Resuelve mensajes como 'hazlo', 'creala' o 'quiero que me la crees'
    usando el historial reciente. Si no hay referente claro, devuelve el
    mensaje original para que el flujo pida aclaracion sin rechazarlo.
    """
    current = str(current_message or "").strip()
    if not current:
        return current

    if not is_ambiguous_follow_up(current):
        return current

    recent_text = _recent_history_text(history)
    if not recent_text:
        return current

    topic = _infer_previous_request(recent_text)
    if not topic:
        return current

    normalized = normalize_text(current)
    additions = []
    if "ahora en sql" in normalized or normalized == "en sql" or "con tablas" in normalized:
        additions.append("Entregarlo en SQL ejecutable con tablas y relaciones.")
    if "agrega" in normalized or "anade" in normalized:
        if "login" in normalized and re.search(r"\b(api|fastapi|backend)\b", normalize_text(topic)):
            return topic.replace("con endpoints CRUD", "con autenticacion/login y endpoints CRUD")
        additions.append(f"Incluir tambien lo solicitado en el seguimiento: {current}.")
    if "completa" in normalized or "completo" in normalized:
        additions.append("Entregar la solucion completa, no solo una explicacion.")

    if additions:
        return f"{topic} {' '.join(additions)}"
    return topic


def _recent_history_text(history: list[dict[str, Any]] | None, max_messages: int = 8) -> str:
    if not history:
        return ""
    parts: list[str] = []
    for item in history[-max_messages:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").lower()
        content = str(item.get("content") or item.get("message") or "").strip()
        if not content:
            continue
        if role in {"human", "user", "estudiante"}:
            parts.append(f"Usuario: {content}")
        elif role in {"ai", "assistant", "tutor"}:
            parts.append(f"Asistente: {content}")
    return "\n".join(parts)


def _infer_previous_request(history_text: str) -> str:
    normalized = normalize_text(history_text)
    if not normalized:
        return ""

    domain = _infer_domain(normalized)
    has_database = bool(
        re.search(r"\b(base de datos|database|sql|tabla|tablas|modelo entidad|entidad relacion|inventario|ventas)\b", normalized)
    )
    if has_database:
        if domain == "bakery":
            return (
                "Crear una estructura completa de base de datos SQL para una panaderia, "
                "incluyendo tablas, claves primarias, claves foraneas, relaciones y script CREATE TABLE."
            )
        if domain == "products_sales_inventory":
            return (
                "Crear tablas SQL completas para productos, ventas e inventario, "
                "incluyendo claves primarias, claves foraneas, relaciones y script CREATE TABLE."
            )
        return (
            "Crear una estructura completa de base de datos SQL, incluyendo tablas, "
            "claves primarias, claves foraneas, relaciones y script CREATE TABLE."
        )

    if re.search(r"\b(api|fastapi|endpoint|backend)\b", normalized):
        if re.search(r"\b(productos|producto)\b", normalized):
            return "Crear una API en FastAPI para productos con endpoints CRUD, validacion y estructura ejecutable."
        return "Crear una API/backend con estructura, endpoints, validacion y codigo base."

    if re.search(r"\b(codigo|error|traceback|exception|no funciona|falla|debug)\b", normalized):
        return "Corregir el codigo compartido anteriormente, explicando la causa del error y entregando una version corregida."

    if re.search(r"\b(crud|crear altas bajas cambios|productos)\b", normalized) and "python" in normalized:
        return "Crear un CRUD en Python para productos, incluyendo estructura, modelo de datos y codigo base."

    if re.search(r"\b(lenguajes de programacion|aprender desde cero|ruta de aprendizaje)\b", normalized):
        return "Crear una estructura de aprendizaje de lenguajes de programacion para aprender desde cero."

    if re.search(r"\b(frontend|pagina|web|html|css|javascript)\b", normalized):
        return "Crear una solucion web/frontend con estructura y codigo base."

    return ""


def _infer_domain(text: str) -> str:
    if re.search(r"\b(panaderia|panaderia|bakery|pan|pastel|reposteria)\b", text):
        return "bakery"
    if re.search(r"\b(productos|ventas|inventario|stock)\b", text):
        return "products_sales_inventory"
    return "general"
