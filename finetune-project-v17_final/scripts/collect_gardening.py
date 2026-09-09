#!/usr/bin/env python3
"""
Gärtnern/Permakultur Daten Sammler - Kostenlose, CC-BY / Public Domain Quellen
Quellen: Uni-Extensions (Public Domain), Wikipedia (CC-BY-SA), Offene Bücher, Foren (mit Erlaubnis)
"""

import json
import requests
import sys
from pathlib import Path
from typing import List, Dict
import time
import re

if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


# ============================================================
# KOSTENLOSE GÄRTNERN-QUELLEN
# ============================================================
GARDENING_SOURCES = {
    "uni_extensions": {
        "description": "Universitäts-Extensions (USA) - Public Domain, wissenschaftlich fundiert",
        "sources": [
            {"name": "UC Davis Agriculture", "url": "https://anrcatalog.ucanr.edu/", "focus": "Obst, Gemüse, Boden, Schädlinge"},
            {"name": "Cornell Cooperative Extension", "url": "https://cce.cornell.edu/", "focus": "Gartenbau, IPM, Boden"},
            {"name": "Penn State Extension", "url": "https://extension.psu.edu/", "focus": "Pflanzenkrankheiten, Nährstoffe"},
            {"name": "Michigan State Extension", "url": "https://www.canr.msu.edu/", "focus": "Gewächshaus, Beeren, Bio-Anbau"},
            {"name": "Oregon State Extension", "url": "https://extension.oregonstate.edu/", "focus": "Permakultur, Bodenbiologie"},
        ]
    },
    "german_institutes": {
        "description": "Deutsche Institute - teils offen, teils kostenpflichtig",
        "sources": [
            {"name": "JKI (Julius Kühn-Institut)", "url": "https://www.jki.bund.de/", "focus": "Pflanzengesundheit, Sorten, Resistenz"},
            {"name": "BMEL / BLE", "url": "https://www.bmel.de/", "focus": "Öko-Landbau, Förderungen, Recht"},
            {"name": "FiBL Deutschland", "url": "https://www.fibl.org/de/", "focus": "Bio-Landbau, Forschung, Praxis"},
            {"name": "Naturschutzbund (NABU)", "url": "https://www.nabu.de/", "focus": "Naturgarten, Insekten, Biodiversität"},
        ]
    },
    "open_books": {
        "description": "Offene Bücher / Public Domain",
        "sources": [
            {"name": "Permaculture: A Designers' Manual (Auszüge)", "note": "Bill Mollison - nicht ganz PD, aber Zusammenfassungen"},
            {"name": "The One-Straw Revolution (Fukuoka)", "note": "Masanobu Fukuoka - Philosophie, Public Domain in Teilen"},
            {"name": "Gaia's Garden (Toby Hemenway)", "note": "Zusammenfassungen erlaubt"},
        ]
    },
    "wikipedia_ccbysa": {
        "description": "Wikipedia (CC-BY-SA 4.0) - strukturierte Artikel",
        "categories": [
            "Permakultur", "Biologischer Landbau", "Kompostierung", "Mulchen",
            "Bodenkunde", "Pflanzenphysiologie", "Nützlinge", "Integrierter Pflanzenschutz",
            "Hydroponik", "Aeroponik", "Aquaponik", "Vertikale Landwirtschaft",
            "Obstbau", "Gemüsebau", "Kräutergarten", "Heilpflanze",
            "Fruchtfolge", "Gründüngung", "Terra Preta", "Biochar",
            "Regenwurm", "Mykorrhiza", "Stickstofffixierung", "Komposttee",
            "Effektive Mikroorganismen (EM)", "Pflanzenstärkungsmittel",
        ]
    }
}


def search_wikipedia_title(query: str, headers: dict) -> str:
    """Fallback: findet den echten Artikeltitel per Volltextsuche, falls der
    angenommene Titel nicht exakt existiert (z.B. 'Biologischer Landbau' ->
    tatsächlicher Artikel heißt 'Ökologischer Landbau')."""
    url = "https://de.wikipedia.org/w/api.php"
    params = {
        "action": "query", "format": "json", "list": "search",
        "srsearch": query, "srlimit": 1,
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        hits = resp.json().get("query", {}).get("search", [])
        if hits:
            return hits[0]["title"]
    except Exception:
        pass
    return ""


def fetch_wikipedia_article(title: str, max_retries: int = 3) -> Dict:
    """Holt Wikipedia-Artikel über API (CC-BY-SA).

    BUGFIX: Die alte User-Agent-Zeile begann mit "Mozilla/5.0 ... AppleWebKit/537.36"
    - also einem kopierten Browser-UA-Präfix mit angehängtem Bot-Namen. Genau das
    verbietet Wikimedias User-Agent-Policy explizit ("Do not copy a browser's user
    agent for your bot, as bot-like behavior with a browser's user agent will be
    assumed malicious") und die Policy verlangt zusätzlich Kontaktinfos (E-Mail,
    Website oder Wiki-Username) im UA-String - beides fehlte, was den 403 "Please
    respect our robot policy" auf JEDER Anfrage erklärt, nicht nur bei zu vielen
    Requests. Ersetze <DEINE-EMAIL-ODER-URL> unten durch echte Kontaktinfo.

    BUGFIX 2: redirects=1 ergänzt, damit echte Wikipedia-Weiterleitungen (z.B.
    Kurztitel -> offizieller Lemma-Titel) automatisch aufgelöst werden. Für
    Titel, die auch damit nicht existieren (z.B. weil unser angenommener Name
    nicht dem tatsächlichen Artikeltitel entspricht), greift zusätzlich eine
    Volltextsuche als zweiter Versuch.
    """
    url = "https://de.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "extracts|categories|links",
        "explaintext": True,
        "exsectionformat": "plain",
        "cllimit": "max",
        "redirects": 1,
    }
    headers = {
        "User-Agent": "FineTuningProjectBot/1.0 (<DEINE-EMAIL-ODER-URL-HIER-EINTRAGEN>)",
        "Accept-Encoding": "gzip",
    }

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=30)
            if resp.status_code in (403, 429):
                retry_after = int(resp.headers.get("Retry-After", 5))
                print(f"     ⏳ Wikipedia bremst uns ({resp.status_code}), warte {retry_after}s...")
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            data = resp.json()
            pages = data.get("query", {}).get("pages", {})

            for page_id, page in pages.items():
                if page_id != "-1" and "extract" in page:
                    return {
                        "title": page.get("title", title),
                        "content": page["extract"],
                        "categories": [c["title"] for c in page.get("categories", [])],
                        "source": "wikipedia_de",
                        "license": "CC-BY-SA 4.0",
                        "url": f"https://de.wikipedia.org/wiki/{page.get('title', title).replace(' ', '_')}"
                    }

            # Exakter Titel existiert nicht (auch nach redirects=1) -> per
            # Volltextsuche den echten Titel finden und einmal nachversuchen.
            real_title = search_wikipedia_title(title, headers)
            if real_title and real_title != title:
                print(f"     🔎 '{title}' nicht gefunden, versuche stattdessen '{real_title}'...")
                return fetch_wikipedia_article(real_title, max_retries=1)
            return {}
        except Exception as e:
            print(f"❌ Wikipedia Fehler {title}: {e}")
            return {}

    print(f"     ⚠️  {title}: nach {max_retries} Versuchen weiterhin blockiert.")
    return {}


def create_gardening_training_data(articles: List[Dict]) -> List[Dict]:
    """Erstellt Trainingsexamples aus Gärtnern-Artikeln."""
    examples = []
    system_prompt = """Du bist ein Gärtnermeister / Permakultur-Experte mit Wissen zu:
- Biologischem Anbau, Permakultur, Regenerativer Landwirtschaft
- Bodenkunde, Kompostierung, Mulchen, Mikrobiologie
- Pflanzenphysiologie, Schädlingsmanagement (Nützlinge, IPM)
- Obst-/Gemüsebau, Kräuter, Heilpflanzen, Waldgarten
- Hydroponik/Aeroponik, Indoor-Growing, LED-Beleuchtung

Praxisnah, saisonal, standortangepasst (DE-Klimazonen)."""
    
    for article in articles:
        title = article.get("title", "")
        content = article.get("content", "")
        url = article.get("url", "")
        
        if len(content) < 300:
            continue
        
        # In Abschnitte splitten (Wikipedia hat oft gute Struktur)
        sections = re.split(r'\n\s*\n', content)
        
        for section in sections:
            section = section.strip()
            if len(section) < 200:
                continue
            
            # Q&A generieren.
            # WICHTIG: Keine "Quelle: {url}" mehr im Trainings-Ziel! Ein 3B-Modell
            # lernt daraus nur das FORMAT "Antwort endet mit einer URL", kann sich
            # aber die tatsächliche URL nicht zuverlässig merken - das Ergebnis sind
            # plausibel aussehende, aber falsche/halluzinierte Links bei Themen, die
            # gar nicht aus dieser Quelle stammen (beobachtet im Praxistest: das Modell
            # hängte "Quelle: https://de.wikipedia.org/wiki/Terpenen" - mit falschem
            # Titel - an eine Cannabis-Antwort, obwohl diese nicht aus dem
            # Wikipedia-Collector stammte). Die echte URL bleibt in "metadata"
            # erhalten, falls du sie fürs Nachschlagen/Zitieren außerhalb des Modells
            # brauchst - sie fließt nur nicht mehr ins Trainingsziel ein.
            qa_pairs = [
                (f"Erkläre das Thema '{title}' für den Hausgarten in Deutschland.",
                 f"{title}: {section[:2000]}..."),
                (f"Was sind die wichtigsten Punkte zu {title} für biologischen Anbau?",
                 f"Für biologischen Anbau relevant bei {title}: {section[:2000]}..."),
            ]
            
            for q, a in qa_pairs:
                examples.append({
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": q},
                        {"role": "assistant", "content": a}
                    ],
                    "metadata": {"source": "wikipedia", "title": title, "url": url}
                })
    
    return examples


def main():
    output_dir = Path("./data/raw/gardening")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("🌱 Sammle Gärtnern/Permakultur-Daten...")
    
    all_articles = []
    
    # Wikipedia Artikel (CC-BY-SA)
    categories = GARDENING_SOURCES["wikipedia_ccbysa"]["categories"]
    print(f"📚 Wikipedia: {len(categories)} Artikel...")
    
    for cat in categories:
        print(f"  📖 {cat}...")
        article = fetch_wikipedia_article(cat)
        if article and article.get("content"):
            all_articles.append(article)
            print(f"     → {len(article['content'])} chars")
        else:
            print(f"     ⚠️  Nicht gefunden")
        time.sleep(1.0)
    
    print(f"\n📊 Wikipedia Artikel gesammelt: {len(all_articles)}")
    
    # Training Data
    training_examples = create_gardening_training_data(all_articles)
    print(f"📝 Training Examples: {len(training_examples)}")
    
    # Speichern
    out_file = output_dir / "gardening_training.jsonl"
    with open(out_file, 'w', encoding='utf-8') as f:
        for ex in training_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    
    raw_file = output_dir / "gardening_raw.jsonl"
    with open(raw_file, 'w', encoding='utf-8') as f:
        for a in all_articles:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")
    
    print(f"\n✅ Gespeichert:")
    print(f"   Training: {out_file}")
    print(f"   Rohdaten: {raw_file}")
    
    # Hinweis für Uni-Extensions
    print(f"\n💡 TIPP: Uni-Extensions (UC Davis, Cornell, etc.) manuell hinzufügen:")
    print(f"   - PDFs herunterladen → in data/raw/gardening/ legen")
    print(f"   - prepare_data.py verarbeitet sie automatisch")


if __name__ == "__main__":
    main()