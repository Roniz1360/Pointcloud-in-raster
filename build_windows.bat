@echo off
REM Lokaler Build unter Windows: braucht Python 3.10+ und Inno Setup 6 (iscc im PATH)
python -m pip install --upgrade pip || exit /b 1
python -m pip install -r requirements.txt || exit /b 1
set PYINSTALLER_COMPILE_BOOTLOADER=1
python -m pip install --no-binary pyinstaller pyinstaller || exit /b 1
if not exist build mkdir build
python packaging\version_info.py || exit /b 1
python -m PyInstaller --noconfirm packaging\LasRasterThin.spec || exit /b 1
cd installer
iscc LasRasterThin.iss || exit /b 1
echo.
echo Fertig: installer\Output\LasRasterThin-Setup-*.exe
