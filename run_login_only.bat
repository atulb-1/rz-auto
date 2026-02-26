@echo off
title Definedge RZone — Login Only
color 0B

echo.
echo  ================================================
echo    Definedge RZone — Login Only
echo    (Logs in + I Agree, then you take over)
echo  ================================================
echo.

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
    python --version >nul 2>&1
    if errorlevel 1 (
        echo  [ERROR] Python not found!
        pause
        exit /b 1
    )
    python -c "import playwright" >nul 2>&1
    if errorlevel 1 (
        echo  [INFO] Installing required packages...
        pip install playwright pyotp requests
        playwright install chromium
        echo.
    )
)

echo  Starting login automation...
echo.
python rzone_login_only.py

echo.
pause
