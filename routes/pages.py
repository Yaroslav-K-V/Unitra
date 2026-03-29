import os
from flask import Blueprint, jsonify, render_template, send_file, current_app

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/health")
def health():
    return jsonify({"ok": True})


@pages_bp.route("/loading")
def loading():
    return render_template("loading.html")


@pages_bp.route("/favicon.ico")
def favicon():
    return send_file(os.path.join(current_app.root_path, "static", "favicon", "favicon.ico"))


@pages_bp.route("/")
def home():
    return render_template("home.html")


@pages_bp.route("/quick")
def quick():
    return render_template("quick.html", active_page="quick")


@pages_bp.route("/project")
def project():
    return render_template("project.html", active_page="project")


@pages_bp.route("/ai")
def ai():
    return render_template("ai.html", active_page="ai")
