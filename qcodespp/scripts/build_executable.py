#!/usr/bin/env python3
"""
Build script for creating Windows executable of QCodes++ offline plotting GUI.
Requires PyInstaller: pip install pyinstaller
"""

import os
import sys
import subprocess
from pathlib import Path


def build_executable():
    """Build Windows executable using PyInstaller."""
    
    # Check if PyInstaller is available
    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller not found. Install with: pip install pyinstaller")
        return False
    
    # Path to the GUI launcher script
    script_path = Path(__file__).parent / "qcodespp_gui_launcher.py"
    
    if not script_path.exists():
        print(f"Error: {script_path} not found")
        return False
    
    # PyInstaller command
    cmd = [
        "pyinstaller",
        "--onefile",                    # Create single executable
        "--windowed",                   # No console window (GUI only)
        "--name=QCodesPP-OfflinePlotting",  # Executable name
        "--icon=NONE",                  # Could add icon here
        "--add-data=qcodespp;qcodespp", # Include qcodespp package
        str(script_path)
    ]
    
    print("Building Windows executable...")
    print("Command:", " ".join(cmd))
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Build successful!")
        print("Executable location: dist/QCodesPP-OfflinePlotting.exe")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False


def build_console_executable():
    """Build Windows console executable using PyInstaller."""
    
    # Check if PyInstaller is available
    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller not found. Install with: pip install pyinstaller")
        return False
    
    # Path to the GUI launcher script
    script_path = Path(__file__).parent / "qcodespp_gui_launcher.py"
    
    if not script_path.exists():
        print(f"Error: {script_path} not found")
        return False
    
    # PyInstaller command for console version
    cmd = [
        "pyinstaller",
        "--onefile",                    # Create single executable
        "--console",                    # Keep console window for debugging
        "--name=QCodesPP-OfflinePlotting-Console",  # Executable name
        "--icon=NONE",                  # Could add icon here
        "--add-data=qcodespp;qcodespp", # Include qcodespp package
        str(script_path)
    ]
    
    print("Building Windows console executable...")
    print("Command:", " ".join(cmd))
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Build successful!")
        print("Executable location: dist/QCodesPP-OfflinePlotting-Console.exe")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False


def main():
    """Main build function."""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--console":
            build_console_executable()
        elif sys.argv[1] == "--gui":
            build_executable()
        elif sys.argv[1] == "--both":
            build_console_executable()
            build_executable()
        else:
            print("Usage: python build_executable.py [--console|--gui|--both]")
    else:
        print("QCodes++ Executable Builder")
        print("Usage:")
        print("  python build_executable.py --console    # Build console version")
        print("  python build_executable.py --gui        # Build GUI version")
        print("  python build_executable.py --both       # Build both versions")
        print("")
        print("Requirements:")
        print("  pip install pyinstaller")


if __name__ == "__main__":
    main()
