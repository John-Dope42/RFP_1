#!/usr/bin/env python3
"""
RAG-Ingestion: liest alle Collector-Rohdaten (data/raw/**/*.jsonl) und baut
daraus einen lokalen, persistenten Vektor-Index (ChromaDB) für Retrieval.

Bewusste Designentscheidungen:
- ChromaDB statt FAISS: reines Python, kein separater Server, persistiert
  automatisch auf Disk, läuft out-of-the-box auf der RTX 3060/CPU.
- Multilingual-Embedding-Modell (paraphrase-multilingual-MiniLM-L12-v2):
  deckt Deutsch/Englisch/Französisch/Polnisch gleichzeitig ab, wie es das
  Projekt braucht (deutsche Gesetze, englische US-Army-Doktrin, etc.).
- Idempotent: IDs werden aus content_hash + url gebildet, ein erneuter Lauf
  überschreibt nur veränderte Chunks statt alles zu duplizieren (Upsert).
- Verarbeitet BEIDE Formate, die im Projekt vorkommen:
    a) Collector-Rohformat: {"id","text","title","url","metadata": {...}}
    b) Trainings-Format:    {"messages":[...], "metadata": {...}}
       (hier wird der Assistant-Turn als Text für den Index genutzt)

Nutzung:
    python scripts/ingest_rag.py                 # alles unter data/raw/ einlesen
    python scripts/ingest_rag.py --domain arma3   # nur eine Domain neu einlesen
    python scripts/ingest_rag.py --rebuild        # Index komplett neu aufbauen
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
DEDUPED_CORPUS = ROOT / "data" / "rag" / "rag_chunks.jsonl"
INDEX_DIR = ROOT / "data" / "rag_index"
COLLECTION_NAME = "finetune_kb"
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
BATCH_SIZE = 128


def iter_jsonl_files(domain: str | None):
    """Nutzt bevorzugt den deduplizierten Korpus aus build_rag_corpus.py
    (empfohlen: erst `python scripts/build_rag_corpus.py` laufen lassen).
    Ohne --domain-Filter und falls der deduplizierte Korpus existiert, wird
    NUR dieser genutzt (sonst gäbe es Duplikate zwischen data/rag/ und
    data/raw/). Mit --domain-Filter wird gezielt aus data/raw/<domain>/
    gelesen, da der deduplizierte Korpus keine Domain-Unterordner hat."""
    if domain is None and DEDUPED_CORPUS.exists():
        print(f"ℹ️  Nutze deduplizierten Korpus: {DEDUPED_CORPUS.relative_to(ROOT)}")
        yield DEDUPED_CORPUS
        return
    if domain is None:
        print("ℹ️  Kein deduplizierter Korpus gefunden - lese data/raw/ direkt.")
        print("   Tipp: 'python scripts/build_rag_corpus.py' davor laufen lassen, dedupliziert automatisch.")
    if not DATA_RAW.exists():
        print(f"⚠️  {DATA_RAW} existiert nicht - noch keine Collector-Daten gesammelt?")
        return
    pattern = f"{domain}/**/*.jsonl" if domain else "**/*.jsonl"
    yield from sorted(DATA_RAW.glob(pattern))


def extract_records(path: Path):
    """Normalisiert beide im Projekt vorkommenden JSONL-Formate auf
    (text, metadata, source_url) - übersprungen wird nur, was wirklich leer ist."""
    domain_guess = path.parent.name
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                print(f"  ⚠️  {path.name}:{line_no} kein gültiges JSON, übersprungen")
                continue

            meta = row.get("metadata", {}) or {}

            if "text" in row and row["text"]:
                # Collector-Rohformat
                text = row["text"]
                url = row.get("url", meta.get("url", ""))
            elif "messages" in row:
                # Trainings-Format: letzten assistant-Turn als Indextext nehmen
                assistant_msgs = [m["content"] for m in row["messages"] if m.get("role") == "assistant"]
                if not assistant_msgs:
                    continue
                text = assistant_msgs[-1]
                url = meta.get("url", meta.get("source", ""))
            else:
                continue

            if len(text.strip()) < 50:
                continue

            meta = dict(meta)
            meta.setdefault("domain", meta.get("domain") or domain_guess)
            meta["source_file"] = path.name
            if url and not meta.get("url"):
                meta["url"] = url
            # Chroma erlaubt keine None-Werte in Metadaten -> rausfiltern
            meta = {k: v for k, v in meta.items() if v is not None and isinstance(v, (str, int, float, bool))}

            yield text, meta, url


def make_id(text: str, url: str) -> str:
    return hashlib.sha256(f"{url}\x1f{text[:500]}".encode("utf-8")).hexdigest()[:24]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", help="Nur diese Domain neu einlesen (z.B. arma3, law, military)")
    ap.add_argument("--rebuild", action="store_true", help="Index komplett verwerfen und neu aufbauen")
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = ap.parse_args()

    try:
        import chromadb
        from chromadb.utils import embedding_functions
    except ImportError:
        print("❌ chromadb fehlt. Installieren mit: pip install chromadb sentence-transformers --break-system-packages")
        sys.exit(1)

    print(f"🔎 Lade Embedding-Modell '{EMBEDDING_MODEL}' (einmalig, danach gecacht)...")
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)

    client = chromadb.PersistentClient(path=str(INDEX_DIR))
    if args.rebuild:
        try:
            client.delete_collection(COLLECTION_NAME)
            print("🗑️  Bestehender Index verworfen (--rebuild).")
        except Exception:
            pass
    collection = client.get_or_create_collection(COLLECTION_NAME, embedding_function=embed_fn)

    files = list(iter_jsonl_files(args.domain))
    if not files:
        print("⚠️  Keine passenden JSONL-Dateien gefunden. Erst Collectors laufen lassen?")
        return

    total_seen, total_added = 0, 0
    batch_ids, batch_texts, batch_metas = [], [], []

    def flush():
        nonlocal batch_ids, batch_texts, batch_metas, total_added
        if not batch_ids:
            return
        collection.upsert(ids=batch_ids, documents=batch_texts, metadatas=batch_metas)
        total_added += len(batch_ids)
        batch_ids, batch_texts, batch_metas = [], [], []

    for path in files:
        print(f"📄 {path.relative_to(ROOT)}")
        file_count = 0
        for text, meta, url in extract_records(path):
            total_seen += 1
            file_count += 1
            batch_ids.append(make_id(text, url))
            batch_texts.append(text)
            batch_metas.append(meta)
            if len(batch_ids) >= args.batch_size:
                flush()
        print(f"   → {file_count} Einträge verarbeitet")
    flush()

    print(f"\n✅ Fertig. {total_added} Chunks im Index (von {total_seen} gesehenen Einträgen).")
    print(f"📁 Index liegt unter: {INDEX_DIR}")
    print(f"📊 Collection-Gesamtgröße jetzt: {collection.count()} Chunks")


if __name__ == "__main__":
    main()
