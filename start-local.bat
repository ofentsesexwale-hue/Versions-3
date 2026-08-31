@echo off
REM Fully local start on Windows. Install Python 3.12+ and Node LTS once, then this needs no internet.
cd /d %~dp0backend
if not exist .venv (
  py -3 -m venv .venv
  .venv\Scripts\pip install -r requirements-runtime.txt
)
.venv\Scripts\python manage.py migrate --noinput
if not exist ..\frontend\build\index.html (
  cd /d %~dp0frontend
  call yarn install
  set CI=false
  call yarn build
)
cd /d %~dp0backend
start "OVC API" .venv\Scripts\python manage.py runserver 127.0.0.1:8001
cd /d %~dp0
python preview_server.py
