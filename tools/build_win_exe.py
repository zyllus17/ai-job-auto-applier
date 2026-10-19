#!/usr/bin/env python3
"""Build Standalone Windows .exe using PyInstaller.

This script compiles tools/windows_launcher.py into a single-file Windows executable:
dist/AI-Job-Auto-Applier-Launcher.exe
"""

import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()
ICON_PATH = REPO_ROOT / "desktop" / "assets" / "icon.ico"
LAUNCHER_SCRIPT = REPO_ROOT / "tools" / "windows_launcher.py"

def main():
    print("==========================================================")
    print("🪟 Compiling Standalone Windows .exe with PyInstaller")
    print("==========================================================")

    # 1. Verify pyinstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("📦 Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 2. Ensure icons exist
    if not ICON_PATH.exists():
        print("🎨 Generating Windows icon assets...")
        subprocess.check_call([sys.executable, str(REPO_ROOT / "desktop" / "generate_icons.py")])

    sep = ';' if sys.platform == 'win32' else ':'

    # 3. Build single-file executable
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--name", "AI-Job-Auto-Applier-Launcher",
        "--onefile",
        "--clean",
        "--noconsole",
    ]

    if ICON_PATH.exists():
        cmd.extend(["--icon", str(ICON_PATH)])

    # Add data directories & core scripts
    cmd.extend([
        "--add-data", f"dashboard{sep}dashboard",
        "--add-data", f"tools{sep}tools",
        "--add-data", f"run.py{sep}.",
        "--add-data", f"requirements.txt{sep}.",
        str(LAUNCHER_SCRIPT)
    ])


    print(f"🚀 Running: {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=str(REPO_ROOT))

    print("\n==========================================================")
    print("✅ Build Completed! Executable generated at:")
    print(f"📍 {REPO_ROOT / 'dist' / ('AI-Job-Auto-Applier-Launcher.exe' if sys.platform == 'win32' else 'AI-Job-Auto-Applier-Launcher')}")
    print("==========================================================")

if __name__ == "__main__":
    main()
