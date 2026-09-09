#!/usr/bin/env python3
"""
Custom Fine-Tuning Script mit TRL SFTTrainer.
Trainiert Qwen2.5-3B-Instruct mit QLoRA (4-bit NF4) auf RTX 3060 12GB.

Warum kein Axolotl? -> weniger Dependency-Konflikte, volle Kontrolle,
transparente Fehlermeldungen. config.yaml bleibt als Referenz/Alternative
für den, der lieber Axolotl direkt nutzen will (siehe README).

Warum LoRA statt AdaLoRA? -> AdaLoRA (dynamischer Rang) ist in Kombination
mit 4-bit-Quantisierung + Gradient Checkpointing bekanntermaßen fragil
(u.a. Probleme mit dem "rank allocator" während Backprop durch gecheckpointete
Layer) und bringt bei einer Domain-Adaption dieser Größenordnung kaum
messbaren Vorteil gegenüber klassischem LoRA. Standard-LoRA ist die von
Community und Bibliotheken am besten getestete Kombination mit QLoRA.
"""

import os
import sys
import glob
import json
import math
import random
import inspect
import dataclasses
import logging
import argparse
from pathlib import Path
from collections import Counter

# Windows-Konsolen (cmd.exe) nutzen standardmäßig cp1252, das keine Emojis
# darstellen kann -> jede Log-Zeile mit Emoji crasht sonst den StreamHandler
# mit UnicodeEncodeError (nicht fatal, aber flutet die Konsole mit Tracebacks).
# UTF-8 erzwingen, wo möglich.
if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
    EarlyStoppingCallback,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
import trl
from trl import SFTTrainer

try:
    from trl import SFTConfig
    HAS_SFTCONFIG = True
except ImportError:
    HAS_SFTCONFIG = False

# ============================================================
# PORTABLE PFADE (kein hartcodierter Username mehr!)
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent

MODEL_ID = os.environ.get("FT_BASE_MODEL", "Qwen/Qwen2.5-3B-Instruct")
DATA_PATH = str(PROJECT_ROOT / "data" / "train.jsonl")
VAL_PATH = str(PROJECT_ROOT / "data" / "val.jsonl")
OUTPUT_DIR = str(PROJECT_ROOT / "output" / "qwen2.5-3b-domain-expert-de")
LOGS_DIR = PROJECT_ROOT / "logs"

MAX_SEQ_LENGTH = 4096


def detect_attn_implementation() -> str:
    """Nutzt Flash-Attention 2 nur, wenn es wirklich installiert UND importierbar ist,
    sonst robuster Fallback auf SDPA (in PyTorch eingebaut, kein Extra-Build nötig)."""
    try:
        import flash_attn  # noqa: F401
        return "flash_attention_2"
    except ImportError:
        return "sdpa"


def build_lora_config() -> LoraConfig:
    return LoraConfig(
        r=64,
        lora_alpha=128,
        lora_dropout=0.05,
        # Aktuelle PEFT-Dokumentation empfiehlt für QLoRA-style Training
        # target_modules="all-linear", damit architekturspezifische Namen nicht
        # manuell gepflegt werden müssen.
        target_modules="all-linear",
        bias="none",
        task_type="CAUSAL_LM",
    )


def find_latest_checkpoint(output_dir: str):
    """Sucht den letzten Checkpoint für --resume."""
    ckpts = sorted(
        glob.glob(os.path.join(output_dir, "checkpoint-*")),
        key=lambda p: int(p.rsplit("-", 1)[-1]) if p.rsplit("-", 1)[-1].isdigit() else -1,
    )
    return ckpts[-1] if ckpts else None


def _base_training_kwargs(debug: bool) -> dict:
    """Argumente, die sowohl in TrainingArguments als auch in SFTConfig existieren
    (SFTConfig ist eine Subklasse von TrainingArguments in allen gängigen TRL-Versionen)."""
    return dict(
        output_dir=OUTPUT_DIR,
        num_train_epochs=3,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=16,
        learning_rate=2e-4,
        lr_scheduler_type="cosine",
        warmup_steps=50,
        optim="adamw_bnb_8bit",
        weight_decay=0.01,
        max_grad_norm=1.0,
        bf16=torch.cuda.is_available() and torch.cuda.is_bf16_supported(),
        fp16=torch.cuda.is_available() and not torch.cuda.is_bf16_supported(),
        tf32=True,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=50,
        save_strategy="steps",
        save_steps=100,
        save_total_limit=3,
        save_safetensors=True,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        seed=42,
        dataloader_num_workers=2,
        dataloader_pin_memory=True,
        remove_unused_columns=False,
        report_to=["tensorboard"] if debug else ["none"],
        logging_dir=str(LOGS_DIR / "tensorboard") if debug else None,
    )


def _filter_kwargs_for_dataclass(cls, kwargs: dict) -> dict:
    """Behält nur Keys, die die Ziel-Dataclass tatsächlich als Feld kennt.
    Notwendig, weil sich Feldnamen zwischen TRL-Versionen leicht unterscheiden
    (z.B. logging_dir=None ist in manchen Versionen nicht erlaubt)."""
    valid_fields = {f.name for f in dataclasses.fields(cls)}
    return {k: v for k, v in kwargs.items() if k in valid_fields and v is not None}


def build_training_config(debug: bool):
    """Baut TrainingArguments/SFTConfig versionsadaptiv.

    Hintergrund: Dieses Projekt hatte zwei widersprüchliche requirements-Dateien
    mit stark unterschiedlichen historischen TRL-Versionen. Ältere TRL-Versionen
    akzeptieren dataset_text_field/max_seq_length/tokenizer= direkt als SFTTrainer-Kwargs;
    neuere TRL-Versionen verlangen dafür ein SFTConfig-Objekt (Felder: dataset_text_field,
    max_length statt max_seq_length) und tokenizer= wurde zu processing_class= umbenannt.
    Damit das Skript nicht bei jedem TRL-Update erneut bricht, wird hier zur Laufzeit
    geprüft, was die installierte TRL-Version tatsächlich unterstützt.
    """
    base_kwargs = _base_training_kwargs(debug)

    if HAS_SFTCONFIG:
        cfg_fields = {f.name for f in dataclasses.fields(SFTConfig)}
        length_field = "max_length" if "max_length" in cfg_fields else "max_seq_length"
        extra = {
            "dataset_text_field": "text", "packing": False, length_field: MAX_SEQ_LENGTH,
            # Prompt-Completion: nur Completion-/Assistant-Tokens tragen zum Loss bei.
            "completion_only_loss": True,
        }
        kwargs = _filter_kwargs_for_dataclass(SFTConfig, {**base_kwargs, **extra})
        return SFTConfig(**kwargs)

    kwargs = _filter_kwargs_for_dataclass(TrainingArguments, base_kwargs)
    return TrainingArguments(**kwargs)


def build_trainer(model, tokenizer, train_dataset, val_dataset, training_config):
    """Baut den SFTTrainer versionsadaptiv (tokenizer= vs. processing_class=,
    dataset_text_field als Trainer-Kwarg vs. als Teil von SFTConfig)."""
    sft_params = inspect.signature(SFTTrainer.__init__).parameters

    trainer_kwargs = dict(
        model=model,
        args=training_config,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3, early_stopping_threshold=0.001)],
    )

    if "processing_class" in sft_params:
        trainer_kwargs["processing_class"] = tokenizer
    elif "tokenizer" in sft_params:
        trainer_kwargs["tokenizer"] = tokenizer

    if not HAS_SFTCONFIG:
        # Alte TRL-Version: dataset_text_field/max_seq_length/packing gehören
        # direkt in den Trainer statt in ein SFTConfig-Objekt.
        if "dataset_text_field" in sft_params:
            trainer_kwargs["dataset_text_field"] = "text"
        if "max_seq_length" in sft_params:
            trainer_kwargs["max_seq_length"] = MAX_SEQ_LENGTH
        if "packing" in sft_params:
            trainer_kwargs["packing"] = False

    return SFTTrainer(**trainer_kwargs)


# ============================================================
# DOMAIN-BALANCING
# ============================================================
# Erkennt die Domain jedes Beispiels am System-Prompt und sorgt dafür, dass
# JEDE Domain mindestens MIN_DOMAIN_FRACTION eines Trainings-Epochs ausmacht -
# unabhängig davon, wie viele Rohdaten die Collectors für diese Domain
# tatsächlich geliefert haben. Hintergrund: ohne diesen Schritt dominierten in
# der Praxis 2 von 6 Domains (Programmieren + Philosophie/Ethik) zusammen 69%
# des Datensatzes, während z.B. Cannabis nur 0,05% ausmachte (3 von 6393
# Beispielen) - das Modell hatte für diese Domain praktisch kein Trainingssignal.
# Unterrepräsentierte Domains werden bis zu einem Faktor MAX_OVERSAMPLE_FACTOR
# dupliziert (zyklisch, deterministisch geseedet). Dominante Domains werden
# NICHT gekürzt - es geht kein vorhandenes Beispiel verloren, es wird nur
# zusätzlich Gewicht auf die kleinen Domains gelegt.
DOMAIN_SIGNALS = {
    "recht_de_eu": ["experte für deutsches und europäisches recht", "experte für de/eu-recht"],
    "cannabis_zucht_sommelier": ["cannabis-zucht-experte"],
    "gaertnern": ["gärtnermeister", "permakultur-experte"],
    "wissenschaft": ["wissenschaftler mit breitem fachwissen"],
    "programmieren": ["senior software engineer"],
    "philosophie_ethik": ["experte für philosophie und ethik", "experte für philosophie/ethik"],
    "lifehacks_alltag": ["praktischer lebensberater"],
    "general": ["allwissender assistent"],
}
MIN_DOMAIN_FRACTION = 0.08
MAX_OVERSAMPLE_FACTOR = 15
BALANCE_SEED = 42


def detect_domain(example) -> str:
    for m in example.get("messages", []):
        if m.get("role") == "system":
            s = m["content"].lower()
            for domain, signals in DOMAIN_SIGNALS.items():
                if any(sig in s for sig in signals):
                    return domain
            return "unbekannt"
    return "unbekannt"


def balance_dataset_by_domain(dataset, logger):
    """Dupliziert Beispiele unterrepräsentierter Domains, bis jede Domain
    mindestens MIN_DOMAIN_FRACTION des (neuen, größeren) Datensatzes ausmacht.
    Gibt den balancierten Datensatz zurück (mehr Zeilen als vorher, keine
    weniger)."""
    rng = random.Random(BALANCE_SEED)

    domains = [detect_domain(ex) for ex in dataset]
    counts = Counter(domains)
    total_before = len(dataset)

    logger.info("📊 Domain-Verteilung VOR Balancing:")
    for d, c in counts.most_common():
        logger.info(f"     {d:28s} {c:5d} ({100*c/total_before:5.1f}%)")

    target_count = max(1, int(total_before * MIN_DOMAIN_FRACTION))

    indices_by_domain = {}
    for i, d in enumerate(domains):
        indices_by_domain.setdefault(d, []).append(i)

    selected_indices = list(range(total_before))
    for d, idxs in indices_by_domain.items():
        if len(idxs) >= target_count:
            continue
        factor = min(MAX_OVERSAMPLE_FACTOR, math.ceil(target_count / len(idxs)))
        capped_target = min(target_count, factor * len(idxs))
        needed = capped_target - len(idxs)
        if needed <= 0:
            continue
        shuffled = idxs[:]
        rng.shuffle(shuffled)
        extra = [shuffled[i % len(shuffled)] for i in range(needed)]
        selected_indices.extend(extra)

    rng.shuffle(selected_indices)
    balanced = dataset.select(selected_indices)

    domains_after = [detect_domain(ex) for ex in balanced]
    counts_after = Counter(domains_after)
    total_after = len(balanced)
    logger.info(f"📊 Domain-Verteilung NACH Balancing ({total_after} statt {total_before} Beispiele):")
    for d, c in counts_after.most_common():
        logger.info(f"     {d:28s} {c:5d} ({100*c/total_after:5.1f}%)")

    return balanced


# ============================================================
# DATA LOADING
# ============================================================
def example_domain(example):
    md = example.get("metadata") or {}
    d = md.get("domain", "general")
    if d.startswith("military."):
        return "military"
    if d.startswith("arma3"):
        return "arma3"
    if d in {"ai_ml", "physics", "climate", "neuroscience", "medicine", "statistics", "chemistry", "biology"}:
        return "wissenschaft"
    return d


def load_data(tokenizer, logger, domain_filter=None):
    """Lädt conversational Daten und wandelt sie in Prompt/Completion um.

    Das ist für Qwen2.5 robuster als assistant_only_loss auf einem reinen
    Chat-Template-Datensatz: TRL kann completion_only_loss zuverlässig anwenden,
    ohne dass das Qwen2.5-Template spezielle generation-Marker benötigt.
    """
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Trainingsdaten nicht gefunden: {DATA_PATH} -> zuerst run_all_collectors.py")
    if not os.path.exists(VAL_PATH):
        raise FileNotFoundError(f"Validierungsdaten nicht gefunden: {VAL_PATH}")
    train_dataset = load_dataset("json", data_files=DATA_PATH, split="train")
    val_dataset = load_dataset("json", data_files=VAL_PATH, split="train")

    def to_prompt_completion(example):
        msgs=example.get("messages", [])
        prompt=[m for m in msgs if m.get("role") != "assistant"]
        completion=[m for m in msgs if m.get("role") == "assistant"]
        if not prompt or not completion:
            raise ValueError("Jedes Beispiel braucht mindestens System/User-Prompt und eine Assistant-Completion.")
        return {"prompt": prompt, "completion": completion}

    train_dataset=train_dataset.map(to_prompt_completion, remove_columns=train_dataset.column_names)
    val_dataset=val_dataset.map(to_prompt_completion, remove_columns=val_dataset.column_names)
    logger.info("   Dataset: conversational Prompt/Completion; Loss nur auf Completion.")
    return train_dataset, val_dataset


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Custom QLoRA Training für Qwen2.5-3B")
    parser.add_argument("--resume", action="store_true", help="Vom letzten Checkpoint fortsetzen")
    parser.add_argument("--debug", action="store_true", help="TensorBoard-Logging aktivieren")
    parser.add_argument("--domain", default=None, help="Optional: nur eine Top-Level-Domain trainieren, z.B. arma3, military, wissenschaft")
    args = parser.parse_args()

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(str(LOGS_DIR / "training.log"), encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logger = logging.getLogger(__name__)

    if not torch.cuda.is_available():
        logger.error("❌ Keine CUDA-GPU gefunden. QLoRA-Training auf CPU ist nicht praktikabel.")
        sys.exit(1)

    attn_impl = detect_attn_implementation()
    logger.info("🚀 Starte QLoRA Fine-Tuning mit TRL SFTTrainer")
    logger.info(f"📁 Modell: {MODEL_ID}")
    logger.info(f"📁 Output: {OUTPUT_DIR}")
    logger.info(f"🧩 Attention-Implementierung: {attn_impl}")
    logger.info(f"🖥️  GPU: {torch.cuda.get_device_name(0)}")
    logger.info(f"💾 VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    logger.info("🔤 Lade Tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    logger.info("🧠 Lade Modell in 4-bit...")
    try:
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
            attn_implementation=attn_impl,
            torch_dtype=torch.bfloat16,
        )
    except (ImportError, ValueError) as e:
        if attn_impl == "flash_attention_2":
            logger.warning(f"⚠️  flash_attention_2 fehlgeschlagen ({e}), Fallback auf sdpa")
            model = AutoModelForCausalLM.from_pretrained(
                MODEL_ID,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True,
                attn_implementation="sdpa",
                torch_dtype=torch.bfloat16,
            )
        else:
            raise

    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    model = get_peft_model(model, build_lora_config())
    model.print_trainable_parameters()

    logger.info("📊 Lade Datasets...")
    train_dataset, val_dataset = load_data(tokenizer, logger, domain_filter=args.domain)
    logger.info(f"   Train: {len(train_dataset)} Beispiele")
    logger.info(f"   Val:   {len(val_dataset)} Beispiele")

    logger.info(f"🔧 TRL Version: {trl.__version__} (SFTConfig verfügbar: {HAS_SFTCONFIG})")
    training_config = build_training_config(debug=args.debug)
    trainer = build_trainer(model, tokenizer, train_dataset, val_dataset, training_config)

    resume_ckpt = None
    if args.resume:
        resume_ckpt = find_latest_checkpoint(OUTPUT_DIR)
        if resume_ckpt:
            # Neuere transformers-Versionen blockieren torch.load() beim Laden des
            # Optimizer-Zustands aus Sicherheitsgründen (CVE-2025-32434), wenn
            # torch < 2.6 installiert ist. Lieber hier klar abbrechen als einen
            # kryptischen Traceback tief in trainer.train() zu bekommen.
            torch_version = tuple(int(x) for x in torch.__version__.split("+")[0].split(".")[:2])
            if torch_version < (2, 6):
                logger.error(
                    f"❌ --resume benötigt torch >= 2.6 (installiert: {torch.__version__}), "
                    "da neuere transformers-Versionen das Laden des Optimizer-Zustands aus "
                    "Sicherheitsgründen sonst blockieren (CVE-2025-32434).\n"
                    "   Fix: pip install --upgrade torch torchvision torchaudio "
                    "--index-url https://download.pytorch.org/whl/cu126"
                )
                sys.exit(1)
            logger.info(f"⏯️  Setze fort von Checkpoint: {resume_ckpt}")
        else:
            logger.warning("⚠️  --resume gesetzt, aber kein Checkpoint gefunden. Starte neu.")

    logger.info("🏋️  Training läuft...")
    trainer.train(resume_from_checkpoint=resume_ckpt)

    logger.info("💾 Speichere LoRA-Adapter...")
    trainer.save_model()
    tokenizer.save_pretrained(OUTPUT_DIR)

    # Trainingsmetadaten für Reproduzierbarkeit sichern
    with open(Path(OUTPUT_DIR) / "training_meta.json", "w", encoding="utf-8") as f:
        json.dump({
            "base_model": MODEL_ID,
            "attn_implementation": attn_impl,
            "train_examples": len(train_dataset),
            "val_examples": len(val_dataset),
            "completion_only_loss": True,
            "lora_target_modules": "all-linear",
            "dataset_format": "conversational",
        }, f, indent=2, ensure_ascii=False)

    logger.info("✅ Training abgeschlossen!")
    logger.info(f"📁 LoRA-Adapter gespeichert unter: {OUTPUT_DIR}")
    logger.info("🔗 Nächster Schritt: python scripts/train.py --merge --quantize")


if __name__ == "__main__":
    main()
