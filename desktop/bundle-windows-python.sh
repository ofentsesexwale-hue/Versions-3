#!/usr/bin/env bash
# Download a portable Windows Python and install the CaseFile engine into it.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/desktop/vendor/python-win"
URL="https://github.com/astral-sh/python-build-standalone/releases/download/20260325/cpython-3.12.13+20260325-x86_64-pc-windows-msvc-install_only_stripped.tar.gz"
WHEELS="$ROOT/desktop/vendor/win-wheels"

if [ -x "$DEST/python.exe" ] && [ -d "$DEST/Lib/site-packages/django" ]; then
  echo "Windows Python + CaseFile engine already bundled at $DEST"
  exit 0
fi

mkdir -p "$ROOT/desktop/vendor"
rm -rf "$DEST" "$WHEELS"
mkdir -p "$WHEELS"
TMP="$(mktemp -d)"
echo "Downloading Windows Python…"
curl -fsSL "$URL" -o "$TMP/python-win.tar.gz"
tar -xzf "$TMP/python-win.tar.gz" -C "$TMP"
mv "$TMP/python" "$DEST"
rm -rf "$TMP"

echo "Downloading Windows engine wheels…"
"$ROOT/backend/.venv/bin/python" -m pip download \
  -r "$ROOT/backend/requirements-engine.txt" \
  -d "$WHEELS" \
  --python-version 3.12 \
  --platform win_amd64 \
  --only-binary=:all:

SITE="$DEST/Lib/site-packages"
mkdir -p "$SITE"
echo "Installing engine into Windows Python (offline wheels)…"
shopt -s nullglob
for whl in "$WHEELS"/*.whl; do
  unzip -qo "$whl" -d "$SITE"
done

test -d "$SITE/django"
echo "Bundled Python at $DEST"
ls -lah "$DEST/python.exe"
du -sh "$DEST"
