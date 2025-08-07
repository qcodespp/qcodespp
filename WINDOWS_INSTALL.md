# QCodes++ Windows Installation Guide

This guide explains how to install QCodes++ on Windows and set up the offline plotting GUI as a desktop application.

## Installation Methods

### Method 1: Standard pip installation (Recommended)

1. Install QCodes++ using pip:
   ```bash
   pip install qcodespp
   ```

2. After installation, you can launch the offline plotting GUI in several ways:

   **Command Line:**
   ```bash
   qcodespp offline_plotting
   ```

   **From Python:**
   ```python
   import qcodespp as qc
   qc.offline_plotting()
   ```

### Method 2: Installation with Windows shortcuts

1. Install QCodes++ using pip:
   ```bash
   pip install qcodespp
   ```

2. Install Windows shell libraries (optional, for shortcuts):
   ```bash
   pip install pywin32 winshell
   ```

3. Create desktop and start menu shortcuts:
   ```bash
   python -c "from qcodespp.scripts.setup_windows import create_windows_shortcuts; create_windows_shortcuts()"
   ```

## Available Scripts

After installation, the following scripts are available in the `scripts/` folder:

### Batch Script (`qcodespp-offline-plotting.bat`)
- Double-click to run the offline plotting GUI
- Can be used to create custom shortcuts
- Automatically tries multiple Python execution methods

### PowerShell Script (`qcodespp-offline-plotting.ps1`)
- More modern Windows approach
- Better error handling and user feedback
- Run with: `powershell -ExecutionPolicy Bypass -File qcodespp-offline-plotting.ps1`

### Python Setup Script (`setup_windows.py`)
- Creates desktop and start menu shortcuts
- Requires `pywin32` and `winshell` packages
- Run with: `python setup_windows.py --create-shortcuts`

## Creating Custom Shortcuts

### Desktop Shortcut (Manual)
1. Right-click on desktop → New → Shortcut
2. Enter target: `python -m qcodespp.cli offline_plotting`
3. Name: "QCodes++ Offline Plotting"
4. Click Finish

### Start Menu Entry (Manual)
1. Open Run dialog (Win+R)
2. Type: `shell:start menu\Programs`
3. Create new folder: "QCodes++"
4. Create shortcut inside folder with target: `python -m qcodespp.cli offline_plotting`

## Command Line Options

The offline plotting GUI supports several command line options:

```bash
qcodespp offline_plotting --help
```

Available options:
- `--folder PATH`: Specify folder containing data files
- `--no-link-default`: Don't link to the qcodespp default folder
- `--no-thread`: Don't run in a separate thread (may be needed on some systems)

## Troubleshooting

### Python not found
If you get "Python not found" errors:
1. Ensure Python is installed and in your PATH
2. Try using the Python launcher: `py -m qcodespp.cli offline_plotting`
3. Use the full path to python.exe

### Permission errors
If you get permission errors when creating shortcuts:
1. Run the command prompt as Administrator
2. Or manually create shortcuts as described above

### Import errors
If you get import errors:
1. Ensure QCodes++ is properly installed: `pip list | findstr qcodespp`
2. Try reinstalling: `pip uninstall qcodespp && pip install qcodespp`
3. Check your Python environment is correct

## Environment-Specific Installation

### Anaconda/Miniconda
```bash
conda activate your_environment
pip install qcodespp
```

### Virtual Environment
```bash
# Create and activate virtual environment
python -m venv qcodespp_env
qcodespp_env\Scripts\activate

# Install QCodes++
pip install qcodespp

# Create shortcuts (they will use the virtual environment)
python -c "from qcodespp.scripts.setup_windows import create_windows_shortcuts; create_windows_shortcuts()"
```

The shortcuts will automatically use the Python environment where QCodes++ was installed.
