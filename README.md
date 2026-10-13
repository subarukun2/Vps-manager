# ⚡ TeleVPS Pro — Personal Heroku Telegram Manager

Turn any fresh **Ubuntu 22.04 LTS** VPS into a personal PaaS cloud (Heroku-like) that you control entirely from **Telegram**. No SSH needed after setup.

![Version](https://img.shields.io/badge/Version-2.0.0-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10+-yellow?style=for-the-badge)
![Node](https://img.shields.io/badge/Node-20.x-green?style=for-the-badge)
![PM2](https://img.shields.io/badge/Process_Manager-PM2-brightgreen?style=for-the-badge)

---

## 🚀 Instant 1-Command Setup

Log into your VPS as `root` and run this magic command:

```bash
curl -sSL https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/setup.sh | bash
```

### 🪄 What this script does:
- ✅ Installs **Node.js 20** & **PM2** globally.
- ✅ Sets up **Python 3.10+** & Virtual Environments.
- ✅ Automates **UFW Firewall** (Port 8080 for webhooks).
- ✅ Configures **GitHub Integration** (Auto-Webhooks).
- ✅ Launches **TeleVPS Dashboard** on Telegram.

---

## 🔥 Key Features

### 1. Direct GitHub Integration
Connect your GitHub account using a **Personal Access Token (PAT)**. Once connected, you can browse all your repositories (Public & Private) directly via inline buttons in Telegram.

### 2. Smart Build & Auto-Detect
TeleVPS analyzes your repository structure just like Heroku Buildpacks:
- **Python:** Detects `requirements.txt`, creates `venv`, and installs dependencies.
- **Node.js:** Detects `package.json` and runs `npm install`.
- **Procfile:** Automatically reads your `web:` start command.

### 3. Fully Automated Webhooks
When you deploy a repo, TeleVPS **automatically creates a Webhook** on your GitHub repository. Every time you `git push`, your app on the VPS will:
1. `git pull` the latest code.
2. Re-install new dependencies (pip/npm).
3. Restart the PM2 process.
4. Notify you on Telegram with the commit details.

### 4. Powerful Telegram UI
Manage everything without touching a terminal:
- **Start / Stop / Restart** apps.
- **View Live Logs** (Last 30 lines) in one click.
- **Monitor System Stats** (CPU, RAM, Disk, Load).
- **Delete Apps** and clean up PM2.

---

## 🛠 Manual Configuration

If you prefer manual setup, edit the `.env` file:

```ini
TELEGRAM_BOT_TOKEN="your_bot_token"
TELEGRAM_ADMIN_ID="your_user_id"
GITHUB_TOKEN=""
WEBHOOK_PORT="8080"
HOST_URL="your_vps_ip"
```

Then start the services:
```bash
pm2 start ecosystem.config.js
pm2 save
```

---

## 📂 Project Structure

```text
├── bot.py                # Telegram Bot (Orchestrator)
├── webhook.py            # FastAPI Webhook Server
├── setup.sh              # 1-Click Installer
├── ecosystem.config.js   # PM2 Process Config
├── requirements.txt      # Python Dependencies
└── apps/                 # Root for all deployed apps
```

---

## 🤝 Contributing
Feel free to fork this project and add more "Buildpacks" or features. 

---

### 🛡 Security Warning
This bot is designed for **personal use**. It includes an `ADMIN_ONLY` whitelist to ensure only you can control your VPS. Never share your `.env` file or Bot Token with anyone.

---
*Created with ❤️🌚
