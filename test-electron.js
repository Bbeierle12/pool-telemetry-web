// Test file outside desktop folder
console.log('Process versions:', process.versions);
console.log('Electron version:', process.versions.electron);

// Use try-catch to handle the require
try {
  const electron = require('electron');
  console.log('Electron module type:', typeof electron);
  console.log('Electron module:', electron);

  if (typeof electron === 'string') {
    console.log('ERROR: electron is a string (path), not the module');
    console.log('This means we are not running in Electron main process context');
  } else if (electron.app) {
    console.log('SUCCESS: electron.app is available');
    electron.app.whenReady().then(() => {
      console.log('App ready!');
      electron.app.quit();
    });
  }
} catch (e) {
  console.error('Error requiring electron:', e);
}
