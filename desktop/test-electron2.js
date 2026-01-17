// Check if we're in Electron
console.log('Electron version:', process.versions.electron);
console.log('Type:', process.type);

// In Electron main process, try different import methods
const path = require('path');
const Module = require('module');

// Log the module paths
console.log('Module paths:', module.paths);

// Check if electron is in the builtin modules
console.log('Builtin modules:', Module.builtinModules.filter(m => m.includes('electron')));

// Try to access electron internals
if (process.electronBinding) {
  console.log('electronBinding available');
}

// The real fix - manually tell Node where electron module is
// This shouldn't be necessary in a properly configured Electron app
try {
  // Try importing from electron/main
  const { app } = require('electron');
  console.log('app from electron:', app);

  if (app) {
    app.whenReady().then(() => {
      console.log('App ready - quitting');
      app.quit();
    });
  }
} catch (e) {
  console.error('Import error:', e.message);

  // Exit after a delay
  setTimeout(() => process.exit(1), 1000);
}
