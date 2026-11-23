@echo off
REM MeterDigit Online — double-click to start server + open browser
setlocal
cd /d "%~dp0\.."
title MeterDigit Online - keep this window open

where node >nul 2>&1
if errorlevel 1 (
  echo Node.js not found. Install from https://nodejs.org then try again.
  pause
  exit /b 1
)

if not exist "package.json" (
  echo package.json not found. Put this folder inside the MeterDigit project.
  pause
  exit /b 1
)

if not exist "node_modules\" (
  echo First run: installing npm packages...
  call npm install
  if errorlevel 1 (
    echo npm install failed.
    pause
    exit /b 1
  )
)

echo.
echo Starting MeterDigit on http://127.0.0.1:43127
echo Browser will open automatically. Keep this window open while using the app.
echo Close this window to stop the server.
echo.

REM Open browser once the server answers (up to ~90s)
start "" /b powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "for ($i=0; $i -lt 90; $i++) { try { Invoke-WebRequest -Uri 'http://127.0.0.1:43127' -UseBasicParsing -TimeoutSec 1 | Out-Null; Start-Process 'http://127.0.0.1:43127'; exit 0 } catch { Start-Sleep -Seconds 1 } }"

call npm run dev
echo.
echo Server stopped.
pause
