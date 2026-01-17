import { app, BrowserWindow, ipcMain, shell } from 'electron';
import * as path from 'path';
import Store from 'electron-store';
import { BackendManager } from './backend';

// Handle Squirrel events for Windows installer
if (require('electron-squirrel-startup')) {
  app.quit();
}

// Declare webpack-generated constants
declare const MAIN_WINDOW_WEBPACK_ENTRY: string;
declare const MAIN_WINDOW_PRELOAD_WEBPACK_ENTRY: string;

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
    icon: path.join(__dirname, '..', '..', 'resources', 'icon.ico'),
    webPreferences: {
      preload: MAIN_WINDOW_PRELOAD_WEBPACK_ENTRY,
      contextIsolation: true,
      nodeIntegration: false,
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

  // Load the app - in dev mode load from Vite dev server
  if (isDev) {
    try {
      await mainWindow.loadURL('http://localhost:5173');
      mainWindow.webContents.openDevTools();
    } catch {
      // Fall back to webpack entry if Vite isn't running
      await mainWindow.loadURL(MAIN_WINDOW_WEBPACK_ENTRY);
    }
  } else {
    await mainWindow.loadURL(MAIN_WINDOW_WEBPACK_ENTRY);
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// IPC Handlers
function setupIpcHandlers(): void {
  ipcMain.handle('get-backend-url', () => {
    return getBackendUrl();
  });

  ipcMain.handle('get-settings', () => {
    return {
      backendMode: store.get('backendMode'),
      externalBackendUrl: store.get('externalBackendUrl')
    };
  });

  ipcMain.handle('set-settings', (_event, settings: { backendMode?: 'bundled' | 'external'; externalBackendUrl?: string }) => {
    if (settings.backendMode !== undefined) {
      store.set('backendMode', settings.backendMode);
    }
    if (settings.externalBackendUrl !== undefined) {
      store.set('externalBackendUrl', settings.externalBackendUrl);
    }
    return true;
  });

  ipcMain.handle('get-backend-status', () => {
    if (store.get('backendMode') === 'external') {
      return { mode: 'external', status: 'unknown' };
    }
    return {
      mode: 'bundled',
      status: backendManager?.getStatus() || 'stopped'
    };
  });

  ipcMain.handle('restart-backend', async () => {
    if (store.get('backendMode') === 'bundled' && backendManager) {
      await backendManager.restart();
      return true;
    }
    return false;
  });

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
  await startBackend();
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
  if (backendManager) {
    await backendManager.stop();
  }
});

process.on('uncaughtException', (error) => {
  console.error('Uncaught exception:', error);
});

process.on('unhandledRejection', (reason) => {
  console.error('Unhandled rejection:', reason);
});
