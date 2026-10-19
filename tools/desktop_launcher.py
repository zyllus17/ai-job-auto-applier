#!/usr/bin/env python3
"""Universal Cross-Platform Native Desktop Launcher for AI Job Auto-Applier.

Provides a lightweight, zero-dependency Tkinter GUI launcher with process management
and automatic browser sync. Runs natively on Windows, macOS, and Linux, and is
fully compilable into standalone executables via PyInstaller.
"""

import sys
import os
import time
import signal
import socket
import shutil
import platform
import subprocess
import threading
import webbrowser
from pathlib import Path

def get_repo_root() -> Path:
    """Resolves repo root across standard Python and PyInstaller frozen execution."""
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent.resolve()
        if (exe_dir / "run.py").exists():
            return exe_dir
        if hasattr(sys, '_MEIPASS') and (Path(sys._MEIPASS) / "run.py").exists():
            return Path(sys._MEIPASS)
        # Check current working directory
        if (Path.cwd() / "run.py").exists():
            return Path.cwd()
        return exe_dir
    return Path(__file__).parent.parent.resolve()

REPO_ROOT = get_repo_root()
try:
    os.chdir(REPO_ROOT)
except Exception:
    pass

PORT = 8420
URL = f"http://localhost:{PORT}"

def detect_python_executable() -> str:
    """Finds a working Python 3 executable on the system, even if frozen by PyInstaller."""
    is_win = sys.platform == "win32"
    
    # 1. If not frozen, current interpreter is best
    if not getattr(sys, 'frozen', False):
        return sys.executable

    # 2. Check local virtual environments first
    venv_candidates = [
        REPO_ROOT / ".venv" / ("Scripts" if is_win else "bin") / ("python.exe" if is_win else "python3"),
        REPO_ROOT / "venv" / ("Scripts" if is_win else "bin") / ("python.exe" if is_win else "python3"),
    ]
    for candidate in venv_candidates:
        if candidate.exists():
            return str(candidate)

    # 3. Check system PATH
    for name in (["python.exe", "py.exe", "python3.exe", "python"] if is_win else ["python3", "python"]):
        found = shutil.which(name)
        if found:
            return found

    # 4. Standard OS installation paths fallback
    if is_win:
        local_app = os.environ.get("LOCALAPPDATA", "")
        for ver in ["Python312", "Python311", "Python310"]:
            p = Path(local_app) / "Programs" / "Python" / ver / "python.exe"
            if p.exists():
                return str(p)
    else:
        for p in ["/usr/bin/python3", "/usr/local/bin/python3", "/opt/homebrew/bin/python3"]:
            if os.path.exists(p):
                return p

    return "python" if is_win else "python3"

PYTHON_BIN = detect_python_executable()

def kill_process_tree(pid: int):
    """Cleanly terminates a process and all of its spawned child workers."""
    if not pid:
        return
    if sys.platform == "win32":
        try:
            subprocess.run(
                f"taskkill /F /T /PID {pid}",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass
    else:
        try:
            # Terminate process group if available
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except Exception:
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass

def kill_port_owner(port: int = PORT):
    """Terminates any stray process occupying port 8420."""
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                conns = getattr(proc, 'net_connections', getattr(proc, 'connections', None))
                if not conns:
                    continue
                for c in conns(kind='inet'):
                    if c.laddr and c.laddr.port == port:
                        proc.terminate()
                        try:
                            proc.wait(timeout=1.0)
                        except Exception:
                            proc.kill()
            except Exception:
                pass
    except Exception:
        pass

    if sys.platform == "win32":
        try:
            cmd = f'netstat -ano -p tcp | findstr :{port}'
            out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
            for line in out.strip().splitlines():
                parts = line.split()
                if len(parts) >= 5 and f':{port}' in parts[1]:
                    pid = parts[-1]
                    if pid.isdigit() and pid != '0':
                        subprocess.run(f'taskkill /F /PID {pid}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    else:
        try:
            subprocess.run(f'lsof -ti :{port} | xargs kill -9', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            try:
                subprocess.run(f'fuser -k {port}/tcp', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

def run_backend():
    """Launches run.py backend server process."""
    run_py = REPO_ROOT / "run.py"
    cmd = [PYTHON_BIN, str(run_py), "--no-browser", "--port", str(PORT)]
    
    # Pre-clean port
    kill_port_owner(PORT)
    time.sleep(0.3)

    kwargs = {
        "cwd": str(REPO_ROOT),
        "env": {**os.environ, "PYTHONUNBUFFERED": "1"}
    }
    if sys.platform != "win32":
        kwargs["preexec_fn"] = os.setsid

    return subprocess.Popen(cmd, **kwargs)

def open_browser_when_ready():
    """Polls port 8420 until open, then opens default browser."""
    for _ in range(45):
        time.sleep(0.4)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex(('127.0.0.1', PORT)) == 0:
                webbrowser.open(URL)
                break

def launch_gui():
    """Starts the native desktop GUI."""
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except ImportError:
        # Headless fallback for servers / headless environments
        print(f"🚀 Headless Mode: Starting AI Job Auto-Applier on {URL}...")
        p = run_backend()
        open_browser_when_ready()
        try:
            p.wait()
        except KeyboardInterrupt:
            kill_process_tree(p.pid)
            kill_port_owner(PORT)
        return

    root = tk.Tk()
    os_name = "Windows" if sys.platform == "win32" else ("macOS" if sys.platform == "darwin" else "Linux")
    root.title(f"AI Job Auto-Applier - Desktop Launcher ({os_name})")
    root.geometry("520x360")
    root.configure(bg="#07090e")
    root.resizable(False, False)

    # Cross-platform font selections
    if sys.platform == "win32":
        font_family = "Segoe UI"
    elif sys.platform == "darwin":
        font_family = "Helvetica Neue"
    else:
        font_family = "DejaVu Sans"

    # Set Window Icon if available
    icon_path = REPO_ROOT / "desktop" / "assets" / ("icon.ico" if sys.platform == "win32" else "icon.png")
    if icon_path.exists():
        try:
            if sys.platform == "win32":
                root.iconbitmap(str(icon_path))
            else:
                img = tk.PhotoImage(file=str(icon_path))
                root.iconphoto(True, img)
        except Exception:
            pass

    # Title & Branding Header
    title_frame = tk.Frame(root, bg="#07090e")
    title_frame.pack(pady=22)

    title_lbl = tk.Label(
        title_frame,
        text="🚀 AI Job Auto-Applier",
        font=(font_family, 17, "bold"),
        fg="#ffffff",
        bg="#07090e"
    )
    title_lbl.pack()

    subtitle_lbl = tk.Label(
        title_frame,
        text="Autonomous Job Discovery & Resume Tailoring Cockpit",
        font=(font_family, 10),
        fg="#94a3b8",
        bg="#07090e"
    )
    subtitle_lbl.pack(pady=4)

    # Status Pill Box
    status_frame = tk.Frame(root, bg="#111827", highlightbackground="#1e293b", highlightthickness=1)
    status_frame.pack(pady=10, padx=30, fill="x")

    status_var = tk.StringVar(value="Status: ⏳ Initializing Engine & Verifying Port 8420...")
    status_lbl = tk.Label(
        status_frame,
        textvariable=status_var,
        font=(font_family, 10, "bold"),
        fg="#10b981",
        bg="#111827",
        pady=8
    )
    status_lbl.pack()

    # Meta Info Row
    meta_frame = tk.Frame(root, bg="#07090e")
    meta_frame.pack(pady=6)

    meta_lbl = tk.Label(
        meta_frame,
        text=f"Port: {PORT}  •  Platform: {os_name}  •  Python: {Path(PYTHON_BIN).name}",
        font=(font_family, 9),
        fg="#64748b",
        bg="#07090e"
    )
    meta_lbl.pack()

    # Control Action Buttons
    btn_frame = tk.Frame(root, bg="#07090e")
    btn_frame.pack(pady=18)

    server_proc = [None]

    def on_open_browser():
        webbrowser.open(URL)

    btn_open = tk.Button(
        btn_frame,
        text="🌐 Open Web Dashboard",
        command=on_open_browser,
        bg="#4f46e5",
        fg="#ffffff",
        activebackground="#4338ca",
        activeforeground="#ffffff",
        font=(font_family, 11, "bold"),
        relief="flat",
        padx=18,
        pady=9,
        cursor="hand2"
    )
    btn_open.pack(side="left", padx=10)

    def on_closing():
        status_var.set("Status: 🛑 Terminating Engine processes...")
        root.update()
        if server_proc[0]:
            try:
                kill_process_tree(server_proc[0].pid)
                server_proc[0].terminate()
            except Exception:
                pass
        kill_port_owner(PORT)
        root.destroy()

    def on_stop():
        on_closing()

    btn_stop = tk.Button(
        btn_frame,
        text="🛑 Stop & Exit",
        command=on_stop,
        bg="#dc2626",
        fg="#ffffff",
        activebackground="#b91c1c",
        activeforeground="#ffffff",
        font=(font_family, 11, "bold"),
        relief="flat",
        padx=18,
        pady=9,
        cursor="hand2"
    )
    btn_stop.pack(side="left", padx=10)

    # Background Engine Startup Thread
    def background_start():
        try:
            server_proc[0] = run_backend()
            open_browser_when_ready()
            status_var.set(f"Status: ● Online - Dashboard active on port {PORT}")
        except Exception as e:
            status_var.set(f"Status: ❌ Failed to start: {e}")

    threading.Thread(target=background_start, daemon=True).start()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    launch_gui()
