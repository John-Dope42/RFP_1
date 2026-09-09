#!/usr/bin/env python3
"""
Deutsches & EU-Recht Sammler - Kostenlose, offizielle Quellen
Quellen: gesetze-im-internet.de (Public Domain), EUR-Lex, Bundesgesetzblatt
"""

import json
import requests
import re
import sys
from pathlib import Path
from typing import List, Dict
import time
from bs4 import BeautifulSoup

if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


# ============================================================
# RELEVANTE GESETZE FÜR DEIN PROJEKT (Deutschland + EU)
# ============================================================
# Quelle: https://www.gesetze-im-internet.de/ - alles Public Domain / amtlich
LAWS_DE = {
    # Verfassungsrecht
    "gg": "Grundgesetz (GG)",
    # Zivilrecht
    "bgb": "Bürgerliches Gesetzbuch (BGB)",
    "hgb": "Handelsgesetzbuch (HGB)",
    # Strafrecht
    "stgb": "Strafgesetzbuch (StGB)",
    "stpo": "Strafprozessordnung (StPO)",
    # Verwaltungsrecht
    "vwvfg": "Verwaltungsverfahrensgesetz (VwVfG)",
    "vwgo": "Verwaltungsgerichtsordnung (VwGO)",  # BUGFIX: war "vgo" (falsch), echtes Kürzel ist "vwgo"
    # Datenschutz
    "bdsg_2018": "Bundesdatenschutzgesetz (BDSG)",  # BUGFIX: war "bdsg", echte URL nutzt "bdsg_2018"
    "ttdsg": "Telekommunikation-Telemedien-Datenschutz-Gesetz (TTDSG)",
    # Betäubungsmittel / Cannabis (NEU: KCanG, MedCanG)
    # BUGFIX: "CanG" ist nur der umgangssprachliche Sammelbegriff für das
    # Mantelgesetz - auf gesetze-im-internet.de existiert dafür KEINE eigene
    # Seite/URL. Die beiden tatsächlichen Einzelgesetze (Art. 1 und Art. 2 des
    # Mantelgesetzes) heißen KCanG (Konsumcannabisgesetz) und MedCanG. Der alte
    # Eintrag "cang" zeigte auf eine nicht existierende URL und lieferte daher
    # vermutlich 0 Inhalt zurück - fehlte still, ohne Fehlermeldung.
    "btmg": "Betäubungsmittelgesetz (BtMG) - Alt",
    "kcang": "Konsumcannabisgesetz (KCanG) - Neu 2024",
    "medcang": "Medizinal-Cannabisgesetz (MedCanG) - Neu 2024",
    # Arzneimittel
    "amg_1976": "Arzneimittelgesetz (AMG)",
    "ampreisv": "Arzneimittelpreisverordnung (AMPreisV)",  # BUGFIX: war "ampg" (falsches Kürzel, existiert so nicht), echte URL ist "ampreisv"
    # Apotheken
    "apog": "Apothekengesetz (ApoG)",
    # Pflanzenschutz / Dünger (für Gärtnern)
    "pflschg_2012": "Pflanzenschutzgesetz (PflSchG)",  # BUGFIX: war "pflschg", echte URL nutzt "pflschg_2012"
    "d_ngg": "Düngemittelgesetz (DüngG)",  # BUGFIX: war "duengG", echte URL nutzt "d_ngg" (ü wird als "_" transkribiert, wie bei d_mv/d_v)
    # Arbeitsschutz
    "arbschg": "Arbeitsschutzgesetz (ArbSchG)",
    "biostoffv_2013": "Biostoffverordnung (BioStoffV)",  # BUGFIX: war "biostoffv", echte URL nutzt "biostoffv_2013"
    # Verbraucherschutz
    "buchprg": "Buchpreisbindungsgesetz (BuchPrG)",  # BUGFIX: war "bkartA" - das ist das Kürzel für ein KOMPLETT ANDERES Gesetz (Kartellrecht/GWB), nicht für BuchPrG. Neuer Wert "buchprg" nach demselben Muster wie apog/vwgo, aber nicht einzeln verifiziert
    # Lebensmittel
    "lfgb": "Lebensmittel- und Futtermittelgesetzbuch (LFGB)",  # BUGFIX: war "lfbg" - Buchstabendreher (Tippfehler), richtig ist "lfgb"
}

LAWS_EU = {
    # DSGVO (bereits in deinen Daten)
    "dsgrv": "DSGVO (EU) 2016/679",
    # Richtlinien
    "richtlinie_2001_83": "Richtlinie 2001/83/EG (Humanarzneimittel)",
    "richtlinie_2004_27": "Richtlinie 2004/27/EG (Änderung Arzneimittelrichtlinie)",
    # Verordnungen
    "verordnung_2019_6": "Verordnung (EU) 2019/6 (Tierarzneimittel)",
    # Cannabis-spezifisch EU
    "emcdda_reg": "EMCDDA Verordnung (EU) 2023/1322",
    # Novel Food (CBD)
    "novel_food": "Verordnung (EU) 2015/2283 (Novel Food)",
}


def fetch_law_gesetze_im_internet(law_code: str) -> Dict:
    """Fetch the current consolidated law from gesetze-im-internet.de.

    The site's /<code>/ page is an index. It links to the actual consolidated
    HTML document, whose structure is more reliable for extraction than the
    table-of-contents page. XML is kept as a secondary source when available.

    WICHTIGER HINWEIS (nicht als "Bug" behandeln, nicht versuchen zu umgehen):
    gesetze-im-internet.de sperrt automatisierten Zugriff über robots.txt -
    verifiziert durch einen direkten Abruf-Versuch, der mit "Site disallows
    automated access" abgelehnt wurde. Das erklärt, warum diese Funktion
    inzwischen bei JEDEM Gesetz "0 Abschnitte" liefert, obwohl der Server
    selbst mit HTTP 200 antwortet (kein Parser-Bug, keine falsche
    CSS-Selektor-Wahl - der zurückgegebene HTML-Body enthält schlicht nicht
    mehr den erwarteten Volltext für automatisierte Clients).
    Alternative recht.bund.de ist KEIN Ersatz für diesen Zweck: laut eigener
    FAQ der Seite (https://www.recht.bund.de/de/informationen/faq/faq_node.html)
    ist recht.bund.de nur das chronologische Verkündungsblatt einzelner
    Änderungsgesetze - für die aktuelle KONSOLIDIERTE Fassung eines Gesetzes
    verweist die Seite selbst auf gesetze-im-internet.de zurück.
    Empfohlener Weg für echten §-Text: Gesetzestext-PDFs manuell herunterladen
    (z.B. https://www.gesetze-im-internet.de/bgb/BGB.pdf - manueller Download
    ist durch robots.txt nicht betroffen, das gilt nur für automatisiertes
    Crawlen) und über scripts/prepare_data.py verarbeiten, analog zum bereits
    etablierten Muster für andere blockierte Quellen (siehe README).
    """
    base="https://www.gesetze-im-internet.de"
    name=LAWS_DE.get(law_code,law_code)
    debug=Path("./data/debug"); debug.mkdir(parents=True,exist_ok=True)
    headers={"User-Agent":"FineTuneKnowledgeCollector/13.0","Accept-Language":"de,en;q=0.8"}
    try:
        idx=requests.get(f"{base}/{law_code}/",headers=headers,timeout=(5,25))
        idx.raise_for_status()
        soup=BeautifulSoup(idx.text,'html.parser')
        # Prefer the actual full-text HTML document linked from the index.
        candidates=[]
        for a in soup.find_all('a',href=True):
            href=a['href'].split('#',1)[0]
            if href.lower().endswith(('.html','.htm')):
                candidates.append(requests.compat.urljoin(idx.url,href))
        candidates=list(dict.fromkeys(candidates))
        full_url=candidates[0] if candidates else idx.url
        if full_url != idx.url:
            page=requests.get(full_url,headers=headers,timeout=(5,30)); page.raise_for_status()
        else:
            page=idx
        result=parse_law_html(page.text,law_code,name)
        if result.get('sections'):
            result['url']=page.url; result['retrieved_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
            return result
        (debug/f'{law_code}_raw.html').write_text(page.text,encoding='utf8')
        print(f"     ⚠️  0 Abschnitte für {law_code}; Rohdaten: data/debug/{law_code}_raw.html")
    except Exception as e:
        print(f"     ❌ {law_code}: {e}")
    return {}


def parse_law_xml(xml_content: bytes, law_code: str, law_name: str) -> Dict:
    import xml.etree.ElementTree as ET
    try: root=ET.fromstring(xml_content)
    except ET.ParseError:return {"code":law_code,"name":law_name,"sections":[]}
    sections=[]
    for el in root.iter():
        tag=el.tag.split('}')[-1].lower()
        if tag not in {'paragraph','artikel'}: continue
        text=' '.join(''.join(el.itertext()).split())
        if len(text)<40: continue
        title=el.get('titel') or el.get('title') or el.get('{http://www.w3.org/1999/xlink}title') or ''
        xid=el.get('id') or el.get('{http://www.w3.org/1999/xlink}id') or ''
        sections.append({'type':tag,'title':title,'text':text,'xml_id':xid})
    return {'code':law_code,'name':law_name,'source':'gesetze-im-internet.de (XML)','sections':sections}


def parse_law_html(html_content: str, law_code: str, law_name: str) -> Dict:
    soup=BeautifulSoup(html_content,'html.parser')
    sections=[]
    # Current site uses jur* classes. Extract one logical paragraph/article at a
    # time instead of every nested div; this fixes the former 4-section result.
    nodes=soup.select('.jurParagraph, .jurArtikel, .jurNorm')
    seen=set()
    for node in nodes:
        text=' '.join(node.get_text(' ',strip=True).split())
        if len(text)<40: continue
        key=hash(text)
        if key in seen: continue
        seen.add(key)
        heading=node.find(['h3','h4','h5'])
        title=heading.get_text(' ',strip=True) if heading else ''
        if not title:
            ident=node.get('id','')
            title=ident
        sections.append({'type':'paragraph' if 'Paragraph' in ' '.join(node.get('class',[])) else 'section','title':title,'text':text,'html_id':node.get('id','')})
    if not sections:
        # Fallback: collect text blocks beginning with § / Art and group until
        # the next heading. This is deliberately conservative.
        content=soup.find('main') or soup.find('div',id='content') or soup.body or soup
        current_title=''; current=[]
        for elem in content.find_all(['h1','h2','h3','h4','h5','p','div']):
            t=' '.join(elem.get_text(' ',strip=True).split())
            if not t: continue
            if re.match(r'^(§+\s*\d+[a-zA-Z]*|Art\.?\s*\d+[a-zA-Z]*)\b',t):
                if current and len(' '.join(current))>=40:
                    sections.append({'type':'section','title':current_title,'text':' '.join(current)})
                current_title=t; current=[t]
            elif current:
                current.append(t)
        if current and len(' '.join(current))>=40:
            sections.append({'type':'section','title':current_title,'text':' '.join(current)})
    return {'code':law_code,'name':law_name,'source':'gesetze-im-internet.de (HTML)','sections':sections}

def fetch_eurlex(celex_id: str) -> Dict:
    """Lädt EU-Recht von EUR-Lex (CELEX-ID)."""
    url = f"https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=CELEX:{celex_id}"
    
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'html.parser')
            # Haupttext extrahieren
            content = soup.find('div', {'id': 'document1'}) or soup.find('div', {'class': 'document'})
            if content:
                text = content.get_text(strip=True)
                return {
                    "celex": celex_id,
                    "source": "eur-lex.europa.eu",
                    "text": text[:10000]
                }
    except Exception as e:
        print(f"❌ EUR-Lex Fehler {celex_id}: {e}")
    
    return {}


def create_law_training_data(laws: Dict) -> List[Dict]:
    """Erstellt Trainingsexamples aus Gesetzestexten."""
    examples = []
    system_prompt = """Du bist ein Experte für deutsches und europäisches Recht mit Fokus auf:
- Verfassungsrecht (GG), Zivilrecht (BGB), Strafrecht (StGB)
- Datenschutzrecht (DSGVO, BDSG, TTDSG)
- Betäubungsmittelrecht (BtMG, MedCanG, CanG)
- Verwaltungsrecht, Europa- & Völkerrecht

Zitiere Paragraphen, Urteile (BGH, BVerfG, EuGH), Literatur. Unterscheide klar: geltendes Recht vs. Rechtslage vor Reformen."""
    
    for law in laws.values():
        code = law.get("code", "")
        name = law.get("name", "")
        sections = law.get("sections", [])
        
        for sec in sections:
            text = sec.get("text", "")
            title = sec.get("title", "")
            
            if len(text) < 200:
                continue
            
            # Q&A Pairs generieren
            qa_pairs = [
                (f"Erkläre {title or f'einen Abschnitt aus {name}'} ({code}).",
                 f"{name} ({code}): {text[:2000]}..."),
                (f"Was regelt {title or f'dieser Paragraf aus {name}'}?",
                 f"Dieser Abschnitt aus {name} ({code}) regelt: {text[:2000]}..."),
            ]
            
            for q, a in qa_pairs:
                examples.append({
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": q},
                        {"role": "assistant", "content": a}
                    ],
                    "metadata": {"source": "gesetze-im-internet.de", "law": code, "section": title}
                })
    
    return examples


def main():
    output_dir = Path("./data/raw/law")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("⚖️  Sammle deutsches & EU-Recht...")
    
    all_laws = {}
    
    # Deutsche Gesetze
    for code, name in LAWS_DE.items():
        print(f"  📜 {name} ({code})...")
        law_data = fetch_law_gesetze_im_internet(code)
        if law_data and law_data.get("sections"):
            all_laws[code] = law_data
            print(f"     → {len(law_data['sections'])} Abschnitte")
        else:
            print(f"     ⚠️  Keine Daten / Fehler")
        time.sleep(0.3)  # Höflich
    
    # EU-Gesetze (EUR-Lex CELEX IDs) - manuell wichtige
    eu_celex = {
        "32016R0679": "DSGVO",
        "32001L0083": "Richtlinie 2001/83/EG (Arzneimittel)",
        "32015R2283": "Novel Food Verordnung",
        "32023R1322": "EMCDDA Verordnung",
    }
    
    for celex, name in eu_celex.items():
        print(f"  🇪🇺 {name} ({celex})...")
        law_data = fetch_eurlex(celex)
        if law_data and law_data.get("text"):
            all_laws[celex] = law_data
            print(f"     → OK")
        time.sleep(0.5)
    
    # Training Data erstellen
    training_examples = create_law_training_data(all_laws)
    print(f"\n📝 Training Examples: {len(training_examples)}")
    
    # Speichern
    out_file = output_dir / "law_training.jsonl"
    with open(out_file, 'w', encoding='utf-8') as f:
        for ex in training_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    
    # Rohdaten
    raw_file = output_dir / "laws_raw.jsonl"
    with open(raw_file, 'w', encoding='utf-8') as f:
        for law in all_laws.values():
            f.write(json.dumps(law, ensure_ascii=False) + "\n")
    
    print(f"\n✅ Gespeichert:")
    print(f"   Training: {out_file}")
    print(f"   Rohdaten: {raw_file}")


if __name__ == "__main__":
    main()