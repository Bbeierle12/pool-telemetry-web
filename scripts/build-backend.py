#!/usr/bin/env python3
"""
Build script for bundling the Pool Telemetry backend with PyInstaller.

This creates a standalone executable that can be distributed with the Electron app.

Usage:
    python scripts/build-backend.py

The output will be placed in backend-dist/ directory.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
OUTPUT_DIR = ROOT_DIR / "backend-dist"
SPEC_FILE = BACKEND_DIR / "pool-telemetry-backend.spec"


def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import PyInstaller
        print(f"PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("ERROR: PyInstaller is not installed.")
        print("Install it with: pip install pyinstaller")
        sys.exit(1)


def create_spec_file():
    """Create PyInstaller spec file for the backend."""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

# Get the backend directory
backend_dir = Path(SPECPATH)

# Collect all data files
datas = [
    # Include any static files, templates, or configuration
    # Add more as needed
]

# Hidden imports that PyInstaller might miss
hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
    'sqlalchemy.sql.default_comparator',
    'sqlalchemy.dialects.sqlite',
    'aiosqlite',
    'jose',
    'passlib.handlers.bcrypt',
    'cv2',
    'numpy',
    'PIL',
    'google.generativeai',
    'anthropic',
    'websockets',
    'pydantic',
    'pydantic_settings',
    'email_validator',
    'httptools',
    'watchfiles',
    'httpx',
    'anyio',
    'sniffio',
]

a = Analysis(
    ['app/main.py'],
    pathex=[str(backend_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='pool-telemetry-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Set to False for GUI-only mode
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path if desired
)
'''

    with open(SPEC_FILE, 'w') as f:
        f.write(spec_content)
    print(f"Created spec file: {SPEC_FILE}")


def create_entry_point():
    """Create a proper entry point for PyInstaller."""
    entry_point = BACKEND_DIR / "app" / "main.py"

    # Read current main.py content
    if entry_point.exists():
        with open(entry_point, 'r') as f:
            content = f.read()

        # Check if it already has the uvicorn.run call for PyInstaller
        if 'if __name__ == "__main__"' not in content:
            # Add entry point for PyInstaller
            addition = '''

# Entry point for PyInstaller executable
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
'''
            with open(entry_point, 'a') as f:
                f.write(addition)
            print(f"Added entry point to {entry_point}")
        else:
            print(f"Entry point already exists in {entry_point}")
    else:
        print(f"WARNING: {entry_point} not found!")


def build_backend():
    """Run PyInstaller to build the backend executable."""
    print("\n" + "="*60)
    print("Building Pool Telemetry Backend")
    print("="*60 + "\n")

    # Clean previous build
    if OUTPUT_DIR.exists():
        print(f"Cleaning previous build: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)

    build_dir = BACKEND_DIR / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)

    # Run PyInstaller
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--distpath", str(OUTPUT_DIR),
        "--workpath", str(BACKEND_DIR / "build"),
        str(SPEC_FILE)
    ]

    print(f"Running: {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd, cwd=str(BACKEND_DIR))

    if result.returncode != 0:
        print("\nERROR: PyInstaller build failed!")
        sys.exit(1)

    print("\n" + "="*60)
    print("Build completed successfully!")
    print(f"Output directory: {OUTPUT_DIR}")
    print("="*60 + "\n")


def cleanup():
    """Clean up temporary build files."""
    # Remove spec file if we created it
    if SPEC_FILE.exists():
        # Keep the spec file for future builds
        pass

    # Remove build directory
    build_dir = BACKEND_DIR / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
        print("Cleaned up build directory")


def main():
    """Main build process."""
    print("Pool Telemetry Backend Build Script")
    print("-" * 40)

    # Check dependencies
    check_dependencies()

    # Ensure we're in the right directory
    os.chdir(ROOT_DIR)

    # Create spec file if it doesn't exist
    if not SPEC_FILE.exists():
        create_spec_file()

    # Ensure entry point exists
    create_entry_point()

    # Build the backend
    build_backend()

    # Cleanup
    cleanup()

    print("Done! The backend executable is ready for packaging with Electron.")


if __name__ == "__main__":
    main()
