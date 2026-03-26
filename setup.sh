#!/bin/bash
set -e

echo "=== Senior TV Setup ==="

# System dependencies
echo "[1/4] Installing system packages..."
sudo apt update
sudo apt install -y cec-utils python3-venv python3-pip xdotool

# Python virtual environment
echo "[2/4] Creating Python virtual environment..."
cd "$(dirname "$0")"
python3 -m venv venv
source venv/bin/activate

# Python packages
echo "[3/4] Installing Python packages..."
pip install -r requirements.txt

# Media directory
echo "[4/4] Setting up media directory..."
mkdir -p static/media

echo ""
echo "=== Setup complete! ==="
echo "To start: source venv/bin/activate && python server.py"
echo "Then open: google-chrome --kiosk http://localhost:5000"
