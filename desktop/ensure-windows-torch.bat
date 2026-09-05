@echo off
REM Install CPU-only torch into the Python the .exe actually runs
REM (desktop\vendor\python-win → packaged as office\python).
REM Does NOT touch model weights (~2 GB stay in %%USERPROFILE%%\.cache\huggingface).
setlocal
cd /d "%~dp0"
if not exist "vendor\python-win\python.exe" (
  echo vendor\python-win is missing.
  echo On Linux/macOS run: desktop\bundle-windows-python.sh
  echo On this PC, unpack a fresh build that includes vendor\python-win, then re-run this bat.
  pause
  exit /b 1
)
echo Installing CPU PyTorch into desktop\vendor\python-win ...
vendor\python-win\python.exe -m pip install --upgrade pip
vendor\python-win\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
vendor\python-win\python.exe -m pip install transformers pillow-heif
vendor\python-win\python.exe -c "import torch, transformers; print('OK torch', torch.__version__, 'cuda', torch.cuda.is_available())"
if errorlevel 1 (
  echo Install failed.
  pause
  exit /b 1
)
echo Done. Rebuild the exe with: cd desktop ^& yarn pack:win
endlocal
