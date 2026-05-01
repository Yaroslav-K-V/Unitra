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
from routes.desktop import desktop_bp
from routes.generate import generate_bp
from routes.runner   import runner_bp
from routes.workspace import workspace_bp
from src.api import Api
from src.config import load_config
import webview


def create_app() -> Flask:
    flask_app = Flask(__name__)
    flask_app.register_blueprint(pages_bp)
    flask_app.register_blueprint(desktop_bp)
    flask_app.register_blueprint(generate_bp)
    flask_app.register_blueprint(runner_bp)
    flask_app.register_blueprint(workspace_bp)
    return flask_app


app = create_app()


if __name__ == "__main__":
    import urllib.request

    config = load_config(root_path=os.path.dirname(__file__))
    api = Api()

    flask_thread = threading.Thread(target=lambda: app.run(port=config.flask_port, use_reloader=False))
    flask_thread.daemon = True
    flask_thread.start()

    gsap_js = open(os.path.join(os.path.dirname(__file__), "static", "scripts", "gsap.min.js"), encoding="utf-8").read()
    loading_html = open(os.path.join(os.path.dirname(__file__), "templates", "loading.html"), encoding="utf-8").read()
    loading_html = loading_html.replace('<script src="/static/scripts/gsap.min.js"></script>', f"<script>{gsap_js}</script>")

    window = webview.create_window(
        "Unitra",
        html=loading_html,
        js_api=api,
        width=config.window_width,
        height=config.window_height,
        min_size=(config.window_min_width, config.window_min_height),
        resizable=True,
        fullscreen=False,
        maximized=False,
        background_color="#08111f",
    )

    def on_loading_shown():
        window.events.loaded -= on_loading_shown
        while True:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{config.flask_port}/health")
                break
            except Exception:
                time.sleep(0.1)
        time.sleep(1.0)
        window.load_url(f"http://127.0.0.1:{config.flask_port}")

    window.events.loaded += on_loading_shown
    icon_name = "favicon.ico" if sys.platform == "win32" else "favicon-32x32.png"
    webview.start(icon=os.path.join(os.path.dirname(__file__), "static", "favicon", icon_name))
