import os
from flask import Blueprint, jsonify, redirect, render_template, send_file, current_app
from src.config import load_config

pages_bp = Blueprint("pages", __name__)


def _page_context(active_page: str, **extra):
    config = load_config(root_path=current_app.root_path)
    context = {"active_page": active_page, "show_hints": config.show_hints}
    context.update(extra)
    return context


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
    return render_template("home.html", **_page_context("home"))


@pages_bp.route("/quick")
def quick():
    return render_template("quick.html", **_page_context("quick"))


@pages_bp.route("/project")
def project():
    return redirect("/workspace")


@pages_bp.route("/workspace")
def workspace():
    return render_template("workspace.html", **_page_context("workspace"))


@pages_bp.route("/info")
def info():
    return render_template("info.html", **_page_context("info"))


@pages_bp.route("/ai")
def ai():
    return redirect("/workspace")


@pages_bp.route("/settings")
def settings():
    from src.container import get_container

    config = load_config(root_path=current_app.root_path)
    settings_result = get_container().settings.load_settings()
    return render_template(
        "settings.html",
        **_page_context(
            "settings",
            api_key_set=settings_result.api_key_set,
            current_model=settings_result.model or config.ai_model,
            current_show_hints=settings_result.show_hints,
            current_ai_policy=settings_result.ai_policy.to_dict(),
        ),
    )
