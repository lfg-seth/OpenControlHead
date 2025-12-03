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
if ! python -c "import ${REQ_PYSIDE}" &>/dev/null; then
  echo "=== Installing dependencies ==="
  pip install -U pip
  pip install -e .
fi

echo "=== Running o9-control-head ==="
export DISPLAY=:0
export XAUTHORITY=/home/setheth/.Xauthority

echo "=== Setting up CAN interface (can0 @ 250000) ==="


# Verify that can0 exists and is UP
if ip link show can0 &>/dev/null; then
  # Sample output fragment:
  # 3: can0: <NOARP,ECHO> mtu 16 qdisc noop state DOWN mode DEFAULT group default qlen 10
  # We just care that the line contains "state UP"
  if ip -o link show can0 | grep -q "state UP"; then
    echo "=== CAN interface can0 is UP ==="
  else
    echo "!!! ERROR: can0 exists but is not UP. Current status:"
    ip -o link show can0
    echo "Exiting so the app doesn't crash with 'Network is down'."
    exit 1
  fi
else
  echo "!!! ERROR: can0 interface does not exist."
  echo "Make sure your CAN adapter is plugged in / configured, then rerun this script."
  exit 1
fi

python run.py
