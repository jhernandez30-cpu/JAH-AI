from __future__ import annotations

import re
from typing import Any

from services.conversation_resolver import normalize_text


TECHNICAL_ALLOWED_RE = re.compile(
    r"\b(programacion|codigo|script|base de datos|database|sql|tabla|tablas|crud|api|"
    r"frontend|backend|html|css|javascript|python|java|c#|php|streamlit|fastapi|flask|"
    r"diagrama|modelo entidad|entidad relacion|arquitectura|algoritmo|ejercicio|clase|"
    r"aprendizaje|aprender|lenguajes|power bi|n8n|automatizacion|documentacion)\b",
    re.IGNORECASE,
)

DANGEROUS_CYBER_RE = re.compile(
    r"\b(robar|extraer|exfiltrar|filtrar|hackear|tumbar|derribar|ddos|phishing|keylogger|"
    r"ransomware|malware|troyano|botnet|evadir antivirus|bypass|crackear|credenciales|"
    r"cookie de sesion|tarjeta de credito)\b",
    re.IGNORECASE,
)

DEFENSIVE_CYBER_RE = re.compile(
    r"\b(aprender|explicar|defensivo|defensa|hardening|owasp|auditoria autorizada|laboratorio|"
    r"ctf|vulnerable|vulnerabilidad|vulnerabilidades|login|demo local|educativo|mitigar|prevenir|detectar|seguro|seguridad)\b",
    re.IGNORECASE,
)

GENERAL_HARM_RE = re.compile(
    r"\b(fabricar bomba|explosivo|arma casera|veneno|matar|asesinar|secuestro|fraude|estafa|"
    r"lavado de dinero|falsificar documentos|robar identidad|droga ilegal)\b",
    re.IGNORECASE,
)

MINOR_EXPLOITATION_RE = re.compile(
    r"\b(menor|menores|nino|niño|nina|niña|adolescente)\b.*\b(sexual|desnudo|desnuda|"
    r"explotacion|explotación|abuso|pornografia|pornografía)\b",
    re.IGNORECASE,
)


def classify_safety(
    message: str,
    intent: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Clasifica si la solicitud es segura.
    Las solicitudes normales de programacion, bases de datos y aprendizaje deben
    permitirse aunque contengan palabras como crear, usuarios, clientes o datos.
    """
    text = normalize_text(message)
    intent = intent or {}

    if _contains_minor_exploitation(text):
        return {"allowed": False, "reason": "minor_exploitation", "confidence": 0.98}

    if _contains_general_harm(text):
        return {"allowed": False, "reason": "harmful_or_illegal_request", "confidence": 0.96}

    if _contains_dangerous_cyber(text) and not _is_defensive_cyber_context(text):
        return {"allowed": False, "reason": "dangerous_cyber_request", "confidence": 0.93}

    if is_safe_programming_request(message, intent):
        return {"allowed": True, "reason": "programming_request", "confidence": 0.95}

    return {"allowed": True, "reason": "general_allowed", "confidence": 0.82}


def is_safe_programming_request(message: str, intent: dict[str, Any] | None = None) -> bool:
    """
    Devuelve True para solicitudes tecnicas normales: programacion, bases de
    datos, diseno web, APIs, scripts seguros, automatizacion, aprendizaje y
    tareas academicas.
    """
    text = normalize_text(message)
    intent_name = str((intent or {}).get("intent") or "")

    technical_intents = {
        "database_design",
        "sql",
        "sql_generation",
        "er_model",
        "crud_generation",
        "api_generation",
        "programming_help",
        "code_generation",
        "code_explanation",
        "code_debugging",
        "code_review",
        "software_architecture",
        "backend_architecture",
        "frontend_development",
        "logical_structure",
        "algorithm_design",
        "project_structure",
        "streamlit_help",
        "fastapi_help",
        "flask_help",
        "python",
        "csharp",
        "learning_path",
        "web_development",
        "api_development",
        "power_bi",
        "powerbi_help",
        "n8n",
        "n8n_help",
        "general_technical_question",
        "follow_up_request",
    }
    if intent_name in technical_intents:
        return True

    if intent_name in {"cybersecurity", "cybersecurity_defensive", "cybersecurity_analysis"} and _is_defensive_cyber_context(text):
        return True

    if TECHNICAL_ALLOWED_RE.search(text):
        return True

    return False


def is_allowed_technical_request(message: str, intent: dict[str, Any] | None = None) -> bool:
    return is_safe_programming_request(message, intent)


def safe_refusal_only_if_really_needed(reason: str = "harmful_or_illegal_request") -> str:
    if reason == "dangerous_cyber_request":
        return (
            "No puedo ayudar a crear, ejecutar o facilitar una accion de ciberseguridad ofensiva o no autorizada. "
            "Si quieres, puedo convertirlo en una version segura: analisis defensivo, hardening, deteccion, laboratorio local o mitigacion."
        )
    if reason == "minor_exploitation":
        return "No puedo ayudar con contenido de explotacion o abuso de menores."
    return (
        "No puedo ayudar con instrucciones para dano real, fraude o actividad ilegal. "
        "Puedo ayudarte con una alternativa segura, educativa o defensiva."
    )


def _contains_minor_exploitation(text: str) -> bool:
    return bool(MINOR_EXPLOITATION_RE.search(text))


def _contains_general_harm(text: str) -> bool:
    return bool(GENERAL_HARM_RE.search(text))


def _contains_dangerous_cyber(text: str) -> bool:
    return bool(DANGEROUS_CYBER_RE.search(text))


def _is_defensive_cyber_context(text: str) -> bool:
    return bool(DEFENSIVE_CYBER_RE.search(text)) and not re.search(
        r"\b(real|victima|sin permiso|cuenta ajena|tercero|produccion)\b",
        text,
    )
