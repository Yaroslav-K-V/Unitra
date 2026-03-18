from flask import Flask, jsonify, render_template, request
from src.parser import parse_functions
from src.generator import generate_test_module
from src.api import Api
import threading
import webview

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json()
    source_code = data.get("code", "")
    functions = parse_functions(source_code)
    test_code = generate_test_module(functions)
    return jsonify({
        "test_code": test_code,
        "functions_found": len(functions)
    })


if __name__ == '__main__':
    api = Api()
    t = threading.Thread(target=lambda: app.run(port=5000, use_reloader=False))
    t.daemon = True
    t.start()
    webview.create_window("Unitra", "http://127.0.0.1:5000", js_api=api, width=1000, height=700)
    webview.start()
