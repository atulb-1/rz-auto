@echo off
title RZone Scanner — First-Time Setup
color 0E

echo.
echo  ====================================================
echo    Definedge RZone Scanner — First-Time Setup
echo  ====================================================
echo.
echo  This script will:
echo    1. Check Python is installed
echo    2. Create a virtual environment (venv)
echo    3. Install all required packages
echo    4. Download Chromium browser for Playwright
echo    5. Verify config.ini exists
echo.
echo  Press any key to begin setup...
pause >nul
echo.

:: ── Change to script directory ──
cd /d "%~dp0"

:: ── 1. Check Python ──
echo  [1/5] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERROR] Python is NOT installed or not in PATH!
    echo.
    echo  Please install Python 3.9+ from https://www.python.org/downloads/
    echo  IMPORTANT: Check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  [OK] %PYVER% found.
echo.

:: ── 2. Create virtual environment ──
echo  [2/5] Creating virtual environment...
if exist "venv" (
    echo  [OK] Virtual environment already exists. Skipping creation.
) else (
    python -m venv venv
    if errorlevel 1 (
        echo  [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
    echo  [OK] Virtual environment created in .\venv
)
echo.

:: ── Activate venv ──
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo  [ERROR] Failed to activate virtual environment!
    pause
    exit /b 1
)
echo  [OK] Virtual environment activated.
echo.

:: ── 3. Upgrade pip and install packages ──
echo  [3/5] Installing Python packages...
echo         - playwright (browser automation)
echo         - pyotp (TOTP/OTP generation)
echo         - requests (Telegram notifications)
echo.
python -m pip install --upgrade pip >nul 2>&1
pip install playwright pyotp requests
if errorlevel 1 (
    echo.
    echo  [ERROR] Package installation failed!
    pause
    exit /b 1
)
echo.
echo  [OK] All packages installed.
echo.

:: ── 4. Install Chromium browser ──
echo  [4/5] Downloading Chromium browser for Playwright...
echo         (This may take a few minutes on first run)
echo.
playwright install chromium
if errorlevel 1 (
    echo.
    echo  [ERROR] Chromium download failed!
    echo  Try running manually: playwright install chromium
    pause
    exit /b 1
)
echo.
echo  [OK] Chromium browser installed.
echo.

:: ── 5. Verify config.ini ──
echo  [5/5] Checking config.ini...
if exist "config.ini" (
    echo  [OK] config.ini found.
) else (
    echo.
    echo  [WARNING] config.ini NOT found!
    echo.
    echo  You need to create config.ini with your credentials before running.
    echo  Copy config_sample.ini to config.ini and fill in your details.
    echo.
)
echo.

:: ── Quick verification ──
echo  ── Verifying installation ──
echo.
python -c "import playwright; import pyotp; import requests; print('  All imports OK')"
if errorlevel 1 (
    echo  [ERROR] Import verification failed!
    pause
    exit /b 1
)
echo.

:: ── Done ──
echo  ====================================================
echo    SETUP COMPLETE!
echo  ====================================================
echo.
echo  Next steps:
echo    1. Edit config.ini with your UCC, Password, TOTP secret
echo    2. Add your strategy names in config.ini
echo    3. Run run_scanner.bat to start scanning
echo       OR run_login_only.bat to test login only
echo.
echo  NOTE: Always use run_scanner.bat or run_login_only.bat
echo        to run — they activate the venv automatically.
echo.
pause
