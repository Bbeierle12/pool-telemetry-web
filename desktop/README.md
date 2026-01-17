# Pool Telemetry Desktop

Electron-based desktop application for Pool Telemetry.

## Prerequisites

- Node.js 18+
- Python 3.10+ (for backend bundling)
- npm or yarn

## Setup

1. Install dependencies:
```bash
cd desktop
npm install
```

2. Generate the icon (first time only):
```bash
npm run build:icons
```

## Development

Run the desktop app in development mode:

```bash
# Terminal 1: Start the backend
cd ../backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Start the frontend dev server
cd ../frontend
npm run dev

# Terminal 3: Start Electron
cd desktop
npm run dev:main
```

Or use the combined command (starts frontend + Electron):
```bash
npm run dev
```

## Building for Distribution

### 1. Build the Backend Executable

First, bundle the Python backend:

```bash
# Install PyInstaller
pip install pyinstaller

# Run the build script
python scripts/build-backend.py
```

This creates `backend-dist/pool-telemetry-backend.exe`.

### 2. Build the Desktop App

```bash
cd desktop

# Build for Windows
npm run package:win
```

The installer will be in `desktop/release/`.

## Project Structure

```
desktop/
├── main/
│   ├── main.ts       # Electron main process
│   ├── preload.ts    # IPC bridge for renderer
│   └── backend.ts    # Backend process manager
├── resources/
│   ├── icon.svg      # Source icon
│   ├── icon.ico      # Windows icon (generated)
│   └── icon.png      # PNG icon (generated)
├── scripts/
│   └── generate-icon.js  # Icon generation script
├── package.json
├── tsconfig.main.json
└── electron-builder.yml
```

## Configuration

The desktop app stores settings in:
- Windows: `%APPDATA%/pool-telemetry-desktop/config.json`

Settings include:
- `backendMode`: 'bundled' or 'external'
- `externalBackendUrl`: URL for external backend
- `windowBounds`: Window size and position

## Features

### Backend Modes

1. **Bundled Mode** (default): The app runs a local Python backend automatically.
   - Backend starts on app launch
   - Auto-restarts on crash
   - Graceful shutdown on app close

2. **External Mode**: Connect to a remote backend server.
   - Configure the backend URL in Settings > Desktop
   - Useful for shared setups or remote access

### Icon

The app uses a pool cue icon. To regenerate:
```bash
npm run build:icons
```

This requires `sharp` and `png-to-ico` packages.
