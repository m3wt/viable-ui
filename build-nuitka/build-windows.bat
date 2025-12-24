@echo off
REM Nuitka build script for Vial on Windows
REM Run from the gui directory: build-nuitka\build-windows.bat

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set GUI_DIR=%SCRIPT_DIR%..
set SRC_DIR=%GUI_DIR%\src\main\python
set RESOURCES_DIR=%GUI_DIR%\src\main\resources\base
set OUTPUT_DIR=%GUI_DIR%\build-nuitka\output

REM Read version from base.json
for /f "tokens=2 delims=:," %%a in ('type "%GUI_DIR%\src\build\settings\base.json" ^| findstr "version"') do (
    set VERSION=%%~a
    set VERSION=!VERSION: =!
    set VERSION=!VERSION:"=!
)

echo Building Vial version %VERSION%

REM Clean previous build
if exist "%OUTPUT_DIR%" rmdir /s /q "%OUTPUT_DIR%"

REM Run Nuitka
python -m nuitka ^
    --standalone ^
    --enable-plugin=pyqt5 ^
    --include-data-dir="%RESOURCES_DIR%"=. ^
    --include-data-file="%GUI_DIR%\src\build\settings\base.json"=build_settings.json ^
    --windows-icon-from-ico="%GUI_DIR%\src\main\icons\Icon.ico" ^
    --windows-company-name="Vial" ^
    --windows-product-name="Vial" ^
    --windows-file-version=%VERSION%.0 ^
    --windows-product-version=%VERSION%.0 ^
    --windows-file-description="Vial Keyboard Configurator" ^
    --output-dir="%OUTPUT_DIR%" ^
    --output-filename=Vial.exe ^
    --assume-yes-for-downloads ^
    --remove-output ^
    "%SRC_DIR%\main.py"

if errorlevel 1 (
    echo Build failed!
    exit /b 1
)

echo.
echo Build complete! Output in: %OUTPUT_DIR%\main.dist
echo.
echo Next steps:
echo 1. Test the executable: %OUTPUT_DIR%\main.dist\Vial.exe
echo 2. Optionally sign with: signtool sign /f cert.pfx /p password /t http://timestamp.digicert.com "%OUTPUT_DIR%\main.dist\Vial.exe"
echo 3. Create installer with Inno Setup using build-nuitka\installer.iss

endlocal
