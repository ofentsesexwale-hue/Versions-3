@echo off
REM Office window. No yarn. Uses backend\.venv (Django + RapidOCR).
setlocal
cd /d "%~dp0"
set USE_SQLITE=true
if not exist backend\.venv\Scripts\python.exe (
  echo Python venv is missing. Double-click OVC-CaseFile.exe instead, or install Python 3.12 and run:
  echo   cd backend
  echo   python -m venv .venv
  echo   .venv\Scripts\python.exe -m pip install -r requirements-engine.txt
  pause
  exit /b 1
)
backend\.venv\Scripts\python.exe -m pip install -q -r backend\requirements-engine.txt
if exist backend\ensure_engine.py backend\.venv\Scripts\python.exe backend\ensure_engine.py
backend\.venv\Scripts\python.exe backend\manage.py migrate --noinput
backend\.venv\Scripts\python.exe backend\manage.py seed_data
if not exist frontend\build\index.html (
  echo frontend\build is missing. Use OVC-CaseFile.exe instead of this bat file.
  pause
  exit /b 1
)
start "OVC API" backend\.venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8001
backend\.venv\Scripts\python.exe preview_server.py
endlocal
