from __future__ import annotations

import re
import unicodedata


TOKEN_RE = re.compile(r"[a-z0-9_#+.-]+", re.IGNORECASE)


PROGRAMMING_SKILLS = [
    {
        "key": "web_fullstack",
        "label": "Sitios y apps web",
        "triggers": {
            "web",
            "sitio",
            "pagina",
            "frontend",
            "backend",
            "fullstack",
            "html",
            "css",
            "javascript",
            "react",
            "streamlit",
            "flask",
            "fastapi",
            "api",
            "dashboard",
            "landing",
        },
        "guidance": [
            "Convierte ideas ambiguas en pantallas, rutas, componentes, endpoints y flujo de datos.",
            "Propone una estructura de carpetas completa antes de escribir codigo extenso.",
            "Incluye comandos de instalacion/ejecucion y una prueba manual de humo.",
        ],
        "deliverables": [
            "arquitectura",
            "estructura de carpetas",
            "frontend",
            "backend/API",
            "comandos",
            "validacion",
        ],
    },
    {
        "key": "software_architecture",
        "label": "Arquitectura de software",
        "triggers": {
            "arquitectura",
            "estructura",
            "sistema",
            "software",
            "modulos",
            "modulo",
            "integracion",
            "integrar",
            "conectar",
            "conecta",
            "conecte",
            "conexion",
            "cerebro",
            "capas",
            "servicios",
            "microservicios",
            "monolito",
            "patron",
            "proyecto",
        },
        "guidance": [
            "Define limites claros entre dominio, datos, interfaz, integraciones y pruebas.",
            "Prefiere una arquitectura simple y evolucionable antes que una compleja sin necesidad.",
            "Explica decisiones con criterio de mantenimiento, rendimiento, seguridad y extensibilidad.",
        ],
        "deliverables": [
            "componentes",
            "contratos",
            "decisiones",
            "riesgos",
            "roadmap",
        ],
    },
    {
        "key": "database_design",
        "label": "Bases de datos",
        "triggers": {
            "base",
            "datos",
            "database",
            "sql",
            "sqlite",
            "postgres",
            "mysql",
            "tabla",
            "tablas",
            "modelo",
            "schema",
            "relacion",
            "normalizacion",
            "consulta",
            "crud",
        },
        "guidance": [
            "Identifica entidades, relaciones, claves, indices y restricciones.",
            "Incluye DDL SQL cuando el usuario pide implementar una base.",
            "Advierte sobre integridad, migraciones, seguridad de datos y consultas costosas.",
        ],
        "deliverables": [
            "modelo entidad-relacion",
            "DDL SQL",
            "indices",
            "consultas",
            "migraciones",
        ],
    },
    {
        "key": "code_review",
        "label": "Revision y mejora de codigo",
        "triggers": {
            "revisa",
            "revision",
            "review",
            "mejora",
            "refactor",
            "refactoriza",
            "optimiza",
            "limpia",
            "mejorar",
            "calidad",
            "codigo",
            "code",
        },
        "guidance": [
            "Prioriza bugs de correctitud, seguridad, rendimiento y mantenibilidad.",
            "Da observaciones accionables y, cuando haya codigo concreto, propone cambios puntuales.",
            "Evita recomendaciones cosmeticas si no reducen riesgo o confusion.",
        ],
        "deliverables": [
            "hallazgos",
            "riesgo",
            "cambio sugerido",
            "pruebas",
        ],
    },
    {
        "key": "debugging",
        "label": "Depuracion",
        "triggers": {
            "bug",
            "error",
            "traceback",
            "fallo",
            "falla",
            "debug",
            "depura",
            "excepcion",
            "exception",
            "no funciona",
            "rompe",
        },
        "guidance": [
            "Sigue el ciclo observar, formular hipotesis, probar y corregir.",
            "Pide el traceback o fragmento minimo si no existe suficiente contexto.",
            "Propone comandos o pruebas pequenas para confirmar la causa raiz.",
        ],
        "deliverables": [
            "causa probable",
            "prueba de confirmacion",
            "fix minimo",
            "prevencion",
        ],
    },
    {
        "key": "testing_quality",
        "label": "Pruebas y calidad",
        "triggers": {
            "test",
            "tests",
            "prueba",
            "pruebas",
            "pytest",
            "unittest",
            "qa",
            "validar",
            "verificar",
            "cobertura",
        },
        "guidance": [
            "Propone pruebas unitarias, integracion y humo segun el riesgo.",
            "Incluye casos felices, bordes y errores esperados.",
            "Conecta cada prueba con el comportamiento que protege.",
        ],
        "deliverables": [
            "plan de pruebas",
            "casos",
            "comandos",
            "criterios de aceptacion",
        ],
    },
    {
        "key": "security",
        "label": "Seguridad",
        "triggers": {
            "seguridad",
            "security",
            "vulnerabilidad",
            "owasp",
            "auth",
            "login",
            "password",
            "token",
            "secreto",
            "inyeccion",
            "xss",
            "csrf",
        },
        "guidance": [
            "Revisa entradas, autenticacion, autorizacion, secretos, sesiones y exposicion de datos.",
            "Separa vulnerabilidades confirmadas de riesgos probables.",
            "Recomienda mitigaciones concretas sin instrucciones de explotacion.",
        ],
        "deliverables": [
            "riesgos",
            "controles",
            "mitigaciones",
            "validacion segura",
        ],
    },
    {
        "key": "documentation",
        "label": "Documentacion y entrega",
        "triggers": {
            "readme",
            "documenta",
            "documentacion",
            "manual",
            "guia",
            "docs",
            "entrega",
            "instalacion",
        },
        "guidance": [
            "Produce README, pasos de instalacion, uso, variables de entorno y decisiones importantes.",
            "Incluye ejemplos minimos de comandos y flujo de usuario.",
            "Deja claro que falta configurar o probar.",
        ],
        "deliverables": [
            "README",
            "comandos",
            "variables",
            "uso",
            "troubleshooting",
        ],
    },
]


DEFAULT_SKILL_KEYS = ["software_architecture", "web_fullstack", "database_design", "code_review"]


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _tokens(text: str) -> set[str]:
    normalized = _strip_accents(text).lower()
    return {token.lower() for token in TOKEN_RE.findall(normalized)}


def detect_programming_skills(question: str, limit: int = 4) -> list[dict]:
    normalized_question = _strip_accents(question).lower()
    tokens = _tokens(question)
    scored = []
    for skill in PROGRAMMING_SKILLS:
        matches = tokens & skill["triggers"]
        phrase_boost = sum(
            1
            for trigger in skill["triggers"]
            if " " in trigger and trigger in normalized_question
        )
        score = len(matches) + phrase_boost
        if score:
            scored.append((score, skill))

    if not scored:
        scored = [
            (1, skill)
            for skill in PROGRAMMING_SKILLS
            if skill["key"] in DEFAULT_SKILL_KEYS
        ]

    scored.sort(key=lambda item: (item[0], item[1]["label"]), reverse=True)
    return [skill for _, skill in scored[:limit]]


def build_programming_skills_context(question: str) -> str:
    skills = detect_programming_skills(question)
    lines = [
        "Habilidades internas de programacion activas:",
    ]
    for skill in skills:
        lines.append(f"- {skill['label']} ({skill['key']})")
        lines.append(f"  Guia: {' '.join(skill['guidance'][:2])}")
        lines.append(f"  Entregables esperados: {', '.join(skill['deliverables'])}.")

    lines.extend(
        [
            "Reglas de entrega para software:",
            "- Si el usuario pide crear un producto, responde con arquitectura, estructura de carpetas, archivos principales, base de datos si aplica, comandos y validacion.",
            "- Si el usuario pide revisar o mejorar codigo, empieza por hallazgos y riesgos antes de sugerir cambios.",
            "- Si hay contexto de proyecto, respeta su tecnologia y estilo antes de proponer librerias nuevas.",
            "- Si faltan archivos, stack o error exacto, pide solo el dato minimo que desbloquea la respuesta.",
            "- Para codigo extenso, divide por archivos y prioriza un MVP funcional antes de extras.",
        ]
    )
    return "\n".join(lines)


def get_programming_skill_catalog() -> list[dict]:
    return [
        {
            "key": skill["key"],
            "label": skill["label"],
            "deliverables": skill["deliverables"],
        }
        for skill in PROGRAMMING_SKILLS
    ]
