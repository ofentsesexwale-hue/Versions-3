#!/usr/bin/env bash
# Build the native packages: Linux AppImage and, when Wine is available, a Windows .exe
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export USE_SQLITE=true
"$ROOT/backend/.venv/bin/python" "$ROOT/backend/manage.py" migrate --noinput || true
if [ ! -f "$ROOT/frontend/build/index.html" ] || [ "${REBUILD_UI:-}" = "1" ]; then
  cd "$ROOT/frontend"
  CI=false yarn build
fi
mkdir -p "$ROOT/desktop/icons"
cp -f "$ROOT/desktop/icons/icon-512.png" "$ROOT/desktop/icons/512x512.png" 2>/dev/null || true
cp -f "$ROOT/desktop/icons/icon-256.png" "$ROOT/desktop/icons/256x256.png" 2>/dev/null || true
cd "$ROOT/desktop"
yarn install
yarn pack:linux
if command -v wine >/dev/null 2>&1; then
  yarn pack:win || echo "Windows package skipped (Wine present but electron-builder failed)"
else
  echo "Wine not installed — Linux AppImage is in desktop/release/. On a Windows PC run: cd desktop && yarn pack:win"
fi
ls -lah "$ROOT/desktop/release" || true
