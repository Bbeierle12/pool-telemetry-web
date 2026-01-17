/* eslint-disable @typescript-eslint/no-var-requires, @typescript-eslint/no-explicit-any */
// Debug: Log what we get from require('electron')
const electronModule = require('electron');
console.log('Electron module type:', typeof electronModule);
console.log('Electron module:', electronModule);
console.log('Electron module keys:', Object.keys(electronModule || {}));
console.log('process.versions.electron:', (process as any).versions?.electron);
console.log('process.type:', (process as any).type);

// If we got a string (path from npm package), the built-in module isn't working
if (typeof electronModule === 'string') {
  console.error('ERROR: Got npm electron path instead of module:', electronModule);
  console.error('This indicates Electron built-in module resolution is not working');
  process.exit(1);
}

if (!electronModule.app) {
  console.error('ERROR: electron.app is undefined');
  console.error('Module contents:', JSON.stringify(electronModule, null, 2));
  process.exit(1);
}

const { app, BrowserWindow, ipcMain, shell } = electronModule;
import * as path from 'path';
import Store from 'electron-store';
import { BackendManager } from './backend';

// Initialize electron store for settings
const store = new Store<{
  backendMode: 'bundled' | 'external';
  externalBackendUrl: string;
  windowBounds: { width: number; height: number; x?: number; y?: number };
}>({
  defaults: {
    backendMode: 'bundled',
    externalBackendUrl: 'http://localhost:8000',
    windowBounds: { width: 1400, height: 900 }
  }
});

let mainWindow: BrowserWindow | null = null;
let backendManager: BackendManager | null = null;

const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;

function getBackendUrl(): string {
  const mode = store.get('backendMode');
  if (mode === 'external') {
    return store.get('externalBackendUrl');
  }
  return 'http://localhost:8000';
}

async function createWindow(): Promise<void> {
  const bounds = store.get('windowBounds');

  mainWindow = new BrowserWindow({
    width: bounds.width,
    height: bounds.height,
    x: bounds.x,
    y: bounds.y,
    minWidth: 1024,
    minHeight: 768,
    icon: path.join(__dirname, '..', 'resources', 'icon.ico'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    },
    titleBarStyle: 'default',
    show: false
  });

  // Save window bounds on resize/move
  mainWindow.on('resize', () => {
    if (mainWindow) {
      const bounds = mainWindow.getBounds();
      store.set('windowBounds', bounds);
    }
  });

  mainWindow.on('move', () => {
    if (mainWindow) {
      const bounds = mainWindow.getBounds();
      store.set('windowBounds', bounds);
    }
  });

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
  });

  // Handle external links
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  // Load the app
  if (isDev) {
    // In development, load from Vite dev server
    await mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    // In production, load the built files
    await mainWindow.loadFile(path.join(__dirname, '..', '..', 'frontend', 'dist', 'index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// IPC Handlers
function setupIpcHandlers(): void {
  // Get backend URL
  ipcMain.handle('get-backend-url', () => {
    return getBackendUrl();
  });

  // Get settings
  ipcMain.handle('get-settings', () => {
    return {
      backendMode: store.get('backendMode'),
      externalBackendUrl: store.get('externalBackendUrl')
    };
  });

  // Update settings
  ipcMain.handle('set-settings', (_event, settings: { backendMode?: 'bundled' | 'external'; externalBackendUrl?: string }) => {
    if (settings.backendMode !== undefined) {
      store.set('backendMode', settings.backendMode);
    }
    if (settings.externalBackendUrl !== undefined) {
      store.set('externalBackendUrl', settings.externalBackendUrl);
    }
    return true;
  });

  // Get backend status
  ipcMain.handle('get-backend-status', () => {
    if (store.get('backendMode') === 'external') {
      return { mode: 'external', status: 'unknown' };
    }
    return {
      mode: 'bundled',
      status: backendManager?.getStatus() || 'stopped'
    };
  });

  // Restart backend
  ipcMain.handle('restart-backend', async () => {
    if (store.get('backendMode') === 'bundled' && backendManager) {
      await backendManager.restart();
      return true;
    }
    return false;
  });

  // Check if running in Electron
  ipcMain.handle('is-electron', () => true);
}

async function startBackend(): Promise<void> {
  const mode = store.get('backendMode');

  if (mode === 'bundled') {
    backendManager = new BackendManager(isDev);
    await backendManager.start();
  }
}

// App lifecycle
app.whenReady().then(async () => {
  setupIpcHandlers();

  // Start backend first (if bundled mode)
  await startBackend();

  // Then create window
  await createWindow();

  app.on('activate', async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      await createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', async () => {
  // Stop backend before quitting
  if (backendManager) {
    await backendManager.stop();
  }
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  console.error('Uncaught exception:', error);
});

process.on('unhandledRejection', (reason) => {
  console.error('Unhandled rejection:', reason);
});
