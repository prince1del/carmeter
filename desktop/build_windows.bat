@echo off
REM Build MeterDigit Desktop .exe on Windows
REM Run from repo root in Developer / normal CMD after: pip install -r requirements-desktop.txt

cd /d "%~dp0\.."

pyinstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name MeterDigit ^
  --add-data "data\digit-cache;data\digit-cache" ^
  --add-data "data\meter_background.jpg;data" ^
  --add-data "scripts\generate_digits.py;scripts" ^
  --hidden-import PIL._tkinter_finder ^
  desktop\meterdigit_desktop.py

echo.
echo EXE: dist\MeterDigit\MeterDigit.exe
echo Copy the whole dist\MeterDigit folder to install.
pause
