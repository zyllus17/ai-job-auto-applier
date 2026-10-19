@echo off
REM ==============================================================================
REM Build Windows EXE (Installer & Standalone Portable) for AI Job Auto-Applier
REM ==============================================================================
setlocal EnableDelayedExpansion

echo ==========================================================
echo 🪟 Building Windows EXE Launcher for AI Job Auto-Applier
echo ==========================================================

cd /d "%~dp0\.."
set REPO_ROOT=%CD%
set DESKTOP_DIR=%REPO_ROOT%\desktop

REM 1. Ensure Python icons exist
if not exist "%DESKTOP_DIR%\assets\icon.ico" (
    echo 🎨 Generating Windows icon assets...
    python "%DESKTOP_DIR%\generate_icons.py"
)

REM 2. Check if bun or npm is available
cd /d "%DESKTOP_DIR%"
where bun >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo 📦 Installing dependencies with Bun...
    call bun install
    echo 🚀 Building Windows NSIS Installer and Portable EXE...
    call bun run build:win
    goto :done
)

where npm >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo 📦 Installing dependencies with NPM...
    call npm install
    echo 🚀 Building Windows NSIS Installer and Portable EXE...
    call npm run build:win
    goto :done
)

echo.
echo ⚠️ Node/Bun not detected on this machine.
echo 🔄 Falling back to PyInstaller native Windows executable generator...
cd /d "%REPO_ROOT%"
python -m pip install --quiet pyinstaller
python tools\build_win_exe.py

:done
echo.
echo ==========================================================
echo ✨ Windows Build Process Finished!
echo 📍 Check desktop\dist or dist for generated .exe files
echo ==========================================================
pause
