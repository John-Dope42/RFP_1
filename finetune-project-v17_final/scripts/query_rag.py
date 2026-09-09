#!/usr/bin/env python3
"""
RAG-Retrieval: durchsucht den mit ingest_rag.py gebauten Index und gibt die
relevantesten Chunks zurück - als eigenständiges CLI-Tool zum Testen, und als
Funktion retrieve() zur Wiederverwendung (z.B. später beim Chatten mit dem
Modell, um die Treffer vor die Frage ins Prompt zu packen).

Nutzung (CLI):
    python scripts/query_rag.py "Was regelt § 15 AMG?"
    python scripts/query_rag.py "SQF Event Handler" --domain arma3 --top-k 3
"""
from __future__ import annotations
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX_DIR = ROOT / "data" / "rag_index"
COLLECTION_NAME = "finetune_kb"
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

_client = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is not None:
        return _collection
    import chromadb
    from chromadb.utils import embedding_functions
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    _client = chromadb.PersistentClient(path=str(INDEX_DIR))
    _collection = _client.get_collection(COLLECTION_NAME, embedding_function=embed_fn)
    return _collection


def retrieve(query: str, top_k: int = 5, domain: str | None = None) -> list[dict]:
    """Gibt eine Liste von {"text", "metadata", "distance"} zurück, sortiert
    nach Relevanz (kleinere distance = relevanter)."""
    collection = _get_collection()
    where = {"domain": domain} if domain else None
    result = collection.query(query_texts=[query], n_results=top_k, where=where)
    hits = []
    for text, meta, dist in zip(result["documents"][0], result["metadatas"][0], result["distances"][0]):
        hits.append({"text": text, "metadata": meta, "distance": dist})
    return hits


def format_for_prompt(hits: list[dict], max_chars_per_hit: int = 800) -> str:
    """Baut aus den Treffern einen Kontext-Block, der vor die eigentliche
    Nutzerfrage ins Prompt gesetzt werden kann."""
    blocks = []
    for i, hit in enumerate(hits, 1):
        src = hit["metadata"].get("url") or hit["metadata"].get("source_file", "unbekannt")
        text = hit["text"][:max_chars_per_hit]
        blocks.append(f"[Quelle {i}: {src}]\n{text}")
    return "\n\n".join(blocks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--domain", help="Nur diese Domain durchsuchen (z.B. law, arma3)")
    args = ap.parse_args()

    try:
        hits = retrieve(args.query, top_k=args.top_k, domain=args.domain)
    except Exception as e:
        print(f"❌ Kein Index gefunden oder Fehler beim Laden: {e}")
        print("   Erst ingest_rag.py laufen lassen, um den Index zu bauen.")
        return

    if not hits:
        print("Keine Treffer.")
        return

    for i, hit in enumerate(hits, 1):
        print(f"\n--- Treffer {i} (Distanz: {hit['distance']:.3f}) ---")
        print(f"Domain: {hit['metadata'].get('domain', '?')}  |  Quelle: {hit['metadata'].get('url', hit['metadata'].get('source_file', '?'))}")
        print(hit["text"][:400] + ("..." if len(hit["text"]) > 400 else ""))


if __name__ == "__main__":
    main()
