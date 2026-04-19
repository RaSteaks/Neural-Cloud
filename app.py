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

        # Also proxy HTML <img> tags
        def html_img_replacer(match):
            try:
                prefix, img_p, quote = match.group(1), match.group(2), match.group(3)
                img_p_u = urllib.parse.unquote(img_p)
                full_p = img_p_u if ":" in img_p_u or img_p_u.startswith(("/", "\\")) else os.path.abspath(os.path.join(os.path.dirname(target), img_p_u))
                return f'{prefix}/api/image?path={urllib.parse.quote(full_p)}{quote}'
            except: return match.group(0)
        processed_content = re.sub(r'(<img[^>]*\ssrc=["\'])([^"\'>]+)(["\'])', html_img_replacer, processed_content)
        
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

@app.route("/api/content/stream")
def api_content_stream():
    """Streaming content for large files"""
    node_id = request.args.get("id")
    if not node_id: return jsonify({"error": "No ID"}), 400

    decoded_id = urllib.parse.unquote(node_id).strip()
    from backend.memo_utils import get_all_md_files, get_prefer_pdf
    files = get_all_md_files()

    target = next((p for p in files if os.path.basename(p).replace(".md", "").strip() in [decoded_id, decoded_id.replace(" ",""), node_id]), None)
    if not target: return jsonify({"error": f"NodeNotFound: {decoded_id}"}), 404

    # Check if prefer_pdf is enabled and PDF exists
    prefer_pdf = get_prefer_pdf()
    pdf_path = None
    if prefer_pdf:
        bn = os.path.basename(target).replace(".md", "")
        for p_pdf in [os.path.join(os.path.dirname(target), bn+".pdf"), os.path.join(os.path.dirname(os.path.dirname(target)), bn+".pdf")]:
            if os.path.exists(p_pdf):
                pdf_path = p_pdf
                break

    # If PDF exists and prefer_pdf is enabled, stream PDF content
    if pdf_path:
        def generate_pdf():
            try:
                pdf_url = f"/api/pdf?path={urllib.parse.quote(pdf_path)}"
                # Send metadata with PDF indicator
                yield json.dumps({"type": "meta", "id": decoded_id, "pdf_link": pdf_url, "file_path": pdf_path, "is_pdf": True}) + "\n"
                # Send PDF embed HTML
                pdf_html = f"""
<div style="text-align:center;padding:10px;color:var(--text-secondary);font-size:12px;border-bottom:1px solid var(--border);margin-bottom:10px;">
    📄 PDF Mode: <a href="{pdf_url}" target="_blank" style="color:var(--accent)">Open in new tab</a>
</div>
<iframe src="{pdf_url}" style="width:100%;height:calc(100vh - 200px);border:none;border-radius:8px;background:#fff;"></iframe>
"""
                yield json.dumps({"type": "chunk", "content": pdf_html}) + "\n"
                yield json.dumps({"type": "done"}) + "\n"
            except Exception as e:
                yield json.dumps({"type": "error", "error": str(e)}) + "\n"
        return Response(generate_pdf(), mimetype="application/x-ndjson",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    CHUNK_LINES = 40

    def img_replacer(match):
        try:
            alt, img_p = match.group(1), match.group(2)
            img_p_u = urllib.parse.unquote(img_p)
            full_p = img_p_u if ":" in img_p_u or img_p_u.startswith(("/", "\\")) else os.path.abspath(os.path.join(os.path.dirname(target), img_p_u))
            return f'![{alt}](/api/image?path={urllib.parse.quote(full_p)})'
        except: return match.group(0)

    def generate():
        try:
            # Send metadata first
            pdf_link = None
            bn = os.path.basename(target).replace(".md", "")
            for p_pdf in [os.path.join(os.path.dirname(target), bn+".pdf"), os.path.join(os.path.dirname(os.path.dirname(target)), bn+".pdf")]:
                if os.path.exists(p_pdf):
                    pdf_link = f"/api/pdf?path={urllib.parse.quote(p_pdf)}"
                    break
            yield json.dumps({"type": "meta", "id": decoded_id, "pdf_link": pdf_link, "file_path": target}) + "\n"

            with open(target, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Stream in chunks
            for i in range(0, len(lines), CHUNK_LINES):
                chunk = "".join(lines[i:i+CHUNK_LINES])
                chunk = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', img_replacer, chunk)
                # Also proxy HTML <img> tags
                def html_img_repl(match):
                    try:
                        prefix, img_p, quote = match.group(1), match.group(2), match.group(3)
                        img_p_u = urllib.parse.unquote(img_p)
                        full_p = img_p_u if ":" in img_p_u or img_p_u.startswith(("/", "\\")) else os.path.abspath(os.path.join(os.path.dirname(target), img_p_u))
                        return f'{prefix}/api/image?path={urllib.parse.quote(full_p)}{quote}'
                    except: return match.group(0)
                chunk = re.sub(r'(<img[^>]*\ssrc=["\'])([^"\'>]+)(["\'])', html_img_repl, chunk)
                yield json.dumps({"type": "chunk", "content": chunk}) + "\n"

            yield json.dumps({"type": "done"}) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "error": str(e)}) + "\n"

    return Response(generate(), mimetype="application/x-ndjson",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.route("/api/image")
def api_image():
    """Media Proxy Hub with fallback search"""
    p = request.args.get("path")
    if not p: return "400", 400
    p = os.path.normpath(urllib.parse.unquote(p))

    # Direct path check
    if os.path.exists(p):
        return _send_image(p)

    # Fallback strategy: try inserting common subdirectories into the path
    # e.g. .../imgs/ch1/img.png -> .../docs/imgs/ch1/img.png
    parts = p.replace("\\", "/").split("/")
    for i in range(len(parts) - 1, 0, -1):
        for sub in ["docs", "doc", "assets", "resources", "src", "content", "static", "public"]:
            candidate = os.path.normpath("/".join(parts[:i] + [sub] + parts[i:]))
            if os.path.exists(candidate):
                print(f"\033[33m[IMG FALLBACK] {p} -> {candidate}\033[0m")
                return _send_image(candidate)

    # Fallback 2: search by filename in scan_paths
    filename = os.path.basename(p)
    from backend.memo_utils import get_scan_paths
    for sp in get_scan_paths():
        for root, dirs, files in os.walk(sp):
            if filename in files:
                found = os.path.join(root, filename)
                print(f"\033[33m[IMG FALLBACK] {p} -> {found}\033[0m")
                return _send_image(found)

    print(f"\033[31m[IMG 404] {p}\033[0m")
    return "404", 404

def _send_image(path):
    mime, _ = mimetypes.guess_type(path)
    with open(path, "rb") as f:
        return Response(f.read(), mimetype=mime or "application/octet-stream")

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

@app.route("/api/browse")
def api_browse():
    """Browse local directories for folder picker"""
    p = request.args.get("path", "").strip()
    show_files = request.args.get("show_files", "").strip() == "1"
    if not p:
        # Return drive roots on Windows, / on Unix
        if os.name == "nt":
            import string
            drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
            return jsonify({"current": "", "dirs": drives, "is_root": True})
        else:
            p = "/"

    p = os.path.expanduser(p)
    p = os.path.normpath(p)
    if not os.path.isdir(p):
        return jsonify({"error": "Not a directory"}), 400

    try:
        dirs = []
        files = []
        for name in sorted(os.listdir(p)):
            full = os.path.join(p, name)
            if os.path.isdir(full) and not name.startswith("."):
                dirs.append(name)
            elif show_files and os.path.isfile(full) and name.lower().endswith(".md"):
                files.append(name)
        parent = os.path.dirname(p)
        result = {
            "current": p,
            "parent": parent if parent != p else None,
            "dirs": dirs,
            "is_root": False
        }
        if show_files:
            result["files"] = files
        return jsonify(result)
    except PermissionError:
        return jsonify({"current": p, "parent": os.path.dirname(p), "dirs": [], "is_root": False, "error": "Permission denied"})
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
        
        # Read existing config to preserve other fields
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                existing_config = json.load(f)
        except Exception:
            existing_config = {}
        
        config = {
            "scan_paths": [str(p).strip() for p in data["scan_paths"] if str(p).strip()],
            "core_memory_file": str(data.get("core_memory_file", "")).strip(),
            "prefer_pdf": data.get("prefer_pdf", existing_config.get("prefer_pdf", False))
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/restart", methods=["POST"])
def api_restart():
    """Restart the Flask server"""
    import sys
    import subprocess
    python = sys.executable
    script = sys.argv[0]
    # Start new process and exit current
    subprocess.Popen([python, script], creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0)
    os._exit(0)

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
