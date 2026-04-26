@echo off
setlocal
title Build — Sistema Antiplagio Portable (Single EXE)
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║   Sistema Antiplagio v1.2  —  Build Single EXE      ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

:: ── 1. Dipendenze ─────────────────────────────────────────────────────────
echo [1/4] Installazione dipendenze...
pip install -q opencv-python pywin32 numpy insightface onnxruntime pyinstaller
if errorlevel 1 ( echo ERRORE pip & pause & exit /b 1 )

:: ── 2. Pre-download modello InsightFace ───────────────────────────────────
echo [2/4] Download modello InsightFace (buffalo_sc)...
python -c "from insightface.app import FaceAnalysis; a=FaceAnalysis(name='buffalo_sc',providers=['CPUExecutionProvider']); a.prepare(ctx_id=0,det_size=(640,640)); print('  OK')"
if errorlevel 1 ( echo ERRORE modello & pause & exit /b 1 )

:: ── 3. Copia modelli nella cartella progetto per il bundle ────────────────
echo [3/4] Copia modelli InsightFace nel bundle...
if exist "%USERPROFILE%\.insightface" (
    xcopy /E /I /Y /Q "%USERPROFILE%\.insightface" ".insightface" >nul
    echo   Modelli copiati in .insightface\
) else (
    echo   ATTENZIONE: .insightface non trovata.
    echo   I modelli saranno scaricati al primo avvio.
)

:: ── 4. Build EXE onefile (UPX disabilitato per i modelli AI) ──────────────
echo [4/4] Compilazione EXE unico...
echo   Nota: UPX disabilitato - evita corruzione modelli ONNX.
echo   Il file sara' piu' grande ma stabile.
pyinstaller antiplagio.spec --clean --noconfirm
if errorlevel 1 ( echo ERRORE PyInstaller & pause & exit /b 1 )

echo.
if exist "dist\SistemaAntiplagio.exe" (
    for %%A in ("dist\SistemaAntiplagio.exe") do (
        set /a SIZE=%%~zA / 1048576
    )
    echo  ╔══════════════════════════════════════════════════════╗
    echo  ║  COMPLETATO                                          ║
    echo  ║                                                      ║
    echo  ║  File: dist\SistemaAntiplagio.exe                    ║
    echo  ║                                                      ║
    echo  ║  Portable: copia il solo .exe ovunque e avvialo.     ║
    echo  ╚══════════════════════════════════════════════════════╝
) else (
    echo ERRORE: EXE non trovato in dist\
)
echo.
pause
