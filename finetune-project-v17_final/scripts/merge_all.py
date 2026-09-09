#!/usr/bin/env python3
"""Kanonischer Dataset-Merger mit robuster Domain-Balance und Legacy-Import."""
from __future__ import annotations
import argparse, hashlib, json, random, re
from collections import Counter, defaultdict
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parent.parent
RAW_DIRS=[ROOT/f'data/raw/{x}' for x in ['cannabis','law','gardening','science','arma3','military','milsim','supplemental']]
PROCESSED=ROOT/'data/processed'; LEGACY=ROOT/'data/legacy'
SCIENCE_ALIASES={'ai_ml','physics','climate','neuroscience','medicine','statistics','chemistry','biology'}
SIGNALS={
 'philosophie_ethik':['philosophie und ethik','philosophie/ethik','philosophie/ethik'], 'recht_de_eu':['deutsches und europäisches recht','de/eu-recht'],
 'programmieren':['senior software engineer'], 'wissenschaft':['wissenschaftler mit breitem fachwissen'], 'gaertnern':['gärtnermeister','permakultur-experte'],
 'cannabis_zucht_sommelier':['cannabis-zucht-experte'], 'lifehacks_alltag':['praktischer lebensberater'], 'infosicherheit':['informationssicherheit'],
 'arma3':['arma-3-experte','arma 3'], 'military':['militärwissenschaftlicher assistent','öffentlich zugängliche britische landstreitkräfte','öffentlichen zugänglichen us-army'],
 'milsim':['arma-3-milsim-experte'], 'general':['allwissender assistent']}

def domain(ex):
 md=ex.get('metadata') or {}; d=md.get('domain')
 if d:
  if d in SCIENCE_ALIASES or d=='science': return 'wissenschaft'
  if d in {'programming','programming_general'}: return 'programmieren'
  if d=='philosophy_ethics': return 'philosophie_ethik'
  if d.startswith('military.') or d.startswith('military_'): return 'military'
  if d.startswith('arma3'): return 'arma3'
  if d=='milsim': return 'milsim'
  return d
 for m in ex.get('messages',[]):
  if m.get('role')=='system':
   s=m.get('content','').lower()
   if 'milsim' in s: return 'milsim'
   for d,ss in SIGNALS.items():
    if any(x in s for x in ss): return d
 return 'general'

def fingerprint(ex):
 text='\n'.join(m.get('content','') for m in ex.get('messages',[]) if m.get('role')!='system').strip().lower()
 return hashlib.sha256(' '.join(text.split()).encode()).hexdigest()

def is_garbage(ex):
 # Entfernt offensichtlich beschädigte/enkodierte Altbeispiele, nicht normalen Code.
 for m in ex.get('messages',[]):
  s=m.get('content','') or ''
  for tok in s.split():
   if len(tok)>=500:
    ratio=sum(c.isalnum() or c in '+/=' for c in tok)/len(tok)
    if ratio>.97 and not any(ch in tok for ch in '.:,;()[]{}<>#\\"\'` '): return True
 return False

def load(path):
 out=[]
 if not path.exists(): return out
 for line in path.read_text(encoding='utf8',errors='ignore').splitlines():
  if not line.strip(): continue
  try:
   x=json.loads(line)
   if isinstance(x.get('messages'),list) and any(m.get('role')=='assistant' for m in x['messages']) and not is_garbage(x): out.append(x)
  except Exception: pass
 return out

def stratified_split(items,val_fraction,seed):
 rng=random.Random(seed); groups=defaultdict(list)
 for x in items: groups[domain(x)].append(x)
 train=[]; val=[]
 for d,g in groups.items():
  rng.shuffle(g); n=max(1,round(len(g)*val_fraction)) if len(g)>1 else 0
  val.extend(g[:n]); train.extend(g[n:])
 rng.shuffle(train); rng.shuffle(val); return train,val

def balance(items,target_per_domain,max_factor,seed):
 rng=random.Random(seed); groups=defaultdict(list)
 for x in items: groups[domain(x)].append(x)
 out=[]; stats={}
 for d,g in groups.items():
  if not g: continue
  target=min(target_per_domain, len(g)*max_factor)
  if len(g)>target:
   chosen=rng.sample(g,target)
  else:
   chosen=list(g)
   while len(chosen)<target: chosen.append(rng.choice(g).copy())
  out.extend(chosen); stats[d]=len(chosen)
 rng.shuffle(out); return out,stats

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--val-split',type=float,default=.02); ap.add_argument('--target-per-domain',type=int,default=None); ap.add_argument('--max-oversample-factor',type=int,default=None); ap.add_argument('--seed',type=int,default=42); args=ap.parse_args()
 cfg=yaml.safe_load((ROOT/'config/domain_balance.yaml').read_text(encoding='utf8')) if (ROOT/'config/domain_balance.yaml').exists() else {}
 target=args.target_per_domain if args.target_per_domain is not None else int(cfg.get('target_per_domain',800)); maxfactor=args.max_oversample_factor if args.max_oversample_factor is not None else int(cfg.get('max_oversample_factor',4))
 allx=[]
 # Bereits erzeugte finale Daten werden nicht rekursiv eingelesen. Stattdessen wird beim ersten
 # Upgrade ein Snapshot unter data/legacy abgelegt und von dort stabil importiert.
 for f in sorted(LEGACY.glob('*.jsonl')): allx.extend(load(f))
 for d in RAW_DIRS:
  for f in sorted(d.glob('*_training.jsonl')): allx.extend(load(f))
 if PROCESSED.exists():
  for f in sorted(PROCESSED.glob('*.jsonl')): allx.extend(load(f))
 dedup={fingerprint(x):x for x in allx}; allx=list(dedup.values())
 print(f'Vorbereitung: {len(allx)} eindeutige Beispiele')
 tr,val=stratified_split(allx,args.val_split,args.seed)
 print('Train vor Balance:',Counter(domain(x) for x in tr))
 tr,stats=balance(tr,target,maxfactor,args.seed)
 print('Train nach Balance:',stats)
 print('Val:',Counter(domain(x) for x in val))
 for path,data in [(ROOT/'data/train.jsonl',tr),(ROOT/'data/val.jsonl',val)]:
  path.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in data),encoding='utf8'); print(path,len(data))
if __name__=='__main__': main()
