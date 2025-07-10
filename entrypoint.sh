#!/bin/bash
echo "Running migrations..."
flask db upgrade

echo "Starting server..."
python -m flask run --port=8080
