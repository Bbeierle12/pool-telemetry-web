// Bootstrap file to fix Electron module resolution
// The npm 'electron' package shadows Electron's built-in module
// This script temporarily renames the entire electron folder

const path = require('path');
const fs = require('fs');

// Path to the npm electron package that causes issues
const electronPkgPath = path.join(__dirname, '..', 'node_modules', 'electron');
const electronPkgBackup = path.join(__dirname, '..', 'node_modules', '_electron_disabled');

// Temporarily rename the entire electron directory
let renamed = false;

try {
  if (fs.existsSync(electronPkgPath) && !fs.existsSync(electronPkgBackup)) {
    fs.renameSync(electronPkgPath, electronPkgBackup);
    renamed = true;
    console.log('[Bootstrap] Temporarily disabled npm electron package');
  }
} catch (e) {
  console.warn('[Bootstrap] Could not rename electron folder:', e.message);
}

// Restore function
const cleanup = () => {
  if (renamed && fs.existsSync(electronPkgBackup)) {
    try {
      fs.renameSync(electronPkgBackup, electronPkgPath);
      console.log('[Bootstrap] Restored npm electron package');
      renamed = false;
    } catch (e) {
      console.warn('[Bootstrap] Could not restore electron folder:', e.message);
    }
  }
};

// Restore after app is running (5 second delay)
setTimeout(() => {
  cleanup();
}, 5000);

// Also restore on exit signals
process.on('SIGINT', () => { cleanup(); process.exit(0); });
process.on('SIGTERM', () => { cleanup(); process.exit(0); });
process.on('exit', cleanup);

// Now load the actual main file
try {
  require('../dist/main/main.js');
} catch (e) {
  console.error('[Bootstrap] Error loading main:', e);
  cleanup();
  process.exit(1);
}
