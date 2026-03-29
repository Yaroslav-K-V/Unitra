import logging
import os
import subprocess
import sys
import threading
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

if sys.platform.startswith("linux"):
    try:
        import gi
    except ImportError:
        log.info("Installing required GTK packages for Linux...")
        subprocess.run(
            ["sudo", "apt-get", "install", "-y",
             "python3-gi", "python3-gi-cairo",
             "gir1.2-gtk-3.0", "gir1.2-webkit2-4.0"],
            check=True
        )

from flask import Flask
from routes.pages    import pages_bp
from routes.generate import generate_bp
from routes.runner   import runner_bp
from src.api import Api
from src.config import FLASK_PORT, WINDOW_WIDTH, WINDOW_HEIGHT
import webview

app = Flask(__name__)
app.register_blueprint(pages_bp)
app.register_blueprint(generate_bp)
app.register_blueprint(runner_bp)


if __name__ == "__main__":
    import urllib.request

    api = Api()

    flask_thread = threading.Thread(target=lambda: app.run(port=FLASK_PORT, use_reloader=False))
    flask_thread.daemon = True
    flask_thread.start()

    gsap_js = open(os.path.join(os.path.dirname(__file__), "static", "scripts", "gsap.min.js"), encoding="utf-8").read()
    loading_html = open(os.path.join(os.path.dirname(__file__), "templates", "loading.html"), encoding="utf-8").read()
    loading_html = loading_html.replace('<script src="/static/scripts/gsap.min.js"></script>', f"<script>{gsap_js}</script>")

    window = webview.create_window("Unitra", html=loading_html, js_api=api, width=WINDOW_WIDTH, height=WINDOW_HEIGHT, background_color="#f5f0e8")

    def on_loading_shown():
        window.events.loaded -= on_loading_shown
        while True:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{FLASK_PORT}/health")
                break
            except Exception:
                time.sleep(0.1)
        time.sleep(1.0)
        window.load_url(f"http://127.0.0.1:{FLASK_PORT}")

    window.events.loaded += on_loading_shown
    icon_name = "favicon.ico" if sys.platform == "win32" else "favicon-32x32.png"
    webview.start(icon=os.path.join(os.path.dirname(__file__), "static", "favicon", icon_name))
