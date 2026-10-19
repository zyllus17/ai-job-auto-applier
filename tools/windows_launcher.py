#!/usr/bin/env python3
"""Windows Native Desktop Launcher for AI Job Auto-Applier.

Maintains complete backward compatibility by delegating to the unified
cross-platform desktop_launcher engine.
"""

from tools.desktop_launcher import (
    PORT,
    URL,
    REPO_ROOT,
    run_backend,
    open_browser_when_ready,
    launch_gui,
    kill_port_owner,
    kill_process_tree,
)

if __name__ == "__main__":
    launch_gui()
