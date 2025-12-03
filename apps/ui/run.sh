#!/usr/bin/env bash
set -e  # Exit on any error


REPO_DIR="$(pwd)"
VENV_DIR="$REPO_DIR/.venv"

echo "=== Updating repository ==="
git pull --rebase

# Create venv if missing
if [ ! -d "$VENV_DIR" ]; then
  echo "=== Creating virtual environment ==="
  python3 -m venv "$VENV_DIR"
fi

# Activate venv
echo "=== Activating virtual environment ==="
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

# Install dependencies if missing
REQ_PYSIDE="PySide6"
if ! python -c "import PySide6" &>/dev/null; then
  echo "=== Installing dependencies ==="
  pip install -U pip
  pip install -e .
fi

echo "=== Running o9-control-head ==="
export DISPLAY=:0
export XAUTHORITY=/home/setheth/.Xauthority


# Verify Can bus is available and the state is up

echo "=== Setting up CAN interface ==="

# For a real CAN adapter on can0
sudo ip link set can0 down 2>/dev/null || true
sudo ip link set can0 type can bitrate 250000
sudo ip link set can0 up

fi

python run.py

