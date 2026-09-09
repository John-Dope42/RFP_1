#!/usr/bin/env python3
"""Reproduzierbarer Daten-Audit: Schema, Duplikate, Domains, Train/Val-Leakage."""
from __future__ import annotations
import hashlib,json,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
SCIENCE_ALIASES={'ai_ml','physics','climate','neuroscience','medicine','statistics','chemistry','biology'}
# BUGFIX: Verschiedene Collector-Generationen taggen dieselbe Domain mit
# unterschiedlichen metadata['domain']-Werten (deutsche Kurzform vs. englischer
# Katalog-Key aus config/source_catalog.yaml). Ohne diese Alias-Tabelle wurden
# identische Inhalte im Audit als ZWEI separate Domains gezählt
# (z.B. "programming": 4340 UND "programmieren": 2201 - derselbe Themenbereich,
# nur unterschiedlich benannt), was den Report verwirrend/falsch macht und
# potenziell das Domain-Balancing in merge_all.py unterläuft, falls dessen
# eigene Kanonisierung abweicht. Kanonische Zielnamen entsprechen den
# System-Prompts der ÄLTEREN, deutschen Collectoren (programmieren,
# wissenschaft, philosophie_ethik, military), da diese zuerst existierten.
DOMAIN_ALIASES = {
    'programming': 'programmieren',
    'science': 'wissenschaft',
    'philosophy_ethics': 'philosophie_ethik',
    'military_general': 'military',
}
SIGNALS={
 'philosophie_ethik':['philosophie und ethik','philosophie/ethik'], 'recht_de_eu':['deutsches und europäisches recht','de/eu-recht'],
 'programmieren':['senior software engineer'], 'wissenschaft':['wissenschaftler mit breitem fachwissen'], 'gaertnern':['gärtnermeister','permakultur-experte'],
 'cannabis_zucht_sommelier':['cannabis-zucht-experte'], 'lifehacks_alltag':['praktischer lebensberater'], 'infosicherheit':['informationssicherheit'],
 'arma3':['arma-3-experte','arma 3'], 'military':['militärwissenschaftlicher assistent','military.'], 'milsim':['arma-3-milsim-experte'], 'general':['allwissender assistent']}
# BUGFIX (Regression ggü. v10): Diese v14-Version hatte den
# Domain-Vollständigkeits-Check verloren (nur noch Schema/Leakage geprüft).
# Dadurch lief "AUDIT OK" durch, obwohl arma3/military/milsim mit 0 Beispielen
# komplett fehlten - genau die drei Domains, für die extra eine
# Collector-Pipeline gebaut wurde. CORE_DOMAINS listet, was mindestens
# MIN_PER_CORE_DOMAIN Trainingsbeispiele haben MUSS, sonst schlägt der Audit
# fehl. Passe die Liste an, falls eine Domain bewusst (noch) nicht gesammelt
# werden soll (z.B. --domains-Filter bei run_all_collectors.py genutzt).
CORE_DOMAINS = [
    'programmieren', 'philosophie_ethik', 'wissenschaft', 'gaertnern',
    'recht_de_eu', 'cannabis_zucht_sommelier', 'arma3', 'military', 'milsim',
]
MIN_PER_CORE_DOMAIN = 20
def load(p):
 out=[]
 if not p.exists(): return out
 for line in p.read_text(encoding='utf-8').splitlines():
  if line.strip(): out.append(json.loads(line))
 return out
def fp(x):
 a='\n'.join(m.get('content','') for m in x.get('messages',[]) if m.get('role')!='system')
 return hashlib.sha256(' '.join(a.lower().split()).encode()).hexdigest()
def dom(x):
 d=(x.get('metadata') or {}).get('domain')
 if d:
  if d in SCIENCE_ALIASES: return 'wissenschaft'
  if d in DOMAIN_ALIASES: return DOMAIN_ALIASES[d]
  if d.startswith('military'): return 'military'
  if d.startswith('arma3'): return 'arma3'
  if d=='milsim': return 'milsim'
  return d
 for m in x.get('messages',[]):
  if m.get('role')=='system':
   text=m.get('content','').lower()
   for name,signals in SIGNALS.items():
    if any(sig in text for sig in signals): return name
 return 'unknown'
def main():
 tr=load(ROOT/'data/train.jsonl'); va=load(ROOT/'data/val.jsonl'); errors=[]
 for name,data in [('train',tr),('val',va)]:
  for i,x in enumerate(data):
   if not isinstance(x.get('messages'),list) or not all(m.get('role') in {'system','user','assistant'} for m in x['messages']): errors.append(f'{name}:{i}: invalid messages')
   if not any(m.get('role')=='assistant' and str(m.get('content','')).strip() for m in x.get('messages',[])): errors.append(f'{name}:{i}: missing assistant')
 tset={fp(x) for x in tr}; vset={fp(x) for x in va}; overlap=tset&vset
 train_counts=Counter(dom(x) for x in tr)
 print('Train:',len(tr),train_counts); print('Val:',len(va),Counter(dom(x) for x in va)); print('Train/Val overlap:',len(overlap)); print('Schema errors:',len(errors))
 missing=[d for d in CORE_DOMAINS if train_counts.get(d,0) < MIN_PER_CORE_DOMAIN]
 if missing: print(f'❌ Fehlende/zu kleine Core-Domains (< {MIN_PER_CORE_DOMAIN} Beispiele): '+', '.join(f'{d} ({train_counts.get(d,0)})' for d in missing))
 if errors: print('\n'.join(errors[:20])); return 1
 if overlap: print('ERROR: Leakage erkannt'); return 2
 if missing: return 3
 print('AUDIT OK'); return 0
if __name__=='__main__': sys.exit(main())
