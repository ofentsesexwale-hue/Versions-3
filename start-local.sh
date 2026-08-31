#!/usr/bin/env bash
# Fully local start: no internet after Python/Node are already installed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/backend"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements-runtime.txt
fi
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py seed_data || true
if [ ! -f "$ROOT/frontend/build/index.html" ]; then
  cd "$ROOT/frontend"
  yarn install --offline 2>/dev/null || yarn install
  CI=false yarn build
fi
cd "$ROOT/backend"
.venv/bin/python manage.py runserver 127.0.0.1:8001 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT
cd "$ROOT"
python3 preview_server.py
