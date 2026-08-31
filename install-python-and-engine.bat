@echo off
REM One-time office PC setup: install Python and the CaseFile engine for THIS folder.
setlocal
cd /d "%~dp0"
echo Installing Python 3.12 (if missing) and the CaseFile engine...
where python >nul 2>&1
if errorlevel 1 (
  winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
)
set "PY=python"
where py >nul 2>&1 && set "PY=py -3"
%PY% -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install --upgrade pip
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-engine.txt
backend\.venv\Scripts\python.exe backend\manage.py migrate --noinput
backend\.venv\Scripts\python.exe backend\manage.py seed_data
echo.
echo Done. Close this window, then double-click OVC-CaseFile.exe again.
pause
endlocal
