#!/usr/bin/env python3
"""
Creates desktop and start menu shortcuts for qcodes++ offline plotting tool and Jupyter Lab.
"""

import os
import sys
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
qcodes++ Offline Plotting Launcher
"""
import sys
import subprocess

def main():
    """Launch qcodes++ offline plotting."""
    try:
        # Try to import and run directly
        from qcodespp.plotting.offline.main import offline_plotting
        offline_plotting()
    except ImportError:
        # Fall back to command line
        try:
            subprocess.run([sys.executable, "-m", "qcodespp.cli", "offline_plotting"])
        except Exception as e:
            print(f"Failed to launch qcodes++ offline plotting: {e}")
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


def create_windows_shortcuts(path=None):
    """Create Windows shortcuts for qcodes++ offline plotting."""
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
    
    if not path:
        path = os.path.expanduser("~")
    if not os.path.exists(path):
        print(f"Specified path does not exist: {path}")
        return
    
    # Create the launcher script
    launcher_path = create_shortcut_script()
    python_exe = find_python_executable()
    
    # Desktop shortcut
    desktop = winshell.desktop()

    success=True

    try:
        desktop_shortcut = os.path.join(desktop, "qcodes++ Offline Plotting.lnk")
        
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(desktop_shortcut)
        shortcut.Targetpath = python_exe
        shortcut.Arguments = f'"{launcher_path}"'
        shortcut.WorkingDirectory = path
        # Set icon to iconGadget.ico in qcodespp/plotting/offline
        icon_path = os.path.join(os.path.dirname(__file__), "..", "plotting", "offline", "iconGadget.ico")
        icon_path = os.path.abspath(icon_path)
        if os.path.exists(icon_path):
            shortcut.IconLocation = icon_path
        else:
            shortcut.IconLocation = python_exe
        shortcut.Description = "qcodes++ Offline Plotting Tool"
        shortcut.save()

        print(f"✓ Created offline plotting desktop shortcut")
    except Exception as e:
        success=False
        print(f"✗ Failed to create offline plotting desktop shortcut: {e}")

    # Start menu shortcut
    try:
        start_menu = winshell.start_menu()
        qcodespp_folder = os.path.join(start_menu, "qcodes++")
        os.makedirs(qcodespp_folder, exist_ok=True)
        
        start_menu_shortcut = os.path.join(qcodespp_folder, "qcodes++ Offline Plotting.lnk")
        
        shortcut = shell.CreateShortCut(start_menu_shortcut)
        shortcut.Targetpath = python_exe
        shortcut.Arguments = f'"{launcher_path}"'
        shortcut.WorkingDirectory = path
        # Set icon to iconGadget.ico in qcodespp/plotting/offline
        icon_path = os.path.join(os.path.dirname(__file__), "..", "plotting", "offline", "iconGadget.ico")
        icon_path = os.path.abspath(icon_path)
        if os.path.exists(icon_path):
            shortcut.IconLocation = icon_path
        else:
            shortcut.IconLocation = python_exe
        shortcut.Description = "qcodes++ Offline Plotting Tool"
        shortcut.save()
        
        print(f"✓ Created offline plotting start menu shortcut")
    except Exception as e:
        success=False
        print(f"✗ Failed to create start menu shortcut: {e}")

    # Jupyter Lab desktop shortcut
    try:
        jupyter_lab_shortcut = os.path.join(desktop, "Jupyter Lab (qcodes++) .lnk")
        shortcut = shell.CreateShortCut(jupyter_lab_shortcut)
        shortcut.Targetpath = python_exe
        shortcut.Arguments = "-m jupyter lab"
        shortcut.WorkingDirectory = path
        shortcut.Description = "Jupyter Lab (qcodes++ environment)"
        shortcut.IconLocation = python_exe
        icon_path = os.path.join(os.path.dirname(__file__), "jupyter.ico")
        icon_path = os.path.abspath(icon_path)
        if os.path.exists(icon_path):
            shortcut.IconLocation = icon_path
        else:
            shortcut.IconLocation = python_exe
        shortcut.save()
        print(f"✓ Created Jupyter lab desktop shortcut")
    except Exception as e:
        success=False
        print(f"✗ Failed to create Jupyter lab desktop shortcut: {e}")

    # Jupyter Lab start menu shortcut
    try:
        start_menu = winshell.start_menu()
        qcodespp_folder = os.path.join(start_menu, "qcodes++")
        os.makedirs(qcodespp_folder, exist_ok=True)

        jupyter_lab_start_menu_shortcut = os.path.join(qcodespp_folder, "Jupyter Lab (qcodes++).lnk")
        shortcut = shell.CreateShortCut(jupyter_lab_start_menu_shortcut)
        shortcut.Targetpath = python_exe
        shortcut.Arguments = "-m jupyter lab"
        shortcut.WorkingDirectory = path
        shortcut.Description = "Jupyter Lab (qcodes++ environment)"
        icon_path = os.path.join(os.path.dirname(__file__), "jupyter.ico")
        icon_path = os.path.abspath(icon_path)
        if os.path.exists(icon_path):
            shortcut.IconLocation = icon_path
        else:
            shortcut.IconLocation = python_exe
        shortcut.save()
        print(f"✓ Created Jupyter Lab start menu shortcut")
    except Exception as e:
        
        print(f"✗ Failed to create Jupyter Lab start menu shortcut: {e}")

    return success

def main():
    """Main function to set up Windows shortcuts."""
    if len(sys.argv) > 1 and sys.argv[1] == "--create-shortcuts":
        if is_windows():
            create_windows_shortcuts()
        else:
            print("Shortcuts can only be created on Windows systems.")
    else:
        print("qcodes++ Windows Setup")
        print("Usage:")
        print("  python setup_windows.py --create-shortcuts")
        print("")
        print("This will create desktop and start menu shortcuts for qcodes++ offline plotting.")


if __name__ == "__main__":
    main()
