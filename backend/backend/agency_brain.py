import hashlib
import math
import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path


AGENCY_AGENT_DIRS = {
    "academic",
    "design",
    "engineering",
    "finance",
    "game-development",
    "marketing",
    "paid-media",
    "product",
    "project-management",
    "sales",
    "spatial-computing",
    "specialized",
    "support",
    "testing",
}

SECTION_KEYWORDS = (
    "identity",
    "core mission",
    "critical rules",
    "core capabilities",
    "technical deliverables",
    "workflow process",
    "success metrics",
)

CATEGORY_HINTS = {
    "academic": "academico estudio aprendizaje investigacion historia psicologia geografia",
    "design": "diseno ui ux visual marca interfaz experiencia usuario",
    "engineering": "ingenieria codigo programacion software backend frontend datos seguridad devops",
    "finance": "finanzas contabilidad inversion impuestos presupuesto",
    "game-development": "juegos gameplay nivel narrativa unity unreal godot roblox",
    "marketing": "marketing contenido redes seo crecimiento lanzamiento marca",
    "paid-media": "anuncios publicidad ppc paid media pauta campana conversion",
    "product": "producto roadmap feedback priorizacion investigacion tendencia",
    "project-management": "proyecto gestion tareas sprint coordinacion planificacion",
    "sales": "ventas prospeccion propuesta pipeline cliente discovery",
    "spatial-computing": "xr espacial visionos realidad aumentada interfaz espacial",
    "specialized": "especializado agente orquestacion legal salud documento automatizacion",
    "support": "soporte cliente resumen operaciones reporte",
    "testing": "pruebas testing qa validacion auditoria rendimiento accesibilidad evidencia",
}

SPANISH_QUERY_HINTS = {
    "agente": "agent agents orchestrator workflow specialist",
    "agentes": "agent agents orchestrator workflow specialist",
    "automatizacion": "automation workflow agents orchestrator operations",
    "aprender": "learning study training academic tutor education",
    "cerebro": "brain memory agents orchestrator ai system",
    "codigo": "code software engineering developer review backend frontend",
    "contenido": "content marketing creator social media",
    "datos": "data database analytics engineer reporting",
    "diseno": "design ui ux visual brand",
    "estudio": "study academic learning tutor training",
    "finanzas": "finance accounting investment tax budget",
    "ideas": "product trend research strategy innovation",
    "ia": "ai artificial intelligence machine learning llm rag ollama ai engineer",
    "inteligencia": "ai artificial intelligence machine learning llm rag",
    "marketing": "marketing growth seo content social media",
    "orquestacion": "orchestrator workflow agents coordination pipeline",
    "plan": "project management sprint roadmap strategy",
    "programacion": "programming code software engineering developer",
    "pruebas": "testing qa validation reality checker evidence",
    "seguridad": "security threat detection compliance audit",
    "ventas": "sales pipeline proposal outreach account discovery",
}

QUERY_BOOSTS = {
    "agente": (
        ("name", "orchestrator", 0.32),
        ("name", "workflow", 0.22),
        ("category", "specialized", 0.04),
    ),
    "agentes": (
        ("name", "orchestrator", 0.32),
        ("name", "workflow", 0.22),
        ("category", "specialized", 0.04),
    ),
    "automatizacion": (
        ("search", "automation", 0.10),
        ("name", "orchestrator", 0.08),
    ),
    "aprender": (
        ("category", "academic", 0.08),
        ("search", "learning", 0.06),
        ("search", "training", 0.06),
    ),
    "codigo": (
        ("category", "engineering", 0.10),
        ("name", "developer", 0.08),
        ("name", "code", 0.06),
    ),
    "diseno": (
        ("category", "design", 0.12),
        ("name", "designer", 0.08),
    ),
    "ia": (
        ("name", "ai engineer", 0.20),
        ("search", "llm", 0.08),
        ("search", "machine learning", 0.08),
        ("category", "engineering", 0.04),
    ),
    "inteligencia": (
        ("name", "ai engineer", 0.18),
        ("search", "machine learning", 0.08),
        ("category", "engineering", 0.04),
    ),
    "orquestacion": (
        ("name", "orchestrator", 0.20),
        ("name", "workflow", 0.12),
    ),
    "programacion": (
        ("category", "engineering", 0.12),
        ("name", "ai engineer", 0.12),
        ("name", "senior developer", 0.08),
        ("name", "software architect", 0.08),
    ),
    "pruebas": (
        ("category", "testing", 0.12),
        ("name", "reality checker", 0.10),
    ),
}

TOKEN_RE = re.compile(r"[a-z0-9_]+")
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$", re.MULTILINE)
CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)


def _strip_accents(text):
    normalized = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _tokens(text):
    return TOKEN_RE.findall(_strip_accents(text).lower())


def _embed(text, dim=384):
    vector = [0.0] * dim
    previous = ""
    for token in _tokens(text):
        features = [token]
        if previous:
            features.append(f"{previous}_{token}")
        previous = token
        for feature in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "little", signed=False)
            index = value % dim
            vector[index] += 1.0 if value & 1 else -1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if not norm:
        return vector
    return [value / norm for value in vector]


def _dot(left, right):
    return sum(a * b for a, b in zip(left, right))


def _clean_text(text):
    text = CODE_BLOCK_RE.sub("", text or "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _trim(text, max_chars):
    text = re.sub(r"[ \t]+", " ", (text or "").strip())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _parse_frontmatter(raw):
    match = FRONTMATTER_RE.match(raw.lstrip("\ufeff"))
    if not match:
        return {}, raw

    metadata = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip('"').strip("'")
        metadata[key.strip().lower()] = value
    return metadata, raw[match.end() :]


def _extract_relevant_sections(body, max_sections=4, max_chars_each=1100):
    cleaned = _clean_text(body)
    headings = list(HEADING_RE.finditer(cleaned))
    sections = []

    for index, heading in enumerate(headings):
        title = _strip_accents(heading.group(2)).lower()
        if not any(keyword in title for keyword in SECTION_KEYWORDS):
            continue
        start = heading.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(cleaned)
        section_text = cleaned[start:end].strip()
        if section_text:
            sections.append(f"{heading.group(2).strip()}: {_trim(section_text, max_chars_each)}")
        if len(sections) >= max_sections:
            break

    if sections:
        return "\n".join(sections)

    return _trim(cleaned, max_sections * max_chars_each)


def _agency_root_candidates():
    env_path = os.getenv("TUTOR_IA_AGENCY_AGENTS_DIR")
    if env_path:
        yield Path(env_path).expanduser()

    here = Path(__file__).resolve().parent
    yield here / "agency-agents-main"
    yield here / "AGENCY-AGENTS-MAIN"
    yield here.parent / "agency-agents-main"
    yield here.parent / "AGENCY-AGENTS-MAIN"


def find_agency_root():
    for candidate in _agency_root_candidates():
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def _iter_agent_files(root):
    for category in sorted(AGENCY_AGENT_DIRS):
        category_dir = root / category
        if not category_dir.exists():
            continue
        for path in sorted(category_dir.rglob("*.md")):
            if path.name.lower() == "readme.md":
                continue
            yield path


def _load_agent(path, root):
    raw = path.read_text(encoding="utf-8", errors="replace")
    metadata, body = _parse_frontmatter(raw)
    name = metadata.get("name")
    description = metadata.get("description", "")
    if not name or not description:
        return None

    rel_path = path.relative_to(root)
    category = rel_path.parts[0] if rel_path.parts else "agency"
    summary = _extract_relevant_sections(body)
    category_hint = CATEGORY_HINTS.get(category, "")
    search_text = "\n".join(
        [
            name,
            description,
            category,
            category_hint,
            summary,
        ]
    )
    tokens = set(_tokens(search_text))

    return {
        "name": name,
        "description": description,
        "category": category,
        "path": str(path),
        "relative_path": str(rel_path).replace("\\", "/"),
        "summary": summary,
        "search_text": search_text,
        "tokens": tokens,
        "vector": _embed(search_text),
    }


@lru_cache(maxsize=8)
def load_agency_agents(root_path=None):
    root = Path(root_path) if root_path else find_agency_root()
    if not root:
        return []

    agents = []
    for path in _iter_agent_files(root):
        try:
            agent = _load_agent(path, root)
        except OSError:
            continue
        if agent:
            agents.append(agent)
    return agents


def clear_agency_cache():
    load_agency_agents.cache_clear()


def get_agency_status():
    root = find_agency_root()
    if not root:
        return {
            "available": False,
            "path": "",
            "count": 0,
            "categories": [],
            "message": "No se encontro agency-agents-main.",
        }

    agents = load_agency_agents(str(root))
    categories = sorted({agent["category"] for agent in agents})
    return {
        "available": bool(agents),
        "path": str(root),
        "count": len(agents),
        "categories": categories,
        "message": f"{len(agents)} agentes disponibles.",
    }


def _expand_query(question):
    normalized = " ".join(_tokens(question))
    additions = []
    for keyword, hint in SPANISH_QUERY_HINTS.items():
        if keyword in normalized:
            additions.append(hint)
    return " ".join([question or "", *additions])


def retrieve_agency_agents(question, limit=3):
    root = find_agency_root()
    if not root:
        return []

    agents = load_agency_agents(str(root))
    if not agents:
        return []

    expanded_query = _expand_query(question)
    query_vector = _embed(expanded_query)
    query_tokens = set(_tokens(expanded_query))
    original_tokens = set(_tokens(question))
    scored = []
    for agent in agents:
        vector_score = _dot(query_vector, agent["vector"])
        overlap = len(query_tokens & agent["tokens"]) / max(len(query_tokens), 1)
        score = (0.75 * vector_score) + (0.25 * overlap)
        name = _strip_accents(agent["name"]).lower()
        category = _strip_accents(agent["category"]).lower()
        search = _strip_accents(agent["summary"] + " " + agent["description"]).lower()
        for trigger in original_tokens:
            for target, needle, boost in QUERY_BOOSTS.get(trigger, ()):
                haystack = name if target == "name" else category if target == "category" else search
                if needle in haystack:
                    score += boost
        scored.append((score, agent))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {key: value for key, value in agent.items() if key not in {"vector", "tokens", "search_text"}}
        for score, agent in scored[: max(limit, 0)]
        if score > 0
    ]


def build_agency_context(matches, max_chars=6000):
    if not matches:
        return ""

    blocks = [
        "AGENCY-AGENTS-MAIN esta activo como capa metodologica interna.",
        "Usa los perfiles siguientes como especialistas de apoyo; no reemplazan las fuentes privadas del usuario.",
    ]
    for agent in matches:
        block = (
            f"Especialista: {agent['name']} ({agent['category']})\n"
            f"Descripcion: {agent.get('description', '')}\n"
            f"Archivo: {agent.get('relative_path', '')}\n"
            f"Metodo relevante:\n{agent.get('summary', '')}"
        )
        blocks.append(_trim(block, 2200))

    return _trim("\n\n".join(blocks), max_chars)
