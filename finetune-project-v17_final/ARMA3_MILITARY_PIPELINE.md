# Arma 3 + Military + Milsim Pipeline (V16)

## Ziel

Die Pipeline trennt bewusst drei Wissensebenen:

1. **`arma3_technical` / `arma3_modding`** – Arma-3-Engine, SQF, Eden, Mission-/Mapbau, Configs, Multiplayer, Server, Performance und Modding.
2. **`milsim`** – öffentliche Community-/Multiplayer-Praxis. Diese Inhalte werden nicht als offizielle Militärdoktrin dargestellt.
3. **`military.*`** – öffentlich zugängliche militärische Quellen nach Streitkraft/Nation sowie allgemeine Militärwissenschaft.

## Quellen

Core-Quellen stehen in `config/sources.yaml`. Die zusätzliche kuratierte Quellenbasis steht in `config/source_catalog.yaml` und ist in `SOURCE_RESEARCH.md` beschrieben.

Wichtige Arma-/Milsim-Quelltypen:

- Bohemia Interactive Community Documentation
- CBA / ACE3 und weitere öffentliche Arma-Projekte
- ACRE2 / TFAR / ALiVE / Antistasi
- Bohemia-Foren und ausgewählte Community-Guides
- öffentliche militärische Primärquellen und Forschungsinstitutionen

## Collector

Einzelne Collector:

```bash
python scripts/collect_arma3.py
python scripts/collect_milsim.py
python scripts/collect_military.py
```

Danach:

```bash
python scripts/prepare_collected.py
python scripts/merge_all.py
python scripts/audit_dataset.py
```

Oder komplett:

```bash
python scripts/run_all_collectors.py
```

## Verhalten bei 403/404/Timeout

Die Bohemia-Community und andere externe Seiten können automatisierte Requests ablehnen. Der Collector versucht **nicht**, solche Zugriffsbeschränkungen zu umgehen. Einzelne Quellen werden übersprungen und die übrigen Quellen weiter verarbeitet.

Das ist besonders wichtig für die Milsim-Pipeline: Ein 403 auf einer Bohemia-Seite darf nicht dazu führen, dass vorhandene CBA-/ACE-/GitHub-/Community-Dokumentation ebenfalls verloren geht.

Wenn ein kompletter Collector anschließend 0 verwertbare Chunks besitzt, wird das als echter Collector-Fehler gemeldet.

## Datenqualität

`prepare_collected.py` erzeugt konservative, quellengrounded Conversational-Beispiele. Der Assistant-Text ist der tatsächlich extrahierte Inhalt; es werden keine zusätzlichen Fakten erfunden. Metadaten enthalten nach Möglichkeit Quelle, URL, Titel und Domain.

Für Milsim und Militär gelten zusätzliche semantische Regeln:

- Community-Praxis ≠ offizielle Doktrin
- historische Quelle ≠ aktueller Stand
- nationale Terminologie ≠ universelle NATO-Terminologie
- öffentlich zugänglich ≠ automatisch frei redistribuierbar

## Supplemental vs. Core

`collect_arma3.py`, `collect_milsim.py` und `collect_military.py` sind Core-Collector mit eigener Logik. `collect_supplemental.py` ergänzt die Quellenbasis generisch und schreibt nach `data/raw/supplemental/`.

Die Supplemental-Daten können sowohl in QLoRA als auch im RAG-Korpus landen. RAG erhält den vollständigen deduplizierten Quellenbestand; QLoRA wird durch `merge_all.py` nach `config/domain_balance.yaml` begrenzt/balanciert.

## Training

Nach einem kompletten Lauf:

```bash
python scripts/audit_dataset.py
python scripts/train.py
```

Der Trainer nutzt QLoRA mit 4-bit NF4 und klassischem LoRA. Für aktuelle TRL-Versionen wird `SFTConfig`/`processing_class` dynamisch erkannt; ältere kompatible TRL-Varianten werden ebenfalls unterstützt.

## Nicht enthalten

Die Pipeline sammelt keine klassifizierten, zugangsbeschränkten oder absichtlich privaten militärischen Informationen. Sie ist für öffentlich dokumentiertes Wissen und Arma-3-/Milsim-Praxis ausgelegt.
