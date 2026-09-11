@echo off
setlocal enabledelayedexpansion

title AI Job Auto-Applier Dashboard

:: Navigate to repo directory
cd /d "%~dp0"

echo ============================================================
echo   AI Job Auto-Applier Dashboard - Windows Launcher
echo ============================================================
echo.

:: Detect Python executable
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
    echo [ERROR] Python was not found on your system!
    echo.
    echo Please install Python 3.10+ from https://www.python.org/
    echo NOTE: During installation, be sure to check "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

echo [OK] Using Python: %PYTHON_EXE%
echo.

:: Execute the universal runner with all passed arguments
%PYTHON_EXE% run.py %*
set "EXIT_CODE=%errorlevel%"

if %EXIT_CODE% neq 0 (
    echo.
    echo [NOTICE] Dashboard exited with code %EXIT_CODE%.
    pause
)

endlocal
