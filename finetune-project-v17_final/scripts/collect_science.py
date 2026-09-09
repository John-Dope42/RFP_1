#!/usr/bin/env python3
"""
Wissenschaft-Daten Sammler - arXiv, PubMed (Open Access), Open Access Journals
Fokus: Evidenzbasiert, DOI/PMID zitierbar
"""

import json
import requests
import time
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict
import arxiv

if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


# ============================================================
# WISSENSCHAFTLICHE QUELLEN (KOSTENLOS, OPEN ACCESS)
# ============================================================
SCIENCE_QUERIES = {
    "physics": [
        "quantum computing",
        "condensed matter physics",
        "particle physics standard model",
        "climate physics modeling",
    ],
    "chemistry": [
        "organic synthesis catalysis",
        "materials chemistry battery",
        "analytical chemistry spectroscopy",
        "green chemistry sustainable",
    ],
    "biology": [
        "molecular biology CRISPR",
        "genomics sequencing",
        "cell biology signaling",
        "evolutionary biology phylogenetics",
    ],
    "medicine": [
        "clinical trial methodology",
        "meta-analysis systematic review",
        "pharmacology drug discovery",
        "neuroscience brain",
        "immunology vaccine",
        "oncology cancer therapy",
    ],
    "neuroscience": [
        "neural networks brain",
        "cognitive neuroscience",
        "neuroplasticity learning",
        "consciousness neuroscience",
    ],
    "climate": [
        "climate change mitigation",
        "carbon cycle modeling",
        "renewable energy integration",
        "climate policy economics",
    ],
    "statistics": [
        "bayesian inference",
        "causal inference",
        "machine learning statistics",
        "reproducibility crisis",
    ],
    "ai_ml": [
        "large language models",
        "transformer architecture",
        "reinforcement learning",
        "AI alignment safety",
        "foundation models",
    ],
}


def fetch_arxiv_papers(categories: List[str], max_per_cat: int = 50) -> List[Dict]:
    """Holt Papers von arXiv (Open Access)."""
    papers = []
    
    # arXiv Kategorien Mapping
    cat_map = {
        "physics": ["physics", "quant-ph", "cond-mat", "hep-ph", "astro-ph"],
        "chemistry": ["physics.chem-ph", "physics.ao-ph"],
        "biology": ["q-bio", "physics.bio-ph"],
        "medicine": ["q-bio", "physics.med-ph"],
        "neuroscience": ["q-bio.NC", "q-bio.QM"],
        "climate": ["physics.ao-ph", "physics.geo-ph"],
        "statistics": ["stat.ML", "stat.AP", "stat.ME"],
        "ai_ml": ["cs.LG", "cs.CL", "cs.AI", "cs.CV", "stat.ML"],
    }
    
    client = arxiv.Client()
    
    for domain, arxiv_cats in cat_map.items():
        if domain not in categories:
            continue
            
        for cat in arxiv_cats:
            try:
                search = arxiv.Search(
                    query=f"cat:{cat}",
                    max_results=max_per_cat,
                    sort_by=arxiv.SortCriterion.Relevance
                )
                
                for paper in client.results(search):
                    papers.append({
                        "arxiv_id": paper.entry_id.split('/')[-1],
                        "title": paper.title,
                        "abstract": paper.summary,
                        "authors": [a.name for a in paper.authors],
                        "categories": paper.categories,
                        "published": paper.published.isoformat() if paper.published else "",
                        "pdf_url": paper.pdf_url,
                        "source": "arxiv",
                        "domain": domain
                    })
            except Exception as e:
                print(f"❌ arXiv Fehler {cat}: {e}")
            time.sleep(0.5)
    
    return papers


def fetch_pubmed_open_access(queries: List[str], max_per_query: int = 30) -> List[Dict]:
    """Holt Open Access Abstracts von PubMed.

    BUGFIX: "pmc[filter]"/"open access[filter]" waren ungültige PubMed-Feld-Tags
    und lieferten lautlos 0 Treffer statt eines Fehlers. Korrekt: "free full text[sb]"
    (siehe https://pubmed.ncbi.nlm.nih.gov/help/).
    """
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    all_results = []
    
    for query in queries:
        # Search
        search_url = f"{base}esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": f"{query} AND free full text[sb]",
            "retmax": max_per_query,
            "retmode": "json",
            "sort": "relevance"
        }
        
        try:
            resp = requests.get(search_url, params=params, timeout=30)
            result_json = resp.json()
            ids = result_json.get("esearchresult", {}).get("idlist", [])
            if not ids:
                count = result_json.get("esearchresult", {}).get("count", "?")
                print(f"     ⚠️  0 Treffer für '{query}' (PubMed count={count})")
        except Exception as e:
            print(f"❌ PubMed Search Fehler: {e}")
            continue
        
        if not ids:
            continue
        
        # Fetch
        fetch_url = f"{base}efetch.fcgi"
        params = {
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "xml",
            "rettype": "abstract"
        }
        
        try:
            resp = requests.get(fetch_url, params=params, timeout=60)
            root = ET.fromstring(resp.content)
        except Exception as e:
            print(f"❌ PubMed Fetch Fehler: {e}")
            continue
        
        for article in root.findall(".//PubmedArticle"):
            try:
                pmid = article.find(".//PMID").text
                title = article.find(".//ArticleTitle").text or ""
                abstract_parts = article.findall(".//AbstractText")
                abstract = " ".join([p.text for p in abstract_parts if p.text])
                journal = article.find(".//Journal/Title")
                journal_name = journal.text if journal is not None else ""
                pubdate = article.find(".//PubDate")
                year = pubdate.find("Year").text if pubdate is not None and pubdate.find("Year") is not None else ""
                doi_elem = article.find(".//ArticleId[@IdType='doi']")
                doi = doi_elem.text if doi_elem is not None else ""
                
                if abstract and len(abstract) > 200:
                    all_results.append({
                        "pmid": pmid,
                        "title": title,
                        "abstract": abstract,
                        "journal": journal_name,
                        "year": year,
                        "doi": doi,
                        "source": "pubmed",
                        "query": query
                    })
            except:
                continue
        
        time.sleep(0.5)
    
    return all_results


def create_science_training_data(arxiv_papers: List[Dict], pubmed_papers: List[Dict]) -> List[Dict]:
    """Erstellt Trainingsexamples aus Wissenschafts-Papers."""
    examples = []
    system_prompt = """Du bist ein Wissenschaftler mit breitem Fachwissen in:
- Physik, Chemie, Biologie, Medizin, Neurowissenschaften
- Klimawissenschaft, Umweltwissenschaften
- Forschungsmethodik, Statistik, Evidenzbewertung (RCT, Meta-Analysen)
- Wissenschaftstheorie (Popper, Kuhn, Falsifikation, Reproduzierbarkeit)

Antworte evidenzbasiert, mit Studien-Referenzen (DOI, PMID, arXiv-ID), unterscheide Hypothese/Theorie/Fakt."""
    
    # arXiv Papers
    for paper in arxiv_papers:
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")
        arxiv_id = paper.get("arxiv_id", "")
        authors = ", ".join(paper.get("authors", [])[:3]) + (" et al." if len(paper.get("authors", [])) > 3 else "")
        cats = ", ".join(paper.get("categories", []))
        
        if len(abstract) < 200:
            continue
        
        qa_pairs = [
            (f"Fasse das Paper '{title}' (arXiv:{arxiv_id}) zusammen.",
             f"{title} (arXiv:{arxiv_id}, {authors}, {cats}): {abstract[:2000]}..."),
            (f"Was sind die Hauptbeiträge dieser Arbeit: {title}?",
             f"Hauptbeiträge von {title} (arXiv:{arxiv_id}): {abstract[:2000]}..."),
        ]
        
        for q, a in qa_pairs:
            examples.append({
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": q},
                    {"role": "assistant", "content": a}
                ],
                "metadata": {"source": "arxiv", "arxiv_id": arxiv_id, "domain": paper.get("domain")}
            })
    
    # PubMed Papers
    for paper in pubmed_papers:
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")
        pmid = paper.get("pmid", "")
        journal = paper.get("journal", "")
        year = paper.get("year", "")
        doi = paper.get("doi", "")
        
        if len(abstract) < 200:
            continue
        
        qa_pairs = [
            (f"Erkläre die Studienergebnisse: '{title}' ({journal}, {year}, PMID:{pmid}).",
             f"Studie ({journal}, {year}, DOI:{doi}, PMID:{pmid}): {title}. {abstract[:2000]}..."),
            (f"Was sind die klinischen/praktischen Implikationen von: {title}?",
             f"Implikationen der Studie ({journal}, {year}): {abstract[:2000]}..."),
        ]
        
        for q, a in qa_pairs:
            examples.append({
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": q},
                    {"role": "assistant", "content": a}
                ],
                "metadata": {"source": "pubmed", "pmid": pmid, "doi": doi}
            })
    
    return examples


def main():
    output_dir = Path("./data/raw/science")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("🔬 Sammle Wissenschaftsdaten (arXiv + PubMed Open Access)...")
    
    # arXiv
    print("📥 arXiv Papers...")
    arxiv_papers = fetch_arxiv_papers(list(SCIENCE_QUERIES.keys()), max_per_cat=30)
    print(f"   → {len(arxiv_papers)} Papers")
    
    # PubMed
    print("📥 PubMed Open Access...")
    all_queries = [q for queries in SCIENCE_QUERIES.values() for q in queries]
    pubmed_papers = fetch_pubmed_open_access(all_queries, max_per_query=20)
    print(f"   → {len(pubmed_papers)} Abstracts")
    
    # Training Data
    training_examples = create_science_training_data(arxiv_papers, pubmed_papers)
    print(f"\n📝 Training Examples: {len(training_examples)}")
    
    # Speichern
    out_file = output_dir / "science_training.jsonl"
    with open(out_file, 'w', encoding='utf-8') as f:
        for ex in training_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    
    raw_arxiv = output_dir / "arxiv_raw.jsonl"
    with open(raw_arxiv, 'w', encoding='utf-8') as f:
        for p in arxiv_papers:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    
    raw_pubmed = output_dir / "pubmed_raw.jsonl"
    with open(raw_pubmed, 'w', encoding='utf-8') as f:
        for p in pubmed_papers:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    
    print(f"\n✅ Gespeichert:")
    print(f"   Training: {out_file}")
    print(f"   arXiv Roh: {raw_arxiv}")
    print(f"   PubMed Roh: {raw_pubmed}")


if __name__ == "__main__":
    main()