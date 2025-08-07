@echo off
REM QCodes++ Offline Plotting Launcher for Windows
REM This script launches the QCodes++ offline plotting GUI

echo Starting QCodes++ Offline Plotting...

REM Try to run with the qcodespp command (if installed via pip)
qcodespp offline_plotting %*

REM If that fails, try running with python -m
if %ERRORLEVEL% neq 0 (
    echo Command 'qcodespp' not found, trying 'python -m qcodespp.cli'...
    python -m qcodespp.cli offline_plotting %*
)

REM If that also fails, try with py launcher
if %ERRORLEVEL% neq 0 (
    echo Trying with 'py' launcher...
    py -m qcodespp.cli offline_plotting %*
)

REM If all attempts fail
if %ERRORLEVEL% neq 0 (
    echo Failed to start QCodes++ Offline Plotting.
    echo Please ensure QCodes++ is properly installed and Python is in your PATH.
    pause
    exit /b 1
)
