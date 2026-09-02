#!/usr/bin/env bash
# Download a portable Windows Python and install the CaseFile engine into it.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/desktop/vendor/python-win"
URL="https://github.com/astral-sh/python-build-standalone/releases/download/20260325/cpython-3.12.13+20260325-x86_64-pc-windows-msvc-install_only_stripped.tar.gz"
WHEELS="$ROOT/desktop/vendor/win-wheels"
SITE="$DEST/Lib/site-packages"

unzip_wheels() {
  mkdir -p "$SITE"
  shopt -s nullglob
  for whl in "$WHEELS"/*.whl; do
    unzip -qo "$whl" -d "$SITE"
  done
}

download_engine_wheels() {
  mkdir -p "$WHEELS"
  echo "Downloading Windows engine wheels…"
  "$ROOT/backend/.venv/bin/python" -m pip download \
    -r "$ROOT/backend/requirements-engine.txt" \
    -d "$WHEELS" \
    --python-version 3.12 \
    --platform win_amd64 \
    --only-binary=:all:
}

download_rapidocr_wheels() {
  mkdir -p "$WHEELS"
  echo "Downloading RapidOCR Windows wheels…"
  "$ROOT/backend/.venv/bin/python" -m pip download \
    rapidocr-onnxruntime onnxruntime pyclipper shapely pyyaml tqdm six protobuf flatbuffers
    -d "$WHEELS" \
    --python-version 3.12 \
    --platform win_amd64 \
    --only-binary=:all: \
    --no-deps
}

if [ ! -x "$DEST/python.exe" ] || [ ! -d "$SITE/django" ]; then
  mkdir -p "$ROOT/desktop/vendor"
  rm -rf "$DEST" "$WHEELS"
  mkdir -p "$WHEELS"
  TMP="$(mktemp -d)"
  echo "Downloading Windows Python…"
  curl -fsSL "$URL" -o "$TMP/python-win.tar.gz"
  tar -xzf "$TMP/python-win.tar.gz" -C "$TMP"
  mv "$TMP/python" "$DEST"
  rm -rf "$TMP"
  download_engine_wheels
  download_rapidocr_wheels
  unzip_wheels
else
  echo "Windows Python already present — ensuring RapidOCR…"
  download_rapidocr_wheels
  unzip_wheels
fi

test -d "$SITE/django"
test -d "$SITE/rapidocr_onnxruntime"
test -d "$SITE/onnxruntime"
echo "Bundled Python at $DEST"
ls -lah "$DEST/python.exe"
du -sh "$DEST"
