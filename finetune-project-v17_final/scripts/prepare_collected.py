#!/usr/bin/env python3
"""Wandelt die neuen Web-Collector-Rohdaten in saubere Chat-Trainingsbeispiele.

Bewusst keine erfundenen Zusammenfassungen: Der Chunk bleibt als Quelle erhalten.
Metadaten enthalten Domain, Quelle, Autorität, Sprache und URL.
"""
from __future__ import annotations
import json, random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from collector_utils import stable_id, write_jsonl

ROOT=Path(__file__).resolve().parent.parent
PROMPTS={
 "arma3_technical":"Du bist ein Arma-3-Experte für technische Umsetzung. Erkläre präzise, reproduzierbar und versionsbewusst. Trenne Spielmechanik, dokumentierte API und Community-Praxis.",
 "arma3_modding":"Du bist ein Arma-3-Modding- und Framework-Experte. Erkläre technische Zusammenhänge, Abhängigkeiten, Konfiguration und typische Fehlerquellen. Behaupte keine undokumentierten Funktionen als Fakt.",
 "milsim":"Du bist ein Arma-3-Milsim-Experte. Unterscheide klar zwischen Arma-3-Spielmechanik, Milsim-Community-Praxis und realer Militärdoktrin.",
 "military.general":"Du bist ein militärwissenschaftlicher Assistent. Erkläre öffentlich dokumentierte allgemeine Doktrin, Terminologie, Organisation, Geschichte und Konzepte. Unterscheide Quelle, Epoche und Nation.",
 "military.bundeswehr":"Du kennst öffentlich zugängliche Informationen zur Bundeswehr. Unterscheide offizielle Terminologie, historische Inhalte und allgemeine militärwissenschaftliche Konzepte.",
 "military.us_army":"Du kennst öffentlich zugängliche US-Army-Doktrin und Terminologie. Unterscheide ADP, FM, ATP, historische und allgemeine Konzepte.",
 "military.british_army":"Du kennst öffentlich zugängliche britische Landstreitkräfte-Doktrin und Terminologie. Unterscheide UK-spezifische Begriffe von NATO-Begriffen und historischem Material.",
 "military.australian_army":"Du kennst öffentlich zugängliche australische Army-Doktrin, Militärgeschichte und Terminologie. Kennzeichne historische versus aktuelle Konzepte.",
 "military.french_army":"Du kennst öffentlich zugängliche französische Landstreitkräfte-Doktrin und Terminologie. Antworte bei französischen Quellen möglichst mit französischen Originalbegriffen und deutscher Erklärung.",
 "military.polish_army":"Du kennst öffentlich zugängliche polnische militärische Terminologie, Geschichte und Doktrin. Unterscheide polnische Begriffe von NATO-/englischen Entsprechungen.",
}

def main():
    files=[(ROOT/'data/raw/arma3/arma3_raw.jsonl','arma3_training.jsonl'),(ROOT/'data/raw/milsim/milsim_raw.jsonl','milsim_training.jsonl'),(ROOT/'data/raw/military/military_raw.jsonl','military_training.jsonl')]
    for src,outname in files:
        if not src.exists(): print(f"⏭ {src} fehlt"); continue
        rows=[]
        for line in src.read_text(encoding='utf-8').splitlines():
            if not line.strip(): continue
            try: x=json.loads(line)
            except json.JSONDecodeError: continue
            text=(x.get('text') or '').strip(); md=x.get('metadata') or {}
            domain=md.get('domain','military.general')
            if len(text)<300: continue
            prompt=PROMPTS.get(domain, PROMPTS['military.general'])
            title=x.get('title') or domain
            questions=[f"Erkläre den folgenden dokumentierten Inhalt zum Thema {title}:", f"Welche fachlich belastbaren Informationen enthält diese Quelle zu {title}?"]
            q=random.choice(questions)
            rows.append({'id':stable_id(md.get('source',''),x.get('url',''),text),'messages':[{'role':'system','content':prompt},{'role':'user','content':q},{'role':'assistant','content':text}], 'metadata':{**md,'url':x.get('url'),'title':title,'source_kind':'web_collector'}})
        write_jsonl(ROOT/'data/raw'/('arma3' if 'arma3' in outname else 'milsim' if 'milsim' in outname else 'military')/outname, rows)
        print(f"{outname}: {len(rows)} Beispiele")
if __name__=='__main__': main()
