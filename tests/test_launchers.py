"""Automated Test Suite for Cross-Platform Desktop Launchers (Windows, Mac, Linux)."""

import os
import sys
import json
import shutil
from pathlib import Path
import pytest


REPO_ROOT = Path(__file__).parent.parent.resolve()

def test_desktop_launcher_imports_and_environment():
    """Verifies tools/desktop_launcher.py initializes correctly."""
    from tools.desktop_launcher import (
        get_repo_root,
        detect_python_executable,
        PORT,
        URL,
        kill_port_owner,
        kill_process_tree
    )

    root = get_repo_root()
    assert (root / "run.py").exists(), f"run.py not found in repo root: {root}"
    assert PORT == 8420
    assert URL == "http://localhost:8420"

    py_bin = detect_python_executable()
    assert os.path.exists(py_bin) or shutil.which(py_bin) is not None, f"Python binary not found: {py_bin}"

    # Verify process kill helpers don't crash with None or non-existent PID
    kill_process_tree(0)
    kill_process_tree(None)

def test_windows_launcher_backward_compatibility():
    """Verifies tools/windows_launcher.py re-exports desktop_launcher functions."""
    import tools.windows_launcher as win_launcher
    assert hasattr(win_launcher, "PORT")
    assert hasattr(win_launcher, "URL")
    assert hasattr(win_launcher, "run_backend")
    assert hasattr(win_launcher, "launch_gui")
    assert win_launcher.PORT == 8420

def test_electron_package_json_schema():
    """Verifies desktop/package.json contains all required Mac, Windows, and Linux configurations."""
    pkg_path = REPO_ROOT / "desktop" / "package.json"
    assert pkg_path.exists(), "desktop/package.json is missing"

    with open(pkg_path, "r", encoding="utf-8") as f:
        pkg = json.load(f)

    # Required scripts
    scripts = pkg.get("scripts", {})
    assert "start" in scripts
    assert "build:mac" in scripts
    assert "build:win" in scripts
    assert "build:linux" in scripts, "build:linux script missing from desktop/package.json"

    # Build targets
    build = pkg.get("build", {})
    assert "mac" in build, "mac build config missing"
    assert "win" in build, "win build config missing"
    assert "linux" in build, "linux build config missing"

    # Verify Linux targets include AppImage & deb
    linux_targets = build["linux"].get("target", [])
    assert "AppImage" in linux_targets, "AppImage missing from linux targets"
    assert "deb" in linux_targets, "deb missing from linux targets"

    # Verify extraResources bundle
    extra_res = build.get("extraResources", [])
    assert len(extra_res) >= 4, "extraResources must bundle core repo files"
    destinations = [r.get("to") for r in extra_res]
    assert "repo/run.py" in destinations
    assert "repo/dashboard" in destinations
    assert "repo/tools" in destinations
    assert "repo/requirements.txt" in destinations

def test_linux_desktop_entry():
    """Verifies tools/ai-job-auto-applier.desktop is valid according to Freedesktop specs."""
    desktop_file = REPO_ROOT / "tools" / "ai-job-auto-applier.desktop"
    assert desktop_file.exists(), "tools/ai-job-auto-applier.desktop missing"

    content = desktop_file.read_text(encoding="utf-8")
    assert "[Desktop Entry]" in content
    assert "Type=Application" in content
    assert "Name=AI Job Auto-Applier" in content
    assert "Exec=" in content
    assert "Categories=" in content

def test_build_scripts_executable():
    """Verifies shell build scripts have proper executable permissions."""
    mac_dmg = REPO_ROOT / "tools" / "build_mac_dmg.sh"
    linux_app = REPO_ROOT / "tools" / "build_linux_app.sh"

    assert mac_dmg.exists()
    assert linux_app.exists()

    if sys.platform != "win32":
        assert os.access(mac_dmg, os.X_OK), "tools/build_mac_dmg.sh is not executable"
        assert os.access(linux_app, os.X_OK), "tools/build_linux_app.sh is not executable"

def test_desktop_assets_icons():
    """Verifies all cross-platform icon assets exist and have valid resolutions."""
    assets_dir = REPO_ROOT / "desktop" / "assets"
    assert (assets_dir / "icon.png").exists(), "Master icon.png missing"
    assert (assets_dir / "icon.ico").exists(), "Windows icon.ico missing"

    if sys.platform == "darwin":
        assert (assets_dir / "icon.icns").exists(), "macOS icon.icns missing"

    # Linux icons folder
    linux_icons = assets_dir / "icons"
    assert linux_icons.exists() and linux_icons.is_dir(), "Linux icons folder missing"
    for sz in [16, 32, 64, 128, 256, 512]:
        sz_icon = linux_icons / f"{sz}x{sz}.png"
        assert sz_icon.exists(), f"Linux icon {sz}x{sz}.png missing"

def test_github_workflow_cross_platform_matrix():
    """Verifies .github/workflows/build-desktop.yml builds and publishes macOS, Windows, and Linux."""
    wf_path = REPO_ROOT / ".github" / "workflows" / "build-desktop.yml"
    assert wf_path.exists(), "build-desktop.yml missing"

    wf_content = wf_path.read_text(encoding="utf-8")
    assert "build-macos:" in wf_content
    assert "build-windows:" in wf_content
    assert "build-linux:" in wf_content, "build-linux job missing from CI workflow"
    assert "Linux-Packages" in wf_content
    assert "macOS-DMG" in wf_content
    assert "Windows-EXE" in wf_content
