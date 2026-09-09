#!/usr/bin/env python3
"""End-to-end collector runner: core data -> source health -> supplemental -> RAG -> QLoRA -> audit."""
from __future__ import annotations
import argparse,os,subprocess,sys,time
from pathlib import Path
if sys.platform=='win32':
    for s in (sys.stdout,sys.stderr):
        try:s.reconfigure(encoding='utf-8',errors='replace')
        except:pass
ROOT=Path(__file__).resolve().parent.parent; SCRIPTS=ROOT/'scripts'

def run(script,desc,args=None,timeout=900,allow_fail=False):
    print('\n'+'='*70+'\n🚀 '+desc+'\n'+'='*70,flush=True)
    env=os.environ.copy(); env['PYTHONIOENCODING']='utf-8'; env['PYTHONUNBUFFERED']='1'
    cmd=[sys.executable,'-u',str(SCRIPTS/script)]+(args or []); start=time.time()
    try:
        p=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace',bufsize=1)
        while True:
            line=p.stdout.readline()
            if line: print(line.rstrip(),flush=True)
            elif p.poll() is not None: break
            if time.time()-start>timeout:
                p.kill(); print(f'⏱ TIMEOUT {timeout}s: {desc}',flush=True); return allow_fail
        rc=p.wait(); ok=rc==0
        print(('✅ ' if ok else '❌ ')+f'{desc} (Exit {rc})',flush=True)
        return ok or allow_fail
    except Exception as e:
        print(f'❌ {desc}: {e}',flush=True); return allow_fail

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--own-data-dir'); ap.add_argument('--skip-own-data',action='store_true'); ap.add_argument('--skip-collectors',action='store_true'); ap.add_argument('--skip-supplemental',action='store_true'); ap.add_argument('--skip-source-health',action='store_true'); ap.add_argument('--source-health-workers',type=int,default=12); ap.add_argument('--source-health-timeout',type=int,default=8); ap.add_argument('--supplemental-pages',type=int,default=25); ap.add_argument('--supplemental-deep',action='store_true'); ap.add_argument('--collector-timeout',type=int,default=900); ap.add_argument('--rag',action='store_true'); args=ap.parse_args()
    ok=True; print(f'🎯 MASTER v16 | {ROOT}',flush=True)
    if not args.skip_own_data:
        own=Path(args.own_data_dir).expanduser() if args.own_data_dir else ROOT/'data/own_data'
        if own.exists(): ok &= run('prepare_data.py','Eigene Daten konvertieren',['--input-dir',str(own),'--output-dir',str(ROOT/'data/processed'),'--max-chars','3000','--val-split','0.02'],args.collector_timeout)
        else: print(f'⚠️ Eigene Daten fehlen: {own}',flush=True)
    if not args.skip_collectors:
        collectors=[('collect_core.py','Core-Recovery'),('collect_lifehacks.py','Lifehacks/Alltag'),('collect_cannabis.py','Cannabis'),('collect_law.py','Deutsches & EU-Recht'),('collect_gardening.py','Gärtnern'),('collect_science.py','Wissenschaft'),('collect_academic.py','Akademische Quellen'),('collect_arma3.py','Arma 3'),('collect_military.py','Militärwissen'),('collect_milsim.py','Milsim')]
        for fn,desc in collectors:
            if not (SCRIPTS/fn).exists(): print(f'⚠️ {fn} fehlt - übersprungen',flush=True); continue
            extra=[]
            if fn=='collect_arma3.py':extra=['--max-pages','80']
            elif fn=='collect_military.py':extra=['--max-pages','60']
            elif fn=='collect_milsim.py':extra=['--max-pages','50']
            ok &= run(fn,desc,extra,args.collector_timeout)
    if not args.skip_source_health:
        ok &= run('source_health.py','Source Health Check',['--workers',str(args.source_health_workers),'--timeout',str(args.source_health_timeout)],max(300,args.collector_timeout),allow_fail=True)
    if not args.skip_supplemental:
        pages=max(args.supplemental_pages,50) if args.supplemental_deep else args.supplemental_pages
        ok &= run('collect_supplemental.py',f'Supplemental-Quellen ({pages} Seiten/Quelle)',['--max-pages-per-source',str(pages)],max(1800,args.collector_timeout*2),allow_fail=True)
        ok &= run('prepare_supplemental.py','Supplemental QLoRA-Aufbereitung',['--multiplier','3'],600)
    if not run('prepare_collected.py','Collector-Rohdaten vorbereiten',timeout=600): ok=False
    if not run('build_rag_corpus.py','RAG-Korpus bauen',timeout=600): ok=False
    if args.rag:
        if not run('ingest_rag.py','RAG-Vektorindex erstellen',['--rebuild'],timeout=1800): ok=False
    if not run('merge_all.py','QLoRA Merge/Dedup/Split/Balance',timeout=600): ok=False
    if not run('audit_dataset.py','Finaler Dataset-Audit',timeout=600): ok=False
    print('\n'+'='*70); print('✅ MASTER v16 ABGESCHLOSSEN' if ok else '⚠️ MASTER v16 mit Fehlern beendet'); print('='*70,flush=True)
    return 0 if ok else 2
if __name__=='__main__':raise SystemExit(main())
