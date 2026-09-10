import sys
import asyncio
import signal
import json
import csv
import os
import time
import logging
import subprocess
import socket
from collections import deque, Counter
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

import psutil
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from dotenv import load_dotenv
from pydantic import BaseModel

# Constants
REPO_ROOT = Path(__file__).parent.parent.resolve()
TOOLS_DIR = REPO_ROOT / 'tools'
TRACKER_CSV = REPO_ROOT / 'job_search_tracker.csv'
ENV_FILE = REPO_ROOT / '.env'
CANDIDATE_PROFILE = TOOLS_DIR / 'candidate_profile.json'
PORT = 8420

SERVICE_REGISTRY = {
    'job_daemon': {
        'name': 'Job Search Daemon',
        'description': 'Continuous job scanning across portals',
        'command': [sys.executable, str(TOOLS_DIR / 'daemon_job_runner.py'), '--interval-mins', '60'],
        'icon': '🔍',
        'color': '#22c55e',  # green
    },
    'browser_autoapply': {
        'name': 'Browser Auto-Apply',
        'description': 'Anti-detect browser form filling',
        'command': [sys.executable, str(TOOLS_DIR / 'browser_autofill.py')],
        'icon': '🌐',
        'color': '#f97316',  # orange
    },
    'telegram_bot': {
        'name': 'Telegram Bot',
        'description': 'Remote control via Telegram',
        'command': [sys.executable, str(TOOLS_DIR / 'telegram_bot.py')],
        'icon': '📱',
        'color': '#3b82f6',  # blue
    },
    'project_scaffolder': {
        'name': 'Project Scaffolder',
        'description': 'Daily skill-gap demo project builder',
        'command': [sys.executable, str(TOOLS_DIR / 'project_scaffolder.py'), '--daemon'],
        'icon': '📦',
        'color': '#06b6d4',  # cyan
    },
    'recruiter_outreach': {
        'name': 'Recruiter Outreach',
        'description': 'Find recruiters & draft cold messages',
        'command': [sys.executable, str(TOOLS_DIR / 'recruiter_finder.py')],
        'icon': '🤝',
        'color': '#ec4899',  # pink
    },
    'sheets_sync': {
        'name': 'Google Sheets Sync',
        'description': 'Sync tracker to Google Sheets',
        'command': [sys.executable, str(TOOLS_DIR / 'google_sheets_sync.py')],
        'icon': '📊',
        'color': '#a855f7',  # purple
    },
}

class ProcessManager:
    def __init__(self):
        self.processes: Dict[str, Dict] = {}
        self.log_buffer: deque = deque(maxlen=1000)
        self.ws_clients: set[WebSocket] = set()
    
    async def start_service(self, service_id: str) -> dict:
        if service_id not in SERVICE_REGISTRY:
            raise HTTPException(status_code=404, detail="Service not found")
            
        current = self.processes.get(service_id)
        if current and current.get('status') == 'running':
            if current['process'].returncode is None:
                return self.get_status(service_id)
                
        svc = SERVICE_REGISTRY[service_id]
        cmd = svc['command']
        
        try:
            sub_env = dict(os.environ)
            sub_env["PYTHONUNBUFFERED"] = "1"
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=sub_env
            )
            
            self.processes[service_id] = {
                'process': process,
                'start_time': time.time(),
                'status': 'running'
            }
            
            asyncio.create_task(self._stream_logs(service_id, process))
            
            status = self.get_status(service_id)
            await self.broadcast({'type': 'status_update', 'service': status})
            return status
            
        except Exception as e:
            self.processes[service_id] = {
                'process': None,
                'start_time': time.time(),
                'status': 'error'
            }
            status = self.get_status(service_id)
            await self.broadcast({'type': 'status_update', 'service': status})
            raise HTTPException(status_code=500, detail=str(e))

    async def stop_service(self, service_id: str) -> dict:
        current = self.processes.get(service_id)
        if not current or current['status'] != 'running' or not current['process']:
            return self.get_status(service_id)
            
        proc = current['process']
        if proc.returncode is None:
            try:
                parent = psutil.Process(proc.pid)
                children = parent.children(recursive=True)
                
                # SIGTERM
                for child in children:
                    try:
                        child.terminate()
                    except psutil.NoSuchProcess:
                        pass
                try:
                    parent.terminate()
                except psutil.NoSuchProcess:
                    pass
                    
                # Wait
                _, alive = psutil.wait_procs(children + [parent], timeout=5.0)
                
                # SIGKILL for alive
                for p in alive:
                    try:
                        p.kill()
                    except psutil.NoSuchProcess:
                        pass
                        
            except psutil.NoSuchProcess:
                pass
            except Exception as e:
                logging.error(f"Error killing process {proc.pid}: {e}")
                
            try:
                proc.kill()
            except ProcessLookupError:
                pass
                
        self.processes[service_id]['status'] = 'idle'
        status = self.get_status(service_id)
        await self.broadcast({'type': 'status_update', 'service': status})
        return status
        
    def get_status(self, service_id: str) -> dict:
        svc = SERVICE_REGISTRY.get(service_id)
        if not svc:
            return {}
            
        res = {
            'id': service_id,
            'name': svc['name'],
            'icon': svc['icon'],
            'color': svc['color'],
            'description': svc['description'],
            'status': 'idle',
            'uptime_seconds': 0
        }
        
        current = self.processes.get(service_id)
        if current:
            proc = current.get('process')
            if proc and proc.returncode is None:
                res['status'] = 'running'
                res['uptime_seconds'] = int(time.time() - current['start_time'])
            else:
                if current['status'] == 'running':
                    current['status'] = 'idle'
                res['status'] = current['status']
                
        return res

    def get_all_statuses(self) -> list[dict]:
        return [self.get_status(sid) for sid in SERVICE_REGISTRY.keys()]

    async def _stream_logs(self, service_id: str, process):
        svc_name = SERVICE_REGISTRY[service_id]['name']
        while process.returncode is None:
            line = await process.stdout.readline()
            if not line:
                break
                
            text = line.decode('utf-8', errors='replace').rstrip('\n')
            level = 'INFO'
            if 'ERROR' in text or 'Exception' in text:
                level = 'ERROR'
            elif 'WARN' in text:
                level = 'WARNING'
                
            entry = {
                'timestamp': datetime.now().isoformat(),
                'service_id': service_id,
                'service_name': svc_name,
                'message': text,
                'level': level
            }
            
            self.log_buffer.append(entry)
            await self.broadcast({'type': 'log', 'log': entry})
            
        # Process ended
        if self.processes.get(service_id):
            self.processes[service_id]['status'] = 'idle' if process.returncode == 0 else 'error'
        status = self.get_status(service_id)
        await self.broadcast({'type': 'status_update', 'service': status})

    async def broadcast(self, message: dict):
        dead_clients = set()
        for client in self.ws_clients:
            try:
                await client.send_json(message)
            except Exception:
                dead_clients.add(client)
                
        for client in dead_clients:
            self.ws_clients.discard(client)

    async def cleanup(self):
        for sid in list(self.processes.keys()):
            await self.stop_service(sid)

app = FastAPI(title='AI Job Auto-Applier Dashboard')
load_dotenv(ENV_FILE)
manager = ProcessManager()

static_dir = Path(__file__).parent / 'static'
static_dir.mkdir(parents=True, exist_ok=True)
if not (static_dir / 'index.html').exists():
    (static_dir / 'index.html').write_text("<html><body><h1>AI Job Auto-Applier</h1></body></html>")
    
app.mount('/static', StaticFiles(directory=str(static_dir)), name='static')

@app.on_event('shutdown')
async def shutdown():
    await manager.cleanup()

@app.get('/')
async def index():
    return FileResponse(str(Path(__file__).parent / 'static' / 'index.html'))

@app.get('/favicon.ico')
async def favicon():
    return HTMLResponse(content="", status_code=204)

@app.get('/api/services')
async def get_services():
    return manager.get_all_statuses()

@app.post('/api/services/{service_id}/start')
async def start_service_api(service_id: str):
    return await manager.start_service(service_id)

@app.post('/api/services/{service_id}/stop')
async def stop_service_api(service_id: str):
    return await manager.stop_service(service_id)

def read_tracker_csv():
    rows = []
    if not TRACKER_CSV.exists():
        return rows
    try:
        with open(TRACKER_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception as e:
        logging.error(f"Error reading CSV: {e}")
    return rows

@app.get('/api/stats')
async def get_stats():
    rows = read_tracker_csv()
    total_jobs = len(rows)
    staged = 0
    applied = 0
    interviews = 0
    offers = 0
    fit_scores = []
    missing_skills = []
    
    for r in rows:
        st = r.get('status', '').lower()
        if 'staged' in st: staged += 1
        if 'applied' in st: applied += 1
        if 'interview' in st: interviews += 1
        if 'offer' in st: offers += 1
        
        fs = r.get('fitScore', '')
        if fs.isdigit():
            fit_scores.append(int(fs))
            
        ms = r.get('missingSkill', '')
        if ms:
            # Split by comma first, then individual skills by ' / ' (with spaces)
            parts = [s.strip() for s in ms.split(',')]
            for part in parts:
                # Split on ' / ' but not inside parentheses
                subparts = [s.strip() for s in part.split(' / ')]
                for skill in subparts:
                    if skill and skill.lower() not in ('none', 'n/a', '-', 'na', ''):
                        missing_skills.append(skill)
            
    avg_fit = sum(fit_scores) / len(fit_scores) if fit_scores else 0
    top_missing = dict(Counter(missing_skills).most_common(10))
    
    return {
        'total_jobs': total_jobs,
        'staged': staged,
        'applied': applied,
        'interviews': interviews,
        'offers': offers,
        'avg_fit_score': round(avg_fit, 2),
        'top_skills_missing': top_missing
    }

@app.get('/api/jobs')
async def get_jobs(search: str = '', sort_by: str = '', sort_order: str = 'asc', page: int = 1, per_page: int = 50):
    rows = read_tracker_csv()
    
    if search:
        search = search.lower()
        filtered = []
        for r in rows:
            if search in r.get('company', '').lower() or \
               search in r.get('title', '').lower() or \
               search in r.get('missingSkill', '').lower():
                filtered.append(r)
        rows = filtered
        
    if sort_by:
        reverse = (sort_order.lower() == 'desc')
        try:
            rows.sort(key=lambda x: x.get(sort_by, ''), reverse=reverse)
        except Exception:
            pass
            
    start = (page - 1) * per_page
    end = start + per_page
    paginated = rows[start:end]
    
    return {
        'data': paginated,
        'total': len(rows),
        'page': page,
        'per_page': per_page
    }

@app.get('/api/analytics')
async def get_analytics():
    rows = read_tracker_csv()
    
    discovered = len(rows)
    staged = 0
    applied = 0
    interviews = 0
    offers = 0
    missing_skills = []
    fit_dist = {"60-70": 0, "70-80": 0, "80-90": 0, "90-100": 0}
    daily_counts = Counter()
    companies = Counter()
    
    for r in rows:
        st = r.get('status', '').lower()
        if 'staged' in st: staged += 1
        if 'applied' in st: applied += 1
        if 'interview' in st: interviews += 1
        if 'offer' in st: offers += 1
        
        fs = r.get('fitScore', '')
        if fs.isdigit():
            val = int(fs)
            if 60 <= val < 70: fit_dist["60-70"] += 1
            elif 70 <= val < 80: fit_dist["70-80"] += 1
            elif 80 <= val < 90: fit_dist["80-90"] += 1
            elif 90 <= val <= 100: fit_dist["90-100"] += 1
            
        ms = r.get('missingSkill', '')
        if ms:
            parts = [s.strip() for s in ms.split(',')]
            for part in parts:
                subparts = [s.strip() for s in part.split(' / ')]
                for skill in subparts:
                    if skill and skill.lower() not in ('none', 'n/a', '-', 'na', ''):
                        missing_skills.append(skill)
            
        ts = r.get('timestamp', '')
        if ts:
            try:
                date_str = ts.split('T')[0] if 'T' in ts else ts.split()[0]
                daily_counts[date_str] += 1
            except: pass
            
        comp = r.get('company', '')
        if comp:
            companies[comp] += 1
            
    top_skills = [{"skill": k, "count": v} for k, v in Counter(missing_skills).most_common(10)]
    timeline = [{"date": k, "count": v} for k, v in sorted(daily_counts.items())]
    top_comps = [{"company": k, "count": v} for k, v in companies.most_common(10)]
    
    return {
        'funnel': {
            'discovered': discovered,
            'staged': staged,
            'applied': applied,
            'interview': interviews,
            'offer': offers
        },
        'skill_gaps': top_skills,
        'fit_distribution': fit_dist,
        'daily_timeline': timeline,
        'top_companies': top_comps
    }

@app.get('/api/settings')
async def get_settings():
    settings = {}
    
    if ENV_FILE.exists():
        try:
            with open(ENV_FILE, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        if len(v) > 4:
                            settings[k] = '*' * (len(v)-4) + v[-4:]
                        else:
                            settings[k] = '****'
        except Exception:
            pass
            
    if CANDIDATE_PROFILE.exists():
        try:
            with open(CANDIDATE_PROFILE, 'r') as f:
                settings['candidate_profile'] = json.load(f)
        except Exception:
            pass
            
    return settings

class SettingsInput(BaseModel):
    env_vars: Optional[Dict[str, str]] = None
    candidate_profile: Optional[Dict[str, Any]] = None

@app.post('/api/settings')
async def update_settings(data: SettingsInput):
    if data.env_vars:
        current_env = {}
        if ENV_FILE.exists():
            with open(ENV_FILE, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        current_env[k] = v
                        
        for k, v in data.env_vars.items():
            if not v.endswith('****'):
                current_env[k] = v
                
        with open(ENV_FILE, 'w') as f:
            for k, v in current_env.items():
                f.write(f"{k}={v}\n")
                
    if data.candidate_profile:
        CANDIDATE_PROFILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CANDIDATE_PROFILE, 'w') as f:
            json.dump(data.candidate_profile, f, indent=2)
            
    return {"status": "success"}

@app.post('/api/actions/scan-once')
async def action_scan_once():
    cmd = [sys.executable, str(TOOLS_DIR / 'daemon_job_runner.py'), '--once']
    subprocess.Popen(cmd)
    return {"status": "started"}

@app.post('/api/actions/scaffold')
async def action_scaffold():
    cmd = [sys.executable, str(TOOLS_DIR / 'project_scaffolder.py'), '--force']
    subprocess.Popen(cmd)
    return {"status": "started"}

@app.post('/api/actions/sync-sheets')
async def action_sync_sheets():
    cmd = [sys.executable, str(TOOLS_DIR / 'google_sheets_sync.py')]
    subprocess.Popen(cmd)
    return {"status": "started"}

@app.get('/api/health')
async def get_health():
    uptime = time.time() - psutil.boot_time()
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory().percent
    
    internet = False
    try:
        socket.setdefaulttimeout(3)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        internet = True
    except socket.error:
        pass
        
    return {
        'status': 'ok',
        'uptime': uptime,
        'cpu_percent': cpu,
        'memory_percent': mem,
        'internet': internet
    }

@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    manager.ws_clients.add(websocket)
    await websocket.send_json({
        'type': 'init',
        'services': manager.get_all_statuses(),
        'logs': list(manager.log_buffer)
    })
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.ws_clients.discard(websocket)
    except Exception:
        manager.ws_clients.discard(websocket)

if __name__ == '__main__':
    uvicorn.run('dashboard.server:app', host='0.0.0.0', port=PORT, reload=True)
