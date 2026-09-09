#!/usr/bin/env python3
"""Komfortabler Einstieg für einen separaten Domain-Adapter.

Beispiel:
  python scripts/train_domain.py --domain arma3
  python scripts/train_domain.py --domain military
Der eigentliche Trainer bleibt zentral in train_custom.py, damit Bugfixes nicht
zwischen mehreren Trainern auseinanderlaufen.
"""
from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--domain',required=True); ap.add_argument('--debug',action='store_true'); ap.add_argument('--resume',action='store_true'); a=ap.parse_args()
 cmd=[sys.executable,str(ROOT/'scripts/train_custom.py'),'--domain',a.domain]
 if a.debug: cmd.append('--debug')
 if a.resume: cmd.append('--resume')
 raise SystemExit(subprocess.call(cmd,cwd=ROOT))
if __name__=='__main__': main()
