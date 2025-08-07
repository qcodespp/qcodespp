#!/usr/bin/env python3
"""
QCodes++ Offline Plotting GUI Launcher
Standalone executable version for Windows distribution.
"""

import sys
import os
import traceback
import tkinter as tk
from tkinter import messagebox


def show_error(title, message):
    """Show error dialog with fallback to console."""
    try:
        root = tk.Tk()
        root.withdraw()  # Hide the root window
        messagebox.showerror(title, message)
        root.destroy()
    except:
        print(f"ERROR - {title}: {message}")
        input("Press Enter to exit...")


def main():
    """Main launcher function."""
    try:
        # Try to import and run qcodespp offline plotting
        from qcodespp.plotting.offline.main import offline_plotting
        
        # Start the offline plotting GUI
        offline_plotting()
        
    except ImportError as e:
        error_msg = (
            "QCodes++ is not installed or not available.\n\n"
            f"Error details: {str(e)}\n\n"
            "Please install QCodes++ using:\n"
            "pip install qcodespp\n\n"
            "Then try running this program again."
        )
        show_error("QCodes++ Not Found", error_msg)
        sys.exit(1)
        
    except Exception as e:
        error_msg = (
            f"An unexpected error occurred:\n\n"
            f"{str(e)}\n\n"
            f"Error type: {type(e).__name__}\n\n"
            "Please check that QCodes++ is properly installed and try again."
        )
        show_error("QCodes++ Error", error_msg)
        
        # Print full traceback to console for debugging
        print("\nFull error traceback:")
        traceback.print_exc()
        
        sys.exit(1)


if __name__ == "__main__":
    # Set window title for console window
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW("QCodes++ Offline Plotting")
        except:
            pass
    
    main()
