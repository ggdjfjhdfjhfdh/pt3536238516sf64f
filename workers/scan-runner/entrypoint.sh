#!/bin/bash
set -e

echo "Current directory: $(pwd)"
echo "Listing files in current directory:"
ls -la

echo "Listing files in /app directory:"
ls -la /app

if [ -f "/app/run_scan.py" ]; then
    echo "run_scan.py found, starting application..."
    python /app/run_scan.py
else
    echo "Error: run_scan.py not found!"
    exit 1
fi