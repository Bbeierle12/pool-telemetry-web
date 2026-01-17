// Type declarations for Electron IPC API
// These match the API exposed in desktop/main/preload.ts

export interface ElectronAPI {
  getBackendUrl: () => Promise<string>
  getSettings: () => Promise<{
    backendMode: 'bundled' | 'external'
    externalBackendUrl: string
  }>
  setSettings: (settings: {
    backendMode?: 'bundled' | 'external'
    externalBackendUrl?: string
  }) => Promise<boolean>
  getBackendStatus: () => Promise<{
    mode: 'bundled' | 'external'
    status: 'starting' | 'running' | 'stopped' | 'error' | 'unknown'
  }>
  restartBackend: () => Promise<boolean>
  isElectron: () => Promise<boolean>
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI
  }
}

export {}
