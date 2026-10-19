const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  platform: process.platform,
  
  // System & Environment
  checkEnvironment: () => ipcRenderer.invoke('check-environment'),
  startServer: () => ipcRenderer.invoke('start-server'),
  stopServer: () => ipcRenderer.invoke('stop-server'),
  restartServer: () => ipcRenderer.invoke('restart-server'),
  cleanPort: () => ipcRenderer.invoke('clean-port'),
  runSetup: () => ipcRenderer.invoke('run-setup'),
  buildDistributable: (platform) => ipcRenderer.invoke('build-distributable', platform),

  // Services Management
  getServices: () => ipcRenderer.invoke('get-services'),
  toggleService: (serviceId, action) => ipcRenderer.invoke('toggle-service', serviceId, action),

  // Configuration & Profile
  getProfile: () => ipcRenderer.invoke('get-profile'),
  saveProfile: (profileData) => ipcRenderer.invoke('save-profile', profileData),

  // Navigation & File System
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
  openFolder: (folderType) => ipcRenderer.invoke('open-folder', folderType),

  // Log streaming & Events
  getLogs: () => ipcRenderer.invoke('get-logs'),
  onLog: (callback) => {
    const handler = (event, data) => callback(data);
    ipcRenderer.on('log-message', handler);
    return () => ipcRenderer.removeListener('log-message', handler);
  },
  onServerStatus: (callback) => {
    const handler = (event, data) => callback(data);
    ipcRenderer.on('server-status-changed', handler);
    return () => ipcRenderer.removeListener('server-status-changed', handler);
  }
});
