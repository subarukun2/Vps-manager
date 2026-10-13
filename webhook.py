from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
import os
import hmac
import hashlib
import subprocess
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load credentials
load_dotenv()

app = FastAPI(title="TeleVPS Auto-Deploy Engine")

# --- Environment Configuration ---
APPS_DIR = Path(os.getenv("APPS_DIR", "/var/www/apps"))
SECRET = os.getenv("WEBHOOK_SECRET", "")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID")

def notify_telegram(message: str):
    """Sends status updates to the Telegram Admin."""
    if BOT_TOKEN and ADMIN_ID:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        try:
            requests.post(url, json={"chat_id": ADMIN_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
        except Exception as e:
            print(f"Failed to send TG notification: {e}")

def run_auto_deploy(app_name: str, pusher_name: str, commit_hash: str, commit_msg: str):
    """Orchestrates git pull, dependency refresh, and PM2 restart."""
    path = APPS_DIR / app_name
    if not path.exists():
        print(f"[!] Auto-deploy failed: {path} not found.")
        return
    
    try:
        # 1. Pull latest code
        subprocess.run(["git", "pull"], cwd=str(path), check=True)
        
        # 2. Smart dependency refresh
        if (path / "package.json").exists():
            subprocess.run(["npm", "install", "--production"], cwd=str(path), check=True)
            
        if (path / "requirements.txt").exists():
            pip_bin = str(path / "venv" / "bin" / "pip") if (path / "venv").exists() else "pip3"
            subprocess.run([pip_bin, "install", "-r", "requirements.txt"], cwd=str(path), check=True)
            
        # 3. Reload PM2 process
        subprocess.run(["pm2", "restart", app_name], check=True)
        
        notify_telegram(
            f"🚀 *Auto-Deploy Successful!*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 *App:* `{app_name}`\n"
            f"👤 *Pushed by:* `{pusher_name}`\n"
            f"🔖 *Commit:* `{commit_hash[:7]}` — _{commit_msg}_"
        )
    except Exception as e:
        notify_telegram(f"❌ *Auto-Deploy Failed:* `{app_name}`\nError: `{str(e)}`")

@app.post("/webhook/{app_name}")
async def handle_github_push(app_name: str, request: Request, tasks: BackgroundTasks):
    """Listens for GitHub push events and validates HMAC signatures."""
    body = await request.body()
    
    # Validate Webhook Secret if set
    if SECRET:
        signature = request.headers.get("X-Hub-Signature-256")
        if not signature:
            raise HTTPException(status_code=401, detail="Signature missing")
        
        expected_signature = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            raise HTTPException(status_code=403, detail="Invalid signature")
        
    payload = await request.json()
    
    # Only react to push events
    event_type = request.headers.get("X-GitHub-Event", "push")
    if event_type == "ping":
        return {"status": "pong", "msg": "Webhook successfully connected"}
        
    if event_type == "push":
        pusher = payload.get("pusher", {}).get("name", "Unknown")
        head = payload.get("head_commit", {})
        commit_id = head.get("id", "latest")
        msg = head.get("message", "New commit").split("\n")[0]
        
        # Offload to background task for instant GitHub response
        tasks.add_task(run_auto_deploy, app_name, pusher, commit_id, msg)
        
    return {"status": "accepted", "app": app_name}

@app.get("/health")
def health():
    return {"status": "healthy"}
