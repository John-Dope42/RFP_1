#!/bin/bash
# ============================================================
# Fine-Tuning Projekt - Linux/macOS Host Setup
# Für RTX 3060 12GB / CUDA 12.6
# Führe aus: chmod +x setup_host_linux.sh && ./setup_host_linux.sh
# ============================================================

set -e  # Exit on error

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}  Fine-Tuning Setup für RTX 3060 12GB${NC}"
echo -e "${BLUE}  Projekt: Qwen2.5-3B QLoRA Domain-Expert${NC}"
echo -e "${BLUE}============================================================${NC}"
echo

# 1. Python prüfen
echo -e "${YELLOW}[1/6]${NC} Prüfe Python Installation..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}OK:${NC} $PYTHON_VERSION gefunden"
    
    # Check version >= 3.10 and <= 3.12 (3.13+ not recommended for ML yet)
    PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
    PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
    if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
        echo -e "${RED}FEHLER:${NC} Python 3.10+ erforderlich, gefunden: $PYTHON_VERSION"
        echo "Installiere Python 3.10-3.14 von https://python.org oder via Paketmanager"
        exit 1
    elif [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -gt 12 ]; then
        echo -e "${YELLOW}WARNUNG:${NC} Python $PY_MINOR ist sehr neu - empfohlen: 3.10 bis 3.14 (stable)"
    fi
else
    echo -e "${RED}FEHLER:${NC} python3 nicht gefunden!"
    echo "Installiere: sudo apt install python3 python3-venv python3-pip (Ubuntu/Debian)"
    echo "          oder: brew install python3 (macOS)"
    exit 1
fi

# 2. Git prüfen
echo -e "${YELLOW}[2/6]${NC} Prüfe Git..."
if command -v git &> /dev/null; then
    echo -e "${GREEN}OK:${NC} $(git --version) gefunden"
else
    echo -e "${YELLOW}WARNUNG:${NC} Git nicht gefunden (optional, aber empfohlen)"
    echo "Installiere: sudo apt install git (Ubuntu/Debian) oder brew install git (macOS)"
fi

# 3. Build Tools prüfen (für bitsandbytes)
echo -e "${YELLOW}[3/6]${NC} Prüfe Build Tools..."
if command -v g++ &> /dev/null; then
    echo -e "${GREEN}OK:${NC} g++ gefunden: $(g++ --version | head -1)"
elif command -v clang++ &> /dev/null; then
    echo -e "${GREEN}OK:${NC} clang++ gefunden: $(clang++ --version | head -1)"
else
    echo -e "${YELLOW}WARNUNG:${NC} Kein C++ Compiler gefunden"
    echo "Für bitsandbytes (QLoRA) werden Build Tools benötigt"
    echo "Ubuntu/Debian: sudo apt install build-essential"
    echo "macOS: xcode-select --install"
    echo "Fedora: sudo dnf groupinstall 'Development Tools'"
fi

# 4. CUDA prüfen
echo -e "${YELLOW}[4/6]${NC} Prüfe CUDA / NVIDIA Treiber..."
if command -v nvidia-smi &> /dev/null; then
    echo -e "${GREEN}OK:${NC} nvidia-smi gefunden"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    CUDA_VERSION=$(nvidia-smi | grep "CUDA Version" | sed 's/.*CUDA Version: \([0-9.]*\).*/\1/')
    echo "CUDA Version: $CUDA_VERSION"
    
    # Check if CUDA >= 12.1
    CUDA_MAJOR=$(echo $CUDA_VERSION | cut -d. -f1)
    CUDA_MINOR=$(echo $CUDA_VERSION | cut -d. -f2)
    if [ "$CUDA_MAJOR" -lt 12 ] || ([ "$CUDA_MAJOR" -eq 12 ] && [ "$CUDA_MINOR" -lt 1 ]); then
        echo -e "${YELLOW}WARNUNG:${NC} CUDA < 12.1 erkannt. Empfohlen: CUDA 12.6+"
        echo "Installiere CUDA 12.6+ von https://developer.nvidia.com/cuda-toolkit"
    fi
else
    echo -e "${RED}FEHLER:${NC} nvidia-smi nicht gefunden!"
    echo "NVIDIA Treiber installieren: https://www.nvidia.com/Download/index.aspx"
    echo "CUDA Toolkit 12.1+: https://developer.nvidia.com/cuda-toolkit"
    exit 1
fi

# 5. Virtuelle Umgebung erstellen
echo -e "${YELLOW}[5/6]${NC} Erstelle virtuelle Umgebung (venv)..."
if [ -d "venv" ]; then
    echo -e "${YELLOW}venv existiert bereits - überspringe${NC}"
else
    python3 -m venv venv
    echo -e "${GREEN}OK:${NC} venv erstellt"
fi

# 5. Dependencies installieren
echo -e "${YELLOW}[5/6]${NC} Installiere Dependencies (CUDA 12.6 / RTX 3060)..."
echo "Dies kann 5-10 Minuten dauern..."

source venv/bin/activate
python -m pip install --upgrade pip

echo "Installiere alle Abhängigkeiten aus requirements.txt (einzige Quelle der Wahrheit für Versionen)..."
pip install -r requirements.txt

# Flash Attention 2 (optional, für schnelleres Training - Build kann fehlschlagen, ist ok)
echo "Versuche Flash-Attention 2 zu installieren (optional)..."
pip install flash-attn==2.5.8 --no-build-isolation || echo "  -> flash-attn Build fehlgeschlagen, kein Problem: Training nutzt automatisch SDPA-Fallback."

# Test Installation
echo
echo -e "${YELLOW}[Test]${NC} Teste Installation..."
python -c "
import torch
print('PyTorch:', torch.__version__)
print('CUDA:', torch.version.cuda)
print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'KEINE GPU!')
import transformers
print('Transformers:', transformers.__version__)
import peft
print('PEFT:', peft.__version__)
import bitsandbytes
print('bitsandbytes: OK')
"

echo
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  SETUP ERFOLGREICH ABGESCHLOSSEN!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo
echo -e "${BLUE}Nächste Schritte:${NC}"
echo "  cd finetune-project"
echo "  source venv/bin/activate"
echo "  python scripts/train_custom.py"
echo
echo -e "${YELLOW}Training dauert ca. 3-5 Stunden auf RTX 3060 12GB.${NC}"
echo
echo "Bei Problemen: Logs prüfen, GPU-Treiber/CUDA-Version checken."