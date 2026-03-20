from flask import Flask, jsonify, render_template, request, send_file
from src.parser import parse_functions
from src.generator import generate_test_module
from src.api import Api
from src.recent import add_recent, get_recent
import threading
import time
import os
import webview

app = Flask(__name__)


@app.route('/health')
def health():
    return jsonify({"ok": True})


@app.route('/loading')
def loading():
    return render_template('loading.html')


@app.route('/favicon.ico')
def favicon():
    return send_file(os.path.join(os.path.dirname(__file__), 'static', 'favicon', 'favicon.ico'))


@app.route('/')
def home():
    return render_template('home.html')

@app.route('/quick')
def quick():
    return render_template('quick.html')

@app.route('/project')
def project():
    return render_template('project.html')

@app.route('/ai')
def ai():
    return render_template('ai.html')


@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json()
    source_code = data.get("code", "")
    try:
        functions = parse_functions(source_code)
    except SyntaxError as e:
        return jsonify({"error": f"SyntaxError: {e.msg} (line {e.lineno})"}), 400
    test_code = generate_test_module(functions)
    return jsonify({
        "test_code": test_code,
        "functions_found": len(functions)
    })


@app.route('/generate-files', methods=['POST'])
def generate_files():
    paths = request.get_json().get("paths", [])
    parts = []
    for path in paths:
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8", errors="ignore") as f:
            parts.append(f"# --- {os.path.basename(path)} ---\n" + f.read())
    source = "\n\n".join(parts)
    try:
        functions = parse_functions(source)
    except SyntaxError as e:
        return jsonify({"error": f"SyntaxError: {e.msg} (line {e.lineno})"}), 400
    return jsonify({
        "test_code": generate_test_module(functions),
        "functions_found": len(functions),
        "files_scanned": len(parts)
    })


@app.route('/generate-project', methods=['POST'])
def generate_project():
    folder = request.get_json().get("folder", "")
    if not os.path.isdir(folder):
        return jsonify({"error": "Invalid folder path"}), 400

    all_code = []
    files_scanned = 0
    for root, _, files in os.walk(folder):
        for fname in files:
            if fname.endswith(".py"):
                with open(os.path.join(root, fname), encoding="utf-8", errors="ignore") as f:
                    all_code.append(f"# --- {fname} ---\n" + f.read())
                files_scanned += 1

    source = "\n\n".join(all_code)
    try:
        functions = parse_functions(source)
    except SyntaxError as e:
        return jsonify({"error": f"SyntaxError: {e.msg} (line {e.lineno})"}), 400

    test_code = generate_test_module(functions)
    return jsonify({
        "test_code": test_code,
        "functions_found": len(functions),
        "files_scanned": files_scanned
    })


@app.route('/recent', methods=['GET'])
def recent():
    return jsonify(get_recent())

@app.route('/recent/add', methods=['POST'])
def recent_add():
    path = request.get_json().get("path", "")
    if path:
        add_recent(path)
    return jsonify({"ok": True})

@app.route('/generate-ai', methods=['POST'])
def generate_ai():
    data = request.get_json()
    source_code = ""

    if "code" in data:
        source_code = data["code"]
    elif "paths" in data:
        parts = []
        for path in data["paths"]:
            if os.path.isfile(path):
                with open(path, encoding="utf-8", errors="ignore") as f:
                    parts.append(f"# --- {os.path.basename(path)} ---\n" + f.read())
        source_code = "\n\n".join(parts)
    elif "file" in data:
        path = data["file"]
        if not os.path.isfile(path):
            return jsonify({"error": "File not found"}), 400
        with open(path, encoding="utf-8") as f:
            source_code = f.read()
    elif "folder" in data:
        folder = data["folder"]
        if not os.path.isdir(folder):
            return jsonify({"error": "Folder not found"}), 400
        parts = []
        for root, _, files in os.walk(folder):
            for fname in files:
                if fname.endswith(".py"):
                    with open(os.path.join(root, fname), encoding="utf-8", errors="ignore") as f:
                        parts.append(f"# --- {fname} ---\n" + f.read())
        source_code = "\n\n".join(parts)

    try:
        functions = parse_functions(source_code)
    except SyntaxError as e:
        return jsonify({"error": f"SyntaxError: {e.msg} (line {e.lineno})"}), 400

    from agent import run_agent
    try:
        test_code = run_agent(source_code)
    except EnvironmentError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"Agent error: {e}"}), 500
    return jsonify({
        "test_code": test_code,
        "functions_found": len(functions)
    })


if __name__ == '__main__':
    import urllib.request
    api = Api()

    flask_thread = threading.Thread(target=lambda: app.run(port=5000, use_reloader=False))
    flask_thread.daemon = True
    flask_thread.start()

    gsap_js = open(os.path.join(os.path.dirname(__file__), "static", "scripts", "gsap.min.js"), encoding="utf-8").read()
    loading_html = open(os.path.join(os.path.dirname(__file__), "templates", "loading.html"), encoding="utf-8").read()
    loading_html = loading_html.replace('<script src="/static/scripts/gsap.min.js"></script>', f'<script>{gsap_js}</script>')

    window = webview.create_window("Unitra", html=loading_html, js_api=api, width=1000, height=700, background_color="#f5f0e8")

    def on_loading_shown():
        window.events.loaded -= on_loading_shown
        # Wait for Flask while loading animation plays
        while True:
            try:
                urllib.request.urlopen("http://127.0.0.1:5000/health")
                break
            except:
                time.sleep(0.1)
        time.sleep(1.0)
        window.load_url("http://127.0.0.1:5000")

    window.events.loaded += on_loading_shown

    webview.start(icon=os.path.join(os.path.dirname(__file__), "static", "favicon", "favicon.ico"))
