# Unitra

Unitra is a local-first Python test tooling app with one shared backend and three frontends:

- Desktop app with `pywebview + Flask`
- CLI for automation and CI-friendly workflows
- Keyboard-first TUI built with Textual

Unitra starts with AST-based pytest generation and local subprocess test execution. AI is optional and now defaults to local Ollama instead of a remote provider.

## Quick Start In 30 Seconds

```bash
git clone https://github.com/yourname/unitra.git
cd unitra
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
ollama pull llama3.2
cp .env.example .env
unitra doctor
python app.py
```

If you prefer the CLI first:

```bash
pip install -e .
unitra workspace init --root .
unitra test generate --root . --repo --dry-run
unitra test run --root . -q
```

## Why Unitra

- Local-first by default: source files stay on your machine
- Shared backend architecture across Desktop, CLI, and TUI
- Safe managed test writing with `.unitra/` workspace metadata
- AST generator works without AI
- Optional AI fallback for generation and failure repair
- Workspace-aware jobs, run history, and guided flows

## Main Modes

### Quick

Paste a snippet, open a file, generate tests, then copy or run them.

### Workspace

Initialize a repository, preview managed changes, write tests, run jobs, and inspect run history.

### CLI

Use Unitra in scripts, local automation, and pre-commit hooks.

### Console

Navigate the same workspace logic through a keyboard-first terminal UI.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Editable install for the CLI:

```bash
pip install -e .
```

Linux desktop dependencies, when needed:

```bash
sudo apt-get install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.0
```

## AI Backends

### Default: local Ollama

Unitra uses Ollama as the default AI backend.

```bash
ollama pull llama3.2
unitra doctor
```

Default `.env`:

```env
AI_PROVIDER=ollama
AI_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434/v1/
```

### Optional remote providers

You can still switch to OpenAI or OpenRouter in Settings or through the CLI:

```bash
unitra settings set --provider openai --model gpt-4o-mini --api-key "$OPENAI_API_KEY"
unitra settings set --provider openrouter --model openai/gpt-5.2 --api-key "$OPENROUTER_API_KEY"
```

## Workspace Configuration

Each initialized repo gets `.unitra/unitra.toml`.

Example:

```toml
[workspace]
root_path = "/path/to/repo"
source_include = ["**/*.py"]
source_exclude = ["tests/**", ".venv/**", "venv/**"]

[output]
test_root = "tests/unit"
test_path_strategy = "mirror"
naming_strategy = "test_{module}.py"

[run]
preferred_pytest_args = ["-q"]

[agent]
selected_profile = "default"

[ai_policy]
inherit = true
ai_generation = "off"
ai_repair = "ask"
ai_explain = "ask"

[ai_backend]
provider = "ollama"
model = "llama3.2"
base_url = "http://localhost:11434/v1/"
```

That backend block is what workspace AI generation and repair flows use.

## Useful Commands

Doctor and validation:

```bash
unitra doctor
unitra check
unitra workspace validate --root .
```

Generate and run:

```bash
unitra generate --code "def add(a, b): return a + b"
unitra generate-ai --code "def divide(a, b): return a / b"
unitra run-tests --test-code "def test_smoke(): assert True"
```

Workspace flows:

```bash
unitra workspace init --root /path/to/repo
unitra workspace status --root /path/to/repo --json
unitra test generate --root /path/to/repo --repo --dry-run --json
unitra test update --root /path/to/repo --changed --write
unitra test fix-failures --root /path/to/repo --repo --use-ai --use-ai-repair
unitra runs list --root /path/to/repo
unitra console --root /path/to/repo
```

Settings:

```bash
unitra settings show
unitra settings set --provider ollama --model qwen2.5-coder:7b
unitra settings set --provider openai --model gpt-4o-mini --api-key "$OPENAI_API_KEY"
```

## Pre-Commit

Unitra ships with pre-commit hooks for Ruff and workspace validation.

```bash
pip install -e ".[dev]"
pre-commit install
pre-commit run --all-files
```

The default config runs:

- `ruff-check`
- `ruff-format`
- `unitra check`

## Project Layout

```text
app.py          desktop app entrypoint
routes/         Flask pages and API routes
src/            core app, CLI, TUI, services, infrastructure
agent/          optional AI runner entrypoint
static/         CSS, JavaScript, assets
templates/      Jinja templates
tests/          automated tests
```

## Development

Run tests:

```bash
python3 -m pytest tests/
```

Run a focused subset:

```bash
python3 -m pytest tests/test_services.py tests/test_cli.py tests/test_workspace_tooling.py -q
```

## License

MIT
