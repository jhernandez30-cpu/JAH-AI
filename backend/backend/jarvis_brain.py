from __future__ import annotations

import os
import platform
import re
from functools import lru_cache
from pathlib import Path


DEFAULT_OPENJARVIS_ROOT = Path.home() / "Documents" / "OpenJarvis-main"
DEFAULT_JARVIS_MLX_ROOT = Path.home() / "Documents" / "jarvis-mlx-main"


PROFILE_LABELS = {
    "unified": "Cerebro Unificado",
    "orchestrator": "Orquestador",
    "architect": "Arquitecto",
    "debugger": "Debugger",
    "code-reviewer": "Code reviewer",
    "security-auditor": "Auditor seguro",
}

PROFILE_METHODS = {
    "unified": [
        "Integra estudio, organizacion, creatividad, programacion, revision y especialistas en una sola respuesta.",
        "Decide internamente que capacidad aplicar segun la pregunta, sin pedir al usuario elegir un modo.",
        "Conecta fuentes privadas, memoria, OpenJarvis, Agency y voz como partes del mismo cerebro.",
    ],
    "orchestrator": [
        "Descompone la tarea en pasos pequenos y verificables.",
        "Elige mentalmente la herramienta adecuada antes de responder.",
        "Cierra con una accion concreta o una prueba de validacion.",
    ],
    "architect": [
        "Evalua limites, contratos y dependencias antes de proponer cambios.",
        "Prefiere diseno simple, mantenible y compatible con el sistema actual.",
        "Explica trade-offs solo cuando afectan una decision real.",
    ],
    "debugger": [
        "Sigue el ciclo observar, formular hipotesis, probar y corregir.",
        "Busca la causa raiz antes de sugerir un parche.",
        "Propone la verificacion minima que confirmaria el arreglo.",
    ],
    "code-reviewer": [
        "Prioriza bugs de correctitud, seguridad, rendimiento y mantenibilidad.",
        "Da observaciones accionables con referencias a codigo cuando existan.",
        "Evita cambios de estilo que no reduzcan riesgo o confusion.",
    ],
    "security-auditor": [
        "Revisa entradas, secretos, permisos, autenticacion y exposicion de datos.",
        "Separa riesgo confirmado de riesgo probable.",
        "Recomienda mitigaciones concretas sin explotar vulnerabilidades.",
    ],
}


def _env_path(name: str, default: Path) -> Path:
    value = os.getenv(name)
    return Path(value).expanduser() if value else default


def _read_text(path: Path, limit: int = 16000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def _extract_string(text: str, key: str, default: str = "") -> str:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*=\s*\"([^\"]*)\"", text)
    return match.group(1).strip() if match else default


def _extract_int(text: str, key: str, default: int = 0) -> int:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*=\s*(\d+)", text)
    return int(match.group(1)) if match else default


def _extract_list(text: str, key: str) -> list[str]:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*=\s*\[([^\]]*)\]", text)
    if not match:
        return []
    return re.findall(r"\"([^\"]+)\"", match.group(1))


def _extract_multiline(text: str, key: str, default: str = "") -> str:
    match = re.search(
        rf"(?s)^\s*{re.escape(key)}\s*=\s*\"\"\"(.*?)\"\"\"",
        text,
        flags=re.MULTILINE,
    )
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else default


def _load_template(root: Path, name: str) -> dict:
    path = root / "src" / "openjarvis" / "templates" / "data" / f"{name}.toml"
    text = _read_text(path)
    if not text:
        return {}
    return {
        "key": _extract_string(text, "name", name),
        "label": PROFILE_LABELS.get(name, name.replace("-", " ").title()),
        "description": _extract_string(text, "description", ""),
        "agent_type": _extract_string(text, "type", ""),
        "max_turns": _extract_int(text, "max_turns", 0),
        "temperature": _extract_string(text, "temperature", ""),
        "tools": _extract_list(text, "tools"),
        "system_prompt": _extract_multiline(text, "system_prompt", ""),
        "source": str(path),
        "available": path.exists(),
    }


def _load_code_assistant_profile(root: Path) -> dict:
    path = root / "configs" / "openjarvis" / "examples" / "code-assistant.toml"
    text = _read_text(path)
    tools = _extract_list(text, "enabled")
    return {
        "key": "orchestrator",
        "label": PROFILE_LABELS["orchestrator"],
        "description": "Agente con ejecucion de codigo, lectura/escritura de archivos, shell y razonamiento.",
        "agent_type": _extract_string(text, "default_agent", "orchestrator"),
        "max_turns": _extract_int(text, "max_turns", 10),
        "temperature": "",
        "tools": tools or ["code_interpreter", "file_read", "file_write", "shell_exec", "think"],
        "system_prompt": "",
        "source": str(path),
        "available": path.exists(),
    }


@lru_cache(maxsize=1)
def get_openjarvis_status() -> dict:
    root = _env_path("TUTOR_IA_OPENJARVIS_ROOT", DEFAULT_OPENJARVIS_ROOT)
    templates_root = root / "src" / "openjarvis" / "templates" / "data"
    config_path = root / "configs" / "openjarvis" / "examples" / "code-assistant.toml"
    template_count = len(list(templates_root.glob("*.toml"))) if templates_root.exists() else 0
    return {
        "name": "OpenJarvis",
        "root": str(root),
        "available": root.exists(),
        "code_assistant": config_path.exists(),
        "template_count": template_count,
        "config_path": str(config_path),
    }


@lru_cache(maxsize=1)
def get_jarvis_mlx_status() -> dict:
    root = _env_path("TUTOR_IA_JARVIS_MLX_ROOT", DEFAULT_JARVIS_MLX_ROOT)
    main_text = _read_text(root / "main.py")
    has_vad = "VADDetector" in main_text
    has_stt = "FastTranscriber" in main_text or "whisper" in main_text.lower()
    has_tts = "TTS" in main_text and "tts_to_file" in main_text
    has_mlx = "mlx_lm" in main_text or "mlx" in main_text.lower()
    system_name = platform.system().lower()
    return {
        "name": "Jarvis MLX",
        "root": str(root),
        "available": root.exists(),
        "voice_activity": has_vad,
        "speech_to_text": has_stt,
        "text_to_speech": has_tts,
        "mlx_runtime": has_mlx,
        "compatible_runtime": system_name == "darwin",
        "runtime_note": "MLX esta orientado a macOS/Apple Silicon; TUTOR_IA usa solo la idea de interfaz por voz en Windows.",
    }


@lru_cache(maxsize=1)
def get_programming_profiles() -> list[dict]:
    root = _env_path("TUTOR_IA_OPENJARVIS_ROOT", DEFAULT_OPENJARVIS_ROOT)
    profiles = [_load_code_assistant_profile(root)]
    for name in ("architect", "debugger", "code-reviewer", "security-auditor"):
        profile = _load_template(root, name)
        if profile:
            profiles.append(profile)

    for profile in profiles:
        profile["method"] = PROFILE_METHODS.get(profile["key"], PROFILE_METHODS["orchestrator"])
        profile["tool_label"] = ", ".join(profile.get("tools") or ["think"])
    return profiles


def get_profile(profile_key: str | None) -> dict:
    if profile_key == "unified":
        return {
            "key": "unified",
            "label": PROFILE_LABELS["unified"],
            "description": "Un solo cerebro que combina aprendizaje, razonamiento, programacion, agentes y fuentes privadas.",
            "agent_type": "unified-orchestrator",
            "max_turns": 12,
            "temperature": "",
            "tools": sorted({tool for profile in get_programming_profiles() for tool in profile.get("tools", [])}),
            "system_prompt": "",
            "source": "TUTOR_IA",
            "available": True,
            "method": PROFILE_METHODS["unified"],
        }

    profiles = get_programming_profiles()
    for profile in profiles:
        if profile["key"] == profile_key:
            return profile
    return profiles[0]


def build_profile_context(profile_key: str | None) -> str:
    profile = get_profile(profile_key)
    lines = [
        f"Perfil OpenJarvis activo: {profile['label']}.",
        f"Patron: {profile.get('description') or 'Orquestacion de programacion local-first.'}",
        f"Tipo de agente conceptual: {profile.get('agent_type') or 'orchestrator'}.",
        f"Herramientas conceptuales: {profile.get('tool_label') or 'think'}.",
        "Metodo:",
    ]
    lines.extend(f"- {item}" for item in profile.get("method", []))
    lines.extend(
        [
            "Reglas de integracion en TUTOR_IA:",
            "- Usa este perfil como disciplina de razonamiento, no como afirmacion de que ejecutaste herramientas externas.",
            "- Si el usuario pide modificar codigo real, pide o usa rutas, errores y fragmentos concretos.",
            "- Si no hay codigo o traceback concreto, entrega diagnostico/checklist y no inventes una implementacion completa.",
            "- Entrega respuestas accionables para un asistente de programacion: diagnostico, cambio minimo y validacion.",
        ]
    )
    return "\n".join(lines)


def build_unified_brain_context() -> str:
    summary = get_jarvis_stack_summary()
    profiles = summary.get("profiles", [])
    profile_lines = []
    for profile in profiles:
        method = "; ".join(profile.get("method", [])[:2])
        profile_lines.append(
            f"- {profile.get('label')}: {profile.get('description', '')}. Metodo: {method}"
        )

    tools = ", ".join(summary.get("tools", [])) or "think"
    return "\n".join(
        [
            "Cerebro Unificado TUTOR_IA activo.",
            "No existen modos separados para el usuario: todo se resuelve desde una sola interfaz mental.",
            "Capacidades internas conectadas:",
            "- Tutor tecnico para explicar y ensenar.",
            "- Organizador para estructurar ideas, planes y argumentos.",
            "- Analista creativo para detectar patrones y oportunidades.",
            "- Programador local-first inspirado en OpenJarvis.",
            "- Orquestador Agency para sumar especialistas cuando la pregunta lo amerite.",
            "- Entrada por voz local inspirada en Jarvis MLX cuando este habilitada.",
            "Perfiles OpenJarvis incorporados:",
            *profile_lines,
            f"Herramientas conceptuales disponibles: {tools}.",
            "Reglas del cerebro unificado:",
            "- Decide internamente si la pregunta requiere ensenar, organizar, crear, programar, auditar o coordinar especialistas.",
            "- Prioriza las fuentes privadas y Obsidian cuando existan; usa Agency y OpenJarvis como metodologia interna.",
            "- Si no hay evidencia suficiente, dilo en una frase y da el siguiente paso mas util.",
            "- Si el usuario pide codigo real sin archivo, traceback o fragmento, entrega diagnostico/checklist y solicita el dato minimo necesario.",
            "- No afirmes que ejecutaste herramientas externas si solo estas usando su enfoque conceptual.",
        ]
    )


def get_jarvis_stack_summary() -> dict:
    openjarvis = get_openjarvis_status()
    jarvis_mlx = get_jarvis_mlx_status()
    profiles = get_programming_profiles()
    detected_profiles = sum(1 for profile in profiles if profile.get("available"))
    tools = sorted({tool for profile in profiles for tool in profile.get("tools", [])})
    return {
        "openjarvis": openjarvis,
        "jarvis_mlx": jarvis_mlx,
        "profiles": profiles,
        "detected_profiles": detected_profiles,
        "tools": tools,
    }
