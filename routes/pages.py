import logging
import os
from flask import Blueprint, jsonify, redirect, send_file, current_app

log = logging.getLogger(__name__)
pages_bp = Blueprint("pages", __name__)

try:
    from importlib.metadata import version as _pkg_version
    _APP_VERSION = _pkg_version("unitra")
except Exception:
    _APP_VERSION = "0.1.0"


_UI_DIR = ("static", "ui")
_BUNDLE_PARTS = ("dist", "bundle.js")
_JSX_FILES = (
    "shared.jsx", "screens.jsx", "console.jsx",
    "flow-icons.jsx", "flow-data.jsx", "flow-history.jsx",
    "flow-library.jsx", "flow-templates.jsx", "flow-codeeditor.jsx",
    "flow-canvas.jsx", "flow-inspector.jsx", "flow-app.jsx",
    "prototype-v2.jsx",
)
_STALE_WARNED = False


def _bundle_staleness() -> str:
    """Return name of the .jsx that's newer than bundle.js, or '' if up-to-date."""
    base = os.path.join(current_app.root_path, *_UI_DIR)
    bundle = os.path.join(base, *_BUNDLE_PARTS)
    try:
        bundle_mtime = os.path.getmtime(bundle)
    except OSError:
        return "(bundle missing)"
    for name in _JSX_FILES:
        try:
            if os.path.getmtime(os.path.join(base, name)) > bundle_mtime:
                return name
        except OSError:
            continue
    return ""


def _serve_ui():
    global _STALE_WARNED
    stale = _bundle_staleness()
    if stale and not _STALE_WARNED:
        log.warning("UI bundle stale (%s) — run: npm run build:ui", stale)
        _STALE_WARNED = True
    response = current_app.make_response(send_file(os.path.join(current_app.root_path, *_UI_DIR, "index.html")))
    if stale:
        response.headers["X-Unitra-Bundle-Stale"] = stale
    return response


@pages_bp.route("/health")
def health():
    stale = _bundle_staleness()
    return jsonify({
        "ok": True,
        "version": _APP_VERSION,
        "bundle_stale": stale or None,
    })


@pages_bp.route("/favicon.ico")
def favicon():
    return send_file(os.path.join(current_app.root_path, "static", "favicon", "favicon.ico"))


@pages_bp.route("/")
@pages_bp.route("/home")
@pages_bp.route("/quick")
@pages_bp.route("/workspace")
@pages_bp.route("/dashboard")
@pages_bp.route("/info")
@pages_bp.route("/settings")
def page():
    return _serve_ui()


@pages_bp.route("/project")
def project():
    return redirect("/workspace")


@pages_bp.route("/ai")
def ai():
    return redirect("/workspace")
