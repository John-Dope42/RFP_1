@echo on
REM ============================================================
REM  Fine-Tuning Projekt - Windows Host Setup
REM  Fuer RTX 3060 12GB / CUDA 12.6
REM  Fuehre als Administrator aus (Rechtsklick -> Als Admin ausfuehren)
REM ============================================================

echo.
echo ============================================================
echo  Fine-Tuning Setup fuer RTX 3060 12GB
echo  Projekt: Qwen2.5-3B QLoRA Domain-Expert
echo ============================================================
echo.

echo Druecke eine Taste, um fortzufahren...
pause >nul

REM 1. Python pruefen
echo.
echo [1/6] Pruefe Python Installation...
python --version 2>nul
if errorlevel 1 (
    echo.
    echo FEHLER: Python nicht gefunden!
    echo Bitte Python 3.10-3.14 von https://python.org installieren
    echo WICHTIG: Haken bei "Add Python to PATH" setzen!
    echo.
    pause
    exit /b 1
)
echo OK: Python gefunden

REM 2. Git pruefen (optional)
echo.
echo [2/6] Pruefe Git...
git --version 2>nul
if errorlevel 1 (
    echo WARNUNG: Git nicht gefunden (optional, aber empfohlen)
    echo Download: https://git-scm.com/download/win
) else (
    echo OK: Git gefunden
)

REM 3. Visual Studio Build Tools pruefen (fuer bitsandbytes)
echo.
echo [3/6] Pruefe Visual Studio Build Tools...
where cl.exe 2>nul
if errorlevel 1 (
    echo WARNUNG: Visual Studio Build Tools nicht gefunden
    echo Fuer bitsandbytes ^(QLoRA^) werden C++ Build Tools benoetigt
    echo Installiere: Visual Studio Installer -> "Desktop-Entwicklung mit C++"
    echo Oder: winget install Microsoft.VisualStudio.2022.BuildTools
) else (
    echo OK: Build Tools gefunden
)

REM 4. Virtuelle Umgebung erstellen
echo.
echo [4/6] Erstelle virtuelle Umgebung (venv)...
if exist venv (
    echo venv existiert bereits - ueberspringe
) else (
    python -m venv venv
    if errorlevel 1 (
        echo.
        echo FEHLER: Konnte venv nicht erstellen
        echo Pruefe ob Python korrekt installiert ist
        echo.
        pause
        exit /b 1
    )
    echo OK: venv erstellt
)

REM 5. Abhaengigkeiten installieren
echo.
echo [5/6] Installiere Dependencies (CUDA 12.6 / RTX 3060)...
echo Dies kann 5-10 Minuten dauern...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo.
    echo FEHLER: Konnte venv nicht aktivieren
    pause
    exit /b 1
)
python -m pip install --upgrade pip
if errorlevel 1 (
    echo FEHLER: pip upgrade fehlgeschlagen
    pause
    exit /b 1
)

echo Installiere alle Abhaengigkeiten aus requirements.txt (einzige Quelle der Wahrheit fuer Versionen)...
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo FEHLER bei Installation der Python-Pakete!
    echo Pruefe: Internetverbindung, CUDA 12.6+ Treiber, Visual Studio Build Tools
    echo.
    pause
    exit /b 1
)
echo OK: Alle Dependencies installiert

echo Versuche Flash-Attention 2 zu installieren (optional, Build kann fehlschlagen)...
pip install flash-attn==2.5.8 --no-build-isolation
if errorlevel 1 (
    echo WARNUNG: flash-attn Build fehlgeschlagen - kein Problem, Training nutzt automatisch SDPA-Fallback.
)

REM 6. Test
echo.
echo [6/6] Teste Installation...
python -c "import torch; print('PyTorch:', torch.__version__); print('CUDA:', torch.version.cuda); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'KEINE GPU'); import transformers; print('Transformers:', transformers.__version__); import peft; print('PEFT:', peft.__version__)"
if errorlevel 1 (
    echo.
    echo FEHLER: Installationstest fehlgeschlagen!
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  SETUP ERFOLGREICH ABGESCHLOSSEN!
echo ============================================================
echo.
echo Naechste Schritte:
echo   1. cd finetune-project
echo   2. venv\Scripts\activate.bat
echo   3. python scripts\train_custom.py
echo.
echo Training dauert ca. 2-3 Stunden auf RTX 3060 12GB (Qwen 3B).
echo.
echo Druecke eine Taste, um das Fenster zu schliessen...
pause