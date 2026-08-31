@echo off
REM Close anything that can lock OVC-CaseFile.exe so Windows will let you copy or open it.
echo Closing OVC CaseFile and leftover unpackers...
taskkill /IM "OVC CaseFile.exe" /F >nul 2>&1
taskkill /IM OVC-CaseFile.exe /F >nul 2>&1
taskkill /IM electron.exe /F >nul 2>&1
echo.
echo Done. Now:
echo  1. Close File Explorer windows that are inside the zip or Downloads.
echo  2. Close Cursor if it has C:\Users\sebue\ovc-case-manager open.
echo  3. Copy OVC-CaseFile.exe to C:\Users\sebue\ovc-case-manager
echo  4. Double-click that copy (not the file still inside the zip).
echo.
pause
