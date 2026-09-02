# One double-click office install: Python 3.12, RapidOCR, Tesseract.
# Always run from the unzipped repo (the folder that contains backend\manage.py).

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Root) { $Root = (Get-Location).Path }
Set-Location $Root
$Log = Join-Path $Root "install-office-engine.log"
function Say($m) {
  Write-Host $m
  Add-Content -Path $Log -Value ("{0} {1}" -f (Get-Date -Format o), $m)
}
Say "Office engine install in $Root"

$Backend = Join-Path $Root "backend"
if (-not (Test-Path (Join-Path $Backend "manage.py"))) {
  throw "backend\manage.py not found. Put this script in Versions-3-main (the folder that contains backend)."
}

function Refresh-Path {
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
              [System.Environment]::GetEnvironmentVariable("Path", "User")
}

function Find-Python {
  Refresh-Path
  foreach ($c in @(
      "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
      "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
      "C:\Program Files\Python312\python.exe",
      "C:\Program Files\Python311\python.exe"
    )) {
    if (Test-Path $c) { return $c }
  }
  foreach ($name in @("py", "python", "python3")) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) {
      if ($name -eq "py") { return $cmd.Source }
      return $cmd.Source
    }
  }
  return $null
}

$Py = Find-Python
if (-not $Py) {
  Say "Downloading Python 3.12 (quiet install, Add to PATH)..."
  $pySetup = Join-Path $env:TEMP "ovc-python-3.12.10-amd64.exe"
  Invoke-WebRequest -UseBasicParsing -Uri "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe" -OutFile $pySetup
  $p = Start-Process -FilePath $pySetup -ArgumentList "/quiet","InstallAllUsers=0","PrependPath=1","Include_pip=1","Include_test=0" -Wait -PassThru
  if ($p.ExitCode -ne 0 -and $p.ExitCode -ne 3010) {
    throw "Python installer failed with code $($p.ExitCode)"
  }
  Start-Sleep -Seconds 3
  $Py = Find-Python
}
if (-not $Py) { throw "Python is still missing after install. Close this window, open a new PowerShell, and run the script again." }
Say "Using $Py"

$VenvPy = Join-Path $Backend ".venv\Scripts\python.exe"
if ($Py -like "*\py.exe") {
  & $Py -3 -m venv (Join-Path $Backend ".venv")
} else {
  & $Py -m venv (Join-Path $Backend ".venv")
}
if (-not (Test-Path $VenvPy)) { throw "venv was not created at $VenvPy" }

Say "Installing RapidOCR and the CaseFile engine (this can take several minutes)..."
& $VenvPy -m pip install --upgrade pip
$req = Join-Path $Backend "requirements-engine.txt"
if (Test-Path $req) {
  & $VenvPy -m pip install -r $req
}
& $VenvPy -m pip install "rapidocr-onnxruntime>=1.4" "onnxruntime>=1.16"
$ensure = Join-Path $Backend "ensure_engine.py"
if (Test-Path $ensure) { & $VenvPy $ensure }
& $VenvPy -c "import rapidocr_onnxruntime, onnxruntime; print('RapidOCR OK')"

Say "Installing Visual C++ runtime (needed by RapidOCR on Windows)..."
try {
  $vc = Join-Path $env:TEMP "ovc-vc_redist.x64.exe"
  Invoke-WebRequest -UseBasicParsing -Uri "https://aka.ms/vs/17/release/vc_redist.x64.exe" -OutFile $vc
  Start-Process -FilePath $vc -ArgumentList "/install","/quiet","/norestart" -Wait
} catch { Say "VC++ download skipped: $_" }

Say "Installing Tesseract (printed ID numbers)..."
try {
  $tess = Join-Path $env:TEMP "ovc-tesseract-w64.exe"
  Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/tesseract-ocr/tesseract/releases/download/5.5.3/tesseract-ocr-w64-setup-5.5.3.20260724.exe" -OutFile $tess
  Start-Process -FilePath $tess -ArgumentList "/S" -Wait
} catch { Say "Tesseract download skipped: $_" }

if (Test-Path (Join-Path $Backend "manage.py")) {
  Say "Migrating the office file..."
  & $VenvPy (Join-Path $Backend "manage.py") migrate --noinput
  try { & $VenvPy (Join-Path $Backend "manage.py") seed_data } catch { Say "seed_data skipped" }
}

Say "Done. Close this window. Open OVC CaseFile from $Root"
Write-Host ""
Write-Host "Done. You can close this window."
pause
