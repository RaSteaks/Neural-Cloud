#!/usr/bin/env python3
import hmac
import json
import mimetypes
import os
import re
import urllib.parse
from flask import Flask, jsonify, send_from_directory, request, make_response, Response

# --- Project Configuration ---
app = Flask(__name__, static_folder="frontend", static_url_path="/static")
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")


def _auth_enabled() -> bool:
    from backend.memo_utils import get_auth_credentials

    username, password = get_auth_credentials()
    return bool(username and password)


def _auth_misconfigured() -> bool:
    from backend.memo_utils import get_auth_credentials

    username, password = get_auth_credentials()
    username_set = bool(username)
    password_set = bool(password)
    return username_set != password_set


def _auth_ok() -> bool:
    from backend.memo_utils import get_auth_credentials

    username, password = get_auth_credentials()
    auth = request.authorization
    if not auth:
        return False
    return hmac.compare_digest(auth.username or "", username) and hmac.compare_digest(auth.password or "", password)


def _auth_required_response():
    response = make_response("Authentication required", 401)
    response.headers["WWW-Authenticate"] = 'Basic realm="Neural Cloud"'
    return response


def _path_is_within(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def _get_allowed_roots(include_missing: bool = True) -> list[str]:
    from backend.memo_utils import get_scan_paths, get_core_mem_file

    roots = []
    for scan_path in get_scan_paths():
        expanded = os.path.abspath(os.path.expanduser(scan_path))
        if include_missing or os.path.isdir(expanded):
            roots.append(expanded)

    core_memory_file = get_core_mem_file().strip()
    if core_memory_file:
        core_dir = os.path.abspath(os.path.dirname(os.path.expanduser(core_memory_file)))
        if include_missing or os.path.isdir(core_dir):
            roots.append(core_dir)

    deduped = []
    seen = set()
    for root in roots:
        if root not in seen:
            seen.add(root)
            deduped.append(root)
    return deduped


def _normalize_request_path(raw_path: str) -> str:
    return os.path.abspath(os.path.normpath(os.path.expanduser(urllib.parse.unquote(raw_path))))


def _is_allowed_path(path: str) -> bool:
    normalized = _normalize_request_path(path)
    return any(_path_is_within(normalized, root) for root in _get_allowed_roots())


def _safe_display_path(path: str) -> str:
    normalized = _normalize_request_path(path)
    for root in _get_allowed_roots():
        if _path_is_within(normalized, root):
            rel_path = os.path.relpath(normalized, root)
            root_label = os.path.basename(root.rstrip("\\/")) or root
            return root_label if rel_path == "." else f"{root_label}/{rel_path.replace(os.sep, '/')}"
    return os.path.basename(normalized)


@app.before_request
def require_auth():
    if request.method == "OPTIONS":
        return None
    if _auth_misconfigured():
        return make_response("Authentication is misconfigured. Set both username and password.", 500)
    if _auth_enabled() and not _auth_ok():
        return _auth_required_response()
    return None


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    is_pdf_response = request.path.startswith("/api/pdf")
    response.headers["X-Frame-Options"] = "SAMEORIGIN" if is_pdf_response else "DENY"
    frame_ancestors = "'self'" if is_pdf_response else "'none'"
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://d3js.org; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
        "img-src 'self' data: blob:; "
        "font-src 'self' https://cdnjs.cloudflare.com; "
        "connect-src 'self'; "
        "frame-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        f"frame-ancestors {frame_ancestors}"
    )
    return response

@app.route("/")
def index():
    """Neural Cloud Main Entrance"""
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/guest")
def guest_index():
    """Read-only visitor entrance"""
    from backend.memo_utils import get_ui_config

    if not get_ui_config().get("guest_enabled", True):
        return make_response("Guest interface disabled", 404)
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
                
        return jsonify({
            "id": decoded_id,
            "content": processed_content,
            "pdf_link": pdf_link,
            "display_path": _safe_display_path(target),
        })
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
                yield json.dumps({
                    "type": "meta",
                    "id": decoded_id,
                    "pdf_link": pdf_url,
                    "display_path": _safe_display_path(pdf_path),
                    "is_pdf": True,
                }) + "\n"
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
            yield json.dumps({
                "type": "meta",
                "id": decoded_id,
                "pdf_link": pdf_link,
                "display_path": _safe_display_path(target),
            }) + "\n"

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
    p = _normalize_request_path(p)

    # Direct path check
    if os.path.exists(p) and _is_allowed_path(p):
        return _send_image(p)

    # Fallback strategy: try inserting common subdirectories into the path
    # e.g. .../imgs/ch1/img.png -> .../docs/imgs/ch1/img.png
    parts = p.replace("\\", "/").split("/")
    for i in range(len(parts) - 1, 0, -1):
        for sub in ["docs", "doc", "assets", "resources", "src", "content", "static", "public"]:
            candidate = os.path.normpath("/".join(parts[:i] + [sub] + parts[i:]))
            candidate = _normalize_request_path(candidate)
            if os.path.exists(candidate) and _is_allowed_path(candidate):
                print(f"\033[33m[IMG FALLBACK] {p} -> {candidate}\033[0m")
                return _send_image(candidate)

    # Fallback 2: search by filename in scan_paths
    filename = os.path.basename(p)
    from backend.memo_utils import get_scan_paths
    for sp in get_scan_paths():
        for root, dirs, files in os.walk(sp):
            if filename in files:
                found = os.path.join(root, filename)
                if _is_allowed_path(found):
                    print(f"\033[33m[IMG FALLBACK] {p} -> {found}\033[0m")
                    return _send_image(found)

    print(f"\033[31m[IMG 404] {p}\033[0m")
    return "404", 404

def _send_image(path):
    mime, _ = mimetypes.guess_type(path)
    if not mime or not mime.startswith("image/"):
        return "403", 403
    with open(path, "rb") as f:
        return Response(f.read(), mimetype=mime or "application/octet-stream")

@app.route("/api/pdf")
def api_pdf():
    """Document Streaming"""
    p = request.args.get("path")
    if not p: return "400", 400
    p = _normalize_request_path(p)
    if os.path.exists(p) and p.lower().endswith(".pdf") and _is_allowed_path(p):
        return send_from_directory(os.path.dirname(p), os.path.basename(p))
    return "404", 404

@app.route("/api/config", methods=["GET"])
def get_config():
    """Read config.json"""
    from backend.memo_utils import get_public_config

    try:
        return jsonify(get_public_config())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/browse")
def api_browse():
    """Browse local directories for folder picker"""
    p = request.args.get("path", "").strip()
    show_files = request.args.get("show_files", "").strip() == "1"
    if not p:
        roots = _get_allowed_roots(include_missing=False)
        return jsonify({"current": "", "dirs": roots, "is_root": True})

    p = _normalize_request_path(p)
    if not _is_allowed_path(p):
        return jsonify({"error": "Path outside allowed roots"}), 403
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
        from backend.memo_utils import DEFAULT_CONFIG, get_full_config

        data = request.get_json()
        if not data or "scan_paths" not in data:
            return jsonify({"error": "Invalid config: scan_paths required"}), 400
        # Validate: scan_paths must be a list of strings
        if not isinstance(data["scan_paths"], list):
            return jsonify({"error": "scan_paths must be a list"}), 400

        existing_config = get_full_config()
        config = {
            **existing_config,
            "scan_paths": [str(p).strip() for p in data["scan_paths"] if str(p).strip()],
            "core_memory_file": str(data.get("core_memory_file", "")).strip(),
            "prefer_pdf": bool(data.get("prefer_pdf", existing_config.get("prefer_pdf", False))),
        }

        if "server" in data:
            server = data["server"]
            if not isinstance(server, dict):
                return jsonify({"error": "server must be an object"}), 400
            host = str(server.get("host", existing_config.get("server", {}).get("host", DEFAULT_CONFIG["server"]["host"]))).strip()
            port = server.get("port", existing_config.get("server", {}).get("port", DEFAULT_CONFIG["server"]["port"]))
            try:
                port = int(port)
            except (TypeError, ValueError):
                return jsonify({"error": "server.port must be an integer"}), 400
            config["server"] = {"host": host or DEFAULT_CONFIG["server"]["host"], "port": port}

        if "auth" in data:
            auth = data["auth"]
            if not isinstance(auth, dict):
                return jsonify({"error": "auth must be an object"}), 400
            current_auth = existing_config.get("auth", {})
            username = str(auth.get("username", current_auth.get("username", ""))).strip()
            password = auth.get("password", current_auth.get("password", ""))
            config["auth"] = {
                "username": username,
                "password": str(password).strip(),
            }

        if "ui" in data:
            ui = data["ui"]
            if not isinstance(ui, dict):
                return jsonify({"error": "ui must be an object"}), 400
            current_ui = existing_config.get("ui", {})
            config["ui"] = {
                "site_title": str(ui.get("site_title", current_ui.get("site_title", ""))).strip(),
                "guest_enabled": bool(ui.get("guest_enabled", current_ui.get("guest_enabled", True))),
                "guest_title": str(ui.get("guest_title", current_ui.get("guest_title", ""))).strip(),
                "guest_subtitle": str(ui.get("guest_subtitle", current_ui.get("guest_subtitle", ""))).strip(),
                "show_file_paths_in_guest": bool(
                    ui.get("show_file_paths_in_guest", current_ui.get("show_file_paths_in_guest", False))
                ),
            }

        if "allow_restart" in data:
            config["allow_restart"] = bool(data["allow_restart"])

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/restart", methods=["POST"])
def api_restart():
    """Restart the Flask server"""
    from backend.memo_utils import get_allow_restart

    if not get_allow_restart():
        return jsonify({"error": "Restart endpoint disabled"}), 403
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
        from backend.memo_utils import build_initial_config

        default_config = build_initial_config()
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        print(f"\033[33m[INFO] config.json created with defaults: {config_path}\033[0m")
        print("  Template copied from config.template.json. Please edit it to set your own paths.")
        print()
    else:
        print(f"\033[32m[OK] Config loaded: {config_path}\033[0m")

    from backend.memo_utils import get_server_host, get_server_port

    host = get_server_host()
    port = get_server_port()
    if _auth_misconfigured():
        raise RuntimeError(
            "Authentication is misconfigured. Set both auth.username and auth.password "
            "in config.json, or leave both empty."
        )
    if host == "0.0.0.0" and not _auth_enabled():
        raise RuntimeError(
            "Public binding requires auth.username and auth.password to be set in config.json."
        )
    app.run(host=host, port=port)
