#!/usr/bin/env bash
# ==============================================================================
# Build macOS DMG for AI Job Auto-Applier
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DESKTOP_DIR="$REPO_ROOT/desktop"
DIST_DIR="$DESKTOP_DIR/dist"
APP_NAME="AI Job Auto-Applier"
DMG_NAME="AI-Job-Auto-Applier-Installer.dmg"

echo "=========================================================="
echo "🍏 Building macOS DMG Installer for $APP_NAME"
echo "=========================================================="

cd "$REPO_ROOT"

# 1. Ensure icons exist
if [ ! -f "$DESKTOP_DIR/assets/icon.icns" ]; then
    echo "🎨 Generating application icons..."
    python3 "$DESKTOP_DIR/generate_icons.py"
fi

# 2. Build the app package with electron-builder
cd "$DESKTOP_DIR"
echo "📦 Packaging Electron macOS application..."

if command -v bun >/dev/null 2>&1; then
    bun run build:mac
elif command -v npm >/dev/null 2>&1; then
    npm run build:mac
else
    echo "❌ Error: Neither bun nor npm is installed."
    exit 1
fi

echo ""
echo "=========================================================="
echo "✨ macOS DMG Build Completed Successfully!"
echo "📍 Output DMG: $DIST_DIR"
ls -lh "$DIST_DIR"/*.dmg 2>/dev/null || echo "Check $DIST_DIR for output."
echo "=========================================================="
