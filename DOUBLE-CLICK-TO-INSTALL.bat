@echo off
REM Double-click this file in File Explorer. Do not type commands.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-office-engine.ps1"
if errorlevel 1 pause
