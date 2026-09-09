# Quick Start – Host PC (RTX 3060 12 GB)

**Projektstand: V16 / 2026-09-09**

Dieser Guide ist bewusst kurz. Für Details siehe `README.md`.

## 1. Voraussetzungen

- Windows 10/11 oder Linux
- Python 3.10–3.14; für maximale Reproduzierbarkeit ist 3.11/3.12 eine konservative Wahl
- NVIDIA-Treiber mit CUDA-12.6-kompatiblem PyTorch-Stack
- RTX 3060 12 GB oder vergleichbare GPU
- ausreichend SSD-Speicher für Modell, Cache, Checkpoints und GGUF
- Internetzugang für Hugging Face und die externen Collector-Quellen

## 2. Setup unter Windows

```cmd
cd finetune-project
setup_host_windows.bat
venv\Scripts\activate
```

Oder manuell:

```cmd
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Installation prüfen

```cmd
python scripts\train.py --check-only
python scripts\self_test.py
```

Wenn beide Checks sauber laufen, ist die Umgebung grundsätzlich bereit.

## 4. Datenpipeline

Kompletter Lauf:

```cmd
python scripts\run_all_collectors.py
```

Schnellerer Lauf ohne Supplemental-Crawl:

```cmd
python scripts\run_all_collectors.py --skip-supplemental
```

Tiefer Supplemental-Crawl:

```cmd
python scripts\run_all_collectors.py --supplemental-deep
```

Nur Quellen prüfen:

```cmd
python scripts\source_health.py
```

Danach:

```cmd
python scripts\audit_dataset.py
```

**Nicht trainieren, wenn der Audit nicht `AUDIT OK` meldet.**

## 5. Eigene Dokumente

Eigene PDFs/MD/TXT/DOCX nach `data/own_data/` legen und anschließend den normalen Master-Lauf ausführen. Alternativ:

```cmd
python scripts\prepare_data.py --input-dir data\own_data --output-dir data\processed
python scripts\merge_all.py
python scripts\audit_dataset.py
```

## 6. Training

```cmd
python scripts\train.py
```

Resume:

```cmd
python scripts\train.py --resume
```

TensorBoard:

```cmd
python scripts\train.py --debug
```

Auf einer RTX 3060 12 GB hängt die Laufzeit stark von Anzahl und Länge der Beispiele ab. Die alte pauschale Angabe „3–5 Stunden“ war zu spezifisch und wurde deshalb entfernt.

## 7. Merge + GGUF

```cmd
python scripts\train.py --merge --quantize --quant-type Q4_K_M
```

Oder nach abgeschlossenem Training:

```cmd
python scripts\train.py --merge-only --quantize --quant-type Q4_K_M
```

Voraussetzung für GGUF: separat gebautes `llama.cpp` mit CUDA und dessen Python-Abhängigkeiten.

## 8. Wichtige Dateien

```text
README.md
QUICKSTART_HOST.md
requirements.txt
config/
  domain_balance.yaml
  sources.yaml
  source_catalog.yaml
  training_profiles.yaml
scripts/
  run_all_collectors.py
  source_health.py
  collect_*.py
  collect_supplemental.py
  prepare_collected.py
  prepare_supplemental.py
  merge_all.py
  build_rag_corpus.py
  audit_dataset.py
  train_custom.py
  train.py
  quick_test.py
  self_test.py
data/
  own_data/
  raw/
  processed/
  rag/
  train.jsonl
  val.jsonl
output/
```

## 9. Domänen

Aktuell getrennt modelliert:

- Programmieren
- Philosophie/Ethik
- Wissenschaft
- Gärtnern/Permakultur
- Cannabis
- deutsches/EU-Recht
- Arma 3 Technik/Modding
- Arma 3 Milsim
- öffentliches Militärwissen nach Nation/Allgemein
- zusätzliche Supplemental-Themen aus dem Quellenkatalog

## 10. Wichtige Qualitätsregel

`403`, `404`, DNS-Fehler oder Timeouts einzelner externer Quellen sind **nicht automatisch Pipeline-Fehler**. Die Quelle wird protokolliert und übersprungen. Das Projekt versucht keinen Zugriffsschutz zu umgehen.

Ein echter Fehler liegt vor, wenn eine erforderliche Pipeline-Stufe keine verwertbaren Daten erzeugt, das Schema verletzt oder der abschließende Audit fehlschlägt.
