import { contextBridge, ipcRenderer } from 'electron';

// Expose protected methods to renderer process
contextBridge.exposeInMainWorld('electronAPI', {
  // Backend URL
  getBackendUrl: (): Promise<string> => ipcRenderer.invoke('get-backend-url'),

  // Settings
  getSettings: (): Promise<{
    backendMode: 'bundled' | 'external';
    externalBackendUrl: string;
  }> => ipcRenderer.invoke('get-settings'),

  setSettings: (settings: {
    backendMode?: 'bundled' | 'external';
    externalBackendUrl?: string;
  }): Promise<boolean> => ipcRenderer.invoke('set-settings', settings),

  // Backend management
  getBackendStatus: (): Promise<{
    mode: 'bundled' | 'external';
    status: 'starting' | 'running' | 'stopped' | 'error' | 'unknown';
  }> => ipcRenderer.invoke('get-backend-status'),

  restartBackend: (): Promise<boolean> => ipcRenderer.invoke('restart-backend'),

  // Environment check
  isElectron: (): Promise<boolean> => ipcRenderer.invoke('is-electron')
});

// Type declarations for renderer process
declare global {
  interface Window {
    electronAPI: {
      getBackendUrl: () => Promise<string>;
      getSettings: () => Promise<{
        backendMode: 'bundled' | 'external';
        externalBackendUrl: string;
      }>;
      setSettings: (settings: {
        backendMode?: 'bundled' | 'external';
        externalBackendUrl?: string;
      }) => Promise<boolean>;
      getBackendStatus: () => Promise<{
        mode: 'bundled' | 'external';
        status: 'starting' | 'running' | 'stopped' | 'error' | 'unknown';
      }>;
      restartBackend: () => Promise<boolean>;
      isElectron: () => Promise<boolean>;
    };
  }
}
