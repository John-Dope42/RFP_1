#!/usr/bin/env python3
"""Bounded collector for config/source_catalog.yaml.

HTML/PDF sources are crawled only on the same host. GitHub sources use the
public repository tree/API and raw files, never GitHub navigation pages.
A failed source is isolated and does not abort the complete collection.
"""
from __future__ import annotations
import argparse, json, re, sys, time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests, yaml
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parent))
from collector_utils import robots_ok, fetch, html_to_text, pdf_to_text, chunk_text, stable_id, write_jsonl, content_hash

ROOT=Path(__file__).resolve().parent.parent
S=requests.Session(); S.headers.update({"User-Agent":"FineTuneKnowledgeCollector/13.0","Accept-Language":"de,en;q=0.8,fr;q=0.6,pl;q=0.5"})
EXT={'.md','.mdx','.rst','.txt','.py','.js','.ts','.tsx','.jsx','.java','.kt','.go','.rs','.c','.h','.hpp','.cpp','.cc','.cs','.json','.yaml','.yml','.toml','.xml','.html','.htm','.sqf','.sqm','.inc','.cfg','.config','.pdf'}
BAD_TERMS=('classified','restricted','defence-gateway','defencegateway','cac-required','intradef','secret','sensitive','login','signin','sign-in')
BAD_GH=('/.git/','/.github/','/node_modules/','/vendor/','/dist/','/build/','/images/','/assets/','/issues/','/pull/','/pulls/','/commit/','/commits/','/actions/','/security/','/releases/','/tags/','/wiki/')


def allowed(url,host,prefixes=()):
    p=urlparse(url); h=(p.hostname or '').lower(); path=p.path.lower()
    if p.scheme not in ('http','https') or not (h==host or h.endswith('.'+host)): return False
    if any(t in path for t in BAD_TERMS): return False
    return not prefixes or any(path.startswith(x.lower()) for x in prefixes)

def github_parts(url):
    p=urlparse(url); parts=[x for x in p.path.strip('/').split('/') if x]
    return (parts[0],parts[1]) if p.netloc.lower()=='github.com' and len(parts)>=2 else None

def github_tree(owner,repo,cap):
    api=f'https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1'
    try:
        r=S.get(api,timeout=(4,20)); r.raise_for_status(); data=r.json()
    except Exception as e:
        print(f'  ⚠ GitHub tree {owner}/{repo}: {e}',flush=True); return []
    files=[]
    for item in data.get('tree',[]):
        if item.get('type')!='blob': continue
        path=item.get('path',''); low='/'+path.lower(); ext=Path(path).suffix.lower()
        if ext not in EXT or any(x in low for x in BAD_GH): continue
        # Avoid generated/minified assets and huge lockfiles.
        if Path(path).name.lower() in {'package-lock.json','pnpm-lock.yaml','yarn.lock'}: continue
        files.append(item)
    files.sort(key=lambda x:(0 if Path(x['path']).suffix.lower() in {'.md','.mdx','.rst','.sqf','.hpp','.cpp','.py'} else 1,x['path']))
    return files[:cap]

def make_row(src,url,i,text,title,kind,extra=None):
    md={"domain":src['domain'],"subdomain":src.get('subdomain'),"source":src['id'],"source_name":src.get('name',''),"authority":src.get('authority',''),"country":src.get('country'),"language":src.get('language','en'),"source_type":src.get('source_type',src.get('authority','')),"document_type":src.get('document_type'),"use_for":src.get('use_for','both'),"source_kind":kind,"retrieved_at":time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),"url":url,"content_hash":content_hash(text),"chunk_id":str(i)}
    if extra: md.update({k:v for k,v in extra.items() if v is not None})
    return {"id":stable_id(src['id'],url,str(i),text[:300]),"text":text,"title":title,"url":url,"metadata":md}

def github_collect(src,out,global_cap):
    parts=github_parts(src['url']);
    if not parts: return 0
    owner,repo=parts; cap=min(global_cap,int(src.get('max_pages',global_cap))); files=github_tree(owner,repo,cap); count=0
    for i,item in enumerate(files,1):
        path=item['path']; raw=f'https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{path}'
        print(f'  📦 [{src["id"]}] {i}/{len(files)} {path}',flush=True)
        try:
            r=S.get(raw,timeout=(4,int(src.get('read_timeout',20))),allow_redirects=True); r.raise_for_status(); data=r.content
        except Exception as e: print(f'     ⚠ {e}',flush=True); continue
        if len(data)>2_000_000: continue
        if Path(path).suffix.lower()=='.pdf': title,text=pdf_to_text(data)
        else: title=Path(path).name; text=data.decode('utf-8','replace')
        if len(text)<250: continue
        for j,ch in enumerate(chunk_text(text,4500,350)):
            out.append(make_row(src,raw,j,ch,title,'github',{'repository':f'{owner}/{repo}','path':path}))
            count+=1
        time.sleep(float(src.get('delay',.12)))
    return count

def crawl_collect(src,out,global_cap,delay,robots):
    seed=src['url']; p=urlparse(seed); host=(p.hostname or '').lower(); cap=min(global_cap,int(src.get('max_pages',global_cap))); prefixes=tuple(src.get('path_prefixes',[]) or [])
    q=deque([seed]); seen=set(); pages=0; count=0
    while q and pages<cap:
        url=q.popleft().split('#',1)[0]
        if url in seen or not allowed(url,host,prefixes): continue
        if not robots_ok(url,robots): continue
        seen.add(url); pages+=1; print(f'  🌐 [{src["id"]}] {pages}/{cap}: {url}',flush=True)
        try: r=fetch(url,timeout=(4,int(src.get('read_timeout',15))),retries=1)
        except Exception as e: print(f'     ⚠ {e}',flush=True); continue
        ct=r.headers.get('content-type','').lower(); final=r.url
        if 'pdf' in ct or final.lower().endswith('.pdf'):
            title,text=pdf_to_text(r.content); links=[]
        elif 'html' in ct or 'text' in ct:
            title,text=html_to_text(r.content); links=[]
            try:
                soup=BeautifulSoup(r.content,'html.parser')
                for a in soup.find_all('a',href=True):
                    u=urljoin(final,a['href']).split('#',1)[0]
                    if not allowed(u,host,prefixes): continue
                    path=urlparse(u).path.lower(); ext=Path(path).suffix
                    if ext in {'.pdf','.html','.htm',''}: q.append(u)
            except Exception: pass
        else: continue
        if len(text)>=350:
            for i,ch in enumerate(chunk_text(text,4500,350)):
                out.append(make_row(src,final,i,ch,title,'pdf' if 'pdf' in ct else 'html')); count+=1
        time.sleep(delay)
    return count

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--config',default=str(ROOT/'config/source_catalog.yaml')); ap.add_argument('--output',default=str(ROOT/'data/raw/supplemental/supplemental_raw.jsonl')); ap.add_argument('--max-pages-per-source',type=int,default=25); ap.add_argument('--delay',type=float,default=.25); ap.add_argument('--domains',default=''); ap.add_argument('--only',default=''); a=ap.parse_args()
    cfg=yaml.safe_load(Path(a.config).read_text(encoding='utf8')) or {}; wanted={x.strip() for x in a.domains.split(',') if x.strip()}; only={x.strip() for x in a.only.split(',') if x.strip()}
    selected=[(d,s) for d,arr in cfg.items() if not wanted or d in wanted for s in arr if not only or s.get('id') in only]
    rows=[]; robots={}; stats={}
    for domain,src0 in selected:
        src=dict(src0); src['domain']=domain; print(f'\n=== {domain}: {src.get("name",src.get("id"))} ===',flush=True); before=len(rows)
        try:
            if src.get('mode')=='github': github_collect(src,rows,a.max_pages_per_source)
            else: crawl_collect(src,rows,a.max_pages_per_source,a.delay,robots)
        except Exception as e: print(f'  ❌ Quelle isoliert fehlgeschlagen: {e}',flush=True)
        stats[src['id']]=len(rows)-before
    uniq={stable_id(x['metadata'].get('source',''),x.get('url',''),x['text']):x for x in rows}
    write_jsonl(Path(a.output),uniq.values())
    report=ROOT/'data/reports/supplemental_summary.json'; report.parent.mkdir(parents=True,exist_ok=True); report.write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf8')
    print(f'\n=== Supplemental Summary ===\nUnique Chunks: {len(uniq)}\nReport: {report}',flush=True)
    return 0
if __name__=='__main__': raise SystemExit(main())
