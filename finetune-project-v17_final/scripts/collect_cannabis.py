#!/usr/bin/env python3
"""
Cannabis-Daten Sammler - Kostenlose, evidenzbasierte Quellen
Quellen: PubMed (Open Access), arXiv, Europäische Beobachtungsstelle, Offene Datenbanken
"""

import json
import re
import requests
import time
import sys
from pathlib import Path
from typing import List, Dict
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

# Windows: cp1252 statt UTF-8 bei umgeleiteter/abgefangener Ausgabe -> Emoji-
# Prints crashen sonst mit UnicodeEncodeError (siehe CHANGELOG_FIXES.md #17).
if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


# ============================================================
# KOSTENLOSE, EVIDENZBASIERTE QUELLEN FÜR CANNABIS
# ============================================================
SOURCES = {
    "pubmed_cannabis": {
        "base_url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/",
        "description": "PubMed/MEDLINE - Cannabis-Forschung (Open Access Filter)",
        "queries": [
            "cannabis terpenes biosynthesis",
            "cannabis genetics breeding",
            "cannabis cultivation indoor",
            "cannabis cannabinoid profile",
            "cannabis trichome development",
            "cannabis curing drying terpene preservation",
            "cannabis medical Germany",
            "cannabis legalization Germany CanG",
            "cannabis sommelier sensory evaluation",
            "cannabis landrace genetics",
        ]
    },
    "european_monitoring": {
        "base_url": "https://www.euda.europa.eu/",
        "description": "Europäische Beobachtungsstelle für Drogen (EMCDDA) - Berichte, Daten",
        "urls": [
            "https://www.euda.europa.eu/topics/cannabis_en",
            "https://www.euda.europa.eu/publications/rapid-communications_en",
        ]
    },
    "german_bfarm": {
        "base_url": "https://www.bfarm.de/",
        "description": "BfArM - Cannabis als Medizin, Anbauvereinigungen",
        "urls": [
            "https://www.bfarm.de/DE/Bundesopiumstelle/Medizinisches-Cannabis/_node.html",
        ]
    },
    "seedfinder": {
        "base_url": "https://en.seedfinder.eu/",
        "description": "SeedFinder - Sorten-Datenbank (teilweise frei zugänglich)",
        "note": "API nicht öffentlich, aber Web-Scraping möglich für Sorten-Profile"
    },
    "leafly_open": {
        "base_url": "https://www.leafly.com/",
        "description": "Leafly - Terpen-Profile, Effekte (teilweise frei)",
        "note": "Keine offizielle API, aber strukturierte Daten"
    }
}


def fetch_pubmed_abstracts(query: str, max_results: int = 50) -> List[Dict]:
    """Holt Abstracts von PubMed für eine Query (Open Access bevorzugt)."""
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    
    # 1. Search
    # BUGFIX: "open access[filter]"/"pmc[filter]" sind KEINE gültigen PubMed-Feld-Tags.
    # Ein ungültiges Tag liefert bei PubMed nicht etwa einen Fehler, sondern lautlos
    # 0 Treffer (kein Crash, keine Warnung) - das fiel erst auf, als pubmed_raw.jsonl
    # nach einem kompletten Lauf leer war. Korrektes Tag laut PubMed User Guide:
    # "free full text[sb]" (https://pubmed.ncbi.nlm.nih.gov/help/).
    search_url = f"{base}esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": f"{query} AND free full text[sb]",
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance"
    }
    
    try:
        resp = requests.get(search_url, params=params, timeout=30)
        resp.raise_for_status()
        result_json = resp.json()
        ids = result_json.get("esearchresult", {}).get("idlist", [])
        if not ids:
            count = result_json.get("esearchresult", {}).get("count", "?")
            print(f"     ⚠️  0 Treffer für '{query}' (PubMed meldet count={count}) - Query evtl. zu eng, kein Bug-Symptom mehr.")
    except Exception as e:
        print(f"❌ PubMed Search Fehler: {e}")
        return []
    
    if not ids:
        return []
    
    # 2. Fetch Details
    fetch_url = f"{base}efetch.fcgi"
    params = {
        "db": "pubmed",
        "id": ",".join(ids),
        "retmode": "xml",
        "rettype": "abstract"
    }
    
    try:
        resp = requests.get(fetch_url, params=params, timeout=60)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as e:
        print(f"❌ PubMed Fetch Fehler: {e}")
        return []
    
    results = []
    for article in root.findall(".//PubmedArticle"):
        try:
            pmid = article.find(".//PMID").text
            title = article.find(".//ArticleTitle").text or ""
            
            # Abstract
            abstract_parts = article.findall(".//AbstractText")
            abstract = " ".join([p.text for p in abstract_parts if p.text])
            
            # Journal
            journal = article.find(".//Journal/Title")
            journal_name = journal.text if journal is not None else ""
            
            # PubDate
            pubdate = article.find(".//PubDate")
            year = pubdate.find("Year").text if pubdate is not None and pubdate.find("Year") is not None else ""
            
            # DOI
            doi_elem = article.find(".//ArticleId[@IdType='doi']")
            doi = doi_elem.text if doi_elem is not None else ""
            
            # Keywords
            keywords = [kw.text for kw in article.findall(".//Keyword") if kw.text]
            
            if abstract and len(abstract) > 200:
                results.append({
                    "pmid": pmid,
                    "title": title,
                    "abstract": abstract,
                    "journal": journal_name,
                    "year": year,
                    "doi": doi,
                    "keywords": keywords,
                    "source": "pubmed",
                    "query": query
                })
        except Exception as e:
            continue
    
    return results


def fetch_page_text(url: str, min_paragraph_len: int = 150) -> List[str]:
    """Lädt eine Webseite und extrahiert Absätze als Textbausteine.

    Generische Hilfsfunktion für Quellen ohne API (EMCDDA, BfArM) - ersetzt das
    frühere Vorgehen, bei dem gar kein echter Seiteninhalt geladen wurde,
    sondern nur ein fest einprogrammierter Platzhaltersatz pro Report als
    Trainingsziel diente (siehe fetch_emcdda_reports() vorher).
    """
    try:
        # BUGFIX: EMCDDA/BfArM sind (anders als Wikipedia) keine APIs mit eigener
        # Bot-Policy, sondern normale Behörden-Webseiten hinter einer simplen WAF,
        # die ehrlich-deklarierte Bot-UAs wie "compatible; research-data-collector"
        # pauschal blockt. Ein vollständiger, aktueller Browser-UA + passende
        # Accept-Header kommen an vielen dieser einfachen Filter vorbei - Garantie
        # gibt es aber keine: falls die Seite Cloudflare/Akamai mit JS-Challenge
        # nutzt, hilft nur noch ein echter Browser (z.B. via playwright), kein
        # Header-Fix mehr.
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        }
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"     ❌ Fehler beim Laden von {url}: {e}")
        return []

    soup = BeautifulSoup(resp.content, "html.parser")
    content = soup.find("main") or soup.find("article") or soup.find("div", {"id": "content"}) or soup.body
    if not content:
        return []

    paragraphs = []
    for elem in content.find_all(["p", "li"]):
        text = elem.get_text(strip=True)
        if len(text) >= min_paragraph_len:
            paragraphs.append(text)
    return paragraphs


def fetch_emcdda_reports() -> List[Dict]:
    """Lädt EMCDDA-Berichte inkl. echtem Seiteninhalt (nicht nur Titel/URL)."""
    reports_meta = [
        {
            "title": "Cannabis: Topic Overview",
            "url": "https://www.euda.europa.eu/topics/cannabis_en",
        },
        {
            "title": "Medical use of cannabis",
            "url": "https://www.euda.europa.eu/publications/rapid-communications/medical-use-cannabis_en",
        },
        {
            "title": "Cannabis legislation in Europe",
            "url": "https://www.euda.europa.eu/topics/cannabis-legislation_en",
        },
    ]
    results = []
    for report in reports_meta:
        paragraphs = fetch_page_text(report["url"])
        if not paragraphs:
            print(f"     ⚠️  Keine Inhalte extrahiert für '{report['title']}'")
            continue
        results.append({**report, "paragraphs": paragraphs, "source": "emcdda"})
        time.sleep(0.3)
    return results


def fetch_bfarm_reports() -> List[Dict]:
    """Lädt BfArM-Seiten zu Cannabis (Anbauvereinigungen, medizinischer Gebrauch).

    BUGFIX: Diese Quelle war in SOURCES["german_bfarm"] definiert, wurde aber
    in main() nie tatsächlich abgerufen - toter Code, 0 Beitrag zum Datensatz.
    """
    urls_meta = [
        {
            "title": "BfArM: Cannabis als Medizin",
            "url": "https://www.bfarm.de/DE/Bundesopiumstelle/Medizinisches-Cannabis/_node.html",
        },
    ]
    results = []
    for item in urls_meta:
        paragraphs = fetch_page_text(item["url"])
        if not paragraphs:
            print(f"     ⚠️  Keine Inhalte extrahiert für '{item['title']}'")
            continue
        results.append({**item, "paragraphs": paragraphs, "source": "bfarm"})
        time.sleep(0.3)
    return results


def create_cannabis_training_data(pubmed_results: List[Dict], emcdda_reports: List[Dict], bfarm_reports: List[Dict]) -> List[Dict]:
    """Erstellt Trainingsexamples aus Cannabis-Daten."""
    examples = []
    system_prompt = """Du bist ein Cannabis-Zucht-Experte & Sommelier mit Spezialisierung auf:
- Genetik: Landraces, IBLs, F1-Hybriden, Polyhybriden, Backcrossing
- Phänotyp-Selektion: Struktur, Blütezeit, Ertrag, Resistenz
- Terpen-Profile: Myrcen, Limonen, Caryophyllen, Pinen, Linalool, Terpinolen, Humulen
- Cannabinoid-Biosynthese: THC, CBD, CBG, CBC, THCV, CBN - Pathways & Regulation
- Anbau: Living Soil, Nährstoffmanagement (veganisch, mineralisch), pH/EC, VPD
- Ernte & Curing: Trichom-Reife, Trocknungskurven, Curing-Protokolle, Terpen-Erhalt
- Sensorik: Aroma-Rad, Flavour-Wheel, Pairing (Food/Drink), Effect-Profile
- Deutsches Recht: BtMG (alt), MedCanG, KCanG/CanG (neu), Anbauvereinigungen, THC-Grenzwerte

Antworte technisch präzise, praxiserprobt, rechtlich aktuell (Stand 2024/2025)."""
    
    # PubMed Abstracts → Q&A
    for paper in pubmed_results:
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")
        journal = paper.get("journal", "")
        year = paper.get("year", "")
        doi = paper.get("doi", "")
        
        if len(abstract) < 300:
            continue
        
        # Verschiedene Frage-Typen
        qa_pairs = [
            (f"Was sind die wichtigsten Erkenntnisse aus der Studie '{title}' ({journal}, {year})?", 
             f"Diese Studie ({journal}, {year}, DOI: {doi}) untersuchte {title.lower()}. Kernfunde: {abstract[:1500]}..."),
            (f"Erkläre die Relevanz dieser Forschung für Cannabis-Zucht und -Anbau: '{title}'",
             f"Für Züchter und Anbauer ist diese Arbeit relevant, weil: {abstract[:1500]}..."),
        ]
        
        for q, a in qa_pairs:
            examples.append({
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": q},
                    {"role": "assistant", "content": a}
                ],
                "metadata": {"source": "pubmed", "pmid": paper.get("pmid"), "doi": doi}
            })
    
    # EMCDDA + BfArM: echte Absätze der Seite → Q&A (kein Template mehr, keine
    # "Quelle: {url}" im Trainingsziel - siehe collect_gardening.py Begründung)
    for report in emcdda_reports + bfarm_reports:
        title = report.get("title", "")
        source_label = "EMCDDA-Bericht" if report.get("source") == "emcdda" else "BfArM-Information"
        for para in report.get("paragraphs", []):
            if len(para) < 150:
                continue
            qa_pairs = [
                (f"Was sagt der {source_label} '{title}' zum Thema Cannabis-Regulierung?",
                 para[:2000]),
                (f"Fasse einen relevanten Punkt aus '{title}' zusammen.",
                 para[:2000]),
            ]
            for q, a in qa_pairs:
                examples.append({
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": q},
                        {"role": "assistant", "content": a}
                    ],
                    "metadata": {"source": report.get("source"), "title": title}
                })
    
    return examples


def main():
    output_dir = Path("./data/raw/cannabis")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("🌿 Sammle Cannabis-Daten aus freien Quellen...")
    
    all_pubmed = []
    for query in SOURCES["pubmed_cannabis"]["queries"]:
        print(f"  🔍 PubMed: '{query}'")
        results = fetch_pubmed_abstracts(query, max_results=30)
        all_pubmed.extend(results)
        print(f"     → {len(results)} Abstracts")
        time.sleep(0.5)  # Rate limit freundlich
    
    # Deduplizieren nach PMID
    seen = set()
    unique_pubmed = []
    for p in all_pubmed:
        if p["pmid"] not in seen:
            seen.add(p["pmid"])
            unique_pubmed.append(p)
    
    print(f"\n📊 PubMed: {len(unique_pubmed)} einzigartige Abstracts")
    
    # EMCDDA
    emcdda = fetch_emcdda_reports()
    print(f"📊 EMCDDA: {len(emcdda)} Reports mit Inhalt")

    # BfArM (BUGFIX: wurde vorher definiert, aber nie aufgerufen)
    bfarm = fetch_bfarm_reports()
    print(f"📊 BfArM: {len(bfarm)} Seiten mit Inhalt")

    # Training Data erstellen
    training_examples = create_cannabis_training_data(unique_pubmed, emcdda, bfarm)
    print(f"📝 Training Examples: {len(training_examples)}")
    
    # Speichern
    out_file = output_dir / "cannabis_training.jsonl"
    with open(out_file, 'w', encoding='utf-8') as f:
        for ex in training_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    
    # Auch Rohdaten speichern
    raw_file = output_dir / "pubmed_raw.jsonl"
    with open(raw_file, 'w', encoding='utf-8') as f:
        for p in unique_pubmed:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    
    print(f"\n✅ Gespeichert:")
    print(f"   Training: {out_file}")
    print(f"   Rohdaten: {raw_file}")


if __name__ == "__main__":
    main()