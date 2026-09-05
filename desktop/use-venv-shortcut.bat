@echo off
REM Force the desktop shortcut to start-desktop.bat (backend\.venv where torch already works).
REM Use this on the 8 GB office PC when yarn pack:win is too heavy.
setlocal
cd /d "%~dp0.."
set "ROOT=%CD%"
set "ICON=%ROOT%\desktop\icons\icon.ico"
set "TARGET=%ROOT%\start-desktop.bat"
if not exist "%TARGET%" (
  echo Missing %TARGET%
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$desk = [Environment]::GetFolderPath('Desktop');" ^
  "$lnk = Join-Path $desk 'OVC CaseFile.lnk';" ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk);" ^
  "$s.TargetPath = '%TARGET%';" ^
  "$s.WorkingDirectory = '%ROOT%';" ^
  "$s.IconLocation = '%ICON%';" ^
  "$s.Description = 'OVC CaseFile (backend venv with torch)';" ^
  "$s.Save();" ^
  "Write-Host ('Shortcut on ' + $lnk)"
echo Done. Use the Desktop shortcut "OVC CaseFile" — it runs start-desktop.bat.
endlocal
