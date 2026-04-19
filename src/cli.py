import argparse
import json
import os
import time
import sys
from typing import List, Optional

from src.application.ai_policy import AiPolicy
from src.application.exceptions import DependencyError, ValidationError
from src.application.models import RunTestsRequest, SaveSettingsRequest
from src.application.workspace_models import TestTarget
from src.config import load_config
from src.container import build_container, get_container
from src.serializers import (
    serialize_ai_policy,
    serialize_agent_profile,
    serialize_job_definition,
    serialize_job_result,
    serialize_run_history_record,
    serialize_workspace_status,
    to_dict,
)


UNITRA_VERSION = "0.1.0"
EXIT_UNEXPECTED = 1
EXIT_VALIDATION = 2
EXIT_DEPENDENCY = 3
EXIT_ENVIRONMENT = 4
EXIT_TIMEOUT = 5
EXIT_TEST_FAILURE = 6


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="unitra", description="Generate and run Python tests.")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Print machine-readable JSON.")
    parser.add_argument("--output-file", help="Write formatted output to a file instead of stdout.")
    parser.add_argument("--verbose", action="store_true", help="Include extra details in human-readable output.")
    parser.add_argument("--timings", action="store_true", help="Include execution timing metadata.")
    parser.add_argument("--estimate-cost", action="store_true", help="Include fallback token and cost estimates when available.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {UNITRA_VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Generate tests from inline code.")
    generate.add_argument("--code", required=True, help="Python source code.")

    generate_files = subparsers.add_parser("generate-files", help="Generate tests from file paths.")
    generate_files.add_argument("paths", nargs="+", help="Python files to scan.")

    generate_project = subparsers.add_parser("generate-project", help="Generate tests from a project folder.")
    generate_project.add_argument("folder", help="Folder to scan.")

    generate_ai = subparsers.add_parser("generate-ai", help="Generate tests with AI.")
    generate_ai_group = generate_ai.add_mutually_exclusive_group(required=True)
    generate_ai_group.add_argument("--code", help="Python source code.")
    generate_ai_group.add_argument("--file", help="Single Python file.")
    generate_ai_group.add_argument("--folder", help="Folder to scan.")
    generate_ai_group.add_argument("--paths", nargs="+", help="Python files to scan.")

    run_tests = subparsers.add_parser("run-tests", help="Run generated tests.")
    run_tests.add_argument("--test-code", required=True, help="Generated pytest module.")
    run_tests.add_argument("--source-code", default="", help="Optional source code under test.")
    run_tests.add_argument("--source-folder", default="", help="Optional project folder.")

    recent = subparsers.add_parser("recent", help="Manage recent items.")
    recent_subparsers = recent.add_subparsers(dest="recent_command", required=True)
    recent_subparsers.add_parser("list", help="List recent items.")

    settings = subparsers.add_parser("settings", help="Manage settings.")
    settings_subparsers = settings.add_subparsers(dest="settings_command", required=True)
    settings_subparsers.add_parser("show", help="Show persisted settings.")
    settings_set = settings_subparsers.add_parser("set", help="Persist settings.")
    settings_set.add_argument("--api-key", default="", help="API key to save.")
    settings_set.add_argument("--model", default="", help="Model name to save.")
    settings_set.add_argument("--show-hints", dest="show_hints", action="store_true", help="Show helper hints.")
    settings_set.add_argument("--hide-hints", dest="show_hints", action="store_false", help="Hide helper hints.")
    settings_set.set_defaults(show_hints=None)
    settings_set.add_argument("--ai-generation", choices=["off", "ask"], default=None, help="Default AI behavior for generation.")
    settings_set.add_argument("--ai-repair", choices=["off", "ask", "auto"], default=None, help="Default AI behavior for repair.")
    settings_set.add_argument("--ai-explain", choices=["off", "ask", "auto"], default=None, help="Default AI behavior for explanations.")

    workspace = subparsers.add_parser("workspace", help="Manage Unitra workspace.")
    workspace_subparsers = workspace.add_subparsers(dest="workspace_command", required=True)
    workspace_init = workspace_subparsers.add_parser("init", help="Initialize workspace metadata in the repo.")
    workspace_init.add_argument("--root", default=".", help="Workspace root directory.")
    workspace_status = workspace_subparsers.add_parser("status", help="Show workspace status.")
    workspace_status.add_argument("--root", default=".", help="Workspace root directory.")
    workspace_validate = workspace_subparsers.add_parser("validate", help="Validate workspace metadata.")
    workspace_validate.add_argument("--root", default=".", help="Workspace root directory.")
    workspace_policy = workspace_subparsers.add_parser("ai-policy", help="Manage workspace AI policy override.")
    workspace_policy_subparsers = workspace_policy.add_subparsers(dest="policy_command", required=True)
    workspace_policy_show = workspace_policy_subparsers.add_parser("show", help="Show workspace AI policy.")
    workspace_policy_show.add_argument("--root", default=".", help="Workspace root directory.")
    workspace_policy_set = workspace_policy_subparsers.add_parser("set", help="Persist workspace AI policy.")
    workspace_policy_set.add_argument("--root", default=".", help="Workspace root directory.")
    inherit_group = workspace_policy_set.add_mutually_exclusive_group()
    inherit_group.add_argument("--inherit", dest="inherit", action="store_true", help="Use global AI settings.")
    inherit_group.add_argument("--no-inherit", dest="inherit", action="store_false", help="Customize this workspace.")
    workspace_policy_set.set_defaults(inherit=None)
    workspace_policy_set.add_argument("--ai-generation", choices=["off", "ask"], default=None, help="Workspace AI behavior for generation.")
    workspace_policy_set.add_argument("--ai-repair", choices=["off", "ask", "auto"], default=None, help="Workspace AI behavior for repair.")
    workspace_policy_set.add_argument("--ai-explain", choices=["off", "ask", "auto"], default=None, help="Workspace AI behavior for explanations.")

    job = subparsers.add_parser("job", help="Manage saved jobs.")
    job_subparsers = job.add_subparsers(dest="job_command", required=True)
    job_list = job_subparsers.add_parser("list", help="List saved jobs.")
    job_list.add_argument("--root", default=".", help="Workspace root directory.")
    job_show = job_subparsers.add_parser("show", help="Show a saved job.")
    job_show.add_argument("name", help="Saved job name.")
    job_show.add_argument("--root", default=".", help="Workspace root directory.")
    job_run = job_subparsers.add_parser("run", help="Run a saved job.")
    job_run.add_argument("name", help="Saved job name.")
    job_run.add_argument("--root", default=".", help="Workspace root directory.")
    job_run.add_argument("--target", default="", help="Override target value.")
    job_run.add_argument("--output-policy", default="", help="Override output policy.")

    runs = subparsers.add_parser("runs", help="Inspect workspace run history.")
    runs_subparsers = runs.add_subparsers(dest="runs_command", required=True)
    runs_list = runs_subparsers.add_parser("list", help="List recorded runs.")
    runs_list.add_argument("--root", default=".", help="Workspace root directory.")
    runs_list.add_argument("--limit", type=int, default=20, help="Maximum number of runs to list.")
    runs_show = runs_subparsers.add_parser("show", help="Show a recorded run.")
    runs_show.add_argument("history_id", help="Run history id.")
    runs_show.add_argument("--root", default=".", help="Workspace root directory.")

    agent = subparsers.add_parser("agent", help="Inspect workspace agent profiles.")
    agent_subparsers = agent.add_subparsers(dest="agent_command", required=True)
    agent_list = agent_subparsers.add_parser("list", help="List agent profiles.")
    agent_list.add_argument("--root", default=".", help="Workspace root directory.")
    agent_show = agent_subparsers.add_parser("show", help="Show an agent profile.")
    agent_show.add_argument("name", help="Agent profile name.")
    agent_show.add_argument("--root", default=".", help="Workspace root directory.")

    console = subparsers.add_parser("console", help="Launch the interactive terminal UI.")
    console.add_argument("--root", default=".", help="Workspace root directory.")
    console.add_argument(
        "--screen",
        default="workspace",
        choices=["home", "workspace", "review", "runs", "agents", "quick"],
        help="Initial console screen.",
    )

    test = subparsers.add_parser("test", help="Workspace-first test management commands.")
    test_subparsers = test.add_subparsers(dest="test_command", required=True)
    for name, help_text in [
        ("generate", "Plan or write managed tests."),
        ("update", "Update managed tests."),
        ("fix-failures", "Generate/update tests and annotate likely failure causes."),
    ]:
        sub = test_subparsers.add_parser(name, help=help_text)
        sub.add_argument("--root", default=".", help="Workspace root directory.")
        scope = sub.add_mutually_exclusive_group()
        scope.add_argument("--repo", action="store_true", help="Target the whole workspace.")
        scope.add_argument("--folder", help="Target a folder.")
        scope.add_argument("--files", nargs="+", help="Target explicit files.")
        scope.add_argument("--changed", action="store_true", help="Target changed Python files from git diff HEAD.")
        sub.add_argument("--write", action="store_true", help="Write files instead of preview only.")
        sub.add_argument("--dry-run", action="store_true", help="Explicitly keep the operation in preview mode.")
        sub.add_argument("--use-ai", action="store_true", help="Allow an AI generation call for this run when policy permits it.")
        if name == "fix-failures":
            sub.add_argument("--use-ai-repair", action="store_true", help="Allow AI repair suggestions when policy permits it.")

    test_run = test_subparsers.add_parser("run", help="Run workspace tests.")
    test_run.add_argument("--root", default=".", help="Workspace root directory.")
    test_run.add_argument("--timeout", type=int, default=None, help="Override pytest timeout in seconds.")
    test_run.add_argument("pytest_args", nargs=argparse.REMAINDER, help="Additional pytest arguments.")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args, unknown = parser.parse_known_args(argv)
    if unknown:
        if args.command == "test" and args.test_command == "run":
            args.pytest_args = list(getattr(args, "pytest_args", [])) + unknown
        else:
            parser.error(f"unrecognized arguments: {' '.join(unknown)}")
    if args.command == "console":
        try:
            return _run_console_command(args)
        except DependencyError as exc:
            return _emit_error(str(exc), args.json_output, EXIT_DEPENDENCY, kind="dependency", output_file=args.output_file)
    started = time.perf_counter()
    try:
        payload, exit_code = _dispatch(args)
    except ValidationError as exc:
        return _emit_error(str(exc), args.json_output, EXIT_VALIDATION, kind="validation", output_file=args.output_file)
    except DependencyError as exc:
        return _emit_error(str(exc), args.json_output, EXIT_DEPENDENCY, kind="dependency", output_file=args.output_file)
    except EnvironmentError as exc:
        return _emit_error(str(exc), args.json_output, EXIT_ENVIRONMENT, kind="environment", output_file=args.output_file)
    except TimeoutError as exc:
        return _emit_error(str(exc), args.json_output, EXIT_TIMEOUT, kind="timeout", output_file=args.output_file)
    except Exception as exc:
        return _emit_error(f"Unexpected error: {exc}", args.json_output, EXIT_UNEXPECTED, kind="internal", output_file=args.output_file)
    if args.timings:
        payload["timings_ms"] = {"total": round((time.perf_counter() - started) * 1000, 3)}
    _emit_payload(payload, args.json_output, output_file=args.output_file, verbose=args.verbose)
    return exit_code


def _dispatch(args):
    if args.command == "generate":
        container = get_container()
        code = sys.stdin.read() if args.code == "-" else args.code
        return _success("generate", result=container.generation.generate_from_code(code).__dict__), 0
    if args.command == "generate-files":
        container = get_container()
        return _success("generate-files", result=container.generation.generate_from_paths(args.paths).__dict__), 0
    if args.command == "generate-project":
        container = get_container()
        return _success("generate-project", result=container.generation.generate_from_folder(args.folder).__dict__), 0
    if args.command == "generate-ai":
        container = get_container()
        if args.code:
            return _success("generate-ai", result=container.ai_generation.generate_from_code(args.code).__dict__), 0
        if args.file:
            return _success("generate-ai", result=container.ai_generation.generate_from_file(args.file).__dict__), 0
        if args.folder:
            return _success("generate-ai", result=container.ai_generation.generate_from_folder(args.folder).__dict__), 0
        return _success("generate-ai", result=container.ai_generation.generate_from_paths(args.paths).__dict__), 0
    if args.command == "run-tests":
        container = get_container()
        result = container.test_runner.run_tests(
            RunTestsRequest(
                test_code=args.test_code,
                source_code=args.source_code,
                source_folder=args.source_folder,
            )
        )
        payload = _success(
            "run-tests",
            result=result.__dict__,
            run={"output": result.output, "returncode": result.returncode, "coverage": result.coverage},
        )
        return payload, EXIT_TEST_FAILURE if result.returncode else 0
    if args.command == "recent" and args.recent_command == "list":
        container = get_container()
        return _success("recent list", result=[item.__dict__ for item in container.recent.list_recent()]), 0
    if args.command == "settings" and args.settings_command == "set":
        container = get_container()
        config = getattr(container, "config", None)
        ai_policy = _ai_policy_from_args(args, base=getattr(config, "ai_policy", AiPolicy()))
        result = container.settings.save_settings(
            SaveSettingsRequest(api_key=args.api_key, model=args.model, show_hints=args.show_hints, ai_policy=ai_policy)
        )
        return _success(
            "settings set",
            result={
                "ok": result.saved,
                "model": result.model,
                "api_key_set": result.api_key_set,
                "show_hints": result.show_hints,
                "ai_policy": getattr(result, "ai_policy", AiPolicy()).to_dict(),
            },
        ), 0
    if args.command == "settings" and args.settings_command == "show":
        container = get_container()
        result = container.settings.load_settings()
        return _success(
            "settings show",
            result={
                "model": result.model,
                "api_key_set": result.api_key_set,
                "show_hints": result.show_hints,
                "ai_policy": result.ai_policy.to_dict(),
            },
        ), 0
    if args.command == "workspace":
        container = _container_for_root(args.root)
        if args.workspace_command == "init":
            return _success("workspace init", workspace_root=_workspace_root(args.root), result=to_dict(container.workspace.init_workspace(args.root))), 0
        if args.workspace_command == "status":
            status = container.workspace.status()
            return _success("workspace status", workspace_root=_workspace_root(args.root), result=serialize_workspace_status(status)), 0
        if args.workspace_command == "validate":
            status = container.workspace.validate()
            return _success(
                "workspace validate",
                workspace_root=_workspace_root(args.root),
                result={"valid": True, **serialize_workspace_status(status)},
            ), 0
        if args.workspace_command == "ai-policy":
            if args.policy_command == "show":
                state = container.workspace.ai_policy_state(container.config.ai_policy)
                return _success(
                    "workspace ai-policy show",
                    workspace_root=_workspace_root(args.root),
                    result=_serialize_ai_policy_state(state),
                ), 0
            inherit = True if args.inherit is None else args.inherit
            policy_values = _ai_policy_values_from_args(args)
            state = container.workspace.save_ai_policy(container.config.ai_policy, inherit=inherit, policy_values=policy_values)
            return _success(
                "workspace ai-policy set",
                workspace_root=_workspace_root(args.root),
                result=_serialize_ai_policy_state(state),
            ), 0
    if args.command == "job":
        container = _container_for_root(args.root)
        if args.job_command == "list":
            return _success(
                "job list",
                workspace_root=_workspace_root(args.root),
                result=[serialize_job_definition(job) for job in container.workspace.list_jobs()],
            ), 0
        if args.job_command == "show":
            return _success(
                "job show",
                workspace_root=_workspace_root(args.root),
                result=serialize_job_definition(container.workspace.get_job(args.name)),
            ), 0
        if args.job_command == "run":
            result = container.jobs.run_job(args.name, target_value=args.target, output_policy=args.output_policy)
            payload = _job_command_success("job run", result, workspace_root=_workspace_root(args.root), model=container.config.ai_model, include_cost=args.estimate_cost)
            return payload, _job_exit_code(result)
    if args.command == "runs":
        container = _container_for_root(args.root)
        if args.runs_command == "list":
            run_ids = container.workspace.list_runs(limit=args.limit)
            return _success("runs list", workspace_root=_workspace_root(args.root), result=run_ids), 0
        if args.runs_command == "show":
            record = container.workspace.get_run(args.history_id)
            serialized = serialize_run_history_record(args.history_id, record, model=container.config.ai_model)
            payload = _success("runs show", workspace_root=_workspace_root(args.root), result=serialized)
            if args.estimate_cost:
                payload["estimated_cost"] = serialized["fallback_context_summary"]
            return payload, EXIT_TEST_FAILURE if serialized["run"]["returncode"] else 0
    if args.command == "agent":
        container = _container_for_root(args.root)
        if args.agent_command == "list":
            return _success(
                "agent list",
                workspace_root=_workspace_root(args.root),
                result=[serialize_agent_profile(profile) for profile in container.workspace.list_agent_profiles()],
            ), 0
        if args.agent_command == "show":
            return _success(
                "agent show",
                workspace_root=_workspace_root(args.root),
                result=serialize_agent_profile(container.workspace.get_agent_profile(args.name)),
            ), 0
    if args.command == "test":
        container = _container_for_root(args.root)
        if args.test_command == "run":
            result = container.jobs.run_tests(pytest_args=args.pytest_args, timeout=args.timeout)
            payload = _job_command_success("test run", result, workspace_root=_workspace_root(args.root), model=container.config.ai_model, include_cost=args.estimate_cost)
            return payload, _job_exit_code(result)
        target = _parse_target(args)
        if args.test_command == "generate":
            result = _call_workspace_generation(container.jobs.generate_tests, target, write=_should_write(args), use_ai_generation=args.use_ai)
            payload = _job_command_success("test generate", result, workspace_root=_workspace_root(args.root), model=container.config.ai_model, include_cost=args.estimate_cost)
            return payload, _job_exit_code(result)
        if args.test_command == "update":
            result = _call_workspace_generation(container.jobs.update_tests, target, write=_should_write(args), use_ai_generation=args.use_ai)
            payload = _job_command_success("test update", result, workspace_root=_workspace_root(args.root), model=container.config.ai_model, include_cost=args.estimate_cost)
            return payload, _job_exit_code(result)
        if args.test_command == "fix-failures":
            result = _call_workspace_generation(
                container.jobs.fix_failed_tests,
                target,
                write=_should_write(args),
                use_ai_generation=args.use_ai,
                use_ai_repair=getattr(args, "use_ai_repair", False),
            )
            payload = _job_command_success("test fix-failures", result, workspace_root=_workspace_root(args.root), model=container.config.ai_model, include_cost=args.estimate_cost)
            return payload, _job_exit_code(result)
    raise ValidationError("Unsupported command")


def _run_console_command(args) -> int:
    from src.tui.app import launch_console

    return launch_console(initial_root=_workspace_root(args.root), initial_screen=args.screen)


def _emit_payload(payload, as_json: bool, output_file: Optional[str] = None, verbose: bool = False) -> None:
    rendered = _render_payload(payload, as_json=as_json, verbose=verbose)
    if output_file:
        with open(output_file, "w", encoding="utf-8") as handle:
            handle.write(rendered)
            if not rendered.endswith("\n"):
                handle.write("\n")
        return
    print(rendered)


def _render_payload(payload, as_json: bool, verbose: bool) -> str:
    if as_json:
        return json.dumps(payload, indent=2)
    lines = [f"{payload['command']} [{payload['status']}]"]
    if payload.get("workspace_root"):
        lines.append(f"Workspace: {payload['workspace_root']}")
    result = payload.get("result")
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict) and "type" in item and "path" in item:
                lines.append(f"{item['type']}: {item['path']}")
            elif isinstance(item, dict) and "name" in item:
                lines.append(f"- {item['name']}")
            else:
                lines.append(str(item))
    elif isinstance(result, dict) and "test_code" in result:
        lines.append(result["test_code"])
    elif isinstance(result, dict) and payload["command"] in {"job run", "test generate", "test update", "test fix-failures", "test run", "runs show"}:
        if payload.get("planned_files"):
            lines.append("Planned files:")
            for item in payload["planned_files"]:
                lines.append(f"- {item['action']}: {item['test_path']}")
        if payload.get("written_files"):
            lines.append("Written files:")
            for item in payload["written_files"]:
                if item["written"]:
                    lines.append(f"- wrote {item['test_path']}")
        run = payload.get("run", {})
        if run.get("output"):
            lines.append(run["output"])
        if payload.get("estimated_cost") and verbose:
            lines.append(f"Fallback estimate: {json.dumps(payload['estimated_cost'])}")
    elif isinstance(result, dict):
        lines.append(json.dumps(result, indent=2))
    if payload.get("timings_ms") and verbose:
        lines.append(f"Timings: {json.dumps(payload['timings_ms'])}")
    return "\n".join(lines)


def _emit_error(message: str, as_json: bool, exit_code: int, kind: str, output_file: Optional[str] = None) -> int:
    payload = {"error": message, "exit_code": exit_code, "kind": kind}
    if as_json:
        rendered = json.dumps(payload, indent=2)
    else:
        rendered = message
    if output_file:
        with open(output_file, "w", encoding="utf-8") as handle:
            handle.write(rendered)
            if not rendered.endswith("\n"):
                handle.write("\n")
    else:
        print(rendered, file=sys.stderr)
    return exit_code


def _parse_target(args) -> TestTarget:
    scope = "repo"
    folder = ""
    paths = []
    if getattr(args, "folder", None):
        scope = "folder"
        folder = args.folder
    elif getattr(args, "files", None):
        scope = "files"
        paths = args.files
    elif getattr(args, "changed", False):
        scope = "changed"
    elif getattr(args, "repo", False):
        scope = "repo"
    return TestTarget(scope=scope, workspace_root=_workspace_root(args.root), folder=folder, paths=paths)


def _ai_policy_values_from_args(args) -> dict:
    values = {}
    if getattr(args, "ai_generation", None) is not None:
        values["ai_generation"] = args.ai_generation
    if getattr(args, "ai_repair", None) is not None:
        values["ai_repair"] = args.ai_repair
    if getattr(args, "ai_explain", None) is not None:
        values["ai_explain"] = args.ai_explain
    return values


def _ai_policy_from_args(args, base: AiPolicy) -> Optional[AiPolicy]:
    values = _ai_policy_values_from_args(args)
    if not values:
        return None
    return AiPolicy.from_dict(values, base=base)


def _call_workspace_generation(action, target: TestTarget, write: bool, use_ai_generation: bool, use_ai_repair: bool = False):
    try:
        return action(target, write=write, use_ai_generation=use_ai_generation, use_ai_repair=use_ai_repair)
    except TypeError:
        try:
            return action(target, write=write, use_ai_generation=use_ai_generation)
        except TypeError:
            return action(target, write=write)


def _serialize_ai_policy_state(state: dict) -> dict:
    return {
        "effective_ai_policy": serialize_ai_policy(state["effective_ai_policy"]),
        "global_ai_policy": serialize_ai_policy(state["global_ai_policy"]),
        "workspace_ai_policy": serialize_ai_policy(state["workspace_ai_policy"]),
        "ai_policy_source": state["ai_policy_source"],
    }


def _success(command: str, workspace_root: str = "", result=None, **extra) -> dict:
    return {
        "command": command,
        "status": "ok",
        "workspace_root": workspace_root,
        "result": result,
        **extra,
    }


def _job_command_success(command: str, result, workspace_root: str, model: str, include_cost: bool) -> dict:
    payload = _success(
        command,
        workspace_root=workspace_root,
        **serialize_job_result(result, model=model),
    )
    if include_cost:
        payload["estimated_cost"] = payload["fallback_context_summary"]
    return payload


def _container_for_root(root: str):
    normalized = _workspace_root(root)
    return build_container(load_config(root_path=normalized))


def _workspace_root(root: str) -> str:
    return os.path.abspath(root or ".")


def _should_write(args) -> bool:
    if getattr(args, "dry_run", False):
        return False
    return bool(getattr(args, "write", False))


def _job_exit_code(result) -> int:
    run = getattr(result, "run_returncode", None)
    return EXIT_TEST_FAILURE if run else 0


if __name__ == "__main__":
    raise SystemExit(main())
