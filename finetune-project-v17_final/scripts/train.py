#!/usr/bin/env python3
"""
Training Launcher für Qwen2.5-3B + QLoRA.
Handhabt: Environment-Checks, Resume, Debug/TensorBoard, Merge, GGUF-Quantize.
"""

import subprocess
import sys
import os
from pathlib import Path
import argparse

if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MERGED_DIR = PROJECT_ROOT / "output" / "merged_model_qwen2.5-3b"
ADAPTER_DIR = PROJECT_ROOT / "output" / "qwen2.5-3b-domain-expert-de"


def check_gpu():
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, check=True,
        )
        print("🖥️  GPU Status:")
        for line in result.stdout.strip().split("\n"):
            print(f"   {line}")
    except Exception as e:
        print(f"⚠️  GPU-Check fehlgeschlagen: {e}")
        print("   (Ohne CUDA-GPU kann QLoRA-Training nicht laufen.)")


def check_disk_space(path: str = "."):
    import shutil
    total, used, free = shutil.disk_usage(path)
    print(f"💾 Disk: {free // (1024**3)} GB frei von {total // (1024**3)} GB")


def check_python_deps():
    missing = []
    for mod in ["torch", "transformers", "peft", "trl", "bitsandbytes", "datasets"]:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        print(f"⚠️  Fehlende Python-Pakete: {', '.join(missing)}")
        print("   -> pip install -r requirements.txt")
    else:
        print("✅ Alle Kern-Pakete installiert.")


def run_training(resume: bool = False, debug: bool = False) -> int:
    """Startet das Training-Skript und reicht --resume/--debug tatsächlich durch."""
    cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / "train_custom.py")]
    if resume:
        cmd.append("--resume")
    if debug:
        cmd.append("--debug")

    print(f"🚀 Starte Training: {' '.join(cmd)}")
    print(f"📁 Working Dir: {PROJECT_ROOT}")

    env = os.environ.copy()
    env.update({
        "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True,max_split_size_mb:128",
        "TOKENIZERS_PARALLELISM": "false",
        "OMP_NUM_THREADS": "4",
        "PYTHONIOENCODING": "utf-8",  # Windows: cp1252 bei umgeleiteter Ausgabe vermeiden
    })

    process = subprocess.Popen(
        cmd, cwd=str(PROJECT_ROOT), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
        encoding="utf-8", errors="replace",
    )
    try:
        for line in process.stdout:
            print(line.rstrip())
        process.wait()
    except KeyboardInterrupt:
        print("\n⏹️  Training unterbrochen (Ctrl+C)")
        process.terminate()
        return 130

    if process.returncode == 0:
        print("\n✅ Training erfolgreich abgeschlossen!")
    else:
        print(f"\n❌ Training fehlgeschlagen (Exit Code: {process.returncode})")
    return process.returncode


def run_merge_lora() -> bool:
    """Merged den LoRA-Adapter direkt via PEFT (kein Axolotl nötig)."""
    print(f"🔗 Merge LoRA-Adapter ({ADAPTER_DIR}) in Base Model...")
    script = f"""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base_model_id = "Qwen/Qwen2.5-3B-Instruct"
adapter_dir = r"{ADAPTER_DIR}"
merged_dir = r"{MERGED_DIR}"

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Lade Base Model (FP16/BF16, unquantisiert) auf {{device}}...")
base_model = AutoModelForCausalLM.from_pretrained(
    base_model_id, torch_dtype=torch.bfloat16, device_map=device
)
tokenizer = AutoTokenizer.from_pretrained(adapter_dir)

print("Lade LoRA-Adapter und merge...")
model = PeftModel.from_pretrained(base_model, adapter_dir)
model = model.merge_and_unload()
model = model.to("cpu")  # vor dem Speichern zurück auf CPU (spart VRAM beim Save)

print("Speichere merged model...")
model.save_pretrained(merged_dir, safe_serialization=True)
tokenizer.save_pretrained(merged_dir)
print("Fertig.")
"""
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=str(PROJECT_ROOT),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    if result.returncode == 0:
        print(f"✅ Merge erfolgreich: {MERGED_DIR}")
        return True
    print("❌ Merge fehlgeschlagen.")
    return False


def run_quantize_gguf(quant_type: str = "Q4_K_M"):
    """Konvertiert merged Model zu GGUF (via llama.cpp)."""
    llama_cpp_dir = Path.home() / "llama.cpp"
    quantize_bin = llama_cpp_dir / "llama-quantize"
    convert_script = llama_cpp_dir / "convert_hf_to_gguf.py"
    output_file = PROJECT_ROOT / "output" / f"qwen2.5-3b-domain-expert-de-{quant_type.lower()}.gguf"
    fp16_gguf = PROJECT_ROOT / "output" / "qwen2.5-3b-domain-expert-de-f16.gguf"

    if not quantize_bin.exists() or not convert_script.exists():
        print(f"⚠️  llama.cpp nicht vollständig gefunden unter {llama_cpp_dir}")
        print("   Installiere: git clone https://github.com/ggml-org/llama.cpp && cd llama.cpp && make GGML_CUDA=1 -j$(nproc)")
        print("   und: pip install -r llama.cpp/requirements.txt")
        return

    print(f"📦 Schritt 1/2: Konvertiere merged Model → GGUF (f16)...")
    conv_cmd = [sys.executable, str(convert_script), str(MERGED_DIR), "--outfile", str(fp16_gguf), "--outtype", "f16"]
    gguf_env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(conv_cmd, env=gguf_env)
    if result.returncode != 0:
        print("❌ HF→GGUF Konvertierung fehlgeschlagen.")
        return

    print(f"📦 Schritt 2/2: Quantisiere zu {quant_type}...")
    quant_cmd = [str(quantize_bin), str(fp16_gguf), str(output_file), quant_type]
    result = subprocess.run(quant_cmd, env=gguf_env)
    if result.returncode == 0:
        print(f"✅ GGUF erstellt: {output_file}")
    else:
        print("❌ Quantisierung fehlgeschlagen.")


def main():
    parser = argparse.ArgumentParser(description="Fine-Tuning Launcher für Qwen2.5-3B + QLoRA")
    parser.add_argument("--config", default="config.yaml", help="(Nur relevant falls Axolotl direkt genutzt wird)")
    parser.add_argument("--resume", action="store_true", help="Vom letzten Checkpoint fortsetzen")
    parser.add_argument("--debug", action="store_true", help="TensorBoard-Logging aktivieren")
    parser.add_argument("--merge", action="store_true", help="LoRA nach Training mergen")
    parser.add_argument("--quantize", action="store_true", help="Nach Merge zu GGUF quantisieren")
    parser.add_argument("--quant-type", default="Q4_K_M", choices=["Q4_K_M", "Q5_K_M", "Q6_K", "Q8_0"])
    parser.add_argument("--check-only", action="store_true", help="Nur Checks, kein Training")
    parser.add_argument("--merge-only", action="store_true", help="Nur mergen (kein Training)")
    args = parser.parse_args()

    print("=" * 60)
    print("🎯 FINE-TUNING LAUNCHER - Qwen2.5-3B + QLoRA")
    print("=" * 60)

    check_gpu()
    check_disk_space()
    check_python_deps()

    if args.check_only:
        print("\n✅ Checks abgeschlossen.")
        return

    if args.merge_only:
        run_merge_lora()
        if args.quantize:
            run_quantize_gguf(args.quant_type)
        return

    rc = run_training(resume=args.resume, debug=args.debug)
    if rc != 0:
        sys.exit(rc)

    if args.merge:
        if run_merge_lora() and args.quantize:
            run_quantize_gguf(args.quant_type)


if __name__ == "__main__":
    main()
