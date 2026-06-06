from __future__ import annotations

import re
from typing import Any

from services.conversation_resolver import (
    is_ambiguous_follow_up,
    normalize_text,
    resolve_follow_up_message,
)


CREATE_RE = re.compile(r"\b(crea|crear|creame|créame|generar|genera|dame|hacer|haz|hazme|construir|disena|diseña)\b", re.IGNORECASE)


def detect_intent(message: str, history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """
    Detecta la intencion tecnica del usuario y devuelve metadatos utiles para
    seguridad, recuperacion de contexto y seleccion de plantilla.
    """
    original = str(message or "").strip()
    resolved = resolve_follow_up_message(original, history)
    text = normalize_text(resolved)
    original_text = normalize_text(original)
    references_previous = bool(resolved != original or is_ambiguous_follow_up(original))
    needs_clarification = references_previous and resolved == original and not _has_concrete_target(text)

    intent = "general_question"
    if needs_clarification:
        intent = "general_question"
    elif _is_er_model(text):
        intent = "er_model"
    elif _is_sql_generation(text):
        intent = "sql_generation"
    elif _is_database_design(text):
        intent = "database_design"
    elif _is_crud_generation(text):
        intent = "crud_generation"
    elif _is_code_debugging(text):
        intent = "code_debugging"
    elif _is_api_development(text):
        intent = "api_development"
    elif _is_web_development(text):
        intent = "web_development"
    elif _is_software_architecture(text):
        intent = "software_architecture"
    elif _is_learning_path(text):
        intent = "learning_path"
    elif _is_power_bi(text):
        intent = "power_bi"
    elif _is_n8n(text):
        intent = "n8n"
    elif _is_cybersecurity(text):
        intent = "cybersecurity"
    elif _is_code_generation(text):
        intent = "code_generation"
    elif _is_programming_help(text):
        intent = "programming_help"

    domain = _detect_domain(text)
    language = _detect_language(text, intent)
    dialect = _detect_sql_dialect(text)
    requires_schema = intent in {"database_design", "sql_generation", "er_model"} or bool(
        re.search(r"\b(estructura|modelo|tablas|relaciones|schema|esquema)\b", text)
    )
    requires_code = intent in {
        "database_design",
        "sql_generation",
        "crud_generation",
        "code_generation",
        "api_development",
        "web_development",
    } or bool(CREATE_RE.search(original_text) and _has_technical_target(text))

    return {
        "intent": intent,
        "domain": domain,
        "language": language,
        "dialect": dialect,
        "requires_code": requires_code,
        "requires_schema": requires_schema,
        "references_previous_message": references_previous,
        "resolved_request": resolved if resolved != original else "",
        "needs_clarification": needs_clarification,
        "safe": True,
        "confidence": _confidence(intent, needs_clarification),
    }


def _is_database_design(text: str) -> bool:
    return bool(
        re.search(r"\b(base de datos|database|modelo de base|modelo entidad|entidad relacion|er|esquema)\b", text)
        and re.search(r"\b(estructura|disenar|disena|crear|creame|generar|dame|hacer|tablas|relaciones)\b", text)
    )


def _is_sql_generation(text: str) -> bool:
    return bool(
        re.search(r"\b(sql|create table|tablas|tabla|mysql|postgres|postgresql|sqlite)\b", text)
        and re.search(r"\b(crear|creame|genera|generar|dame|haz|hazme|script|estructura|productos|ventas|inventario)\b", text)
    )


def _is_er_model(text: str) -> bool:
    return bool(re.search(r"\b(modelo entidad relacion|entidad relacion|diagrama er|modelo er|erd)\b", text))


def _is_crud_generation(text: str) -> bool:
    return bool(re.search(r"\b(crud|altas bajas cambios|crear leer actualizar eliminar)\b", text))


def _is_code_debugging(text: str) -> bool:
    return bool(re.search(r"\b(error|traceback|exception|bug|debug|depurar|fallo|no funciona|stack trace)\b", text))


def _is_software_architecture(text: str) -> bool:
    return bool(re.search(r"\b(arquitectura|patron|capas|microservicios|monolito|modular|refactor|diseno de software)\b", text))


def _is_learning_path(text: str) -> bool:
    return bool(
        re.search(r"\b(ruta|camino|estructura|plan|temario|aprender desde cero|desde cero)\b", text)
        and re.search(r"\b(aprender|lenguajes de programacion|programacion|python|javascript|java|c#|sql)\b", text)
    )


def _is_web_development(text: str) -> bool:
    return bool(re.search(r"\b(frontend|pagina web|sitio web|html|css|javascript|typescript|react|vue|angular)\b", text))


def _is_api_development(text: str) -> bool:
    return bool(re.search(r"\b(api|rest|endpoint|backend|fastapi|flask|django|express)\b", text))


def _is_cybersecurity(text: str) -> bool:
    return bool(re.search(r"\b(ciberseguridad|seguridad|owasp|vulnerabilidad|hardening|xss|csrf|inyeccion sql|pentest)\b", text))


def _is_power_bi(text: str) -> bool:
    return bool(re.search(r"\b(power bi|dax|power query|dashboard|medida|reporte bi)\b", text))


def _is_n8n(text: str) -> bool:
    return bool(re.search(r"\b(n8n|workflow|automatizacion|rpa|webhook)\b", text))


def _is_code_generation(text: str) -> bool:
    return bool(
        CREATE_RE.search(text)
        and re.search(r"\b(codigo|script|programa|clase|funcion|app|aplicacion|python|javascript|java|c#|php)\b", text)
    )


def _is_programming_help(text: str) -> bool:
    return bool(re.search(r"\b(programacion|codigo|software|algoritmo|funcion|clase|variable|lenguaje)\b", text))


def _detect_domain(text: str) -> str:
    if re.search(r"\b(panaderia|bakery|pan|pastel|reposteria)\b", text):
        return "bakery"
    if re.search(r"\b(productos|ventas|inventario|stock)\b", text):
        return "products_sales_inventory"
    if re.search(r"\b(lenguajes de programacion|programacion desde cero|aprender programacion)\b", text):
        return "programming_languages"
    if re.search(r"\b(clientes|proveedores|empleados|negocio|tienda)\b", text):
        return "business"
    return "general"


def _detect_language(text: str, intent: str) -> str:
    language_patterns = [
        ("python", r"\b(python|py|fastapi|flask|django)\b"),
        ("javascript", r"\b(javascript|js|typescript|node|react|vue|angular)\b"),
        ("csharp", r"\b(c#|csharp|asp\.net|blazor|\.net)\b"),
        ("java", r"\b(java|spring)\b"),
        ("php", r"\b(php|laravel)\b"),
        ("sql", r"\b(sql|mysql|postgres|postgresql|sqlite|base de datos|tabla|tablas)\b"),
    ]
    for language, pattern in language_patterns:
        if re.search(pattern, text):
            return language
    if intent in {"database_design", "sql_generation", "er_model"}:
        return "sql"
    return ""


def _detect_sql_dialect(text: str) -> str:
    if re.search(r"\b(postgres|postgresql)\b", text):
        return "postgresql"
    if re.search(r"\bsqlite\b", text):
        return "sqlite"
    if re.search(r"\b(sql server|mssql)\b", text):
        return "sqlserver"
    return "mysql"


def _has_concrete_target(text: str) -> bool:
    return bool(
        re.search(
            r"\b(base de datos|database|sql|tabla|tablas|crud|api|pagina|web|codigo|app|"
            r"lenguajes|programacion|productos|ventas|inventario|panaderia)\b",
            text,
        )
    )


def _has_technical_target(text: str) -> bool:
    return _has_concrete_target(text) or bool(
        re.search(r"\b(frontend|backend|script|diagrama|modelo|ejercicio|clase|funcion)\b", text)
    )


def _confidence(intent: str, needs_clarification: bool) -> float:
    if needs_clarification:
        return 0.55
    if intent == "general_question":
        return 0.62
    return 0.92
