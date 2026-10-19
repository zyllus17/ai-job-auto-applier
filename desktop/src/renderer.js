// AI Job Auto-Applier Desktop Launcher - Renderer Logic

let currentServerStatus = 'stopped';
let uptimeInterval = null;
let startTime = null;
let logsCount = 0;

// DOM Elements
const statusPill = document.getElementById('status-pill');
const statusText = document.getElementById('status-text');
const heroStatusLabel = document.getElementById('hero-status-label');
const masterBtn = document.getElementById('btn-master-engine');
const masterBtnText = document.getElementById('master-btn-text');
const masterSpinner = document.getElementById('master-spinner');
const metaPort = document.getElementById('meta-port');
const metaPid = document.getElementById('meta-pid');
const metaUptime = document.getElementById('meta-uptime');

const crmIframe = document.getElementById('crm-iframe');
const iframePlaceholder = document.getElementById('iframe-placeholder');
const embeddedUrlDisplay = document.getElementById('embedded-url-display');
const consoleStream = document.getElementById('console-stream');
const logCounter = document.getElementById('log-counter');
const chkAutoscroll = document.getElementById('chk-autoscroll');

// Tab Navigation
document.querySelectorAll('.nav-item').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

    btn.classList.add('active');
    const tabId = btn.getAttribute('data-tab');
    const targetPane = document.getElementById(`pane-${tabId}`);
    if (targetPane) targetPane.classList.add('active');

    if (tabId === 'embedded-dashboard' && currentServerStatus === 'running') {
      reloadIframe();
    }
  });
});

// Switch to Embedded CRM helper
document.getElementById('btn-switch-embedded')?.addEventListener('click', () => {
  const crmTab = document.querySelector('.nav-item[data-tab="embedded-dashboard"]');
  if (crmTab) crmTab.click();
});

// Master Engine Start / Stop
masterBtn.addEventListener('click', async () => {
  if (currentServerStatus === 'running') {
    setButtonLoading(true, 'Stopping...');
    await window.api.stopServer();
    setButtonLoading(false);
  } else if (currentServerStatus === 'stopped' || currentServerStatus === 'error') {
    setButtonLoading(true, 'Starting...');
    await window.api.startServer();
    setButtonLoading(false);
  }
});

function setButtonLoading(loading, text = '') {
  if (loading) {
    masterSpinner.style.display = 'block';
    masterBtn.querySelector('.btn-icon').style.display = 'none';
    if (text) masterBtnText.textContent = text;
    masterBtn.disabled = true;
  } else {
    masterSpinner.style.display = 'none';
    masterBtn.querySelector('.btn-icon').style.display = 'block';
    masterBtn.disabled = false;
  }
}

// Server Status Update
function updateStatusUI(data) {
  const { status, port, pid } = data;
  currentServerStatus = status;

  statusPill.className = `status-indicator status-${status}`;
  
  if (status === 'running') {
    statusText.textContent = `Online • Port ${port || 8420}`;
    heroStatusLabel.textContent = 'ENGINE ACTIVE';
    masterBtn.className = 'engine-master-btn btn-stop';
    masterBtnText.textContent = 'Stop Engine';
    masterBtn.querySelector('.btn-icon').innerHTML = '<rect x="6" y="6" width="12" height="12"/>';
    
    metaPort.textContent = `http://localhost:${port || 8420}`;
    metaPid.textContent = pid ? `PID ${pid}` : 'Active';
    
    if (!startTime) startTime = Date.now();
    startUptimeTimer();

    // Enable Embedded CRM
    iframePlaceholder.style.display = 'none';
    if (!crmIframe.src || crmIframe.src === 'about:blank') {
      crmIframe.src = `http://127.0.0.1:${port || 8420}/`;
    }
    syncServices();

  } else if (status === 'starting') {
    statusText.textContent = 'Initializing...';
    heroStatusLabel.textContent = 'STARTING...';
    masterBtnText.textContent = 'Starting Engine...';
  } else {
    statusText.textContent = 'Engine Stopped';
    heroStatusLabel.textContent = 'ENGINE READY';
    masterBtn.className = 'engine-master-btn btn-start';
    masterBtnText.textContent = 'Start Engine';
    masterBtn.querySelector('.btn-icon').innerHTML = '<polygon points="5 3 19 12 5 21 5 3"/>';

    metaPid.textContent = 'Idle';
    stopUptimeTimer();
    iframePlaceholder.style.display = 'flex';
  }
}

// Uptime Timer
function startUptimeTimer() {
  if (uptimeInterval) clearInterval(uptimeInterval);
  uptimeInterval = setInterval(() => {
    if (!startTime) return;
    const diff = Math.floor((Date.now() - startTime) / 1000);
    const hrs = String(Math.floor(diff / 3600)).padStart(2, '0');
    const mins = String(Math.floor((diff % 3600) / 60)).padStart(2, '0');
    const secs = String(diff % 60).padStart(2, '0');
    metaUptime.textContent = `${hrs}:${mins}:${secs}`;
  }, 1000);
}

function stopUptimeTimer() {
  if (uptimeInterval) clearInterval(uptimeInterval);
  uptimeInterval = null;
  startTime = null;
  metaUptime.textContent = '00:00:00';
}

// Open Externals
document.getElementById('btn-quick-browser')?.addEventListener('click', () => {
  window.api.openExternal(`http://localhost:8420`);
});

document.getElementById('btn-open-browser-main')?.addEventListener('click', () => {
  window.api.openExternal(`http://localhost:8420`);
});

document.getElementById('btn-popout-browser')?.addEventListener('click', () => {
  window.api.openExternal(`http://localhost:8420`);
});

document.getElementById('btn-reload-iframe')?.addEventListener('click', () => {
  reloadIframe();
});

function reloadIframe() {
  if (crmIframe && currentServerStatus === 'running') {
    crmIframe.src = `http://127.0.0.1:8420/?t=${Date.now()}`;
  }
}

// Port Cleaner
document.getElementById('btn-clean-port')?.addEventListener('click', async () => {
  const btn = document.getElementById('btn-clean-port');
  btn.style.opacity = '0.5';
  await window.api.cleanPort();
  btn.style.opacity = '1';
  appendConsoleLog('info', '🧹 Port 8420 freed successfully.');
});

// Open Folders
document.getElementById('btn-folder-apps')?.addEventListener('click', () => window.api.openFolder('applications'));
document.getElementById('btn-folder-cv')?.addEventListener('click', () => window.api.openFolder('cv'));
document.getElementById('btn-folder-logs')?.addEventListener('click', () => window.api.openFolder('logs'));

// Environment Diagnostics
async function refreshEnvironment() {
  try {
    const env = await window.api.checkEnvironment();
    
    // Python
    const diagPy = document.getElementById('diag-python');
    const diagPyVal = document.getElementById('diag-python-val');
    if (env.python.ok) {
      diagPy.querySelector('.diag-status-dot').className = 'diag-status-dot ok';
      diagPyVal.textContent = env.python.version.replace('Python ', 'v');
    } else {
      diagPy.querySelector('.diag-status-dot').className = 'diag-status-dot err';
      diagPyVal.textContent = 'Not Found';
    }

    // Dependencies
    const diagDeps = document.getElementById('diag-deps');
    const diagDepsVal = document.getElementById('diag-deps-val');
    if (env.dependencies.ok) {
      diagDeps.querySelector('.diag-status-dot').className = 'diag-status-dot ok';
      diagDepsVal.textContent = 'Installed & Verified';
    } else {
      diagDeps.querySelector('.diag-status-dot').className = 'diag-status-dot warn';
      diagDepsVal.textContent = 'Click Auto-Install';
    }

    // LaTeX
    const diagLatex = document.getElementById('diag-latex');
    const diagLatexVal = document.getElementById('diag-latex-val');
    if (env.latex.ok) {
      diagLatex.querySelector('.diag-status-dot').className = 'diag-status-dot ok';
      diagLatexVal.textContent = 'LuaLaTeX Ready';
    } else {
      diagLatex.querySelector('.diag-status-dot').className = 'diag-status-dot warn';
      diagLatexVal.textContent = 'TinyTeX Optional';
    }

    // Bun / Node
    const diagBun = document.getElementById('diag-bun');
    const diagBunVal = document.getElementById('diag-bun-val');
    if (env.bun.ok) {
      diagBun.querySelector('.diag-status-dot').className = 'diag-status-dot ok';
      diagBunVal.textContent = `Bun v${env.bun.version}`;
    } else if (env.node.ok) {
      diagBun.querySelector('.diag-status-dot').className = 'diag-status-dot ok';
      diagBunVal.textContent = `Node ${env.node.version}`;
    } else {
      diagBun.querySelector('.diag-status-dot').className = 'diag-status-dot warn';
      diagBunVal.textContent = 'Missing';
    }

    if (env.serverRunning && currentServerStatus !== 'running') {
      updateStatusUI({ status: 'running', port: env.port, pid: null });
    }
  } catch (err) {
    console.error('Environment check failed:', err);
  }
}

// Auto-Install Button
document.getElementById('btn-run-setup')?.addEventListener('click', async () => {
  const btn = document.getElementById('btn-run-setup');
  btn.disabled = true;
  btn.querySelector('span').textContent = 'Installing...';
  appendConsoleLog('info', '📦 Executing automated setup & dependency installation...');
  
  const res = await window.api.runSetup();
  btn.disabled = false;
  btn.querySelector('span').textContent = 'Auto-Install & Fix All';

  if (res.success) {
    appendConsoleLog('success', '✅ All dependencies installed successfully!');
    await refreshEnvironment();
  } else {
    appendConsoleLog('error', `Setup encountered issue: ${res.message}`);
  }
});

// Services Sync
async function syncServices() {
  if (currentServerStatus !== 'running') return;
  try {
    const services = await window.api.getServices();
    if (!services) return;

    for (const [id, s] of Object.entries(services)) {
      const card = document.querySelector(`.service-card[data-service-id="${id}"]`);
      if (!card) continue;

      const badge = card.querySelector('.service-status-pill');
      const toggleBtn = card.querySelector('.service-toggle-btn');
      const isRunning = s.running;

      if (isRunning) {
        badge.className = 'service-status-pill running';
        badge.textContent = 'Running';
        toggleBtn.className = 'service-toggle-btn btn-active';
        toggleBtn.textContent = 'Stop Service';
      } else {
        badge.className = 'service-status-pill stopped';
        badge.textContent = 'Stopped';
        toggleBtn.className = 'service-toggle-btn';
        toggleBtn.textContent = 'Start Service';
      }
    }
  } catch (e) {
    console.error('Error syncing services:', e);
  }
}

document.getElementById('btn-refresh-services')?.addEventListener('click', () => {
  syncServices();
});

window.toggleService = async function(serviceId) {
  if (currentServerStatus !== 'running') {
    appendConsoleLog('warn', 'Please start the Engine before toggling individual services.');
    return;
  }
  const card = document.querySelector(`.service-card[data-service-id="${serviceId}"]`);
  const badge = card?.querySelector('.service-status-pill');
  const isRunning = badge?.classList.contains('running');
  const action = isRunning ? 'stop' : 'start';

  appendConsoleLog('info', `Sending ${action} command to service: ${serviceId}...`);
  await window.api.toggleService(serviceId, action);
  setTimeout(syncServices, 1000);
};

// Console & Logs
function appendConsoleLog(level, message) {
  const line = document.createElement('div');
  line.className = `console-line line-${level}`;
  
  const time = new Date().toLocaleTimeString();
  const tagClass = `tag-${level}`;
  const tagText = level.toUpperCase();

  line.innerHTML = `
    <span class="c-time">[${time}]</span>
    <span class="c-tag ${tagClass}">${tagText}</span>
    <span class="c-msg">${escapeHtml(message)}</span>
  `;

  consoleStream.appendChild(line);
  logsCount++;
  logCounter.textContent = logsCount;

  if (chkAutoscroll.checked) {
    consoleStream.scrollTop = consoleStream.scrollHeight;
  }
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

document.getElementById('btn-clear-logs')?.addEventListener('click', () => {
  consoleStream.innerHTML = '';
  logsCount = 0;
  logCounter.textContent = '0';
});

document.getElementById('btn-export-logs')?.addEventListener('click', () => {
  const text = Array.from(consoleStream.children).map(c => c.textContent).join('\n');
  const blob = new Blob([text], { type: 'text/plain' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `auto_applier_logs_${Date.now()}.txt`;
  a.click();
});

// Candidate Profile Onboarding Logic
async function loadCandidateProfile() {
  try {
    const data = await window.api.getProfile();
    if (!data) return;

    const { env, profile } = data;
    if (profile) {
      if (profile.name) document.getElementById('cfg-name').value = profile.name;
      if (profile.email) document.getElementById('cfg-email').value = profile.email;
      if (profile.phone) document.getElementById('cfg-phone').value = profile.phone;
      if (profile.target_roles) {
        document.getElementById('cfg-roles').value = Array.isArray(profile.target_roles)
          ? profile.target_roles.join(', ')
          : profile.target_roles;
      }
      if (profile.target_locations) {
        document.getElementById('cfg-locations').value = Array.isArray(profile.target_locations)
          ? profile.target_locations.join(', ')
          : profile.target_locations;
      }
      if (profile.skills) {
        document.getElementById('cfg-skills').value = Array.isArray(profile.skills)
          ? profile.skills.join(', ')
          : profile.skills;
      }
    }

    if (env) {
      if (env.GOOGLE_SHEETS_WEBHOOK_URL) document.getElementById('cfg-webhook').value = env.GOOGLE_SHEETS_WEBHOOK_URL;
      if (env.TELEGRAM_BOT_TOKEN) document.getElementById('cfg-telegram-token').value = env.TELEGRAM_BOT_TOKEN;
      if (env.TELEGRAM_CHAT_ID) document.getElementById('cfg-telegram-chat').value = env.TELEGRAM_CHAT_ID;
      if (env.COMPANY_FILTER) document.getElementById('cfg-filter').value = env.COMPANY_FILTER;
      if (env.CAMOUFOX_AUTO_SUBMIT === 'true') document.getElementById('cfg-browser-mode').value = 'full-auto';
    }
  } catch (e) {
    console.error('Failed to load profile:', e);
  }
}

document.getElementById('btn-save-config')?.addEventListener('click', async () => {
  const btn = document.getElementById('btn-save-config');
  const statusMsg = document.getElementById('save-status-msg');

  const profileData = {
    name: document.getElementById('cfg-name').value.trim(),
    email: document.getElementById('cfg-email').value.trim(),
    phone: document.getElementById('cfg-phone').value.trim(),
    target_roles: document.getElementById('cfg-roles').value.split(',').map(s => s.trim()).filter(Boolean),
    target_locations: document.getElementById('cfg-locations').value.split(',').map(s => s.trim()).filter(Boolean),
    skills: document.getElementById('cfg-skills').value.split(',').map(s => s.trim()).filter(Boolean)
  };

  const envData = {
    GOOGLE_SHEETS_WEBHOOK_URL: document.getElementById('cfg-webhook').value.trim(),
    TELEGRAM_BOT_TOKEN: document.getElementById('cfg-telegram-token').value.trim(),
    TELEGRAM_CHAT_ID: document.getElementById('cfg-telegram-chat').value.trim(),
    COMPANY_FILTER: document.getElementById('cfg-filter').value.trim(),
    CAMOUFOX_AUTO_SUBMIT: document.getElementById('cfg-browser-mode').value === 'full-auto' ? 'true' : 'false'
  };

  btn.disabled = true;
  statusMsg.textContent = 'Saving...';

  const res = await window.api.saveProfile({ profile: profileData, env: envData });
  btn.disabled = false;

  if (res.success) {
    statusMsg.textContent = '✅ Profile & Settings successfully applied!';
    setTimeout(() => { statusMsg.textContent = ''; }, 4000);
  } else {
    statusMsg.textContent = `❌ Error: ${res.message}`;
  }
});

// Packaging & Distributable compilation triggers (Mac, Windows, Linux)
async function triggerBuild(platform, btnId, originalText) {
  const btn = document.getElementById(btnId);
  if (!btn || btn.disabled) return;

  btn.disabled = true;
  const btnSpan = btn.querySelector('span');
  if (btnSpan) btnSpan.textContent = `Building ${platform.toUpperCase()}...`;

  appendConsoleLog('info', `🔨 Triggered ${platform.toUpperCase()} distributable compilation. Live logs streaming below...`);
  
  // Switch to console tab to show progress
  const consoleTab = document.querySelector('.nav-item[data-tab="console"]');
  if (consoleTab) consoleTab.click();

  try {
    const res = await window.api.buildDistributable(platform);
    if (res && res.success) {
      appendConsoleLog('success', `🎉 ${platform.toUpperCase()} installer build completed successfully! Check desktop/dist`);
    } else {
      appendConsoleLog('error', `❌ ${platform.toUpperCase()} build encountered an error.`);
    }
  } catch (err) {
    appendConsoleLog('error', `Build invocation failed: ${err.message}`);
  } finally {
    btn.disabled = false;
    if (btnSpan) btnSpan.textContent = originalText;
  }
}

document.getElementById('btn-build-mac')?.addEventListener('click', () => {
  triggerBuild('mac', 'btn-build-mac', 'Compile macOS .dmg');
});

document.getElementById('btn-build-win')?.addEventListener('click', () => {
  triggerBuild('win', 'btn-build-win', 'Compile Windows .exe');
});

document.getElementById('btn-build-linux')?.addEventListener('click', () => {
  triggerBuild('linux', 'btn-build-linux', 'Compile Linux AppImage');
});


// IPC Event Listeners
window.api.onLog((data) => {
  appendConsoleLog(data.level, data.message);
});

window.api.onServerStatus((data) => {
  updateStatusUI(data);
});

window.startEngineFromAnywhere = function() {
  masterBtn.click();
};

// Initial Setup on DOM Ready
window.addEventListener('DOMContentLoaded', async () => {
  await refreshEnvironment();
  await loadCandidateProfile();
  
  // Fetch existing logs
  const existingLogs = await window.api.getLogs();
  if (existingLogs && existingLogs.length) {
    existingLogs.forEach(l => appendConsoleLog(l.level, l.message));
  }

  // Periodic services check if running
  setInterval(() => {
    if (currentServerStatus === 'running') {
      syncServices();
    }
  }, 10000);
});
