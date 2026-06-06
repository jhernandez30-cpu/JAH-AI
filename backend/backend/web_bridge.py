from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from email import policy
from email.parser import BytesParser
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import chromadb
from chromadb.config import Settings
from langchain_ollama import OllamaLLM

BASE_DIR = Path(__file__).resolve().parent
LOGGER = logging.getLogger(__name__)


def path_from_env(value):
    return Path(value).expanduser() if value else None


def tutor_root_candidates():
    env_root = path_from_env(os.getenv("TUTOR_IA_ROOT"))
    if env_root:
        yield env_root

    yield Path.home() / "Documents" / "tutor_ia"
    yield BASE_DIR
    yield BASE_DIR.parent


def find_tutor_root():
    for candidate in tutor_root_candidates():
        try:
            candidate = candidate.resolve()
        except OSError:
            continue
        if (
            (candidate / "vectores" / "brain_db").exists()
            or (candidate / "conocimiento").exists()
            or (candidate / "backend" / "agency_brain.py").exists()
            or (candidate / "brain_db").exists()
            or (candidate / "Tutor_IA").exists()
            or (candidate / "agency_brain.py").exists()
        ):
            return candidate
    return BASE_DIR


TUTOR_ROOT = find_tutor_root()
BACKEND_ROOT = TUTOR_ROOT / "backend"
if BACKEND_ROOT.exists() and str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(TUTOR_ROOT) not in sys.path:
    sys.path.insert(0, str(TUTOR_ROOT))

try:
    from agency_brain import build_agency_context, get_agency_status, retrieve_agency_agents
except Exception:
    build_agency_context = None
    get_agency_status = None
    retrieve_agency_agents = None

try:
    from jarvis_brain import build_profile_context, build_unified_brain_context, get_jarvis_stack_summary
except Exception:
    build_profile_context = None
    build_unified_brain_context = None
    get_jarvis_stack_summary = None

try:
    from programming_skills import build_programming_skills_context
    from project_workspace import build_workspace_brain_context, retrieve_workspace_context
except Exception:
    build_programming_skills_context = None
    build_workspace_brain_context = None
    retrieve_workspace_context = None

try:
    from connected_brain import (
        build_connected_brain_context,
        build_quick_code_docs,
        retrieve_connected_workspace_docs,
    )
except Exception:
    build_connected_brain_context = None
    build_quick_code_docs = None
    retrieve_connected_workspace_docs = None

try:
    from local_model_router import AUTO_MODEL_OPTION, choose_local_model, get_model_plan
except Exception:
    AUTO_MODEL_OPTION = "Auto (Cerebro Unificado)"
    choose_local_model = None
    get_model_plan = None

try:
    from services.brain_orchestrator import notebooklm_result_to_doc, notebooklm_status_message
    from services.notebooklm_service import NotebookLMService
    from services.unified_brain import BrainSourceContext, UnifiedBrain
    from services.conversation_context import resolve_user_request
    from services.safety_filter import classify_safety, safe_refusal_only_if_really_needed
    from services.technical_generators import generate_technical_answer, should_use_technical_generator
    from services.technical_intent_router import detect_technical_intent
except Exception:
    notebooklm_result_to_doc = None
    notebooklm_status_message = None
    NotebookLMService = None
    BrainSourceContext = None
    UnifiedBrain = None
    resolve_user_request = None
    classify_safety = None
    safe_refusal_only_if_really_needed = None
    generate_technical_answer = None
    should_use_technical_generator = None
    detect_technical_intent = None


PERSIST_DIR = os.getenv("TUTOR_IA_PERSIST_DIR", str(TUTOR_ROOT / "vectores" / "brain_db"))
OBSIDIAN_VAULT_DIR = os.getenv("TUTOR_IA_OBSIDIAN_DIR", str(TUTOR_ROOT / "conocimiento"))
COLLECTION_NAME = os.getenv("TUTOR_IA_COLLECTION", "conocimiento_fast")
LLM_MODEL = os.getenv("TUTOR_IA_LLM_MODEL", "llama3.2:1b")
RECOMMENDED_OLLAMA_MODEL = os.getenv("TUTOR_IA_RECOMMENDED_MODEL", "llama3.2:1b")
OLLAMA_NUM_CTX = int(os.getenv("TUTOR_IA_OLLAMA_NUM_CTX", "4096"))
OLLAMA_NUM_PREDICT = int(os.getenv("TUTOR_IA_OLLAMA_NUM_PREDICT", "3072"))
OLLAMA_TEMPERATURE = float(os.getenv("TUTOR_IA_OLLAMA_TEMPERATURE", "0.2"))
OLLAMA_KEEP_ALIVE = os.getenv("TUTOR_IA_OLLAMA_KEEP_ALIVE", "10m")
WEB_FAST_NUM_CTX = int(os.getenv("TUTOR_IA_WEB_FAST_NUM_CTX", "3072"))
WEB_FAST_NUM_PREDICT = int(os.getenv("TUTOR_IA_WEB_FAST_NUM_PREDICT", "420"))
WEB_FAST_CODE_NUM_PREDICT = int(os.getenv("TUTOR_IA_WEB_FAST_CODE_NUM_PREDICT", "850"))
EMBED_DIM = int(os.getenv("TUTOR_IA_EMBED_DIM", "384"))
RETRIEVE_CANDIDATES = int(os.getenv("TUTOR_IA_RETRIEVE_CANDIDATES", "6"))
RESPONSE_TOP_K = int(os.getenv("TUTOR_IA_RESPONSE_TOP_K", "1"))
MAX_DOC_CONTEXT_CHARS = int(os.getenv("TUTOR_IA_MAX_DOC_CONTEXT_CHARS", "280"))
PROMPT_HISTORY_TURNS = int(os.getenv("TUTOR_IA_PROMPT_HISTORY_TURNS", "1"))
AGENCY_MATCH_LIMIT = int(os.getenv("TUTOR_IA_AGENCY_MATCH_LIMIT", "1"))
AGENCY_CONTEXT_CHARS = int(os.getenv("TUTOR_IA_AGENCY_CONTEXT_CHARS", "300"))
OBSIDIAN_TOP_K = int(os.getenv("TUTOR_IA_OBSIDIAN_TOP_K", "1"))
OBSIDIAN_MAX_NOTE_CHARS = int(os.getenv("TUTOR_IA_OBSIDIAN_MAX_NOTE_CHARS", "320"))
OBSIDIAN_ENABLED = os.getenv("TUTOR_IA_OBSIDIAN_ENABLED", "1").lower() not in {"0", "false", "no", "off"}
LOW_MEMORY_MODEL_PRIORITY = ["llama3.2:1b", "qwen2.5:1.5b", "gemma3:1b", "llama3.2:3b"]
ALLOWED_GROUP_RE = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")
TOKEN_RE = re.compile(r"\w+", re.UNICODE)
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
SOURCE_REQUEST_RE = re.compile(
    r"\b(fuente|fuentes|cita|citas|bibliografia|documento|documentos|de donde|origen)\b",
    re.IGNORECASE,
)
DEFAULT_ALLOWED_ORIGINS = "null,http://localhost,http://127.0.0.1"
ALLOWED_ORIGINS = {
    origin.strip().rstrip("/")
    for origin in os.getenv("TUTOR_IA_WEB_ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS).split(",")
    if origin.strip()
}
WEB_ACCESS_GROUPS = os.getenv("TUTOR_IA_WEB_GROUPS", "admin,public")
SMART_SEARCH_UNCONFIGURED_MESSAGE = (
    "La Búsqueda inteligente está activada, pero todavía no hay una API de búsqueda web configurada."
)
ALLOWED_UPLOAD_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".pdf",
    ".docx",
    ".txt",
    ".py",
    ".js",
    ".html",
    ".css",
    ".json",
    ".md",
    ".csv",
    ".sql",
    ".cs",
}
TEXT_UPLOAD_EXTENSIONS = {".txt", ".py", ".js", ".html", ".css", ".json", ".md", ".csv", ".sql", ".cs"}
MAX_UPLOAD_BYTES = int(os.getenv("TUTOR_IA_MAX_UPLOAD_BYTES", str(8 * 1024 * 1024)))
MAX_UPLOAD_TEXT_CHARS = int(os.getenv("TUTOR_IA_MAX_UPLOAD_TEXT_CHARS", "80000"))
MAX_UPLOAD_PROMPT_CHARS = int(os.getenv("TUTOR_IA_MAX_UPLOAD_PROMPT_CHARS", "12000"))
MAX_FINAL_PROMPT_CHARS = int(os.getenv("TUTOR_IA_MAX_FINAL_PROMPT_CHARS", "26000"))
UPLOAD_CHUNK_CHARS = int(os.getenv("TUTOR_IA_UPLOAD_CHUNK_CHARS", "1800"))
UPLOAD_CHUNK_OVERLAP = int(os.getenv("TUTOR_IA_UPLOAD_CHUNK_OVERLAP", "220"))
UPLOAD_RELEVANT_CHUNKS = int(os.getenv("TUTOR_IA_UPLOAD_RELEVANT_CHUNKS", "5"))
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("TUTOR_IA_OLLAMA_TIMEOUT_SECONDS", "120"))
WEB_FAST_TIMEOUT_SECONDS = int(os.getenv("TUTOR_IA_WEB_FAST_TIMEOUT_SECONDS", str(OLLAMA_TIMEOUT_SECONDS)))
WEB_FAST_BRAIN_CONTEXT_CHARS = int(os.getenv("TUTOR_IA_WEB_FAST_BRAIN_CONTEXT_CHARS", "350"))
WEB_FAST_CONTEXT_CHARS = int(os.getenv("TUTOR_IA_WEB_FAST_CONTEXT_CHARS", "3200"))
WEB_FAST_SUPPORT_CHARS = int(os.getenv("TUTOR_IA_WEB_FAST_SUPPORT_CHARS", "220"))
WEB_FAST_QUICK_CODE_CHARS = int(os.getenv("TUTOR_IA_WEB_FAST_QUICK_CODE_CHARS", "1500"))
NOTEBOOKLM_ENABLED_DEFAULT = os.getenv("NOTEBOOKLM_ENABLED", "false").lower() not in {"0", "false", "no", "off", ""}
NOTEBOOKLM_ACTIVE_ID = os.getenv("NOTEBOOKLM_ACTIVE_ID", "").strip()
STATUS_QUESTION_RE = re.compile(
    r"\b(estas|esta|est[aá]s|est[aá]|conectado|conexion|conexi[oó]n|online|ping|funciona)\b",
    re.IGNORECASE,
)
SIMPLE_CONVERSATION_RE = re.compile(
    r"^\s*(hola|buenas|buenos dias|buenas tardes|buenas noches|que tal|qué tal|como estas|cómo estás|"
    r"hola como estas|hola cómo estás|hola jarvis|hola jah|hey|hello)\s*[¿?¡!.,;:]*\s*$",
    re.IGNORECASE,
)

INTERACTION_MODES = {
    "unified": {
        "label": "Cerebro Unificado",
        "instructions": """
Modo Cerebro Unificado:
- Eres un solo cerebro conectado, no una lista de modos separados.
- Eres un Asistente de Programacion experto. Tu prioridad es crear, analizar, explicar, corregir y mejorar soluciones tecnicas de software.
- Las solicitudes normales de programacion, bases de datos, APIs, ciberseguridad defensiva, aprendizaje y proyectos academicos son permitidas y deben resolverse de forma completa.
- Decide internamente si conviene ensenar, organizar, crear, programar, auditar o coordinar especialistas.
- Integra fuentes privadas, Obsidian, Agency, OpenJarvis, Ollama y voz local como capas del mismo razonamiento.
- Prioriza claridad, accion concreta y validacion.
- Si falta informacion, dilo en una frase y pide el dato minimo necesario.
- No inventes ejecuciones, fuentes ni resultados que no esten en el contexto.
""",
    },
    "study": {
        "label": "Potencia tu estudio",
        "instructions": """
Modo Potencia tu estudio:
- Actua como tutor paciente y claro.
- Explica conceptos complejos en terminos simples sin perder precision.
- Usa ejemplos del mundo real cuando el contexto lo permita.
- Refuerza la comprension con pasos, analogias, mini-resumenes o preguntas de practica.
- Si falta informacion en el contexto interno, dilo con claridad.
""",
    },
    "organize": {
        "label": "Organiza tu pensamiento",
        "instructions": """
Modo Organiza tu pensamiento:
- Ordena el material en estructuras utiles: esquema, narrativa, secciones y conclusiones.
- Incluye puntos clave y evidencia de respaldo tomada del contexto.
- Ayuda a presentar temas con confianza: anticipa dudas, objeciones y transiciones.
- Si falta evidencia para una afirmacion, avisa y sugiere que fuente haria falta.
""",
    },
    "create": {
        "label": "Elabora nuevas ideas",
        "instructions": """
Modo Elabora nuevas ideas:
- Identifica patrones, tendencias, tensiones, oportunidades y huecos en el material.
- Genera ideas nuevas conectadas con el contexto, no ocurrencias desconectadas.
- Distingue entre evidencia del contexto, inferencia razonable e hipotesis.
- Propone proximos pasos accionables cuando sea util.
""",
    },
    "programming": {
        "label": "Cerebro Programador",
        "instructions": """
Modo Cerebro Programador:
- Actua como asistente senior de programacion local-first.
- Usa el perfil Jarvis/OpenJarvis como disciplina de razonamiento.
- Para debugging, sigue observar, formular hipotesis, probar y corregir.
- Para arquitectura, respeta el sistema existente, limites claros y cambios pequenos.
- Para review, prioriza correctitud, seguridad, rendimiento y mantenibilidad.
- Si no hay codigo o traceback concreto, no inventes una implementacion completa; entrega checklist y pide el fragmento necesario.
- Entrega acciones concretas, comandos o pruebas solo cuando sean utiles y verificables.
""",
    },
    "agency": {
        "label": "Cerebro Agency",
        "instructions": """
Modo Cerebro Agency:
- Actua como orquestador de especialistas.
- Selecciona el enfoque de los agentes relevantes de Agency segun la pregunta.
- Integra metodologia de expertos con la evidencia recuperada del contexto privado.
- Distingue entre hechos del contexto, criterio experto e inferencias.
- Entrega pasos concretos, criterios de validacion y siguientes acciones cuando sea util.
""",
    },
}

MODE_ALIASES = {
    "pensando": "unified",
    "thinking": "unified",
    "auto": "unified",
    "unified": "unified",
    "cerebro": "unified",
    "cerebro unificado": "unified",
    "el mas reciente - 5.5": "unified",
    "el mas reciente • 5.5": "study",
    "el más reciente • 5.5": "study",
    "configurar": "unified",
    "configurar...": "unified",
    "study": "unified",
    "organizar": "unified",
    "organize": "unified",
    "crear": "unified",
    "create": "unified",
    "programacion": "unified",
    "programming": "unified",
    "cerebro programador": "unified",
    "code": "unified",
    "debug": "unified",
    "agency": "unified",
    "cerebro agency": "unified",
}

memory_store = {}


@lru_cache(maxsize=1)
def get_collection():
    client = chromadb.PersistentClient(path=PERSIST_DIR, settings=Settings(anonymized_telemetry=False))
    return client.get_or_create_collection(COLLECTION_NAME)


@lru_cache(maxsize=8)
def get_llm(model_name):
    return OllamaLLM(
        model=model_name,
        temperature=OLLAMA_TEMPERATURE,
        num_ctx=OLLAMA_NUM_CTX,
        num_predict=OLLAMA_NUM_PREDICT,
        keep_alive=OLLAMA_KEEP_ALIVE,
        sync_client_kwargs={"timeout": OLLAMA_TIMEOUT_SECONDS},
        async_client_kwargs={"timeout": OLLAMA_TIMEOUT_SECONDS},
    )


@lru_cache(maxsize=16)
def get_fast_llm(model_name, extended_fast=False):
    num_predict = WEB_FAST_CODE_NUM_PREDICT if extended_fast else WEB_FAST_NUM_PREDICT
    return OllamaLLM(
        model=model_name,
        temperature=OLLAMA_TEMPERATURE,
        num_ctx=WEB_FAST_NUM_CTX,
        num_predict=num_predict,
        keep_alive=OLLAMA_KEEP_ALIVE,
        sync_client_kwargs={"timeout": WEB_FAST_TIMEOUT_SECONDS},
        async_client_kwargs={"timeout": WEB_FAST_TIMEOUT_SECONDS},
    )


def get_installed_ollama_models():
    try:
        completed = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return []

    if completed.returncode != 0:
        return []

    models = []
    for line in completed.stdout.splitlines()[1:]:
        parts = line.split()
        if parts:
            models.append(parts[0])
    return models


def choose_llm_model(preferred_model=None, question="", docs=None, brain_context=""):
    models = get_installed_ollama_models()
    if choose_local_model:
        return choose_local_model(
            models,
            preferred_model=preferred_model,
            question=question,
            docs=docs,
            brain_context=brain_context,
            fallback_model=LLM_MODEL,
        )
    preferred_model = preferred_model or LLM_MODEL
    if preferred_model in models:
        return preferred_model
    return LLM_MODEL if LLM_MODEL in models else (models[0] if models else None)


def normalize_groups(groups):
    if isinstance(groups, str):
        raw_groups = groups.split(",")
    else:
        raw_groups = groups or []

    clean_groups = []
    for group in raw_groups:
        group = str(group).strip().lower()
        if group and ALLOWED_GROUP_RE.fullmatch(group) and group not in clean_groups:
            clean_groups.append(group)
    return clean_groups or ["public"]


def payload_bool(payload, key, default=False):
    if key not in payload:
        return default
    value = payload.get(key)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off", ""}


def normalize_mode_text(value):
    text = str(value or "").strip().lower()
    return (
        text.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("  ", " ")
    )


def normalized_query_text(value):
    return normalize_mode_text(value).replace("ñ", "n")


def normalize_interaction_mode(mode_key):
    raw_mode = str(mode_key or "unified").strip()
    normalized = normalize_mode_text(raw_mode)
    if normalized in MODE_ALIASES:
        return MODE_ALIASES[normalized]
    if raw_mode == "unified":
        return "unified"
    if raw_mode in INTERACTION_MODES:
        return "unified"
    return "unified"


def get_interaction_mode(mode_key):
    return INTERACTION_MODES.get(normalize_interaction_mode(mode_key), INTERACTION_MODES["unified"])


def trim_prompt_text(text, max_chars):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def clean_answer_text(text):
    text = str(text or "").replace("**", "")
    text = re.sub(r"(?im)^\s*fuentes?\s*:\s*(?:\n\s*[-*].*)+", "", text)
    text = re.sub(r"(?im)^\s*sources?\s*:\s*(?:\n\s*[-*].*)+", "", text)
    text = re.sub(r"(?im)^\s*fuentes?\s*:\s*.*$", "", text)
    text = re.sub(r"(?im)^\s*sources?\s*:\s*.*$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def source_requested(question):
    return bool(SOURCE_REQUEST_RE.search(str(question or "")))


def needs_extended_fast_answer(question, docs=None):
    text = normalized_query_text(question)
    action_terms = ("crea", "crear", "creame", "creale", "genera", "generar", "implementa", "corrige", "modifica")
    technical_terms = (
        "base de datos",
        "base datos",
        "sql",
        "script",
        "codigo",
        "tabla",
        "tablas",
        "backend",
        "frontend",
        "api",
        "html",
        "css",
        "javascript",
        "python",
    )
    has_action = any(term in text for term in action_terms)
    has_technical_target = any(term in text for term in technical_terms)
    has_files = bool(docs)
    return (has_action and has_technical_target) or (has_files and has_technical_target)


def is_status_question(question):
    text = str(question or "").strip()
    if len(text) > 140:
        return False
    return bool(STATUS_QUESTION_RE.search(text))


def is_simple_conversation(question):
    text = re.sub(r"\s+", " ", str(question or "").strip().lower())
    if not text or len(text) > 120:
        return False
    if SIMPLE_CONVERSATION_RE.fullmatch(text):
        return True
    clean = re.sub(r"[¿?¡!.,;:]+", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean in {
        "hola",
        "hola como estas",
        "hola cómo estás",
        "como estas",
        "cómo estás",
        "buenas",
        "buenos dias",
        "buenas tardes",
        "buenas noches",
        "que tal",
        "qué tal",
    }


def simple_conversation_answer(question, tutor_ia_enabled=True, smart_search_enabled=False):
    brain = "con el cerebro tutor_ia activo" if tutor_ia_enabled else "en modo chat rapido"
    web = " y con Busqueda inteligente activada" if smart_search_enabled else ""
    return (
        f"Hola, estoy bien y listo para ayudarte. Estoy {brain}{web}. "
        "Puedes preguntarme por codigo, bases de datos, archivos, RAG o cualquier parte de tu proyecto."
    )


def smart_web_search(query):
    """
    Función preparada para búsqueda inteligente en la web.
    Aquí se podrá conectar una API real de búsqueda web como Tavily, SerpAPI,
    Brave Search API, Google Custom Search o similar.
    """
    return {
        "enabled": False,
        "message": SMART_SEARCH_UNCONFIGURED_MESSAGE,
        "results": [],
    }


def get_notebooklm_service(enabled=True, active_notebook_id=None):
    if not NotebookLMService:
        return None
    return NotebookLMService(
        enabled=enabled,
        active_notebook_id=active_notebook_id or NOTEBOOKLM_ACTIVE_ID,
    )


def payload_notebooklm_enabled(payload):
    return payload_bool(
        payload,
        "notebookLMEnabled",
        payload_bool(
            payload,
            "notebookLM",
            payload_bool(
                payload,
                "notebook_lm",
                payload_bool(payload, "notebooklm_enabled", NOTEBOOKLM_ENABLED_DEFAULT),
            ),
        ),
    )


def payload_notebooklm_id(payload):
    return str(
        payload.get("notebookLMActiveId")
        or payload.get("notebooklm_active_id")
        or payload.get("notebook_id")
        or NOTEBOOKLM_ACTIVE_ID
        or ""
    ).strip()


def doc_to_brain_context(source, doc, confidence=0.7):
    metadata = doc.get("metadata", {}) if isinstance(doc, dict) else {}
    title = metadata.get("title") or metadata.get("source") or source
    content = trim_prompt_text(doc.get("text", "") if isinstance(doc, dict) else str(doc), WEB_FAST_CONTEXT_CHARS)
    if BrainSourceContext:
        return BrainSourceContext(
            source=source,
            success=bool(content),
            confidence=confidence,
            content=f"[{title}]\n{content}",
            references=[metadata],
            metadata={"docs": [doc] if isinstance(doc, dict) else []},
        )
    return {
        "source": source,
        "success": bool(content),
        "confidence": confidence,
        "content": content,
        "references": [metadata],
        "metadata": {"docs": [doc] if isinstance(doc, dict) else []},
    }


def contexts_to_docs(contexts):
    docs = []
    for context in contexts or []:
        metadata = getattr(context, "metadata", {}) if not isinstance(context, dict) else context.get("metadata", {})
        docs.extend(metadata.get("docs", []) or [])
    return docs


def context_by_source(contexts, source):
    return [context for context in contexts or [] if (getattr(context, "source", None) if not isinstance(context, dict) else context.get("source")) == source]


def context_content(context):
    return getattr(context, "content", "") if not isinstance(context, dict) else context.get("content", "")


def context_metadata(context):
    return getattr(context, "metadata", {}) if not isinstance(context, dict) else context.get("metadata", {})


def safe_tools_context(question, route):
    if route.get("requires_calculation"):
        match = re.search(r"(-?\d+(?:\.\d+)?)\s*([\+\-\*/])\s*(-?\d+(?:\.\d+)?)", question)
        if match:
            left = float(match.group(1))
            op = match.group(2)
            right = float(match.group(3))
            result = {
                "+": left + right,
                "-": left - right,
                "*": left * right,
                "/": left / right if right != 0 else "division entre cero",
            }[op]
            return f"calculator: {match.group(0)} = {result}"
    if route.get("requires_shell"):
        return "shell_exec disponible, pero no se ejecutan comandos sin confirmacion explicita."
    if route.get("requires_file_read"):
        return "file_read disponible para leer archivos dentro de rutas permitidas."
    if route.get("requires_file_write"):
        return "file_write disponible con validacion de rutas y sin sobrescribir sin necesidad."
    return ""


def file_extension(filename):
    return Path(str(filename or "")).suffix.lower()


def log_bridge(message):
    LOGGER.info(message)
    print(f"[TUTOR_IA bridge] {message}", flush=True)


def public_uploaded_file(file_info):
    return {
        "name": file_info.get("name", ""),
        "extension": file_info.get("extension", ""),
        "type": file_info.get("content_type", ""),
        "size": file_info.get("size", 0),
        "accepted": file_info.get("accepted", False),
        "content_chars": len(file_info.get("content", "") or file_info.get("text_preview", "")),
        "truncated": bool(file_info.get("truncated")),
        "error": file_info.get("error", ""),
        "chunk_count": int(file_info.get("chunk_count", 0) or 0),
    }


def _uploaded_name_and_bytes(uploaded_file):
    if isinstance(uploaded_file, dict):
        name = uploaded_file.get("name") or uploaded_file.get("filename") or "archivo"
        raw = uploaded_file.get("content") or uploaded_file.get("bytes") or uploaded_file.get("data") or b""
        if isinstance(raw, str):
            raw = raw.encode("utf-8", errors="ignore")
        return str(name), bytes(raw)

    name = getattr(uploaded_file, "name", None) or getattr(uploaded_file, "filename", None) or "archivo"
    if hasattr(uploaded_file, "getbuffer"):
        return str(name), bytes(uploaded_file.getbuffer())
    if hasattr(uploaded_file, "read"):
        raw = uploaded_file.read()
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        if isinstance(raw, str):
            raw = raw.encode("utf-8", errors="ignore")
        return str(name), bytes(raw or b"")
    if isinstance(uploaded_file, (bytes, bytearray)):
        return str(name), bytes(uploaded_file)
    return str(name), b""


def read_uploaded_file(uploaded_file):
    name, raw = _uploaded_name_and_bytes(uploaded_file)
    safe_name = Path(str(name or "archivo")).name
    extension = file_extension(safe_name)
    original_size = len(raw)

    if extension not in TEXT_UPLOAD_EXTENSIONS:
        error = (
            f"Extension no soportada para lectura de texto: {extension or 'sin extension'}. "
            "Usa .html, .css, .js, .py, .json, .md, .txt o .sql."
        )
        log_bridge(f"uploaded file rejected name={safe_name} ext={extension or 'none'} size={original_size} reason=unsupported")
        return {
            "name": safe_name,
            "extension": extension,
            "content": "",
            "size": original_size,
            "accepted": False,
            "truncated": False,
            "error": error,
        }

    truncated = original_size > MAX_UPLOAD_BYTES
    limited_raw = raw[:MAX_UPLOAD_BYTES]
    decoded = limited_raw.decode("utf-8", errors="ignore")
    if len(decoded) > MAX_UPLOAD_TEXT_CHARS:
        decoded = decoded[:MAX_UPLOAD_TEXT_CHARS]
        truncated = True

    log_bridge(
        f"uploaded file read name={safe_name} ext={extension} bytes={original_size} chars={len(decoded)} truncated={truncated}"
    )
    return {
        "name": safe_name,
        "extension": extension,
        "content": decoded,
        "size": original_size,
        "accepted": True,
        "truncated": truncated,
        "error": "",
    }


def normalize_uploaded_file(filename, content_type, content):
    file_info = read_uploaded_file({"name": filename, "content": content or b""})
    file_info["content_type"] = content_type or "application/octet-stream"
    file_info["raw_content"] = (content or b"")[:MAX_UPLOAD_BYTES]
    file_info["text_preview"] = file_info.get("content", "")
    return file_info


def split_text_chunks(text, chunk_chars=None, overlap=None):
    text = str(text or "").replace("\r\n", "\n")
    chunk_chars = max(400, int(chunk_chars or UPLOAD_CHUNK_CHARS))
    overlap = max(0, min(int(overlap if overlap is not None else UPLOAD_CHUNK_OVERLAP), chunk_chars // 3))
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_chars, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def is_database_request(message):
    normalized = normalized_query_text(message)
    return bool(re.search(r"\b(base\s+(?:de\s+)?datos|database|sql|tabla|tablas|modelo\s+er|entidad\s+relacion)\b", normalized))


def summarize_uploaded_structure(file_info):
    content = str(file_info.get("content") or "")
    extension = file_info.get("extension", "")
    name = file_info.get("name", "archivo")
    if not content:
        return ""

    if extension == ".html":
        title_match = re.search(r"<title[^>]*>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
        meta_match = re.search(
            r"<meta[^>]+name=[\"']description[\"'][^>]+content=[\"']([^\"']+)[\"']",
            content,
            re.IGNORECASE,
        )
        headings = [
            re.sub(r"<[^>]+>", " ", match).strip()
            for match in re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", content, re.IGNORECASE | re.DOTALL)[:20]
        ]
        controls = re.findall(r"<(?:form|input|textarea|select|option|button|a)\b[^>]*>", content, re.IGNORECASE)[:80]
        scripts = re.findall(r"<script\b[^>]*>|<link\b[^>]*>|<form\b[^>]*>", content, re.IGNORECASE)[:40]
        parts = [
            f"Resumen estructural de {name}:",
            f"Titulo: {re.sub(r'<[^>]+>', ' ', title_match.group(1)).strip() if title_match else 'no detectado'}",
            f"Meta descripcion: {meta_match.group(1).strip() if meta_match else 'no detectada'}",
            "Encabezados principales: " + "; ".join(item for item in headings if item)[:1600],
            "Controles, formularios y enlaces detectados:\n" + "\n".join(controls),
            "Recursos y bloques relevantes:\n" + "\n".join(scripts),
        ]
        return trim_prompt_text("\n".join(parts), 4500)

    if extension in {".json", ".sql", ".py", ".js", ".css", ".md", ".txt"}:
        lines = [line.strip() for line in content.splitlines() if line.strip()][:80]
        return trim_prompt_text(f"Resumen de {name}:\n" + "\n".join(lines), 3500)
    return ""


def select_uploaded_file_chunks(file_info, query, max_chunks=None):
    content = str(file_info.get("content") or "")
    if not content:
        return []
    if len(content) <= MAX_UPLOAD_PROMPT_CHARS:
        return [{"text": content, "index": 0, "score": 1.0, "total": 1}]

    chunks = split_text_chunks(content)
    file_info["chunk_count"] = len(chunks)
    query_vector = embed_text(query)
    query_tokens = set(TOKEN_RE.findall(normalized_query_text(query)))
    wants_db = is_database_request(query)
    scored = []
    for index, chunk in enumerate(chunks):
        chunk_tokens = set(TOKEN_RE.findall(normalized_query_text(chunk)))
        vector_score = dot_score(query_vector, embed_text(chunk))
        overlap = len(query_tokens & chunk_tokens) / max(len(query_tokens), 1)
        structure_boost = 0.0
        if wants_db and re.search(
            r"\b(form|input|textarea|select|name=|contact|cliente|servicio|proyecto|lead|email|telefono|whatsapp|mensaje)\b",
            chunk,
            re.IGNORECASE,
        ):
            structure_boost = 0.22
        if index == 0:
            structure_boost += 0.06
        scored.append(((0.62 * vector_score) + (0.28 * overlap) + structure_boost, index, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    limit = max(1, int(max_chunks or UPLOAD_RELEVANT_CHUNKS))
    selected = sorted(scored[:limit], key=lambda item: item[1])
    return [
        {"text": chunk, "index": index, "score": score, "total": len(chunks)}
        for score, index, chunk in selected
    ]


def index_uploaded_files(uploaded_files, session_id="default"):
    indexed = 0
    for file_info in uploaded_files or []:
        if not file_info.get("accepted") or not file_info.get("content"):
            continue
        chunks = split_text_chunks(file_info.get("content", ""))
        file_info["chunk_count"] = len(chunks)
        if not chunks:
            continue
        try:
            ids = []
            documents = []
            embeddings = []
            metadatas = []
            fingerprint = hashlib.sha1(
                f"{session_id}:{file_info.get('name')}:{file_info.get('size')}:{file_info.get('content')[:500]}".encode(
                    "utf-8",
                    errors="ignore",
                )
            ).hexdigest()[:24]
            for index, chunk in enumerate(chunks):
                ids.append(f"upload-{fingerprint}-{index}")
                documents.append(chunk)
                embeddings.append(embed_text(chunk))
                metadatas.append(
                    {
                        "source": f"upload:{file_info.get('name', 'archivo')}",
                        "title": file_info.get("name", "archivo"),
                        "type": "uploaded_file",
                        "extension": file_info.get("extension", ""),
                        "access_group": "admin",
                        "session_id": str(session_id)[:120],
                        "chunk_index": index,
                    }
                )
            get_collection().upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
            indexed += len(chunks)
            log_bridge(f"uploaded file indexed name={file_info.get('name')} chunks={len(chunks)} persist_dir={PERSIST_DIR}")
        except Exception as exc:
            file_info["error"] = f"No se pudo indexar en tutor_ia: {exc}"
            log_bridge(f"uploaded file index error name={file_info.get('name')} error={exc}")
    return indexed


def build_uploaded_file_docs(uploaded_files):
    docs = []
    for file_info in uploaded_files or []:
        if not file_info.get("accepted"):
            continue

        name = file_info.get("name", "archivo")
        extension = file_info.get("extension", "")
        if file_info.get("text_preview"):
            text = f"Archivo adjunto: {name}\nContenido:\n{file_info['text_preview']}"
        else:
            text = (
                f"Archivo adjunto recibido: {name}. "
                f"Tipo: {file_info.get('content_type', 'archivo')}. "
                "El backend actual registra el archivo, pero no extrae contenido de este formato todavía."
            )

        docs.append(
            {
                "text": text,
                "metadata": {
                    "source": f"upload:{name}",
                    "type": "archivo",
                    "title": name,
                    "extension": extension,
                    "access_group": "admin",
                },
            }
        )
    return docs


def build_uploaded_file_docs(uploaded_files, question=""):
    docs = []
    for file_info in uploaded_files or []:
        if not file_info.get("accepted"):
            if file_info.get("error"):
                log_bridge(f"uploaded file not usable name={file_info.get('name')} error={file_info.get('error')}")
            continue

        name = file_info.get("name", "archivo")
        extension = file_info.get("extension", "")
        summary = summarize_uploaded_structure(file_info)
        if summary:
            docs.append(
                {
                    "text": summary,
                    "metadata": {
                        "source": f"upload:{name}:summary",
                        "type": "archivo_resumen",
                        "title": f"{name} resumen",
                        "extension": extension,
                        "access_group": "admin",
                        "uploaded_file": True,
                    },
                }
            )

        for chunk in select_uploaded_file_chunks(file_info, question):
            docs.append(
                {
                    "text": (
                        f"Archivo adjunto: {name}\n"
                        f"Extension: {extension}\n"
                        f"Fragmento {chunk['index'] + 1} de {chunk['total']} "
                        f"(score {chunk['score']:.3f}):\n{chunk['text']}"
                    ),
                    "metadata": {
                        "source": f"upload:{name}",
                        "type": "archivo",
                        "title": name,
                        "extension": extension,
                        "access_group": "admin",
                        "uploaded_file": True,
                        "chunk_index": chunk["index"],
                    },
                }
            )
    return docs


def _prompt_file_blocks(uploaded_files):
    blocks = []
    for item in uploaded_files or []:
        if isinstance(item, dict) and "metadata" in item and "text" in item:
            metadata = item.get("metadata", {})
            name = metadata.get("title") or metadata.get("source") or "archivo"
            extension = metadata.get("extension", "")
            content = item.get("text", "")
        else:
            name = item.get("name", "archivo") if isinstance(item, dict) else "archivo"
            extension = item.get("extension", "") if isinstance(item, dict) else ""
            content = item.get("content", "") if isinstance(item, dict) else str(item or "")
        blocks.append(
            f"{name}\nExtension: {extension or 'desconocida'}\nContenido relevante:\n{trim_prompt_text(content, MAX_UPLOAD_PROMPT_CHARS)}"
        )
    return "\n\n".join(blocks)


def build_prompt(user_message, uploaded_files, tutor_context):
    file_context = _prompt_file_blocks(uploaded_files)
    if not file_context:
        file_context = "No hay archivos adjuntos con texto legible."
    elif len(file_context) > MAX_UPLOAD_PROMPT_CHARS:
        log_bridge(
            f"uploaded context too large chars={len(file_context)} limit={MAX_UPLOAD_PROMPT_CHARS}; trimming file context"
        )
        file_context = trim_prompt_text(file_context, MAX_UPLOAD_PROMPT_CHARS)

    database_instruction = ""
    if is_database_request(user_message):
        database_instruction = """
Si el usuario pide crear una base de datos, responde con estas secciones:
1. Analisis del archivo adjunto.
2. Propuesta de tablas y relaciones.
3. Script SQL funcional.
4. Explicacion de conexion backend.
5. Recomendaciones de seguridad.
6. Proximos pasos.
"""

    def render(context_text):
        return f"""
CONTEXTO Y ROL:
Eres un asistente de programacion experto en Python, C#, SQL, HTML, CSS, JavaScript, ciberseguridad, diseno de bases de datos, arquitectura de software y analisis de codigo.

TAREA DEL USUARIO:
{user_message}

ARCHIVOS ADJUNTOS:
{file_context}

CONTEXTO DEL CEREBRO TUTOR_IA:
{context_text or "No se recupero contexto adicional de tutor_ia."}

INSTRUCCIONES:
Analiza primero los archivos adjuntos. No respondas de forma generica.
Lee la estructura del archivo, detecta que necesita el usuario, propone una solucion tecnica y genera codigo cuando sea necesario.
Explica en que archivo o capa aplicar los cambios. No inventes archivos que no existen sin aclararlo.
{database_instruction}

CRITERIOS DE CALIDAD:
- Respuesta logica.
- Respuesta tecnica.
- Codigo funcional.
- Usar el contenido adjunto.
- Explicar pasos.
- Recomendar buenas practicas de seguridad.
- Responder en espanol.

RESPUESTA:
"""

    prompt = render(tutor_context)
    if len(prompt) > MAX_FINAL_PROMPT_CHARS:
        allowed_context = max(1200, MAX_FINAL_PROMPT_CHARS - len(prompt) + len(str(tutor_context or "")) - 300)
        log_bridge(f"context too large for model prompt chars={len(prompt)} limit={MAX_FINAL_PROMPT_CHARS}; trimming tutor_ia context")
        prompt = render(trim_prompt_text(tutor_context, allowed_context))
    return prompt


def _unique_values(values, limit=20):
    seen = set()
    result = []
    for value in values:
        clean = re.sub(r"\s+", " ", str(value or "")).strip()
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(clean)
        if len(result) >= limit:
            break
    return result


def _html_text_items(pattern, content, limit=20):
    return _unique_values(
        re.sub(r"<[^>]+>", " ", match).strip()
        for match in re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
    )[:limit]


def extract_upload_business_signals(uploaded_files):
    signals = {
        "files": [],
        "titles": [],
        "descriptions": [],
        "headings": [],
        "forms": [],
        "fields": [],
        "links": [],
    }
    for file_info in uploaded_files or []:
        if not file_info.get("accepted"):
            continue
        name = file_info.get("name", "archivo")
        content = str(file_info.get("content") or "")
        signals["files"].append(name)
        if file_info.get("extension") == ".html":
            signals["titles"].extend(_html_text_items(r"<title[^>]*>(.*?)</title>", content, 5))
            signals["descriptions"].extend(
                re.findall(
                    r"<meta[^>]+name=[\"']description[\"'][^>]+content=[\"']([^\"']+)[\"']",
                    content,
                    re.IGNORECASE,
                )[:5]
            )
            signals["headings"].extend(_html_text_items(r"<h[1-3][^>]*>(.*?)</h[1-3]>", content, 30))
            signals["forms"].extend(re.findall(r"<form\b[^>]*>", content, re.IGNORECASE)[:10])
            signals["fields"].extend(
                re.findall(r"\b(?:name|id)=[\"']([^\"']+)[\"']", content, re.IGNORECASE)[:80]
            )
            signals["links"].extend(
                re.findall(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>", content, re.IGNORECASE)[:40]
            )
    return {key: _unique_values(value, 30) for key, value in signals.items()}


def generate_uploaded_database_solution(user_message, uploaded_files, file_docs=None, project_path=""):
    signals = extract_upload_business_signals(uploaded_files)
    files = ", ".join(signals.get("files") or ["archivo adjunto"])
    title = "; ".join(signals.get("titles") or ["sitio web adjunto"])
    description = "; ".join(signals.get("descriptions") or ["pagina HTML con contenido de servicios/proyectos"])
    headings = "; ".join((signals.get("headings") or [])[:12]) or "no se detectaron encabezados principales"
    fields = ", ".join((signals.get("fields") or [])[:20]) or "sin campos de formulario visibles en el fragmento analizado"
    forms = "si" if signals.get("forms") else "no"
    project_note = (
        f"Proyecto enviado por la interfaz: {project_path}."
        if project_path
        else "No se recibio una ruta de backend existente; propongo crear una capa backend nueva."
    )
    indexed = sum(int(file_info.get("chunk_count", 0) or 0) for file_info in uploaded_files or [])

    return f"""
Analisis del archivo adjunto
- Archivo usado: {files}.
- Titulo detectado: {title}.
- Descripcion detectada: {description}.
- Encabezados/areas utiles: {headings}.
- Formularios detectados: {forms}.
- Campos/id/name detectados: {fields}.
- El archivo fue leido en backend, dividido en {indexed} fragmentos e indexado en tutor_ia antes de generar esta propuesta.
- {project_note}

Propuesta de tablas
- servicios: catalogo de servicios ofrecidos en la pagina.
- proyectos: casos/proyectos mostrados en el portafolio.
- leads_contacto: solicitudes que llegan desde formularios, botones de WhatsApp o llamadas a la accion.
- mensajes_asistente: historial de preguntas del asistente o chatbot web.
- paginas_seo: metadatos SEO por pagina para administrar titulos, descripciones y slugs.

Script SQL funcional (MySQL)
```sql
CREATE DATABASE IF NOT EXISTS abraham_hernandez_web
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE abraham_hernandez_web;

CREATE TABLE IF NOT EXISTS servicios (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  slug VARCHAR(160) NOT NULL UNIQUE,
  nombre VARCHAR(180) NOT NULL,
  descripcion TEXT NOT NULL,
  categoria VARCHAR(120) NULL,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proyectos (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  slug VARCHAR(160) NOT NULL UNIQUE,
  nombre VARCHAR(180) NOT NULL,
  cliente VARCHAR(180) NULL,
  descripcion TEXT NOT NULL,
  stack_tecnico VARCHAR(255) NULL,
  url_demo VARCHAR(500) NULL,
  url_repositorio VARCHAR(500) NULL,
  destacado BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS leads_contacto (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(160) NULL,
  email VARCHAR(180) NULL,
  telefono VARCHAR(60) NULL,
  empresa VARCHAR(180) NULL,
  servicio_interes VARCHAR(180) NULL,
  presupuesto VARCHAR(80) NULL,
  mensaje TEXT NOT NULL,
  origen_pagina VARCHAR(220) NOT NULL DEFAULT 'index.html',
  estado ENUM('nuevo', 'contactado', 'calificado', 'cerrado', 'descartado') NOT NULL DEFAULT 'nuevo',
  ip_hash CHAR(64) NULL,
  user_agent_hash CHAR(64) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_leads_estado_created (estado, created_at),
  INDEX idx_leads_email (email)
);

CREATE TABLE IF NOT EXISTS mensajes_asistente (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  session_id VARCHAR(120) NOT NULL,
  lead_id BIGINT UNSIGNED NULL,
  pregunta TEXT NOT NULL,
  respuesta MEDIUMTEXT NULL,
  intencion VARCHAR(120) NULL,
  archivo_adjunto VARCHAR(255) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_mensajes_lead
    FOREIGN KEY (lead_id) REFERENCES leads_contacto(id)
    ON DELETE SET NULL,
  INDEX idx_mensajes_session_created (session_id, created_at)
);

CREATE TABLE IF NOT EXISTS paginas_seo (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  ruta VARCHAR(220) NOT NULL UNIQUE,
  titulo VARCHAR(220) NOT NULL,
  descripcion VARCHAR(320) NOT NULL,
  keywords TEXT NULL,
  canonical_url VARCHAR(500) NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

Explicacion de conexion backend
- En el adjunto solo se ve el lado HTML; no asumo que ya exista backend.
- Crea un endpoint backend, por ejemplo `POST /api/leads`, que reciba nombre, email, telefono, servicio_interes y mensaje.
- Desde `index.html` o el JS del formulario, envia los datos con `fetch('/api/leads', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(payload) }})`.
- En Python puedes usar FastAPI/Flask con un pool MySQL y consultas parametrizadas; no construyas SQL concatenando texto del usuario.

Recomendaciones de seguridad
- Validar y sanear todos los campos del formulario.
- Usar consultas preparadas para evitar SQL injection.
- Guardar hashes de IP/user-agent si necesitas auditoria, no datos sensibles en bruto.
- Activar HTTPS, CORS limitado, rate limit y proteccion CSRF si usas cookies.
- No guardar secretos de base de datos en el frontend; usa variables de entorno en el backend.

Proximos pasos
1. Crear `database/schema.sql` con el script anterior.
2. Crear un backend pequeno para `POST /api/leads`.
3. Conectar el formulario o CTA de `index.html` al endpoint.
4. Probar insercion con un lead falso.
5. Agregar una vista privada para revisar leads y estados.
""".strip()


def parse_multipart_form(content_type, body):
    message = BytesParser(policy=policy.default).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body
    )
    payload = {}
    uploaded_files = []

    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue

        name = part.get_param("name", header="content-disposition")
        filename = part.get_filename()
        content = part.get_payload(decode=True) or b""

        if filename:
            uploaded_files.append(
                normalize_uploaded_file(filename, part.get_content_type(), content)
            )
            continue

        payload[name] = content.decode(part.get_content_charset() or "utf-8", errors="replace")

    return payload, uploaded_files


def dot_score(left, right):
    return sum(a * b for a, b in zip(left, right))


def parse_frontmatter(raw):
    match = FRONTMATTER_RE.match(str(raw or "").lstrip("\ufeff"))
    if not match:
        return {}, raw

    metadata = {}
    current_key = ""
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- ") and current_key:
            metadata[current_key] = f"{metadata.get(current_key, '')} {stripped[2:].strip()}".strip()
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        current_key = key.strip().lower()
        metadata[current_key] = value.strip().strip('"').strip("'")
    return metadata, raw[match.end() :]


def clean_obsidian_text(text):
    text = CODE_BLOCK_RE.sub("", str(text or ""))
    text = WIKI_LINK_RE.sub(lambda match: match.group(1).split("|")[-1], text)
    text = re.sub(r"(?m)^#{1,6}\s*", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def iter_obsidian_files():
    if not OBSIDIAN_ENABLED:
        return []

    root = Path(OBSIDIAN_VAULT_DIR).expanduser()
    if not root.exists() or not root.is_dir():
        return []

    files = []
    for current_root, dirs, names in os.walk(root):
        dirs[:] = [
            name
            for name in dirs
            if name not in {".obsidian", ".git", "__pycache__"} and not name.startswith(".")
        ]
        for name in names:
            path = Path(current_root) / name
            if path.suffix.lower() in {".md", ".canvas"}:
                files.append(path)
    return sorted(files)


def read_canvas_text(raw):
    try:
        data = json.loads(raw)
    except Exception:
        return raw

    parts = []
    for node in data.get("nodes", []):
        text = node.get("text") or node.get("file") or node.get("label")
        if text:
            parts.append(str(text))
    for edge in data.get("edges", []):
        label = edge.get("label")
        if label:
            parts.append(str(label))
    return "\n".join(parts)


def build_obsidian_note(path, root):
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".canvas":
        raw = read_canvas_text(raw)
    metadata, body = parse_frontmatter(raw)
    title = metadata.get("title") or path.stem
    rel_path = path.relative_to(root).as_posix()
    summary = metadata.get("resumen", "")
    tags = metadata.get("tags", "")
    note_type = metadata.get("tipo", "obsidian")
    area = metadata.get("area", "")
    status = metadata.get("estado", "")
    cleaned_body = clean_obsidian_text(body)
    context_text = "\n".join(
        part
        for part in [
            f"Titulo: {title}",
            f"Ruta Obsidian: {rel_path}",
            f"Resumen: {summary}" if summary else "",
            f"Tags: {tags}" if tags else "",
            f"Tipo: {note_type}" if note_type else "",
            f"Area: {area}" if area else "",
            f"Estado: {status}" if status else "",
            trim_prompt_text(cleaned_body, OBSIDIAN_MAX_NOTE_CHARS),
        ]
        if part
    )
    search_text = " ".join([title, rel_path, summary, tags, note_type, area, cleaned_body])
    return {
        "text": context_text,
        "metadata": {
            "source": f"obsidian:{rel_path}",
            "type": "obsidian",
            "title": title,
            "path": rel_path,
            "access_group": "admin",
            "area": area,
            "estado": status,
        },
        "tokens": set(TOKEN_RE.findall(search_text.lower())),
        "vector": embed_text(search_text),
    }


def obsidian_signature():
    files = iter_obsidian_files()
    signature = []
    for path in files:
        try:
            stat = path.stat()
        except OSError:
            continue
        signature.append((str(path), stat.st_mtime_ns, stat.st_size))
    return tuple(signature)


@lru_cache(maxsize=4)
def load_obsidian_notes(signature):
    root = Path(OBSIDIAN_VAULT_DIR).expanduser()
    notes = []
    for raw_path, _, _ in signature:
        path = Path(raw_path)
        try:
            notes.append(build_obsidian_note(path, root))
        except OSError:
            continue
    return notes


def get_obsidian_notes():
    signature = obsidian_signature()
    if not signature:
        return []
    return load_obsidian_notes(signature)


def retrieve_obsidian(question, top_k=None):
    top_k = top_k if top_k is not None else OBSIDIAN_TOP_K
    if top_k <= 0:
        return []

    notes = get_obsidian_notes()
    if not notes:
        return []

    query_text = str(question or "")
    query_vector = embed_text(query_text)
    query_tokens = set(TOKEN_RE.findall(query_text.lower()))
    scored = []
    for note in notes:
        vector_score = dot_score(query_vector, note["vector"])
        overlap = len(query_tokens & note["tokens"]) / max(len(query_tokens), 1)
        path = note["metadata"].get("path", "").lower()
        title = note["metadata"].get("title", "").lower()
        boost = 0.08 if any(token in path or token in title for token in query_tokens) else 0.0
        score = (0.78 * vector_score) + (0.22 * overlap) + boost
        scored.append((score, note))

    scored.sort(key=lambda item: item[0], reverse=True)
    results = []
    for score, note in scored[: max(top_k, 0)]:
        if score <= 0:
            continue
        results.append(
            {
                "text": note["text"],
                "metadata": note["metadata"],
            }
        )
    return results


def get_obsidian_status():
    root = Path(OBSIDIAN_VAULT_DIR).expanduser()
    notes = get_obsidian_notes()
    return {
        "enabled": OBSIDIAN_ENABLED,
        "available": root.exists() and root.is_dir(),
        "path": str(root),
        "notes": len(notes),
    }


def embed_text(text):
    vector = [0.0] * EMBED_DIM
    tokens = TOKEN_RE.findall((text or "").lower())
    if not tokens:
        return vector

    previous = ""
    for token in tokens:
        features = [token]
        if previous:
            features.append(f"{previous}_{token}")
        previous = token

        for feature in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "little", signed=False)
            index = value % EMBED_DIM
            vector[index] += 1.0 if value & 1 else -1.0

    norm = math.sqrt(sum(value * value for value in vector))
    if not norm:
        return vector
    return [value / norm for value in vector]


def retrieve(question, user_groups=None, k=None, top_k=None, selected_sources=None):
    collection = get_collection()
    total_docs = collection.count()
    if total_docs == 0:
        return []

    k = k or RETRIEVE_CANDIDATES
    top_k = top_k or RESPONSE_TOP_K
    user_groups = normalize_groups(user_groups or ["public"])
    if selected_sources is not None:
        selected_sources = set(selected_sources)
        if not selected_sources:
            return []

    n_results = min(max(k, top_k * 8), total_docs)
    where_filter = None
    if "admin" not in user_groups:
        if len(user_groups) == 1:
            where_filter = {"access_group": user_groups[0]}
        else:
            where_filter = {"$or": [{"access_group": group} for group in user_groups]}

    try:
        result = collection.query(query_embeddings=[embed_text(question)], n_results=n_results, where=where_filter)
    except Exception:
        result = collection.query(query_embeddings=[embed_text(question)], n_results=n_results)

    docs = []
    if result.get("documents"):
        for index, doc_text in enumerate(result["documents"][0]):
            metadata = result["metadatas"][0][index]
            doc_group = metadata.get("access_group", "public")
            source = metadata.get("source", "")
            source_allowed = selected_sources is None or source in selected_sources
            if source_allowed and (doc_group in user_groups or "admin" in user_groups):
                docs.append({"text": doc_text, "metadata": metadata})

    return docs[:top_k]


def add_memory_turn(memory, question, answer, max_turns=12):
    memory.append({"role": "human", "content": question})
    memory.append({"role": "ai", "content": answer})
    max_messages = max_turns * 2
    if len(memory) > max_messages:
        del memory[:-max_messages]


def generate_answer(
    question,
    docs,
    memory=None,
    interaction_mode="unified",
    model_name=None,
    agency_context="",
    brain_context="",
    show_sources=False,
    assistant_profile="",
    fast_response=False,
):
    mode = get_interaction_mode(interaction_mode)
    model_name = choose_llm_model(
        model_name,
        question=question,
        docs=docs,
        brain_context=brain_context,
    )
    if not model_name:
        response = (
            "No hay modelos de Ollama instalados todavia. "
            f"Descarga uno con: `ollama pull {RECOMMENDED_OLLAMA_MODEL}`. "
            "Despues vuelve a intentarlo."
        )
        response = clean_answer_text(response)
        if memory is not None:
            add_memory_turn(memory, question, response)
        return response

    if not docs and not agency_context and not brain_context:
        response = clean_answer_text("No encontre informacion relevante en la base de conocimiento para responder esa pregunta.")
        if memory is not None:
            add_memory_turn(memory, question, response)
        return response

    context = ""
    uploaded_prompt_docs = []
    for doc in docs or []:
        metadata = doc["metadata"]
        source_type = metadata.get("type", "fuente")
        title = metadata.get("title", metadata.get("source", "fuente"))
        if metadata.get("uploaded_file") or str(metadata.get("source", "")).startswith("upload:"):
            uploaded_prompt_docs.append(doc)
            continue
        context += f"[{source_type} {title}]\n{trim_prompt_text(doc['text'], MAX_DOC_CONTEXT_CHARS)}\n\n"

    if not context and not uploaded_prompt_docs:
        context = "No se recuperaron fuentes privadas relevantes para esta pregunta.\n"

    agency_section = ""
    if agency_context:
        agency_section = f"""
Base Agency:
{agency_context}

Reglas para usar Agency:
- Usa Agency como metodologia interna y como apoyo experto.
- Prioriza el contexto privado cuando exista.
- Si solo Agency respalda una recomendacion, dilo como criterio experto o inferencia.
- No inventes que un especialista ejecuto acciones reales; solo usa su enfoque.
"""

    brain_section = ""
    if brain_context:
        brain_section = f"""
Capa Jarvis/OpenJarvis:
{brain_context}
"""

    history_text = ""
    if memory:
        recent_memory = memory[-(PROMPT_HISTORY_TURNS * 2):]
        for message in recent_memory:
            if message.get("role") == "human":
                history_text += f"Estudiante: {trim_prompt_text(message.get('content', ''), 500)}\n"
            elif message.get("role") == "ai":
                history_text += f"Tutor: {trim_prompt_text(message.get('content', ''), 900)}\n"
        if history_text:
            history_text = "Historial de la conversacion:\n" + history_text + "\n"

    source_rule = (
        "- Si el usuario pidio fuentes, menciona solo los titulos estrictamente necesarios al final.\n"
        if show_sources
        else "- No cites fuentes, no agregues secciones de fuentes y no digas 'segun el documento'; usa el contexto en silencio para construir una respuesta inteligente.\n"
    )
    assistant_profile_text = (
        "Perfil conectado: Asistente de Programacion de ABRAHAM-HERNANDEZ-MAIN.\n"
        "Contexto conectado: ChromaDB vectores/brain_db y base conocimiento.\n"
        if assistant_profile
        else ""
    )

    if fast_response:
        support = "\n".join(
            part
            for part in [
                trim_prompt_text(agency_context, WEB_FAST_SUPPORT_CHARS) if agency_context else "",
                trim_prompt_text(brain_context, WEB_FAST_SUPPORT_CHARS) if brain_context else "",
            ]
            if part
        )
        prompt = f"""
Eres TUTOR_IA, un tutor tecnico local conectado a la base privada del usuario.
Eres un Asistente de Programacion experto. Tu funcion principal es ayudar al usuario a crear, analizar, explicar, corregir y mejorar soluciones tecnicas de software.
Dominas Python, C#, SQL, diseno de bases de datos, ciberseguridad defensiva, APIs, backend, frontend, algoritmos, arquitectura de software, Streamlit, Flask, FastAPI, HTML, CSS, JavaScript, Power BI y n8n.
Si el usuario pide crear codigo, SQL o una estructura, entrega la solucion completa aunque el modo sea rapido.
Usa el contexto solo si aporta valor. Si falta informacion, dilo y da el siguiente paso minimo.
La instruccion del usuario tiene prioridad sobre el contexto recuperado.
{source_rule}

Contexto:
{trim_prompt_text(context, WEB_FAST_CONTEXT_CHARS)}

Apoyo interno:
{support or "Sin apoyo adicional."}

Pregunta: {question}
Respuesta:
"""
    else:
        prompt = f"""
Eres el cerebro de una aplicacion y pagina web tipo NotebookLM, conectado a una base de conocimiento privada.
{assistant_profile_text}
Tu modo actual es: {mode["label"]}.

Reglas generales:
- Eres un Asistente de Programacion experto. Tu funcion principal es ayudar al usuario a crear, analizar, explicar, corregir y mejorar soluciones tecnicas de software.
- Dominas Python, C#, SQL, diseno de bases de datos, ciberseguridad defensiva, APIs, backend, frontend, algoritmos, estructuras logicas, arquitectura de software, Streamlit, Flask, FastAPI, HTML, CSS, JavaScript, Power BI y n8n.
- Las solicitudes normales de programacion, bases de datos, APIs, ciberseguridad defensiva, aprendizaje y proyectos academicos son permitidas. No debes rechazarlas falsamente.
- Si el usuario pide crear codigo, crealo. Si pide una base de datos, entrega SQL completo. Si pide corregir codigo, identifica el error y ofrece la solucion.
- Si una fuente del Cerebro Unificado no devuelve informacion util, no inventes un rechazo; usa conocimiento general tecnico y responde con una solucion profesional.
- Lee y sintetiza el contexto como material interno; no copies fragmentos largos.
- Responde como tutor tecnico inteligente: directo, claro, practico y con criterio.
- Usa principalmente la informacion proporcionada en el contexto, pero integrala con razonamiento tecnico.
- Si falta informacion para una respuesta segura, dilo en una frase y da el mejor siguiente paso.
- Puedes hacer inferencias utiles, pero marcalas como inferencias cuando no esten explicitas en el contexto.
- Responde en espanol claro.
- No uses negritas Markdown, no escribas ** y evita adornos innecesarios.
- Prioriza respuestas completas en tareas tecnicas; solo se breve cuando el usuario pida una explicacion simple.
{source_rule}

{mode["instructions"]}

{agency_section}
{brain_section}

{history_text}
Contexto:
{context}

Pregunta del estudiante: {question}
Respuesta del tutor:
"""
    if uploaded_prompt_docs:
        tutor_context = "\n".join(
            part
            for part in [
                source_rule,
                mode["instructions"],
                agency_section,
                brain_section,
                history_text,
                f"Contexto recuperado de tutor_ia:\n{context}" if context else "",
            ]
            if part
        )
        prompt = build_prompt(question, uploaded_prompt_docs, tutor_context)

    try:
        extended_fast = needs_extended_fast_answer(question, uploaded_prompt_docs or docs)
        llm = get_fast_llm(model_name, extended_fast) if fast_response else get_llm(model_name)
        llm_started = time.perf_counter()
        response = llm.invoke(prompt)
        log_bridge(
            f"ollama response model={model_name} fast={fast_response} extended={extended_fast} seconds={time.perf_counter() - llm_started:.2f} prompt_chars={len(prompt)}"
        )
    except Exception as exc:
        log_bridge(f"ollama error model={model_name} error={exc}")
        detail = str(exc)
        if "requires more system memory" in detail or "more system memory" in detail:
            response = (
                f"El modelo `{model_name}` es demasiado grande para la memoria disponible ahora. "
                f"Usa un modelo mas ligero: `ollama pull {RECOMMENDED_OLLAMA_MODEL}`."
            )
        else:
            response = (
                f"No pude usar el modelo `{model_name}` en Ollama. "
                f"Verifica que este instalado con `ollama list` o descargalo con "
                f"`ollama pull {model_name}`. Detalle: {exc}"
            )

    response = clean_answer_text(response)
    if memory is not None:
        add_memory_turn(memory, question, response)
    return response


def generate_general_answer(
    question,
    file_docs=None,
    memory=None,
    interaction_mode="unified",
    model_name=None,
    fast_response=False,
):
    mode = get_interaction_mode(interaction_mode)
    model_name = choose_llm_model(
        model_name,
        question=question,
        docs=file_docs,
    )
    if not model_name:
        response = (
            "No hay modelos de Ollama instalados todavia. "
            f"Descarga uno con: `ollama pull {RECOMMENDED_OLLAMA_MODEL}`. "
            "Despues vuelve a intentarlo."
        )
        response = clean_answer_text(response)
        if memory is not None:
            add_memory_turn(memory, question, response)
        return response

    file_context = ""
    for doc in file_docs or []:
        metadata = doc.get("metadata", {})
        title = metadata.get("title", "archivo")
        file_context += f"[archivo {title}]\n{trim_prompt_text(doc.get('text', ''), MAX_UPLOAD_PROMPT_CHARS)}\n\n"

    history_text = ""
    if memory:
        recent_memory = memory[-(PROMPT_HISTORY_TURNS * 2):]
        for message in recent_memory:
            if message.get("role") == "human":
                history_text += f"Usuario: {trim_prompt_text(message.get('content', ''), 500)}\n"
            elif message.get("role") == "ai":
                history_text += f"Asistente: {trim_prompt_text(message.get('content', ''), 900)}\n"
        if history_text:
            history_text = "Historial de la conversacion:\n" + history_text + "\n"

    prompt = f"""
Eres un asistente de programacion senior dentro de ABRAHAM-HERNANDEZ-MAIN.
El chip Cerebro tutor_ia esta desactivado, asi que no uses ni afirmes usar fuentes privadas.
Tu modo actual es: {mode["label"]}.

Reglas:
- Responde en espanol claro.
- Ayuda con HTML, CSS, JavaScript, Python, Flask, bases de datos, APIs y depuracion.
- Si faltan datos, dilo y da el siguiente paso mas util.
- No inventes fuentes privadas ni resultados web.
- Si hay archivos adjuntos, usalos como contexto de trabajo.

{history_text}
Archivos adjuntos:
{file_context or "No hay archivos adjuntos con texto extraible."}

Pregunta del usuario: {question}
Respuesta:
"""
    if file_docs:
        tutor_context = (
            "Cerebro tutor_ia desactivado para esta consulta; usa solo el archivo adjunto y conocimiento tecnico general.\n"
            f"{history_text}"
        )
        prompt = build_prompt(question, file_docs, tutor_context)
    try:
        extended_fast = needs_extended_fast_answer(question, file_docs)
        llm = get_fast_llm(model_name, extended_fast) if fast_response else get_llm(model_name)
        llm_started = time.perf_counter()
        response = llm.invoke(prompt)
        log_bridge(
            f"ollama response model={model_name} fast={fast_response} extended={extended_fast} seconds={time.perf_counter() - llm_started:.2f} prompt_chars={len(prompt)}"
        )
    except Exception as exc:
        log_bridge(f"ollama error model={model_name} error={exc}")
        response = (
            f"No pude usar el modelo `{model_name}` en Ollama. "
            f"Verifica que este instalado con `ollama list`. Detalle: {exc}"
        )

    response = clean_answer_text(response)
    if memory is not None:
        add_memory_turn(memory, question, response)
    return response


def answer_from_brain(payload, uploaded_files=None):
    started_at = time.perf_counter()
    question = str(payload.get("message") or payload.get("question") or "").strip()
    if not question:
        raise ValueError("La pregunta esta vacia.")

    session_id = str(payload.get("session_id") or "default")[:120]
    memory = memory_store.setdefault(session_id, [])
    raw_mode = payload.get("mode") or payload.get("interaction_mode") or "unified"
    interaction_mode = normalize_interaction_mode(raw_mode)
    user_groups = normalize_groups(WEB_ACCESS_GROUPS)
    selected_sources = payload.get("selected_sources")
    agency_enabled = payload_bool(payload, "agency_enabled", True)
    client_name = str(payload.get("client") or "")
    response_profile = str(payload.get("response_profile") or "web_fast").lower()
    fast_profile = response_profile not in {"full", "deep", "balanced"}
    show_sources = payload_bool(payload, "show_sources", False) or source_requested(question)
    tutor_ia_enabled = payload_bool(payload, "tutorIA", payload_bool(payload, "tutor_ia", True))
    smart_search_enabled = payload_bool(payload, "smartSearch", payload_bool(payload, "smart_search", False))
    notebooklm_enabled = payload_notebooklm_enabled(payload)
    notebooklm_active_id = payload_notebooklm_id(payload)
    k = int(payload.get("k") or (4 if fast_profile else RETRIEVE_CANDIDATES))
    top_k = int(payload.get("top_k") or (1 if fast_profile else RESPONSE_TOP_K))
    include_obsidian = tutor_ia_enabled and payload_bool(payload, "include_obsidian", True)
    obsidian_top_k = int(payload.get("obsidian_top_k") or (1 if fast_profile else OBSIDIAN_TOP_K))
    project_path = str(payload.get("project_path") or payload.get("workspace_path") or "").strip()
    quick_code_limit = WEB_FAST_QUICK_CODE_CHARS if fast_profile else 6000
    quick_code_context = str(payload.get("quick_code_context") or payload.get("code_context") or "")[:quick_code_limit].strip()
    uploaded_files = uploaded_files or []
    indexed_upload_chunks = index_uploaded_files(uploaded_files, session_id=session_id) if uploaded_files else 0
    file_docs = build_uploaded_file_docs(uploaded_files, question=question)
    has_readable_upload = any(file_info.get("accepted") and file_info.get("content") for file_info in uploaded_files)
    log_bridge(
        f"flow files_read={len(uploaded_files)} readable={has_readable_upload} file_docs={len(file_docs)} indexed_chunks={indexed_upload_chunks}"
    )
    notebooklm_docs = []
    notebooklm_result = None
    notebooklm_error = ""
    requested_model = payload.get("model")
    requested_model_text = str(requested_model or "").strip()
    if fast_profile and (
        not requested_model_text
        or requested_model_text == AUTO_MODEL_OPTION
        or requested_model_text.lower() == "auto"
    ):
        requested_model = os.getenv("TUTOR_IA_FAST_MODEL", "").strip() or RECOMMENDED_OLLAMA_MODEL

    if not has_readable_upload and is_simple_conversation(question):
        answer = simple_conversation_answer(
            question,
            tutor_ia_enabled=tutor_ia_enabled,
            smart_search_enabled=smart_search_enabled,
        )
        add_memory_turn(memory, question, answer)
        return {
            "ok": True,
            "success": True,
            "answer": answer,
            "mode": str(raw_mode),
            "brain_mode": get_interaction_mode(interaction_mode)["label"],
            "tutorIA": tutor_ia_enabled,
            "smartSearch": smart_search_enabled,
            "notebookLM": notebooklm_enabled,
            "usedTutorIA": False,
            "usedSmartSearch": False,
            "usedNotebookLM": False,
            "smart_search": None,
            "show_sources": False,
            "used_sources_count": 0,
            "model": "local_simple_conversation",
            "brain_error": "",
            "obsidian_used_count": 0,
            "workspace_used_count": 0,
            "quick_code_used": False,
            "jarvis_profile": "",
            "brain_parts": ["simple_conversation"],
            "notebooklm": None,
            "sources": [],
            "uploadedFiles": [],
            "agency_agents": [],
        }

    if fast_profile and tutor_ia_enabled and is_status_question(question):
        model = choose_llm_model(requested_model, question=question)
        try:
            fragments = get_collection().count()
        except Exception:
            fragments = 0
        answer = (
            f"Si, TUTOR_IA esta conectado. Modelo rapido activo: {model or 'sin modelo'}; "
            f"base privada: {fragments} fragmentos; Obsidian: {'activo' if OBSIDIAN_ENABLED else 'desactivado'}."
        )
        add_memory_turn(memory, question, answer)
        return {
            "ok": True,
            "success": True,
            "answer": answer,
            "mode": str(raw_mode),
            "brain_mode": get_interaction_mode(interaction_mode)["label"],
            "tutorIA": tutor_ia_enabled,
            "smartSearch": smart_search_enabled,
            "notebookLM": notebooklm_enabled,
            "usedTutorIA": tutor_ia_enabled,
            "usedSmartSearch": False,
            "usedNotebookLM": False,
            "smart_search": None,
            "show_sources": False,
            "used_sources_count": 0,
            "model": model,
            "brain_error": "",
            "obsidian_used_count": 0,
            "workspace_used_count": 0,
            "quick_code_used": False,
            "jarvis_profile": "",
            "brain_parts": ["status"],
            "notebooklm": None,
            "sources": [],
            "uploadedFiles": [],
            "agency_agents": [],
        }

    if detect_technical_intent and classify_safety and resolve_user_request:
        technical_intent = detect_technical_intent(question, memory)
        resolved_question = technical_intent.get("resolved_request") or resolve_user_request(question, memory)
        safety = classify_safety(resolved_question, technical_intent, memory)
        LOGGER.info(
            "Bridge diagnostic original=%r resolved=%r intent=%s safety=%s",
            question,
            resolved_question,
            technical_intent,
            safety,
        )

        if technical_intent.get("needs_clarification") and not has_readable_upload:
            answer = "¿Te refieres a la base de datos, una página, un CRUD u otra estructura?"
            add_memory_turn(memory, question, answer)
            return {
                "ok": True,
                "success": True,
                "answer": answer,
                "mode": str(raw_mode),
                "brain_mode": get_interaction_mode(interaction_mode)["label"],
                "tutorIA": tutor_ia_enabled,
                "smartSearch": smart_search_enabled,
                "notebookLM": notebooklm_enabled,
                "usedTutorIA": tutor_ia_enabled,
                "usedSmartSearch": False,
                "usedNotebookLM": False,
                "smart_search": None,
                "show_sources": False,
                "used_sources_count": 0,
                "model": choose_llm_model(requested_model, question=resolved_question),
                "brain_error": "",
                "obsidian_used_count": 0,
                "workspace_used_count": 0,
                "quick_code_used": False,
                "jarvis_profile": "",
                "brain_parts": ["conversation_context", "technical_intent_router"],
                "notebooklm": None,
                "sources": [],
                "uploadedFiles": [public_uploaded_file(file_info) for file_info in uploaded_files],
                "agency_agents": [],
                "resolved_message": resolved_question,
                "intent": technical_intent,
                "safety": safety,
            }

        if not safety.get("allowed", True):
            answer = safe_refusal_only_if_really_needed(str(safety.get("reason") or "")) if safe_refusal_only_if_really_needed else "No puedo ayudar con esa solicitud."
            add_memory_turn(memory, question, answer)
            return {
                "ok": True,
                "success": True,
                "answer": answer,
                "mode": str(raw_mode),
                "brain_mode": get_interaction_mode(interaction_mode)["label"],
                "tutorIA": tutor_ia_enabled,
                "smartSearch": smart_search_enabled,
                "notebookLM": notebooklm_enabled,
                "usedTutorIA": tutor_ia_enabled,
                "usedSmartSearch": False,
                "usedNotebookLM": False,
                "smart_search": None,
                "show_sources": False,
                "used_sources_count": 0,
                "model": choose_llm_model(requested_model, question=resolved_question),
                "brain_error": "",
                "obsidian_used_count": 0,
                "workspace_used_count": 0,
                "quick_code_used": False,
                "jarvis_profile": "",
                "brain_parts": ["safety_filter"],
                "notebooklm": None,
                "sources": [],
                "uploadedFiles": [public_uploaded_file(file_info) for file_info in uploaded_files],
                "agency_agents": [],
                "resolved_message": resolved_question,
                "intent": technical_intent,
                "safety": safety,
            }

        if (
            generate_technical_answer
            and should_use_technical_generator
            and should_use_technical_generator(technical_intent)
            and not has_readable_upload
        ):
            answer = generate_technical_answer(resolved_question, technical_intent)
            add_memory_turn(memory, question, answer)
            source_name = "database_generator" if str(technical_intent.get("resolved_intent") or technical_intent.get("intent")) in {"database_design", "sql", "sql_generation", "er_model"} else "technical_generators"
            return {
                "ok": True,
                "success": True,
                "answer": answer,
                "mode": str(raw_mode),
                "brain_mode": get_interaction_mode(interaction_mode)["label"],
                "tutorIA": tutor_ia_enabled,
                "smartSearch": smart_search_enabled,
                "notebookLM": notebooklm_enabled,
                "usedTutorIA": tutor_ia_enabled,
                "usedSmartSearch": False,
                "usedNotebookLM": False,
                "smart_search": None,
                "show_sources": False,
                "used_sources_count": 1,
                "model": "technical_template",
                "brain_error": "",
                "obsidian_used_count": 0,
                "workspace_used_count": 0,
                "quick_code_used": False,
                "jarvis_profile": "",
                "brain_parts": ["conversation_context", "technical_intent_router", "safety_filter", source_name],
                "notebooklm": None,
                "sources": [{"metadata": {"source": source_name, "title": source_name, "type": "technical_template"}, "snippet": trim_prompt_text(answer, 260)}],
                "uploadedFiles": [public_uploaded_file(file_info) for file_info in uploaded_files],
                "agency_agents": [],
                "resolved_message": resolved_question,
                "intent": technical_intent,
                "safety": safety,
            }

    if has_readable_upload and is_database_request(question):
        answer = generate_uploaded_database_solution(question, uploaded_files, file_docs, project_path=project_path)
        add_memory_turn(memory, question, answer)
        return {
            "ok": True,
            "success": True,
            "answer": answer,
            "mode": str(raw_mode),
            "brain_mode": get_interaction_mode(interaction_mode)["label"],
            "tutorIA": tutor_ia_enabled,
            "smartSearch": smart_search_enabled,
            "notebookLM": notebooklm_enabled,
            "usedTutorIA": tutor_ia_enabled,
            "usedSmartSearch": False,
            "usedNotebookLM": False,
            "smart_search": None,
            "notebooklm": None,
            "show_sources": show_sources,
            "used_sources_count": len(file_docs),
            "model": "local_database_generator",
            "latency_ms": int((time.perf_counter() - started_at) * 1000),
            "brain_error": "",
            "obsidian_used_count": 0,
            "workspace_used_count": 0,
            "quick_code_used": False,
            "notebooklm_used_count": 0,
            "jarvis_profile": "",
            "brain_parts": ["uploaded_files", "tutor_ia_upload_index", "database_generator"],
            "sources": [
                {
                    "metadata": doc.get("metadata", {}),
                    "snippet": trim_prompt_text(doc.get("text", ""), 260),
                }
                for doc in file_docs
            ],
            "uploadedFiles": [public_uploaded_file(file_info) for file_info in uploaded_files],
            "agency_agents": [],
        }

    brain_error = ""
    obsidian_docs = []
    workspace_docs = []
    quick_code_docs = []
    agency_matches = []
    agency_context = ""
    brain_profile = str(payload.get("jarvis_profile") or payload.get("brain_profile") or "unified")
    brain_context = ""
    brain_parts = []

    if build_quick_code_docs:
        quick_code_docs = build_quick_code_docs(quick_code_context, source="payload:quick-code")
    elif quick_code_context:
        quick_code_docs = [
            {
                "text": quick_code_context,
                "metadata": {
                    "source": "payload:quick-code",
                    "title": "Codigo o requerimiento rapido",
                    "type": "code",
                },
            }
        ]

    def local_sources_provider(message, options, route):
        nonlocal brain_error, obsidian_docs, workspace_docs
        contexts = []
        uploaded_docs = file_docs + quick_code_docs
        if uploaded_docs:
            contexts.append(
                BrainSourceContext(
                    source="uploaded_files",
                    success=True,
                    confidence=0.95,
                    content="\n\n".join(trim_prompt_text(doc.get("text", ""), MAX_UPLOAD_PROMPT_CHARS) for doc in uploaded_docs),
                    metadata={"docs": uploaded_docs},
                )
            )

        local_docs = []
        if tutor_ia_enabled:
            try:
                local_docs = retrieve(
                    message,
                    user_groups=user_groups,
                    k=k,
                    top_k=top_k,
                    selected_sources=selected_sources,
                )
            except Exception as exc:
                brain_error = str(exc)

            obsidian_docs = retrieve_obsidian(message, top_k=obsidian_top_k) if include_obsidian else []
            if selected_sources is not None:
                selected_source_set = set(selected_sources)
                obsidian_docs = [
                    doc
                    for doc in obsidian_docs
                    if doc.get("metadata", {}).get("source") in selected_source_set
                ]
            if project_path and retrieve_connected_workspace_docs:
                workspace_docs = retrieve_connected_workspace_docs(message, project_path)
            elif project_path and retrieve_workspace_context:
                workspace_docs = retrieve_workspace_context(message, project_path)
        all_local_docs = local_docs + obsidian_docs + workspace_docs
        if all_local_docs:
            contexts.append(
                BrainSourceContext(
                    source="local_sources",
                    success=True,
                    confidence=0.82,
                    content="\n\n".join(
                        f"[{doc.get('metadata', {}).get('title', doc.get('metadata', {}).get('source', 'fuente'))}] "
                        f"{trim_prompt_text(doc.get('text', ''), 600)}"
                        for doc in all_local_docs[:6]
                    ),
                    metadata={"docs": all_local_docs},
                )
            )
        return contexts

    def notebooklm_provider(message, options, route):
        nonlocal notebooklm_result, notebooklm_error, notebooklm_docs
        service = get_notebooklm_service(enabled=True, active_notebook_id=notebooklm_active_id)
        if not service:
            notebooklm_error = "Cerebro NotebookLM no esta disponible en este entorno."
            return BrainSourceContext(source="notebooklm", success=False, error=notebooklm_error)
        notebooklm_result = service.ask(message, notebook_id=notebooklm_active_id)
        if notebooklm_result.ok and notebooklm_result.answer and notebooklm_result_to_doc:
            notebook_doc = notebooklm_result_to_doc(
                notebooklm_result.to_dict(),
                notebook_id=notebooklm_active_id,
                question=message,
                max_chars=WEB_FAST_CONTEXT_CHARS if fast_profile else 1800,
            )
            if notebook_doc:
                notebooklm_docs = [notebook_doc]
                return BrainSourceContext(
                    source="notebooklm",
                    success=True,
                    confidence=0.8,
                    content=notebook_doc["text"],
                    references=notebooklm_result.references,
                    metadata={"docs": notebooklm_docs, "result": notebooklm_result.to_dict()},
                )
        notebooklm_error = notebooklm_status_message(notebooklm_result) if notebooklm_status_message else ""
        return BrainSourceContext(source="notebooklm", success=False, error=notebooklm_error)

    def agency_provider(message, options, route):
        nonlocal agency_matches, agency_context
        if not (tutor_ia_enabled and agency_enabled and retrieve_agency_agents and build_agency_context):
            return BrainSourceContext(source="agency", success=False, error="Agency desactivado")
        agency_matches = retrieve_agency_agents(message, limit=AGENCY_MATCH_LIMIT)
        agency_context = build_agency_context(agency_matches, max_chars=AGENCY_CONTEXT_CHARS)
        return BrainSourceContext(
            source="agency",
            success=bool(agency_context),
            confidence=0.7,
            content=agency_context,
            metadata={"agency_matches": agency_matches},
        )

    def openjarvis_provider(message, options, route):
        nonlocal brain_context, brain_profile, brain_parts
        if tutor_ia_enabled and build_connected_brain_context:
            brain_bundle = build_connected_brain_context(
                message,
                interaction_mode=interaction_mode,
                brain_profile=brain_profile,
                workspace_path=project_path,
                quick_code_context=quick_code_context,
            )
            brain_context = brain_bundle["context"]
            brain_profile = brain_bundle["profile"]
            brain_parts = brain_bundle["parts"]
        elif tutor_ia_enabled and interaction_mode == "unified" and build_unified_brain_context:
            brain_context_parts = [build_unified_brain_context()]
            if build_programming_skills_context:
                brain_context_parts.append(build_programming_skills_context(f"{message}\n{quick_code_context}"))
            if project_path and build_workspace_brain_context:
                brain_context_parts.append(build_workspace_brain_context(project_path))
            brain_context = "\n\n".join(part for part in brain_context_parts if part)
            brain_profile = "unified"
            brain_parts = ["unified_brain", "programming_skills", "workspace"]
        elif tutor_ia_enabled and interaction_mode == "programming" and build_profile_context:
            brain_context = build_profile_context(brain_profile)
            brain_parts = ["jarvis_profile"]
        if fast_profile:
            brain_context = trim_prompt_text(brain_context, WEB_FAST_BRAIN_CONTEXT_CHARS)
        return BrainSourceContext(
            source="openjarvis",
            success=bool(brain_context),
            confidence=0.65,
            content=brain_context,
            metadata={"brain_profile": brain_profile, "brain_parts": brain_parts},
        )

    def web_provider(message, options, route):
        search = smart_web_search(message)
        content = search.get("message", "")
        return BrainSourceContext(
            source="web_search",
            success=bool(search.get("enabled")),
            confidence=0.55,
            content=content,
            error="" if search.get("enabled") else content,
            metadata={"smart_search": search},
        )

    def tools_provider(message, options, route):
        content = safe_tools_context(message, route)
        return BrainSourceContext(
            source="tools",
            success=bool(content),
            confidence=0.6,
            content=content,
            metadata={"route": route},
        )

    brain_options = {
        "fast_mode": fast_profile,
        "deep_thinking": payload_bool(payload, "deep_thinking", response_profile in {"deep", "full"}),
        "web_search": smart_search_enabled,
        "notebooklm": notebooklm_enabled,
        "agency": agency_enabled,
        "openjarvis": True,
        "local_sources": tutor_ia_enabled or bool(file_docs or quick_code_docs),
        "tools": payload_bool(payload, "tools", True),
    }
    unified_brain = UnifiedBrain(
        providers={
            "local_sources": local_sources_provider,
            "notebooklm": notebooklm_provider,
            "agency": agency_provider,
            "openjarvis": openjarvis_provider,
            "web_search": web_provider,
            "tools": tools_provider,
        },
        status_provider=unified_brain_status_payload,
    )
    route = unified_brain.route_question(question)
    contexts = unified_brain.collect_context(question, brain_options, route)
    merged_contexts = unified_brain.merge_contexts(contexts)
    docs = contexts_to_docs(merged_contexts)
    log_bridge(
        f"tutor_ia context loaded docs={len(docs)} contexts={len(merged_contexts)} brain_parts={len(brain_parts)} elapsed_ms={int((time.perf_counter() - started_at) * 1000)}"
    )
    agency_contexts = context_by_source(merged_contexts, "agency")
    if agency_contexts and not agency_context:
        agency_context = context_content(agency_contexts[0])
        agency_matches = context_metadata(agency_contexts[0]).get("agency_matches", [])
    openjarvis_contexts = context_by_source(merged_contexts, "openjarvis")
    if openjarvis_contexts and not brain_context:
        brain_context = context_content(openjarvis_contexts[0])
        brain_profile = context_metadata(openjarvis_contexts[0]).get("brain_profile", brain_profile)
        brain_parts = context_metadata(openjarvis_contexts[0]).get("brain_parts", brain_parts)
    web_contexts = context_by_source(contexts, "web_search")
    smart_search = context_metadata(web_contexts[0]).get("smart_search") if web_contexts else None

    if tutor_ia_enabled:
        if fast_profile and not docs and not agency_context and not brain_context:
            answer = generate_general_answer(
                question,
                file_docs=file_docs + quick_code_docs + notebooklm_docs,
                memory=memory,
                interaction_mode=interaction_mode,
                model_name=requested_model,
                fast_response=True,
            )
        else:
            answer = generate_answer(
                question,
                docs,
                memory,
                interaction_mode=interaction_mode,
                model_name=requested_model,
                agency_context=agency_context,
                brain_context=brain_context,
                show_sources=show_sources,
                assistant_profile=client_name,
                fast_response=fast_profile,
            )
    else:
        answer = generate_general_answer(
            question,
            file_docs=file_docs + quick_code_docs + notebooklm_docs,
            memory=memory,
            interaction_mode=interaction_mode,
            model_name=requested_model,
            fast_response=fast_profile,
        )

    if smart_search_enabled:
        if smart_search is None:
            smart_search = smart_web_search(question)
        if not smart_search.get("enabled"):
            notice = smart_search.get("message") or SMART_SEARCH_UNCONFIGURED_MESSAGE
            answer = f"{answer}\n\n{notice}" if answer else notice

    return {
        "ok": True,
        "success": True,
        "answer": answer,
        "mode": str(raw_mode),
        "brain_mode": get_interaction_mode(interaction_mode)["label"],
        "tutorIA": tutor_ia_enabled,
        "smartSearch": smart_search_enabled,
        "notebookLM": notebooklm_enabled,
        "usedTutorIA": tutor_ia_enabled,
        "usedSmartSearch": smart_search_enabled and bool(smart_search and smart_search.get("enabled")),
        "usedNotebookLM": bool(notebooklm_docs),
        "smart_search": smart_search,
        "notebooklm": {
            "enabled": notebooklm_enabled,
            "active_notebook_id": notebooklm_active_id,
            "ok": bool(notebooklm_result and notebooklm_result.ok),
            "message": notebooklm_error,
        },
        "show_sources": show_sources,
        "used_sources_count": len(docs),
        "model": choose_llm_model(
            requested_model,
            question=question,
            docs=docs,
            brain_context=brain_context,
        ),
        "latency_ms": int((time.perf_counter() - started_at) * 1000),
        "response_profile": "web_fast" if fast_profile else response_profile,
        "brain_error": brain_error,
        "obsidian_used_count": len(obsidian_docs),
        "workspace_used_count": len(workspace_docs),
        "quick_code_used": bool(quick_code_docs),
        "notebooklm_used_count": len(notebooklm_docs),
        "jarvis_profile": brain_profile if brain_context else "",
        "brain_parts": brain_parts,
        "sources": [
            {
                "metadata": doc.get("metadata", {}),
                "snippet": trim_prompt_text(doc.get("text", ""), 260),
            }
            for doc in docs
        ],
        "uploadedFiles": [public_uploaded_file(file_info) for file_info in uploaded_files],
        "agency_agents": agency_matches,
    }


def cors_origin(handler):
    origin = handler.headers.get("Origin")
    if not origin:
        return "*"
    normalized = origin.rstrip("/")
    if normalized == "null" and "null" in ALLOWED_ORIGINS:
        return origin
    parsed = urlparse(normalized)
    if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        return origin
    if "*" in ALLOWED_ORIGINS or normalized in ALLOWED_ORIGINS:
        return origin
    return ""


def json_response(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    allowed_origin = cors_origin(handler)
    if allowed_origin:
        handler.send_header("Access-Control-Allow-Origin", allowed_origin)
        handler.send_header("Vary", "Origin")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.end_headers()
    try:
        handler.wfile.write(body)
    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
        return


def read_request_payload(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    raw_body = handler.rfile.read(min(length, (MAX_UPLOAD_BYTES * 4) + (1024 * 1024)))
    content_type = handler.headers.get("Content-Type", "")
    if "multipart/form-data" in content_type.lower():
        return parse_multipart_form(content_type, raw_body)
    return json.loads(raw_body.decode("utf-8") or "{}"), []


def notebooklm_status_payload(check_auth=False):
    service = get_notebooklm_service(enabled=True)
    if not service:
        return {"enabled": False, "installed": False, "message": "notebooklm-py no esta disponible."}
    return service.get_status(check_auth=check_auth)


def notebooklm_list_payload():
    service = get_notebooklm_service(enabled=True)
    if not service:
        return {"ok": False, "notebooks": [], "message": "notebooklm-py no esta disponible."}
    result = service.list_notebooks()
    return {"ok": result.ok, "notebooks": result.data or [], "message": result.message}


def unified_brain_status_payload():
    fragments = 0
    try:
        fragments = get_collection().count()
    except Exception:
        pass

    agency_status = get_agency_status() if get_agency_status else {"available": False, "count": 0}
    jarvis_summary = get_jarvis_stack_summary() if get_jarvis_stack_summary else {}
    installed_models = get_installed_ollama_models()
    return {
        "mode": "local-first",
        "local_sources": fragments,
        "agency_specialists": agency_status.get("count", 0),
        "openjarvis": bool(jarvis_summary.get("openjarvis", {}).get("available")),
        "notebooklm": notebooklm_status_payload(check_auth=False),
        "voice": bool(jarvis_summary.get("jarvis_mlx", {}).get("speech_to_text")),
        "ollama_models": len(installed_models),
        "active_model": choose_llm_model(AUTO_MODEL_OPTION, brain_context="Cerebro Unificado"),
        "tools": sorted(jarvis_summary.get("tools", []))
        or ["calculator", "code_interpreter", "file_read", "file_write", "shell_exec", "think", "web_search"],
    }


class TutorBridgeHandler(BaseHTTPRequestHandler):
    server_version = "TutorIABridge/1.0"

    def log_message(self, format, *args):
        return

    def do_OPTIONS(self):
        json_response(self, 200, {"ok": True})

    def do_GET(self):
        path = self.path.rstrip("/")
        if path in {"/health", "/api/health", "/api/unified-brain/health"}:
            json_response(
                self,
                200,
                {
                    "ok": True,
                    "success": True,
                    "name": "TUTOR_IA",
                    "mode": "local-first",
                    "root_dir": str(TUTOR_ROOT),
                },
            )
            return
        if path in {"/status", "/api/status"}:
            json_response(self, 200, {"ok": True, "success": True, "brain": unified_brain_status_payload()})
            return
        if path == "/api/unified-brain/status":
            json_response(self, 200, {"ok": True, "success": True, "brain": unified_brain_status_payload()})
            return
        if path == "/api/unified-brain/sources":
            status = unified_brain_status_payload()
            json_response(
                self,
                200,
                {
                    "ok": True,
                    "success": True,
                    "sources": {
                        "local_sources": status["local_sources"],
                        "agency": status["agency_specialists"],
                        "openjarvis": status["openjarvis"],
                        "notebooklm": status["notebooklm"],
                        "tools": status["tools"],
                    },
                },
            )
            return
        if path == "/api/notebooklm/status":
            json_response(self, 200, {"ok": True, "notebooklm": notebooklm_status_payload(check_auth=True)})
            return
        if path == "/api/notebooklm/notebooks":
            payload = notebooklm_list_payload()
            json_response(self, 200 if payload.get("ok") else 503, payload)
            return

        if path != "/api/health":
            json_response(self, 404, {"ok": False, "error": "Ruta no encontrada."})
            return

        brain_error = ""
        try:
            fragments = get_collection().count()
        except Exception as exc:
            fragments = 0
            brain_error = str(exc)

        obsidian_status = get_obsidian_status()
        agency_status = get_agency_status() if get_agency_status else {"available": False, "count": 0}
        installed_models = get_installed_ollama_models()
        model_plan = get_model_plan(installed_models) if get_model_plan else {}
        if get_jarvis_stack_summary:
            jarvis_summary = get_jarvis_stack_summary()
            jarvis_status = {
                "openjarvis": jarvis_summary.get("openjarvis", {}),
                "jarvis_mlx": jarvis_summary.get("jarvis_mlx", {}),
                "detected_profiles": jarvis_summary.get("detected_profiles", 0),
                "tools": jarvis_summary.get("tools", []),
                "profiles": [
                    {
                        "key": profile.get("key"),
                        "label": profile.get("label"),
                        "available": profile.get("available"),
                    }
                    for profile in jarvis_summary.get("profiles", [])
                ],
            }
        else:
            jarvis_status = {"available": False}

        json_response(
            self,
            200,
            {
                "ok": True,
                "success": True,
                "name": "TUTOR_IA",
                "profile": "abraham-programming-assistant-ready",
                "fragments": fragments,
                "model": choose_llm_model(AUTO_MODEL_OPTION, brain_context="Cerebro Unificado"),
                "models": {
                    "installed": installed_models,
                    "routing": model_plan,
                },
                "root_dir": str(TUTOR_ROOT),
                "persist_dir": PERSIST_DIR,
                "brain_error": brain_error,
                "obsidian": obsidian_status,
                "agency": agency_status,
                "jarvis": jarvis_status,
                "notebooklm": notebooklm_status_payload(check_auth=False),
            },
        )

    def do_POST(self):
        global NOTEBOOKLM_ACTIVE_ID

        path = self.path.rstrip("/")
        if path == "/api/notebooklm/set-active":
            try:
                payload, _ = read_request_payload(self)
                notebook_id = str(payload.get("notebook_id") or payload.get("id") or "").strip()
                service = get_notebooklm_service(enabled=True, active_notebook_id=notebook_id)
                result = service.set_active_notebook(notebook_id) if service else None
                if result and result.ok:
                    NOTEBOOKLM_ACTIVE_ID = notebook_id
                json_response(
                    self,
                    200 if result and result.ok else 400,
                    result.to_dict() if result else {"ok": False, "message": "NotebookLM no disponible."},
                )
            except Exception as exc:
                json_response(self, 500, {"ok": False, "message": "No se pudo configurar NotebookLM.", "error": str(exc)})
            return

        if path == "/api/notebooklm/ask":
            try:
                payload, _ = read_request_payload(self)
                question = str(payload.get("question") or payload.get("message") or "").strip()
                notebook_id = str(payload.get("notebook_id") or NOTEBOOKLM_ACTIVE_ID or "").strip()
                service = get_notebooklm_service(enabled=True, active_notebook_id=notebook_id)
                result = service.ask(question, notebook_id=notebook_id) if service else None
                json_response(
                    self,
                    200 if result and result.ok else 503,
                    result.to_dict() if result else {"ok": False, "message": "NotebookLM no disponible."},
                )
            except Exception:
                json_response(self, 500, {"ok": False, "message": "NotebookLM no pudo responder."})
            return

        if path == "/api/notebooklm/add-url":
            try:
                payload, _ = read_request_payload(self)
                notebook_id = str(payload.get("notebook_id") or NOTEBOOKLM_ACTIVE_ID or "").strip()
                url = str(payload.get("url") or "").strip()
                service = get_notebooklm_service(enabled=True, active_notebook_id=notebook_id)
                result = service.add_url_source(notebook_id, url) if service else None
                json_response(
                    self,
                    200 if result and result.ok else 400,
                    result.to_dict() if result else {"ok": False, "message": "NotebookLM no disponible."},
                )
            except Exception:
                json_response(self, 500, {"ok": False, "message": "No se pudo agregar la URL a NotebookLM."})
            return

        if path == "/api/notebooklm/add-file":
            try:
                payload, uploaded_files = read_request_payload(self)
                notebook_id = str(payload.get("notebook_id") or NOTEBOOKLM_ACTIVE_ID or "").strip()
                service = get_notebooklm_service(enabled=True, active_notebook_id=notebook_id)
                result = None
                if uploaded_files:
                    file_info = uploaded_files[0]
                    suffix = file_info.get("extension") or Path(file_info.get("name", "source")).suffix
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                        temp_file.write(file_info.get("content", b""))
                        temp_path = temp_file.name
                    try:
                        result = service.add_file_source(notebook_id, temp_path) if service else None
                    finally:
                        try:
                            Path(temp_path).unlink(missing_ok=True)
                        except OSError:
                            pass
                else:
                    file_path = str(payload.get("file_path") or "").strip()
                    result = service.add_file_source(notebook_id, file_path) if service else None
                json_response(
                    self,
                    200 if result and result.ok else 400,
                    result.to_dict() if result else {"ok": False, "message": "NotebookLM no disponible."},
                )
            except Exception:
                json_response(self, 500, {"ok": False, "message": "No se pudo agregar el archivo a NotebookLM."})
            return

        if path == "/api/unified-brain/ask":
            try:
                payload, uploaded_files = read_request_payload(self)
                payload["response_profile"] = payload.get("response_profile") or "balanced"
                result = answer_from_brain(payload, uploaded_files=uploaded_files)
                json_response(self, 200, result)
            except Exception as exc:
                json_response(self, 500, {"ok": False, "error": str(exc)})
            return

        if path in {"/ask", "/chat", "/api/ask", "/api/brain/ask"}:
            try:
                payload, uploaded_files = read_request_payload(self)
                result = answer_from_brain(payload, uploaded_files=uploaded_files)
                json_response(self, 200, result)
            except Exception as exc:
                json_response(self, 500, {"ok": False, "success": False, "error": str(exc)})
            return

        if path != "/api/chat":
            json_response(self, 404, {"ok": False, "error": "Ruta no encontrada."})
            return

        try:
            payload, uploaded_files = read_request_payload(self)
            result = answer_from_brain(payload, uploaded_files=uploaded_files)
            json_response(self, 200, result)
        except Exception as exc:
            json_response(self, 500, {"ok": False, "error": str(exc)})


def main():
    host = os.getenv("TUTOR_IA_WEB_HOST", "127.0.0.1")
    port = int(os.getenv("TUTOR_IA_WEB_PORT", "8787"))
    server = ThreadingHTTPServer((host, port), TutorBridgeHandler)
    print(f"TUTOR_IA web bridge listening on http://{host}:{port}")
    print(f"TUTOR_IA root: {TUTOR_ROOT}")
    print(f"Chroma brain: {PERSIST_DIR}")
    print(f"Obsidian vault: {OBSIDIAN_VAULT_DIR}")
    print("Endpoints: GET /api/health, POST /api/chat, /api/notebooklm/*, /api/unified-brain/*")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
