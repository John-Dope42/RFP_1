#!/usr/bin/env python3
"""Sammelt öffentliche Primär-/Sekundärquellen zu Landstreitkräften.
Keine operative Ziel-/Personendaten; Fokus auf öffentlich zugängliche Doktrin,
Terminologie, Geschichte, Organisation und allgemeine militärische Konzepte.
"""
from __future__ import annotations
import argparse, sys, time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collector_utils import allowed, robots_ok, fetch, html_to_text, pdf_to_text, chunk_text, stable_id, write_jsonl
ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--config", default=str(ROOT/"config/sources.yaml")); ap.add_argument("--delay", type=float, default=1.0); ap.add_argument("--max-pages", type=int, default=300)
    args = ap.parse_args(); cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    rows, seen, robots = [], set(), {}
    for src in cfg.get("military", []):
        domains = {urlparse(u).netloc.lower().split(":")[0] for u in src["urls"]}; q=deque(src["urls"]); n=0
        while q and n < min(args.max_pages, int(src.get("max_pages", args.max_pages))):
            url=q.popleft().split("#",1)[0]
            if url in seen or not allowed(url, domains) or not robots_ok(url, robots): continue
            seen.add(url); n+=1
            print(f"  🌐 [{src['id']}] Seite {n}: {url}", flush=True)
            try: r=fetch(url)
            except Exception as e: print(f"  ! {url}: {e}"); continue
            ct=r.headers.get("content-type","").lower()
            if "pdf" in ct or url.lower().endswith(".pdf"):
                title,text=pdf_to_text(r.content); links=[]
            elif "html" in ct or "text" in ct:
                title,text=html_to_text(r.content)
                try:
                    from bs4 import BeautifulSoup
                    soup=BeautifulSoup(r.content,"html.parser")
                    links=[urljoin(url,a["href"]) for a in soup.find_all("a",href=True)]
                except Exception: links=[]
                for link in links:
                    if allowed(link,domains) and any(x in link.lower() for x in (".pdf","/publication","/publications","/doctrine","/research","/manual","/document")):
                        q.append(link)
            else: continue
            if len(text)<500:
                print(f"     ⚠️ Zu wenig Text ({len(text)} Zeichen)", flush=True)
                continue
            for i,chunk in enumerate(chunk_text(text)):
                rows.append({"id":stable_id(src["id"],r.url,str(i),chunk[:200]),"text":chunk,"title":title,"url":r.url,"metadata":{"domain":src["domain"],"source":src["id"],"authority":src["authority"],"language":src.get("language","en")}})
            time.sleep(args.delay)
    uniq={stable_id(x["text"]):x for x in rows}
    out=ROOT/"data/raw/military/military_raw.jsonl"; write_jsonl(out,uniq.values()); print(f"Gespeichert: {len(uniq)} Chunks -> {out}", flush=True)
    return bool(uniq)

if __name__=="__main__": raise SystemExit(0 if main() else 2)
