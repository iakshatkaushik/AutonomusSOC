#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# CyberSOC Agent — EC2 Deployment Script
# Run this on a fresh Ubuntu 22.04 EC2 instance (t3.medium)
# ═══════════════════════════════════════════════════════════════════

set -e

echo "═══ CyberSOC Agent — EC2 Setup ═══"

# ─── 1. System packages ────────────────────────────────────────
echo "[1/7] Installing system packages..."
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv git nginx curl

# Install Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# ─── 2. Clone the repo ────────────────────────────────────────
echo "[2/6] Cloning repository..."
cd /home/ubuntu
if [ -d "CyberSOC-Agent" ]; then
    cd CyberSOC-Agent && git pull
else
    git clone https://github.com/iakshatkaushik/CyberSOC-Agent.git
    cd CyberSOC-Agent
fi

# ─── 3. Python virtual env + dependencies ─────────────────────
echo "[3/6] Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# ─── 4. Build React frontend ──────────────────────────────────
echo "[4/7] Building frontend..."
cd /home/ubuntu/CyberSOC-Agent/dashboard
npm install
npm run build
cd /home/ubuntu/CyberSOC-Agent

# ─── 4. Create .env file ──────────────────────────────────────
echo "[4/6] Setting up environment..."
cat > .env << 'ENVFILE'
DATABASE_URL=sqlite:///data/processed/autonomussoc.db
RAW_DATA_DIR=data/raw/r4.2
ANSWERS_DIR=data/raw/answers
LLM_PROVIDER=gemini
LLM_API_KEY=YOUR_GEMINI_KEY_HERE
LLM_MODEL=gemini-2.5-flash
ENVFILE

echo ">>> IMPORTANT: Edit /home/ubuntu/CyberSOC-Agent/.env and set your LLM_API_KEY"

# ─── 5. Nginx reverse proxy ───────────────────────────────────
echo "[5/6] Configuring Nginx..."
sudo tee /etc/nginx/sites-available/cybersoc > /dev/null << 'NGINX'
server {
    listen 80;
    server_name _;

    # Proxy all requests to FastAPI (which serves both API + React SPA)
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
    }
}
NGINX

sudo ln -sf /etc/nginx/sites-available/cybersoc /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

# ─── 6. Systemd service for auto-start ────────────────────────
echo "[6/6] Creating systemd service..."
sudo tee /etc/systemd/system/cybersoc.service > /dev/null << 'SERVICE'
[Unit]
Description=CyberSOC Agent API
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/CyberSOC-Agent
Environment=PATH=/home/ubuntu/CyberSOC-Agent/venv/bin:/usr/bin
ExecStart=/home/ubuntu/CyberSOC-Agent/venv/bin/uvicorn src.api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable cybersoc
sudo systemctl start cybersoc

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  ✅ CyberSOC Agent deployed!"
echo ""
echo "  1. Edit .env:  nano /home/ubuntu/CyberSOC-Agent/.env"
echo "  2. Upload your data/ folder to /home/ubuntu/CyberSOC-Agent/data/"
echo "  3. Restart:    sudo systemctl restart cybersoc"
echo "  4. Visit:      http://YOUR_EC2_PUBLIC_IP"
echo ""
echo "  Logs:  sudo journalctl -u cybersoc -f"
echo "═══════════════════════════════════════════════════════"
