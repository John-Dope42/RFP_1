#!/usr/bin/env python3
"""Prepare grounded QLoRA examples from supplemental chunks.

Generates several question formulations per source chunk, while keeping the
assistant answer exactly grounded in the collected source text. RAG retains the
original chunks separately. The default multiplier is 3 and can be lowered.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from collector_utils import stable_id,write_jsonl
ROOT=Path(__file__).resolve().parent.parent
PROMPTS={
'programming':'Du bist ein Senior Software Engineer. Erkläre dokumentierte Softwaretechnik präzise und versionsbewusst. Behaupte keine API oder Semantik, die nicht aus der Quelle hervorgeht.',
'science':'Du bist ein wissenschaftlicher Assistent. Trenne Befund, Interpretation und Unsicherheit und bewahre den Quellenkontext.',
'philosophy_ethics':'Du bist ein Philosophie- und Ethik-Assistent. Stelle Positionen fair dar und unterscheide Primärtext, Interpretation und Einwand.',
'gaertnern':'Du bist ein Gartenbau- und Botanik-Assistent. Erkläre fachlich und standortbewusst und unterscheide Forschung von Praxisempfehlungen.',
'cannabis_zucht_sommelier':'Du bist ein wissenschaftlich orientierter Cannabis-Assistent. Trenne Botanik, Chemie, Medizin und Rechtslage und bleibe quellengebunden.',
'recht_de_eu':'Du bist ein Assistent für deutsches und europäisches Recht. Unterscheide geltendes Recht, historische Fassungen und Rechtsprechung und nenne den Quellenkontext.',
'arma3_technical':'Du bist ein Arma-3-Technikassistent. Trenne Engine/API, Mod-Code und Community-Praxis und beachte Versionsabhängigkeiten.',
'military_general':'Du bist ein Assistent für öffentlich dokumentierte Militärwissenschaft und Doktrin. Unterscheide Nation, Ebene, Epoche und Quellenstatus.',
'milsim':'Du bist ein Arma-3-Milsim-Assistent. Unterscheide Spielmechanik, Community-Praxis und reale Militärdoktrin.'}

def questions(d,title):
    base={
    'programming':[f'Erkläre die dokumentierte technische Information aus „{title}“.',f'Welche Regeln, APIs oder technischen Zusammenhänge beschreibt „{title}“?',f'Welche wichtigen Punkte sollte ein Entwickler aus „{title}“ kennen?'],
    'science':[f'Welche wissenschaftlichen Aussagen enthält „{title}“?',f'Fasse die zentralen Befunde aus „{title}“ quellengetreu zusammen.',f'Welche Einschränkungen oder Unsicherheiten ergeben sich aus „{title}“?'],
    'philosophy_ethics':[f'Welche philosophische Position oder Argumentation wird in „{title}“ dargestellt?',f'Erkläre die zentralen Begriffe und Argumente aus „{title}“.',f'Welche Einwände oder Gegenpositionen sind im dokumentierten Material relevant?'],
    'gaertnern':[f'Welche gartenbaulichen Erkenntnisse enthält „{title}“?',f'Welche Faktoren und Empfehlungen werden in „{title}“ beschrieben?',f'Was sollte man aus „{title}“ bei der praktischen Anwendung beachten?'],
    'cannabis_zucht_sommelier':[f'Welche fachlichen Informationen zu Cannabis enthält „{title}“?',f'Welche botanischen, chemischen oder medizinischen Zusammenhänge beschreibt „{title}“?',f'Welche Aussagen sind in „{title}“ belegt und welche Grenzen nennt die Quelle?'],
    'recht_de_eu':[f'Was regelt der dokumentierte Inhalt aus „{title}“?',f'Welche Voraussetzungen, Rechtsfolgen oder Begriffe werden in „{title}“ genannt?',f'Welche zeitliche oder rechtliche Einordnung ist bei „{title}“ zu beachten?'],
    'arma3_technical':[f'Wie funktioniert der dokumentierte Arma-3-Inhalt aus „{title}“?',f'Welche Funktionen, Parameter oder Konfigurationen beschreibt „{title}“?',f'Welche versions- oder modabhängigen Punkte nennt „{title}“?'],
    'military_general':[f'Welche militärwissenschaftlichen oder doktrinären Konzepte beschreibt „{title}“?',f'Wie ist der dokumentierte Inhalt aus „{title}“ einzuordnen?',f'Welche Begriffe und Grundsätze werden in „{title}“ erklärt?'],
    'milsim':[f'Welche Arma-3-Milsim-Praxis wird in „{title}“ beschrieben?',f'Welche spielbezogenen Verfahren oder Begriffe erklärt „{title}“?',f'Was davon gehört zur Simulation und was ist laut Quelle reale Doktrin?']}
    return base.get(d,[f'Erkläre den dokumentierten Inhalt aus „{title}“.'])

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--input',default=str(ROOT/'data/raw/supplemental/supplemental_raw.jsonl')); ap.add_argument('--output',default=str(ROOT/'data/raw/supplemental/supplemental_training.jsonl')); ap.add_argument('--multiplier',type=int,default=3); args=ap.parse_args()
    inp=Path(args.input)
    if not inp.exists(): print(f'⏭ {inp} fehlt'); return 0
    rows=[]; seen=set()
    for line in inp.read_text(encoding='utf8').splitlines():
        try:x=json.loads(line)
        except:continue
        text=(x.get('text') or '').strip(); md=x.get('metadata') or {}; d=md.get('domain','science'); title=x.get('title') or md.get('source_name') or d
        if len(text)<350: continue
        for qi,q in enumerate(questions(d,title)[:max(1,args.multiplier)]):
            fid=stable_id(md.get('source',''),x.get('url',''),text,q)
            if fid in seen: continue
            seen.add(fid)
            rows.append({'id':fid,'messages':[{'role':'system','content':PROMPTS.get(d,PROMPTS['science'])},{'role':'user','content':q},{'role':'assistant','content':text}], 'metadata':{**md,'title':title,'url':x.get('url'),'source_kind':'supplemental_grounded_qa','question_variant':qi}})
    write_jsonl(Path(args.output),rows); print(f'Supplemental QLoRA: {len(rows)} Beispiele -> {args.output}'); return 0
if __name__=='__main__': raise SystemExit(main())
