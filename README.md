# Unitra

A desktop app for generating Python unit tests — automatically, from your source code.

Paste a function, scan an entire project, or let an AI write tests for you.

---

## Features

- **Quick mode** — paste any Python function or class and get tests instantly
- **Project mode** — scan a folder, pick files, generate tests for the whole codebase
- **AI mode** — describe what you want, let an LLM write tests via OpenAI-compatible API
- **Run Tests** — execute the generated tests with `pytest` directly from the UI
- **Dark mode** — persistent theme toggle (light / dark)
- **Copy output** — one click to copy generated tests or run results
- **Recent projects** — quick access to recently scanned folders
- Keyboard shortcuts: `Ctrl+Enter` to generate, `Ctrl+S` to save

---

## Requirements

- Python 3.10+
- Windows, macOS, or Ubuntu/Debian

---

## Installation

```bash
git clone https://github.com/yourname/unitra.git
cd unitra
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

**Linux only** — GTK dependencies are installed automatically on first run via `apt-get`. You can also install them manually:

```bash
sudo apt-get install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.0
```

---

## Configuration (AI mode)

Copy `.env.example` to `.env` and fill in your API key:

```bash
cp .env.example .env
```

```env
API_KEY=your_openai_key_here
MODEL=gpt-5.4-mini
```

---

## Running

```bash
python app.py
```

---

## Project Structure

```
app.py                  # Entry point: Flask + pywebview startup
routes/
  pages.py              # Page routes (home, quick, project, ai)
  generate.py           # Test generation routes
  runner.py             # Run tests + recent projects
src/
  parser.py             # AST-based Python source parser
  generator.py          # Test code generator
  recent.py             # Recent projects history
  api.py                # pywebview JS bridge
agent/
  main.py               # LangChain agent for AI mode
static/                 # CSS, JS, fonts
templates/              # Jinja2 HTML templates
tests/                  # Unit tests for the app itself
```

---

## Running Tests

```bash
pytest tests/
```

---

## License

MIT
