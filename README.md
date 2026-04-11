# Unitra

A local-first Python test tool with a desktop UI, a workspace-aware CLI, and a terminal console.

Use Quick for one-off drafts, Workspace for managed repo flows, and `unitra` for CI, automation, and power-user workflows.

---

## Features

- **Quick mode** — paste any Python function or class and get tests instantly
- **Workspace mode** — open a repo, preview managed test changes, run jobs, and inspect runs
- **CLI** — workspace, jobs, runs, agents, and CI-safe JSON output via `unitra`
- **Terminal console** — interactive Textual TUI via `unitra console`
- **AI fallback** — optional model-assisted generation and failure repair context
- **Run Tests** — execute generated or workspace tests with `pytest`
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

## Running the desktop app

```bash
python app.py
```

## CLI

Installed command:

```bash
pip install -e .
unitra --help
```

Useful examples:

```bash
unitra workspace init --root /path/to/repo
unitra workspace status --root /path/to/repo --json
unitra console --root /path/to/repo
unitra test generate --root /path/to/repo --repo --dry-run --json
unitra test run --root /path/to/repo -q
unitra runs list --root /path/to/repo
unitra agent show default --root /path/to/repo --json
```

---

## Project Structure

```
app.py                  # Entry point: Flask + pywebview startup
routes/
  pages.py              # Page routes (home, quick, workspace, info)
  generate.py           # Test generation routes
  runner.py             # Run tests + recent projects
  workspace.py          # Workspace routes
src/
  cli.py                # Reference CLI surface
  tui/                  # Textual terminal app over shared core
  parser.py             # AST-based Python source parser
  generator.py          # Test code generator
  api.py                # pywebview JS bridge
  application/          # Core services and models
  infrastructure/       # Repositories, planners, writers, execution
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
