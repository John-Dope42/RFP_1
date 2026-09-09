#!/usr/bin/env python3
"""Build one deduplicated, provenance-rich RAG corpus from all collected data."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent

def fp(text): return hashlib.sha256(' '.join(text.lower().split()).encode()).hexdigest()

def main():
    out=ROOT/'data/rag/rag_chunks.jsonl'; out.parent.mkdir(parents=True,exist_ok=True); seen=set(); rows=[]
    files=[]
    raw=ROOT/'data/raw'
    if raw.exists(): files.extend(sorted(raw.rglob('*.jsonl')))
    processed=ROOT/'data/processed'
    if processed.exists(): files.extend(sorted(processed.glob('*.jsonl')))
    # The final train/val files are intentionally not re-ingested: raw/processed
    # are the canonical source layer and avoid a second copy of synthetic prompts.
    for f in files:
        for line in f.read_text(encoding='utf8',errors='replace').splitlines():
            try:x=json.loads(line)
            except:continue
            text=(x.get('text') or '').strip()
            if not text and isinstance(x.get('messages'),list):
                text='\n\n'.join(m.get('content','') for m in x['messages'] if m.get('role')=='assistant').strip()
            if not text and x.get('abstract'): text=str(x['abstract']).strip()
            if len(text)<250: continue
            h=fp(text)
            if h in seen: continue
            seen.add(h)
            md=dict(x.get('metadata') or {}); md.setdefault('title',x.get('title','')); md.setdefault('url',x.get('url','')); md['source_file']=str(f.relative_to(ROOT))
            rows.append({'id':x.get('id') or h,'text':text,'metadata':md})
    out.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows),encoding='utf8')
    print(f'RAG-Korpus: {len(rows)} eindeutige Chunks -> {out}')
    return 0
if __name__=='__main__': raise SystemExit(main())
