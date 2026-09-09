#!/usr/bin/env python3
"""Sammelt öffentliche Arma-3-Dokumentation für Mission-, Map- und Modbau.
Konfiguriert über config/sources.yaml; keine hartcodierte Wissensliste nötig.
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


def collect_group(entries, output: Path, delay: float, page_cap: int):
    rows, seen, robots = [], set(), {}
    total_fetched = 0
    for src in entries:
        seeds = src.get("urls", [])
        domains = {urlparse(u).netloc.lower().split(":")[0] for u in seeds}
        q = deque(seeds)
        local_seen = 0
        while q and local_seen < min(page_cap, int(src.get("max_pages", page_cap))):
            url = q.popleft().split("#", 1)[0]
            if url in seen or not allowed(url, domains) or not robots_ok(url, robots):
                continue
            seen.add(url); local_seen += 1
            print(f"  🌐 [{src['id']}] Seite {local_seen}: {url}", flush=True)
            try:
                r = fetch(url)
            except Exception as e:
                print(f"  ! {url}: {e}"); continue
            ctype = r.headers.get("content-type", "").lower()
            if "pdf" in ctype or url.lower().endswith(".pdf"):
                title, text = pdf_to_text(r.content)
            elif "html" in ctype or "text" in ctype:
                title, text = html_to_text(r.content)
                soup_links = []
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(r.content, "html.parser")
                    soup_links = [urljoin(url, a.get("href")) for a in soup.find_all("a", href=True)]
                except Exception:
                    pass
                for link in soup_links:
                    if link and allowed(link, domains) and ("#" not in link or link.split("#")[0] not in seen):
                        if any(x in link.lower() for x in (".pdf", "/wiki/", "/doc", "/manual", "/category/", "/reference", "/guide")):
                            q.append(link)
            else:
                continue
            if len(text) < 500:
                print(f"     ⚠️ Zu wenig Text ({len(text)} Zeichen)", flush=True)
                continue
            total_fetched += 1
            for i, chunk in enumerate(chunk_text(text)):
                rows.append({
                    "id": stable_id(src["id"], url, str(i), chunk[:200]),
                    "text": chunk,
                    "title": title,
                    "url": r.url,
                    "metadata": {
                        "domain": src["domain"], "source": src["id"], "authority": src["authority"],
                        "language": src.get("language", "en"), "content_type": "pdf" if "pdf" in ctype else "html",
                    },
                })
            time.sleep(delay)
    # Dedup by id/text fingerprint
    uniq = {}
    for x in rows:
        uniq.setdefault(stable_id(x["text"]), x)
    write_jsonl(output, uniq.values())
    print(f"Gespeichert: {len(uniq)} Chunks -> {output}", flush=True)
    if not uniq:
        print("❌ Arma-Collector hat 0 verwertbare Chunks geliefert.", flush=True)
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config" / "sources.yaml"))
    ap.add_argument("--delay", type=float, default=0.8)
    ap.add_argument("--max-pages", type=int, default=250)
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    collect_group(cfg.get("arma3", []), ROOT / "data/raw/arma3/arma3_raw.jsonl", args.delay, args.max_pages)

if __name__ == "__main__": main()
