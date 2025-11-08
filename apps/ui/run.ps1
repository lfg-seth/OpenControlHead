#!/usr/bin/env pwsh
# Exit on first error
$ErrorActionPreference = "Stop"

$RepoDir = Get-Location
$VenvDir = Join-Path $RepoDir ".venv"

Write-Host "=== Updating repository ==="
git pull --rebase

# Create venv if missing
if (-not (Test-Path $VenvDir)) {
    Write-Host "=== Creating virtual environment ==="
    python -m venv $VenvDir
}

# Activate venv
Write-Host "=== Activating virtual environment ==="
$ActivateScript = Join-Path $VenvDir "Scripts\Activate.ps1"
. $ActivateScript

# Install dependencies if missing
$ReqPySide = "PySide6"
try {
    python -c "import $ReqPySide" | Out-Null
} catch {
    Write-Host "=== Installing dependencies ==="
    python -m pip install --upgrade pip
    pip install -e .
}

Write-Host "=== Running o9-control-head ==="
python run.py
