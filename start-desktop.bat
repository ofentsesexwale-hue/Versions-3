@echo off
REM Double-click this file on Windows to open OVC CaseFile as a desktop window (not a browser).
setlocal
cd /d "%~dp0"
set USE_SQLITE=true
if not exist backend\.venv\Scripts\python.exe (
  py -3 -m venv backend\.venv
  backend\.venv\Scripts\pip install -r backend\requirements-runtime.txt
)
backend\.venv\Scripts\python backend\manage.py migrate --noinput
backend\.venv\Scripts\python backend\manage.py seed_data
if not exist frontend\build\index.html (
  cd frontend
  call yarn install
  set CI=false
  call yarn build
  cd ..
)
cd desktop
if not exist node_modules\electron (
  call yarn install
)
call yarn start
