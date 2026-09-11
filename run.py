#!/usr/bin/env python3
"""Universal Cross-Platform Runner for AI Job Auto-Applier Dashboard.

Works out of the box on Windows, macOS, and Linux without requiring 'make'.

Usage:
    python run.py               # Install deps, free port, start dashboard & open browser
    python run.py --no-browser  # Start without opening browser
    python run.py --clean-only  # Free port 8420 and exit
    python run.py --install     # Install dependencies and exit
"""

import sys
import os
import time
import socket
import argparse
import platform
import threading
import webbrowser
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.resolve()
os.chdir(REPO_ROOT)

DEFAULT_PORT = 8420
DEFAULT_HOST = "0.0.0.0"

REQUIRED_PACKAGES = [
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn[standard]"),
    ("websockets", "websockets"),
    ("psutil", "psutil"),
    ("dotenv", "python-dotenv"),
    ("playwright", "playwright"),
]

def print_banner():
    is_win = sys.platform == "win32"
    rocket = "[>]" if is_win else "🚀"
    gear   = "[*]" if is_win else "⚙️"
    print("" + "=" * 62)
    print(f"  {rocket} AI Job Auto-Applier Dashboard - Universal Launcher")
    print("=" * 62 + "\n")

def check_and_install_dependencies():
    """Checks for required packages and installs any that are missing."""
    missing = []
    for import_name, pkg_name in REQUIRED_PACKAGES:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg_name)

    if not missing:
        return

    print(f"📦 Installing missing dependencies: {', '.join(missing)}...")
    cmd = [sys.executable, "-m", "pip", "install"] + missing
    try:
        subprocess.check_call(cmd)
        print("✅ All dependencies installed successfully!\n")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        print("Please run: python -m pip install -r requirements.txt")
        sys.exit(1)

def kill_port_owner(port: int):
    """Terminates any process currently bound to the specified port across Windows, macOS, and Linux."""
    # Method 1: psutil (OS-agnostic, preferred)
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                get_conns = getattr(proc, 'net_connections', getattr(proc, 'connections', None))
                if not get_conns:
                    continue
                for conn in get_conns(kind='inet'):
                    if conn.laddr and conn.laddr.port == port:
                        print(f"🧹 Freeing port {port} (Terminating PID {proc.pid}: {proc.name()})...")
                        proc.terminate()
                        try:
                            proc.wait(timeout=2.0)
                        except psutil.TimeoutExpired:
                            proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                pass
    except ImportError:
        pass

    # Method 2: Windows native netstat + taskkill fallback
    if sys.platform == "win32":
        try:
            cmd = f'netstat -ano -p tcp | findstr :{port}'
            out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
            pids = set()
            for line in out.strip().splitlines():
                parts = line.split()
                if len(parts) >= 5 and f':{port}' in parts[1]:
                    pid = parts[-1]
                    if pid.isdigit() and pid != '0':
                        pids.add(pid)
            for pid in pids:
                print(f"🧹 Windows Taskkill: Terminating PID {pid} on port {port}...")
                subprocess.run(f'taskkill /F /PID {pid}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    # Method 3: Unix native lsof + kill fallback
    elif sys.platform in ("darwin", "linux"):
        try:
            cmd = f'lsof -t -i :{port}'
            out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
            for pid in out.strip().splitlines():
                if pid.isdigit():
                    print(f"🧹 Unix Kill: Terminating PID {pid} on port {port}...")
                    subprocess.run(f'kill -9 {pid}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    time.sleep(0.5)

def is_port_open(host: str, port: int) -> bool:
    """Checks if the server port is reachable."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(('127.0.0.1', port)) == 0

def auto_open_browser(url: str, port: int):
    """Waits until the server is listening, then opens the default browser."""
    for _ in range(30):
        time.sleep(0.3)
        if is_port_open('127.0.0.1', port):
            break
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"Note: Could not open browser automatically: {e}")

def main():
    parser = argparse.ArgumentParser(description="AI Job Auto-Applier Dashboard Universal Launcher")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port to listen on (default: {DEFAULT_PORT})")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Host interface (default: {DEFAULT_HOST})")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    parser.add_argument("--clean-only", action="store_true", help="Kill processes on dashboard port and exit")
    parser.add_argument("--install", action="store_true", help="Install dependencies and exit")
    args = parser.parse_args()

    print_banner()

    if args.clean_only:
        kill_port_owner(args.port)
        print(f"✅ Port {args.port} cleaned up.")
        return

    check_and_install_dependencies()

    if args.install:
        print("✅ Dependencies verified.")
        return

    kill_port_owner(args.port)

    url = f"http://localhost:{args.port}"
    print(f"🚀 Starting Web Dashboard on {url}...")
    print("   Press Ctrl+C to stop the server.\n")

    if not args.no_browser:
        threading.Thread(target=auto_open_browser, args=(url, args.port), daemon=True).start()

    cmd = [
        sys.executable,
        "-m", "uvicorn",
        "dashboard.server:app",
        "--host", args.host,
        "--port", str(args.port),
        "--reload"
    ]

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n🛑 Dashboard stopped cleanly. Have a productive job search!")

if __name__ == "__main__":
    main()
