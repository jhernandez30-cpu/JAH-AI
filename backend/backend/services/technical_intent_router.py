from __future__ import annotations

import re
from typing import Any

from services.code_interpreter_router import analyze_code_request, detect_code_language
from services.conversation_context import resolve_user_request
from services.conversation_resolver import is_ambiguous_follow_up, normalize_text


def detect_technical_intent(message: str, history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """
    Router tecnico principal para programacion, SQL, C#, Python, ciberseguridad
    defensiva, arquitectura, debugging y estructuras logicas.
    """
    original = str(message or "").strip()
    resolved = resolve_user_request(original, history)
    text = normalize_text(resolved)
    original_text = normalize_text(original)
    code_info = analyze_code_request(resolved)
    is_follow_up = bool(resolved != original or is_ambiguous_follow_up(original))
    needs_clarification = is_follow_up and resolved == original and not _has_target(text)

    intent = "general_technical_question"
    resolved_intent = ""
    if needs_clarification:
        intent = "follow_up_request"
    elif _is_database_design(text):
        intent = "database_design"
    elif _is_sql(text):
        intent = "sql"
    elif _is_er_model(text):
        intent = "er_model"
    elif _is_api(text):
        intent = "api_generation"
    elif _is_crud(text):
        intent = "crud_generation"
    elif _is_code_debugging(text, code_info):
        intent = "code_debugging"
    elif _is_cyber_defensive(text):
        intent = "cybersecurity_defensive"
    elif _is_cyber_analysis(text):
        intent = "cybersecurity_analysis"
    elif _is_code_review(text):
        intent = "code_review"
    elif _is_code_explanation(text, code_info):
        intent = "code_explanation"
    elif _is_project_structure(text):
        intent = "project_structure"
    elif _is_algorithm_design(text):
        intent = "algorithm_design"
    elif _is_logical_structure(text):
        intent = "logical_structure"
    elif _is_backend_architecture(text):
        intent = "backend_architecture"
    elif _is_frontend(text):
        intent = "frontend_development"
    elif _is_streamlit(text):
        intent = "streamlit_help"
    elif _is_fastapi(text):
        intent = "fastapi_help"
    elif _is_flask(text):
        intent = "flask_help"
    elif _is_powerbi(text):
        intent = "powerbi_help"
    elif _is_n8n(text):
        intent = "n8n_help"
    elif _is_csharp(text):
        intent = "csharp"
    elif _is_python(text):
        intent = "python"
    elif _is_code_generation(text):
        intent = "code_generation"
    elif _is_programming(text):
        intent = "programming_help"

    if is_follow_up and intent != "follow_up_request":
        resolved_intent = intent
        if normalize_text(original) in {"quiero que me la crees", "quiero que me lo crees", "hazlo", "creala", "crealo"}:
            intent = "follow_up_request"

    language = _detect_language(text, code_info, intent)
    domain = _detect_domain(text)
    requires_code = intent in {
        "database_design",
        "sql",
        "crud_generation",
        "api_generation",
        "code_generation",
        "python",
        "csharp",
        "fastapi_help",
        "flask_help",
        "streamlit_help",
    } or bool(re.search(r"\b(crea|crear|creame|dame|haz|hazme|genera|generar|construir)\b", original_text) and _has_target(text))

    return {
        "intent": intent,
        "resolved_intent": resolved_intent,
        "domain": domain,
        "language": language,
        "dialect": _detect_sql_dialect(text),
        "requires_code": requires_code,
        "requires_explanation": intent in {"code_explanation", "code_debugging", "code_review"} or "explica" in text,
        "requires_context": intent in {"code_debugging", "code_review", "code_explanation"} and not code_info.get("has_code"),
        "requires_schema": intent in {"database_design", "sql", "er_model"},
        "is_follow_up": is_follow_up,
        "references_previous_message": is_follow_up,
        "resolved_request": resolved if resolved != original else "",
        "needs_clarification": needs_clarification,
        "safe_category": "allowed_technical_request",
        "safe": True,
        "code": code_info,
        "confidence": 0.55 if needs_clarification else (0.95 if intent != "general_technical_question" else 0.7),
    }


def _is_database_design(text: str) -> bool:
    return bool(re.search(r"\b(base de datos|database|modelo entidad|entidad relacion|modelo er|esquema de datos)\b", text))


def _is_sql(text: str) -> bool:
    return bool(re.search(r"\b(sql|create table|tablas|tabla|mysql|postgres|postgresql|sqlite|ventas|inventario)\b", text))


def _is_er_model(text: str) -> bool:
    return bool(re.search(r"\b(modelo entidad relacion|entidad relacion|diagrama er|modelo er|erd)\b", text))


def _is_crud(text: str) -> bool:
    return bool(re.search(r"\b(crud|crear leer actualizar eliminar|altas bajas cambios)\b", text))


def _is_api(text: str) -> bool:
    return bool(re.search(r"\b(api|endpoint|rest|fastapi|flask|django|express)\b", text) and re.search(r"\b(crea|haz|dame|genera|productos|login|backend)\b", text))


def _is_code_debugging(text: str, code_info: dict[str, Any]) -> bool:
    return bool(re.search(r"\b(error|traceback|exception|corrige|arregla|debug|falla|no funciona|por que da error)\b", text))


def _is_code_review(text: str) -> bool:
    return bool(re.search(r"\b(revisa|review|audita|mejora|optimiza|hazlo mas seguro|vulnerabilidades en este codigo)\b", text))


def _is_code_explanation(text: str, code_info: dict[str, Any]) -> bool:
    return bool(re.search(r"\b(explica|explicame|que hace|como funciona|interpreta)\b", text) and (code_info.get("has_code") or "codigo" in text))


def _is_cyber_defensive(text: str) -> bool:
    return bool(
        re.search(r"\b(login seguro|hash|jwt|sql injection|xss|csrf|owasp|hardening|protejo|seguridad en api|checklist de seguridad|vulnerabilidades)\b", text)
        and not re.search(r"\b(robar|phishing|malware|ransomware|exfiltrar|sin permiso)\b", text)
    )


def _is_cyber_analysis(text: str) -> bool:
    return bool(re.search(r"\b(ciberseguridad|seguridad|auditoria|riesgos|vulnerabilidad|vulnerabilidades)\b", text))


def _is_logical_structure(text: str) -> bool:
    return bool(re.search(r"\b(estructura logica|logica|flujo|paso a paso|aprender programacion desde cero|aprender desde cero)\b", text))


def _is_algorithm_design(text: str) -> bool:
    return bool(re.search(r"\b(algoritmo|pseudocodigo|pseudocódigo|complejidad|estructura de datos)\b", text))


def _is_project_structure(text: str) -> bool:
    return bool(re.search(r"\b(estructura del proyecto|carpetas|arquitectura de proyecto|scaffold|plantilla de proyecto)\b", text))


def _is_backend_architecture(text: str) -> bool:
    return bool(re.search(r"\b(backend|arquitectura backend|servicios|repositorios|controladores|capas)\b", text))


def _is_frontend(text: str) -> bool:
    return bool(re.search(r"\b(frontend|html|css|javascript|react|vue|angular|pagina web|interfaz)\b", text))


def _is_streamlit(text: str) -> bool:
    return bool(re.search(r"\b(streamlit|st\.|session_state|chat_input)\b", text))


def _is_fastapi(text: str) -> bool:
    return bool(re.search(r"\b(fastapi|uvicorn|pydantic)\b", text))


def _is_flask(text: str) -> bool:
    return bool(re.search(r"\b(flask|jinja|blueprint)\b", text))


def _is_powerbi(text: str) -> bool:
    return bool(re.search(r"\b(power bi|dax|power query|dashboard|medida)\b", text))


def _is_n8n(text: str) -> bool:
    return bool(re.search(r"\b(n8n|workflow|webhook|automatizacion)\b", text))


def _is_csharp(text: str) -> bool:
    return bool(re.search(r"\b(c#|csharp|\.net|asp\.net|blazor|clase en c)\b", text))


def _is_python(text: str) -> bool:
    return bool(re.search(r"\b(python|py|pip|pytest|pandas|fastapi|flask|django)\b", text))


def _is_code_generation(text: str) -> bool:
    return bool(re.search(r"\b(crea|crear|creame|haz|hazme|genera|dame)\b", text) and re.search(r"\b(codigo|script|clase|funcion|app|programa)\b", text))


def _is_programming(text: str) -> bool:
    return bool(re.search(r"\b(programacion|codigo|software|desarrollo|clase|funcion|lenguaje)\b", text))


def _detect_language(text: str, code_info: dict[str, Any], intent: str) -> str:
    code_language = code_info.get("language") or detect_code_language(text)
    if code_language:
        return code_language
    if _is_csharp(text):
        return "csharp"
    if _is_python(text):
        return "python"
    if _is_sql(text) or intent in {"database_design", "sql", "er_model"}:
        return "sql"
    if _is_frontend(text):
        return "javascript" if "javascript" in text or "react" in text else "html_css"
    return ""


def _detect_domain(text: str) -> str:
    if re.search(r"\b(panaderia|panaderia|bakery|pan|pastel|reposteria)\b", text):
        return "panaderia"
    if re.search(r"\b(productos|producto)\b", text):
        return "productos"
    if re.search(r"\b(clientes|cliente)\b", text):
        return "clientes"
    if re.search(r"\b(ventas|inventario|stock)\b", text):
        return "ventas_inventario"
    return "general"


def _detect_sql_dialect(text: str) -> str:
    if "postgres" in text or "postgresql" in text:
        return "postgresql"
    if "sqlite" in text:
        return "sqlite"
    if "sql server" in text or "mssql" in text:
        return "sqlserver"
    return "mysql"


def _has_target(text: str) -> bool:
    return bool(
        re.search(
            r"\b(base de datos|database|sql|tabla|tablas|crud|api|codigo|clase|python|c#|"
            r"login|productos|clientes|panaderia|estructura|programacion|error)\b",
            text,
        )
    )
