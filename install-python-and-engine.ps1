# One-time office PC setup: Python 3.12 + RapidOCR + Tesseract + VC++ runtime
# Right-click → Run with PowerShell, from the OVC-CaseFile folder (not ovc-case-manager).

$ErrorActionPreference = "Stop"
$Office = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Office) { $Office = Get-Location }
Set-Location $Office

Write-Host "Installing office scan tools into $Office ..."
winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
winget install -e --id Microsoft.VCRedist.2015+.x64 --accept-package-agreements --accept-source-agreements
winget install -e --id UB-Mannheim.TesseractOCR --accept-package-agreements --accept-source-agreements

$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")

$Py = $null
foreach ($cmd in @("py", "python")) {
  $found = Get-Command $cmd -ErrorAction SilentlyContinue
  if ($found) { $Py = $found.Source; break }
}
if (-not $Py) { throw "Python is not on PATH. Close this window, open a new one, and run the script again." }

Write-Host "Using $Py"
if ($Py -like "*py.exe") {
  & $Py -3 -m venv "$Office\backend\.venv"
} else {
  & $Py -m venv "$Office\backend\.venv"
}

$VenvPy = "$Office\backend\.venv\Scripts\python.exe"
& $VenvPy -m pip install --upgrade pip
& $VenvPy -m pip install -r "$Office\backend\requirements-engine.txt"
& $VenvPy "$Office\backend\ensure_engine.py"
& $VenvPy "$Office\backend\manage.py" migrate --noinput
& $VenvPy "$Office\backend\manage.py" seed_data

Write-Host ""
Write-Host "Python, RapidOCR, and Tesseract are ready."
Write-Host "Close this window, then open OVC CaseFile again."
