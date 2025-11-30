#!/bin/bash
set -e

# --- CONFIGURATION ---
APP_NAME="ImageHosting"
VENV_NAME="venv"
DOMAIN="lopeza06web.moraviancs.click" # <--- YOUR DOMAIN

echo "=== Deploying $APP_NAME ==="

# ---------------------------------------------------
# 1. SYSTEM DEPENDENCIES
# ---------------------------------------------------
echo "Checking system dependencies..."
NEEDS_INSTALL=false

if ! command -v redis-server &> /dev/null && ! command -v redis6-server &> /dev/null; then
    echo "Redis missing."
    NEEDS_INSTALL=true
fi

if ! command -v nginx &> /dev/null; then
    echo "Nginx missing."
    NEEDS_INSTALL=true
fi

if [ "$NEEDS_INSTALL" = true ]; then
    echo "Installing missing dependencies..."
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        if [[ "$NAME" == "Amazon Linux"* ]]; then
            if [[ "$VERSION_ID" == "2" ]]; then
                sudo amazon-linux-extras install redis6 nginx1 -y
            else
                sudo dnf install redis6 nginx -y
            fi
        fi
    fi
fi

# ---------------------------------------------------
# 2. CONFIGURE NGINX (Smart SSL Check)
# ---------------------------------------------------
echo "Configuring Nginx..."

if [ ! -d "/etc/nginx/conf.d" ]; then
    sudo mkdir -p /etc/nginx/conf.d
fi

# CHECK: Does the config file have Certbot settings?
# If yes, we DO NOT overwrite it.
if [ -f "/etc/nginx/conf.d/imagehost.conf" ] && grep -q "managed by Certbot" /etc/nginx/conf.d/imagehost.conf; then
    echo "SSL Certificate detected. Skipping Nginx overwrite to preserve HTTPS."
else
    echo "No SSL detected. Writing standard HTTP config..."
    
    # Write standard HTTP config
    sudo tee /etc/nginx/conf.d/imagehost.conf > /dev/null << EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF
fi

# Restart Nginx
sudo systemctl enable nginx
sudo systemctl restart nginx

# ---------------------------------------------------
# 3. PYTHON SETUP
# ---------------------------------------------------
if [ ! -d "$VENV_NAME" ]; then
    echo "Creating virtual environment..."
    python3 -m venv $VENV_NAME
fi

source $VENV_NAME/bin/activate

if [ -f requirements.txt ]; then
    echo "Installing Python dependencies..."
    pip install -r requirements.txt
fi

if [ -f .env ]; then
  echo "Loading env vars..."
  export $(grep -v '^#' .env | xargs)
fi

# ---------------------------------------------------
# 4. START REDIS
# ---------------------------------------------------
if command -v redis-server &> /dev/null; then
    REDIS_CMD="redis-server"
elif command -v redis6-server &> /dev/null; then
    REDIS_CMD="redis6-server"
fi

if ! pgrep -f "$REDIS_CMD" > /dev/null; then
    echo "Starting Redis..."
    $REDIS_CMD --daemonize yes
    sleep 1
fi

# ---------------------------------------------------
# 5. START APP
# ---------------------------------------------------
echo "Starting Application..."

if [ "$USER" == "ec2-user" ] || [ "$USER" == "ubuntu" ]; then
    if pgrep -f "gunicorn" > /dev/null; then
        pkill -f "gunicorn"
        sleep 1
    fi
    echo "Starting Gunicorn on Port 8000..."
    nohup gunicorn -w 4 -b 0.0.0.0:8000 app:app > app.log 2>&1 &
else
    python3 app.py
fi

echo "=== Deployment Complete ==="