#!/usr/bin/env python3
"""Offline regression tests for the collection/RAG pipeline."""
from __future__ import annotations
import json, tempfile, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from collect_law import parse_law_html
from collector_utils import chunk_text,stable_id,build_metadata

def main():
    html='''<html><body><div class="jurNorm"><h4>§ 1 Anwendungsbereich</h4><div class="jurAbsatz">Ein ausreichend langer Testabsatz beschreibt den Anwendungsbereich des Gesetzes und enthält mehrere fachliche Sätze, damit der Parser einen echten Abschnitt erkennt.</div></div><div class="jurNorm"><h4>§ 2 Begriffsbestimmungen</h4><div class="jurAbsatz">Ein zweiter ausreichend langer Testabsatz beschreibt Begriffe und Voraussetzungen mit genügend Inhalt für die Regression.</div></div></body></html>'''
    r=parse_law_html(html,'test','Testgesetz'); assert len(r['sections'])==2
    parts=chunk_text('A'*1200,max_chars=500,overlap=50); assert len(parts)>=2
    md=build_metadata(domain='test',url='https://example.invalid',chunk_id='1',content_hash='x'); assert md['domain']=='test' and 'version' in md
    print('SELF TEST OK: law parser, chunking, metadata')
if __name__=='__main__': main()
