@echo off
REM One-time office PC setup: Python, RapidOCR, Tesseract, VC++ runtime.
setlocal
cd /d "%~dp0"
echo Installing office scan tools (needs Wi-Fi this once)...

where winget >nul 2>&1
if not errorlevel 1 (
  winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
  winget install -e --id Microsoft.VCRedist.2015+.x64 --accept-package-agreements --accept-source-agreements
  winget install -e --id UB-Mannheim.TesseractOCR --accept-package-agreements --accept-source-agreements
) else (
  echo winget is missing. Install Python 3.12 and Tesseract-OCR from their websites, then re-run this file.
)

set "PY=python"
where py >nul 2>&1 && set "PY=py -3"
%PY% -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install --upgrade pip
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-engine.txt
backend\.venv\Scripts\python.exe backend\ensure_engine.py
backend\.venv\Scripts\python.exe backend\manage.py migrate --noinput
backend\.venv\Scripts\python.exe backend\manage.py seed_data
echo.
echo Done. Close this window, then start OVC CaseFile again.
pause
endlocal
