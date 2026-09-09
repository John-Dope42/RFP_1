#!/usr/bin/env python3
"""
Quick-Test: Lädt Base-Model + LoRA-Adapter direkt (4-bit, kein Merge/GGUF nötig)
und lässt ein paar Beispielfragen aus verschiedenen Domains beantworten.

Speichern unter: finetune-project/scripts/quick_test.py
Ausführen aus dem venv:
    python scripts/quick_test.py
"""

import sys
import torch
from pathlib import Path
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASE_MODEL = "Qwen/Qwen2.5-3B-Instruct"
ADAPTER_DIR = PROJECT_ROOT / "output" / "qwen2.5-3b-domain-expert-de"

# Ein paar Testfragen über verschiedene Domains, damit man sieht ob das
# Fine-Tuning gegriffen hat (nicht nur "irgendwie funktioniert das Modell").
TEST_CASES = [
    {
        "system": "Du bist ein Experte für deutsches und europäisches Recht.",
        "user": "Was ist der Unterschied zwischen dem alten BtMG und dem neuen CanG in Bezug auf Cannabis-Besitz?",
    },
    {
        "system": "Du bist ein Cannabis-Zucht-Experte & Sommelier.",
        "user": "Welche Terpene sind typisch für ein Myrcen-dominantes Sortenprofil und wie wirkt sich das auf den Effekt aus?",
    },
    {
        "system": "Du bist ein Gärtnermeister / Permakultur-Experte.",
        "user": "Wie stelle ich das ideale C:N-Verhältnis für meinen Kompost her?",
    },
    {
        "system": "Du bist ein Senior Software Engineer.",
        "user": "Was ist der Unterschied zwischen Gradient Checkpointing und normalem Training bei LLMs?",
    },
]


def main():
    if not ADAPTER_DIR.exists():
        print(f"❌ Adapter nicht gefunden: {ADAPTER_DIR}")
        print("   Erst Training abschließen (python train.py).")
        return

    print(f"🔤 Lade Tokenizer von {ADAPTER_DIR}...")
    tokenizer = AutoTokenizer.from_pretrained(str(ADAPTER_DIR))

    print(f"🧠 Lade Base Model ({BASE_MODEL}) in 4-bit...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )

    print(f"🔗 Lade LoRA-Adapter von {ADAPTER_DIR}...")
    model = PeftModel.from_pretrained(base_model, str(ADAPTER_DIR))
    model.eval()

    print("\n" + "=" * 70)
    print("STARTE TESTS")
    print("=" * 70)

    for i, case in enumerate(TEST_CASES, 1):
        messages = [
            {"role": "system", "content": case["system"]},
            {"role": "user", "content": case["user"]},
        ]
        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=300,
                temperature=0.7,
                top_p=0.9,
                do_sample=True,
                repetition_penalty=1.1,
                pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
            )

        response = tokenizer.decode(
            output_ids[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
        )

        print(f"\n--- Test {i}/{len(TEST_CASES)} ---")
        print(f"System:  {case['system']}")
        print(f"Frage:   {case['user']}")
        print(f"Antwort: {response.strip()}")
        print("-" * 70)

    print("\n✅ Quick-Test abgeschlossen.")


if __name__ == "__main__":
    main()
