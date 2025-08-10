# qcodes++ Windows Scripts

This directory contains scripts and utilities for setting up qcodes++ on Windows systems.

## Files

### User Scripts
- **`windows_setup_helper.py`** - Interactive setup script for Windows users
- **`qcodespp-offline-plotting.bat`** - Batch script to launch offline plotting GUI
- **`qcodespp-offline-plotting.ps1`** - PowerShell script to launch offline plotting GUI
- **`qcodespp_gui_launcher.py`** - Python GUI launcher with error handling

### Developer Scripts
- **`setup_windows.py`** - Creates Windows shortcuts programmatically
- **`build_executable.py`** - Builds standalone executables using PyInstaller

## Quick Start for Windows Users

1. Install qcodes++:
   ```bash
   pip install qcodespp
   ```

2. Run the setup helper:
   ```bash
   qcodes create_shortcuts
   ```
## Manual Setup

### Command Line Usage
After installing qcodes++, you can launch the offline plotting GUI with:
```bash
qcodespp offline_plotting

## Building Standalone Executables

For distribution without requiring Python installation:

1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```

2. Build executables:
   ```bash
   python scripts/build_executable.py --both
   ```

This creates standalone `.exe` files in the `dist/` directory.

## Troubleshooting

- **Python not found**: Ensure Python is in your PATH or use the full path to python.exe
- **Permission errors**: Run as Administrator or manually create shortcuts
- **Import errors**: Verify qcodes++ is installed with `pip list | findstr qcodespp`

For more detailed troubleshooting, see `WINDOWS_INSTALL.md` in the project root.
