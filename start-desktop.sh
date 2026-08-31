#!/usr/bin/env bash
# Double-click / terminal launcher for the native OVC CaseFile window.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export USE_SQLITE=true
if [ ! -x "$ROOT/backend/.venv/bin/python" ]; then
  python3 -m venv "$ROOT/backend/.venv"
  "$ROOT/backend/.venv/bin/pip" install -r "$ROOT/backend/requirements-runtime.txt"
fi
"$ROOT/backend/.venv/bin/python" "$ROOT/backend/manage.py" migrate --noinput
"$ROOT/backend/.venv/bin/python" "$ROOT/backend/manage.py" seed_data || true
if [ ! -f "$ROOT/frontend/build/index.html" ]; then
  cd "$ROOT/frontend"
  yarn install --offline 2>/dev/null || yarn install
  CI=false yarn build
fi
cd "$ROOT/desktop"
if [ ! -d node_modules/electron ]; then
  yarn install
fi
exec yarn start
