#!/usr/bin/env python3
"""Gemeinsame, robuste Utilities für öffentliche Web-Collector."""
from __future__ import annotations
import hashlib, json, os, re, time
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

CONTACT = os.getenv("FT_CONTACT_EMAIL", "project-contact@example.invalid")
UA = f"FineTuneKnowledgeCollector/10.1 (+mailto:{CONTACT})"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9,de;q=0.8,fr;q=0.7,pl;q=0.6", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf;q=0.8,*/*;q=0.5"})


def allowed(url: str, domains: set[str]) -> bool:
    p = urlparse(url); host = p.netloc.lower().split(":")[0]; path = p.path.lower()
    if p.scheme not in {"http", "https"}: return False
    blocked = ("official-sensitive", "official_sensitive", "classified", "restricted", "defence-gateway", "defencegateway", "cac-required", "intradef")
    if any(term in path for term in blocked): return False
    return host in domains


def robots_ok(url: str, cache: dict[str, RobotFileParser | None], timeout: int = 8) -> bool:
    """Robots check with a hard network timeout. Never allow robots.txt to hang a collector."""
    p = urlparse(url); base = f"{p.scheme}://{p.netloc}"
    if base not in cache:
        rp = RobotFileParser()
        robots_url = base + "/robots.txt"
        try:
            rr = SESSION.get(robots_url, timeout=timeout, allow_redirects=True)
            if rr.status_code >= 400:
                cache[base] = None
                return True
            rp.parse(rr.text.splitlines())
            cache[base] = rp
        except requests.RequestException:
            cache[base] = None
            return True
    rp = cache[base]
    return True if rp is None else rp.can_fetch(UA, url)


def fetch(url: str, timeout: tuple[int, int] = (5, 20), retries: int = 1):
    last = None
    for attempt in range(retries + 1):
        try:
            r = SESSION.get(url, timeout=timeout, allow_redirects=True)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise last


def clean_text(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def html_to_text(html: bytes | str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "form"]): tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    main = soup.find("main") or soup.find("article") or soup.body or soup
    return title, clean_text(main.get_text("\n", strip=True))


def pdf_to_text(content: bytes) -> tuple[str, str]:
    try:
        import fitz
        with fitz.open(stream=content, filetype="pdf") as doc:
            parts = [p.get_text("text") for p in doc]
        return "PDF", clean_text("\n".join(parts))
    except Exception:
        return "PDF", ""


def chunk_text(text: str, max_chars: int = 5000, overlap: int = 300):
    if len(text) <= max_chars: return [text]
    out=[]; start=0
    while start < len(text):
        end=min(start+max_chars,len(text))
        if end < len(text):
            cut=max(text.rfind("\n\n",start,end),text.rfind(".",start,end))
            if cut > start + max_chars//2: end=cut+1
        part=text[start:end].strip()
        if len(part)>=300: out.append(part)
        if end>=len(text): break
        start=max(0,end-overlap)
    return out


def stable_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]


# ============================================================
# GEMEINSAMES METADATEN-SCHEMA (v10.3)
# ============================================================
# Jeder Collector soll build_metadata() nutzen statt eigene ad-hoc dicts zu
# bauen, damit Recht/Militär (wo Version/Gültigkeit entscheidend sind) und
# alle anderen Domains dasselbe Schema teilen. Felder, die ein Collector
# nicht kennt, bleiben None - das ist bewusst kein Zwang, ALLE Felder zu
# befüllen, sondern eine gemeinsame Struktur, gegen die RAG-Indexierung und
# QLoRA-Aufbereitung einheitlich filtern/sortieren können.
SCHEMA_FIELDS = [
    "domain", "subdomain", "source_type", "authority", "country", "language",
    "document_type", "title", "author", "publication_date", "updated_date",
    "valid_from", "valid_until", "version", "license", "url",
    "content_hash", "chunk_id", "parent_document_id",
]


def build_metadata(
    *, domain: str, url: str, chunk_id: str, content_hash: str,
    subdomain: str | None = None, source_type: str | None = None,
    authority: str | None = None, country: str | None = None,
    language: str = "de", document_type: str | None = None,
    title: str | None = None, author: str | None = None,
    publication_date: str | None = None, updated_date: str | None = None,
    valid_from: str | None = None, valid_until: str | None = None,
    version: str | None = None, license: str | None = None,
    parent_document_id: str | None = None,
) -> dict:
    """Baut ein Metadaten-dict nach dem gemeinsamen v10.3-Schema."""
    return {
        "domain": domain, "subdomain": subdomain, "source_type": source_type,
        "authority": authority, "country": country, "language": language,
        "document_type": document_type, "title": title, "author": author,
        "publication_date": publication_date, "updated_date": updated_date,
        "valid_from": valid_from, "valid_until": valid_until,
        "version": version, "license": license, "url": url,
        "content_hash": content_hash, "chunk_id": chunk_id,
        "parent_document_id": parent_document_id,
    }


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w",encoding="utf-8") as f:
        for row in rows: f.write(json.dumps(row,ensure_ascii=False)+"\n")
