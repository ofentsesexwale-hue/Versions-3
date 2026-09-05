#!/usr/bin/env bash
# Download a portable Windows Python and install the CaseFile engine into it.
# Always installs CPU-only PyTorch (+ transformers, pillow-heif). Never CUDA/ROCm/bitsandbytes.
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

strip_disallowed_wheels() {
  # Never ship CUDA / ROCm / bitsandbytes into the office bundle (8 GB AMD PC).
  shopt -s nullglob
  for bad in "$WHEELS"/*cuda* "$WHEELS"/*rocm* "$WHEELS"/bitsandbytes*; do
    [ -e "$bad" ] || continue
    echo "Removing disallowed wheel: $(basename "$bad")"
    rm -f "$bad"
  done
}

download_engine_wheels() {
  # Engine deps WITHOUT torch — torch must come from the CPU index only.
  mkdir -p "$WHEELS"
  echo "Downloading Windows engine wheels (excluding torch)…"
  local req
  req="$(mktemp)"
  grep -viE '^(torch|torchvision|torchaudio)\b' "$ROOT/backend/requirements-engine.txt" > "$req" || true
  "$ROOT/backend/.venv/bin/python" -m pip download \
    -r "$req" \
    -d "$WHEELS" \
    --python-version 3.12 \
    --platform win_amd64 \
    --only-binary=:all:
  rm -f "$req"
  strip_disallowed_wheels
}

download_rapidocr_wheels() {
  mkdir -p "$WHEELS"
  echo "Downloading RapidOCR Windows wheels…"
  "$ROOT/backend/.venv/bin/python" -m pip download \
    rapidocr-onnxruntime onnxruntime pyclipper shapely pyyaml tqdm six protobuf flatbuffers \
    -d "$WHEELS" \
    --python-version 3.12 \
    --platform win_amd64 \
    --only-binary=:all: \
    --no-deps
}

download_cpu_torch_wheels() {
  # The .exe runs this bundled Python (office/python), NOT backend\.venv.
  # LightOnOCR / TrOCR weights stay in %USERPROFILE%\.cache\huggingface — not in the .exe.
  mkdir -p "$WHEELS"
  echo "Downloading Windows CPU PyTorch (no CUDA / no ROCm)…"
  "$ROOT/backend/.venv/bin/python" -m pip download \
    torch torchvision \
    -d "$WHEELS" \
    --index-url https://download.pytorch.org/whl/cpu \
    --python-version 3.12 \
    --platform win_amd64 \
    --only-binary=:all:
  echo "Downloading transformers + pillow-heif for Windows…"
  "$ROOT/backend/.venv/bin/python" -m pip download \
    transformers pillow-heif \
    -d "$WHEELS" \
    --python-version 3.12 \
    --platform win_amd64 \
    --only-binary=:all:
  strip_disallowed_wheels
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
  download_cpu_torch_wheels
  unzip_wheels
else
  echo "Windows Python already present — ensuring RapidOCR + CPU torch…"
  download_rapidocr_wheels
  download_cpu_torch_wheels
  unzip_wheels
fi

test -d "$SITE/django"
test -d "$SITE/rapidocr_onnxruntime"
test -d "$SITE/onnxruntime"
test -d "$SITE/torch"
test -d "$SITE/transformers"
echo "Bundled Python at $DEST"
ls -lah "$DEST/python.exe"
du -sh "$DEST"
if command -v wine >/dev/null 2>&1; then
  wine "$DEST/python.exe" -c "import torch; import transformers; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())" \
    || echo "Wine smoke import skipped (wheels are still installed for Windows)."
fi
