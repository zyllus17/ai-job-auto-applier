const { app, BrowserWindow, ipcMain, shell, Tray, Menu, nativeImage, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn, exec, execSync } = require('child_process');
const http = require('http');

// Global References
let mainWindow = null;
let tray = null;
let serverProcess = null;
let serverStatus = 'stopped'; // 'stopped' | 'starting' | 'running' | 'error'
const logBuffer = [];
const MAX_LOGS = 1500;
const SERVER_PORT = 8420;

// Resolve Repo Root
function getRepoRoot() {
  // 1. Explicit environment variable override
  if (process.env.AI_JOB_REPO_ROOT && fs.existsSync(path.join(process.env.AI_JOB_REPO_ROOT, 'run.py'))) {
    return path.resolve(process.env.AI_JOB_REPO_ROOT);
  }

  // 2. Packaged app: bundled resources
  if (app.isPackaged) {
    const resourceRepo = path.join(process.resourcesPath, 'repo');
    if (fs.existsSync(path.join(resourceRepo, 'run.py'))) return resourceRepo;

    const bundledAsar = path.join(process.resourcesPath, 'app.asar.unpacked');
    if (fs.existsSync(path.join(bundledAsar, 'run.py'))) return bundledAsar;

    // Check adjacent to app executable (portable mode)
    const exeDir = path.dirname(app.getPath('exe'));
    if (fs.existsSync(path.join(exeDir, 'run.py'))) return exeDir;
  }

  // 3. Current working directory
  const cwd = process.cwd();
  if (fs.existsSync(path.join(cwd, 'run.py'))) return cwd;

  // 4. Standard development path (parent of desktop/)
  const devPath = path.resolve(__dirname, '..', '..');
  if (fs.existsSync(path.join(devPath, 'run.py'))) return devPath;

  // 5. User home directory standard location
  const homePath = path.join(app.getPath('home'), 'personal', 'ai-job-auto-applier');
  if (fs.existsSync(path.join(homePath, 'run.py'))) return homePath;

  const homePath2 = path.join(app.getPath('home'), 'ai-job-auto-applier');
  if (fs.existsSync(path.join(homePath2, 'run.py'))) return homePath2;

  return devPath;
}

const REPO_ROOT = getRepoRoot();

// Helper to push logs
function addLog(level, message) {
  const timestamp = new Date().toLocaleTimeString();
  const entry = { timestamp, level, message };
  logBuffer.push(entry);
  if (logBuffer.length > MAX_LOGS) logBuffer.shift();

  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('log-message', entry);
  }
}

// Find Python executable on system across Windows, macOS, and Linux
function detectPython() {
  const isWin = process.platform === 'win32';

  // Check active virtual environment first
  if (process.env.VIRTUAL_ENV) {
    const venvPy = isWin
      ? path.join(process.env.VIRTUAL_ENV, 'Scripts', 'python.exe')
      : path.join(process.env.VIRTUAL_ENV, 'bin', 'python3');
    if (fs.existsSync(venvPy)) return venvPy;
  }

  const candidates = isWin
    ? [
        path.join(REPO_ROOT, '.venv', 'Scripts', 'python.exe'),
        path.join(REPO_ROOT, 'venv', 'Scripts', 'python.exe'),
        'python.exe',
        'py.exe',
        'python3.exe',
        path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python312', 'python.exe'),
        path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python311', 'python.exe'),
        path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python310', 'python.exe')
      ]
    : [
        path.join(REPO_ROOT, '.venv', 'bin', 'python3'),
        path.join(REPO_ROOT, 'venv', 'bin', 'python3'),
        '/opt/homebrew/bin/python3',
        '/usr/local/bin/python3',
        '/usr/bin/python3',
        path.join(process.env.HOME || '', '.local', 'bin', 'python3'),
        'python3',
        'python'
      ];

  for (const cmd of candidates) {
    try {
      const out = execSync(`"${cmd}" -c "import sys; print(sys.executable)"`, {
        encoding: 'utf-8',
        stdio: ['pipe', 'pipe', 'ignore'],
        timeout: 2500
      }).trim();
      if (out && fs.existsSync(out)) {
        return out;
      }
    } catch (e) {
      // Continue checking next candidate
    }
  }
  return isWin ? 'python' : 'python3';
}

const pythonExecutable = detectPython();

// Check if port 8420 is actively responding
function checkPortOpen(port = SERVER_PORT) {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${port}/api/health`, (res) => {
      resolve(res.statusCode === 200);
    });
    req.on('error', () => {
      // Check root if /api/health not ready yet
      const req2 = http.get(`http://127.0.0.1:${port}/`, (res2) => {
        resolve(res2.statusCode < 500);
      });
      req2.on('error', () => resolve(false));
      req2.setTimeout(1000, () => {
        req2.destroy();
        resolve(false);
      });
    });
    req.setTimeout(1000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

// Kill anything occupying port 8420 across Windows, macOS, and Linux
function killPort(port = SERVER_PORT) {
  return new Promise((resolve) => {
    addLog('info', `🧹 Checking and freeing port ${port}...`);
    const isWin = process.platform === 'win32';
    if (isWin) {
      exec(`netstat -ano | findstr :${port}`, (err, stdout) => {
        if (!err && stdout) {
          const lines = stdout.trim().split('\n');
          for (const line of lines) {
            const parts = line.trim().split(/\s+/);
            const pid = parts[parts.length - 1];
            if (pid && pid !== '0') {
              try {
                // Kill process tree on Windows
                execSync(`taskkill /F /T /PID ${pid}`);
                addLog('info', `Terminated PID ${pid} holding port ${port}`);
              } catch (_) {}
            }
          }
        }
        resolve(true);
      });
    } else {
      // Unix: try lsof first, then fuser fallback
      exec(`lsof -ti :${port}`, (err, stdout) => {
        if (!err && stdout) {
          const pids = stdout.trim().split('\n').filter(Boolean);
          for (const pid of pids) {
            try {
              execSync(`kill -9 ${pid}`);
              addLog('info', `Terminated PID ${pid} holding port ${port}`);
            } catch (_) {}
          }
          resolve(true);
        } else {
          // Linux fallback without lsof
          try {
            execSync(`fuser -k ${port}/tcp`);
            addLog('info', `Freed port ${port} via fuser`);
          } catch (_) {}
          resolve(true);
        }
      });
    }
  });
}

// Start the Backend Server (FastAPI / Dashboard)
async function startServer() {
  if (serverStatus === 'running' || serverStatus === 'starting') {
    return { success: true, message: 'Server is already running or starting.' };
  }

  // Check if port already active from previous outside instance
  const alreadyOpen = await checkPortOpen();
  if (alreadyOpen) {
    serverStatus = 'running';
    updateServerStatus('running');
    addLog('info', `Attached to existing server running on http://127.0.0.1:${SERVER_PORT}`);
    return { success: true, message: 'Connected to existing dashboard instance.' };
  }

  serverStatus = 'starting';
  updateServerStatus('starting');
  addLog('info', `🚀 Initializing AI Job Auto-Applier Engine with Python: ${pythonExecutable}`);

  await killPort(SERVER_PORT);

  const runPyPath = path.join(REPO_ROOT, 'run.py');
  const serverArgs = [runPyPath, '--no-browser', '--port', String(SERVER_PORT)];

  try {
    serverProcess = spawn(pythonExecutable, serverArgs, {
      cwd: REPO_ROOT,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
        PATH: process.env.PATH
      }
    });

    serverProcess.stdout.on('data', (data) => {
      const text = data.toString();
      text.split('\n').forEach(line => {
        if (line.trim()) addLog('info', line.trim());
      });
    });

    serverProcess.stderr.on('data', (data) => {
      const text = data.toString();
      text.split('\n').forEach(line => {
        if (line.trim()) {
          if (line.includes('ERROR') || line.includes('Error') || line.includes('Traceback')) {
            addLog('error', line.trim());
          } else {
            addLog('info', line.trim());
          }
        }
      });
    });

    serverProcess.on('error', (err) => {
      addLog('error', `Server process failure: ${err.message}`);
      serverStatus = 'error';
      updateServerStatus('error');
    });

    serverProcess.on('close', (code) => {
      addLog('warn', `Server process terminated (code: ${code})`);
      serverStatus = 'stopped';
      serverProcess = null;
      updateServerStatus('stopped');
    });

    // Wait until port is reachable
    let retries = 35;
    while (retries > 0) {
      await new Promise(r => setTimeout(r, 600));
      const isOpen = await checkPortOpen();
      if (isOpen) {
        serverStatus = 'running';
        updateServerStatus('running');
        addLog('success', `✨ Engine active and listening on http://localhost:${SERVER_PORT}`);
        return { success: true, port: SERVER_PORT };
      }
      retries--;
    }

    serverStatus = 'error';
    updateServerStatus('error');
    return { success: false, message: 'Server launched but timed out waiting for port response.' };

  } catch (err) {
    serverStatus = 'error';
    updateServerStatus('error');
    addLog('error', `Failed to spawn server: ${err.message}`);
    return { success: false, message: err.message };
  }
}

// Stop Server
async function stopServer() {
  addLog('info', '🛑 Stopping AI Job Auto-Applier Engine...');
  if (serverProcess) {
    try {
      serverProcess.kill('SIGINT');
      setTimeout(() => {
        if (serverProcess) {
          try { serverProcess.kill('SIGKILL'); } catch (_) {}
        }
      }, 1500);
    } catch (_) {}
  }
  await killPort(SERVER_PORT);
  serverStatus = 'stopped';
  serverProcess = null;
  updateServerStatus('stopped');
  addLog('info', '✅ Engine stopped cleanly.');
  return { success: true };
}

function updateServerStatus(status) {
  serverStatus = status;
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('server-status-changed', {
      status,
      port: SERVER_PORT,
      pid: serverProcess ? serverProcess.pid : null
    });
  }
  if (tray) {
    const isRunning = status === 'running';
    tray.setToolTip(`AI Job Auto-Applier (${status})`);
  }
}

// Environment & Health Check
async function checkEnvironment() {
  const result = {
    python: { ok: false, version: '', path: pythonExecutable },
    latex: { ok: false, path: '' },
    bun: { ok: false, version: '' },
    node: { ok: false, version: '' },
    dependencies: { ok: false, details: [] },
    serverRunning: serverStatus === 'running' || await checkPortOpen(),
    port: SERVER_PORT,
    repoRoot: REPO_ROOT
  };

  // Python Check
  try {
    const pyVer = execSync(`"${pythonExecutable}" --version`, { encoding: 'utf-8', timeout: 2000 }).trim();
    result.python.ok = true;
    result.python.version = pyVer;
  } catch (e) {
    result.python.ok = false;
  }

  // LaTeX Check
  const isWin = process.platform === 'win32';
  const latexCmd = isWin
    ? 'where lualatex'
    : 'which lualatex || ls ~/Library/TinyTeX/bin/*/lualatex 2>/dev/null || ls ~/.TinyTeX/bin/*/lualatex 2>/dev/null';
  try {
    const lpath = execSync(latexCmd, { encoding: 'utf-8', timeout: 2000 }).trim().split('\n')[0];
    if (lpath) {
      result.latex.ok = true;
      result.latex.path = lpath;
    }
  } catch (_) {
    result.latex.ok = false;
  }

  // Bun & Node
  try {
    result.bun.version = execSync('bun --version', { encoding: 'utf-8', timeout: 2000 }).trim();
    result.bun.ok = true;
  } catch (_) {}

  try {
    result.node.version = execSync('node --version', { encoding: 'utf-8', timeout: 2000 }).trim();
    result.node.ok = true;
  } catch (_) {}

  // Python Dependencies
  try {
    const testScript = `
import fastapi, uvicorn, playwright, websockets, psutil
print("ALL_OK")
`;
    const checkOut = execSync(`"${pythonExecutable}" -c "${testScript.replace(/\n/g, ' ')}"`, {
      encoding: 'utf-8',
      timeout: 3000
    }).trim();
    result.dependencies.ok = checkOut.includes('ALL_OK');
  } catch (_) {
    result.dependencies.ok = false;
  }

  return result;
}

// Profile & Env Reader/Writer
function getProfileData() {
  const envPath = path.join(REPO_ROOT, '.env');
  const candidateJsonPath = path.join(REPO_ROOT, 'tools', 'candidate_profile.json');

  let envConfig = {};
  if (fs.existsSync(envPath)) {
    const lines = fs.readFileSync(envPath, 'utf-8').split('\n');
    lines.forEach(l => {
      const match = l.match(/^\s*([\w_]+)\s*=\s*(.*)?\s*$/);
      if (match) {
        const val = match[2] ? match[2].trim().replace(/^['"](.*)['"]$/, '$1') : '';
        envConfig[match[1]] = val;
      }
    });
  }

  let candidateProfile = {};
  if (fs.existsSync(candidateJsonPath)) {
    try {
      candidateProfile = JSON.parse(fs.readFileSync(candidateJsonPath, 'utf-8'));
    } catch (_) {}
  }

  return { env: envConfig, profile: candidateProfile };
}

function saveProfileData(data) {
  const envPath = path.join(REPO_ROOT, '.env');
  const candidateJsonPath = path.join(REPO_ROOT, 'tools', 'candidate_profile.json');

  try {
    if (data.env) {
      let currentEnv = '';
      if (fs.existsSync(envPath)) {
        currentEnv = fs.readFileSync(envPath, 'utf-8');
      }
      for (const [key, val] of Object.entries(data.env)) {
        const regex = new RegExp(`^${key}=.*$`, 'm');
        if (regex.test(currentEnv)) {
          currentEnv = currentEnv.replace(regex, `${key}=${val}`);
        } else {
          currentEnv += `\n${key}=${val}`;
        }
      }
      fs.writeFileSync(envPath, currentEnv.trim() + '\n', 'utf-8');
    }

    if (data.profile) {
      fs.writeFileSync(candidateJsonPath, JSON.stringify(data.profile, null, 2), 'utf-8');
    }

    addLog('success', 'Candidate profile & environment variables updated.');
    return { success: true };
  } catch (err) {
    addLog('error', `Failed to save configuration: ${err.message}`);
    return { success: false, message: err.message };
  }
}

// Create Main Window
function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1240,
    height: 840,
    minWidth: 1000,
    minHeight: 680,
    title: 'AI Job Auto-Applier',
    backgroundColor: '#07090e',
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    frame: true,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: false // Enables embedded dashboard iframe/fetch to localhost:8420
    }
  });

  // Intercept external links and open in OS default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (!url.startsWith('file://')) {
      event.preventDefault();
      shell.openExternal(url);
    }
  });

  mainWindow.loadFile(path.join(__dirname, 'index.html'));

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    // Auto start server on launch
    startServer();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// Setup IPC Handlers
function setupIpc() {
  ipcMain.handle('check-environment', async () => await checkEnvironment());
  ipcMain.handle('start-server', async () => await startServer());
  ipcMain.handle('stop-server', async () => await stopServer());
  ipcMain.handle('restart-server', async () => {
    await stopServer();
    await new Promise(r => setTimeout(r, 1000));
    return await startServer();
  });
  ipcMain.handle('clean-port', async () => {
    await killPort(SERVER_PORT);
    serverStatus = 'stopped';
    updateServerStatus('stopped');
    return { success: true };
  });
  ipcMain.handle('run-setup', async () => {
    addLog('info', '📦 Running automated dependency setup...');
    return new Promise((resolve) => {
      const cmd = `"${pythonExecutable}" "${path.join(REPO_ROOT, 'run.py')}" --install`;
      exec(cmd, { cwd: REPO_ROOT }, (err, stdout, stderr) => {
        if (err) {
          addLog('error', `Setup error: ${stderr || err.message}`);
          resolve({ success: false, message: stderr || err.message });
        } else {
          addLog('success', '✅ Dependencies installation completed.');
          resolve({ success: true, output: stdout });
        }
      });
    });
  });

  // Distributable Builder IPC (mac, win, linux)
  ipcMain.handle('build-distributable', async (_, targetPlatform) => {
    const desktopDir = path.join(REPO_ROOT, 'desktop');
    const distDir = path.join(desktopDir, 'dist');
    addLog('info', `🚀 Starting package build for: ${targetPlatform.toUpperCase()}...`);

    const hasBun = (() => { try { execSync('bun --version', { stdio: 'ignore' }); return true; } catch (_) { return false; } })();
    const hasNpm = (() => { try { execSync('npm --version', { stdio: 'ignore' }); return true; } catch (_) { return false; } })();

    let buildCmd = '';
    let buildCwd = desktopDir;

    if (targetPlatform === 'mac') {
      if (hasBun) buildCmd = 'bun run build:mac';
      else if (hasNpm) buildCmd = 'npm run build:mac';
      else {
        buildCmd = `bash "${path.join(REPO_ROOT, 'tools', 'build_mac_dmg.sh')}"`;
        buildCwd = REPO_ROOT;
      }
    } else if (targetPlatform === 'win') {
      if (hasBun) buildCmd = 'bun run build:win';
      else if (hasNpm) buildCmd = 'npm run build:win';
      else {
        buildCmd = `"${pythonExecutable}" "${path.join(REPO_ROOT, 'tools', 'build_win_exe.py')}"`;
        buildCwd = REPO_ROOT;
      }
    } else if (targetPlatform === 'linux') {
      if (hasBun) buildCmd = 'bun run build:linux';
      else if (hasNpm) buildCmd = 'npm run build:linux';
      else {
        buildCmd = `bash "${path.join(REPO_ROOT, 'tools', 'build_linux_app.sh')}"`;
        buildCwd = REPO_ROOT;
      }
    } else {
      return { success: false, message: `Unknown platform: ${targetPlatform}` };
    }

    addLog('info', `Running: ${buildCmd}`);

    return new Promise((resolve) => {
      const proc = exec(buildCmd, { cwd: buildCwd });
      proc.stdout.on('data', (d) => {
        d.toString().split('\n').forEach(line => {
          if (line.trim()) addLog('info', line.trim());
        });
      });
      proc.stderr.on('data', (d) => {
        d.toString().split('\n').forEach(line => {
          if (line.trim()) addLog('warn', line.trim());
        });
      });
      proc.on('close', (code) => {
        if (code === 0) {
          addLog('success', `✨ Successfully built ${targetPlatform.toUpperCase()} installer in desktop/dist!`);
          try {
            if (fs.existsSync(distDir)) shell.openPath(distDir);
          } catch (_) {}
          resolve({ success: true, distDir });
        } else {
          addLog('error', `Build process exited with code ${code}.`);
          resolve({ success: false, code });
        }
      });
    });
  });

  ipcMain.handle('get-services', async () => {
    try {
      const res = await new Promise((resolve) => {
        http.get(`http://127.0.0.1:${SERVER_PORT}/api/services`, (r) => {
          let data = '';
          r.on('data', chunk => data += chunk);
          r.on('end', () => {
            try { resolve(JSON.parse(data)); } catch (_) { resolve(null); }
          });
        }).on('error', () => resolve(null));
      });
      return res;
    } catch (_) {
      return null;
    }
  });

  ipcMain.handle('toggle-service', async (_, serviceId, action) => {
    try {
      const postData = JSON.stringify({});
      const options = {
        hostname: '127.0.0.1',
        port: SERVER_PORT,
        path: `/api/services/${serviceId}/${action}`,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(postData)
        }
      };

      return new Promise((resolve) => {
        const req = http.request(options, (res) => {
          let body = '';
          res.on('data', chunk => body += chunk);
          res.on('end', () => {
            try {
              resolve(JSON.parse(body));
            } catch (_) {
              resolve({ success: res.statusCode < 400 });
            }
          });
        });
        req.on('error', (e) => resolve({ success: false, message: e.message }));
        req.write(postData);
        req.end();
      });
    } catch (e) {
      return { success: false, message: e.message };
    }
  });

  ipcMain.handle('get-profile', () => getProfileData());
  ipcMain.handle('save-profile', (_, data) => saveProfileData(data));

  ipcMain.handle('open-external', (_, url) => {
    shell.openExternal(url);
    return true;
  });

  ipcMain.handle('open-folder', (_, folderType) => {
    let target = REPO_ROOT;
    if (folderType === 'applications') target = path.join(REPO_ROOT, 'documents', 'applications');
    else if (folderType === 'cv') target = path.join(REPO_ROOT, 'cv');
    else if (folderType === 'logs') target = path.join(REPO_ROOT, 'logs');
    else if (folderType === 'cover_letters') target = path.join(REPO_ROOT, 'cover_letters');
    else if (folderType === 'dist') target = path.join(REPO_ROOT, 'desktop', 'dist');

    if (!fs.existsSync(target)) fs.mkdirSync(target, { recursive: true });
    shell.openPath(target);
    return true;
  });

  ipcMain.handle('get-logs', () => logBuffer);
}

// Clean shutdown helper
async function cleanupProcesses() {
  if (serverProcess) {
    try {
      if (process.platform === 'win32') {
        execSync(`taskkill /F /T /PID ${serverProcess.pid}`);
      } else {
        serverProcess.kill('SIGKILL');
      }
    } catch (_) {}
  }
  await killPort(SERVER_PORT);
}

// App Lifecycle
app.whenReady().then(() => {
  setupIpc();
  createMainWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createMainWindow();
  });
});

app.on('before-quit', async (e) => {
  await cleanupProcesses();
});

app.on('window-all-closed', async () => {
  await cleanupProcesses();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

