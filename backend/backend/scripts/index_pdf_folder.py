from __future__ import annotations

import argparse
import hashlib
import math
import os
import re
import sys
from pathlib import Path

import chromadb
import fitz
from chromadb.config import Settings
from langchain_text_splitters import RecursiveCharacterTextSplitter


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
DEFAULT_PDF_DIR = PROJECT_ROOT / "conocimiento" / "_pdfs"
DEFAULT_PERSIST_DIR = PROJECT_ROOT / "vectores" / "brain_db"
COLLECTION_NAME = os.getenv("TUTOR_IA_COLLECTION", "conocimiento_fast")
EMBED_DIM = int(os.getenv("TUTOR_IA_EMBED_DIM", "384"))
CHUNK_SIZE = int(os.getenv("TUTOR_IA_CHUNK_SIZE", "1200"))
CHUNK_OVERLAP = int(os.getenv("TUTOR_IA_CHUNK_OVERLAP", "180"))
CHROMA_UPSERT_BATCH_SIZE = int(os.getenv("TUTOR_IA_CHROMA_UPSERT_BATCH_SIZE", "256"))
CHROMA_EXISTING_CHECK_BATCH_SIZE = int(os.getenv("TUTOR_IA_CHROMA_EXISTING_CHECK_BATCH_SIZE", "500"))
TOKEN_RE = re.compile(r"[a-záéíóúüñ0-9_]+", re.IGNORECASE)


def clean_metadata(metadata: dict) -> dict:
    clean = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            clean[key] = value
        else:
            clean[key] = str(value)
    return clean


def make_doc_id(metadata: dict, text: str) -> str:
    source = metadata.get("source", "unknown")
    location_parts = [
        metadata.get("type", ""),
        metadata.get("page", ""),
        metadata.get("sheet", ""),
        metadata.get("slide", ""),
        metadata.get("start", ""),
        metadata.get("end", ""),
    ]
    location = "|".join(str(part) for part in location_parts)
    digest = hashlib.sha256(f"{source}|{location}|{text}".encode("utf-8")).hexdigest()
    return digest[:32]


def embed_text(text: str) -> list[float]:
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


def extract_pdf_pages(path: Path) -> list[dict]:
    chunks = []
    with fitz.open(path) as doc:
        for index, page in enumerate(doc, start=1):
            text = page.get_text()
            if text.strip():
                chunks.append(
                    {
                        "text": text,
                        "metadata": {
                            "source": path.name,
                            "path": str(path.relative_to(PROJECT_ROOT)),
                            "type": "pdf",
                            "page": index,
                            "title": path.stem,
                        },
                    }
                )
    return chunks


def prepare_records(raw_chunks: list[dict], access_group: str) -> tuple[list[str], list[dict], list[str]]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    docs: list[str] = []
    metas: list[dict] = []
    ids: list[str] = []
    seen_ids = set()

    for raw in raw_chunks:
        text = (raw.get("text") or "").strip()
        if not text:
            continue
        base_metadata = clean_metadata(raw.get("metadata", {}))
        base_metadata["access_group"] = access_group
        pieces = splitter.split_text(text) if len(text) > 1000 else [text]

        for piece in pieces:
            piece = piece.strip()
            if not piece:
                continue
            doc_id = make_doc_id(base_metadata, piece)
            if doc_id in seen_ids:
                continue
            seen_ids.add(doc_id)
            docs.append(piece)
            metas.append(base_metadata.copy())
            ids.append(doc_id)

    return docs, metas, ids


def filter_existing(collection, docs: list[str], metas: list[dict], ids: list[str]) -> tuple[list[str], list[dict], list[str], int]:
    existing_ids = set()
    for start in range(0, len(ids), CHROMA_EXISTING_CHECK_BATCH_SIZE):
        batch_ids = ids[start : start + CHROMA_EXISTING_CHECK_BATCH_SIZE]
        try:
            existing = collection.get(ids=batch_ids)
        except Exception:
            continue
        existing_ids.update(existing.get("ids", []))

    if not existing_ids:
        return docs, metas, ids, 0

    new_docs: list[str] = []
    new_metas: list[dict] = []
    new_ids: list[str] = []
    for doc, meta, doc_id in zip(docs, metas, ids):
        if doc_id in existing_ids:
            continue
        new_docs.append(doc)
        new_metas.append(meta)
        new_ids.append(doc_id)
    return new_docs, new_metas, new_ids, len(existing_ids)


def upsert_records(collection, docs: list[str], metas: list[dict], ids: list[str]) -> int:
    total = len(docs)
    for start in range(0, total, CHROMA_UPSERT_BATCH_SIZE):
        end = min(start + CHROMA_UPSERT_BATCH_SIZE, total)
        batch_docs = docs[start:end]
        collection.upsert(
            documents=batch_docs,
            metadatas=metas[start:end],
            ids=ids[start:end],
            embeddings=[embed_text(doc) for doc in batch_docs],
        )
        print(f"  indexados {end}/{total} fragmentos", flush=True)
    return total


def index_pdf_folder(pdf_dir: Path, persist_dir: Path, access_group: str, limit: int | None = None) -> int:
    pdfs = sorted(pdf_dir.rglob("*.pdf"))
    if limit is not None:
        pdfs = pdfs[:limit]
    if not pdfs:
        print(f"No se encontraron PDF en {pdf_dir}")
        return 0

    client = chromadb.PersistentClient(path=str(persist_dir), settings=Settings(anonymized_telemetry=False))
    collection = client.get_or_create_collection(COLLECTION_NAME)

    total_indexed = 0
    total_skipped = 0
    total_prepared = 0
    failures: list[tuple[str, str]] = []

    print(f"PDF dir: {pdf_dir}")
    print(f"Chroma: {persist_dir}")
    print(f"Coleccion: {COLLECTION_NAME}")
    print(f"Grupo: {access_group}")
    print(f"PDF detectados: {len(pdfs)}")

    for number, path in enumerate(pdfs, start=1):
        print(f"[{number}/{len(pdfs)}] {path.name}", flush=True)
        try:
            raw_chunks = extract_pdf_pages(path)
            docs, metas, ids = prepare_records(raw_chunks, access_group)
            prepared_count = len(ids)
            docs, metas, ids, skipped_count = filter_existing(collection, docs, metas, ids)
            indexed_count = upsert_records(collection, docs, metas, ids)
            total_prepared += prepared_count
            total_skipped += skipped_count
            total_indexed += indexed_count
            print(
                f"  paginas={len(raw_chunks)} preparados={prepared_count} nuevos={indexed_count} existentes={skipped_count}",
                flush=True,
            )
        except Exception as exc:
            failures.append((path.name, str(exc)))
            print(f"  ERROR: {exc}", flush=True)

    print("\nResumen")
    print(f"PDF procesados: {len(pdfs)}")
    print(f"Fragmentos preparados: {total_prepared}")
    print(f"Fragmentos nuevos indexados: {total_indexed}")
    print(f"Fragmentos ya existentes: {total_skipped}")
    print(f"Fallos: {len(failures)}")
    for name, error in failures:
        print(f"- {name}: {error}")

    return 1 if failures else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Indexa PDF de conocimiento en la base vectorial de TUTOR_IA.")
    parser.add_argument("--pdf-dir", type=Path, default=DEFAULT_PDF_DIR)
    parser.add_argument("--persist-dir", type=Path, default=Path(os.getenv("TUTOR_IA_PERSIST_DIR", str(DEFAULT_PERSIST_DIR))))
    parser.add_argument("--access-group", default=os.getenv("TUTOR_IA_INDEX_ACCESS_GROUP", "admin"))
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pdf_dir = args.pdf_dir.expanduser().resolve()
    persist_dir = args.persist_dir.expanduser().resolve()
    if not pdf_dir.exists():
        print(f"No existe la carpeta de PDF: {pdf_dir}", file=sys.stderr)
        return 2
    persist_dir.mkdir(parents=True, exist_ok=True)
    return index_pdf_folder(pdf_dir, persist_dir, args.access_group.strip() or "admin", args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
