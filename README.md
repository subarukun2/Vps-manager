# ⚡ TeleVPS Pro — Your Personal Telegram-Based PaaS

Turn any fresh **Ubuntu 22.04 LTS** VPS into a personal cloud platform (Heroku-like) that you control entirely from **Telegram**. No SSH needed after initial setup.

![Status](https://img.shields.io/badge/Status-Stable-brightgreen)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![PM2](https://img.shields.io/badge/Manager-PM2-orange)

## 🚀 Key Features

*   **1-Click Deployment:** Just select your GitHub repository from the bot menu.
*   **Smart Auto-Detection:** Automatically scans for `Procfile`, `manage.py`, `package.json`, or `main.py` and sets up the environment (Python Venv or Node.js).
*   **Recursive Subfolder Support:** Safely finds your app root even if it's deep inside a subfolder.
*   **Live Webhooks:** Instant auto-redeploy whenever you push code to GitHub.
*   **Full App Lifecycle:** Start, Stop, Restart, Delete, and view Logs directly from Telegram buttons.
*   **Environment Management:** Add or delete Config Vars (`.env`) without touching the terminal.
*   **Config Sync:** One-tap import of constants from a `config.py` file (Heroku-style).
*   **System Monitoring:** Real-time CPU, RAM, and Disk telemetry.

## 🛠 Installation

1.  Log in to your VPS as `root`.
2.  Run the one-click installer:
    ```bash
    curl -sSL https://raw.githubusercontent.com/your-username/your-repo/main/setup.sh | bash
    ```
3.  Follow the prompts to enter your **Bot Token** (from @BotFather) and your **Telegram ID** (from @userinfobot).
4.  Once setup is complete, go to your Telegram bot and type `/start`.

## 🛡️ Security Safety Rules

The bot follows these strict rules for scanning repositories:
1.  **Priority Order:** `Procfile` is always used first. If not found, it looks for `manage.py`, `package.json`, `main.py`, or `bot.py`.
2.  **Junk Exclusion:** Explicitly ignores `.git`, `node_modules`, `venv`, `env`, `__pycache__`, `dist`, and `build` folders.
3.  **Shallowest Preference:** If multiple entry files are found (e.g., multiple `package.json`), the one closest to the repository root is selected.

## 📁 Architecture

*   `bot.py`: The main orchestrator and Telegram interface.
*   `webhook.py`: A lightweight FastAPI server for handling GitHub push events.
*   `utils.py`: Shared logic for smart project detection and environment setup.
*   `setup.sh`: Automated script for installing all dependencies (Python, Node, PM2, Redis).

## 🤝 Support

For bugs or feature requests, please reach out via Telegram or open an issue in the repository.

---
*Created with ❤️ for zero-effort VPS management.*
