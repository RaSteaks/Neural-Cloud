#!/usr/bin/env python3
import os
import re
import json
from datetime import datetime, timedelta
import random
from typing import Dict, List, Any

# --- Load Configuration (with hot-reload) ---
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT_DIR, "config.json")

_config_cache = {}
_config_mtime = 0

def _load_config() -> dict:
    """Load configuration from config.json, auto-reload on file change."""
    global _config_cache, _config_mtime
    try:
        mtime = os.path.getmtime(CONFIG_PATH)
        if mtime != _config_mtime:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                _config_cache = json.load(f)
            _config_mtime = mtime
    except Exception:
        _config_cache = {}
    return _config_cache

def get_scan_paths() -> List[str]:
    """Get scan paths from config (hot-reloaded)."""
    config = _load_config()
    return [os.path.expanduser(p) for p in config.get("scan_paths", [])]

def get_core_mem_file() -> str:
    """Get core memory file path from config (hot-reloaded)."""
    config = _load_config()
    return os.path.expanduser(config.get("core_memory_file", ""))

def get_all_md_files() -> List[str]:
    md_files = []
    core_mem = get_core_mem_file()
    if core_mem and os.path.exists(core_mem):
        md_files.append(core_mem)
    for path in get_scan_paths():
        path = path.strip()
        if not path or not os.path.exists(path): continue
        for file in os.listdir(path):
            if file.endswith(".md"):
                md_files.append(os.path.abspath(os.path.join(path, file)))
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
    scan_paths = get_scan_paths()
    core_mem = get_core_mem_file()

    # Build group labels: 0 = Core, 1..N = scan paths (by folder name)
    group_labels = {0: "Core (MEMORY)"}
    for i, sp in enumerate(scan_paths):
        folder_name = os.path.basename(os.path.normpath(sp))
        group_labels[i + 1] = folder_name

    def _get_group(path: str) -> int:
        """Determine group index by matching scan path."""
        norm_path = os.path.normpath(path)
        if core_mem and os.path.normpath(core_mem) == norm_path:
            return 0
        for i, sp in enumerate(scan_paths):
            if norm_path.startswith(os.path.normpath(sp)):
                return i + 1
        return len(scan_paths)  # fallback group

    for path in all_files:
        name = os.path.basename(path).replace(".md", "").strip()
        file_map[name] = path
        group = _get_group(path)
        try:
            file_size = os.path.getsize(path)
        except Exception:
            file_size = 0
        nodes.append({"id": name, "group": group, "size": file_size})

    # Link patterns: [[wiki-link]], [text](file.md), [text](./file.md)
    wiki_pattern = re.compile(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]')
    md_link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+\.md)\)')
    # Build a case-insensitive lookup map for fuzzy matching
    name_lookup = {n.lower().strip(): n for n in file_map}
    seen_links = set()

    def _resolve(target_name):
        """Resolve a target name to a known node id."""
        t = target_name.strip().replace(".md", "")
        # Remove leading ./ or path prefix, keep only filename
        t = os.path.basename(t)
        return file_map.get(t) and t or name_lookup.get(t.lower().strip())

    for name, path in file_map.items():
        try:
            content = _read_text(path)

            # 1. Wiki-style [[links]]
            for target in wiki_pattern.findall(content):
                resolved = _resolve(target)
                if resolved and resolved != name:
                    key = (name, resolved)
                    if key not in seen_links:
                        seen_links.add(key)
                        links.append({"source": name, "target": resolved, "value": 1})

            # 2. Standard markdown [text](file.md) links
            for text, href in md_link_pattern.findall(content):
                resolved = _resolve(href)
                if resolved and resolved != name:
                    key = (name, resolved)
                    if key not in seen_links:
                        seen_links.add(key)
                        links.append({"source": name, "target": resolved, "value": 1})

        except Exception: continue

    # Fallback: if no links detected, connect core memory node to all others
    if not links:
        core_name = None
        for node in nodes:
            if node["group"] == 0:
                core_name = node["id"]
                break
        if core_name:
            for node in nodes:
                if node["id"] != core_name:
                    links.append({"source": core_name, "target": node["id"], "value": 0.5})
    return {"nodes": nodes, "links": links, "groups": group_labels}
