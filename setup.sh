#!/bin/bash
set -e

echo "==========================================="
echo "SizeTrimmer System Installer"
echo "==========================================="

check_cmd() {
    command -v "$1" >/dev/null 2>&1
}

# 1. Check and install FFmpeg based on OS
echo "[1/3] Checking system dependencies..."
if check_cmd ffmpeg; then
    echo "  -> FFmpeg is already installed!"
else
    echo "  -> FFmpeg not found. Attempting to install..."
    
    if check_cmd apt; then
        echo "  -> Detected apt package manager (Debian/Ubuntu)"
        sudo apt update && sudo apt install -y ffmpeg
    elif check_cmd dnf; then
        echo "  -> Detected dnf package manager (Fedora/RHEL)"
        sudo dnf install -y ffmpeg
    elif check_cmd yum; then
        echo "  -> Detected yum package manager (CentOS/RHEL)"
        sudo yum install -y epel-release
        sudo yum install -y ffmpeg
    elif check_cmd pacman; then
        echo "  -> Detected pacman package manager (Arch/Manjaro)"
        sudo pacman -S --noconfirm ffmpeg
    elif check_cmd brew; then
        echo "  -> Detected Homebrew (macOS/Linux)"
        brew install ffmpeg
    else
        echo "  -> ERROR: Unsupported package manager. Please install FFmpeg manually."
        exit 1
    fi
fi

# 2. Setup Python environment
echo ""
echo "[2/3] Setting up Python environment..."
if [ ! -d ".venv" ]; then
    echo "  -> Creating virtual environment..."
    python3 -m venv .venv
else
    echo "  -> Virtual environment already exists."
fi

# 3. Install requirements
echo ""
echo "[3/3] Installing Python requirements..."
source .venv/bin/activate
pip install -r requirements.txt

echo ""
echo "==========================================="
echo "Setup Complete! You can now start the server with:"
echo "source .venv/bin/activate"
echo "python3 sizetrimmer.py"
echo "==========================================="
