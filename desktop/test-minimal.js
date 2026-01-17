// Minimal test to verify Electron context
console.log('=== Electron Context Test ===');
console.log('process.type:', process.type);
console.log('process.versions.electron:', process.versions.electron);
console.log('process.versions.node:', process.versions.node);

const electron = require('electron');
console.log('require("electron") type:', typeof electron);
console.log('require("electron"):', electron);

if (typeof electron === 'object' && electron.app) {
  console.log('SUCCESS: electron.app is available');
  const { app, BrowserWindow } = electron;

  app.whenReady().then(() => {
    const win = new BrowserWindow({ width: 400, height: 300 });
    win.loadURL('data:text/html,<h1>Electron Works!</h1>');
    console.log('Window created successfully');
  });
} else {
  console.log('FAILURE: electron.app is not available');
  console.log('This may indicate the npm electron package is shadowing the built-in module');
  process.exit(1);
}
