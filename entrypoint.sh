#!/bin/bash
set -e

echo "Running migrations..."
flask db upgrade

echo "Starting server with Gunicorn..."
exec gunicorn -w 4 -b 0.0.0.0:8080 run:app
