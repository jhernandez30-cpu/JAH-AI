from __future__ import annotations

from project_workspace import build_workspace_brain_context, retrieve_workspace_context
from jarvis_brain import build_profile_context, build_unified_brain_context
from programming_skills import build_programming_skills_context


QUICK_CODE_MAX_CHARS = 6000


def build_quick_code_docs(
    quick_code_context: str | None,
    *,
    source: str = "session:quick-code",
    title: str = "Codigo o requerimiento rapido",
    access_group: str | None = None,
    max_chars: int = QUICK_CODE_MAX_CHARS,
) -> list[dict]:
    quick_code = str(quick_code_context or "").strip()
    if not quick_code:
        return []

    metadata = {
        "source": source,
        "title": title,
        "type": "code",
    }
    if access_group:
        metadata["access_group"] = access_group

    return [
        {
            "text": quick_code[:max_chars],
            "metadata": metadata,
        }
    ]


def retrieve_connected_workspace_docs(
    question: str,
    workspace_path: str | None,
    *,
    max_files: int = 5,
    max_chars_per_file: int = 1800,
) -> list[dict]:
    if not workspace_path:
        return []
    return retrieve_workspace_context(
        question,
        workspace_path,
        max_files=max_files,
        max_chars_per_file=max_chars_per_file,
    )


def build_connected_brain_context(
    question: str,
    *,
    interaction_mode: str = "unified",
    brain_profile: str | None = "unified",
    workspace_path: str | None = "",
    quick_code_context: str | None = "",
) -> dict:
    mode = str(interaction_mode or "unified").strip().lower()
    profile_key = str(brain_profile or "unified").strip() or "unified"
    programming_question = "\n".join(
        part for part in [str(question or ""), str(quick_code_context or "")] if part.strip()
    )

    parts: list[tuple[str, str]] = []
    if mode == "programming" and profile_key != "unified":
        parts.append(("jarvis_profile", build_profile_context(profile_key)))
    else:
        profile_key = "unified"
        parts.append(("unified_brain", build_unified_brain_context()))

    parts.append(("programming_skills", build_programming_skills_context(programming_question)))

    workspace_context = build_workspace_brain_context(workspace_path)
    if workspace_context:
        parts.append(("workspace", workspace_context))

    parts.append(
        (
            "connection_contract",
            "\n".join(
                [
                    "Contrato de conexion del cerebro programador:",
                    "- Trata fuentes privadas, Obsidian, workspace, codigo rapido, Agency, OpenJarvis y Ollama como capas de un mismo razonamiento.",
                    "- Prioridad para tareas de software: codigo pegado y workspace primero; fuentes privadas despues; Agency y OpenJarvis como metodologia.",
                    "- Si una capa no trae evidencia suficiente, dilo con brevedad y usa la siguiente capa disponible.",
                    "- Entrega siempre una salida conectada: diagnostico, cambio recomendado, impacto y validacion.",
                ]
            ),
        )
    )

    context = "\n\n".join(text for _, text in parts if text)
    return {
        "context": context,
        "profile": profile_key,
        "parts": [name for name, text in parts if text],
        "workspace_connected": bool(workspace_context),
        "quick_code_connected": bool(str(quick_code_context or "").strip()),
    }
