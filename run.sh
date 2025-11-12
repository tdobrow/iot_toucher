#!/usr/bin/env bash
set -euo pipefail

# Create venv if it doesn't exist
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

# Activate it
. .venv/bin/activate

# Install deps
pip3 install --upgrade pip
pip3 install -r requirements.txt

# Run your app
python3 main.py