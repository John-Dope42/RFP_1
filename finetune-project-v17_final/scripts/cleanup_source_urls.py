#!/usr/bin/env python3
"""
Einmaliges Cleanup: Entfernt "\n\nQuelle: <url> ..." aus bereits gesammelten
Trainingsdaten. Hintergrund: collect_gardening.py hängte bisher an jede
Antwort eine Wikipedia-Quelle an - das trainierte kleine Modelle darauf, am
Ende JEDER Antwort eine URL zu erfinden, auch wenn keine echte Quelle vorlag
(beobachtetes Symptom: halluzinierte, leicht falsche URLs bei Themen, die gar
nicht aus dem Wikipedia-Collector stammten). collect_gardening.py wurde bereits
gefixt (sammelt ab jetzt ohne "Quelle:"-Anhang) - dieses Skript bereinigt die
schon vorhandenen Dateien rückwirkend, damit der Fix auch beim nächsten
Training wirkt, ohne alles neu von Wikipedia sammeln zu müssen.

Nutzung:
    python scripts/cleanup_source_urls.py
"""

import json
import re
import sys
from pathlib import Path

if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Matcht "\n\nQuelle: <alles bis Zeilenende, ggf. mit (CC-BY-SA)>" am Ende der Antwort
SOURCE_PATTERN = re.compile(r"\n\nQuelle:\s*\S+.*$", re.MULTILINE)

TARGET_FILES = [
    PROJECT_ROOT / "data" / "raw" / "gardening" / "gardening_training.jsonl",
    PROJECT_ROOT / "data" / "train.jsonl",
    PROJECT_ROOT / "data" / "val.jsonl",
]


def clean_file(path: Path) -> int:
    if not path.exists():
        print(f"⏭️  {path.relative_to(PROJECT_ROOT)} existiert nicht, überspringe")
        return 0

    lines_out = []
    changed = 0

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            touched = False
            for msg in obj.get("messages", []):
                if msg.get("role") == "assistant" and "Quelle:" in msg.get("content", ""):
                    new_content = SOURCE_PATTERN.sub("", msg["content"]).rstrip()
                    if new_content != msg["content"]:
                        msg["content"] = new_content
                        touched = True
            if touched:
                changed += 1
            lines_out.append(json.dumps(obj, ensure_ascii=False))

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_out) + "\n")

    print(f"✅ {path.relative_to(PROJECT_ROOT)}: {changed} Beispiele bereinigt")
    return changed


def main():
    total = 0
    for f in TARGET_FILES:
        total += clean_file(f)
    print(f"\n📊 Gesamt: {total} Beispiele bereinigt")
    print("\nHinweis: Falls du data/raw/gardening/gardening_training.jsonl geändert hast,")
    print("führe zur Sicherheit noch 'python scripts/merge_all.py' aus, um train.jsonl/")
    print("val.jsonl neu aus den (jetzt bereinigten) Rohdaten zu erzeugen.")


if __name__ == "__main__":
    main()
