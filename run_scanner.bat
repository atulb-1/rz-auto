@echo off
title DefineE RZ Momentum Scanner
color 0A

echo.
echo  ================================================
echo    DefineE RZ Momentum Scanner Automation
echo  ================================================
echo.

:: Change to script directory
cd /d "%~dp0"

:: Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo  [OK] Virtual environment activated.
    echo.
) else (
    echo  [WARNING] No virtual environment found.
    echo  Run setup.bat first for best results.
    echo  Falling back to system Python...
    echo.
    :: Check Python is installed
    python --version >nul 2>&1
    if errorlevel 1 (
        echo  [ERROR] Python not found! Please install Python and add it to PATH.
        echo.
        pause
        exit /b 1
    )
    :: Check if playwright is installed
    python -c "import playwright" >nul 2>&1
    if errorlevel 1 (
        echo  [INFO] Installing required packages...
        pip install playwright pyotp requests
        playwright install chromium
        echo.
    )
)

echo  Starting fully automated scan...
echo.
python rz_scanner.py

if errorlevel 1 (
    echo.
    echo  [ERROR] Script exited with an error. Check the output above.
) else (
    echo.
    echo  [DONE] Script completed successfully!
)

echo.
pause
