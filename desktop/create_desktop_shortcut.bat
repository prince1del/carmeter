@echo off
REM Creates a Desktop shortcut: double-click → MeterDigit Online starts
setlocal
cd /d "%~dp0"

set "TARGET=%~dp0start_online.bat"
set "WORKDIR=%~dp0.."
set "ICON=%SystemRoot%\System32\shell32.dll,13"
set "LINK=%USERPROFILE%\Desktop\MeterDigit Online.lnk"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$target = '%TARGET%'; $workdir = '%WORKDIR%'; $link = '%LINK%'; $icon = '%ICON%'; ^
   $ws = New-Object -ComObject WScript.Shell; ^
   $s = $ws.CreateShortcut($link); ^
   $s.TargetPath = $target; ^
   $s.WorkingDirectory = $workdir; ^
   $s.WindowStyle = 1; ^
   $s.Description = 'Start MeterDigit web app (Excel → JPG)'; ^
   $s.IconLocation = $icon; ^
   $s.Save(); ^
   Write-Host ('Shortcut created: ' + $link)"
if errorlevel 1 (
  echo Failed to create shortcut.
  pause
  exit /b 1
)

echo.
echo DONE. Desktop pe "MeterDigit Online" shortcut ban gaya.
echo Double-click karo → server start + browser open.
echo.
pause
