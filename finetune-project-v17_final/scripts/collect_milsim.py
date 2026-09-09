#!/usr/bin/env python3
"""Sammelt öffentliche Arma-3-Milsim-/Multiplayer-Dokumentation.
Communitywissen wird explizit als community_documentation markiert und nicht
mit offizieller Militärdoktrin gleichgesetzt.
"""
from __future__ import annotations
import sys, argparse
from pathlib import Path
import yaml
sys.path.insert(0,str(Path(__file__).resolve().parent))
from collect_arma3 import collect_group
ROOT=Path(__file__).resolve().parent.parent

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--config",default=str(ROOT/"config/sources.yaml")); ap.add_argument("--delay",type=float,default=0.8); ap.add_argument("--max-pages",type=int,default=120); a=ap.parse_args()
    cfg=yaml.safe_load(Path(a.config).read_text(encoding="utf-8"))
    ok = collect_group(cfg.get("milsim",[]),ROOT/"data/raw/milsim/milsim_raw.jsonl",a.delay,a.max_pages)
    raise SystemExit(0)
if __name__=="__main__": main()
