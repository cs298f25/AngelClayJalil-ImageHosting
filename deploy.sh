#!/bin/bash
# ImageHosting Deployment Script

set -e

echo "Starting ImageHosting..."

# Load environment variables
if [ -f .env ]; then
  echo "Loading environment variables..."
  export $(grep -v '^#' .env | xargs)
fi

# Check if Redis is installed
if ! command -v redis6-server &> /dev/null; then
  echo "Redis is not installed. Install it with: brew install redis"
  exit 1
fi

# Start Redis if not already running
if ! pgrep -x "redis6-server" > /dev/null; then
  echo "Starting Redis..."
  redis6-server --daemonize yes
  sleep 2
else
  echo "Redis is already running."
fi

# Verify Redis connection
echo "Checking Redis connection..."
if redis6-cli ping | grep -q "PONG"; then
  echo "Redis is responding."
else
  echo "Redis did not respond. Please check Redis logs."
  exit 1
fi

# Run Flask app
echo "Starting Flask app..."
python3 app.py
