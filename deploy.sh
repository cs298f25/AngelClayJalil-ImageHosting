#!/bin/bash
set -e

# --- CONFIGURATION ---
APP_NAME="ImageHosting"
VENV_NAME="venv"

echo "=== Deploying $APP_NAME ==="

# ---------------------------------------------------
# 1. SYSTEM DEPENDENCIES (Redis & Nginx)
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
                echo "Amazon Linux 2 detected."
                sudo amazon-linux-extras install redis6 nginx1 -y
            else
                echo "Amazon Linux 2023+ detected."
                sudo dnf install redis6 nginx -y
            fi
        else
            echo "Error: Not on Amazon Linux. Install Redis/Nginx manually."
            exit 1
        fi
    fi
else
    echo "System dependencies are installed."
fi

# ---------------------------------------------------
# 2. CONFIGURE NGINX (Port 80 -> 8000)
# ---------------------------------------------------
echo "Configuring Nginx..."

# --- FIX: Ensure the directory exists before writing the file ---
if [ ! -d "/etc/nginx/conf.d" ]; then
    echo "Creating Nginx configuration directory..."
    sudo mkdir -p /etc/nginx/conf.d
fi

# We write the config file directly using sudo tee
sudo tee /etc/nginx/conf.d/imagehost.conf > /dev/null << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
EOF

# Restart Nginx to load the new config
sudo systemctl enable nginx
sudo systemctl restart nginx
echo "Nginx configured and restarted."

# ---------------------------------------------------
# 3. PYTHON SETUP
# ---------------------------------------------------
if [ ! -d "$VENV_NAME" ]; then
    echo "Creating virtual environment..."
    python3 -m venv $VENV_NAME
fi

echo "Activating virtual environment..."
source $VENV_NAME/bin/activate

if [ -f requirements.txt ]; then
    echo "Installing Python dependencies..."
    pip install -r requirements.txt
fi

if [ -f .env ]; then
  echo "Loading environment variables..."
  export $(grep -v '^#' .env | xargs)
fi

# ---------------------------------------------------
# 4. START REDIS
# ---------------------------------------------------
# Detect Redis command
if command -v redis-server &> /dev/null; then
    REDIS_CMD="redis-server"
elif command -v redis6-server &> /dev/null; then
    REDIS_CMD="redis6-server"
fi

if pgrep -f "$REDIS_CMD" > /dev/null; then
    echo "Redis is running."
else
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
        echo "Reloading Gunicorn..."
        pkill -f "gunicorn"
        sleep 1
    fi
    echo "Starting Gunicorn on Port 8000 (Nginx will forward to this)..."
    nohup gunicorn -w 4 -b 0.0.0.0:8000 app:app > app.log 2>&1 &
else
    echo "Local environment detected. Running dev server."
    python3 app.py
fi

echo "=== Deployment Complete ==="
echo "Your site should be live at http://$(curl -s http://checkip.amazonaws.com)"