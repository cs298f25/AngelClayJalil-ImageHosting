#!/bin/bash
# ImageHosting Shutdown Script

echo "=== Stopping ImageHosting Application ==="

# 1. STOP NGINX
if systemctl is-active --quiet nginx; then
    echo "Stopping Nginx..."
    sudo systemctl stop nginx
    echo "Nginx stopped."
fi

# 2. STOP GUNICORN
if pgrep -f "gunicorn" > /dev/null; then
    echo "Stopping Gunicorn..."
    pkill -f "gunicorn"
    echo "Gunicorn stopped."
else
    echo "Gunicorn is not running."
fi

# 3. STOP FLASK DEV
if pgrep -f "python3 app.py" > /dev/null; then
    echo "Stopping Flask Dev Server..."
    pkill -f "python3 app.py"
    echo "Flask stopped."
fi

# 4. STOP REDIS
if pgrep -f "redis" > /dev/null; then
    echo "Stopping Redis..."
    if command -v redis-cli &> /dev/null; then
        redis-cli shutdown
    elif command -v redis6-cli &> /dev/null; then
        redis6-cli shutdown
    else
        pkill -f "redis"
    fi
    echo "Redis stopped."
fi

echo "=== Application is completely down ==="