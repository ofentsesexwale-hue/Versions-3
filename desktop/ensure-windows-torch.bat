@echo off
REM Install the matched CPU torch stack into desktop\vendor\python-win
REM (this is what gets packed as office\python inside OVC-CaseFile.exe).
REM
REM Do NOT pip into %%TEMP%% portable extracts of the .exe — those folders are
REM wiped or corrupted on restart (torchvision\_C.pyd entry point errors).
REM Always install here, then rebuild: cd desktop && yarn pack:win
setlocal
cd /d "%~dp0"

if not exist "vendor\python-win\python.exe" (
  echo vendor\python-win is missing.
  echo On the build machine run: desktop\bundle-windows-python.sh
  echo Then copy vendor\python-win into this tree, or rebuild the .exe.
  pause
  exit /b 1
)

echo Installing matched CPU stack into desktop\vendor\python-win ...
echo   torch==2.14.0+cpu
echo   torchvision==0.29.0+cpu
echo   transformers==4.49.0
echo   tokenizers==0.21.4
echo   opencv-python-headless
vendor\python-win\python.exe -m pip install --upgrade pip
vendor\python-win\python.exe -m pip uninstall -y torch torchvision transformers tokenizers 2>nul
vendor\python-win\python.exe -m pip install torch==2.14.0+cpu torchvision==0.29.0+cpu --index-url https://download.pytorch.org/whl/cpu
vendor\python-win\python.exe -m pip install transformers==4.49.0 tokenizers==0.21.4 opencv-python-headless pillow-heif
vendor\python-win\python.exe -c "import torch, torchvision, tokenizers; from transformers import TrOCRProcessor, VisionEncoderDecoderModel; print(torch.__version__, torchvision.__version__, tokenizers.__version__); TrOCRProcessor.from_pretrained('microsoft/trocr-base-handwritten', use_fast=False); print('TrOCR load OK')"
if errorlevel 1 (
  echo Install / verify failed.
  pause
  exit /b 1
)
echo.
echo OK. Rebuild the exe so staff get this stack:
echo   cd desktop
echo   yarn pack:win
echo Then replace C:\Users\sebue\OVC-CaseFile\OVC-CaseFile.exe
echo Do not ask staff to pip into %%TEMP%% extracts.
endlocal
