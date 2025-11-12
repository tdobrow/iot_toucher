#!/usr/bin/env bash
set -euo pipefail

echo "Running run.sh"

# Create venv if it doesn't exist
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment"
  python3 -m venv .venv
fi

echo "Activating virtual environment"
. .venv/bin/activate

echo "Updating pip"
pip3 install --upgrade pip
echo "Installing requirements.txt"
pip3 install -r ~/Documents/iot_toucher/requirements.txt

echo "Running main.py"
python3 ~/Documents/iot_toucher/main.py
