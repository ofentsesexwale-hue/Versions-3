@echo off
REM Put "OVC CaseFile" on the Windows desktop.
REM Prefers start-desktop.bat (backend\.venv + torch) when the portable .exe is old / missing torch.
setlocal
cd /d "%~dp0.."
set "ROOT=%CD%"
set "ICON=%ROOT%\desktop\icons\icon.ico"
set "TARGET=%ROOT%\start-desktop.bat"
if exist "%ROOT%\desktop\release\OVC-CaseFile.exe" (
  REM Prefer a freshly packed exe that includes office\python with torch.
  set "TARGET=%ROOT%\desktop\release\OVC-CaseFile.exe"
)
if exist "%ROOT%\OVC-CaseFile.exe" set "TARGET=%ROOT%\OVC-CaseFile.exe"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$desk = [Environment]::GetFolderPath('Desktop');" ^
  "$lnk = Join-Path $desk 'OVC CaseFile.lnk';" ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk);" ^
  "$s.TargetPath = '%TARGET%';" ^
  "$s.WorkingDirectory = '%ROOT%';" ^
  "$s.IconLocation = '%ICON%';" ^
  "$s.Description = 'Office case files for orphans and vulnerable children';" ^
  "$s.Save();" ^
  "Write-Host ('Shortcut on ' + $lnk + ' -> %TARGET%')"
endlocal
