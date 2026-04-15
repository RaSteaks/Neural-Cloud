#!/usr/bin/env python3
import os
import re
import json
import urllib.parse
import mimetypes
from flask import Flask, jsonify, send_from_directory, request, make_response, Response

# --- Project Configuration ---
app = Flask(__name__, static_folder="frontend", static_url_path="/static")
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")

@app.route("/")
def index():
    """Neural Cloud Main Entrance"""
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/favicon.ico")
def favicon():
    return send_from_directory(FRONTEND_DIR, "favicon.ico", mimetype="image/x-icon")

@app.route("/api/graph")
def api_graph():
    """Neural Synapses Topology"""
    from backend.memo_utils import build_memory_graph
    try:
        return jsonify(build_memory_graph())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/content")
def api_content():
    """Intelligence Fragment Preview"""
    node_id = request.args.get("id")
    if not node_id: return jsonify({"error": "No ID"}), 400
    
    decoded_id = urllib.parse.unquote(node_id).strip()
    from backend.memo_utils import get_all_md_files
    files = get_all_md_files()
    
    target = next((p for p in files if os.path.basename(p).replace(".md", "").strip() in [decoded_id, decoded_id.replace(" ",""), node_id]), None)
    if not target: return jsonify({"error": f"NodeNotFound: {decoded_id}"}), 404
    
    try:
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Image Replacement Proxy
        def img_replacer(match):
            try:
                alt, img_p = match.group(1), match.group(2)
                img_p_u = urllib.parse.unquote(img_p)
                full_p = img_p_u if ":" in img_p_u or img_p_u.startswith(("/", "\\")) else os.path.abspath(os.path.join(os.path.dirname(target), img_p_u))
                return f'![{alt}](/api/image?path={urllib.parse.quote(full_p)})'
            except: return match.group(0)
            
        processed_content = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', img_replacer, content)
        
        # PDF Detection
        pdf_link = None
        bn = os.path.basename(target).replace(".md", "")
        for p_pdf in [os.path.join(os.path.dirname(target), bn+".pdf"), os.path.join(os.path.dirname(os.path.dirname(target)), bn+".pdf")]:
            if os.path.exists(p_pdf):
                pdf_link = f"/api/pdf?path={urllib.parse.quote(p_pdf)}"
                break
                
        return jsonify({"id": decoded_id, "content": processed_content, "pdf_link": pdf_link})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/image")
def api_image():
    """Media Proxy Hub"""
    p = request.args.get("path")
    if not p: return "400", 400
    p = os.path.normpath(urllib.parse.unquote(p))
    if os.path.exists(p):
        mime, _ = mimetypes.guess_type(p)
        with open(p, "rb") as f:
            return Response(f.read(), mimetype=mime or "application/octet-stream")
    return "404", 404

@app.route("/api/pdf")
def api_pdf():
    """Document Streaming"""
    p = request.args.get("path")
    if not p: return "400", 400
    p = os.path.normpath(urllib.parse.unquote(p))
    if os.path.exists(p):
        return send_from_directory(os.path.dirname(p), os.path.basename(p))
    return "404", 404

@app.route("/api/config", methods=["GET"])
def get_config():
    """Read config.json"""
    config_path = os.path.join(ROOT_DIR, "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/config", methods=["POST"])
def save_config():
    """Write config.json"""
    config_path = os.path.join(ROOT_DIR, "config.json")
    try:
        data = request.get_json()
        if not data or "scan_paths" not in data:
            return jsonify({"error": "Invalid config: scan_paths required"}), 400
        # Validate: scan_paths must be a list of strings
        if not isinstance(data["scan_paths"], list):
            return jsonify({"error": "scan_paths must be a list"}), 400
        config = {
            "scan_paths": [str(p).strip() for p in data["scan_paths"] if str(p).strip()],
            "core_memory_file": str(data.get("core_memory_file", "")).strip()
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Check config.json on startup, create default if missing
    config_path = os.path.join(ROOT_DIR, "config.json")
    if not os.path.exists(config_path):
        default_config = {
            "scan_paths": [
                os.path.join(os.path.expanduser("~"), ".openclaw", "workspace", "memory")
            ],
            "core_memory_file": os.path.join(os.path.expanduser("~"), ".openclaw", "workspace", "MEMORY.md")
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        print(f"\033[33m[INFO] config.json created with defaults: {config_path}\033[0m")
        print("  Please edit it to set your own scan paths.")
        print()
    else:
        print(f"\033[32m[OK] Config loaded: {config_path}\033[0m")

    # Standard Port for Neural Cloud
    app.run(host="0.0.0.0", port=19001)
