#!/usr/bin/env python3
import os
import re
import json
from datetime import datetime, timedelta
import random
from typing import Dict, List, Any

# --- Load Configuration ---
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT_DIR, "config.json")

def _load_config() -> dict:
    """Load configuration from config.json"""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

_config = _load_config()

# Resolve paths from config (support ~ expansion)
SCAN_PATHS = [os.path.expanduser(p) for p in _config.get("scan_paths", [])]
CORE_MEM_FILE = os.path.expanduser(_config.get("core_memory_file", ""))

def get_all_md_files() -> List[str]:
    md_files = []
    if os.path.exists(CORE_MEM_FILE):
        md_files.append(CORE_MEM_FILE)
    for path in SCAN_PATHS:
        path = path.strip()
        if not path or not os.path.exists(path): continue
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith(".md"):
                    md_files.append(os.path.abspath(os.path.join(root, file)))
    return md_files

def get_yesterday_date_str() -> str:
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")

def sanitize_content(text: str) -> str:
    text = re.sub(r'ou_[a-f0-9]+', '[USER_ID]', text)
    text = re.sub(r'user_id="[^"]+"', 'user_id="[HIDDEN]"', text)
    # Redact any remaining local C:/Users/... patterns found in text
    text = re.sub(r'[a-zA-Z]:\\Users\\[^\s\\]+', '[LOCAL_PATH]', text)
    return text

def extract_memo_from_file(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        lines = content.strip().split("\n")
        core_points = [l.strip()[2:] if l.strip().startswith("- ") else l.strip() 
                       for l in lines if l.strip() and not l.strip().startswith("#") and len(l.strip()) > 5]
        if not core_points: return "「Record Empty」"
        selected = core_points[:3]
        return "\n".join([f"· {sanitize_content(p[:37]+'...') if len(p)>40 else sanitize_content(p)}" for p in selected]).strip()
    except Exception: return "「Load Failure」"

def build_memory_graph() -> Dict[str, Any]:
    nodes = []
    links = []
    file_map = {} 
    all_files = get_all_md_files()
    for path in all_files:
        name = os.path.basename(path).replace(".md", "").strip()
        file_map[name] = path
        # 1 for workspace, 2 for external/archive
        group = 1 if ".openclaw" in path.lower() else 2
        # File size in bytes for frontend node scaling
        try:
            file_size = os.path.getsize(path)
        except Exception:
            file_size = 0
        nodes.append({"id": name, "group": group, "size": file_size})

    link_pattern = re.compile(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]')
    for name, path in file_map.items():
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                matches = link_pattern.findall(content)
                for target in matches:
                    target = target.strip().replace(".md", "")
                    if target in file_map:
                        links.append({"source": name, "target": target, "value": 1})
        except Exception: continue
            
    if not links and "MEMORY" in file_map:
        for node in nodes:
            if node["id"] != "MEMORY":
                links.append({"source": "MEMORY", "target": node["id"], "value": 0.5})
    return {"nodes": nodes, "links": links}
