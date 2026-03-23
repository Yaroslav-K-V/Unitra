import subprocess
import sys
import os

if sys.platform.startswith("linux"):
    try:
        import gi
    except ImportError:
        print("Installing required GTK packages for Linux...")
        subprocess.run(
            ["sudo", "apt-get", "install", "-y",
             "python3-gi", "python3-gi-cairo",
             "gir1.2-gtk-3.0", "gir1.2-webkit2-4.0"],
            check=True
        )

from flask import Flask, jsonify, render_template, request, send_file
from src.parser import parse_functions, parse_classes
from src.generator import generate_test_module
from src.api import Api
from src.recent import add_recent, get_recent
import tempfile
import threading
import time
import webview

app = Flask(__name__)


def _count_tests(test_code: str) -> int:
    """Count how many test functions are in the generated test code."""
    return test_code.count("\ndef test_")


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
        classes = parse_classes(source_code)
    except SyntaxError as e:
        return jsonify({"error": f"SyntaxError: {e.msg} (line {e.lineno})"}), 400
    test_code = generate_test_module(functions, classes)
    return jsonify({
        "test_code": test_code,
        "functions_found": len(functions),
        "classes_found": len(classes),
        "tests_generated": _count_tests(test_code),
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
        classes = parse_classes(source)
    except SyntaxError as e:
        return jsonify({"error": f"SyntaxError: {e.msg} (line {e.lineno})"}), 400
    test_code = generate_test_module(functions, classes)
    return jsonify({
        "test_code": test_code,
        "functions_found": len(functions),
        "classes_found": len(classes),
        "tests_generated": _count_tests(test_code),
        "files_scanned": len(parts),
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
        classes = parse_classes(source)
    except SyntaxError as e:
        return jsonify({"error": f"SyntaxError: {e.msg} (line {e.lineno})"}), 400

    test_code = generate_test_module(functions, classes)
    return jsonify({
        "test_code": test_code,
        "functions_found": len(functions),
        "classes_found": len(classes),
        "tests_generated": _count_tests(test_code),
        "files_scanned": files_scanned,
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
    classes = parse_classes(source_code)
    return jsonify({
        "test_code": test_code,
        "functions_found": len(functions),
        "classes_found": len(classes),
        "tests_generated": _count_tests(test_code),
    })


@app.route('/run-tests', methods=['POST'])
def run_tests():
    body = request.get_json()
    test_code     = body.get("test_code", "")
    source_code   = body.get("source_code", "")    # prepended so functions are in scope
    source_folder = body.get("source_folder", "")  # run pytest from here if provided

    if not test_code:
        return jsonify({"error": "No test code provided"}), 400

    work_dir = source_folder if source_folder and os.path.isdir(source_folder) else None
    full_code = (source_code + "\n\n" + test_code) if source_code else test_code

    # Save temp file in the project dir (not system Temp) so pytest rootdir is correct
    project_dir = os.path.dirname(os.path.abspath(__file__))
    save_dir = work_dir or project_dir
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.py', delete=False, encoding='utf-8', dir=save_dir
    ) as f:
        f.write(full_code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", tmp_path, "-v", "--tb=short", "--no-header"],
            capture_output=True, text=True, timeout=30, cwd=work_dir
        )
        return jsonify({
            "output": result.stdout + result.stderr,
            "returncode": result.returncode,
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timed out after 30s"}), 408
    finally:
        os.unlink(tmp_path)


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
    icon_name = "favicon.ico" if sys.platform == "win32" else "favicon-32x32.png"
    webview.start(icon=os.path.join(os.path.dirname(__file__), "static", "favicon", icon_name))
