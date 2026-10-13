import os
import sys
import json
import logging
import subprocess
import html
import asyncio
import time
from functools import wraps
from pathlib import Path
import psutil
from github import Github, GithubException
from dotenv import load_dotenv, set_key

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# --- Configuration Loading ---
ENV_PATH = Path(".env")
load_dotenv(dotenv_path=ENV_PATH)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "0"))
WEBHOOK_PORT = os.getenv("WEBHOOK_PORT", "8080")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
HOST_URL = os.getenv("HOST_URL", "localhost")
APPS_DIR = Path(os.getenv("APPS_DIR", "/var/www/apps"))

# Ensure directories exist
APPS_DIR.mkdir(parents=True, exist_ok=True)
Path("logs").mkdir(parents=True, exist_ok=True)

# --- Logging Setup ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("logs/bot.log"), logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TeleVPS")

# --- Conversation States ---
WAITING_GITHUB_TOKEN = 1

# ------------------------------------------------------------------------------
# SECURITY: ADMIN WHITELIST DECORATOR
# ------------------------------------------------------------------------------
def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id if update.effective_user else None
        if user_id != ADMIN_ID:
            if update.message:
                await update.message.reply_text("⛔ *Unauthorized Access*\nThis bot is private and restricted to the administrator.", parse_mode=ParseMode.MARKDOWN)
            logger.warning(f"Rejected unauthorized access from User ID: {user_id}")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# ------------------------------------------------------------------------------
# HELPERS: GITHUB & BUILD DETECTION
# ------------------------------------------------------------------------------
def get_gh_client(context):
    token = context.user_data.get("github_token") or os.getenv("GITHUB_TOKEN")
    if not token or len(token) < 10:
        return None
    return Github(token)

def detect_build_profile(repo_path):
    """Detects environment and start command like a Heroku buildpack."""
    p = Path(repo_path)
    profile = {"type": "unknown", "cmd": ""}
    
    # 1. Procfile check (highest priority)
    if (p / "Procfile").exists():
        with open(p / "Procfile", "r") as f:
            for line in f:
                if line.strip().startswith("web:"):
                    profile["cmd"] = line.replace("web:", "").strip()
                    break

    # 2. Node.js detection
    if (p / "package.json").exists():
        profile["type"] = "nodejs"
        if not profile["cmd"]:
            try:
                with open(p / "package.json") as f:
                    data = json.load(f)
                    if "scripts" in data and "start" in data["scripts"]:
                        profile["cmd"] = "npm start"
                    else:
                        profile["cmd"] = "node index.js"
            except:
                profile["cmd"] = "npm start"
            
    # 3. Python detection
    elif (p / "requirements.txt").exists():
        profile["type"] = "python"
        if not profile["cmd"]:
            if (p / "main.py").exists(): profile["cmd"] = "python3 main.py"
            elif (p / "app.py").exists(): profile["cmd"] = "python3 app.py"
            elif (p / "run.py").exists(): profile["cmd"] = "python3 run.py"
            else: profile["cmd"] = "python3 manage.py runserver"
            
    return profile

def run_cmd(cmd, cwd=None):
    """Executes a shell command and returns output + error."""
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd, timeout=300)
        return res.stdout, res.stderr, res.returncode
    except Exception as e:
        return "", str(e), 1

def get_pm2_apps():
    """Gets list of all PM2 apps."""
    res = subprocess.run(["pm2", "jlist"], capture_output=True, text=True)
    try:
        return [a for a in json.loads(res.stdout) if a['name'] not in ["televps-bot", "televps-webhook"]]
    except:
        return []

def get_pm2_app_status(name):
    """Gets detailed status of a PM2 app."""
    apps = get_pm2_apps()
    return next((a for a in apps if a['name'] == name), None)

# ------------------------------------------------------------------------------
# CORE HANDLERS
# ------------------------------------------------------------------------------

@admin_only
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main dashboard menu."""
    token = context.user_data.get("github_token") or os.getenv("GITHUB_TOKEN")
    gh_status = "🟢 Connected" if (token and len(token) > 10) else "🔴 Disconnected"
    
    # Quick Summary
    apps = get_pm2_apps()
    online_apps = len([a for a in apps if a['pm2_env']['status'] == 'online'])
    
    kb = [
        [InlineKeyboardButton("📦 My Repositories", callback_data="list_repos")],
        [InlineKeyboardButton("🚀 Manage Apps", callback_data="manage_apps"), InlineKeyboardButton("📊 System Stats", callback_data="stats")],
        [InlineKeyboardButton("🔗 Connect GitHub (PAT)", callback_data="connect_gh")],
        [InlineKeyboardButton("⚙️ Advanced Settings", callback_data="advanced_menu")]
    ]
    
    text = (
        f"⚡ *TeleVPS Pro - Control Panel*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *Admin:* `{ADMIN_ID}`\n"
        f"🔗 *GitHub:* {gh_status}\n"
        f"📦 *Apps:* `{online_apps}/{len(apps)} Online`\n"
        f"🌐 *Host:* `{HOST_URL}`\n\n"
        f"Select an orchestration option:"
    )
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

@admin_only
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command with documentation."""
    help_text = (
        "📖 *TeleVPS Help Guide*\n\n"
        "1️⃣ *Connect GitHub:* Use the 'Connect GitHub' button and send your Personal Access Token. Scopes required: `repo` and `admin:repo_hook`.\n\n"
        "2️⃣ *Deploy:* Select a repo from 'My Repositories'. TeleVPS will clone, install deps, create a webhook, and start the app via PM2.\n\n"
        "3️⃣ *Manage:* View status, logs, restart or delete apps from the 'Manage Apps' menu.\n\n"
        "4️⃣ *Auto-Deploy:* Every `git push` to your GitHub repo will automatically pull and restart your app on the VPS.\n\n"
        "💡 *Tip:* Use /start to refresh the main menu anytime."
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

@admin_only
async def connect_gh_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiates GitHub connection flow."""
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "🔑 *GitHub Integration*\n\nPlease send your GitHub Personal Access Token (classic).\n\n"
        "*Required Scopes:*\n• `repo` (Full control)\n• `admin:repo_hook` (Manage webhooks)\n\n"
        "Send token as a reply or /cancel to abort."
    )
    return WAITING_GITHUB_TOKEN

async def token_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Validates and saves the GitHub token."""
    token = update.message.text.strip()
    if token.startswith("/"): return ConversationHandler.END
    
    try:
        g = Github(token)
        user = g.get_user().login
        set_key(str(ENV_PATH), "GITHUB_TOKEN", token)
        os.environ["GITHUB_TOKEN"] = token
        context.user_data["github_token"] = token
        await update.message.reply_text(f"✅ *Connected as {user}!*\nToken has been saved to your environment.", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"❌ *Connection Failed:*\n`{e}`", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

@admin_only
async def list_repos_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches and lists GitHub repositories."""
    query = update.callback_query; await query.answer("Fetching repos...")
    gh = get_gh_client(context)
    if not gh:
        await query.edit_message_text("❌ *GitHub Not Connected*\nPlease connect your account first.", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]), parse_mode=ParseMode.MARKDOWN)
        return

    try:
        user = gh.get_user()
        repos = user.get_repos(sort="updated", direction="desc")
        kb = []
        for r in repos:
            icon = "🔒" if r.private else "🌐"
            kb.append([InlineKeyboardButton(f"{icon} {r.name}", callback_data=f"deploy:{r.full_name}")])
            if len(kb) >= 15: break
        
        kb.append([InlineKeyboardButton("🔄 Refresh List", callback_data="list_repos"), InlineKeyboardButton("🔙 Back", callback_data="back_main")])
        await query.edit_message_text(f"📂 *Select Repo to Deploy:*", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await query.edit_message_text(f"❌ *API Error:*\n`{e}`", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]), parse_mode=ParseMode.MARKDOWN)

@admin_only
async def deploy_repo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deployment flow with real-time feedback."""
    query = update.callback_query; await query.answer()
    repo_full_name = query.data.split(":")[1]
    app_name = repo_full_name.split("/")[-1].lower().replace(".", "-")
    
    status_msg = await query.edit_message_text(f"🚀 *Deploying:* `{repo_full_name}`\n\n⚙️ *Status:* Initializing...", parse_mode=ParseMode.MARKDOWN)
    
    gh = get_gh_client(context); repo = gh.get_repo(repo_full_name)
    token = context.user_data.get("github_token") or os.getenv("GITHUB_TOKEN")
    target_dir = APPS_DIR / app_name
    clone_url = f"https://{token}@github.com/{repo_full_name}.git"
    
    try:
        # Step 1: Git Operations
        await status_msg.edit_text(f"🚀 *Deploying:* `{repo_full_name}`\n\n⚙️ *Status:* 📥 Fetching source code...", parse_mode=ParseMode.MARKDOWN)
        if target_dir.exists():
            out, err, code = run_cmd("git pull", cwd=str(target_dir))
        else:
            out, err, code = run_cmd(f"git clone {clone_url} {str(target_dir)}")
        if code != 0: raise Exception(f"Git Error: {err or out}")

        # Step 2: Build & Dependencies
        await status_msg.edit_text(f"🚀 *Deploying:* `{repo_full_name}`\n\n⚙️ *Status:* 🛠 Building dependencies...", parse_mode=ParseMode.MARKDOWN)
        profile = detect_build_profile(target_dir)
        if profile["type"] == "nodejs":
            out, err, code = run_cmd("npm install --production", cwd=str(target_dir))
        elif profile["type"] == "python":
            venv = target_dir / "venv"
            if not venv.exists(): run_cmd(f"python3 -m venv {str(venv)}", cwd=str(target_dir))
            out, err, code = run_cmd(f"{venv}/bin/pip install -r requirements.txt", cwd=str(target_dir))
        if code != 0: raise Exception(f"Build Error: {err or out}")

        # Step 3: Webhook Automation
        await status_msg.edit_text(f"🚀 *Deploying:* `{repo_full_name}`\n\n⚙️ *Status:* 🔗 Configuring Webhooks...", parse_mode=ParseMode.MARKDOWN)
        webhook_url = f"http://{HOST_URL}:{WEBHOOK_PORT}/webhook/{app_name}"
        try:
            repo.create_hook("web", {"url": webhook_url, "content_type": "json", "secret": WEBHOOK_SECRET}, ["push"], active=True)
        except GithubException as ge:
            if "already exists" not in str(ge): raise ge
            
        # Step 4: PM2 Activation
        await status_msg.edit_text(f"🚀 *Deploying:* `{repo_full_name}`\n\n⚙️ *Status:* ⚡ Activating via PM2...", parse_mode=ParseMode.MARKDOWN)
        cmd = profile["cmd"]
        if not cmd: raise Exception("Buildpack error: Start command not found.")
        if profile["type"] == "python" and cmd.startswith("python3"): 
            cmd = f"{target_dir}/venv/bin/python " + cmd[8:]
        
        run_cmd(f"pm2 delete {app_name}")
        out, err, code = run_cmd(f"pm2 start \"{cmd}\" --name \"{app_name}\" --cwd \"{target_dir}\"")
        run_cmd("pm2 save")
        if code != 0: raise Exception(f"PM2 Error: {err or out}")

        # Final Verification
        await asyncio.sleep(2)
        app_status = get_pm2_app_status(app_name)
        if app_status and app_status['pm2_env']['status'] == 'online':
            await status_msg.edit_text(f"✅ *App Deployed & Online!*\n\n📦 *App:* `{app_name}`\n⚡ *Type:* `{profile['type'].upper()}`\n⚙️ *Start:* `{profile['cmd']}`\n\nAuto-deploy is active for every push!", 
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Manage Apps", callback_data="manage_apps")]]), parse_mode=ParseMode.MARKDOWN)
        else:
            # Automatic Log Dump on Failure
            res = subprocess.run(["pm2", "logs", app_name, "--lines", "20", "--nostream"], capture_output=True, text=True)
            logs = html.escape((res.stdout + res.stderr)[-3500:])
            await status_msg.edit_text(f"⚠️ *App Crash Detected*\nThe app started but failed quickly.\n\n*Logs:* \n<pre>{logs or 'No logs available.'}</pre>", 
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Restart", callback_data=f"app_act:restart:{app_name}"), InlineKeyboardButton("🔙 Menu", callback_data="back_main")]]), parse_mode=ParseMode.HTML)

    except Exception as e:
        await status_msg.edit_text(f"❌ *Deployment Failed*\n\n`{str(e)[:500]}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_main")]]), parse_mode=ParseMode.MARKDOWN)

@admin_only
async def manage_apps_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists PM2 managed apps."""
    query = update.callback_query; await query.answer()
    apps = get_pm2_apps()
    
    if not apps:
        await query.edit_message_text("📦 *No Active Apps*\nYou haven't deployed anything yet.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]), parse_mode=ParseMode.MARKDOWN)
        return

    kb = [[InlineKeyboardButton(f"{'🟢' if a['pm2_env']['status']=='online' else '🔴'} {a['name']}", callback_data=f"app_info:{a['name']}")] for a in apps]
    kb.append([InlineKeyboardButton("🔄 Refresh Status", callback_data="manage_apps"), InlineKeyboardButton("🔙 Main Menu", callback_data="back_main")])
    await query.edit_message_text("📦 *Managed Applications:*", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

@admin_only
async def app_info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detailed app view."""
    query = update.callback_query; await query.answer(); name = query.data.split(":")[1]
    app = get_pm2_app_status(name)
    if not app: return
    
    status = app['pm2_env']['status']
    mem = app['monit']['memory'] / (1024 * 1024)
    cpu = app['monit']['cpu']
    uptime = app['pm2_env'].get('pm_uptime', 0)
    restarts = app['pm2_env'].get('restart_time', 0)
    
    text = (f"⚙️ *App:* `{name}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Status: `{status.upper()}`\n"
            f"CPU Usage: `{cpu}%`\n"
            f"Memory: `{mem:.1f} MB`\n"
            f"Restarts: `{restarts}`\n\n"
            f"Manage this process:")
    
    kb = [
        [InlineKeyboardButton("🔄 Restart", callback_data=f"app_act:restart:{name}"),
         InlineKeyboardButton("⏹ Stop" if status == 'online' else "▶️ Start", callback_data=f"app_act:toggle:{name}")],
        [InlineKeyboardButton("📜 View Logs", callback_data=f"app_act:logs:{name}"),
         InlineKeyboardButton("🗑 Delete", callback_data=f"app_act:delete_confirm:{name}")],
        [InlineKeyboardButton("🔙 Back to List", callback_data="manage_apps")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

@admin_only
async def app_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Executes actions like restart, toggle, delete, logs."""
    query = update.callback_query; await query.answer()
    parts = query.data.split(":")
    action = parts[1]
    name = parts[2]
    
    if action == "restart":
        subprocess.run(["pm2", "restart", name])
        await query.answer(f"✅ {name} restarted")
    elif action == "toggle":
        app = get_pm2_app_status(name)
        if app:
            cmd = "stop" if app['pm2_env']['status'] == "online" else "start"
            subprocess.run(["pm2", cmd, name])
            await query.answer(f"✅ {name} {cmd}ed")
    elif action == "delete_confirm":
        kb = [[InlineKeyboardButton("⚠️ Yes, Delete", callback_data=f"app_act:delete_final:{name}")], [InlineKeyboardButton("❌ Cancel", callback_data=f"app_info:{name}")]]
        await query.edit_message_text(f"🗑 *Are you sure?*\nDeleting `{name}` will stop the process and remove it from PM2.", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
        return
    elif action == "delete_final":
        subprocess.run(["pm2", "delete", name])
        subprocess.run(["pm2", "save"])
        await query.answer(f"🗑 {name} deleted")
        return await manage_apps_handler(update, context)
    elif action == "logs":
        res = subprocess.run(["pm2", "logs", name, "--lines", "40", "--nostream"], capture_output=True, text=True)
        logs = html.escape((res.stdout + res.stderr)[-3800:])
        await query.edit_message_text(f"📜 *Recent Logs for* `{name}`:\n\n<pre>{logs or 'No logs available.'}</pre>", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"app_info:{name}")]]) , parse_mode=ParseMode.HTML)
        return

    # Auto-refresh app info after action
    query.data = f"app_info:{name}"; await app_info_handler(update, context)

@admin_only
async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """System telemetry dashboard."""
    query = update.callback_query; await query.answer()
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    load = os.getloadavg()
    
    text = (f"📊 *Server Telemetry*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💻 *CPU:* `{cpu}%`\n"
            f"🧠 *RAM:* `{mem.percent}%` (`{mem.used//1048576}/{mem.total//1048576} MB`)\n"
            f"💽 *Disk:* `{disk.percent}%` (`{disk.free//1073741824} GB Free`)\n"
            f"⏳ *Load:* `{load[0]}, {load[1]}, {load[2]}`\n"
            f"🕒 *Uptime:* `{psutil.boot_time()}`")
            
    kb = [[InlineKeyboardButton("🔄 Refresh Stats", callback_data="stats")], [InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

@admin_only
async def advanced_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Settings and advanced options."""
    query = update.callback_query; await query.answer()
    kb = [
        [InlineKeyboardButton("📜 Full PM2 List", callback_data="pm2_raw_list")],
        [InlineKeyboardButton("🧹 Clean PM2 Logs", callback_data="clean_pm2_logs")],
        [InlineKeyboardButton("🔙 Back to Main", callback_data="back_main")]
    ]
    await query.edit_message_text("⚙️ *Advanced Settings & Utilities:*", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

@admin_only
async def raw_pm2_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Raw PM2 status text."""
    query = update.callback_query; await query.answer()
    res = subprocess.run(["pm2", "status"], capture_output=True, text=True)
    await query.edit_message_text(f"📋 *Raw PM2 Status:* \n<pre>{html.escape(res.stdout)}</pre>", 
                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="advanced_menu")]]), parse_mode=ParseMode.HTML)

@admin_only
async def clean_logs_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Flushes PM2 logs."""
    query = update.callback_query; await query.answer()
    subprocess.run(["pm2", "flush"])
    await query.edit_message_text("✅ *PM2 Logs Flushed Successfully!*", 
                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="advanced_menu")]]), parse_mode=ParseMode.MARKDOWN)

# --- Main Entry ---

def main():
    if not BOT_TOKEN: return
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    gh_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(connect_gh_start, pattern="^connect_gh$")],
        states={WAITING_GITHUB_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, token_received)]},
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )
    
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(gh_conv)
    
    # Unified Pattern Routing
    routing = [
        ("^back_main$", start_handler), ("^list_repos$", list_repos_handler), ("^deploy:", deploy_repo_handler), 
        ("^manage_apps$", manage_apps_handler), ("^app_info:", app_info_handler), ("^app_act:", app_action_handler), 
        ("^stats$", stats_handler), ("^advanced_menu$", advanced_menu_handler), ("^pm2_raw_list$", raw_pm2_handler), 
        ("^clean_pm2_logs$", clean_logs_handler)
    ]
    for pattern, handler in routing: app.add_handler(CallbackQueryHandler(handler, pattern=pattern))
    
    print(f"[*] TeleVPS Pro is running. Admin: {ADMIN_ID}")
    app.run_polling()

if __name__ == "__main__": main()
