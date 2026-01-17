const electron = require('electron');
console.log('Electron module:', electron);
console.log('Type of electron:', typeof electron);
console.log('Keys:', Object.keys(electron));
console.log('app:', electron.app);
console.log('BrowserWindow:', electron.BrowserWindow);

if (electron.app) {
  electron.app.whenReady().then(() => {
    console.log('App is ready!');
    electron.app.quit();
  });
} else {
  console.log('app is not defined - might be running in wrong context');
  process.exit(1);
}
