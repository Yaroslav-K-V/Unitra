import json
import os
from datetime import datetime
from typing import Optional

from src.application.exceptions import DependencyError
from src.tui.actions import TuiActions
from src.tui.state import ScreenActionResult, SessionState

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.widgets import Button, Footer, Header, Input, Static, TextArea

    TEXTUAL_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when dependency missing.
    App = object
    ComposeResult = object
    Binding = object
    Horizontal = Vertical = object
    Button = Footer = Header = Input = Static = TextArea = object
    TEXTUAL_AVAILABLE = False


def launch_console(initial_root: str = ".", initial_screen: str = "workspace") -> int:
    if not TEXTUAL_AVAILABLE:
        raise DependencyError("Textual is not installed. Install Unitra with the TUI dependency to use `unitra console`.")
    app = UnitraConsoleApp(initial_root=initial_root, initial_screen=initial_screen)
    app.run()
    return 0


if TEXTUAL_AVAILABLE:

    class UnitraConsoleApp(App):
        CSS = """
        Screen {
            layout: vertical;
        }

        #shell {
            height: 1fr;
        }

        #sidebar, #inspector {
            width: 28;
            padding: 1 2;
            background: $panel;
        }

        #content {
            width: 1fr;
            padding: 1 2;
        }

        .section {
            margin-bottom: 1;
            border: round $primary-background-lighten-1;
            padding: 1;
        }

        .screen-title {
            text-style: bold;
            margin-bottom: 1;
        }

        .nav-button, .action-button {
            width: 100%;
            margin-bottom: 1;
        }

        .target-row {
            height: auto;
            margin-bottom: 1;
        }

        .output {
            height: 1fr;
            border: round $boost;
            padding: 1;
            overflow: auto auto;
        }

        #command-input {
            dock: bottom;
            margin: 0 1 1 1;
        }

        TextArea {
            height: 12;
            margin-bottom: 1;
        }
        """

        BINDINGS = [
            Binding("ctrl+w", "focus_workspace", "Workspace"),
            Binding("ctrl+q", "focus_quick", "Quick"),
            Binding("ctrl+r", "focus_runs", "Runs"),
            Binding("ctrl+a", "focus_agents", "Agents"),
            Binding("ctrl+e", "focus_review", "Review"),
            Binding("ctrl+l", "focus_command", "Command"),
        ]

        def __init__(self, initial_root: str = ".", initial_screen: str = "workspace") -> None:
            super().__init__()
            self.session = SessionState(current_screen=initial_screen)
            self.actions = TuiActions()
            self.initial_root = initial_root
            self.last_result: Optional[ScreenActionResult] = None

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Horizontal(id="shell"):
                with Vertical(id="sidebar"):
                    yield Static("Unitra Console", classes="screen-title")
                    yield Button("Workspace", id="nav-workspace", classes="nav-button", variant="primary")
                    yield Button("Review", id="nav-review", classes="nav-button")
                    yield Button("Runs", id="nav-runs", classes="nav-button")
                    yield Button("Agents", id="nav-agents", classes="nav-button")
                    yield Button("Quick", id="nav-quick", classes="nav-button")
                with Vertical(id="content"):
                    yield Static("", id="screen-title", classes="screen-title")
                    yield from self._compose_workspace_section()
                    yield from self._compose_review_section()
                    yield from self._compose_runs_section()
                    yield from self._compose_agents_section()
                    yield from self._compose_quick_section()
                with Vertical(id="inspector"):
                    yield Static("Assistant hints", classes="screen-title")
                    yield Static("", id="hint-output", classes="output")
                    yield Static("Session", classes="screen-title")
                    yield Static("", id="session-output", classes="output")
            yield Input(placeholder="Command: open /repo | init /repo | target changed | preview [ai] | write [ai] | run | fix [ai] | runs | agent default", id="command-input")
            yield Footer()

        def _compose_workspace_section(self) -> ComposeResult:
            with Vertical(id="workspace-panel", classes="section"):
                yield Static("Open / current workspace")
                yield Input(value=self.initial_root, placeholder="Workspace root", id="workspace-root-input")
                with Horizontal(classes="target-row"):
                    yield Button("Open", id="workspace-open", classes="action-button", variant="primary")
                    yield Button("Init", id="workspace-init", classes="action-button")
                    yield Button("Validate", id="workspace-validate", classes="action-button")
                yield Static("Choose target")
                with Horizontal(classes="target-row"):
                    yield Button("Repo", id="target-repo", classes="action-button", variant="primary")
                    yield Button("Changed", id="target-changed", classes="action-button")
                    yield Button("Folder", id="target-folder", classes="action-button")
                    yield Button("Files", id="target-files", classes="action-button")
                yield Input(placeholder="Optional folder path or comma-separated files", id="target-value-input")
                yield Static("Choose next action")
                with Horizontal(classes="target-row"):
                    yield Button("Preview", id="action-preview", classes="action-button", variant="success")
                    yield Button("Write", id="action-write", classes="action-button")
                    yield Button("Run tests", id="action-run", classes="action-button")
                    yield Button("Fix failures", id="action-fix", classes="action-button", variant="warning")
                yield Static("", id="workspace-output", classes="output")

        def _compose_review_section(self) -> ComposeResult:
            with Vertical(id="review-panel", classes="section"):
                yield Static("Review")
                yield Static("Planned changes and the last run result land here after preview, write, run, or fix.", id="review-output", classes="output")

        def _compose_runs_section(self) -> ComposeResult:
            with Vertical(id="runs-panel", classes="section"):
                yield Static("Runs")
                with Horizontal(classes="target-row"):
                    yield Button("List runs", id="runs-list", classes="action-button", variant="primary")
                    yield Button("Show run", id="runs-show", classes="action-button")
                yield Input(placeholder="History id", id="run-id-input")
                yield Static("", id="runs-output", classes="output")

        def _compose_agents_section(self) -> ComposeResult:
            with Vertical(id="agents-panel", classes="section"):
                yield Static("Agents")
                with Horizontal(classes="target-row"):
                    yield Button("List agents", id="agents-list", classes="action-button", variant="primary")
                    yield Button("Show agent", id="agents-show", classes="action-button")
                    yield Button("List jobs", id="jobs-list", classes="action-button")
                yield Input(placeholder="Agent profile or job name", id="agent-name-input")
                yield Static("", id="agents-output", classes="output")

        def _compose_quick_section(self) -> ComposeResult:
            with Vertical(id="quick-panel", classes="section"):
                yield Static("Quick")
                yield TextArea("", id="quick-code-input")
                with Horizontal(classes="target-row"):
                    yield Button("Generate", id="quick-generate", classes="action-button", variant="primary")
                    yield Button("Run", id="quick-run", classes="action-button")
                yield Static("", id="quick-output", classes="output")

        def on_mount(self) -> None:
            self._set_screen(self.session.current_screen)
            if self.initial_root:
                self.query_one("#workspace-root-input", Input).value = self.initial_root
                config_path = os.path.join(os.path.abspath(self.initial_root), ".unitra", "unitra.toml")
                if os.path.exists(config_path):
                    self._open_workspace()
            self._refresh_hints()

        def action_focus_workspace(self) -> None:
            self._set_screen("workspace")

        def action_focus_quick(self) -> None:
            self._set_screen("quick")

        def action_focus_runs(self) -> None:
            self._set_screen("runs")

        def action_focus_agents(self) -> None:
            self._set_screen("agents")

        def action_focus_review(self) -> None:
            self._set_screen("review")

        def action_focus_command(self) -> None:
            self.query_one("#command-input", Input).focus()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            button_id = event.button.id or ""
            if button_id.startswith("nav-"):
                self._set_screen(button_id.split("-", 1)[1])
                return
            handlers = {
                "workspace-open": self._open_workspace,
                "workspace-init": self._init_workspace,
                "workspace-validate": self._validate_workspace,
                "target-repo": lambda: self._set_target("repo"),
                "target-changed": lambda: self._set_target("changed"),
                "target-folder": lambda: self._set_target("folder"),
                "target-files": lambda: self._set_target("files"),
                "action-preview": lambda: self._run_action(self.actions.preview_generate(self.session)),
                "action-write": lambda: self._run_action(self.actions.write_generate(self.session)),
                "action-run": lambda: self._run_action(self.actions.run_workspace_tests(self.session)),
                "action-fix": lambda: self._run_action(self.actions.fix_failures(self.session, write=True)),
                "runs-list": lambda: self._run_action(self.actions.list_runs(self.session)),
                "runs-show": self._show_run,
                "agents-list": lambda: self._run_action(self.actions.list_agents(self.session)),
                "agents-show": self._show_agent,
                "jobs-list": lambda: self._run_action(self.actions.list_jobs(self.session)),
                "quick-generate": self._quick_generate,
                "quick-run": self._quick_run,
            }
            handler = handlers.get(button_id)
            if handler is not None:
                try:
                    handler()
                except Exception as exc:
                    action_prefix = {
                        "agents": "agent",
                        "runs": "runs",
                        "quick": "quick",
                        "review": "test",
                    }.get(self.session.current_screen, "workspace")
                    self._run_action(
                        ScreenActionResult(
                            action=f"{action_prefix}.error",
                            ok=False,
                            error=str(exc),
                        )
                    )

        def on_input_submitted(self, event: Input.Submitted) -> None:
            if event.input.id != "command-input":
                return
            command = event.value.strip()
            if not command:
                return
            self._handle_command(command)
            event.input.value = ""

        def _handle_command(self, command: str) -> None:
            parts = command.split()
            name = parts[0].lower()
            rest = parts[1:]
            if name == "open" and rest:
                self.query_one("#workspace-root-input", Input).value = " ".join(rest)
                self._open_workspace()
            elif name == "init" and rest:
                self.query_one("#workspace-root-input", Input).value = " ".join(rest)
                self._init_workspace()
            elif name == "validate":
                self._validate_workspace()
            elif name == "screen" and rest:
                self._set_screen(rest[0].lower())
            elif name == "target" and rest:
                scope = rest[0].lower()
                value = " ".join(rest[1:])
                self.query_one("#target-value-input", Input).value = value
                self._set_target(scope)
            elif name == "preview":
                self._run_action(self.actions.preview_generate(self.session, use_ai_generation="ai" in rest))
            elif name == "write":
                self._run_action(self.actions.write_generate(self.session, use_ai_generation="ai" in rest))
            elif name == "run":
                self._run_action(self.actions.run_workspace_tests(self.session))
            elif name == "fix":
                self._run_action(
                    self.actions.fix_failures(
                        self.session,
                        write=True,
                        use_ai_generation="ai" in rest,
                        use_ai_repair="repair" in rest or "ai-repair" in rest,
                    )
                )
            elif name == "runs":
                self._run_action(self.actions.list_runs(self.session))
                self._set_screen("runs")
            elif name == "run-id" and rest:
                self.query_one("#run-id-input", Input).value = rest[0]
                self._show_run()
            elif name == "agents":
                self._run_action(self.actions.list_agents(self.session))
                self._set_screen("agents")
            elif name == "agent" and rest:
                self.query_one("#agent-name-input", Input).value = rest[0]
                self._show_agent()
            elif name == "jobs":
                self._run_action(self.actions.list_jobs(self.session))
                self._set_screen("agents")
            elif name == "quick":
                self._set_screen("quick")
            else:
                self._notify_text(f"Unknown command: {command}")

        def _set_screen(self, screen: str) -> None:
            self.session.current_screen = screen
            mapping = {
                "workspace": "#workspace-panel",
                "review": "#review-panel",
                "runs": "#runs-panel",
                "agents": "#agents-panel",
                "quick": "#quick-panel",
                "home": "#workspace-panel",
            }
            for item in ("#workspace-panel", "#review-panel", "#runs-panel", "#agents-panel", "#quick-panel"):
                widget = self.query_one(item)
                widget.display = item == mapping.get(screen, "#workspace-panel")
            titles = {
                "workspace": "Workspace",
                "review": "Review",
                "runs": "Runs",
                "agents": "Agents",
                "quick": "Quick",
                "home": "Workspace",
            }
            self.query_one("#screen-title", Static).update(titles.get(screen, "Workspace"))
            self._refresh_hints()

        def _open_workspace(self) -> None:
            root = self.query_one("#workspace-root-input", Input).value.strip() or "."
            self._run_action(self.actions.select_workspace(self.session, root))

        def _init_workspace(self) -> None:
            root = self.query_one("#workspace-root-input", Input).value.strip() or "."
            self._run_action(self.actions.init_workspace(self.session, root))

        def _validate_workspace(self) -> None:
            self._run_action(self.actions.validate_workspace(self.session))

        def _set_target(self, scope: str) -> None:
            value = self.query_one("#target-value-input", Input).value.strip()
            if scope == "folder":
                self.session.set_target("folder", folder=value)
            elif scope == "files":
                paths = [item.strip() for item in value.split(",") if item.strip()]
                self.session.set_target("files", paths=paths)
            else:
                self.session.set_target(scope)
            self._refresh_hints()
            self._notify_text(f"Target set to {self.session.selected_target.describe()}")

        def _show_run(self) -> None:
            history_id = self.query_one("#run-id-input", Input).value.strip()
            if history_id:
                self._run_action(self.actions.show_run(self.session, history_id))

        def _show_agent(self) -> None:
            name = self.query_one("#agent-name-input", Input).value.strip()
            if name:
                self._run_action(self.actions.show_agent(self.session, name))

        def _quick_generate(self) -> None:
            code = self.query_one("#quick-code-input", TextArea).text
            self._run_action(self.actions.quick_generate(self.session, code))

        def _quick_run(self) -> None:
            payload = self.last_result.payload if self.last_result else {}
            test_code = payload.get("test_code") or self.query_one("#quick-output", Static).renderable
            if not isinstance(test_code, str):
                test_code = str(test_code)
            self._run_action(self.actions.quick_run(self.session, test_code=test_code))

        def _run_action(self, result: ScreenActionResult) -> None:
            self.last_result = result
            text = self._render_result(result)
            if result.action.startswith("quick."):
                self.query_one("#quick-output", Static).update(text)
            elif result.action.startswith("runs."):
                self.query_one("#runs-output", Static).update(text)
            elif result.action.startswith("agent.") or result.action.startswith("job."):
                self.query_one("#agents-output", Static).update(text)
            elif result.action in {"test.generate", "test.update", "test.fix-failures", "test.run", "job.run"}:
                self.query_one("#review-output", Static).update(text)
                self._set_screen("review")
            else:
                self.query_one("#workspace-output", Static).update(text)
            self._refresh_hints()

        def _refresh_hints(self) -> None:
            hints = "\n\n".join(f"{hint.title}\n{hint.body}" for hint in self.session.hints())
            self.query_one("#hint-output", Static).update(hints)
            session_summary = {
                "workspace": self.session.active_workspace_root or "<none>",
                "target": self.session.selected_target.describe(),
                "profile": self.session.selected_agent_profile or "<default>",
                "last_screen": self.session.current_screen,
            }
            self.query_one("#session-output", Static).update(json.dumps(session_summary, indent=2))

        @staticmethod
        def _render_payload(payload: dict) -> str:
            return json.dumps(payload, indent=2)

        def _render_result(self, result: ScreenActionResult) -> str:
            if result.error:
                return result.error
            if result.action == "workspace.status":
                return self._render_workspace_status(result)
            if result.action == "workspace.init":
                config = result.payload.get("config", {})
                return "\n".join([
                    result.message or "Workspace initialized.",
                    f"Root: {config.get('root_path', self.session.active_workspace_root)}",
                    f"Active profile: {config.get('selected_agent_profile', self.session.selected_agent_profile or 'default')}",
                ])
            if result.action == "workspace.validate":
                return "Workspace metadata looks healthy."
            if result.action == "runs.list":
                return self._render_runs_list(result.payload.get("runs", []))
            if result.action == "runs.show":
                return self._render_job_result(result.payload)
            if result.action == "agent.list":
                return self._render_agent_list(result.payload.get("profiles", []))
            if result.action == "agent.show":
                return self._render_agent_profile(result.payload)
            if result.action == "job.list":
                return self._render_job_list(result.payload.get("jobs", []))
            if result.action == "job.show":
                return self._render_job_definition(result.payload)
            if result.action in {"test.generate", "test.update", "test.fix-failures", "test.run", "job.run"}:
                return self._render_job_result(result.payload)
            if result.action == "quick.generate":
                return result.payload.get("test_code", "") or result.message
            if result.action == "quick.run":
                run = result.payload.get("run", {})
                return "\n".join(
                    item for item in [
                        "Quick tests passed." if run.get("returncode") == 0 else "Quick tests failed.",
                        f"Coverage: {run.get('coverage')}" if run.get("coverage") else "",
                        run.get("output", ""),
                    ] if item
                )
            if result.payload:
                return self._render_payload(result.payload)
            return result.message or result.action

        def _render_workspace_status(self, result: ScreenActionResult) -> str:
            status = result.payload
            config = status.get("config", {})
            return "\n".join([
                result.message or "Workspace loaded.",
                f"Root: {config.get('root_path', self.session.active_workspace_root)}",
                f"Tests: {config.get('test_root', 'tests/unit')}",
                f"Profile: {config.get('selected_agent_profile', self.session.selected_agent_profile or 'default')}",
                f"Jobs: {', '.join(status.get('jobs', [])) or 'none'}",
                f"Recent runs: {len(status.get('recent_runs', []))}",
            ])

        def _render_runs_list(self, runs) -> str:
            if not runs:
                return "No recorded runs yet."
            lines = ["Recent runs"]
            for item in runs:
                run_id = item.get("history_id") if isinstance(item, dict) else str(item)
                label = self._format_run_id(run_id)
                if isinstance(item, dict):
                    status = self._status_label(item.get("run", {}).get("returncode"))
                    name = item.get("job_name") or item.get("mode") or "run"
                    lines.append(f"- {label}  {name}  {status}")
                else:
                    lines.append(f"- {label}")
            return "\n".join(lines)

        def _render_agent_list(self, profiles) -> str:
            if not profiles:
                return "No agent profiles found."
            lines = ["Agent profiles"]
            for profile in profiles:
                roles = ", ".join(profile.get("roles_enabled", [])) or "no roles"
                lines.append(f"- {profile.get('name', 'unnamed')}  model={profile.get('model', 'unknown')}  roles={roles}")
            return "\n".join(lines)

        def _render_agent_profile(self, profile) -> str:
            roles = ", ".join(profile.get("roles_enabled", [])) or "none"
            effective_policy = profile.get("effective_ai_policy", {})
            workspace_policy = profile.get("workspace_ai_policy", {})
            return "\n".join([
                f"Agent profile: {profile.get('name', 'unnamed')}",
                f"Model: {profile.get('model', 'unknown')}",
                f"Roles: {roles}",
                f"Input budget: {profile.get('input_token_budget', 'unknown')}",
                f"Output budget: {profile.get('output_token_budget', 'unknown')}",
                f"Failure mode: {profile.get('failure_mode', 'unknown')}",
                f"AI policy: generation={effective_policy.get('ai_generation', 'off')} repair={effective_policy.get('ai_repair', 'ask')} explain={effective_policy.get('ai_explain', 'ask')}",
                f"Policy source: {profile.get('ai_policy_source', 'global')} inherit={workspace_policy.get('inherit', True)}",
            ])

        def _render_job_list(self, jobs) -> str:
            if not jobs:
                return "No saved jobs found."
            lines = ["Saved jobs"]
            for job in jobs:
                lines.append(
                    f"- {job.get('name', 'unnamed')}  mode={job.get('mode', 'unknown')}  "
                    f"target={job.get('target_scope', 'repo')}  output={job.get('output_policy', 'preview')}"
                )
            return "\n".join(lines)

        def _render_job_definition(self, job) -> str:
            return "\n".join([
                f"Job: {job.get('name', 'unnamed')}",
                f"Mode: {job.get('mode', 'unknown')}",
                f"Target: {job.get('target_scope', 'repo')}",
                f"Output: {job.get('output_policy', 'preview')}",
                f"Timeout: {job.get('timeout', 30)}s",
            ])

        def _render_job_result(self, payload) -> str:
            run = payload.get("run", {})
            planned = payload.get("planned_files", [])
            written = payload.get("written_files", [])
            fallbacks = payload.get("fallback_context_summary", {}).get("count", 0)
            lines = [
                f"Job: {payload.get('job_name', payload.get('mode', 'workspace job'))}",
                f"Mode: {payload.get('mode', 'unknown')}",
                f"Target: {payload.get('target_scope', 'repo')}",
                f"Planned files: {len(planned)}",
                f"Written files: {len(written)}",
                f"Run: {self._status_label(run.get('returncode'))}",
            ]
            if payload.get("history_id"):
                lines.append(f"History id: {payload['history_id']}")
            if run.get("coverage"):
                lines.append(f"Coverage: {run['coverage']}")
            if fallbacks:
                lines.append(f"Fallback contexts: {fallbacks}")
            if planned:
                lines.append("")
                lines.append("Planned:")
                for item in planned[:8]:
                    lines.append(f"- {item.get('action', 'plan')}: {item.get('test_path', '')} [{self._ai_label(item)}]")
                if len(planned) > 8:
                    lines.append(f"- ... {len(planned) - 8} more")
            if run.get("output"):
                lines.append("")
                lines.append("Pytest output:")
                lines.append(run["output"])
            return "\n".join(lines)

        @staticmethod
        def _status_label(returncode) -> str:
            if returncode is None:
                return "not run"
            return "passed" if returncode == 0 else f"failed ({returncode})"

        @staticmethod
        def _ai_label(item) -> str:
            ai_attempted = item.get("ai_attempted")
            ai_used = item.get("ai_used")
            if ai_attempted is None or ai_used is None:
                return "AI unknown"
            if ai_attempted is True and ai_used is True:
                return "AI used"
            if ai_attempted is True and ai_used is False:
                return "AI fallback"
            return "AI skipped"

        @staticmethod
        def _format_run_id(run_id: str) -> str:
            value = str(run_id or "")
            if len(value) >= 14 and value[:14].isdigit():
                try:
                    return datetime.strptime(value[:14], "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    return value
            return value or "unknown run"

        def _notify_text(self, text: str) -> None:
            self.query_one("#workspace-output", Static).update(text)
            self._refresh_hints()
