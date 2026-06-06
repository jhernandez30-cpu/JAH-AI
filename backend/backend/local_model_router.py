from __future__ import annotations

import os
import re
import unicodedata


AUTO_MODEL_OPTION = "Auto (Cerebro Unificado)"

FAST_MODEL_PRIORITY = [
    os.getenv("TUTOR_IA_FAST_MODEL", "").strip(),
    "llama3.2:1b",
    "qwen2.5:1.5b",
    "gemma3:1b",
    "llama3.2:3b",
]

BALANCED_MODEL_PRIORITY = [
    os.getenv("TUTOR_IA_BALANCED_MODEL", "").strip(),
    "llama3.2:1b",
    "llama3.2:3b",
    "llama3.1:8b",
]

CODE_MODEL_PRIORITY = [
    os.getenv("TUTOR_IA_CODE_MODEL", "").strip(),
    "qwen2.5-coder:7b",
    "deepseek-coder:6.7b",
    "codellama:7b",
    "llama3.1:8b",
    "qwen2.5-coder:3b",
    "llama3.2:3b",
    "qwen2.5-coder:1.5b",
    "llama3.2:1b",
]

REASONING_MODEL_PRIORITY = [
    os.getenv("TUTOR_IA_REASONING_MODEL", "").strip(),
    "llama3.1:8b",
    "qwen2.5:7b",
    "llama3.2:3b",
    "llama3.2:1b",
]

RECOMMENDED_PULLS = [
    {
        "model": "qwen2.5-coder:7b",
        "use": "codigo, refactor, bugs, arquitectura y SQL",
        "command": "ollama pull qwen2.5-coder:7b",
    },
    {
        "model": "qwen2.5-coder:1.5b",
        "use": "codigo ligero si tienes poca RAM",
        "command": "ollama pull qwen2.5-coder:1.5b",
    },
    {
        "model": "llama3.1:8b",
        "use": "razonamiento general y respuestas largas",
        "command": "ollama pull llama3.1:8b",
    },
]

CODE_INTENT_RE = re.compile(
    r"\b("
    r"codigo|code|programa|programacion|software|app|api|backend|frontend|fullstack|"
    r"html|css|javascript|typescript|react|python|flask|fastapi|streamlit|sql|"
    r"base de datos|database|schema|tabla|debug|bug|error|traceback|review|"
    r"revisa|refactor|optimiza|test|pytest|arquitectura|programador|programadora|"
    r"modulo|modulos"
    r")\b",
    re.IGNORECASE,
)

SIMPLE_INTENT_RE = re.compile(
    r"\b(resume|explica|define|que es|lista|pasos simples|rapido|breve)\b",
    re.IGNORECASE,
)


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _clean_priority(priority: list[str]) -> list[str]:
    return [model for model in priority if model]


def _first_installed(installed_models: list[str], priority: list[str]) -> str | None:
    installed = set(installed_models or [])
    for model in _clean_priority(priority):
        if model in installed:
            return model
    return None


def infer_model_task(question: str = "", docs: list | None = None, brain_context: str = "") -> str:
    text = _strip_accents(question or "").lower()
    docs = docs or []
    has_code_doc = any((doc.get("metadata", {}).get("type") == "code") for doc in docs if isinstance(doc, dict))
    prompt_size = len(text) + sum(
        min(len(str(doc.get("text", ""))), 1000)
        for doc in docs
        if isinstance(doc, dict)
    )
    if has_code_doc or CODE_INTENT_RE.search(text):
        return "code"
    if SIMPLE_INTENT_RE.search(text) and len(text) < 1200:
        return "fast"
    if prompt_size > 2500 or len(docs) >= 4:
        return "reasoning"
    return "balanced"


def choose_local_model(
    installed_models: list[str],
    preferred_model: str | None = None,
    question: str = "",
    docs: list | None = None,
    brain_context: str = "",
    fallback_model: str = "llama3.2:1b",
) -> str | None:
    installed_models = installed_models or []
    preferred = (preferred_model or "").strip()
    if preferred and preferred != AUTO_MODEL_OPTION and preferred.lower() != "auto":
        if preferred in installed_models:
            return preferred

    task = infer_model_task(question=question, docs=docs, brain_context=brain_context)
    if task == "code":
        selected = _first_installed(installed_models, CODE_MODEL_PRIORITY)
    elif task == "reasoning":
        selected = _first_installed(installed_models, REASONING_MODEL_PRIORITY)
    elif task == "fast":
        selected = _first_installed(installed_models, FAST_MODEL_PRIORITY)
    else:
        selected = _first_installed(installed_models, BALANCED_MODEL_PRIORITY)

    if selected:
        return selected
    if fallback_model in installed_models:
        return fallback_model
    return installed_models[0] if installed_models else None


def sort_models_for_ui(models: list[str]) -> list[str]:
    priority = []
    for group in (CODE_MODEL_PRIORITY, REASONING_MODEL_PRIORITY, FAST_MODEL_PRIORITY):
        priority.extend(_clean_priority(group))
    order = {model: index for index, model in enumerate(dict.fromkeys(priority))}
    return sorted(models or [], key=lambda model: (order.get(model, 999), model))


def get_model_plan(installed_models: list[str]) -> dict:
    installed_models = installed_models or []
    return {
        "auto_label": AUTO_MODEL_OPTION,
        "fast": _first_installed(installed_models, FAST_MODEL_PRIORITY),
        "balanced": _first_installed(installed_models, BALANCED_MODEL_PRIORITY),
        "code": _first_installed(installed_models, CODE_MODEL_PRIORITY),
        "reasoning": _first_installed(installed_models, REASONING_MODEL_PRIORITY),
        "recommended_pulls": [
            item for item in RECOMMENDED_PULLS if item["model"] not in set(installed_models)
        ],
    }
