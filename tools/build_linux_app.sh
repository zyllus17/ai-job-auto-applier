#!/usr/bin/env bash
# ==============================================================================
# Build Linux Desktop App (AppImage, DEB, tar.gz) for AI Job Auto-Applier
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DESKTOP_DIR="$REPO_ROOT/desktop"
DIST_DIR="$DESKTOP_DIR/dist"
APP_NAME="AI Job Auto-Applier"

echo "=========================================================="
echo "🐧 Building Linux Desktop Package for $APP_NAME"
echo "=========================================================="

cd "$REPO_ROOT"

# 1. Ensure icons exist (Linux requires assets/icons folder and icon.png)
if [ ! -d "$DESKTOP_DIR/assets/icons" ] || [ ! -f "$DESKTOP_DIR/assets/icon.png" ]; then
    echo "🎨 Generating Linux icon assets..."
    python3 "$DESKTOP_DIR/generate_icons.py"
fi

# 2. Build the app package with Electron Builder or fallback to PyInstaller
cd "$DESKTOP_DIR"

if command -v bun >/dev/null 2>&1; then
    echo "📦 Packaging with Bun and Electron-Builder (AppImage & DEB)..."
    bun install
    bun run build:linux
elif command -v npm >/dev/null 2>&1; then
    echo "📦 Packaging with NPM and Electron-Builder (AppImage & DEB)..."
    npm install
    npm run build:linux
else
    echo "⚠️ Neither bun nor npm detected on this machine."
    echo "🔄 Falling back to PyInstaller native Linux executable generator..."
    cd "$REPO_ROOT"
    python3 -m pip install --quiet pyinstaller
    python3 -m PyInstaller \
        --name "AI-Job-Auto-Applier-Launcher" \
        --onefile \
        --clean \
        --add-data "dashboard:dashboard" \
        --add-data "tools:tools" \
        --add-data "run.py:." \
        --add-data "requirements.txt:." \
        tools/desktop_launcher.py
fi

echo ""
echo "=========================================================="
echo "✨ Linux Desktop Build Completed Successfully!"
echo "📍 Output packages located in: $DIST_DIR or $REPO_ROOT/dist"
ls -lh "$DIST_DIR"/*.AppImage "$DIST_DIR"/*.deb "$DIST_DIR"/*.tar.gz 2>/dev/null || ls -lh "$REPO_ROOT/dist" 2>/dev/null || true
echo "=========================================================="
