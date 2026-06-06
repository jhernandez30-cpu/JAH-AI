from __future__ import annotations

import re
from typing import Any


def trim_context(text: str, max_chars: int = 1800) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def notebooklm_result_to_doc(
    result: Any,
    *,
    notebook_id: str = "",
    question: str = "",
    max_chars: int = 1800,
) -> dict | None:
    """Convert a NotebookLM answer into the existing RAG doc shape."""
    answer = ""
    references = []
    if isinstance(result, dict):
        answer = str(result.get("answer") or "").strip()
        references = result.get("references") or []
    else:
        answer = str(getattr(result, "answer", "") or "").strip()
        references = getattr(result, "references", []) or []

    if not answer:
        return None

    reference_text = ""
    if references:
        titles = []
        for ref in references[:4]:
            if isinstance(ref, dict):
                title = ref.get("source_title") or ref.get("source_id")
            else:
                title = getattr(ref, "source_title", None) or getattr(ref, "source_id", None)
            if title and title not in titles:
                titles.append(str(title))
        if titles:
            reference_text = "Referencias NotebookLM: " + ", ".join(titles)

    text = "\n".join(
        part
        for part in [
            f"Pregunta consultada en NotebookLM: {question}" if question else "",
            f"Respuesta NotebookLM: {answer}",
            reference_text,
        ]
        if part
    )
    return {
        "text": trim_context(text, max_chars=max_chars),
        "metadata": {
            "source": f"notebooklm:{notebook_id or 'active'}",
            "title": "Cerebro NotebookLM",
            "type": "notebooklm",
            "access_group": "admin",
        },
    }


def notebooklm_status_message(result: Any) -> str:
    if isinstance(result, dict):
        return str(result.get("message") or "")
    return str(getattr(result, "message", "") or "")

