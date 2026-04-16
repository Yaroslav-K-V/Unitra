# Unitra

Unitra is a local-first tool for generating and running Python tests.

It has a desktop UI for day-to-day work, a CLI for automation, and a terminal console for keyboard-first workflows.

## What It Does

- Generates pytest drafts from Python functions and classes.
- Works with pasted code, single files, folders, or full repositories.
- Shows planned workspace changes before writing files.
- Runs tests locally with pytest.
- Keeps workspace config, jobs, and run history in `.unitra`.
- Can use AI as an optional fallback for harder generation or failure-repair cases.

## Main Modes

### Quick

For snippets and one-off files. Paste or open Python code, generate tests, then copy, save, or run them.

### Workspace

For real repositories. Open a folder, preview managed test changes, write tests, run jobs, and inspect recent runs.

### CLI

For scripts, CI, and repeatable terminal workflows.

### Console

An interactive terminal UI over the same workspace logic.

## Local-First Behavior

- Basic generation works without an API key.
- Workspace files stay in the repo under `.unitra`.
- Settings and API keys stay in `.env`.
- AI is not required for the normal local generation path.

## AI / LangChain

Unitra uses local AST parsing for the default generator.

LangChain is used only for optional AI-assisted paths. Workspace agent profiles define the model, token budget, enabled roles, and failure behavior. For repair flows, Unitra can build a focused context from pytest output, source snippets, generated tests, and recommendations.

## Install

```bash
git clone https://github.com/yourname/unitra.git
cd unitra
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Linux desktop dependencies, if needed:

```bash
sudo apt-get install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.0
```

## Configure AI Fallback

AI is optional. For local-only generation, skip this step.

```bash
cp .env.example .env
```

```env
API_KEY=your_openai_key_here
OPENAI_MODEL=gpt-5.4-mini
```

## Run

Desktop app:

```bash
python app.py
```

CLI:

```bash
pip install -e .
unitra --help
```

Examples:

```bash
unitra workspace init --root /path/to/repo
unitra workspace status --root /path/to/repo --json
unitra test generate --root /path/to/repo --repo --dry-run --json
unitra test run --root /path/to/repo -q
unitra runs list --root /path/to/repo
unitra console --root /path/to/repo
```

## Project Layout

```text
app.py          # desktop app entrypoint
routes/         # Flask pages and API routes
src/            # core app, CLI, TUI, services, infrastructure
agent/          # AI runner entrypoint
static/         # CSS, JavaScript, assets
templates/      # Jinja templates
tests/          # test suite
```

## Tests

```bash
pytest tests/
```

CI runs tests in shards for faster pull request feedback.

## License

MIT
