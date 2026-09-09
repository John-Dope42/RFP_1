# Qwen2.5-3B Tuned_by_Pino

**Stand: 2026-09-09**  
Deutschsprachiger Domain-Assistent basierend auf **Qwen/Qwen2.5-3B-Instruct** mit **QLoRA 4-bit (NF4)** und **TRL/PEFT** – ohne Axolotl-Abhängigkeit. Optimiert für **RTX 3060 12 GB**.

---

## Kernfunktionen

- **Datenaufbereitung**: Eigene Dokumente (PDF/MD/TXT/DOCX) und automatisierte Collector für Domänen (Cannabis, Recht, Gärtnern, Wissenschaft, Arma 3, Milsim, Militär).
- **Quellenmanagement**: Provenienzerhaltung, Gesundheitsprüfung (`source_health.py`), non-fatal Fehlerbehandlung.
- **Pipeline**: Dedup, Domain-Split, Balancierung, Audit (`audit_dataset.py`), Train/Val-Leakage-Prüfung.
- **Training**: QLoRA mit LoRA (rank 64, alpha 128), 3 Epochen, 4096 Context, GGUF-Export für LM Studio.
- **RAG-Unterstützung**: Separater Korpus (`data/rag/`) für dynamische Inhalte (z. B. aktuelle Rechtsstände).

---

## Architektur

```text
Eigene Daten + Core/Supplemental Collector → data/raw/ → prepare_* → merge_all → audit
                                                   ↓
                                          data/train.jsonl, data/val.jsonl, data/rag/
                                          train.py → LoRA Adapter → Merge → GGUF
```

**Datenebenen**:  
`own_data/` (eigene Dokumente) → `raw/` (Rohdaten) → `processed/` → `train.jsonl`/`val.jsonl` → `output/` (Adapter/Modell).

---

## Schnellstart

### 1. Installation

**Windows/Linux**:

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

*Alternativ*: `setup_host_windows.bat` oder `setup_host_linux.sh`.

### 2. Daten sammeln &amp; aufbereiten

```bash
# Vollständiger Pipeline-Lauf (Core + Supplemental + RAG)
python scripts/run_all_collectors.py

# Nur Core-Collector (ohne Supplemental/RAG)
python scripts/run_all_collectors.py --skip-supplemental

# Quellen prüfen
python scripts/source_health.py

# Audit (Pflicht vor Training!)
python scripts/audit_dataset.py
```

### 3. Training

```bash
# Prüfen
python scripts/train.py --check-only

# Training starten (QLoRA, 3 Epochen)
python scripts/train.py

# Fortsetzen
python scripts/train.py --resume

# Mergen + Quantisieren (Q4_K_M)
python scripts/train.py --merge --quantize --quant-type Q4_K_M
```

---

## Wichtige Skripte


| Skript                  | Zweck                                            |
| ----------------------- | ------------------------------------------------ |
| `run_all_collectors.py` | End-to-End-Pipeline (Collector → Audit)          |
| `audit_dataset.py`      | **Pflicht vor Training**: Datenintegrität prüfen |
| `train.py`              | Training, Merge, GGUF-Export                     |
| `source_health.py`      | Erreichbarkeit externer Quellen testen           |
| `prepare_data.py`       | Eigene Dokumente verarbeiten                     |
| `merge_all.py`          | Dedup, Split, Balance                            |
| `build_rag_corpus.py`   | RAG-Korpus erstellen                             |


---

## Konfiguration

- **Domain-Balance**: `config/domain_balance.yaml`
  ```yaml
  target_per_domain: 800  # Max. Trainingsbeispiele pro Domain
  max_oversample_factor: 4  # Oversampling für kleine Domänen
  ```
- **Training**: `scripts/train_custom.py` (LoRA, Batch-Größe, etc.)

---

## Domänen


| Domain       | Fokus                     | Datenstand (Snapshot)                |
| ------------ | ------------------------- | ------------------------------------ |
| Cannabis     | Fachwissen                | 308 Beispiele                        |
| Gärtnern     | Permakultur/Praxis        | 856                                  |
| Wissenschaft | arXiv/PubMed              | 2,586                                |
| Arma 3       | Technik/Modding           | 104                                  |
| Milsim       | Community-Praxis          | 45                                   |
| Militär      | Öffentliche Doktrin       | 1,130                                |
| **Gesamt**   | **6,488 Train / 304 Val** | *(dynamisch je nach Collector-Lauf)* |


**Hinweis**:

- `arma3_technical`/`modding` ≠ `milsim` ≠ `military.*` (bewusst getrennt).
- Details: Siehe `ARMA3_MILITARY_PIPELINE.md`.

---

## Fehlerbehebung


| Problem                        | Lösung                                                                                                                     |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| **OOM**                        | `MAX_SEQ_LENGTH` in `train_custom.py` auf 2048 reduzieren                                                                  |
| **403/404 Quellen**            | `source_health.py` ausführen, Katalog anpassen                                                                             |
| **Audit fehlgeschlagen**       | **Nicht trainieren!** Fehlermeldung beheben, Audit wiederholen                                                             |
| **GGUF-Export fehlgeschlagen** | `llama.cpp` mit CUDA neu bauen                                                                                             |
| **Paketversionen prüfen**      | `python -c "import torch,transformers,peft,trl,datasets,bitsandbytes; print(torch.__version__, transformers.__version__)"` |


---

## Rechtliches

- **Provenienz**: Jedes Beispiel enthält Quellenangabe (Domain/URL).
- **Lizenzprüfung**: Vor Redistribution des Datensatzes/Modells **Lizenz jeder Quelle prüfen**.
- **Gesetze**: Automatisierter Zugriff auf `gesetze-im-internet.de` wird nicht erzwungen. Manuelle PDFs in `data/own_data/` ablegen.

---

## Reproduzierbarkeit

```bash
python -m compileall -q scripts  # Syntaxprüfung
python scripts/self_test.py       # Offline-Regressionstest
python scripts/audit_dataset.py   # Daten-Audit
```

---

**Status V16**: Vollständige Integration von Collector-, Supplemental-, RAG-, Dataset- und Training-Pipeline. Dokumentation spiegelt aktuellen Funktionsumfang wider.
