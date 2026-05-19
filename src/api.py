import os
import subprocess
import sys

import webview


class Api:
    def maximize_window(self):
        if webview.windows:
            webview.windows[0].maximize()

    def toggle_fullscreen(self):
        if webview.windows:
            webview.windows[0].toggle_fullscreen()

    def open_file(self):
        result = webview.windows[0].create_file_dialog(
            webview.FileDialog.OPEN,
            file_types=("Python files (*.py)", "All files (*.*)")
        )
        if not result:
            return None
        path = result[0]
        with open(path, "r", encoding="utf-8") as f:
            return {"code": f.read(), "path": path}

    def open_files(self):
        result = webview.windows[0].create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=True,
            file_types=("Python files (*.py)", "All files (*.*)")
        )
        if not result:
            return None
        parts = []
        for path in result:
            with open(path, "r", encoding="utf-8") as f:
                parts.append(f"# --- {os.path.basename(path)} ---\n" + f.read())
        return {"code": "\n\n".join(parts), "paths": list(result)}

    def open_file_by_path(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            return {"code": f.read(), "path": path}

    def save_file(self, content: str, default_name: str = "test_generated.py"):
        result = webview.windows[0].create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=default_name,
            file_types=("Python files (*.py)",)
        )
        if not result:
            return None
        path = result if isinstance(result, str) else result[0]
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def navigate(self, url: str):
        webview.windows[0].load_url(url)

    def open_folder(self):
        result = webview.windows[0].create_file_dialog(webview.FileDialog.FOLDER)
        if not result:
            return None
        return result[0]

    def reveal_in_finder(self, path: str):
        """Open the given file or directory in the OS file browser.

        Returns dict {ok, path, error?}. Safe-no-op if path doesn't exist.
        """
        if not path or not isinstance(path, str):
            return {"ok": False, "error": "no path provided"}
        if not os.path.exists(path):
            return {"ok": False, "error": f"path does not exist: {path}"}
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", "-R" if os.path.isfile(path) else path] + ([path] if os.path.isfile(path) else []), check=False)
            elif sys.platform == "win32":
                if os.path.isfile(path):
                    subprocess.run(["explorer", "/select,", path], check=False)
                else:
                    subprocess.run(["explorer", path], check=False)
            else:
                target = path if os.path.isdir(path) else os.path.dirname(path)
                subprocess.run(["xdg-open", target], check=False)
            return {"ok": True, "path": path}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
