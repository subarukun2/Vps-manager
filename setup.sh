#!/usr/bin/env bash
# ==============================================================================
#  TeleVPS Pro - Zero-Effort 1-Click Installer
#  Personal Heroku-like Telegram Bot & PM2 Webhook Manager
# ==============================================================================

set -e

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

clear
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}         ⚡ TeleVPS Pro - Personal Heroku Installer ⚡         ${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 1. Root Check
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}[!] This script must be run as root${NC}" 
   exit 1
fi

# 2. System Dependencies
echo -e "${BLUE}[1/6] Installing System Dependencies...${NC}"
apt-get update -y > /dev/null
apt-get install -y curl git python3-pip python3-venv build-essential jq ufw xxd ffmpeg > /dev/null

# 3. Node.js & PM2
echo -e "${BLUE}[2/6] Installing Node.js & PM2...${NC}"
if ! command -v node >/dev/null 2>&1; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - > /dev/null
    apt-get install -y nodejs > /dev/null
fi

if ! command -v pm2 >/dev/null 2>&1; then
    npm install -g pm2 > /dev/null
fi

# 4. Project Setup
echo -e "${BLUE}[3/6] Setting up project environment...${NC}"
mkdir -p /var/www/apps
mkdir -p logs

# 5. Python Environment
echo -e "${BLUE}[4/6] Initializing Python Virtual Environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
./venv/bin/pip install --upgrade pip > /dev/null
./venv/bin/pip install -r requirements.txt > /dev/null

# 6. Configuration (.env)
echo -e "${BLUE}[5/6] Configuring Environment...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}[?] Configuration needed!${NC}"
    read -p "Enter Telegram Bot Token: " TG_TOKEN
    read -p "Enter Telegram Admin ID: " TG_ADMIN
    
    WEBHOOK_SECRET=$(head -c 16 /dev/urandom | xxd -ps)
    HOST_URL=$(curl -s -4 ifconfig.me || echo "localhost")
    
    cat > .env << EOF
TELEGRAM_BOT_TOKEN="$TG_TOKEN"
TELEGRAM_ADMIN_ID="$TG_ADMIN"
GITHUB_TOKEN=""
WEBHOOK_PORT="8080"
WEBHOOK_SECRET="$WEBHOOK_SECRET"
HOST_URL="$HOST_URL"
APPS_DIR="/var/www/apps"
EOF
    echo -e "${GREEN}[+] .env created successfully!${NC}"
else
    echo -e "${GREEN}[+] .env already exists. Skipping...${NC}"
fi

# 7. Starting Daemons
echo -e "${BLUE}[6/6] Launching TeleVPS Daemons via PM2...${NC}"
pm2 delete televps-bot televps-webhook 2>/dev/null || true
pm2 start ecosystem.config.js
pm2 save > /dev/null

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}             🎉 TeleVPS Pro Setup Successfully! 🎉             ${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "Your bot is now running in the background."
echo -e "Check your Telegram Bot and type ${YELLOW}/start${NC} to begin."
echo ""
echo -e "💡 ${CYAN}Useful Commands:${NC}"
echo -e " - View Bot Logs:   ${YELLOW}pm2 logs televps-bot${NC}"
echo -e " - View Webhook:    ${YELLOW}pm2 logs televps-webhook${NC}"
echo -e " - Restart All:     ${YELLOW}pm2 restart ecosystem.config.js${NC}"
echo ""
echo -e "${BLUE}Deployment directory:${NC} /var/www/apps"
echo -e "${BLUE}Webhook endpoint:${NC} http://$(cat .env | grep HOST_URL | cut -d'"' -f2):8080/webhook/{app_name}"
echo ""
