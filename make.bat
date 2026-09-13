@echo off
setlocal
cd /d "%~dp0"

set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=help"

if /i "%TARGET%"=="help" (
    echo.
    echo ============================================================
    echo   AI Job Auto-Applier - Windows Make Shim
    echo ============================================================
    echo.
    echo Usage:
    echo   make run      - Install deps, free port, start dashboard and open browser
    echo   make install  - Install dependencies and Playwright browser binary
    echo   make clean    - Free port 8420 by stopping dashboard processes
    echo   make test     - Run automated test suite
    echo.
    echo Direct Windows alternatives:
    echo   run.bat       - Double-click or run from CMD
    echo   .\run.ps1     - Run from PowerShell
    echo   python run.py - Universal cross-platform launcher
    echo.
    exit /b 0
)

if /i "%TARGET%"=="run" (
    shift
    call run.bat %1 %2 %3 %4 %5 %6 %7 %8 %9
    exit /b %errorlevel%
)

if /i "%TARGET%"=="install" (
    call run.bat --install
    exit /b %errorlevel%
)

if /i "%TARGET%"=="clean" (
    call run.bat --clean-only
    exit /b %errorlevel%
)

if /i "%TARGET%"=="test" (
    call run.bat --test
    exit /b %errorlevel%
)

:: Forward any custom targets/arguments directly to run.bat
call run.bat %*
exit /b %errorlevel%
