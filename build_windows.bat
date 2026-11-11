@echo off
REM Lokaler Build unter Windows: braucht Python 3.10+ und Inno Setup 6 (iscc im PATH)
python -m pip install --upgrade pip || exit /b 1
python -m pip install -r requirements.txt pyinstaller || exit /b 1
python -m PyInstaller --noconfirm --windowed --name LasRasterThin --collect-all laspy --collect-all lazrs run_gui.py || exit /b 1
python -m PyInstaller --noconfirm --onefile --console --name lasrasterthin-cli --collect-all laspy --collect-all lazrs run_cli.py || exit /b 1
cd installer
iscc LasRasterThin.iss || exit /b 1
echo.
echo Fertig: installer\Output\LasRasterThin-Setup-*.exe
