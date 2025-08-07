#!/usr/bin/env python3
"""
Windows installation script for QCodes++ shortcuts.
This script creates desktop and start menu shortcuts for the QCodes++ offline plotting tool.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path


def is_windows():
    """Check if running on Windows."""
    return sys.platform == "win32"


def find_python_executable():
    """Find the Python executable being used."""
    return sys.executable


def create_shortcut_script():
    """Create a Python script that launches offline plotting."""
    script_content = '''#!/usr/bin/env python3
"""
QCodes++ Offline Plotting Launcher
"""
import sys
import subprocess

def main():
    """Launch QCodes++ offline plotting."""
    try:
        # Try to import and run directly
        from qcodespp.plotting.offline.main import offline_plotting
        offline_plotting()
    except ImportError:
        # Fall back to command line
        try:
            subprocess.run([sys.executable, "-m", "qcodespp.cli", "offline_plotting"])
        except Exception as e:
            print(f"Failed to launch QCodes++ offline plotting: {e}")
            input("Press Enter to exit...")

if __name__ == "__main__":
    main()
'''
    
    # Get the Scripts directory where pip installs console scripts
    scripts_dir = Path(sys.executable).parent / "Scripts"
    if not scripts_dir.exists():
        scripts_dir = Path(sys.executable).parent
    
    launcher_path = scripts_dir / "qcodespp-offline-plotting-launcher.py"
    
    with open(launcher_path, 'w') as f:
        f.write(script_content)
    
    return launcher_path


def create_windows_shortcuts():
    """Create Windows shortcuts for QCodes++ offline plotting."""
    if not is_windows():
        print("This function is only for Windows systems.")
        return
    
    try:
        import winshell
        from win32com.client import Dispatch
    except ImportError:
        print("Windows shell libraries not available. Install with:")
        print("pip install pywin32 winshell")
        return
    
    # Create the launcher script
    launcher_path = create_shortcut_script()
    python_exe = find_python_executable()
    
    # Desktop shortcut
    desktop = winshell.desktop()
    desktop_shortcut = os.path.join(desktop, "QCodes++ Offline Plotting.lnk")
    
    shell = Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(desktop_shortcut)
    shortcut.Targetpath = python_exe
    shortcut.Arguments = f'"{launcher_path}"'
    shortcut.WorkingDirectory = os.path.dirname(python_exe)
    shortcut.IconLocation = python_exe
    shortcut.Description = "QCodes++ Offline Plotting Tool"
    shortcut.save()
    
    print(f"Created desktop shortcut: {desktop_shortcut}")
    
    # Start menu shortcut
    try:
        start_menu = winshell.start_menu()
        qcodespp_folder = os.path.join(start_menu, "QCodes++")
        os.makedirs(qcodespp_folder, exist_ok=True)
        
        start_menu_shortcut = os.path.join(qcodespp_folder, "QCodes++ Offline Plotting.lnk")
        
        shortcut = shell.CreateShortCut(start_menu_shortcut)
        shortcut.Targetpath = python_exe
        shortcut.Arguments = f'"{launcher_path}"'
        shortcut.WorkingDirectory = os.path.dirname(python_exe)
        shortcut.IconLocation = python_exe
        shortcut.Description = "QCodes++ Offline Plotting Tool"
        shortcut.save()
        
        print(f"Created start menu shortcut: {start_menu_shortcut}")
    except Exception as e:
        print(f"Failed to create start menu shortcut: {e}")


def main():
    """Main function to set up Windows shortcuts."""
    if len(sys.argv) > 1 and sys.argv[1] == "--create-shortcuts":
        if is_windows():
            create_windows_shortcuts()
        else:
            print("Shortcuts can only be created on Windows systems.")
    else:
        print("QCodes++ Windows Setup")
        print("Usage:")
        print("  python setup_windows.py --create-shortcuts")
        print("")
        print("This will create desktop and start menu shortcuts for QCodes++ offline plotting.")


if __name__ == "__main__":
    main()
