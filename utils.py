import os
import json
import logging
from pathlib import Path

def detect_build_profile(repo_path):
    """
    Strictly detects the app root folder following these safety rules:
    1. Priority: Procfile > manage.py > package.json > main.py > bot.py.
    2. Exclusion: Ignores system/dependency folders like .git, node_modules, venv, etc.
    3. Depth: Prefers files closest to the root directory.
    """
    root = Path(repo_path)
    # Priority 1: Procfile is the king.
    priority_order = ["Procfile", "manage.py", "package.json", "main.py", "bot.py", "app.py", "requirements.txt"]
    exclude_dirs = {".git", "node_modules", "venv", "env", "__pycache__", "dist", "build", ".next", ".cache", "target"}
    
    matches = {}

    for dirpath, dirnames, filenames in os.walk(root):
        # Rule 2: Prune junk folders
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        
        current_dir = Path(dirpath)
        depth = len(current_dir.relative_to(root).parts)

        for fname in filenames:
            if fname in priority_order:
                # Rule 3: Shallowest match
                if fname not in matches or depth < matches[fname][0]:
                    matches[fname] = (depth, current_dir)
        
        # Rule 1 Optimization
        if "Procfile" in matches and matches["Procfile"][0] == 0:
            break

    # Priority Order (Rule 1)
    best_match_dir = root
    selected_file = None
    
    for target in priority_order:
        if target in matches:
            best_match_dir = matches[target][1]
            selected_file = target
            break

    profile = {"type": "unknown", "cmd": "", "app_root": str(best_match_dir), "entry_file": selected_file}
    p = best_match_dir
    
    # 1. Procfile check
    if (p / "Procfile").exists():
        try:
            with open(p / "Procfile", "r") as f:
                for line in f:
                    if line.strip().startswith("web:"):
                        profile["cmd"] = line.replace("web:", "").strip()
                        break
        except: pass

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
                    profile["cmd"] = "python3 main.py"
            
    return profile
