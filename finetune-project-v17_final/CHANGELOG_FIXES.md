# Changelog: Fixes gegenüber der Ursprungsversion

Diese Datei dokumentiert, was kaputt war und wie es behoben wurde – zur Nachvollziehbarkeit
und damit du beim nächsten Umbau nicht wieder in dieselben Fallen läufst.

## 🔴 Kritische Bugs (verhinderten erfolgreichen Lauf)

1. **`run_all_collectors.py`: doppelter `scripts/`-Pfad.**
   `Path(__file__).parent` zeigte bereits auf `scripts/`, danach wurde nochmal `/ "scripts"`
   angehängt → gesucht wurde in `scripts/scripts/` (existiert nicht) → `FileNotFoundError`.
   *Fix:* `PROJECT_ROOT = Path(__file__).resolve().parent.parent`, `SCRIPTS_DIR = PROJECT_ROOT / "scripts"`.

2. **Zwei widersprüchliche `requirements*.txt`-Dateien** mit völlig unterschiedlichen,
   inkompatiblen Versionen (`transformers==4.41.2`/`trl==0.9.4` vs.
   `transformers==4.56.2`/`trl==0.18.0`), während die `setup_host_*`-Skripte wiederum ihre
   eigenen hartcodierten `pip install`-Zeilen hatten, die von beiden Dateien abwichen.
   Je nachdem, welchen Pfad man nahm, landete man mit unterschiedlichen Bibliotheksversionen.
   *Fix:* Eine einzige `requirements.txt`, alle Setup-Skripte installieren jetzt exakt diese.

3. **`train_custom.py` (und andere Skripte): hartcodierte Pfade** wie
   `/home/hannelore-hanftee/finetune-project/...` – funktionierte nur auf genau diesem
   einen Rechner/Benutzerkonto.
   *Fix:* `PROJECT_ROOT = Path(__file__).resolve().parent.parent`, alles relativ dazu.

4. **`train_custom.py`: `attn_implementation="flash_attention_2"` hartcodiert.**
   Stürzte sofort ab, wenn `flash-attn` nicht installiert war (laut eigener README
   "kann Probleme machen auf RTX 3060" und in `requirements.txt` auskommentiert – also der
   Normalfall).
   *Fix:* Laufzeit-Erkennung, automatischer Fallback auf PyTorch SDPA.

5. **`train_custom.py`: `logging.FileHandler('./logs/training.log')`** ohne dass der
   Ordner `logs/` je erstellt wurde → Absturz beim allerersten Log-Aufruf.
   *Fix:* `LOGS_DIR.mkdir(parents=True, exist_ok=True)` vor dem Logging-Setup.

6. **TRL-API-Inkompatibilität.** Je nach installierter TRL-Version (siehe Punkt 2) erwartet
   `SFTTrainer` entweder `tokenizer=`/`dataset_text_field=`/`max_seq_length=` direkt als
   Kwargs (alte API) *oder* ein `SFTConfig`-Objekt mit `processing_class=`/`max_length=`
   (aktuelle API). Der ursprüngliche Code passte nur zur alten API und wäre mit der in
   `setup_host_linux.sh` installierten neueren TRL-Version sofort mit einem `TypeError`
   abgestürzt.
   *Fix:* `train_custom.py` prüft die installierte TRL-Version zur Laufzeit
   (`inspect.signature`) und baut Trainer-Argumente entsprechend adaptiv auf.

7. **`train.py`: `--resume`/`--debug` waren No-Ops.** Wurden entgegengenommen, aber nie
   an das eigentliche Trainingsskript weitergereicht.
   *Fix:* Werden jetzt als echte CLI-Flags an `train_custom.py` durchgereicht; `--resume`
   sucht automatisch den letzten Checkpoint.

8. **Doppelte, widersprüchliche Skripte:** `prepare_data.py` vs. `prepare_data_ultra.py`,
   `merge_all.py` vs. `merge_all_v2.py`. Der Orchestrator rief teils die falsche/alte
   Variante auf, mit doppeltem, kaputtem Aufruf von `prepare_data.py` (einmal ohne
   Pflicht-Argumente → Fehler, einmal korrekt).
   *Fix:* Je ein kanonisches Skript, Duplikate entfernt, ein sauberer Aufruf.

9. **`config.yaml` vs. README: Modellgröße.** README sprach durchgehend von Qwen2.5-**7B**,
   `config.yaml`/`train_custom.py` nutzten faktisch Qwen2.5-**3B**.
   *Fix:* Durchgängig 3B (passt am komfortabelsten in 12GB VRAM); 7B bleibt per
   `FT_BASE_MODEL`-Umgebungsvariable weiterhin ansteuerbar (im README dokumentiert).

10. **`config.yaml`: widersprüchliche Validation-Strategie.** `val_set_size: 0.05` UND ein
    explizites `val.jsonl`-Dataset gleichzeitig gesetzt; `eval_steps`/`save_steps` gesetzt,
    aber `eval_strategy`/`save_strategy: "epoch"` ignorierte diese komplett.
    *Fix:* Konsistent `eval_strategy`/`save_strategy: "steps"` mit den passenden
    `eval_steps`/`save_steps`; `val_set_size` entfernt (explizites `val.jsonl` reicht).

11. **`requirements.txt` installierte zusätzlich Axolotl**, obwohl `train_custom.py` laut
    eigenem Docstring "bypasses Axolotl dependency hell" – Axolotl bringt eigene,
    abweichende Versionsanforderungen an transformers/peft/trl mit → Konfliktquelle.
    *Fix:* Axolotl entfernt; `config.yaml` bleibt als reine Referenz/Dokumentation nutzbar,
    falls jemand Axolotl separat (eigenes venv) nutzen möchte.

12. **`requirements_host.txt`: `huggingface-hub==0.25.0` gepinnt**, obwohl
    `transformers==4.56.2` eine deutlich neuere `huggingface-hub`-Version voraussetzt →
    Resolver-/Import-Konflikt.
    *Fix:* `huggingface-hub`/`safetensors` bewusst nur mit Mindestversion (`>=`) statt
    exakt gepinnt, damit `pip` automatisch eine kompatible Version wählt.

## 🟡 Stabilität / Architektur

13. **AdaLoRA statt LoRA.** AdaLoRA (dynamischer Rang) in Kombination mit 4-bit-QLoRA +
    Gradient Checkpointing ist eine in der Community bekanntermaßen fragile Kombination
    und bringt bei einer Domain-Adaption dieser Größenordnung kaum messbaren Vorteil.
    *Fix:* Standard-`LoraConfig` (r=64, alpha=128) – deutlich besser getestet, stabiler.

14. **Kein echtes Chat-Template.** `train_custom.py` baute den ChatML-String manuell per
    String-Concatenation zusammen, statt `tokenizer.apply_chat_template()` zu nutzen –
    fehleranfällig bei Sonderzeichen/zukünftigen Template-Änderungen.
    *Fix:* Nutzt jetzt `tokenizer.apply_chat_template()`.

15. **`merge_lora` in `train.py` rief `axolotl merge-lora` auf**, obwohl das Projekt gar
    kein Axolotl-Training mehr durchführt (Custom-Script) – hätte nie funktioniert.
    *Fix:* Eigenständiges PEFT-basiertes Merge (`PeftModel.merge_and_unload()`).

## 🟢 Datenqualität

16. **`prepare_data.py`: "Zusammenfassungen" waren nur abgeschnittener Originaltext**
    (`chunk[:2000] + "..."`). Das trainiert das Modell darauf, Text zu kopieren statt ihn
    zu verstehen/zusammenzufassen – irreführend, weil es wie eine Fähigkeit aussieht, die
    gar nicht vorhanden ist.
    *Fix:* Ehrliches Format ("Erkläre mir Thema X" → Originaltext als Fachantwort), ohne
    eine nicht vorhandene Zusammenfassungs-Fähigkeit vorzutäuschen. Echte Zusammenfassungen
    bräuchten eine zusätzliche LLM-API – siehe README "Bekannte Einschränkungen".

## Unverändert gelassen

- `data/*.jsonl` (bereits valide, 6266/127 Beispiele geprüft (historischer V13-Snapshot)).
- `collect_cannabis.py`, `collect_law.py`, `collect_gardening.py`, `collect_science.py`:
  Logik unverändert (nutzten bereits relative Pfade), da funktional in Ordnung – Hinweis:
  Web-Scraping ist von Natur aus fragil gegenüber Änderungen an den Ziel-Websites.

---

# Changelog v2: Nach dem ersten erfolgreichen Trainingslauf gefunden

Diese Bugs kamen erst zum Vorschein, nachdem das erste Training tatsächlich durchgelaufen
war und die Ergebnisse inhaltlich geprüft wurden (`quick_test.py`).

## 🔴 Windows-spezifisch

17. **`train_custom.py`: Emoji-Logging crasht unter Windows.** `cmd.exe` nutzt standardmäßig
    `cp1252` statt UTF-8 - jede Log-Zeile mit Emoji (🚀📁💾 etc.) löste einen
    `UnicodeEncodeError` im Logging-Handler aus (nicht fatal, aber flutete die Konsole mit
    Tracebacks).
    *Fix:* UTF-8 wird jetzt erzwungen (`sys.stdout/stderr.reconfigure`), `FileHandler` mit
    explizitem `encoding="utf-8"`.

18. **`train_custom.py`: `--resume` schlägt mit `torch < 2.6` fehl.** Neuere `transformers`-
    Versionen blockieren `torch.load()` (beim Laden des Optimizer-Zustands) aus
    Sicherheitsgründen (CVE-2025-32434), wenn `torch < 2.6` installiert ist - kryptischer
    Traceback tief in `trainer.train()`.
    *Fix:* Frühzeitige, klare Fehlermeldung mit konkretem Fix-Befehl statt kryptischem
    Traceback. `requirements.txt` fordert jetzt `torch>=2.6`.

19. **`setup_host_windows.bat`: unescapte Klammer bricht den `cmd.exe`-Parser.** Die Zeile
    `echo Fuer bitsandbytes (QLoRA) werden C++ Build Tools benoetigt` innerhalb eines
    `if (...)`-Blocks verwirrte `cmd.exe`s Klammer-Zählung (schließende Klammer nach
    "QLoRA" wurde als Ende des if-Blocks fehlinterpretiert) - Folge: Skript brach mit
    Syntaxfehler ab bzw. übersprang die restlichen Setup-Schritte.
    *Fix:* Klammern escaped (`^(QLoRA^)`).

20. **`train.py`: `run_merge_lora()` nutzte `device_map="cpu"`.** Merged ein 3B-Modell auf
    der CPU statt der GPU, obwohl es in BF16 (~6GB) komfortabel in 12GB VRAM passt - unnötig
    langsam (mehrere Minuten statt Sekunden), wirkte wie ein hängender Prozess.
    *Fix:* `device_map="cuda"` falls verfügbar, Modell wird erst vor dem Speichern auf
    CPU verschoben.

## 🟡 Datenqualität: irreführende/halluzinierte Inhalte

21. **`collect_gardening.py`: `"Quelle: {url}"` im Trainingsziel trainierte Halluzinationen.**
    Jede Gärtnern-Antwort endete mit einer angehängten Wikipedia-URL. Ein 3B-Modell lernt
    daraus nur das *Format* "Antwort endet mit URL", kann sich die tatsächliche URL aber
    nicht zuverlässig merken - Ergebnis im Praxistest: plausibel aussehende, aber falsche
    URL (`.../wiki/Terpenen` statt korrekt `.../wiki/Terpene`) angehängt an eine
    Cannabis-Antwort, die gar nicht aus dieser Quelle stammte.
    *Fix:* `"Quelle: {url}"` wird nicht mehr ins Trainingsziel geschrieben (nur noch in
    `metadata`, für eigene Nachschlagezwecke außerhalb des Modells). `cleanup_source_urls.py`
    bereinigt rückwirkend 780 bereits betroffene Beispiele in den vorhandenen Dateien.

22. **PubMed-Abfragen in `collect_cannabis.py` UND `collect_science.py` lieferten 0 Treffer.**
    `"open access[filter]"` bzw. `"pmc[filter]"` sind keine gültigen PubMed-Suchfeld-Tags.
    PubMeds ESearch liefert bei ungültigen Tags nicht etwa einen Fehler, sondern lautlos
    0 Treffer - deshalb war `pubmed_raw.jsonl` in beiden Domains komplett leer, ohne dass
    das im Log auffiel.
    *Fix:* Korrektes Tag laut PubMed User Guide: `"free full text[sb]"`. Zusätzlich wird
    jetzt bei 0 Treffern eine Warnung mit der PubMed-Trefferzahl ausgegeben.

23. **`collect_law.py`: `"cang"` ist kein gültiger URL-Slug auf gesetze-im-internet.de.**
    "CanG" ist nur der umgangssprachliche Sammelbegriff für das Mantelgesetz - es existiert
    keine eigene Seite dafür. Die tatsächlichen Einzelgesetze heißen **KCanG**
    (Konsumcannabisgesetz, Slug `kcang`) und **MedCanG** (Slug `medcang`, war bereits
    korrekt). Der `cang`-Eintrag lieferte vermutlich 0 Inhalt (fiel bereits vorher als
    "⚠️ Keine Daten / Fehler" im Log auf, wurde aber nicht behoben).
    *Fix:* `"cang"` durch korrektes `"kcang"` ersetzt.

24. **`collect_cannabis.py`: EMCDDA-"Zusammenfassungen" waren hartcodierte Textbausteine,
    kein echter Seiteninhalt.** `fetch_emcdda_reports()` lud nie tatsächlich die Report-Seiten,
    sondern nur eine manuelle Titel/URL-Liste; die "Antwort" im Trainingsbeispiel war ein
    fest einprogrammierter Platzhaltersatz ("Für Deutschland relevant: CanG (2024)...").
    *Fix:* `fetch_emcdda_reports()` lädt jetzt echte Seiteninhalte (Absätze via
    BeautifulSoup) statt eines Templates.

25. **`collect_cannabis.py`: Quelle `german_bfarm` war definiert, aber nie abgerufen.**
    Tote Konfiguration in `SOURCES`, trug 0 Beispiele zum Datensatz bei.
    *Fix:* Neue Funktion `fetch_bfarm_reports()`, wird jetzt tatsächlich in `main()`
    aufgerufen.

## 🟢 Strukturell: Domain-Ungleichgewicht

26. **Kein Mechanismus gegen extreme Domain-Ungleichgewichte im Datensatz.** Reale Zahlen vor
    dem Fix: Programmieren 35,6%, Philosophie/Ethik 33,6% (beide vermutlich aus eigenen
    hochgeladenen Dokumenten), Wissenschaft 20,4%, Gärtnern 6,1%, Recht 4,1%,
    **Cannabis 0,05% (3 von 6393 Beispielen)**. Das Modell hatte für die dünn besetzten
    Domains praktisch kein Trainingssignal - im Quick-Test zeigte sich das u.a. daran, dass
    eine CanG-Rechtsfrage in Richtung generisches EU-/Datenschutzrecht abdriftete.
    *Fix:* `train_custom.py` erkennt jetzt die Domain jedes Beispiels am System-Prompt und
    dupliziert unterrepräsentierte Domains (gedeckelt, siehe README "Domain-Balancing im
    Detail"), sodass jede Domain mindestens 8% eines Trainings-Epochs ausmacht - unabhängig
    davon, wie viele Rohdaten die Collectors tatsächlich geliefert haben. Ergänzend:
    `analyze_domains.py` (neu) macht die tatsächliche Verteilung jederzeit sichtbar, bevor
    man Trainingszeit investiert.

## Neue Hilfsskripte

- **`scripts/analyze_domains.py`** - zeigt Domain- und Feinthema-Verteilung in
  `data/train.jsonl`/`val.jsonl` (z.B. wie viele Recht-Beispiele tatsächlich CanG-spezifisch
  sind vs. generisches EU-Recht).
- **`scripts/cleanup_source_urls.py`** - einmaliges Cleanup für Bug #21, entfernt bereits
  vorhandene `"Quelle: {url}"`-Anhänge rückwirkend aus den Trainingsdaten.
- **`scripts/quick_test.py`** - lädt den LoRA-Adapter direkt (ohne Merge/GGUF) und testet
  ein paar Beispielfragen aus verschiedenen Domains, bevor man Zeit in Merge/Quantize steckt.

---

# Changelog v3: Emoji-Crash in den Collector-Skripten

27. **Alle `collect_*.py`, `merge_all.py`, `run_all_collectors.py`, `prepare_data.py`,
    `analyze_domains.py`, `cleanup_source_urls.py`, `quick_test.py`: derselbe
    Windows-Emoji-Crash wie Bug #17, aber ungefixt.** Der Fix aus Changelog v2 wurde nur in
    `train_custom.py` eingebaut - alle anderen Skripte crashten weiterhin sofort beim ersten
    `print()` mit Emoji, sobald ihre Ausgabe umgeleitet/abgefangen wurde (z.B. durch
    `run_all_collectors.py`, das jeden Collector per `subprocess.run(capture_output=True)`
    aufruft). Hintergrund: Python nutzt für *direkte* Konsolenausgabe unter Windows seit
    Version 3.6 automatisch UTF-8 (PEP 528), aber für *umgeleitete/abgefangene* Ausgabe
    (Pipes, wie bei `subprocess.run` mit `capture_output=True`) fällt es auf die
    Windows-Codepage zurück (meist `cp1252` auf deutschen Systemen) - daher lief
    `run_all_collectors.py` selbst direkt im Terminal anfangs fehlerfrei, brach dann aber
    bei jedem aufgerufenen Collector-Skript sofort ab.
    *Fix:* (a) `PYTHONIOENCODING=utf-8` wird jetzt in der `env` jedes `subprocess`-Aufrufs
    gesetzt (`run_all_collectors.py`, `train.py`s Merge-/Quantize-/Training-Aufrufe), (b)
    zusätzlich erzwingt jedes einzelne Skript UTF-8 für `sys.stdout`/`sys.stderr` beim
    Start, damit es auch bei direktem oder in eine Datei umgeleitetem Aufruf robust ist.

---

# Changelog v4: Encoding-Bug hatte noch eine zweite Hälfte

28. **`run_all_collectors.py`/`train.py`: Eltern-Prozess las UTF-8-Ausgabe der Kindprozesse
    weiterhin mit `cp1252`.** Changelog v3 fixte, dass die Collector-Skripte (Kindprozesse)
    korrekt UTF-8 *schreiben* - aber `subprocess.run(..., text=True)` im aufrufenden
    Elternprozess (`run_all_collectors.py`) nutzte beim *Zurücklesen* der Pipe weiterhin die
    Windows-Standardcodepage (`cp1252`), da `text=True` ohne explizites `encoding="utf-8"`
    auf die Locale-Einstellung des Elternprozesses zurückfällt - unabhängig davon, was der
    Kindprozess tatsächlich geschrieben hat. Symptom: `UnicodeDecodeError` in einem internen
    `_readerthread` von `subprocess.run`. Der Thread stirbt zwar nur im Hintergrund (der
    Hauptablauf lief scheinbar weiter, "✅ ERFOLGREICH"), aber dadurch wird die
    Ausgabe-Pipe nicht mehr geleert - bei Domains mit viel Ausgabe (z.B. Wissenschaft mit
    vielen PubMed/arXiv-Log-Zeilen) lief die Pipe voll und der Kindprozess blockierte beim
    Schreiben, wirkte wie ein Hänger.
    *Fix:* `encoding="utf-8", errors="replace"` explizit an allen `subprocess.run`/`Popen`-
    Aufrufen gesetzt, die Ausgabe im Textmodus einlesen (`run_all_collectors.py`, sowie
    `train.py`s `subprocess.Popen` für den eigentlichen (ggf. stundenlangen) Trainingslauf -
    war vom selben Bug betroffen, auch wenn es dort noch nicht aufgefallen war).

## 2026-09-04 – Große Quellenbasis / RAG-Pipeline
- `config/source_catalog.yaml` ergänzt: 114 kuratierte zusätzliche Quellen in 9 Themengebieten (historischer Katalogstand; der aktuelle Katalog umfasst 123 Einträge).
- `scripts/collect_supplemental.py` ergänzt: bounded HTML/PDF crawler + GitHub Tree/Raw collector; keine GitHub-Navigationsseiten.
- `scripts/prepare_supplemental.py` ergänzt: provenance-erhaltende QLoRA-Beispiele ohne erfundene Fakten.
- `scripts/build_rag_corpus.py` ergänzt: deduplizierter RAG-Korpus unter `data/rag/rag_chunks.jsonl`.
- Master-Runner integriert Supplemental-Collector und RAG-Build; `--supplemental-pages` steuert Breite, `--supplemental-deep` erhöht Tiefe.
- Einzelne nicht erreichbare Quellen sind non-fatal; der Lauf beendet nicht mehr wegen eines einzelnen blockierten Hosts.
- Merge erkennt `programming` -> `programmieren` und `military_*` -> `military`.
- `SOURCE_RESEARCH.md` dokumentiert Quellen, Autorität und vorgesehene Nutzung.

---

# Historischer Changelog v14.1: Domain-Duplikate, Gärtnern-Fehltreffer, Recht-Sackgasse

29. **Domain-Label-Duplikate im finalen Audit/Balancing.** Verschiedene Collector-
    Generationen taggen dieselben Inhalte mit unterschiedlichen `metadata['domain']`-
    Werten: `programming` (Supplemental, englischer Katalog-Key) vs. `programmieren`
    (älterer Collector, deutscher System-Prompt) - identisch für `science`/
    `wissenschaft` und `philosophy_ethics`/`philosophie_ethik`. Wurden als ZWEI
    getrennte Domains gezählt (z.B. "programming": 4340 UND "programmieren": 2201 im
    selben Report) - kein Datenverlust, aber verwirrende Berichterstattung und
    potenziell falsches Domain-Balancing, falls eine der beiden Teilmengen für sich
    genommen unter die Balancing-Schwelle fällt, obwohl die kombinierte Menge längst
    ausreichend wäre.
    *Fix:* `DOMAIN_ALIASES`-Tabelle in `audit_dataset.py` UND `merge_all.py`
    (letzteres hatte bereits `programming`/`military_general`-Aliase, aber nicht für
    `science`/`philosophy_ethics` - jetzt an beiden Stellen vollständig und synchron).

30. **`collect_gardening.py`: "Kräuteranbau" ist kein Wikipedia-Artikeltitel.**
    Die Volltextsuche wich auf "Ricola" (die Hustenbonbon-Marke) aus - ein
    Trainingsbeispiel bekam dadurch einen thematisch falschen Inhalt.
    *Fix:* Ersetzt durch **"Kräutergarten"** (echter, eigenständiger deutscher
    Wikipedia-Artikel, keine Überschneidung mit dem bereits vorhandenen Eintrag
    "Heilpflanzen"). Zusätzlich "Heilpflanzen" (Plural, scheiterte komplett, kein
    Fallback-Treffer) auf den echten Titel **"Heilpflanze"** (Singular) korrigiert.

31. **`collect_law.py`: gesetze-im-internet.de blockiert automatisierten Zugriff
    (robots.txt) - kein Parser-Bug.** Alle 20 Gesetze scheiterten mit "0 Abschnitte",
    obwohl der Server HTTP 200 zurückgab. Verifiziert durch einen direkten
    Abruf-Versuch, der explizit mit "Site disallows automated access" abgelehnt
    wurde. **Empfehlung: nicht versuchen zu umgehen** (anderer User-Agent, Browser-
    Fingerprint-Spoofing o.ä.) - das würde eine bewusste Zugriffsbeschränkung der
    Seite missachten.
    Geprüfte Alternative `recht.bund.de` ist **kein Ersatz**: laut eigener FAQ der
    Seite ist recht.bund.de nur das chronologische Verkündungsblatt einzelner
    Änderungsgesetze: "Die aktuelle Fassung eines Gesetzes... finden Sie auf
    www.gesetze-im-internet.de" (Zitat von recht.bund.de selbst).
    *Empfohlener Weg für echten Gesetzestext:* Einzelne PDFs manuell herunterladen
    (z.B. `gesetze-im-internet.de/bgb/BGB.pdf` - manueller Download ist von der
    robots.txt-Sperre nicht betroffen, die gilt nur für automatisiertes Crawlen)
    und über `scripts/prepare_data.py` verarbeiten - analog zum bereits etablierten
    Muster für andere blockierte Quellen (RHS, siehe Changelog v3/v4). Ausführliche
    Dokumentation dazu jetzt direkt im Docstring von `fetch_law_gesetze_im_internet()`,
    damit das nicht in einer zukünftigen Session erneut als "Parser-Bug" fehldiagnostiziert wird.

## v14.1 – Rechtsdaten + Domain-Balance

- `prepare_data.py`: juristische Trainingsprompts variiert und auf konkrete §-/Artikel-Einheiten ausgerichtet.
- Juristische Beispiele erhalten zusätzliche Provenienz-Metadaten (`source_file`, `document`, `document_type`, `content_basis`, `temporal_status`). `temporal_status=unknown` behauptet ausdrücklich keinen Rechtsstand.
- `merge_all.py`: vorhandene v13-Trainingsdaten werden einmalig über `data/legacy/` übernommen, statt beim nächsten Merge verloren zu gehen.
- Offensichtlich beschädigte, extrem lange Base64-artige Altbeispiele werden beim Legacy-Import verworfen.
- Fine-Tuning-Domain-Balance auf `target_per_domain: 800` umgestellt: große Domänen werden begrenzt, kleine bis maximal 4x hochgesampelt. RAG-Daten bleiben vollständig.
- RAG-Korpus nach der erneuten Aufbereitung der 33 vorhandenen Rechts-PDFs neu gebaut.
- Validiert: JSONL/Schema OK, Train/Val-Leakage 0, Self-Test OK, Python Compile OK.
- Das vorhandene `finetune-project-v12-CHATGPT_CLAUDE-merged.zip` bleibt unverändert als ZIP im Projekt.


# Changelog V16 – Dokumentation, Host-Setup und aktuelle Kompatibilitätslage

**2026-09-09**

Die technische Pipeline war bereits auf Core-Collector, Supplemental-Quellen, RAG, Audit, QLoRA und robustes Fehlerhandling erweitert worden. Die Projektdokumentation enthielt jedoch noch mehrere historische V13/V14-Angaben.

## Dokumentations-Synchronisierung

- `README.md` vollständig auf den aktuellen V16-Funktionsumfang aktualisiert.
- historische Trainingszahlen aus früheren Versionen entfernt bzw. ausdrücklich als Snapshot gekennzeichnet.
- `QUICKSTART_HOST.md` auf die tatsächlich vorhandenen Skripte und aktuellen Setup-Schritte synchronisiert.
- `ARMA3_MILITARY_PIPELINE.md` auf Core-/Supplemental-Trennung, Milsim/Militär-Abgrenzung und non-fatal Source Failures aktualisiert.
- `SOURCE_RESEARCH.md` direkt aus dem aktuellen `config/source_catalog.yaml` synchronisiert; damit sind die 9 Supplemental-Domains und ihre aktuell konfigurierten Quellen dokumentiert.
- historische Changelog-Einträge bleiben erhalten, werden aber nicht mehr als aktueller Projektzustand präsentiert.

## Requirements / Host Setup

- `requirements.txt` beschreibt jetzt eine aktuelle, bewusst begrenzte Kompatibilitäts-Lane statt historischer TRL-0.x/Transformers-4.x-Beispiele.
- aktuelle Release-Stände wurden gegen die offiziellen PyPI-Projektseiten geprüft: Transformers 5.16.1, TRL 1.12.0, PEFT 0.20.0, bitsandbytes 0.50.2, Accelerate 1.14/1.15 und Datasets 5.0.1 sind inzwischen veröffentlicht. Die Requirements bleiben absichtlich innerhalb einer stabilen Major-/Minor-Lane, damit zukünftige Releases nicht ungeprüft in die Trainingsumgebung rutschen.
- PyTorch/CUDA wird über den CUDA-12.6-Index installiert; das ist für die dokumentierte RTX-3060-Zielplattform geeignet.
- Host-Setup-Skripte wurden von den veralteten CUDA-12.1-/alten Versionshinweisen auf die aktuelle Requirements-Strategie synchronisiert.

## Aktueller Snapshot

Der mitgelieferte V16-Snapshot enthält aktuell 6.488 Train- und 304 Validation-Beispiele. Diese Zahlen sind keine feste Zielgröße: nach einem neuen Collect/Merge-Lauf ändern sie sich abhängig von erreichbaren Quellen, eigenen Dokumenten und der konfigurierten Balance.

## Verifikation

- Python-Skripte werden mit `python -m compileall -q scripts` geprüft.
- `python scripts/self_test.py` prüft Parser, Chunking und Metadaten offline.
- `python scripts/audit_dataset.py` bleibt die verbindliche letzte Qualitätsprüfung vor dem Training.
