<# 
.SYNOPSIS
    Fine-Tuning Setup für RTX 3060 12GB / CUDA 12.1
    Projekt: Qwen2.5-3B QLoRA Domain-Expert

.DESCRIPTION
    Prüft Python, Git, Visual Studio Build Tools, CUDA, erstellt venv,
    installiert Dependencies (PyTorch, Transformers, PEFT, TRL, bitsandbytes, etc.)

.NOTES
    Als Administrator ausführen (Rechtsklick -> "Als Administrator ausführen")
    Ausführungspolicy muss RemoteSigned oder Unrestricted sein:
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
#>

# ============================================================
# Fine-Tuning Setup für RTX 3060 12GB / CUDA 12.1
# Projekt: Qwen2.5-3B QLoRA Domain-Expert
# ============================================================

Write-Host "`n============================================================"
Write-Host "  Fine-Tuning Setup für RTX 3060 12GB"
Write-Host "  Projekt: Qwen2.5-3B QLoRA Domain-Expert"
Write-Host "============================================================`n"

Write-Host "Drücke eine Taste, um fortzufahren..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

# ============================================================
# Hilfsfunktionen
# ============================================================
function Write-Step($num, $total, $msg) {
    Write-Host "`n[$num/$total] $msg"
}

function Write-OK($msg) {
    Write-Host "  [OK] $msg" -ForegroundColor Green
}

function Write-Warn($msg) {
    Write-Host "  [WARNUNG] $msg" -ForegroundColor Yellow
}

function Write-Error($msg) {
    Write-Host "  [FEHLER] $msg" -ForegroundColor Red
}

function Test-Command($cmd, $args = @()) {
    try {
        $result = & $cmd @args 2>$null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

# ============================================================
# 1. Python prüfen
# ============================================================
Write-Step 1 6 "Prüfe Python Installation..."
if (Test-Command "python" "--version") {
    $pyVer = python --version 2>$null
    Write-OK "Python gefunden: $pyVer"
    
    # Version prüfen (3.10-3.12 empfohlen)
    $ver = [System.Version](python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if ($ver.Major -eq 3 -and $ver.Minor -ge 10 -and $ver.Minor -le 12) {
        Write-OK "Python Version $ver wird unterstützt"
    } else {
        Write-Warn "Python $ver - empfohlen: 3.10 bis 3.12"
    }
} else {
    Write-Error "Python nicht gefunden!"
    Write-Host "Bitte Python 3.10-3.12 von https://python.org installieren"
    Write-Host "WICHTIG: Haken bei 'Add Python to PATH' setzen!"
    Read-Host "Drücke Enter zum Beenden"
    exit 1
}

# ============================================================
# 2. Git prüfen (optional)
# ============================================================
Write-Step 2 6 "Prüfe Git..."
if (Test-Command "git" "--version") {
    $gitVer = git --version
    Write-OK "Git gefunden: $gitVer"
} else {
    Write-Warn "Git nicht gefunden (optional, aber empfohlen)"
    Write-Host "Download: https://git-scm.com/download/win"
}

# ============================================================
# 3. Visual Studio Build Tools prüfen (für bitsandbytes)
# ============================================================
Write-Step 3 6 "Prüfe Visual Studio Build Tools..."
if (Test-Command "where" "cl.exe") {
    Write-OK "Build Tools gefunden (cl.exe verfügbar)"
} else {
    Write-Warn "Visual Studio Build Tools nicht gefunden"
    Write-Host "Für bitsandbytes (QLoRA) werden C++ Build Tools benötigt"
    Write-Host "Option 1: winget install Microsoft.VisualStudio.2022.BuildTools"
    Write-Host "Option 2: Visual Studio Installer -> 'Desktop-Entwicklung mit C++' anhaken"
    Write-Host "Download: https://visualstudio.microsoft.com/downloads/"
    Write-Host "`nNach Installation: Setup erneut ausführen!"
}

# ============================================================
# 4. CUDA / NVIDIA Treiber prüfen
# ============================================================
Write-Step 4 6 "Prüfe CUDA / NVIDIA Treiber..."
if (Test-Command "nvidia-smi") {
    $gpuInfo = nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    Write-OK "GPU erkannt: $($gpuInfo.Trim())"
    
    $cudaVer = nvidia-smi | Select-String "CUDA Version" | ForEach-Object { $_ -replace '.*CUDA Version:\s*([\d.]+).*', '$1' }
    if ($cudaVer) {
        Write-Host "  CUDA Version: $cudaVer"
        if ([version]$cudaVer -lt [version]"12.1") {
            Write-Warn "CUDA < 12.1 erkannt. Empfohlen: CUDA 12.1+"
        }
    }
} else {
    Write-Error "nvidia-smi nicht gefunden!"
    Write-Host "NVIDIA Treiber installieren: https://www.nvidia.com/Download/index.aspx"
    Write-Host "CUDA Toolkit 12.1+: https://developer.nvidia.com/cuda-toolkit"
    Read-Host "Drücke Enter zum Beenden"
    exit 1
}

# ============================================================
# 5. Virtuelle Umgebung erstellen
# ============================================================
Write-Step 5 6 "Erstelle virtuelle Umgebung (venv)..."
if (Test-Path "venv") {
    Write-Host "  venv existiert bereits - überspringe"
} else {
    Write-Host "  Erstelle venv..."
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Konnte venv nicht erstellen"
        Read-Host "Drücke Enter zum Beenden"
        exit 1
    }
    Write-OK "venv erstellt"
}

# ============================================================
# 6. Dependencies installieren
# ============================================================
Write-Step 6 6 "Installiere Dependencies (CUDA 12.1 / RTX 3060)..."
Write-Host "  Dies kann 5-10 Minuten dauern..."

# venv aktivieren
& .\venv\Scripts\Activate.ps1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Konnte venv nicht aktivieren"
    Read-Host "Drücke Enter zum Beenden"
    exit 1
}

Write-Host "  Upgrade pip..."
python -m pip install --upgrade pip -q
if ($LASTEXITCODE -ne 0) {
    Write-Error "pip upgrade fehlgeschlagen"
    Read-Host "Drücke Enter zum Beenden"
    exit 1
}

Write-Host "  Installiere alle Abhängigkeiten aus requirements.txt (einzige Quelle der Wahrheit für Versionen)..."
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Error "Installation der Python-Pakete fehlgeschlagen!"
    Write-Host "Prüfe: Internetverbindung, CUDA 12.1+ Treiber, Visual Studio Build Tools"
    Read-Host "Drücke Enter zum Beenden"
    exit 1
}

# Flash Attention 2 (optional, für schnelleres Training)
Write-Host "  Installiere Flash Attention 2..."
pip install flash-attn==2.5.8 --no-build-isolation
if ($LASTEXITCODE -ne 0) {
    Write-Warn "Flash Attention 2 Installation fehlgeschlagen (optional, Training funktioniert auch ohne)"
}
Write-OK "Alle Dependencies installiert"

# ============================================================
# 7. Test
# ============================================================
Write-Host "`n============================================================"
Write-Host "  INSTALLATIONSTEST"
Write-Host "============================================================"
$test = python -c "
import torch
print('PyTorch:', torch.__version__)
print('CUDA:', torch.version.cuda)
print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'KEINE GPU')
import transformers
print('Transformers:', transformers.__version__)
import peft
print('PEFT:', peft.__version__)
"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Installationstest fehlgeschlagen!"
    Read-Host "Drücke Enter zum Beenden"
    exit 1
}

Write-Host "`n============================================================"
Write-Host "  SETUP ERFOLGREICH ABGESCHLOSSEN!"
Write-Host "============================================================`n"
Write-Host "Nächste Schritte:"
Write-Host "  1. cd finetune-project"
Write-Host "  2. .\venv\Scripts\Activate.ps1"
Write-Host "  3. python scripts\train_custom.py"
Write-Host "`nTraining dauert ca. 2-3 Stunden auf RTX 3060 12GB (Qwen 3B)."
Write-Host "`nDrücke Enter zum Beenden..."
Read-Host