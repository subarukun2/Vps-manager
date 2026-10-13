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
WAITING_CONFIG_VAR = 2
CURRENT_CONFIG_APP = "current_app" # Used in context.user_data

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

from utils import detect_build_profile

async def get_pm2_app_status(name):
    """Helper to get status of a single PM2 app."""
    try:
        out, err, code = await run_async_cmd("pm2 jlist")
        apps = json.loads(out)
        return next((a for a in apps if a['name'] == name), None)
    except Exception as e:
        logger.error(f"Error getting PM2 status for {name}: {e}")
        return None

@admin_only
async def advanced_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    kb = [
        [InlineKeyboardButton("📋 Raw PM2 List", callback_data="pm2_raw_list")],
        [InlineKeyboardButton("🧹 Flush All Logs", callback_data="clean_pm2_logs")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
    ]
    await query.edit_message_text("🛠 *Advanced Management*\nDirect control over PM2 and system logs.", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

@admin_only
async def raw_pm2_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    out, err, code = await run_async_cmd("pm2 list")
    text = f"📋 *PM2 Process List:*\n<pre>{html.escape(out or 'No processes.')}</pre>"
    kb = [[InlineKeyboardButton("🔙 Back", callback_data="advanced_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

@admin_only
async def clean_logs_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer("Flushing logs...")
    await run_async_cmd("pm2 flush")
    await query.edit_message_text("✅ *All PM2 logs have been cleared.*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="advanced_menu")]]), parse_mode=ParseMode.MARKDOWN)

async def run_async_cmd(cmd, cwd=None):
    """Executes a shell command asynchronously and returns output + error."""
    try:
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )
        stdout, stderr = await process.communicate()
        return stdout.decode().strip(), stderr.decode().strip(), process.returncode
    except Exception as e:
        return "", str(e), 1

def run_cmd(cmd, cwd=None):
    """Legacy blocking wrapper (if needed for non-async parts)."""
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
        [InlineKeyboardButton("📊 System Stats", callback_data="stats")],
        [InlineKeyboardButton("🛠 Advanced Tools", callback_data="advanced_menu")]
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
            out, err, code = await run_async_cmd("git pull", cwd=str(repo_dir))
        else:
            out, err, code = await run_async_cmd(f"git clone {clone_url} {str(repo_dir)}")
        if code != 0: raise Exception(f"Git failed: {err or out}")

        # Step 2: Recursive Search for App Root
        await status_msg.edit_text(f"🚀 *Deploying:* `{repo_full_name}`\n\n⚙️ *Status:* 🔍 Scanning for entry file...", parse_mode=ParseMode.MARKDOWN)
        profile = detect_build_profile(repo_dir)
        app_root = Path(profile["app_root"])
        
        # Step 3: Install Dependencies
        await status_msg.edit_text(f"🚀 *Deploying:* `{repo_full_name}`\n\n⚙️ *Status:* 🛠 Installing dependencies in `{app_root.relative_to(repo_dir)}`...", parse_mode=ParseMode.MARKDOWN)
        if profile["type"] == "nodejs":
            out, err, code = await run_async_cmd("npm install --production", cwd=str(app_root))
        elif profile["type"] == "python":
            venv = app_root / "venv"
            if not venv.exists(): await run_async_cmd(f"python3 -m venv {str(venv)}", cwd=str(app_root))
            out, err, code = await run_async_cmd(f"{venv}/bin/pip install -r requirements.txt", cwd=str(app_root))
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
        
        await run_async_cmd(f"pm2 delete {app_name}")
        out, err, code = await run_async_cmd(f"pm2 start \"{cmd}\" --name \"{app_name}\" --cwd \"{app_root}\"")
        await run_async_cmd("pm2 save")
        
        if code != 0: raise Exception(f"PM2 failed: {err or out}")

        # Verification step: Wait 3 seconds and check if still online
        await asyncio.sleep(3)
        app_check = await get_pm2_app_status(app_name)
        if not app_check or app_check['pm2_env']['status'] != 'online':
            # It crashed! Fetch logs
            l_out, l_err, _ = await run_async_cmd(f"pm2 logs {app_name} --lines 15 --nostream")
            error_logs = html.escape((l_out + l_err)[-500:])
            raise Exception(f"App started but crashed immediately.\n\n*Logs:*\n<pre>{error_logs}</pre>")

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
    
    app = await get_pm2_app_status(name)
    if not app:
        await query.edit_message_text(f"❌ *App `{name}` not found in PM2.*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="manage_apps")]]), parse_mode=ParseMode.MARKDOWN)
        return
    
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
        [InlineKeyboardButton("🔑 Config Vars", callback_data=f"app_vars:{name}")],
        [InlineKeyboardButton("📜 Logs", callback_data=f"app_act:logs:{name}"),
         InlineKeyboardButton("🗑 Delete", callback_data=f"app_act:delete_confirm:{name}")],
        [InlineKeyboardButton("🔙 Back", callback_data="manage_apps")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

@admin_only
async def app_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """App actions with async non-blocking feedback."""
    query = update.callback_query; await query.answer()
    parts = query.data.split(":")
    action = parts[1]
    name = parts[2]
    
    if action == "restart":
        msg = await query.edit_message_text(f"⏳ *Restarting* `{name}`...", parse_mode=ParseMode.MARKDOWN)
        await run_async_cmd(f"pm2 restart {name}")
        await asyncio.sleep(2) # Give PM2 time to settle
    elif action == "toggle":
        app = await get_pm2_app_status(name)
        if app:
            current_status = app['pm2_env']['status']
            cmd = "stop" if current_status == 'online' else "start"
            msg = await query.edit_message_text(f"⏳ *{cmd.capitalize()}ing* `{name}`...", parse_mode=ParseMode.MARKDOWN)
            await run_async_cmd(f"pm2 {cmd} {name}")
            await asyncio.sleep(2)
    elif action == "delete_confirm":
        kb = [[InlineKeyboardButton("⚠️ Yes, Delete", callback_data=f"app_act:delete_final:{name}")], [InlineKeyboardButton("❌ Cancel", callback_data=f"app_info:{name}")]]
        await query.edit_message_text(f"🗑 *Are you sure?*\nDeleting `{name}` will stop the process and remove it from PM2.", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
        return
    elif action == "delete_final":
        await query.edit_message_text(f"🗑 *Deleting* `{name}`...", parse_mode=ParseMode.MARKDOWN)
        await run_async_cmd(f"pm2 delete {name}")
        await run_async_cmd("pm2 save")
        await asyncio.sleep(1)
        return await manage_apps_handler(update, context)
    elif action == "logs":
        await query.edit_message_text(f"📜 *Fetching logs for* `{name}`...", parse_mode=ParseMode.MARKDOWN)
        out, err, code = await run_async_cmd(f"pm2 logs {name} --lines 40 --nostream")
        logs = html.escape((out + err)[-3800:])
        await query.edit_message_text(f"📜 *Logs for* `{name}`:\n<pre>{logs or 'No logs found.'}</pre>", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"app_info:{name}")]]) , parse_mode=ParseMode.HTML)
        return

    # Final refresh to show updated status
    query.data = f"app_info:{name}"
    await app_info_handler(update, context)

@admin_only
async def app_vars_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists environment variables for an app."""
    query = update.callback_query; await query.answer()
    name = query.data.split(":")[1]
    env_file = APPS_DIR / name / ".env"
    
    vars_dict = {}
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.strip().split("=", 1)
                    vars_dict[k] = v

    text = f"🔑 *Config Vars:* `{name}`\n\n"
    if vars_dict:
        for k, v in vars_dict.items():
            text += f"`{k}` = `{v}`\n"
    else:
        text += "_No variables set yet._"
    
    text += "\n\n💡 *Note:* Adding/Deleting a variable will automatically restart the app."

    kb = [
        [InlineKeyboardButton("➕ Add Variable", callback_data=f"add_var:{name}")],
        [InlineKeyboardButton("🔍 Scan config.py", callback_data=f"import_cfg:{name}")],
        [InlineKeyboardButton("🔙 Back to App", callback_data=f"app_info:{name}")]
    ]
    
    # Add delete buttons for each var
    for k in vars_dict:
        kb.insert(-2, [InlineKeyboardButton(f"🗑 Delete {k}", callback_data=f"del_var:{name}:{k}")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

@admin_only
async def import_config_py_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Scans config.py for variables and imports them into .env."""
    query = update.callback_query; await query.answer()
    name = query.data.split(":")[1]
    app_dir = APPS_DIR / name
    cfg_file = app_dir / "config.py"
    env_file = app_dir / ".env"
    
    if not cfg_file.exists():
        await query.answer("❌ config.py not found in app root.", show_alert=True)
        return

    import re
    # Regex to find: CONSTANT = "value" or CONSTANT = 123
    pattern = re.compile(r'^([A-Z_]+)\s*=\s*[\'"]?([^\'"]+)[\'"]?', re.MULTILINE)
    
    found_vars = {}
    with open(cfg_file, "r") as f:
        content = f.read()
        matches = pattern.findall(content)
        for k, v in matches:
            if k not in ["LOGGER", "ENV"]: # Exclude some common non-config constants
                found_vars[k] = v

    if not found_vars:
        await query.answer("ℹ️ No variables found in config.py to import.", show_alert=True)
        return

    # Merge into .env
    existing_vars = {}
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    existing_vars[k] = v
    
    existing_vars.update(found_vars)
    
    with open(env_file, "w") as f:
        for k, v in existing_vars.items():
            f.write(f"{k}={v}\n")
            
    await query.edit_message_text(f"✅ *Imported {len(found_vars)} vars* from `config.py`!\n🚀 *Restarting* `{name}`...", parse_mode=ParseMode.MARKDOWN)
    await run_async_cmd(f"pm2 restart {name}")
    await asyncio.sleep(2)
    
    query.data = f"app_vars:{name}"
    await app_vars_handler(update, context)

@admin_only
async def add_var_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompts for new config var."""
    query = update.callback_query; await query.answer()
    name = query.data.split(":")[1]
    context.user_data[CURRENT_CONFIG_APP] = name
    await query.edit_message_text(f"➕ *Add Config Var for* `{name}`\n\nPlease send the variable in `KEY=VALUE` format.\n\n_Example:_ `API_ID=1234567`", parse_mode=ParseMode.MARKDOWN)
    return WAITING_CONFIG_VAR

async def var_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves the new config var and restarts the app."""
    text = update.message.text.strip()
    name = context.user_data.get(CURRENT_CONFIG_APP)
    
    if "=" not in text or not name:
        await update.message.reply_text("❌ *Invalid Format*\nPlease use `KEY=VALUE` format or type /cancel.")
        return WAITING_CONFIG_VAR
        
    key, val = text.split("=", 1)
    env_file = APPS_DIR / name / ".env"
    
    # Read existing
    lines = []
    found = False
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                if line.startswith(f"{key}="):
                    lines.append(f"{key}={val}\n")
                    found = True
                else:
                    lines.append(line)
    
    if not found:
        lines.append(f"{key}={val}\n")
        
    # Write back
    with open(env_file, "w") as f:
        f.writelines(lines)
        
    await update.message.reply_text(f"✅ *Saved:* `{key}`\n🚀 *Restarting* `{name}`...", parse_mode=ParseMode.MARKDOWN)
    await run_async_cmd(f"pm2 restart {name}")
    
    # Return to app menu
    context.user_data.pop(CURRENT_CONFIG_APP, None)
    return ConversationHandler.END

@admin_only
async def delete_var_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deletes a config var and restarts the app."""
    query = update.callback_query; await query.answer()
    _, name, key = query.data.split(":")
    env_file = APPS_DIR / name / ".env"
    
    if env_file.exists():
        lines = []
        with open(env_file, "r") as f:
            for line in f:
                if not line.startswith(f"{key}="):
                    lines.append(line)
        
        with open(env_file, "w") as f:
            f.writelines(lines)
            
        await query.edit_message_text(f"🗑 *Deleted:* `{key}`\n🚀 *Restarting* `{name}`...", parse_mode=ParseMode.MARKDOWN)
        await run_async_cmd(f"pm2 restart {name}")
        await asyncio.sleep(1.5)
        
    query.data = f"app_vars:{name}"
    await app_vars_handler(update, context)

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
        entry_points=[
            CallbackQueryHandler(connect_gh_start, pattern="^connect_gh$"),
            CallbackQueryHandler(add_var_start, pattern="^add_var:")
        ],
        states={
            WAITING_GITHUB_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, token_received)],
            WAITING_CONFIG_VAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, var_received)]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )
    
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(gh_conv)
    
    # Unified Pattern Routing
    routing = [
        ("^back_main$", start_handler), ("^list_repos$", list_repos_handler), ("^deploy:", deploy_repo_handler), 
        ("^manage_apps$", manage_apps_handler), ("^app_info:", app_info_handler), ("^app_act:", app_action_handler), 
        ("^stats$", stats_handler), ("^advanced_menu$", advanced_menu_handler), ("^pm2_raw_list$", raw_pm2_handler), 
        ("^clean_pm2_logs$", clean_logs_handler), ("^app_vars:", app_vars_handler), ("^del_var:", delete_var_handler)
    ]
    for pattern, handler in routing: app.add_handler(CallbackQueryHandler(handler, pattern=pattern))
    print("[*] TeleVPS Pro Booted.")
    app.run_polling()

if __name__ == "__main__": main()
