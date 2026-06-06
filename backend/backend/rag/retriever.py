from __future__ import annotations

import math
from pathlib import Path
from typing import Any

try:
    from .. import web_bridge
except ImportError:  # pragma: no cover - allows running from backend/ directly
    import web_bridge  # type: ignore


def _source_file(metadata: dict[str, Any]) -> str:
    raw_source = str(metadata.get("source") or metadata.get("title") or "documento")
    if raw_source.startswith("upload:"):
        return raw_source.replace("upload:", "", 1) or "archivo-subido"
    return Path(raw_source.replace("\\", "/")).name or raw_source


def _score_from_distance(distance: Any) -> float:
    try:
        value = float(distance)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(value):
        return 0.0
    return round(1 / (1 + max(value, 0.0)), 4)


def _where_filter(user_groups: list[str]) -> dict[str, Any] | None:
    if "admin" in user_groups:
        return None
    if len(user_groups) == 1:
        return {"access_group": user_groups[0]}
    return {"$or": [{"access_group": group} for group in user_groups]}


def retrieve_relevant_chunks(
    message: str,
    top_k: int | None = None,
    user_groups: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve RAG chunks from the existing Chroma collection with public source data."""
    clean_message = str(message or "").strip()
    if not clean_message:
        return []

    collection = web_bridge.get_collection()
    total_docs = collection.count()
    if total_docs <= 0:
        return []

    groups = web_bridge.normalize_groups(user_groups or ["admin", "public"])
    limit = max(1, min(int(top_k or web_bridge.RESPONSE_TOP_K or 4), 12))
    n_results = min(max(limit * 3, limit), total_docs)
    query_embedding = web_bridge.embed_text(clean_message)

    try:
        raw_result = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=_where_filter(groups),
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        raw_result = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

    documents = (raw_result.get("documents") or [[]])[0] or []
    metadatas = (raw_result.get("metadatas") or [[]])[0] or []
    distances = (raw_result.get("distances") or [[]])[0] or []
    chunks: list[dict[str, Any]] = []

    for index, document in enumerate(documents):
        metadata = metadatas[index] if index < len(metadatas) and isinstance(metadatas[index], dict) else {}
        access_group = metadata.get("access_group", "public")
        if access_group not in groups and "admin" not in groups:
            continue

        distance = distances[index] if index < len(distances) else None
        chunk_text = str(document or "").strip()
        if not chunk_text:
            continue

        chunks.append(
            {
                "text": chunk_text,
                "metadata": metadata,
                "file": _source_file(metadata),
                "chunk": web_bridge.trim_prompt_text(chunk_text, 420),
                "score": _score_from_distance(distance),
            }
        )

    return chunks[:limit]


def collection_fragment_count() -> int:
    try:
        return int(web_bridge.get_collection().count())
    except Exception:
        return 0

