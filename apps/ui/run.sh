#!/usr/bin/env bash
set -e  # Exit on any error

# --- Config: allowed Python versions for o9-control-head ---
PYTHON_CANDIDATES=("python3.12" "python3.11" "python3.10")

# --- Resolve paths ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"        # project root: OpenControlHead
VENV_DIR="$REPO_DIR/.venv"

echo "=== Using repo directory: $REPO_DIR ==="

# --- Pick a compatible Python binary ---
PYTHON_BIN=""

for candidate in "${PYTHON_CANDIDATES[@]}"; do
  if command -v "$candidate" &>/dev/null; then
    PYTHON_BIN="$(command -v "$candidate")"
    break
  fi
done

if [ -z "$PYTHON_BIN" ]; then
  echo "ERROR: No compatible Python found."
  echo "Please install one of: ${PYTHON_CANDIDATES[*]}"
  exit 1
fi

echo "=== Using Python: $PYTHON_BIN ==="

# --- (Re)create venv if needed or wrong version ---
NEED_VENV=0
if [ ! -d "$VENV_DIR" ]; then
  echo "=== No virtualenv found, creating one ==="
  NEED_VENV=1
elif ! "$VENV_DIR/bin/python" -c 'import sys; exit(0 if (3,10) <= sys.version_info[:2] < (3,13) else 1)' 2>/dev/null; then
  echo "=== Existing venv has incompatible Python, recreating ==="
  rm -rf "$VENV_DIR"
  NEED_VENV=1
fi

if [ "$NEED_VENV" -eq 1 ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# --- Activate venv ---
echo "=== Activating virtual environment ==="
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

# --- Install dependencies (only once / when missing) ---
echo "=== Ensuring dependencies are installed ==="
pip install -U pip

# Install the core project in editable mode from repo root
if ! python -c "import PySide6" &>/dev/null || ! python -c "import o9_control_head" &>/dev/null; then
  echo "=== Installing project dependencies (editable) ==="
  cd "$REPO_DIR"
  pip install -e .
fi

# --- Run UI app ---
echo "=== Running o9-control-head UI ==="
export DISPLAY=:0
export XAUTHORITY=/home/setheth/.Xauthority

cd "$SCRIPT_DIR"
python run.py
