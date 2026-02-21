# ===========================================
# SizeTrimmer System Installer (Windows)
# ===========================================

Write-Host "==========================================="
Write-Host "SizeTrimmer System Installer"
Write-Host "==========================================="

function Check-Command {
    param([string]$cmd)
    try {
        $null = Get-Command $cmd -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

# 1. Check and install FFmpeg based on OS
Write-Host "[1/3] Checking system dependencies..."
if (Check-Command "ffmpeg") {
    Write-Host "  -> FFmpeg is already installed!"
} else {
    Write-Host "  -> FFmpeg not found. Attempting to install..."
    
    if (Check-Command "winget") {
        Write-Host "  -> Detected WinGet package manager"
        winget install --id=Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
    } elseif (Check-Command "choco") {
        Write-Host "  -> Detected Chocolatey package manager"
        choco install ffmpeg -y
    } elseif (Check-Command "scoop") {
        Write-Host "  -> Detected Scoop package manager"
        scoop install ffmpeg
    } else {
        Write-Host "  -> ERROR: Unsupported package manager. Please install FFmpeg manually from https://ffmpeg.org/download.html"
        exit 1
    }
    
    # Reload environment variables so FFmpeg drops into the current terminal session
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}

# 2. Setup Python environment
Write-Host "`n[2/3] Setting up Python environment..."
if (-Not (Test-Path ".venv")) {
    Write-Host "  -> Creating virtual environment..."
    python -m venv .venv
} else {
    Write-Host "  -> Virtual environment already exists."
}

# 3. Install requirements
Write-Host "`n[3/3] Installing Python requirements..."
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Write-Host "`n==========================================="
Write-Host "Setup Complete! You can now start the server with:"
Write-Host ".\.venv\Scripts\Activate.ps1"
Write-Host "python sizetrimmer.py"
Write-Host "==========================================="
