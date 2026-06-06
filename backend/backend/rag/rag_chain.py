from __future__ import annotations

from typing import Any

try:
    from .. import web_bridge
    from .retriever import collection_fragment_count, retrieve_relevant_chunks
except ImportError:  # pragma: no cover - allows running from backend/ directly
    import web_bridge  # type: ignore
    from rag.retriever import collection_fragment_count, retrieve_relevant_chunks  # type: ignore


NO_DOCUMENTS_MESSAGE = "El cerebro RAG todavia no tiene documentos cargados o indexados."
NO_RESULTS_MESSAGE = "No encontre informacion suficiente en los documentos cargados para responder con precision."


def query_rag(message: str, top_k: int | None = None) -> dict[str, Any]:
    clean_message = str(message or "").strip()
    if not clean_message:
        return {
            "ok": False,
            "status": "empty_message",
            "answer": "Escribe una pregunta para consultar el cerebro RAG.",
            "sources": [],
        }

    fragment_count = collection_fragment_count()
    if fragment_count <= 0:
        return {
            "ok": True,
            "status": "no_documents",
            "answer": NO_DOCUMENTS_MESSAGE,
            "sources": [],
            "fragments": 0,
        }

    chunks = retrieve_relevant_chunks(clean_message, top_k=top_k or 4, user_groups=["admin", "public"])
    if not chunks:
        return {
            "ok": True,
            "status": "no_results",
            "answer": NO_RESULTS_MESSAGE,
            "sources": [],
            "fragments": fragment_count,
        }

    docs = [
        {
            "text": chunk["text"],
            "metadata": chunk.get("metadata", {}),
        }
        for chunk in chunks
    ]
    answer = web_bridge.generate_answer(
        clean_message,
        docs,
        memory=None,
        interaction_mode="unified",
        model_name=None,
        show_sources=False,
        assistant_profile="abraham-programming-assistant",
        fast_response=True,
    )

    return {
        "ok": True,
        "status": "answered",
        "answer": answer,
        "sources": [
            {
                "file": chunk["file"],
                "chunk": chunk["chunk"],
                "score": chunk["score"],
            }
            for chunk in chunks
        ],
        "fragments": fragment_count,
    }

