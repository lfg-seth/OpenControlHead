#!/usr/bin/env bash
set -e  # Exit on any error

echo "=== o9-control-head startup ==="
echo "=== Waiting for X display :0 ==="
for i in {1..10}; do
  if DISPLAY=:0 xhost >/dev/null 2>&1; then
    echo "=== X display is ready ==="
    break
  fi
  echo "X not ready yet, retrying..."
  sleep 1
done

# Absolute paths so systemd can't confuse us
REPO_ROOT="/home/setheth/dev/OpenControlHead"
APP_DIR="$REPO_ROOT/apps/ui"
VENV_DIR="$REPO_ROOT/apps/ui/.venv"

cd "$APP_DIR"

echo "=== Using repo root: $REPO_ROOT ==="
echo "=== Using app dir : $APP_DIR ==="
echo "=== Using venv    : $VENV_DIR ==="

echo "=== Activating virtual environment ==="
if [ ! -d "$VENV_DIR" ]; then
  echo "=== Creating virtual environment at $VENV_DIR ==="
  python3 -m venv "$VENV_DIR"

  # shellcheck source=/dev/null
  source "$VENV_DIR/bin/activate"

  echo "=== Installing dependencies (first time) ==="
  pip install -U pip
  cd "$REPO_ROOT"
  pip install -e .
  cd "$APP_DIR"
else
  # shellcheck source=/dev/null
  source "$VENV_DIR/bin/activate"

  # Only reinstall deps if PySide6 is missing
  if ! python -c "import PySide6" &>/dev/null; then
    echo "=== Installing dependencies (PySide6 missing) ==="
    pip install -U pip
    cd "$REPO_ROOT"
    pip install -e .
    cd "$APP_DIR"
  fi
fi

echo "=== Setting display env ==="
export DISPLAY=:0
export XAUTHORITY=/home/setheth/.Xauthority

echo "=== Launching UI ==="
exec python run.py
