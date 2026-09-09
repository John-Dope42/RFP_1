# Fine-Tuning Projekt – Qwen2.5-3B Domain Expert (V16)

**Stand: 2026-09-09**

Dieses Projekt baut einen deutschsprachig orientierten Domain-Assistenten auf Basis von **Qwen/Qwen2.5-3B-Instruct**. Training erfolgt mit **QLoRA 4-bit (NF4)** und direktem **TRL/PEFT**, ohne Axolotl als Laufzeitabhängigkeit.

## Was das Projekt aktuell kann

- eigene PDF/MD/TXT/DOCX-Dokumente aufbereiten
- Core-Collector für Cannabis, Recht, Gärtnern und Wissenschaft
- Arma-3-Technik/Modding, Milsim und öffentlich zugängliches Militärwissen getrennt sammeln
- eine kuratierte Supplemental-Quellenbasis aus HTML/PDF und öffentlichen Git-Repositories verarbeiten
- Provenienz/Quelle/Domain in den Rohdaten erhalten
- QLoRA-Trainingsdaten und einen separaten RAG-Korpus erzeugen
- Quellen vor dem Crawl mit `source_health.py` prüfen
- Einzelne blockierte/defekte externe Quellen non-fatal behandeln
- finalen Datensatz deduplizieren, domänenweise splitten, balancieren und auditieren
- Train/Val-Leakage auf Dokument-/Inhaltsebene prüfen
- LoRA trainieren, Adapter mergen und optional GGUF für LM Studio erzeugen

**Wichtig:** Ein erfolgreicher Pipeline-Lauf bedeutet nicht, dass jede externe Website erreichbar war. Der Collector dokumentiert nicht erreichbare Quellen und arbeitet mit den übrigen Quellen weiter. Ein Collector gilt erst dann als problematisch, wenn er trotz seiner verfügbaren Quellen keine verwertbaren Daten liefern kann.

## Aktueller Datenstand im mitgelieferten Snapshot

Der ZIP-Snapshot enthält derzeit **6,488 Train-** und **304 Validation-Beispiele**. Diese Zahlen sind nur der Stand der mitgelieferten Dateien; ein neuer Collect-Lauf kann andere Zahlen erzeugen.

Die Roh-Training-Dateien im Snapshot umfassen u.a.:
- Cannabis: 308
- Gärtnern: 856
- Wissenschaft: 2,586
- Arma 3: 104
- Milsim: 45
- Militär: 1,130

## Architektur

```text
Eigene Daten ─────────────┐
Core Collector ───────────┼─> data/raw/ ─> prepare_* ─> merge_all ─> audit
Supplemental Collector ──┘                         │
                                                   ├─> data/train.jsonl
                                                   ├─> data/val.jsonl
                                                   └─> data/rag/rag_chunks.jsonl

train.py -> train_custom.py -> LoRA Adapter -> Merge -> optional GGUF -> LM Studio
```

### Datenebenen

- `data/own_data/`: eigene Dokumente
- `data/raw/`: Rohdaten mit Provenienz
- `data/processed/`: aufbereitete eigene Daten
- `data/legacy/`: bewusst eingefrorene ältere Datensätze für den einmaligen Legacy-Import
- `data/rag/`: deduplizierter RAG-Korpus
- `data/train.jsonl`, `data/val.jsonl`: finales SFT/QLoRA-Dataset
- `output/`: Adapter, gemergtes Modell und GGUF

## Wichtigste Skripte

| Skript | Zweck |
|---|---|
| `scripts/prepare_data.py` | eigene PDF/MD/TXT/DOCX verarbeiten |
| `scripts/collect_cannabis.py` | Cannabis-Quellen |
| `scripts/collect_law.py` | DE/EU-Recht |
| `scripts/collect_gardening.py` | Gärtnern/Permakultur |
| `scripts/collect_science.py` | arXiv/PubMed |
| `scripts/collect_arma3.py` | Arma-3-Technik/Modding |
| `scripts/collect_milsim.py` | Arma-3-Milsim/Multiplayer-Praxis |
| `scripts/collect_military.py` | öffentliches Militärwissen/Doktrin |
| `scripts/source_health.py` | Quellen-Erreichbarkeit prüfen |
| `scripts/collect_supplemental.py` | kuratierte Zusatzquellen |
| `scripts/prepare_collected.py` | Core-Collector-Daten in SFT-Beispiele überführen |
| `scripts/prepare_supplemental.py` | Supplemental-Daten konservativ für QLoRA vorbereiten |
| `scripts/merge_all.py` | Dedup, Split, Balance, finales JSONL |
| `scripts/build_rag_corpus.py` | RAG-Korpus bauen |
| `scripts/audit_dataset.py` | finaler Dataset-Audit |
| `scripts/train_custom.py` | QLoRA/SFT mit TRL + PEFT |
| `scripts/train.py` | Checks, Training, Merge, GGUF |
| `scripts/quick_test.py` | Adapter-Schnelltest |
| `scripts/self_test.py` | Offline-Regressionstest |

## Installation

### Windows / RTX 3060 12 GB

```cmd
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Oder das Host-Setup verwenden:

```cmd
setup_host_windows.bat
```

### Linux

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Oder:

```bash
chmod +x setup_host_linux.sh
./setup_host_linux.sh
```

Die Requirements sind bewusst eine **Kompatibilitäts-Lane** und keine Aufforderung, bei jedem Release blind alle ML-Pakete auf die neueste Major-Version zu ziehen. Das verhindert, dass eine neue TRL/Transformers-Major-Version ein ansonsten funktionierendes Training plötzlich inkompatibel macht.

## Vollständiger Datenlauf

Der empfohlene End-to-End-Lauf ist:

```bash
python scripts/run_all_collectors.py
```

Für einen tieferen Supplemental-Crawl:

```bash
python scripts/run_all_collectors.py --supplemental-deep
```

Nur Core-Collector ohne Supplemental/RAG:

```bash
python scripts/run_all_collectors.py --skip-supplemental
```

Nur die Quellen prüfen:

```bash
python scripts/source_health.py
```

Danach zwingend:

```bash
python scripts/audit_dataset.py
```

**Erst bei `AUDIT OK` trainieren.**

### Was `run_all_collectors.py` tatsächlich macht

1. eigene Daten vorbereiten, sofern vorhanden
2. Core-Collector ausführen
3. Source Health prüfen
4. Supplemental-Quellen sammeln
5. Supplemental-QLoRA-Beispiele erzeugen
6. RAG-Korpus bauen (sofern aktiviert)
7. alle Trainingsquellen mergen/deduplizieren
8. Train/Val splitten und Domain-Balance anwenden
9. finalen Audit ausführen

Einzelne externe Quellen mit 403/404/DNS/Timeout werden protokolliert und sind non-fatal. Das Projekt versucht **nicht**, Zugriffsschutz zu umgehen.

## Datenqualität und Balance

Die Pipeline unterscheidet zwischen **echten neuen Beispielen** und Oversampling.

`config/domain_balance.yaml`:

```yaml
target_per_domain: 800
max_oversample_factor: 4
seed: 42
```

Das bedeutet:
- große Domains werden auf maximal 800 Trainingsbeispiele begrenzt
- kleine Domains dürfen bis zum Vierfachen ihrer echten Größe hochgesampelt werden
- RAG-Daten werden dadurch **nicht** gekürzt
- Oversampling erzeugt keine neue Information und ersetzt fehlende Quellen nicht

Train/Val wird domänenstratifiziert erzeugt; Dedup erfolgt vor dem Split. Das reduziert das Risiko, dass nahezu identische Inhalte in beiden Mengen landen.

## Arma 3 / Milsim / Militär

Drei Ebenen bleiben bewusst getrennt:

1. `arma3_technical` / `arma3_modding`: technische Arma-3-Dokumentation, SQF, Engine, Mission-/Modding-Themen
2. `milsim`: Community-/Multiplayer-Praxis; **keine offizielle Militärdoktrin**
3. `military.*`: öffentlich zugängliche militärische Quellen nach Streitkraft/Nation und allgemeiner Militärwissenschaft

Details und Quellenhierarchie: `ARMA3_MILITARY_PIPELINE.md` und `SOURCE_RESEARCH.md`.

## RAG vs. Fine-Tuning

Das Projekt unterstützt bewusst beide Mechanismen:

**Fine-Tuning** lernt Stil, Aufgabenverhalten und stabile Wissensmuster aus `data/train.jsonl`.

**RAG** hält den aktuellen Quellenbestand separat in `data/rag/rag_chunks.jsonl` bzw. optional im Chroma-Index. Für häufig veränderliche Inhalte wie aktuelle Rechtsstände oder Software-Dokumentation ist RAG die bessere Ergänzung als immer wieder dieselbe Information in die Modellgewichte zu trainieren.

## Training

```bash
python scripts/train.py --check-only
python scripts/train.py
```

Mit TensorBoard:

```bash
python scripts/train.py --debug
```

Resume:

```bash
python scripts/train.py --resume
```

Nach dem Training direkt mergen/quantisieren:

```bash
python scripts/train.py --merge --quantize --quant-type Q4_K_M
```

Separat:

```bash
python scripts/train.py --merge-only --quantize --quant-type Q4_K_M
```

### Trainingseinstellungen

- Base: `Qwen/Qwen2.5-3B-Instruct`
- QLoRA: 4-bit NF4
- LoRA rank: 64
- LoRA alpha: 128
- LoRA dropout: 0.05
- `target_modules: all-linear`
- Context: 4096
- Micro-batch: 1
- Gradient accumulation: 16
- Learning rate: 2e-4
- 3 Epochen
- Gradient checkpointing aktiv
- Flash Attention 2 optional; ohne Flash Attention wird SDPA verwendet

### Warum 3B statt 7B?

Das Projekt ist für eine **RTX 3060 12 GB** ausgelegt. Das 3B-Modell ist die konservative, reproduzierbare Standardwahl. Ein 7B-Modell kann je nach Einstellungen ebenfalls quantisiert laufen, ist aber nicht der dokumentierte Standardpfad und wird hier deshalb nicht als „garantiert passend“ beworben.

## Rechtliche und Lizenz-Hinweise

Die Quellenkataloge enthalten bewusst unterschiedliche Autoritäts- und Lizenztypen. **Öffentlich erreichbar bedeutet nicht automatisch frei zur Weiterverwendung im Training.**

Vor Redistribution eines Datensatzes oder Modells muss die Lizenz jeder tatsächlich verwendeten Quelle geprüft werden. Das Projekt speichert deshalb Provenienz und Quelle möglichst mit den Beispielen.

Bei `gesetze-im-internet.de` wird automatisierter Zugriff nicht erzwungen oder umgangen. Für blockierte Gesetzestexte können amtliche PDFs manuell in `data/own_data/` gelegt und mit `prepare_data.py` verarbeitet werden.

## Fehlerdiagnose

### OOM
`MAX_SEQ_LENGTH` in `scripts/train_custom.py` auf 2048 reduzieren oder die effektive Batch-Größe anpassen.

### Externe Quelle liefert 403/404
Nicht als Parser-Bug behandeln. `python scripts/source_health.py` ausführen und alternative Quellen im Katalog nutzen.

### Audit schlägt fehl
Nicht trainieren. Die konkrete Fehlermeldung aus `audit_dataset.py` beheben und den Audit wiederholen.

### GGUF schlägt fehl
`llama.cpp` separat mit CUDA-Unterstützung bauen und sicherstellen, dass das gemergte HF-Modell vorhanden ist.

### Paketversionen prüfen

```bash
python -c "import torch,transformers,peft,trl,datasets,bitsandbytes; print('torch',torch.__version__); print('transformers',transformers.__version__); print('peft',peft.__version__); print('trl',trl.__version__); print('datasets',datasets.__version__); print('bitsandbytes',bitsandbytes.__version__)"
```

## Reproduzierbarer Minimaltest

```bash
python -m compileall -q scripts
python scripts/self_test.py
python scripts/audit_dataset.py
```

---

**Projektstatus V16:** Collector-/Supplemental-/RAG-/Dataset-/Training-Pipeline ist integriert; die Dokumentation beschreibt den tatsächlichen aktuellen Funktionsumfang und nicht mehr historische V13/V14-Zustände.
