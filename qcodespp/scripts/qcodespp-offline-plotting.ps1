# QCodes++ Offline Plotting Launcher for Windows (PowerShell)
# This script launches the QCodes++ offline plotting GUI

Write-Host "Starting QCodes++ Offline Plotting..." -ForegroundColor Green

# Function to test if a command exists
function Test-Command($cmdname) {
    return [bool](Get-Command -Name $cmdname -ErrorAction SilentlyContinue)
}

# Try different methods to launch the application
$success = $false

# Method 1: Try qcodespp command (if installed via pip)
if (Test-Command "qcodespp") {
    Write-Host "Using 'qcodespp' command..." -ForegroundColor Cyan
    try {
        & qcodespp offline_plotting $args
        $success = $true
    }
    catch {
        Write-Host "Failed with 'qcodespp' command: $_" -ForegroundColor Yellow
    }
}

# Method 2: Try python -m qcodespp.cli
if (-not $success -and (Test-Command "python")) {
    Write-Host "Trying 'python -m qcodespp.cli'..." -ForegroundColor Cyan
    try {
        & python -m qcodespp.cli offline_plotting $args
        $success = $true
    }
    catch {
        Write-Host "Failed with 'python -m qcodespp.cli': $_" -ForegroundColor Yellow
    }
}

# Method 3: Try py launcher
if (-not $success -and (Test-Command "py")) {
    Write-Host "Trying 'py -m qcodespp.cli'..." -ForegroundColor Cyan
    try {
        & py -m qcodespp.cli offline_plotting $args
        $success = $true
    }
    catch {
        Write-Host "Failed with 'py -m qcodespp.cli': $_" -ForegroundColor Yellow
    }
}

# If all methods failed
if (-not $success) {
    Write-Host "Failed to start QCodes++ Offline Plotting." -ForegroundColor Red
    Write-Host "Please ensure QCodes++ is properly installed and Python is in your PATH." -ForegroundColor Red
    Write-Host "Press any key to continue..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}
