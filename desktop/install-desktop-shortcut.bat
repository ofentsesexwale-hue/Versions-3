@echo off
REM Put an OVC CaseFile shortcut (Sebueng Itumeleng icon) on this Windows desktop.
setlocal
cd /d "%~dp0.."
set "ROOT=%CD%"
set "ICON=%ROOT%\desktop\icons\icon.ico"
set "TARGET=%ROOT%\start-desktop.bat"
if exist "%ROOT%\desktop\release\OVC-CaseFile.exe" set "TARGET=%ROOT%\desktop\release\OVC-CaseFile.exe"
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
  "Write-Host ('Shortcut on ' + $lnk)"
endlocal
