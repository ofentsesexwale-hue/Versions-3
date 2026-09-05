@echo off
REM Daily launcher for the office PC (8 GB). Uses backend\.venv where torch already works.
REM Prefer this if the portable .exe is missing torch / too heavy to rebuild.
setlocal
cd /d "%~dp0"

set "USE_SQLITE=true"
set "HF_HOME=%USERPROFILE%\.cache\huggingface"
set "HUGGINGFACE_HUB_CACHE=%USERPROFILE%\.cache\huggingface\hub"
set "TRANSFORMERS_CACHE=%USERPROFILE%\.cache\huggingface\hub"

if not exist "backend\.venv\Scripts\python.exe" (
  echo backend\.venv is missing.
  echo Install Python 3.12, then:
  echo   cd backend
  echo   py -3.12 -m venv .venv
  echo   .venv\Scripts\python.exe -m pip install -r requirements-engine.txt
  echo   .venv\Scripts\python.exe -m pip install torch==2.14.0+cpu torchvision==0.29.0+cpu --index-url https://download.pytorch.org/whl/cpu
  echo   .venv\Scripts\python.exe -m pip install transformers==4.49.0
  pause
  exit /b 1
)

backend\.venv\Scripts\python.exe -c "import torch, torchvision; from transformers import TrOCRProcessor; print(torch.__version__, torchvision.__version__, 'TrOCR OK')" 1>nul 2>nul
if errorlevel 1 (
  echo Installing matched CPU torch stack into backend\.venv ...
  echo Do NOT pip into %%TEMP%% portable .exe extracts — rebuild the .exe instead.
  backend\.venv\Scripts\python.exe -m pip install torch==2.14.0+cpu torchvision==0.29.0+cpu --index-url https://download.pytorch.org/whl/cpu
  backend\.venv\Scripts\python.exe -m pip install transformers==4.49.0 pillow-heif opencv-python-headless
)

if exist backend\ensure_engine.py backend\.venv\Scripts\python.exe backend\ensure_engine.py
backend\.venv\Scripts\python.exe backend\manage.py migrate --noinput
backend\.venv\Scripts\python.exe backend\manage.py seed_data

if not exist frontend\build\index.html (
  echo frontend\build is missing. Build the UI once, or use a packed OVC-CaseFile.exe.
  pause
  exit /b 1
)

start "OVC API" backend\.venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8001 --noreload
backend\.venv\Scripts\python.exe preview_server.py
endlocal
