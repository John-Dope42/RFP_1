#!/usr/bin/env python3
"""Validate source catalog coverage before a long crawl."""
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parent.parent
cfg=yaml.safe_load((ROOT/'config/source_catalog.yaml').read_text(encoding='utf8')) or {}
failed=False
for domain,items in cfg.items():
    if len(items)<10:
        print(f'FAIL {domain}: only {len(items)} sources'); failed=True
    ids=[x.get('id') for x in items]
    if len(ids)!=len(set(ids)):
        print(f'FAIL {domain}: duplicate ids'); failed=True
    for x in items:
        if not x.get('url') or not x.get('mode'):
            print(f"FAIL {domain}: incomplete {x}"); failed=True
    print(f'OK   {domain}: {len(items)} sources')
print('SOURCE CATALOG OK' if not failed else 'SOURCE CATALOG INVALID')
raise SystemExit(1 if failed else 0)
