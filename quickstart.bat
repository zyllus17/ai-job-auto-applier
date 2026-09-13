@echo off
setlocal enabledelayedexpansion

title AI Job Auto-Applier - Windows Turnkey Quickstart

cd /d "%~dp0"

echo.
echo =================================================================
echo    AI JOB AUTO-APPLIER - WINDOWS TURNKEY SETUP
echo =================================================================
echo Setting up your automated job search, CV generator, and tracker...
echo.

:: 1. Detect Python
set "PYTHON_EXE="
where py >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_EXE=py -3"
    goto :found_python
)
where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_EXE=python"
    goto :found_python
)
where python3 >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_EXE=python3"
    goto :found_python
)

:found_python
if "%PYTHON_EXE%"=="" (
    echo [ERROR] Python 3 was not found on your system!
    echo.
    echo Please install Python 3.10+ from https://www.python.org/
    echo IMPORTANT: Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo [OK] Detected Python: %PYTHON_EXE%
echo.

:: 2. Install Required Python Packages
echo [+] Installing Python dependencies...
%PYTHON_EXE% -m pip install --quiet --upgrade pip
%PYTHON_EXE% -m pip install pypdf pyyaml python-telegram-bot psutil python-dotenv aiohttp playwright fastapi "uvicorn[standard]" websockets
if %errorlevel% neq 0 (
    echo [WARNING] Some dependencies failed to install. Retrying standard install...
    %PYTHON_EXE% -m pip install -r requirements.txt 2>nul
)
echo [OK] Python dependencies installed successfully.
echo.

:: 3. Install Playwright Chromium Browser
echo [+] Verifying anti-detect browser binaries (Playwright Chromium)...
%PYTHON_EXE% -m playwright install chromium
echo [OK] Playwright Chromium browser binary ready.
echo.

:: 4. Environment Configuration
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [OK] Created .env configuration file from template.
    )
) else (
    echo [OK] Existing .env found.
)
echo.

:: 5. Create Documents and Applications Directories
if not exist "documents\applications" mkdir "documents\applications"
if not exist "logs" mkdir "logs"

echo.
echo =================================================================
echo    CONGRATULATIONS! AI JOB AUTO-APPLIER IS READY ON WINDOWS
echo =================================================================
echo.
echo You can now start the application:
echo.
echo   1. Web Dashboard (Recommended):
echo      run.bat               (Double-click or run from CMD)
echo      .\run.ps1             (Run in PowerShell)
echo      make run              (Command Prompt make shim)
echo.
echo   2. Autonomous Daemon:
echo      %PYTHON_EXE% tools\daemon_job_runner.py --interval-mins 60
echo.
echo   3. Browser Auto-Apply (Single Job):
echo      %PYTHON_EXE% tools\browser_autofill.py "<job_url>" --mode semi-auto
echo.
echo   4. Telegram Mobile Bot:
echo      %PYTHON_EXE% tools\telegram_bot.py
echo.
echo =================================================================
echo.
pause
endlocal
