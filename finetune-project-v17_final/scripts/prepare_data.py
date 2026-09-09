#!/usr/bin/env python3
"""
Data Preparation Script für Fine-Tuning Projekt
Konvertiert PDF/MD/TXT/DOCX/Code → chat_template JSONL.

Wichtige Qualitätsregeln:
- PDF-Text wird vor dem Chunking bereinigt (Kopf-/Fußzeilen, Seitenmarker,
  typische PDF-Formularreste).
- Zeilenumbrüche innerhalb von Wörtern werden repariert.
- Gesetzestexte werden strukturbewusst an §/Artikel-Grenzen geschnitten.
- Allgemeine Texte werden bevorzugt an Absatz-/Satzgrenzen geschnitten.
- Kein harter Schnitt mitten in einem Wort.
- Train/Validation wird auf DOKUMENT-Ebene getrennt, damit überlappende
  Chunks desselben Dokuments nicht in beide Splits gelangen.
- Doppelte bzw. offensichtlich unbrauchbare Chunks werden verworfen.

Nutzung:
    python scripts/prepare_data.py --input-dir "/pfad/zu/eigenen/Daten" --output-dir ./data/processed
"""

import os
import sys
import json
import argparse
import re
import unicodedata
from pathlib import Path
from typing import List, Dict, Iterator, Tuple
import random

if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

try:
    from docx import Document
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False


DOMAIN_SYSTEM_PROMPTS = {
    "philosophie_ethik": """Du bist ein Experte für Philosophie und Ethik mit tiefgreifendem Wissen zu:
- Klassischer Philosophie (Aristoteles, Platon, Stoa, Epikur)
- Neuzeitlicher Ethik (Kant, Utilitarismus, Tugendethik, Diskursethik)
- Politischer Philosophie (Althusius, Löwenthal, militante Demokratie)
- Angewandter Ethik (Bioethik, Technikethik, KI-Ethik)

Antworte präzise, strukturiert, mit Quellenangaben (Werke, Kapitel) wo möglich.""",

    "recht_de_eu": """Du bist ein Experte für deutsches und europäisches Recht mit Fokus auf:
- Verfassungsrecht (GG), Zivilrecht (BGB), Strafrecht (StGB)
- Datenschutzrecht (DSGVO, BDSG, TTDSG)
- Betäubungsmittelrecht (BtMG, MedCanG, CanG)
- Verwaltungsrecht, Europa- & Völkerrecht

Zitiere Paragraphen, Urteile (BGH, BVerfG, EuGH), Literatur. Unterscheide klar: geltendes Recht vs. Rechtslage vor Reformen.""",

    "programmieren": """Du bist ein Senior Software Engineer mit Expertise in:
- Python, Java, JavaScript/TypeScript, Rust, Go, C/C++
- Software Architecture (Clean Code, SOLID, Design Patterns, DDD)
- Testing (PyTest, JUnit, Jest), CI/CD, DevOps, Container
- Performance Engineering, Security, Data Structures & Algorithms

Code-Beispiele: lauffähig, typisiert, dokumentiert, Best Practices. Erkläre Trade-offs.""",

    "wissenschaft": """Du bist ein Wissenschaftler mit breitem Fachwissen in:
- Physik, Chemie, Biologie, Medizin, Neurowissenschaften
- Klimawissenschaft, Umweltwissenschaften
- Forschungsmethodik, Statistik, Evidenzbewertung (RCT, Meta-Analysen)
- Wissenschaftstheorie (Popper, Kuhn, Falsifikation, Reproduzierbarkeit)

Antworte evidenzbasiert, mit Studien-Referenzen (DOI, PMID), unterscheide Hypothese/Theorie/Fakt.""",

    "gaertnern": """Du bist ein Gärtnermeister / Permakultur-Experte mit Wissen zu:
- Biologischem Anbau, Permakultur, Regenerativer Landwirtschaft
- Bodenkunde, Kompostierung, Mulchen, Mikrobiologie
- Pflanzenphysiologie, Schädlingsmanagement (Nützlinge, IPM)
- Obst-/Gemüsebau, Kräuter, Heilpflanzen, Waldgarten
- Hydroponik/Aeroponik, Indoor-Growing, LED-Beleuchtung

Praxisnah, saisonal, standortangepasst (DE-Klimazonen).""",

    "cannabis_zucht_sommelier": """Du bist ein Cannabis-Zucht-Experte & Sommelier mit Spezialisierung auf:
- Genetik: Landraces, IBLs, F1-Hybriden, Polyhybriden, Backcrossing
- Phänotyp-Selektion: Struktur, Blütezeit, Ertrag, Resistenz
- Terpen-Profile: Myrcen, Limonen, Caryophyllen, Pinen, Linalool, Terpinolen, Humulen
- Cannabinoid-Biosynthese: THC, CBD, CBG, CBC, THCV, CBN - Pathways & Regulation
- Anbau: Living Soil, Nährstoffmanagement (veganisch, mineralisch), pH/EC, VPD
- Ernte & Curing: Trichom-Reife, Trocknungskurven, Curing-Protokolle, Terpen-Erhalt
- Sensorik: Aroma-Rad, Flavour-Wheel, Pairing (Food/Drink), Effect-Profile
- Deutsches Recht: BtMG (alt), MedCanG, CanG (neu), Anbauvereinigungen, THC-Grenzwerte

Antworte technisch präzise, praxiserprobt, rechtlich aktuell.""",

    "arma3_technical": """Du bist ein Arma-3-Experte für Missionbau, Mapbau, SQF, Configs, Multiplayer, Servertechnik und Performance. Trenne dokumentierte Engine-/API-Funktionen von Community-Praxis und nenne Versionsabhängigkeiten, wenn relevant.""",
    "arma3_modding": """Du bist ein Arma-3-Modding-Experte mit Schwerpunkt CBA/ACE und Addon-/Config-Entwicklung. Erkläre technische Zusammenhänge reproduzierbar und unterscheide dokumentierte Fakten von Community-Konventionen.""",
    "milsim": """Du bist ein Arma-3-Milsim-Experte. Unterscheide strikt zwischen Spielmechanik, Milsim-Community-Praxis und realer Militärdoktrin.""",
    "military_general": """Du bist ein militärwissenschaftlicher Assistent für öffentlich dokumentierte allgemeine Doktrin, Terminologie, Organisation und Militärgeschichte. Unterscheide Nation, Epoche und Quelle.""",
    "military_bundeswehr": """Du kennst öffentlich zugängliche Informationen zur Bundeswehr. Erkläre Terminologie, Organisation, Geschichte und allgemein dokumentierte Doktrinkonzepte und kennzeichne Quellenstatus und Aktualität.""",
    "military_us_army": """Du kennst öffentlich zugängliche US-Army-Doktrin und Terminologie. Unterscheide ADP, FM und ATP sowie historische und aktuelle Inhalte.""",
    "military_british_army": """Du kennst öffentlich zugängliche britische Landstreitkräfte-Doktrin und Terminologie. Unterscheide UK-spezifische Begriffe von NATO-Begriffen.""",
    "military_australian_army": """Du kennst öffentlich zugängliche australische Army-Doktrin, Militärgeschichte und Terminologie. Kennzeichne historische und aktuelle Inhalte.""",
    "military_french_army": """Du kennst öffentlich zugängliche französische Landstreitkräfte-Doktrin und Terminologie. Nutze bei französischen Quellen Originalbegriffe mit deutscher Erklärung.""",
    "military_polish_army": """Du kennst öffentlich zugängliche polnische militärische Terminologie, Geschichte und Doktrin. Unterscheide polnische Begriffe von NATO-/englischen Entsprechungen.""",

    "lifehacks_alltag": """Du bist ein praktischer Lebensberater für Alltagsprobleme & Lifehacks:
- Haushalt, Organisation, Zeitmanagement, Produktivität
- Gesundheit, Schlaf, Ernährung, Bewegung (evidenzbasiert)
- Finanzen, Steuern, Versicherungen, Verträge (DE-Kontext)
- Reparaturen, DIY, Werkzeug, Materialkunde
- Digital Life: Privacy, Security, Automation, Tools

Lösungsorientiert, kosteneffizient, nachhaltig, sofort umsetzbar.""",

    "general": """Du bist ein allwissender Assistent mit tiefer Expertise in:
- Ethik, Philosophie, Wissenschaft
- Programmierung (alle Sprachen, Best Practices)
- Gärtnern (biologisch, Permakultur, Hydroponik)
- Deutscher & EU-Gesetzeslage (BGB, StGB, BtMG, MedCanG, CanG, DSGVO)
- Lifehacks, Alltagsprobleme, praktische Lösungen
- Cannabis-Zucht (Genetik, Terpene, Nährstoffe, Ernte, Curing)
- Cannabis-Sommelier (Sorten-Profiling, Sensorik, Pairing)

Antworte präzise, praxisnah, mit Quellenangaben wo möglich.""",
}

DOMAIN_KEYWORDS = {
    "philosophie_ethik": ["philosophie", "ethik", "kant", "aristoteles", "platon", "stoa", "althusius", "loewenstein", "militant", "montaigne", "marc aurel", "tugend"],
    "recht_de_eu": ["dsgvo", "gdpr", "bgb", "stgb", "btmg", "medcang", "cang", "gesetz", "verordnung", "richtlinie", "eu-recht", "datenschutz", "bds", "ttdsg", "grundgesetz", "artikel"],
    "programmieren": ["python", "java", "javascript", "typescript", "rust", "software", "oop", "design pattern", "clean code", "testing", "pytest", "git", "docker", "kubernetes", "algorithmus", "datenstruktur"],
    "wissenschaft": ["arxiv", "pubmed", "paper", "studie", "forschung", "wissenschaft", "physik", "chemie", "biologie", "medizin", "neurowissenschaft", "klima", "statistik", "meta-analyse"],
    "gaertnern": ["gaertnern", "garten", "permakultur", "boden", "kompost", "pflanze", "anbau", "obst", "gemuese", "kraeuter", "heilpflanze", "hydroponik", "indoor"],
    "cannabis_zucht_sommelier": ["cannabis", "hanf", "marihuana", "thc", "cbd", "terpen", "zucht", "genetik", "phänotyp", "ernte", "curing", "sommelier", "sensorik", "sorten", "landrace", "ibl", "backcross"],
    "lifehacks_alltag": ["lifehack", "alltag", "haushalt", "organisation", "produktivitaet", "finanzen", "steuern", "versicherung", "reparatur", "diy", "werkzeug", "schlaf", "ernaehrung"],
    "infosicherheit": ["informationssicherheit", "datensicherheit", "bsi", "isds", "isms", "schutzbedarf", "risikoanalyse", "cyber", "cps", "pico", "micropython"],
    "arma3_technical": ["arma 3", "arma3", "sqf", "eden", "3den", "mission.sqm", "description.ext", "terrain builder", "buldozer", "headless client", "zeus"],
    "arma3_modding": ["cba_a3", "ace3", "config.cpp", "cfgfunctions", "addon builder", "object builder", "modding"],
    "milsim": ["milsim", "mil-sim", "zeus", "briefing", "debriefing", "radio procedure"],
    "military_general": ["militärdoktrin", "military doctrine", "nato", "land operations", "combined arms", "militärgeschichte"],
    "military_bundeswehr": ["bundeswehr", "heer", "auftragstaktik", "zentrale dienstvorschrift"],
    "military_us_army": ["u.s. army", "us army", "adp ", "field manual", "army techniques publication", "mission command"],
    "military_british_army": ["british army", "uk defence", "uk land power", "army field manual", "land warfare centre"],
    "military_australian_army": ["australian army", "australian army journal", "australian doctrine"],
    "military_french_army": ["armée de terre", "cdec", "rft 3.2.1", "tactique générale"],
    "military_polish_army": ["wojsko polskie", "polish army", "siły zbrojne", "doktryna"],
}

ALLOWED_EXTENSIONS = {
    ".md", ".txt", ".py", ".js", ".ts", ".java", ".cpp", ".c", ".h",
    ".json", ".yaml", ".yml", ".csv", ".pdf", ".docx", ".doc",
    ".rst", ".tex", ".html", ".htm", ".xml", ".mdx",
}

# Typische Kopf-/Fußzeilen der von gesetze-im-internet.de gespeicherten PDFs.
HEADER_FOOTER_PATTERNS = [
    re.compile(r"^\s*Ein Service des Bundesminister(?:iums|ium).*Justiz.*$", re.I),
    re.compile(r"^\s*Ein Service des Bundesamts für Justiz.*$", re.I),
    re.compile(r"^\s*www\.gesetze-im-internet\.de\s*$", re.I),
    re.compile(r"^\s*-\s*Seite\s+\d+\s+von\s+\d+\s*-\s*$", re.I),
    re.compile(r"^\s*Seite\s+\d+\s*(?:von\s+\d+)?\s*$", re.I),
]

LAW_MARKER_RE = re.compile(
    r"(?m)^(?:\s*)(§{1,2}\s*\d+[a-zA-Z]*(?:\s*[-–]\s*\d+)?\.?|"
    r"Artikel\s+\d+[a-zA-Z]*(?:\s*[-–]\s*\d+)?\.?)\s*"
)

def detect_domain(filepath: Path, content: str) -> str:
    path_str = str(filepath).lower()
    content_lower = content[:5000].lower()
    scores = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if kw in path_str:
                score += 3
            if kw in content_lower:
                score += 1
        if score > 0:
            scores[domain] = score
    return max(scores, key=scores.get) if scores else "general"


def _is_noise_line(line: str) -> bool:
    s = " ".join(line.split()).strip()
    if not s:
        return True
    for pat in HEADER_FOOTER_PATTERNS:
        if pat.match(s):
            return True
    # Reine Seiten-/Formularpunkte oder extrem kurze Navigationsreste.
    if len(s) >= 6 and re.fullmatch(r"[\s.\-_–—·•]{6,}", s):
        return True
    return False


def clean_pdf_text(text: str) -> str:
    """Bereinigt PDF-Textextraktion, ohne den eigentlichen Inhalt umzuschreiben."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")

    # PDF-Zeilenumbruch mitten im Wort: "Bundes-\nministerium" -> "Bundesministerium".
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)

    raw_lines = text.split("\n")
    lines = []
    for line in raw_lines:
        line = line.replace("\u00a0", " ").strip()
        if _is_noise_line(line):
            continue
        lines.append(line)

    # Wiederkehrende Kopf-/Fußzeilen erkennen. Nur entfernen, wenn sie
    # mehrfach exakt vorkommen; so werden echte Überschriften nicht versehentlich gelöscht.
    counts = {}
    for line in lines:
        key = re.sub(r"\s+", " ", line).strip()
        if 4 <= len(key) <= 160:
            counts[key] = counts.get(key, 0) + 1

    repeated_noise = {
        k for k, v in counts.items()
        if v >= 3 and (
            "gesetze-im-internet.de" in k.lower()
            or "bundesministerium" in k.lower()
            or "bundesamt für justiz" in k.lower()
            or re.fullmatch(r"-?\s*Seite\s+\d+\s+von\s+\d+\s*-?", k, re.I)
        )
    }
    lines = [x for x in lines if re.sub(r"\s+", " ", x).strip() not in repeated_noise]

    # PDF-Text hat oft harte Zeilenumbrüche nach jedem visuellen Zeilenende.
    # Wir verbinden normale Fließtextzeilen, behalten aber Strukturmarker.
    out = []
    current = ""

    def flush():
        nonlocal current
        if current.strip():
            out.append(current.strip())
        current = ""

    for line in lines:
        stripped = line.strip()

        # Gesetzes-/Artikelmarker oder Überschrift: neuen Block beginnen.
        if LAW_MARKER_RE.match(stripped):
            flush()
            current = stripped
            continue

        # Überschriften/Nummerierungen sollen ebenfalls nicht an die vorige
        # Textzeile angeklebt werden.
        if re.match(r"^(?:Abschnitt|Unterabschnitt|Kapitel|Teil|Anlage|Inhaltsübersicht)\b", stripped, re.I):
            flush()
            current = stripped
            continue

        if not current:
            current = stripped
            continue

        # Wenn die vorherige Zeile mit Satzzeichen endet, ist ein neuer
        # Absatz/Block plausibel; sonst handelt es sich meist um PDF-Wrapping.
        if re.search(r"[.!?:;)]$", current) and (
            stripped[:1].isupper() or re.match(r"^[A-ZÄÖÜ§]", stripped)
        ):
            # Bei Gesetzeslisten ist ein Absatzwechsel häufig trotzdem nur
            # ein visueller Umbruch. Wir setzen hier einen normalen Absatz.
            current += " " + stripped
        else:
            current += " " + stripped

    flush()

    cleaned = "\n\n".join(out)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def clean_text(text: str, is_pdf: bool = False) -> str:
    if is_pdf:
        text = clean_pdf_text(text)
    else:
        text = unicodedata.normalize("NFC", text)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _hard_split_by_sentences(text: str, max_chars: int) -> List[str]:
    """Teilt lange Blöcke an Satzgrenzen; niemals mitten im Wort."""
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ0-9§])", text)
    chunks, current = [], ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > max_chars:
            # Letzter Ausweg: Wortgrenze, nie Character-Schnitt.
            words = sentence.split()
            part = ""
            for word in words:
                if part and len(part) + 1 + len(word) > max_chars:
                    chunks.append(part.strip())
                    part = word
                else:
                    part = f"{part} {word}".strip()
            if part:
                chunks.append(part.strip())
            continue

        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > max_chars:
            chunks.append(current.strip())
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current.strip())
    return chunks


def chunk_law_text(text: str, max_chars: int = 3000, overlap: int = 0) -> List[str]:
    """Strukturbewusstes Chunking für Gesetzes-/Verordnungstexte.

    §/Artikel-Einheiten werden bevorzugt vollständig erhalten. Sehr lange
    Einheiten werden an Absätzen/Sätzen bzw. Wortgrenzen geteilt.
    """
    markers = list(LAW_MARKER_RE.finditer(text))
    if not markers:
        return chunk_text_generic(text, max_chars=max_chars, overlap=overlap)

    units = []
    # Text vor dem ersten §/Artikel (z.B. Titel) behalten.
    prefix = text[:markers[0].start()].strip()
    if len(prefix) >= 150:
        units.append(prefix)

    for i, m in enumerate(markers):
        start = m.start()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        unit = text[start:end].strip()
        if len(unit) >= 120:
            units.append(unit)

    result = []
    for unit in units:
        if len(unit) <= max_chars:
            result.append(unit)
        else:
            result.extend(_hard_split_by_sentences(unit, max_chars))

    return [x for x in result if len(x) >= 150]


def chunk_text_generic(text: str, max_chars: int = 3000, overlap: int = 0) -> List[str]:
    """Absatz-/satzbasiertes Chunking für normale Dokumente.

    overlap=0 ist absichtlich Standard: Für Fine-Tuning wird keine künstliche
    Duplikation erzeugt. Ein optionaler kleiner Satz-Overlap kann aktiviert
    werden, wenn das Projekt dies ausdrücklich benötigt.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]

    chunks = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_hard_split_by_sentences(paragraph, max_chars))
            continue

        candidate = f"{current}\n\n{paragraph}".strip()
        if current and len(candidate) > max_chars:
            chunks.append(current.strip())
            current = paragraph
        else:
            current = candidate

    if current:
        chunks.append(current.strip())

    # Optionaler Satz-Overlap nur auf fertigen Chunks. Standardmäßig 0.
    if overlap > 0 and len(chunks) > 1:
        overlapped = []
        for i, chunk in enumerate(chunks):
            if i == 0:
                overlapped.append(chunk)
                continue
            prev_sentences = re.split(r"(?<=[.!?])\s+", chunks[i - 1])
            tail = prev_sentences[-1].strip() if prev_sentences else ""
            candidate = f"{tail} {chunk}".strip() if tail else chunk
            overlapped.append(candidate[:max_chars] if len(candidate) <= max_chars else chunk)
        chunks = overlapped

    return [c for c in chunks if len(c) >= 150]


def chunk_text(text: str, max_chars: int = 3000, overlap: int = 0, domain: str = "", source: str = "") -> List[str]:
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if len(text) >= 150 else []

    is_law = domain == "recht_de_eu" or any(
        x in source.lower()
        for x in ("bgb", "stgb", "stpo", "gg", "btmg", "hgb", "bdsg", "ttdsg",
                  "dsgvo", "amg", "pflag", "pflschg", "gesetz", "verordnung")
    )
    if is_law and LAW_MARKER_RE.search(text):
        return chunk_law_text(text, max_chars=max_chars, overlap=overlap)
    return chunk_text_generic(text, max_chars=max_chars, overlap=overlap)


def is_bad_chunk(chunk: str) -> bool:
    """Qualitätsfilter gegen kaputte PDF-Fragmente und Layout-Müll."""
    s = " ".join(chunk.split())
    if len(s) < 150:
        return True

    # Typische Zeichen-/Layoutartefakte.
    if len(re.findall(r"[.·•_-]", s)) > max(25, len(s) * 0.08):
        return True

    if re.search(r"\bSeite\s+\d+\s+von\s+\d+\b", s, re.I):
        return True

    # Kein Chunk sollte mit einem offensichtlichen Wortfragment beginnen
    # (z.B. "rkehrbringen"). Normale Bindestrichwörter bleiben erlaubt.
    first = s.split()[0]
    if re.match(r"^[a-zäöüß]{3,}$", first) and first not in {
        "und", "oder", "aber", "auch", "bei", "mit", "von", "für", "durch",
        "nach", "über", "unter", "gegen", "ohne", "sowie", "dabei", "hier",
        "dies", "diese", "dieser", "dem", "den", "der", "die", "das"
    }:
        # Nur sehr vorsichtig filtern: Ein echter Satz kann klein beginnen.
        # Verdächtig ist insbesondere ein kurzer Rest ohne erkennbare Endung.
        if len(first) <= 8 and not re.search(r"[.!?:;]", s[:80]):
            return True

    # Extrem hoher Anteil einzelner Layout-/Formularfragmente.
    words = s.split()
    if len(words) >= 10:
        single_char_words = sum(1 for w in words if len(w.strip(".,:;()[]")) <= 1)
        if single_char_words / len(words) > 0.35:
            return True

    return False


def dedupe_chunks(chunks: List[str]) -> List[str]:
    seen = set()
    result = []
    for chunk in chunks:
        normalized = re.sub(r"\s+", " ", chunk).strip().casefold()
        if len(normalized) < 150 or normalized in seen:
            continue
        seen.add(normalized)
        result.append(chunk.strip())
    return result


def guess_title(chunk: str, filepath: Path) -> str:
    for line in chunk.splitlines():
        line = line.strip().lstrip("#").strip()
        if 10 < len(line) < 120:
            return line
    return filepath.stem.replace("_", " ").replace("-", " ")


def create_training_examples(chunks: List[str], domain: str, source: str, filepath: Path) -> List[Dict]:
    system_prompt = DOMAIN_SYSTEM_PROMPTS.get(domain, DOMAIN_SYSTEM_PROMPTS["general"])
    examples = []
    domain_readable = domain.replace("_", " ")

    for i, chunk in enumerate(chunks):
        if is_bad_chunk(chunk):
            continue

        title = guess_title(chunk, filepath)
        if domain == "recht_de_eu":
            # Juristische Chunks sollen nicht nur über generische "Erkläre mir"-Prompts
            # abgefragt werden. Die Antwort bleibt bewusst der dokumentierte Originalchunk;
            # so lernt das Modell Quellenbindung statt frei erfundener Rechtsauslegung.
            marker = re.match(r"(?:§{1,2}\s*\d+[a-zA-Z]*|Artikel\s+\d+[a-zA-Z]*)", chunk.strip())
            norm = marker.group(0) if marker else title
            templates = [
                f"Was regelt {norm} in {source}?",
                f"Welche Regelung enthält der dokumentierte Abschnitt {norm} aus {source}?",
                f"Gib den relevanten Inhalt von {norm} aus {source} quellengetreu wieder.",
                f"Welche Vorschrift ist hier in {source} dokumentiert ({norm})?",
                f"Erkläre anhand des vorliegenden Gesetzestextes, worum es bei {norm} geht.",
            ]
        else:
            templates = [
                f"Was weißt du über folgendes Thema aus dem Bereich {domain_readable}: {title}?",
                f"Erkläre mir fundiert: {title}",
                f"Ich interessiere mich für {title} (Bereich {domain_readable}). Was sollte ich wissen?",
            ]

        examples.append({
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": random.choice(templates)},
                {"role": "assistant", "content": chunk},
            ],
            "metadata": {
                "source": source,
                "source_file": source,
                "document": filepath.name,
                "domain": domain,
                "document_type": "pdf" if filepath.suffix.lower() == ".pdf" else filepath.suffix.lower().lstrip("."),
                "content_basis": "document_extraction",
                "temporal_status": "unknown",
                "chunk_index": i,
            },
        })
    return examples


def extract_text_from_file(filepath: Path) -> Tuple[str, bool]:
    suffix = filepath.suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        return "", False

    try:
        if filepath.stat().st_size > 10 * 1024 * 1024:
            print(f"⚠️  Datei zu groß (>10MB), überspringe: {filepath}")
            return "", False
    except OSError:
        pass

    text_exts = {
        ".md", ".txt", ".py", ".js", ".ts", ".java", ".cpp", ".c", ".h",
        ".json", ".yaml", ".yml", ".csv", ".rst", ".tex", ".html", ".htm",
        ".xml", ".mdx"
    }

    if suffix in text_exts:
        try:
            return clean_text(filepath.read_text(encoding="utf-8", errors="ignore")), False
        except Exception as e:
            print(f"❌ Lesefehler {filepath}: {e}")
            return "", False

    if suffix == ".pdf":
        if not HAS_FITZ:
            print(f"⏭️  PDF übersprungen (PyMuPDF fehlt, 'pip install pymupdf'): {filepath}")
            return "", True
        try:
            text_parts = []
            with fitz.open(filepath) as doc:
                for page in doc:
                    text_parts.append(page.get_text("text"))
            text = clean_pdf_text("\n".join(text_parts))
            if not text:
                print("⚠️  PDF ohne extrahierbaren Text (vermutlich Scan/Bild-PDF, OCR nötig):", filepath)
            return text, True
        except Exception as e:
            print(f"❌ PDF-Fehler {filepath}: {e}")
            return "", True

    if suffix in [".docx", ".doc"]:
        if not HAS_DOCX:
            print(f"⏭️  DOCX übersprungen (python-docx fehlt): {filepath}")
            return "", False
        try:
            doc = Document(filepath)
            return clean_text("\n\n".join(p.text for p in doc.paragraphs)), False
        except Exception as e:
            print(f"❌ DOCX-Fehler {filepath}: {e}")
            return "", False

    return "", False


def iter_files(input_dir: Path, extensions: set) -> Iterator[Path]:
    for filepath in sorted(input_dir.rglob("*")):
        if filepath.is_file() and filepath.suffix.lower() in extensions:
            yield filepath


def choose_split_for_document(rng: random.Random, val_split: float) -> str:
    return "val" if rng.random() < val_split else "train"


def main():
    parser = argparse.ArgumentParser(description="Prepare training data (JSONL, chat_template)")
    parser.add_argument("--input-dir", required=True, help="Verzeichnis mit Rohdaten")
    parser.add_argument("--output-dir", required=True, help="Ausgabe-Verzeichnis")
    parser.add_argument("--max-chars", type=int, default=3000, help="Max. Zeichen pro Chunk")
    parser.add_argument("--val-split", type=float, default=0.02, help="Validation-Split auf Dokumentebene")
    parser.add_argument("--overlap", type=int, default=0, help="Optionaler Satz-Overlap; 0 empfohlen")
    args = parser.parse_args()

    if not 0.0 < args.val_split < 1.0:
        raise SystemExit("❌ --val-split muss zwischen 0 und 1 liegen.")
    if args.max_chars < 500:
        raise SystemExit("❌ --max-chars muss mindestens 500 sein.")
    if args.overlap < 0 or args.overlap >= args.max_chars:
        raise SystemExit("❌ --overlap muss >= 0 und kleiner als --max-chars sein.")

    input_dir = Path(args.input_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()

    if not input_dir.exists():
        print(f"❌ Input-Verzeichnis existiert nicht: {input_dir}")
        raise SystemExit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    train_path = output_dir / "train.jsonl"
    val_path = output_dir / "val.jsonl"

    rng = random.Random(42)
    domain_stats = {}
    total_files = 0
    skipped_files = 0
    train_count = 0
    val_count = 0

    with open(train_path, "w", encoding="utf-8") as train_file, \
         open(val_path, "w", encoding="utf-8") as val_file:

        for filepath in iter_files(input_dir, ALLOWED_EXTENSIONS):
            total_files += 1
            rel = filepath.relative_to(input_dir)
            print(f"  🔄 [{total_files}] {rel}")

            text, is_pdf = extract_text_from_file(filepath)
            if not text or len(text) < 200:
                print("     ⏭️  Zu kurz/leer, übersprungen")
                skipped_files += 1
                continue

            domain = detect_domain(filepath, text)
            domain_stats[domain] = domain_stats.get(domain, 0) + 1

            chunks = chunk_text(
                text,
                max_chars=args.max_chars,
                overlap=args.overlap,
                domain=domain,
                source=str(rel),
            )
            chunks = dedupe_chunks([c for c in chunks if not is_bad_chunk(c)])
            examples = create_training_examples(chunks, domain, str(rel), filepath)

            if not examples:
                print("     ⚠️  Keine qualitativ brauchbaren Chunks nach Bereinigung")
                skipped_files += 1
                continue

            # KRITISCH: Das komplette Dokument bleibt in genau EINEM Split.
            # So können überlappende/benachbarte Chunks derselben PDF nicht
            # gleichzeitig Train und Validation kontaminieren.
            split = choose_split_for_document(rng, args.val_split)
            target = val_file if split == "val" else train_file

            for ex in examples:
                target.write(json.dumps(ex, ensure_ascii=False) + "\n")
                if split == "val":
                    val_count += 1
                else:
                    train_count += 1

            print(
                f"     ✅ Domain: {domain}, Chunks: {len(chunks)}, "
                f"Examples: {len(examples)}, Split: {split}"
            )

            if total_files % 100 == 0:
                train_file.flush()
                val_file.flush()

    print("\n✅ Fertig!")
    print(f"   Train: {train_count} examples → {train_path}")
    print(f"   Val:   {val_count} examples → {val_path}")
    print(f"   Dateien verarbeitet: {total_files}")
    print(f"   Dateien übersprungen: {skipped_files}")
    print("\n📊 Domain-Verteilung (Dateien):")
    for domain, count in sorted(domain_stats.items(), key=lambda x: -x[1]):
        print(f"   {domain}: {count} Dateien")


if __name__ == "__main__":
    main()
