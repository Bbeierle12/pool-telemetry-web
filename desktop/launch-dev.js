// Development launcher that properly handles electron module resolution
// This script renames the electron package.json, launches electron,
// then restores it when electron exits

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const electronPkgPath = path.join(__dirname, 'node_modules', 'electron');
const electronPkgJson = path.join(electronPkgPath, 'package.json');
const electronPkgJsonBackup = path.join(electronPkgPath, 'package.json.disabled');
const electronExePath = path.join(electronPkgPath, 'dist', 'electron.exe');

// Rename package.json to prevent Node from resolving the electron package
let renamed = false;
if (fs.existsSync(electronPkgJson) && !fs.existsSync(electronPkgJsonBackup)) {
  fs.renameSync(electronPkgJson, electronPkgJsonBackup);
  renamed = true;
  console.log('Disabled npm electron package.json');
}

// Restore function
function restore() {
  if (renamed && fs.existsSync(electronPkgJsonBackup)) {
    fs.renameSync(electronPkgJsonBackup, electronPkgJson);
    console.log('Restored npm electron package.json');
    renamed = false;
  }
}

// Launch Electron
console.log('Launching Electron...');
const electron = spawn(electronExePath, ['.'], {
  cwd: __dirname,
  stdio: 'inherit',
  env: { ...process.env, NODE_ENV: 'development' }
});

electron.on('close', (code) => {
  console.log(`Electron exited with code ${code}`);
  restore();
  process.exit(code || 0);
});

electron.on('error', (err) => {
  console.error('Failed to start Electron:', err);
  restore();
  process.exit(1);
});

// Handle signals
process.on('SIGINT', () => {
  electron.kill('SIGINT');
});

process.on('SIGTERM', () => {
  electron.kill('SIGTERM');
});

// Also restore on uncaught errors
process.on('uncaughtException', (err) => {
  console.error('Uncaught exception:', err);
  restore();
  process.exit(1);
});
