#!/usr/bin/env bash
# AI Job Auto-Applier - macOS Quick Installer
# Automatically downloads latest DMG, installs to /Applications, and removes macOS Gatekeeper quarantine.

set -e

echo "🚀 Installing AI Job Auto-Applier for macOS..."

TEMP_DMG=$(mktemp /tmp/ai-job-auto-applier-XXXXXX.dmg)
DOWNLOAD_URL="https://github.com/zyllus17/ai-job-auto-applier/releases/latest/download/AI-Job-Auto-Applier-6.0.0.dmg"

echo "📥 Downloading AI-Job-Auto-Applier-6.0.0.dmg..."
curl -fSL --progress-bar -o "$TEMP_DMG" "$DOWNLOAD_URL"

MOUNT_DIR=$(mktemp -d /tmp/ai-job-mount-XXXXXX)
echo "💿 Mounting disk image..."
hdiutil attach "$TEMP_DMG" -mountpoint "$MOUNT_DIR" -nobrowse -quiet

echo "📦 Installing AI Job Auto-Applier to /Applications..."
rm -rf "/Applications/AI Job Auto-Applier.app"
cp -R "$MOUNT_DIR/AI Job Auto-Applier.app" /Applications/

echo "🧹 Cleaning up disk image..."
hdiutil detach "$MOUNT_DIR" -quiet
rm -f "$TEMP_DMG"
rmdir "$MOUNT_DIR" 2>/dev/null || true

echo "🔓 Removing macOS quarantine flag (xattr -cr)..."
xattr -cr "/Applications/AI Job Auto-Applier.app" 2>/dev/null || true

echo ""
echo "✅ AI Job Auto-Applier installed successfully to /Applications!"
echo "✨ You can launch it from Spotlight, Launchpad, or run:"
echo "   open '/Applications/AI Job Auto-Applier.app'"
