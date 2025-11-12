#!/usr/bin/env bash
set -euo pipefail

echo "Running run.sh"
cd ~/Documents/iot_toucher/

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
pip3 install -r requirements.txt

echo "Running main.py"
python3 main.py
