#!/usr/bin/env bash
# Download a portable Windows Python and install the CaseFile engine into it.
# Matched CPU stack (never CUDA / ROCm / bitsandbytes):
#   torch 2.14.x+cpu + torchvision 0.29.x+cpu  (PyTorch CPU index only)
#   transformers==4.49.0
#   opencv-python-headless
# Staff must NOT pip into %TEMP% portable extracts — that breaks on restart.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/desktop/vendor/python-win"
URL="https://github.com/astral-sh/python-build-standalone/releases/download/20260325/cpython-3.12.13+20260325-x86_64-pc-windows-msvc-install_only_stripped.tar.gz"
WHEELS="$ROOT/desktop/vendor/win-wheels"
SITE="$DEST/Lib/site-packages"

# Exact matched pins — keep these in sync with ensure-windows-torch.bat
TORCH_PIN='torch==2.14.0+cpu'
TORCHVISION_PIN='torchvision==0.29.0+cpu'
TRANSFORMERS_PIN='transformers==4.49.0'
# transformers 4.49 requires tokenizers>=0.21,<0.22 — 0.23.x causes
# RobertaProcessing.__new__() unexpected keyword argument 'cls' on TrOCR load.
TOKENIZERS_PIN='tokenizers==0.21.4'

unzip_wheels() {
  mkdir -p "$SITE"
  shopt -s nullglob
  for whl in "$WHEELS"/*.whl; do
    unzip -qo "$whl" -d "$SITE"
  done
}

strip_disallowed_wheels() {
  shopt -s nullglob
  for bad in "$WHEELS"/*cuda* "$WHEELS"/*rocm* "$WHEELS"/bitsandbytes* "$WHEELS"/*+cu[0-9]*; do
    [ -e "$bad" ] || continue
    echo "Removing disallowed wheel: $(basename "$bad")"
    rm -f "$bad"
  done
}

wipe_torch_stack() {
  # Remove mismatched leftover installs (e.g. torch 2.14 + torchvision 0.26,
  # or tokenizers 0.23 next to transformers 4.49).
  echo "Clearing previous torch / torchvision / transformers / tokenizers from site-packages…"
  rm -rf \
    "$SITE"/torch \
    "$SITE"/torchgen \
    "$SITE"/functorch \
    "$SITE"/torchvision \
    "$SITE"/transformers \
    "$SITE"/tokenizers \
    "$SITE"/opencv_python_headless* \
    "$SITE"/cv2 \
    "$SITE"/torch-*.dist-info \
    "$SITE"/torchvision-*.dist-info \
    "$SITE"/transformers-*.dist-info \
    "$SITE"/tokenizers-*.dist-info \
    "$SITE"/opencv_python_headless-*.dist-info
}

download_engine_wheels() {
  # Engine deps WITHOUT torch / torchvision / transformers — those are pinned below.
  mkdir -p "$WHEELS"
  echo "Downloading Windows engine wheels (excluding torch stack)…"
  local req
  req="$(mktemp)"
  grep -viE '^(torch|torchvision|torchaudio|transformers|tokenizers)\b' \
    "$ROOT/backend/requirements-engine.txt" > "$req" || true
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

download_matched_cpu_torch_stack() {
  # The .exe runs this bundled Python (office/python), NOT backend\.venv and NOT %TEMP%.
  # Model weights stay in %USERPROFILE%\.cache\huggingface.
  mkdir -p "$WHEELS"
  # Drop any previously downloaded mismatched torch/vision/transformers/tokenizers wheels.
  shopt -s nullglob
  rm -f "$WHEELS"/torch-*.whl "$WHEELS"/torchvision-*.whl "$WHEELS"/transformers-*.whl
  rm -f "$WHEELS"/tokenizers-*.whl

  echo "Downloading matched CPU torch stack from download.pytorch.org/whl/cpu …"
  "$ROOT/backend/.venv/bin/python" -m pip download \
    "$TORCH_PIN" "$TORCHVISION_PIN" \
    -d "$WHEELS" \
    --index-url https://download.pytorch.org/whl/cpu \
    --python-version 3.12 \
    --platform win_amd64 \
    --only-binary=:all: \
    --no-deps

  echo "Downloading $TRANSFORMERS_PIN + $TOKENIZERS_PIN + opencv-python-headless + pillow-heif …"
  "$ROOT/backend/.venv/bin/python" -m pip download \
    "$TRANSFORMERS_PIN" "$TOKENIZERS_PIN" opencv-python-headless pillow-heif \
    -d "$WHEELS" \
    --python-version 3.12 \
    --platform win_amd64 \
    --only-binary=:all:

  # transformers may pull a newer tokenizers as a dep — keep only 0.21.x.
  shopt -s nullglob
  for bad_tok in "$WHEELS"/tokenizers-0.2[2-9]*.whl "$WHEELS"/tokenizers-0.[3-9]*.whl; do
    [ -e "$bad_tok" ] || continue
    echo "Removing incompatible tokenizers wheel: $(basename "$bad_tok")"
    rm -f "$bad_tok"
  done

  strip_disallowed_wheels

  # Sanity: refuse to pack if pins did not resolve.
  shopt -s nullglob
  local torch_whl=( "$WHEELS"/torch-2.14.*+cpu*win*.whl )
  local vision_whl=( "$WHEELS"/torchvision-0.29.*+cpu*win*.whl )
  local tf_whl=( "$WHEELS"/transformers-4.49.*.whl )
  local tok_whl=( "$WHEELS"/tokenizers-0.21.*.whl )
  if [ ${#torch_whl[@]} -lt 1 ] || [ ${#vision_whl[@]} -lt 1 ] || [ ${#tf_whl[@]} -lt 1 ] || [ ${#tok_whl[@]} -lt 1 ]; then
    echo "ERROR: matched torch/torchvision/transformers/tokenizers wheels missing after download." >&2
    ls -lah "$WHEELS"/torch*.whl "$WHEELS"/transformers*.whl "$WHEELS"/tokenizers*.whl 2>/dev/null || true
    exit 1
  fi
  echo "Using $(basename "${torch_whl[0]}") + $(basename "${vision_whl[0]}") + $(basename "${tf_whl[0]}") + $(basename "${tok_whl[0]}")"
}

verify_stack_versions() {
  # Prefer a real Windows import via Wine; fall back to METADATA checks on Linux CI.
  if command -v wine >/dev/null 2>&1; then
    if wine "$DEST/python.exe" -c \
      "import torch, torchvision, tokenizers; from transformers import TrOCRProcessor, VisionEncoderDecoderModel; print(torch.__version__, torchvision.__version__, tokenizers.__version__); TrOCRProcessor.from_pretrained('microsoft/trocr-base-handwritten', use_fast=False); print('TrOCR load OK')"; then
      return 0
    fi
    echo "Wine import/load failed (DLL host limits or no HF cache) — checking installed dist-info pins…"
  fi
  local torch_meta vision_meta tf_meta tok_meta
  torch_meta="$(echo "$SITE"/torch-2.14.*+cpu*.dist-info/METADATA)"
  vision_meta="$(echo "$SITE"/torchvision-0.29.*+cpu*.dist-info/METADATA)"
  tf_meta="$(echo "$SITE"/transformers-4.49.*.dist-info/METADATA)"
  tok_meta="$(echo "$SITE"/tokenizers-0.21.*.dist-info/METADATA)"
  grep -q '^Version: 2\.14\.' $torch_meta
  grep -q '^Version: 0\.29\.' $vision_meta
  grep -q '^Version: 4\.49\.' $tf_meta
  grep -q '^Version: 0\.21\.' $tok_meta
  # Refuse a co-installed newer tokenizers (causes TrOCR RobertaProcessing TypeError).
  shopt -s nullglob
  local bad_tok=( "$SITE"/tokenizers-0.2[2-9]*.dist-info "$SITE"/tokenizers-0.[3-9]*.dist-info )
  if [ ${#bad_tok[@]} -gt 0 ]; then
    echo "ERROR: incompatible tokenizers dist-info present: ${bad_tok[*]}" >&2
    exit 1
  fi
  test -d "$SITE/cv2" || test -d "$SITE"/opencv_python_headless-*.dist-info
  echo "Pinned stack present: torch 2.14.x+cpu, torchvision 0.29.x+cpu, transformers 4.49.x, tokenizers 0.21.x, opencv"
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
  download_matched_cpu_torch_stack
  wipe_torch_stack
  unzip_wheels
else
  echo "Windows Python already present — refreshing matched CPU torch stack…"
  download_rapidocr_wheels
  download_matched_cpu_torch_stack
  wipe_torch_stack
  unzip_wheels
fi

test -d "$SITE/django"
test -d "$SITE/rapidocr_onnxruntime"
test -d "$SITE/onnxruntime"
test -d "$SITE/torch"
test -d "$SITE/torchvision"
test -d "$SITE/transformers"
verify_stack_versions
echo "Bundled Python at $DEST"
ls -lah "$DEST/python.exe"
du -sh "$DEST"
