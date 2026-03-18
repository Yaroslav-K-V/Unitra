import webview


class Api:
    def open_file(self):
        result = webview.windows[0].create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("Python files (*.py)", "All files (*.*)")
        )
        if not result:
            return None
        with open(result[0], "r", encoding="utf-8") as f:
            return f.read()

    def open_folder(self):
        result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
        return result[0] if result else None
