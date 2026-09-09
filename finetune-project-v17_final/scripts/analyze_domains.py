#!/usr/bin/env python3
"""
Analysiert die Domain- und Feinthema-Verteilung in data/train.jsonl + val.jsonl.

Wichtig: Sucht Keywords NUR im Assistant-Antworttext, NICHT im System-Prompt.
Der System-Prompt listet pro Domain immer dieselbe Themen-Boilerplate auf
(z.B. "BtMG, MedCanG, CanG, DSGVO..." für JEDES Recht-Beispiel) - würde man
dort mitsuchen, sähe jede Recht-Antwort fälschlich nach "behandelt CanG UND
DSGVO" aus, egal worum es im Beispiel tatsächlich geht.

Nutzung:
    python scripts/analyze_domains.py
"""

import json
import sys
from pathlib import Path
from collections import Counter

if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Grobe Domain-Erkennung anhand des System-Prompts (der ist pro Domain fix)
DOMAIN_SIGNALS = {
    "recht_de_eu": ["experte für deutsches und europäisches recht", "experte für de/eu-recht"],
    "cannabis_zucht_sommelier": ["cannabis-zucht-experte", "cannabis-sommelier", "cannabis-zucht-experte & sommelier"],
    "gaertnern": ["gärtnermeister", "permakultur-experte"],
    "wissenschaft": ["wissenschaftler mit breitem fachwissen"],
    "programmieren": ["senior software engineer"],
    "philosophie_ethik": ["experte für philosophie und ethik", "experte für philosophie/ethik"],
    "lifehacks_alltag": ["praktischer lebensberater"],
    "general": ["allwissender assistent"],
}

# Feinthema-Keywords, gesucht NUR im Assistant-Text
FEINTHEMEN = {
    "recht_de_eu": {
        "CanG/MedCanG (aktuell)": ["cang", "medcang", "anbauvereinigung", "eigenanbau"],
        "BtMG (altes Recht)": ["btmg", "betäubungsmittelgesetz"],
        "DSGVO/Datenschutz": ["dsgvo", "gdpr", "datenschutz"],
        "BGB/Zivilrecht": ["bgb", "zivilrecht", "vertragsrecht"],
        "StGB/Strafrecht": ["stgb", "strafrecht", "straftat"],
        "EU-Recht (allgemein)": ["eu-recht", "eur-lex", "richtlinie (eu)", "verordnung (eu)"],
    },
    "cannabis_zucht_sommelier": {
        "Terpene/Sensorik": ["terpen", "sensorik", "aroma"],
        "Genetik/Zucht": ["genetik", "phänotyp", "landrace", "backcross", "hybrid"],
        "Anbau/Nährstoffe": ["nährstoff", "living soil", "ph-wert", "ec-wert"],
        "Ernte/Curing": ["curing", "trocknung", "trichom"],
        "Cannabinoide": ["thc", "cbd", "cbg", "cbc"],
    },
}


def load_examples(path: Path):
    if not path.exists():
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def detect_domain(example) -> str:
    sysmsg = ""
    for m in example.get("messages", []):
        if m.get("role") == "system":
            sysmsg = m["content"].lower()
            break
    for domain, signals in DOMAIN_SIGNALS.items():
        if any(sig in sysmsg for sig in signals):
            return domain
    return "unbekannt"


def assistant_text(example) -> str:
    for m in example.get("messages", []):
        if m.get("role") == "assistant":
            return m["content"].lower()
    return ""


def main():
    examples = load_examples(PROJECT_ROOT / "data" / "train.jsonl") + \
               load_examples(PROJECT_ROOT / "data" / "val.jsonl")

    if not examples:
        print("❌ Keine Trainingsdaten gefunden (data/train.jsonl bzw. val.jsonl leer/fehlend).")
        return

    domain_counts = Counter()
    feinthema_counts = {domain: Counter() for domain in FEINTHEMEN}
    feinthema_none = Counter()  # Beispiele, die KEIN Feinthema-Keyword treffen

    for ex in examples:
        domain = detect_domain(ex)
        domain_counts[domain] += 1

        if domain in FEINTHEMEN:
            text = assistant_text(ex)
            matched_any = False
            for label, keywords in FEINTHEMEN[domain].items():
                if any(kw in text for kw in keywords):
                    feinthema_counts[domain][label] += 1
                    matched_any = True
            if not matched_any:
                feinthema_none[domain] += 1

    total = sum(domain_counts.values())
    print(f"📊 Gesamt: {total} Beispiele (train + val)\n")

    print("=" * 60)
    print("DOMAIN-VERTEILUNG")
    print("=" * 60)
    for domain, count in domain_counts.most_common():
        pct = 100 * count / total
        bar = "█" * int(pct / 2)
        print(f"{domain:30s} {count:5d} ({pct:5.1f}%) {bar}")

    for domain, counter in feinthema_counts.items():
        if domain not in domain_counts:
            continue
        domain_total = domain_counts[domain]
        print(f"\n{'=' * 60}")
        print(f"FEINTHEMEN INNERHALB '{domain}' ({domain_total} Beispiele gesamt)")
        print("Hinweis: Ein Beispiel kann mehrere Feinthemen gleichzeitig treffen,")
        print("Prozentangaben daher NICHT auf 100% summierbar.")
        print("=" * 60)
        for label, count in counter.most_common():
            pct = 100 * count / domain_total
            bar = "█" * int(pct / 2)
            print(f"  {label:28s} {count:5d} ({pct:5.1f}%) {bar}")
        no_match = feinthema_none[domain]
        pct = 100 * no_match / domain_total
        print(f"  {'(kein Feinthema erkannt)':28s} {no_match:5d} ({pct:5.1f}%)")


if __name__ == "__main__":
    main()
