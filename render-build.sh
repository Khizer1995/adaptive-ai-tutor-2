#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "Installing dependencies..."
pip install --upgrade pip
pip install --no-cache-dir -r requirements.txt

echo "Build complete!"
