#!/bin/bash

echo "=== Entrypoint script starting ==="

echo "Current user: $(whoami)"
echo "Current working directory: $(pwd)"

# Ensure the /data directory exists and has proper permissions
echo "Creating /data directory..."
mkdir -p /data
echo "Setting permissions on /data..."
chmod 777 /data

echo "Checking /data directory before database creation:"
ls -la /data

echo "=== Starting FastAPI application ==="
# Start the FastAPI application
exec uvicorn app.main:app --host 0.0.0.0 --port 8000