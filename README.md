# Qwen2.5-3B Tuned_by_Pino

**As of: 2026-09-09**  
German-language domain assistant based on **Qwen/Qwen2.5-3B-Instruct** with **QLoRA 4-bit (NF4)** and **TRL/PEFT** – without an Axolotl dependency. Optimized for **RTX 3060 12 GB**.

---

## Core Features

- **Data Preparation**: User-provided documents (PDF/MD/TXT/DOCX) and automated collectors for domains (cannabis, law, gardening, science, Arma 3, milsim, military).
- **Source Management**: Provenance preservation, source health checks (`source_health.py`), and non-fatal error handling.
- **Pipeline**: Deduplication, domain splitting, balancing, auditing (`audit_dataset.py`), and train/validation leakage checks.
- **Training**: QLoRA with LoRA (rank 64, alpha 128), 3 epochs, 4096-token context, and GGUF export for LM Studio.
- **RAG Support**: Separate corpus (`data/rag/`) for dynamic content, such as current legal statuses.

---

## Architecture

```text
User data + Core/Supplemental collectors → data/raw/ → prepare_* → merge_all → audit
                                                   ↓
                                          data/train.jsonl, data/val.jsonl, data/rag/
                                          train.py → LoRA Adapter → Merge → GGUF
```

**Data layers**:  
`own_data/` (user documents) → `raw/` (raw data) → `processed/` → `train.jsonl`/`val.jsonl` → `output/` (adapter/model).

---

## Quick Start

### 1. Installation

**Windows/Linux**:

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

*Alternatively*: `setup_host_windows.bat` or `setup_host_linux.sh`.

### 2. Collect &amp; Prepare Data

```bash
# Full pipeline run (Core + Supplemental + RAG)
python scripts/run_all_collectors.py

# Core collector only (without Supplemental/RAG)
python scripts/run_all_collectors.py --skip-supplemental

# Check sources
python scripts/source_health.py

# Audit (required before training!)
python scripts/audit_dataset.py
```

### 3. Training

```bash
# Check
python scripts/train.py --check-only

# Start training (QLoRA, 3 epochs)
python scripts/train.py

# Resume
python scripts/train.py --resume

# Merge + quantize (Q4_K_M)
python scripts/train.py --merge --quantize --quant-type Q4_K_M
```

---

## Important Scripts


| Script                  | Purpose                                          |
| ----------------------- | ------------------------------------------------ |
| `run_all_collectors.py` | End-to-end pipeline (collector → audit)          |
| `audit_dataset.py`      | **Required before training**: validate data integrity |
| `train.py`              | Training, merging, and GGUF export              |
| `source_health.py`      | Test external source availability               |
| `prepare_data.py`       | Process user documents                           |
| `merge_all.py`          | Deduplication, splitting, and balancing          |
| `build_rag_corpus.py`   | Build the RAG corpus                             |


---

## Configuration

- **Domain Balance**: `config/domain_balance.yaml`
  ```yaml
  target_per_domain: 800  # Maximum training examples per domain
  max_oversample_factor: 4  # Oversampling for small domains
  ```
- **Training**: `scripts/train_custom.py` (LoRA, batch size, etc.)

---

## Domains


| Domain       | Focus                     | Data Status (Snapshot)               |
| ------------ | ------------------------- | ------------------------------------ |
| Cannabis     | Subject-matter expertise  | 308 examples                         |
| Gardening    | Permaculture/practice     | 856                                   |
| Science      | arXiv/PubMed              | 2,586                                 |
| Arma 3       | Technology/modding        | 104                                   |
| Milsim       | Community practice        | 45                                    |
| Military     | Public doctrine           | 1,130                                 |
| **Total**    | **6,488 train / 304 val** | *(varies by collector run)*         |


**Note**:

- `arma3_technical`/`modding` ≠ `milsim` ≠ `military.*` (intentionally kept separate).
- Details: See `ARMA3_MILITARY_PIPELINE.md`.

---

## Troubleshooting


| Problem                        | Solution                                                                                                                   |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| **OOM**                        | Reduce `MAX_SEQ_LENGTH` in `train_custom.py` to 2048                                                                     |
| **403/404 sources**            | Run `source_health.py` and update the catalog                                                                              |
| **Audit failed**               | **Do not train!** Fix the reported error and rerun the audit                                                               |
| **GGUF export failed**         | Rebuild `llama.cpp` with CUDA support                                                                                      |
| **Check package versions**     | `python -c "import torch,transformers,peft,trl,datasets,bitsandbytes; print(torch.__version__, transformers.__version__)"` |


---

## Legal Notes

- **Provenance**: Each example includes source information (domain/URL).
- **License review**: Before redistributing the dataset or model, **review the license of every source**.
- **Legal texts**: Automated access to `gesetze-im-internet.de` is not forced. Place manual PDFs in `data/own_data/`.

---

## Reproducibility

```bash
python -m compileall -q scripts  # Syntax check
python scripts/self_test.py       # Offline regression test
python scripts/audit_dataset.py   # Dataset audit
```

---

**Status V17**: Full integration of the collector, supplemental, RAG, dataset, and training pipelines. The documentation reflects the current feature set.
