@echo off
REM Offline desktop GUI (no browser) — Excel → JPG
setlocal
cd /d "%~dp0\.."
title MeterDigit Desktop

where py >nul 2>&1
if errorlevel 1 (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Python not found. Install Python 3.11+ from https://www.python.org
    pause
    exit /b 1
  )
  set "PY=python"
) else (
  set "PY=py"
)

echo Starting MeterDigit Desktop...
%PY% desktop\meterdigit_desktop.py
if errorlevel 1 pause
