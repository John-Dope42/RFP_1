#!/usr/bin/env python3
"""Concurrent source-health check for the catalog.

The checker distinguishes between a dead URL (404), a reachable endpoint that
rejects automated requests (401/403/429), a bad request (400), server errors,
and DNS/network failures.  This prevents normal bot protection from being
mistaken for an unavailable source.
"""
from __future__ import annotations
import argparse, json, socket, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse
import requests, yaml

ROOT=Path(__file__).resolve().parent.parent
UA="FineTuneKnowledgeCollector/16.0 source-health-check"
HEADERS={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) FineTuneKnowledgeCollector/16.0","Accept":"text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.5","Accept-Language":"de,en;q=0.8"}
# Manche institutionellen Seiten (WAF/Bot-Management) lehnen unseren Custom-Tool-
# Header ab, aber melden das als 404 statt ehrlich als 403 - Prüfung mit einem
# reinen Standard-Browser-Header (kein Tool-Identifier) zeigt, ob DAS die
# Ursache ist. Das ist keine Umgehung von Zugriffsschutz (keine JS-Ausführung,
# keine Session-/Cookie-Tricks, kein IP-Rotieren) - nur eine zweite, ebenso
# ehrliche Anfrage zur Ursachenklärung, transparent im Report vermerkt.
PLAIN_BROWSER_HEADERS={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36","Accept":"text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.5","Accept-Language":"de,en;q=0.8"}
BAD_HOSTS={"example.invalid","example.com"}


def _get(url, headers, timeout):
    return requests.get(url, headers=headers, timeout=(5, timeout), allow_redirects=True, stream=True)


def check(item, timeout):
    domain,src=item; url=src.get('url','')
    result={"domain":domain,"id":src.get('id'),"name":src.get('name'),"url":url,"status":"error"}
    try:
        p=urlparse(url)
        if p.scheme not in ('http','https') or not p.hostname or p.hostname.lower() in BAD_HOSTS:
            result.update(status='invalid',error='invalid/placeholder URL'); return result
        # Do not pre-fail on DNS: requests has better IPv4/IPv6/proxy handling.
        try:
            r=_get(url, HEADERS, timeout)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            # BUGFIX: Transiente Netzwerk-/Timeout-Fehler (z.B. ein einzelner
            # langsamer Request bei einer an sich erreichbaren Regierungsseite
            # wie noaa.gov) wurden bisher ohne erneuten Versuch als endgültig
            # tot gemeldet. Ein Retry mit kurzer Pause fängt solche Ausreißer ab.
            time.sleep(1.5)
            r=_get(url, HEADERS, timeout)
        code=r.status_code; result.update(http_status=code,final_url=r.url,content_type=r.headers.get('content-type',''))
        if 200 <= code < 400:
            result['status']='ok'
        elif code in (401,403,405,406,407,408,409,429):
            result['status']='reachable_restricted'; result['error']=f'HTTP {code} (endpoint reachable; automated request restricted)'
        elif code == 400:
            result['status']='reachable_bad_request'; result['error']='HTTP 400 (endpoint reachable; server rejected this request)'
        elif code == 404:
            # BUGFIX: Manche WAFs (z.B. bei rhs.org.uk, zms.bundeswehr.de -
            # beide nachweislich live) antworten auf unseren Tool-Header mit
            # einem irreführenden 404 statt einem ehrlichen 403. Ein zweiter
            # Versuch mit rein standardmäßigem Browser-Header (kein
            # Tool-Identifier) klärt, ob das die Ursache ist - ohne
            # JS-Rendering, Session-Tricks o.ä.
            r.close()
            try:
                r2 = _get(url, PLAIN_BROWSER_HEADERS, timeout)
                if 200 <= r2.status_code < 400:
                    result.update(http_status=r2.status_code, final_url=r2.url)
                    result['status'] = 'reachable_ua_sensitive'
                    result['error'] = ('HTTP 404 nur mit Tool-Header, HTTP '
                                       f'{r2.status_code} mit Standard-Browser-Header - '
                                       'Quelle vermutlich live, aber WAF-empfindlich')
                    r2.close()
                    return result
                r2.close()
            except requests.RequestException:
                pass
            result['status']='not_found'; result['error']='HTTP 404 (auch mit Standard-Browser-Header)'
        elif 400 <= code < 500:
            result['status']='reachable_client_error'; result['error']=f'HTTP {code}'
        else:
            result['status']='server_error'; result['error']=f'HTTP {code}'
        r.close()
    except requests.exceptions.ConnectionError as e:
        result.update(status='network_error',error=str(e))
    except requests.exceptions.Timeout as e:
        result.update(status='timeout',error=str(e))
    except requests.RequestException as e:
        result.update(status='request_error',error=str(e))
    except Exception as e:
        result.update(status='error',error=repr(e))
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--config',default=str(ROOT/'config/source_catalog.yaml'))
    ap.add_argument('--workers',type=int,default=12)
    ap.add_argument('--timeout',type=int,default=10)
    ap.add_argument('--output',default=str(ROOT/'data/reports/source_health.json'))
    ap.add_argument('--domains',default='')
    ap.add_argument('--strict',action='store_true',help='Treat restricted/bad-request endpoints as warnings in the console.')
    args=ap.parse_args()
    cfg=yaml.safe_load(Path(args.config).read_text(encoding='utf8')) or {}
    wanted={x.strip() for x in args.domains.split(',') if x.strip()}
    items=[(d,s) for d,arr in cfg.items() if not wanted or d in wanted for s in arr]
    print(f'Prüfe {len(items)} Quellen mit {args.workers} Threads ...',flush=True)
    results=[]
    with ThreadPoolExecutor(max_workers=max(1,args.workers)) as ex:
        futs=[ex.submit(check,it,args.timeout) for it in items]
        for i,f in enumerate(as_completed(futs),1):
            x=f.result(); results.append(x); st=x['status']
            mark={'ok':'OK','reachable_restricted':'INFO','reachable_bad_request':'INFO','reachable_client_error':'INFO','reachable_ua_sensitive':'INFO','not_found':'FAIL','server_error':'FAIL','network_error':'FAIL','timeout':'FAIL','request_error':'FAIL','error':'FAIL','invalid':'FAIL'}.get(st,'FAIL')
            print(f'[{mark}] {i}/{len(items)} {x["domain"]}/{x["id"]}: {st} {x.get("http_status","")}',flush=True)
    results.sort(key=lambda x:(x['domain'],x['id'] or ''))
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({"checked_at":time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),"results":results},ensure_ascii=False,indent=2),encoding='utf8')
    counts={}
    for x in results: counts[x['status']]=counts.get(x['status'],0)+1
    usable=sum(counts.get(k,0) for k in ('ok','reachable_restricted','reachable_bad_request','reachable_client_error','reachable_ua_sensitive'))
    print('\nSource health summary:')
    print(f'  OK: {counts.get("ok",0)}')
    print(f'  erreichbar, aber eingeschränkt: {counts.get("reachable_restricted",0)+counts.get("reachable_bad_request",0)+counts.get("reachable_client_error",0)}')
    print(f'  erreichbar, aber 404 nur mit Tool-Header (vermutlich WAF, siehe error-Feld): {counts.get("reachable_ua_sensitive",0)}')
    print(f'  404 (auch mit Standard-Browser-Header): {counts.get("not_found",0)}')
    print(f'  Netzwerk/DNS/Timeout (nach 1 Retry): {counts.get("network_error",0)+counts.get("timeout",0)+counts.get("request_error",0)}')
    print(f'  Gesamt nutzbar/erreichbar: {usable}/{len(results)}')
    print(f'Bericht: {out}')
    return 0 if args.strict is False or all(x['status'] in ('ok','reachable_restricted','reachable_bad_request','reachable_client_error','reachable_ua_sensitive') for x in results) else 1

if __name__=='__main__': raise SystemExit(main())
