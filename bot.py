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
                await update.message.reply_text("⛔ *Unauthorized Access*\nThis bot is private.", parse_mode=ParseMode.MARKDOWN)
            logger.warning(f"Rejected unauthorized access from User ID: {user_id}")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# ------------------------------------------------------------------------------
# HELPERS: GITHUB & BUILD DETECTION (RECURSIVE)
# ------------------------------------------------------------------------------
def get_gh_client(context):
    token = context.user_data.get("github_token") or os.getenv("GITHUB_TOKEN")
    if not token or len(token) < 10:
        return None
    return Github(token)

def detect_build_profile(repo_path):
    """
    Strictly detects the app root folder following these safety rules:
    1. Priority: Procfile > manage.py > package.json > main.py > bot.py.
    2. Exclusion: Ignores system/dependency folders like .git, node_modules, venv, etc.
    3. Depth: Prefers files closest to the root directory.
    """
    root = Path(repo_path)
    priority_order = ["Procfile", "manage.py", "package.json", "main.py", "bot.py", "app.py", "requirements.txt"]
    exclude_dirs = {".git", "node_modules", "venv", "env", "__pycache__", "dist", "build", ".next", ".cache"}
    
    best_match = None # (depth, priority_index, directory_path, filename)

    # Walk the directory tree
    for dirpath, dirnames, filenames in os.walk(root):
        # Rule 2: Prune junk folders to prevent searching inside them
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        
        # Calculate current depth relative to repo root
        current_dir = Path(dirpath)
        depth = len(current_dir.relative_to(root).parts)

        # Optimization: If we already found a match at a shallower depth, 
        # and we are now looking deeper, we can stop because of Rule 3.
        if best_match and depth > best_match[0]:
            break

        for fname in filenames:
            if fname in priority_order:
                p_idx = priority_order.index(fname)
                
                # Rule 1 & 3 logic:
                # If this is the first match, or it's at the same depth but has higher priority
                if best_match is None or p_idx < best_match[1]:
                    best_match = (depth, p_idx, current_dir, fname)
                    
                    # Rule 1 Special: If we find a Procfile at this depth, it's the absolute winner for this level.
                    if fname == "Procfile":
                        break
        
        # If we found a Procfile at this level, we are strictly done according to Rule 1.
        if best_match and best_match[3] == "Procfile":
            break

    # Determine final app root and build profile
    found_root = best_match[2] if best_match else root
    p = found_root
    profile = {"type": "unknown", "cmd": "", "app_root": str(found_root)}
    
    # 1. Procfile check
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
    elif any((p / f).exists() for f in ["manage.py", "main.py", "app.py", "bot.py", "requirements.txt"]):
        profile["type"] = "python"
        if not profile["cmd"]:
            if (p / "manage.py").exists(): 
                profile["cmd"] = "python3 manage.py runserver 0.0.0.0:8000"
            elif (p / "bot.py").exists(): 
                profile["cmd"] = "python3 bot.py"
            elif (p / "main.py").exists(): 
                profile["cmd"] = "python3 main.py"
            elif (p / "app.py").exists(): 
                profile["cmd"] = "python3 app.py"
            else:
                # If only requirements.txt exists, try to find ANY .py file
                py_files = list(p.glob("*.py"))
                if py_files:
                    profile["cmd"] = f"python3 {py_files[0].name}"
                else:
                    profile["cmd"] = "python3 main.py" # Last resort
            
    return profile

def run_cmd(cmd, cwd=None):
    """Executes a shell command and returns output + error."""
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd, timeout=300)
        return res.stdout, res.stderr, res.returncode
    except Exception as e:
        return "", str(e), 1

# ------------------------------------------------------------------------------
# CORE HANDLERS
# ------------------------------------------------------------------------------

@admin_only
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main dashboard menu."""
    token = context.user_data.get("github_token") or os.getenv("GITHUB_TOKEN")
    status = "🟢 Connected" if (token and len(token) > 10) else "🔴 Disconnected"
    
    kb = [
        [InlineKeyboardButton("📦 My Repositories", callback_data="list_repos")],
        [InlineKeyboardButton("🔗 Connect GitHub (PAT)", callback_data="connect_gh")],
        [InlineKeyboardButton("🚀 Manage Apps", callback_data="manage_apps")],
        [InlineKeyboardButton("📊 System Stats", callback_data="stats")]
    ]
    
    text = (
        f"⚡ *TeleVPS Pro Dashboard*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *Admin:* `{ADMIN_ID}`\n"
        f"🔗 *GitHub:* {status}\n"
        f"🌐 *Host:* `{HOST_URL}`\n\n"
        f"What would you like to do today?"
    )
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

@admin_only
async def connect_gh_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiates GitHub connection flow."""
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "🔑 *GitHub Integration*\n\nPlease send your GitHub Personal Access Token (classic).\n\n"
        "*Required Scopes:*\n• `repo` (Full control)\n• `admin:repo_hook` (Manage webhooks)"
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
        await update.message.reply_text(f"✅ *Connected as {user}!*\nToken saved.", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"❌ *Connection Failed:*\n`{e}`")
        return ConversationHandler.END

@admin_only
async def list_repos_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches and lists GitHub repositories."""
    query = update.callback_query; await query.answer("Fetching repos...")
    gh = get_gh_client(context)
    if not gh:
        await query.edit_message_text("❌ *GitHub Not Connected*", 
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
        kb.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="back_main")])
        await query.edit_message_text(f"📂 *Select Repo to Deploy:*", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await query.edit_message_text(f"❌ *API Error:*\n`{e}`", parse_mode=ParseMode.MARKDOWN)

@admin_only
async def deploy_repo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deployment with smart recursive subfolder detection."""
    query = update.callback_query; await query.answer()
    repo_full_name = query.data.split(":")[1]
    app_name = repo_full_name.split("/")[-1].lower().replace(".", "-")
    
    status_msg = await query.edit_message_text(f"🚀 *Deploying:* `{repo_full_name}`\n\n⚙️ *Status:* Preparing...", parse_mode=ParseMode.MARKDOWN)
    
    gh = get_gh_client(context); repo = gh.get_repo(repo_full_name)
    token = context.user_data.get("github_token") or os.getenv("GITHUB_TOKEN")
    repo_dir = APPS_DIR / app_name
    clone_url = f"https://{token}@github.com/{repo_full_name}.git"
    
    try:
        # Step 1: Git Clone/Pull
        await status_msg.edit_text(f"🚀 *Deploying:* `{repo_full_name}`\n\n⚙️ *Status:* 📥 Cloning/Pulling code...", parse_mode=ParseMode.MARKDOWN)
        if repo_dir.exists():
            out, err, code = run_cmd("git pull", cwd=str(repo_dir))
        else:
            out, err, code = run_cmd(f"git clone {clone_url} {str(repo_dir)}")
        if code != 0: raise Exception(f"Git failed: {err or out}")

        # Step 2: Recursive Search for App Root
        await status_msg.edit_text(f"🚀 *Deploying:* `{repo_full_name}`\n\n⚙️ *Status:* 🔍 Scanning for entry file...", parse_mode=ParseMode.MARKDOWN)
        profile = detect_build_profile(repo_dir)
        app_root = Path(profile["app_root"])
        
        # Step 3: Install Dependencies
        await status_msg.edit_text(f"🚀 *Deploying:* `{repo_full_name}`\n\n⚙️ *Status:* 🛠 Installing dependencies in `{app_root.relative_to(repo_dir)}`...", parse_mode=ParseMode.MARKDOWN)
        if profile["type"] == "nodejs":
            out, err, code = run_cmd("npm install --production", cwd=str(app_root))
        elif profile["type"] == "python":
            venv = app_root / "venv"
            if not venv.exists(): run_cmd(f"python3 -m venv {str(venv)}", cwd=str(app_root))
            out, err, code = run_cmd(f"{venv}/bin/pip install -r requirements.txt", cwd=str(app_root))
        if code != 0: raise Exception(f"Install failed: {err or out}")

        # Step 4: Webhook
        await status_msg.edit_text(f"🚀 *Deploying:* `{repo_full_name}`\n\n⚙️ *Status:* 🔗 Configuring Webhook...", parse_mode=ParseMode.MARKDOWN)
        webhook_url = f"http://{HOST_URL}:{WEBHOOK_PORT}/webhook/{app_name}"
        try:
            repo.create_hook("web", {"url": webhook_url, "content_type": "json", "secret": WEBHOOK_SECRET}, ["push"], active=True)
        except GithubException as ge:
            if "already exists" not in str(ge): raise ge
            
        # Step 5: PM2 Start with correct CWD
        await status_msg.edit_text(f"🚀 *Deploying:* `{repo_full_name}`\n\n⚙️ *Status:* ⚡ Starting PM2...", parse_mode=ParseMode.MARKDOWN)
        cmd = profile["cmd"]
        if profile["type"] == "python" and cmd.startswith("python3"): 
            cmd = f"{app_root}/venv/bin/python " + cmd[8:]
        
        run_cmd(f"pm2 delete {app_name}")
        out, err, code = run_cmd(f"pm2 start \"{cmd}\" --name \"{app_name}\" --cwd \"{app_root}\"")
        run_cmd("pm2 save")
        if code != 0: raise Exception(f"PM2 failed: {err or out}")

        await status_msg.edit_text(f"✅ *Deployment Successful!*\n\n📦 *App:* `{app_name}`\n📁 *Path:* `{app_root.relative_to(repo_dir)}/`\n⚙️ *Cmd:* `{profile['cmd']}`", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Manage Apps", callback_data="manage_apps")]]), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await status_msg.edit_text(f"❌ *Failed:* `{str(e)[:500]}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu", callback_data="back_main")]]), parse_mode=ParseMode.MARKDOWN)

@admin_only
async def manage_apps_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists PM2 managed apps."""
    query = update.callback_query; await query.answer()
    res = subprocess.run(["pm2", "jlist"], capture_output=True, text=True)
    try:
        apps = [a for a in json.loads(res.stdout) if a['name'] not in ["televps-bot", "televps-webhook"]]
    except: apps = []
    
    if not apps:
        await query.edit_message_text("📦 *No apps found.*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]), parse_mode=ParseMode.MARKDOWN)
        return
    kb = [[InlineKeyboardButton(f"{'🟢' if a['pm2_env']['status']=='online' else '🔴'} {a['name']}", callback_data=f"app_info:{a['name']}")] for a in apps]
    kb.append([InlineKeyboardButton("🔙 Main Menu", callback_data="back_main")])
    await query.edit_message_text("📦 *Managed Applications:*", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

@admin_only
async def app_info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detailed app view."""
    query = update.callback_query; await query.answer(); name = query.data.split(":")[1]
    res = subprocess.run(["pm2", "jlist"], capture_output=True, text=True)
    app = next((a for a in json.loads(res.stdout) if a['name'] == name), None)
    if not app: return
    
    status = app['pm2_env']['status']
    mem = app['monit']['memory'] / (1024 * 1024)
    cpu = app['monit']['cpu']
    
    text = (f"⚙️ *App:* `{name}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Status: `{status.upper()}`\n"
            f"CPU: `{cpu}%` | MEM: `{mem:.1f} MB`")
    kb = [
        [InlineKeyboardButton("🔄 Restart", callback_data=f"app_act:restart:{name}"),
         InlineKeyboardButton("⏹ Stop/Start", callback_data=f"app_act:toggle:{name}")],
        [InlineKeyboardButton("📜 Logs", callback_data=f"app_act:logs:{name}"),
         InlineKeyboardButton("🗑 Delete", callback_data=f"app_act:delete:{name}")],
        [InlineKeyboardButton("🔙 Back", callback_data="manage_apps")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

@admin_only
async def app_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """App actions with improved feedback."""
    query = update.callback_query; await query.answer()
    parts = query.data.split(":")
    action = parts[1]
    name = parts[2]
    
    if action == "restart":
        await query.edit_message_text(f"⏳ *Restarting* `{name}`...", parse_mode=ParseMode.MARKDOWN)
        run_cmd(f"pm2 restart {name}")
        await asyncio.sleep(1.5)
    elif action == "toggle":
        res = subprocess.run(["pm2", "jlist"], capture_output=True, text=True)
        app = next((a for a in json.loads(res.stdout) if a['name'] == name), None)
        if app:
            cmd = "stop" if app['pm2_env']['status'] == 'online' else "start"
            await query.edit_message_text(f"⏳ *{cmd.capitalize()}ing* `{name}`...", parse_mode=ParseMode.MARKDOWN)
            run_cmd(f"pm2 {cmd} {name}")
            await asyncio.sleep(1.5)
    elif action == "delete": 
        await query.edit_message_text(f"🗑 *Deleting* `{name}`...", parse_mode=ParseMode.MARKDOWN)
        run_cmd(f"pm2 delete {name}")
        run_cmd("pm2 save")
        await asyncio.sleep(1)
        return await manage_apps_handler(update, context)
    elif action == "logs":
        res = subprocess.run(["pm2", "logs", name, "--lines", "30", "--nostream"], capture_output=True, text=True)
        logs = html.escape((res.stdout + res.stderr)[-3500:])
        await query.edit_message_text(f"📜 *Logs:* `{name}`\n<pre>{logs or 'No logs found.'}</pre>", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"app_info:{name}")]]) , parse_mode=ParseMode.HTML)
        return

    # Final refresh to show updated status
    query.data = f"app_info:{name}"
    await app_info_handler(update, context)

@admin_only
async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """System telemetry."""
    query = update.callback_query; await query.answer()
    cpu = psutil.cpu_percent(interval=0.5); mem = psutil.virtual_memory(); disk = psutil.disk_usage('/')
    text = (f"📊 *System Performance*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"CPU: `{cpu}%` | RAM: `{mem.percent}%` | Disk: `{disk.percent}%`")
    kb = [[InlineKeyboardButton("🔄 Refresh", callback_data="stats")], [InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

def main():
    if not BOT_TOKEN: return
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    gh_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(connect_gh_start, pattern="^connect_gh$")],
        states={WAITING_GITHUB_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, token_received)]},
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(gh_conv)
    routing = [("^back_main$", start_handler), ("^list_repos$", list_repos_handler), ("^deploy:", deploy_repo_handler), 
               ("^manage_apps$", manage_apps_handler), ("^app_info:", app_info_handler), ("^app_act:", app_action_handler), ("^stats$", stats_handler)]
    for pattern, handler in routing: app.add_handler(CallbackQueryHandler(handler, pattern=pattern))
    print("[*] TeleVPS Pro Booted.")
    app.run_polling()

if __name__ == "__main__": main()
