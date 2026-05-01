import json
import os
from datetime import datetime
from typing import Any, Callable, Optional

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.application.exceptions import DependencyError
from src.tui.actions import TuiActions
from src.tui.state import ScreenActionResult, SessionState
from src.ui.styles import DEFAULT_THEME, textual_status_markup

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.events import Key
    from textual.widgets import Button, Footer, Header, Input, ProgressBar, Static, TextArea

    TEXTUAL_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when dependency missing.
    App = object
    ComposeResult = object
    Binding = object
    Key = object
    Horizontal = Vertical = object
    Button = Footer = Header = Input = ProgressBar = Static = TextArea = object
    TEXTUAL_AVAILABLE = False


def launch_console(initial_root: str = ".", initial_screen: str = "workspace") -> int:
    if not TEXTUAL_AVAILABLE:
        raise DependencyError(
            "Textual is not installed. Install Unitra with the TUI dependency to use `unitra console`."
        )
    app = UnitraConsoleApp(initial_root=initial_root, initial_screen=initial_screen)
    app.run()
    return 0


if TEXTUAL_AVAILABLE:

    class UnitraConsoleApp(App):
        CSS = f"""
        Screen {
            layout: vertical;
            background: {DEFAULT_THEME.colors["bg"]};
            color: {DEFAULT_THEME.colors["text"]};
        }

        #shell {
            height: 1fr;
            padding: 0 1;
        }

        #sidebar, #inspector {
            width: 30;
            padding: 1 2;
            background: {DEFAULT_THEME.colors["card_alt"]};
            border: round {DEFAULT_THEME.colors["border"]};
        }

        #content {
            width: 1fr;
            padding: 1 2;
        }

        #task-bar {
            display: none;
            height: auto;
            margin: 1 1 0 1;
            padding: 1 2;
            border: round {DEFAULT_THEME.colors["border_strong"]};
            background: {DEFAULT_THEME.colors["card"]};
        }

        #task-label {
            width: 36;
            padding-top: 1;
            text-style: bold;
            color: {DEFAULT_THEME.colors["accent"]};
        }

        #task-progress {
            width: 1fr;
        }

        #task-message {
            display: none;
            margin-top: 1;
            color: {DEFAULT_THEME.colors["text_muted"]};
        }

        .section {
            margin-bottom: 1;
            border: round {DEFAULT_THEME.colors["border"]};
            padding: 1;
            background: {DEFAULT_THEME.colors["card"]};
        }

        .screen-title {
            text-style: bold;
            margin-bottom: 1;
            color: {DEFAULT_THEME.colors["accent"]};
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
            border: round {DEFAULT_THEME.colors["border_strong"]};
            padding: 1;
            overflow: auto auto;
            background: {DEFAULT_THEME.colors["card_alt"]};
        }

        #command-input {
            dock: bottom;
            margin: 0 1 1 1;
            background: {DEFAULT_THEME.colors["card"]};
        }

        TextArea {
            height: 12;
            margin-bottom: 1;
            background: {DEFAULT_THEME.colors["card_alt"]};
        }
        """

        BINDINGS = [
            Binding("ctrl+w", "focus_workspace", "Workspace"),
            Binding("ctrl+k", "focus_quick", "Quick"),
            Binding("ctrl+r", "focus_runs", "Runs"),
            Binding("ctrl+a", "focus_agents", "Agents"),
            Binding("ctrl+e", "focus_review", "Review"),
            Binding("ctrl+l", "focus_command", "Command"),
            Binding("q", "quit", "Quit"),
        ]

        def __init__(self, initial_root: str = ".", initial_screen: str = "workspace") -> None:
            super().__init__()
            self.session = SessionState(current_screen=initial_screen)
            self.actions = TuiActions()
            self.initial_root = initial_root
            self.last_result: Optional[ScreenActionResult] = None
            self._task_running = False

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Horizontal(id="task-bar"):
                yield Static("Idle", id="task-label")
                yield ProgressBar(total=100, show_eta=False, id="task-progress")
            yield Static("", id="task-message")
            with Horizontal(id="shell"):
                with Vertical(id="sidebar"):
                    yield Static("Unitra Console", classes="screen-title")
                    yield Static("Hotkeys: g generate · r run · d diff · q quit", id="hotkey-help")
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
            yield Input(
                placeholder=(
                    "Command: open /repo | init /repo | target changed | preview [ai] | "
                    "write [ai] | run | fix [ai] | runs | agent default"
                ),
                id="command-input",
            )
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
                yield Static(
                    "Planned changes and the last run result land here after preview, write, run, or fix.",
                    id="review-output",
                    classes="output",
                )

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

        def action_hotkey_generate(self) -> None:
            if self._editing_text():
                return
            if self.session.current_screen == "quick":
                self._quick_generate()
                return
            self._queue_action("Generate tests", lambda: self.actions.preview_generate(self.session))

        def action_hotkey_run_tests(self) -> None:
            if self._editing_text():
                return
            if self.session.current_screen == "quick":
                self._quick_run()
                return
            self._queue_action("Run workspace tests", lambda: self.actions.run_workspace_tests(self.session))

        def action_hotkey_preview(self) -> None:
            if self._editing_text():
                return
            self._set_screen("review")
            if self.last_result is not None:
                self._notify_text("Opened the latest preview in Review.")
                self._run_action(self.last_result)
                return
            self._queue_action("Preview managed changes", lambda: self.actions.preview_generate(self.session))

        def on_key(self, event: Key) -> None:
            if self._editing_text():
                return
            key = (getattr(event, "key", "") or "").lower()
            if key == "g":
                event.stop()
                self.action_hotkey_generate()
            elif key == "r":
                event.stop()
                self.action_hotkey_run_tests()
            elif key == "d":
                event.stop()
                self.action_hotkey_preview()

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
                "action-preview": lambda: self._queue_action(
                    "Preview managed changes",
                    lambda: self.actions.preview_generate(self.session),
                ),
                "action-write": lambda: self._queue_action(
                    "Write managed tests",
                    lambda: self.actions.write_generate(self.session),
                ),
                "action-run": lambda: self._queue_action(
                    "Run workspace tests",
                    lambda: self.actions.run_workspace_tests(self.session),
                ),
                "action-fix": lambda: self._queue_action(
                    "Repair failing tests",
                    lambda: self.actions.fix_failures(self.session, write=True),
                ),
                "runs-list": lambda: self._queue_action("Load runs", lambda: self.actions.list_runs(self.session)),
                "runs-show": self._show_run,
                "agents-list": lambda: self._queue_action(
                    "Load agents",
                    lambda: self.actions.list_agents(self.session),
                ),
                "agents-show": self._show_agent,
                "jobs-list": lambda: self._queue_action("Load jobs", lambda: self.actions.list_jobs(self.session)),
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
                self._queue_action(
                    "Preview managed changes",
                    lambda: self.actions.preview_generate(self.session, use_ai_generation="ai" in rest),
                )
            elif name == "write":
                self._queue_action(
                    "Write managed tests",
                    lambda: self.actions.write_generate(self.session, use_ai_generation="ai" in rest),
                )
            elif name == "run":
                self._queue_action("Run workspace tests", lambda: self.actions.run_workspace_tests(self.session))
            elif name == "fix":
                self._queue_action(
                    "Repair failing tests",
                    lambda: self.actions.fix_failures(
                        self.session,
                        write=True,
                        use_ai_generation="ai" in rest,
                        use_ai_repair="repair" in rest or "ai-repair" in rest,
                    ),
                )
            elif name == "runs":
                self._queue_action("Load runs", lambda: self.actions.list_runs(self.session))
                self._set_screen("runs")
            elif name == "run-id" and rest:
                self.query_one("#run-id-input", Input).value = rest[0]
                self._show_run()
            elif name == "agents":
                self._queue_action("Load agents", lambda: self.actions.list_agents(self.session))
                self._set_screen("agents")
            elif name == "agent" and rest:
                self.query_one("#agent-name-input", Input).value = rest[0]
                self._show_agent()
            elif name == "jobs":
                self._queue_action("Load jobs", lambda: self.actions.list_jobs(self.session))
                self._set_screen("agents")
            elif name == "guide" and rest:
                verb = rest[0].lower()
                args = rest[1:]
                if verb == "create":
                    if args and args[0].lower() == "job" and len(args) > 1:
                        self._queue_action(
                            "Create guided job",
                            lambda: self.actions.create_guided_job(self.session, args[1]),
                        )
                    else:
                        self._queue_action("Create guided run", lambda: self.actions.create_guided_core(self.session))
                    self._set_screen("review")
                elif verb == "list":
                    self._queue_action("Load guided runs", lambda: self.actions.list_guided_runs(self.session))
                    self._set_screen("runs")
                elif verb == "show" and args:
                    self._queue_action("Load guided run", lambda: self.actions.show_guided_run(self.session, args[0]))
                    self._set_screen("review")
                elif verb == "approve" and len(args) >= 2:
                    self._queue_action(
                        "Approve guided step",
                        lambda: self.actions.approve_guided_step(
                            self.session,
                            args[0],
                            args[1],
                            use_ai_generation="ai" in args,
                            use_ai_repair="repair" in args or "ai-repair" in args,
                        ),
                    )
                    self._set_screen("review")
                elif verb == "skip" and len(args) >= 2:
                    self._queue_action(
                        "Skip guided step",
                        lambda: self.actions.skip_guided_step(self.session, args[0], args[1]),
                    )
                    self._set_screen("review")
                elif verb == "reject" and len(args) >= 2:
                    self._queue_action(
                        "Reject guided step",
                        lambda: self.actions.reject_guided_step(self.session, args[0], args[1]),
                    )
                    self._set_screen("review")
                else:
                    self._notify_text(f"Unknown guide command: {command}")
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
            self._queue_action("Open workspace", lambda: self.actions.select_workspace(self.session, root))

        def _init_workspace(self) -> None:
            root = self.query_one("#workspace-root-input", Input).value.strip() or "."
            self._queue_action("Initialize workspace", lambda: self.actions.init_workspace(self.session, root))

        def _validate_workspace(self) -> None:
            self._queue_action("Validate workspace", lambda: self.actions.validate_workspace(self.session))

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
                self._queue_action("Load run details", lambda: self.actions.show_run(self.session, history_id))

        def _show_agent(self) -> None:
            name = self.query_one("#agent-name-input", Input).value.strip()
            if name:
                self._queue_action("Load agent profile", lambda: self.actions.show_agent(self.session, name))

        def _quick_generate(self) -> None:
            code = self.query_one("#quick-code-input", TextArea).text
            self._queue_action("Generate quick tests", lambda: self.actions.quick_generate(self.session, code))

        def _quick_run(self) -> None:
            payload = self.last_result.payload if self.last_result else {}
            test_code = payload.get("test_code") or self.query_one("#quick-output", Static).renderable
            if not isinstance(test_code, str):
                test_code = str(test_code)
            self._queue_action("Run quick tests", lambda: self.actions.quick_run(self.session, test_code=test_code))

        def _editing_text(self) -> bool:
            focused = getattr(self, "focused", None)
            return isinstance(focused, (Input, TextArea))

        def _queue_action(self, label: str, callback: Callable[[], ScreenActionResult]) -> None:
            if self._task_running:
                self._notify_text("Another task is already running. Wait for it to finish first.")
                return
            self._task_running = True
            self._set_task_state(label=label, progress=8, message="Preparing action...", visible=True)
            self.call_after_refresh(lambda: self._execute_queued_action(label, callback))

        def _execute_queued_action(self, label: str, callback: Callable[[], ScreenActionResult]) -> None:
            result: ScreenActionResult
            try:
                self._set_task_state(label=label, progress=42, message="Running workflow...", visible=True)
                result = callback()
            except Exception as exc:
                result = ScreenActionResult(
                    action=f"{self.session.current_screen}.error",
                    ok=False,
                    error=str(exc),
                )
            self._set_task_state(
                label=label,
                progress=100,
                message="Completed successfully." if result.ok else "Completed with issues.",
                visible=True,
            )
            self._run_action(result)
            self.set_timer(0.8, self._clear_task_state)

        def _set_task_state(self, label: str, progress: int, message: str, visible: bool) -> None:
            self.query_one("#task-bar").display = visible
            progress_bar = self.query_one("#task-progress", ProgressBar)
            progress_bar.update(total=100, progress=max(0, min(100, progress)))
            self.query_one("#task-label", Static).update(Text(label, style=f"bold {DEFAULT_THEME.colors['accent']}"))
            task_message = self.query_one("#task-message", Static)
            task_message.display = visible
            task_message.update(message)

        def _clear_task_state(self) -> None:
            self._task_running = False
            self.query_one("#task-bar").display = False
            task_message = self.query_one("#task-message", Static)
            task_message.display = False
            task_message.update("")
            self.query_one("#task-progress", ProgressBar).update(total=100, progress=0)

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
            hint_panels = []
            for hint in self.session.hints():
                hint_panels.append(
                    Panel(
                        Text.from_markup(f"[bold]{hint.title}[/]\n{hint.body}"),
                        border_style=DEFAULT_THEME.colors["border"],
                        padding=(0, 1),
                    )
                )
            self.query_one("#hint-output", Static).update(Group(*hint_panels) if hint_panels else "No hints yet.")

            session_table = Table.grid(expand=True, padding=(0, 1))
            session_table.add_column(style=DEFAULT_THEME.colors["text_muted"], ratio=1)
            session_table.add_column(style=DEFAULT_THEME.colors["text"], ratio=2)
            backend = self.session.active_ai_backend
            backend_label = backend.get("provider", "ollama") if backend else "<default>"
            if backend.get("model"):
                backend_label = f"{backend_label} / {backend['model']}"
            session_table.add_row("Workspace", self.session.active_workspace_root or "<none>")
            session_table.add_row("Target", self.session.selected_target.describe())
            session_table.add_row("Profile", self.session.selected_agent_profile or "<default>")
            session_table.add_row("Backend", backend_label)
            session_table.add_row("Screen", self.session.current_screen)
            self.query_one("#session-output", Static).update(
                Panel(session_table, border_style=DEFAULT_THEME.colors["border"], padding=(0, 1))
            )

        @staticmethod
        def _render_payload(payload: dict) -> Panel:
            return Panel(
                Text(json.dumps(payload, indent=2), style=DEFAULT_THEME.colors["text"]),
                title="Payload",
                border_style=DEFAULT_THEME.colors["border"],
            )

        def _render_result(self, result: ScreenActionResult) -> Any:
            if result.error:
                return Panel(
                    Text(result.error, style=DEFAULT_THEME.colors["danger"]),
                    title="Error",
                    border_style=DEFAULT_THEME.colors["danger"],
                )
            if result.action == "workspace.status":
                return self._render_workspace_status(result)
            if result.action == "workspace.init":
                return self._render_workspace_status(
                    ScreenActionResult(
                        action="workspace.status",
                        ok=result.ok,
                        payload={"config": result.payload.get("config", {})},
                        message=result.message or "Workspace initialized.",
                    )
                )
            if result.action == "workspace.validate":
                return Panel(
                    Text.from_markup(
                        f"{textual_status_markup('pass')}\nWorkspace metadata looks healthy."
                    ),
                    title="Workspace validation",
                    border_style=DEFAULT_THEME.colors["success"],
                )
            if result.action == "runs.list":
                return self._render_runs_list(result.payload.get("runs", []))
            if result.action == "runs.show":
                if result.payload.get("kind") == "guided_run":
                    return self._render_guided_result(result.payload)
                return self._render_job_result(result.payload)
            if result.action in {"guided.create", "guided.show", "guided.approve", "guided.skip", "guided.reject"}:
                return self._render_guided_result(result.payload)
            if result.action == "guided.list":
                return self._render_runs_list(result.payload.get("runs", []))
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
                return Panel(
                    Text(result.payload.get("test_code", "") or result.message, style=DEFAULT_THEME.colors["text"]),
                    title="Quick preview",
                    border_style=DEFAULT_THEME.colors["border_strong"],
                )
            if result.action == "quick.run":
                run = result.payload.get("run", {})
                return Panel(
                    Group(
                        Text.from_markup(textual_status_markup("pass" if run.get("returncode") == 0 else "failed")),
                        Text(f"Coverage: {run.get('coverage')}" if run.get("coverage") else "Coverage: n/a"),
                        Text(run.get("output", ""), style=DEFAULT_THEME.colors["text_muted"]),
                    ),
                    title="Quick run",
                    border_style=(
                        DEFAULT_THEME.colors["success"]
                        if run.get("returncode") == 0
                        else DEFAULT_THEME.colors["danger"]
                    ),
                )
            if result.payload:
                return self._render_payload(result.payload)
            return result.message or result.action

        def _render_workspace_status(self, result: ScreenActionResult) -> Panel:
            status = result.payload
            config = status.get("config", {})
            backend = config.get("ai_backend", {})
            grid = Table.grid(expand=True, padding=(0, 1))
            grid.add_column(style=DEFAULT_THEME.colors["text_muted"], ratio=1)
            grid.add_column(style=DEFAULT_THEME.colors["text"], ratio=2)
            grid.add_row("Summary", result.message or "Workspace loaded.")
            grid.add_row("Root", config.get("root_path", self.session.active_workspace_root))
            grid.add_row("Tests", config.get("test_root", "tests/unit"))
            grid.add_row(
                "Profile",
                config.get("selected_agent_profile", self.session.selected_agent_profile or "default"),
            )
            grid.add_row("Jobs", str(len(status.get("jobs", []))))
            grid.add_row("Recent runs", str(len(status.get("recent_runs", []))))
            grid.add_row(
                "AI backend",
                " / ".join(item for item in [backend.get("provider", "ollama"), backend.get("model", "")] if item),
            )
            if backend.get("base_url"):
                grid.add_row("Endpoint", backend["base_url"])
            return Panel(grid, title="Workspace", border_style=DEFAULT_THEME.colors["border_strong"])

        def _render_runs_list(self, runs) -> Panel:
            if not runs:
                return Panel(
                    Text("No recorded runs yet.", style=DEFAULT_THEME.colors["text_muted"]),
                    title="Runs",
                    border_style=DEFAULT_THEME.colors["border"],
                )
            table = Table(expand=True, header_style=f"bold {DEFAULT_THEME.colors['accent']}")
            table.add_column("When", ratio=2)
            table.add_column("Kind", ratio=2)
            table.add_column("Status", ratio=2)
            table.add_column("Coverage", ratio=1)
            for item in runs:
                run_id = item.get("history_id") if isinstance(item, dict) else str(item)
                label = self._format_run_id(run_id)
                if isinstance(item, dict):
                    if item.get("kind") == "guided_run":
                        table.add_row(
                            label,
                            item.get("workflow_name", "guided"),
                            Text.from_markup(textual_status_markup(item.get("status", "unknown"))),
                            "—",
                        )
                    else:
                        status = self._status_label(item.get("run", {}).get("returncode"))
                        name = item.get("job_name") or item.get("mode") or "run"
                        table.add_row(
                            label,
                            name,
                            Text.from_markup(textual_status_markup(status)),
                            item.get("run", {}).get("coverage") or "—",
                        )
                else:
                    table.add_row(label, "run", Text.from_markup(textual_status_markup("unknown")), "—")
            return Panel(table, title="Recent runs", border_style=DEFAULT_THEME.colors["border"])

        def _render_agent_list(self, profiles) -> Panel:
            if not profiles:
                return Panel(
                    Text("No agent profiles found.", style=DEFAULT_THEME.colors["text_muted"]),
                    title="Agents",
                    border_style=DEFAULT_THEME.colors["border"],
                )
            table = Table(expand=True, header_style=f"bold {DEFAULT_THEME.colors['accent_alt']}")
            table.add_column("Name", ratio=1)
            table.add_column("Model", ratio=2)
            table.add_column("Roles", ratio=2)
            for profile in profiles:
                roles = ", ".join(profile.get("roles_enabled", [])) or "no roles"
                table.add_row(profile.get("name", "unnamed"), profile.get("model", "unknown"), roles)
            return Panel(table, title="Agent profiles", border_style=DEFAULT_THEME.colors["border"])

        def _render_agent_profile(self, profile) -> Panel:
            roles = ", ".join(profile.get("roles_enabled", [])) or "none"
            effective_policy = profile.get("effective_ai_policy", {})
            workspace_policy = profile.get("workspace_ai_policy", {})
            backend = self.session.active_ai_backend
            grid = Table.grid(expand=True, padding=(0, 1))
            grid.add_column(style=DEFAULT_THEME.colors["text_muted"], ratio=1)
            grid.add_column(style=DEFAULT_THEME.colors["text"], ratio=2)
            grid.add_row("Profile", profile.get("name", "unnamed"))
            grid.add_row("Model", profile.get("model", "unknown"))
            grid.add_row("Roles", roles)
            grid.add_row("Input budget", str(profile.get("input_token_budget", "unknown")))
            grid.add_row("Output budget", str(profile.get("output_token_budget", "unknown")))
            grid.add_row("Failure mode", profile.get("failure_mode", "unknown"))
            grid.add_row(
                "AI policy",
                (
                    f"generation={effective_policy.get('ai_generation', 'off')} "
                    f"repair={effective_policy.get('ai_repair', 'ask')} "
                    f"explain={effective_policy.get('ai_explain', 'ask')}"
                ),
            )
            grid.add_row(
                "Policy source",
                f"{profile.get('ai_policy_source', 'global')} / inherit={workspace_policy.get('inherit', True)}",
            )
            if backend:
                grid.add_row(
                    "Workspace backend",
                    " / ".join(item for item in [backend.get("provider", "ollama"), backend.get("model", "")] if item),
                )
            return Panel(grid, title="Agent profile", border_style=DEFAULT_THEME.colors["border"])

        def _render_job_list(self, jobs) -> Panel:
            if not jobs:
                return Panel(
                    Text("No saved jobs found.", style=DEFAULT_THEME.colors["text_muted"]),
                    title="Jobs",
                    border_style=DEFAULT_THEME.colors["border"],
                )
            table = Table(expand=True, header_style=f"bold {DEFAULT_THEME.colors['accent_alt']}")
            table.add_column("Name", ratio=2)
            table.add_column("Mode", ratio=2)
            table.add_column("Target", ratio=1)
            table.add_column("Output", ratio=1)
            for job in jobs:
                table.add_row(
                    job.get("name", "unnamed"),
                    job.get("mode", "unknown"),
                    job.get("target_scope", "repo"),
                    job.get("output_policy", "preview"),
                )
            return Panel(table, title="Saved jobs", border_style=DEFAULT_THEME.colors["border"])

        def _render_job_definition(self, job) -> Panel:
            grid = Table.grid(expand=True, padding=(0, 1))
            grid.add_column(style=DEFAULT_THEME.colors["text_muted"], ratio=1)
            grid.add_column(style=DEFAULT_THEME.colors["text"], ratio=2)
            grid.add_row("Job", job.get("name", "unnamed"))
            grid.add_row("Mode", job.get("mode", "unknown"))
            grid.add_row("Target", job.get("target_scope", "repo"))
            grid.add_row("Output", job.get("output_policy", "preview"))
            grid.add_row("Timeout", f"{job.get('timeout', 30)}s")
            return Panel(grid, title="Job details", border_style=DEFAULT_THEME.colors["border"])

        def _render_job_result(self, payload) -> Panel:
            run = payload.get("run", {})
            planned = payload.get("planned_files", [])
            written = payload.get("written_files", [])
            fallbacks = payload.get("fallback_context_summary", {}).get("count", 0)
            summary = Table.grid(expand=True, padding=(0, 1))
            summary.add_column(style=DEFAULT_THEME.colors["text_muted"], ratio=1)
            summary.add_column(style=DEFAULT_THEME.colors["text"], ratio=2)
            summary.add_row("Job", payload.get("job_name", payload.get("mode", "workspace job")))
            summary.add_row("Mode", payload.get("mode", "unknown"))
            summary.add_row("Target", payload.get("target_scope", "repo"))
            summary.add_row("Planned files", str(len(planned)))
            summary.add_row("Written files", str(len(written)))
            summary.add_row("Run", Text.from_markup(textual_status_markup(self._status_label(run.get("returncode")))))
            if payload.get("history_id"):
                summary.add_row("History id", payload["history_id"])
            if run.get("coverage"):
                summary.add_row("Coverage", run["coverage"])
            if fallbacks:
                summary.add_row("Fallback contexts", str(fallbacks))
            sections: list[Any] = [summary]
            if planned:
                planned_table = Table(expand=True, header_style=f"bold {DEFAULT_THEME.colors['accent']}")
                planned_table.add_column("Action", ratio=1)
                planned_table.add_column("Test path", ratio=3)
                planned_table.add_column("AI", ratio=1)
                for item in planned[:8]:
                    planned_table.add_row(item.get("action", "plan"), item.get("test_path", ""), self._ai_label(item))
                if len(planned) > 8:
                    planned_table.add_row("…", f"{len(planned) - 8} more entries", "")
                sections.extend([Text(""), planned_table])
            if run.get("output"):
                sections.extend([
                    Text(""),
                    Panel(
                        Text(run["output"], style=DEFAULT_THEME.colors["text_muted"]),
                        title="Pytest output",
                        border_style=DEFAULT_THEME.colors["border"],
                    ),
                ])
            return Panel(Group(*sections), title="Run result", border_style=DEFAULT_THEME.colors["border_strong"])

        def _render_guided_result(self, payload) -> Panel:
            summary = Table.grid(expand=True, padding=(0, 1))
            summary.add_column(style=DEFAULT_THEME.colors["text_muted"], ratio=1)
            summary.add_column(style=DEFAULT_THEME.colors["text"], ratio=2)
            summary.add_row("Guided run", payload.get("workflow_name", "guided"))
            summary.add_row("Source", payload.get("workflow_source", "core"))
            summary.add_row("Status", Text.from_markup(textual_status_markup(payload.get("status", "unknown"))))
            summary.add_row("Target", payload.get("target_scope", "repo"))
            if payload.get("history_id"):
                summary.add_row("History id", payload["history_id"])
            if payload.get("awaiting_step_id"):
                summary.add_row("Awaiting approval", payload["awaiting_step_id"])
            if payload.get("next_recommendation"):
                summary.add_row("Next step", payload["next_recommendation"])
            sections: list[Any] = [summary]
            steps = payload.get("steps", [])
            if steps:
                steps_table = Table(expand=True, header_style=f"bold {DEFAULT_THEME.colors['accent_alt']}")
                steps_table.add_column("Step", ratio=2)
                steps_table.add_column("Status", ratio=1)
                steps_table.add_column("Summary", ratio=3)
                for step in steps:
                    status = step.get("status", "unknown")
                    if step.get("requires_approval"):
                        status = f"{status} / approval"
                    steps_table.add_row(
                        step.get("id", ""),
                        Text.from_markup(textual_status_markup(status)),
                        step.get("summary", ""),
                    )
                sections.extend([Text(""), steps_table])
            timeline = payload.get("timeline", [])
            if timeline:
                timeline_text = Text(style=DEFAULT_THEME.colors["text_muted"])
                for event in timeline[-8:]:
                    timeline_text.append(f"• {event.get('label', '')} [{event.get('status', '')}]\n")
                sections.extend(
                    [
                        Text(""),
                        Panel(
                            timeline_text,
                            title="Timeline",
                            border_style=DEFAULT_THEME.colors["border"],
                        ),
                    ]
                )
            latest_child = payload.get("latest_child_run")
            if isinstance(latest_child, dict):
                sections.extend([Text(""), self._render_job_result(latest_child)])
            return Panel(Group(*sections), title="Guided workflow", border_style=DEFAULT_THEME.colors["border_strong"])

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
            self.query_one("#workspace-output", Static).update(
                Panel(Text(text, style=DEFAULT_THEME.colors["text_muted"]), border_style=DEFAULT_THEME.colors["border"])
            )
            self._refresh_hints()
