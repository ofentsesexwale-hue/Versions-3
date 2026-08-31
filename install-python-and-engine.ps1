# One-time office PC setup: Python 3.12 + CaseFile engine
# Run in PowerShell (right-click Start → Windows PowerShell, or Terminal).

$ErrorActionPreference = "Stop"
$Office = "C:\Users\sebue\ovc-case-manager"
Set-Location $Office

Write-Host "Installing Python 3.12..."
winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements

$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")

$Py = $null
foreach ($cmd in @("py", "python")) {
  $found = Get-Command $cmd -ErrorAction SilentlyContinue
  if ($found) { $Py = $found.Source; break }
}
if (-not $Py) { throw "Python is not on PATH. Close PowerShell, open a new window, and run this script again." }

Write-Host "Using $Py"
if ($Py -like "*py.exe") {
  & $Py -3 -m venv "$Office\backend\.venv"
} else {
  & $Py -m venv "$Office\backend\.venv"
}

$VenvPy = "$Office\backend\.venv\Scripts\python.exe"
& $VenvPy -m pip install --upgrade pip
& $VenvPy -m pip install -r "$Office\backend\requirements-engine.txt"
& $VenvPy "$Office\backend\manage.py" migrate --noinput
& $VenvPy "$Office\backend\manage.py" seed_data

Write-Host ""
Write-Host "Python and the CaseFile engine are ready."
Write-Host "Close this window, then double-click OVC-CaseFile.exe"
