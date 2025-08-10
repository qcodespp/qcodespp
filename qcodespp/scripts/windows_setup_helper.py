#!/usr/bin/env python3
"""
QCodes++ Windows Installation and Setup Helper
This script helps Windows users set up QCodes++ with desktop integration.
"""

import sys
import subprocess
import shutil
from pathlib import Path


def check_windows():
    """Check if running on Windows."""
    if sys.platform != "win32":
        print("This script is designed for Windows systems only.")
        sys.exit(1)


def install_dependencies():
    """Install required dependencies for Windows integration."""
    print("\nInstalling Windows integration dependencies...")
    
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "pywin32", "winshell"
        ], check=True)
        print("✓ Windows dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install dependencies: {e}")
        return False


def create_shortcuts(path=None):
    """Create desktop and start menu shortcuts."""
    try:
        from qcodespp.scripts.setup_windows import create_windows_shortcuts
        success=create_windows_shortcuts(path=path)
        return success
    except ImportError:
        print("✗ Windows shell libraries not available")
        print("  Try installing them with: pip install pywin32 winshell")
        return False
    except Exception as e:
        print(f"✗ Failed to create shortcuts: {e}")
        return False


def test_installation():
    """Test that qcodespp can be imported and the CLI works."""
    print("Testing QCodes++ installation...")
    
    # Test import
    try:
        import qcodespp
        print(f"✓ QCodes++ version {qcodespp.__version__} imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import QCodes++: {e}")
        return False
    
    # Test CLI
    try:
        result = subprocess.run([
            sys.executable, "-m", "qcodespp.cli", "--help"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✓ QCodes++ CLI is working")
            return True
        else:
            print(f"✗ QCodes++ CLI failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("✗ QCodes++ CLI test timed out")
        return False
    except Exception as e:
        print(f"✗ QCodes++ CLI test failed: {e}")
        return False


def copy_scripts_to_desktop():
    """Copy useful scripts to the desktop."""
    try:
        import winshell
        desktop = Path(winshell.desktop())
        
        # Get the scripts directory
        scripts_dir = Path(__file__).parent
        
        # Copy batch script
        batch_script = scripts_dir / "qcodespp-offline-plotting.bat"
        if batch_script.exists():
            shutil.copy(batch_script, desktop / "QCodes++ Offline Plotting.bat")
            print("✓ Batch script copied to desktop")
        
        # Copy PowerShell script
        ps_script = scripts_dir / "qcodespp-offline-plotting.ps1"
        if ps_script.exists():
            shutil.copy(ps_script, desktop / "QCodes++ Offline Plotting.ps1")
            print("✓ PowerShell script copied to desktop")
        
        return True
    except Exception as e:
        print(f"✗ Failed to copy scripts to desktop: {e}")
        return False


def main(path=None):
    """Main setup function."""
    print("QCodes++ Windows Setup Helper")
    print("=" * 40)
    
    check_windows()
    
    # Check if QCodes++ is installed
    try:
        import qcodespp
        print(f"QCodes++ version {qcodespp.__version__} is already installed")
    except ImportError:
        print("QCodes++ is not installed. Please install it first with:")
        print("  pip install qcodespp")
        sys.exit(1)
    
    print("\nWhat would you like to do?")
    print("1. Create desktop and start menu shortcuts")
    print("2. Copy script files to desktop")
    print("3. Test installation")
    print("4. Do everything")
    print("Press any other key to exit.")
    
    try:
        choice = input("\nEnter your choice (1-4): ").strip()
    except KeyboardInterrupt:
        print("\nSetup cancelled.")
        sys.exit(0)
    
    success = True
    
    if choice in ["1", "2", "4"]:
        print("\n" + "=" * 40)
        success &= install_dependencies()

    if choice in ["1", "4"]:
        if not path:
            print("\nIf offline_plotting and Jupyter Lab should be launched from a specific folder, " \
            "specify the path below.\n" \
            "Otherwise, press Enter to use the default (user's home directory).")
            try:
                path = input("\nEnter the path: ").strip()
            except KeyboardInterrupt:
                print("\nSetup cancelled.")
                sys.exit(0)
            if path == "":
                path = None
        print("\n" + "=" * 40)
        success &= create_shortcuts(path=path)

    if choice in ["2", "4"]:
        print("\n" + "=" * 40)
        success &= copy_scripts_to_desktop()

    if choice in ["3", "4"]:
        print("\n" + "=" * 40)
        success &= test_installation()

    if choice not in ["1", "2", "3", "4"]:
        print("Exiting.")
        sys.exit(1)
    
    print("\n" + "=" * 40)
    if success:
        print("✓ Setup completed!")
    else:
        print("✗ Setup completed with some errors.")
        print("Check the messages above for details.")
    
    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
