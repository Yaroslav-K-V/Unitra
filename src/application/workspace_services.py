import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import replace
from typing import Any, List, Optional

from src.application.ai_policy import AiPolicy, WorkspaceAiPolicy
from src.application.exceptions import ValidationError
from src.application.models import RunResult, RunTestsRequest
from src.application.workspace_models import (
    AgentProfile,
    AnalysisArtifact,
    FailureAnalysisArtifact,
    GenerationArtifact,
    JobDefinition,
    JobRunResult,
    MANAGED_HEADER,
    TestPlanArtifact,
    TestTarget,
    USER_BLOCK_BEGIN,
    USER_BLOCK_END,
    WorkspaceConfig,
    WorkspaceStatus,
)
from src.generator import generate_conftest, generate_test_module
from src.parser import parse_classes, parse_functions


AI_REPAIR_ACTIONS = {
    "update_test_expectation",
    "remove_edge_case",
    "change_expected_exception",
    "suggest_source_change",
    "needs_human_decision",
}
AI_REPAIR_ELIGIBLE_CATEGORIES = {
    "assertion_mismatch",
    "wrong_exception_type",
    "runtime_error",
}
_EXCEPTION_NAME_PATTERN = re.compile(r"\b([A-Za-z_][\w.]*(?:Error|Exception)):")


def build_source_binding_preamble(
    workspace_root: str,
    source_path: str,
    test_path: str,
    functions,
    classes,
    source_code: str = "",
) -> str:
    """Build an importlib source binding block for a managed workspace test file."""
    names = [func.name for func in functions if not getattr(func, "is_method", False)]
    top_level_classes = _top_level_class_names(source_code)
    if source_code:
        names.extend(cls.name for cls in classes if cls.name in top_level_classes)
    else:
        names.extend(cls.name for cls in classes)
    names = sorted(dict.fromkeys(names))
    if not names:
        return ""

    absolute_source = os.path.abspath(source_path)
    absolute_test = os.path.abspath(test_path)
    absolute_root = os.path.abspath(workspace_root)
    relative_source = os.path.relpath(absolute_source, os.path.dirname(absolute_test))
    digest = hashlib.sha1(absolute_source.encode("utf-8")).hexdigest()[:12]
    stem = re.sub(r"\W+", "_", os.path.splitext(os.path.basename(absolute_source))[0]).strip("_") or "module"
    module_name = f"unitra_source_{stem}_{digest}"

    lines = [
        "import importlib.util",
        "import sys",
        "from pathlib import Path",
        "",
        f"_UNITRA_WORKSPACE_ROOT = Path({json.dumps(absolute_root)}).resolve()",
        "if str(_UNITRA_WORKSPACE_ROOT) not in sys.path:",
        "    sys.path.insert(0, str(_UNITRA_WORKSPACE_ROOT))",
        f"_UNITRA_SOURCE_RELATIVE = {json.dumps(relative_source)}",
        f"_UNITRA_SOURCE_FALLBACK = Path({json.dumps(absolute_source)}).resolve()",
        "_UNITRA_SOURCE_PATH = (Path(__file__).resolve().parent / _UNITRA_SOURCE_RELATIVE).resolve()",
        "if not _UNITRA_SOURCE_PATH.exists():",
        "    _UNITRA_SOURCE_PATH = _UNITRA_SOURCE_FALLBACK",
        f"_UNITRA_SOURCE_SPEC = importlib.util.spec_from_file_location({json.dumps(module_name)}, _UNITRA_SOURCE_PATH)",
        "if _UNITRA_SOURCE_SPEC is None or _UNITRA_SOURCE_SPEC.loader is None:",
        "    raise ImportError(f'Cannot load Unitra source module from {_UNITRA_SOURCE_PATH}')",
        "_unitra_source = importlib.util.module_from_spec(_UNITRA_SOURCE_SPEC)",
        "sys.modules[_UNITRA_SOURCE_SPEC.name] = _unitra_source",
        "_UNITRA_SOURCE_SPEC.loader.exec_module(_unitra_source)",
        "",
    ]
    lines.extend(f"{name} = _unitra_source.{name}" for name in names)
    return "\n".join(lines)


def _top_level_class_names(source_code: str) -> set:
    if not source_code:
        return set()
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return set()
    return {node.name for node in tree.body if isinstance(node, ast.ClassDef)}


class WorkspaceService:
    def __init__(self, repository, job_repository, agent_repository, run_history_repository=None):
        self._repository = repository
        self._job_repository = job_repository
        self._agent_repository = agent_repository
        self._run_history_repository = run_history_repository

    def init_workspace(self, root_path: str) -> WorkspaceConfig:
        config = WorkspaceConfig(root_path=os.path.abspath(root_path))
        self._repository.init_workspace(config)
        self._agent_repository.ensure_default()
        for job in self._default_jobs():
            self._job_repository.save(job)
        return config

    def status(self) -> WorkspaceStatus:
        config = self._repository.load_config()
        return WorkspaceStatus(
            config=config,
            jobs=self._job_repository.list_names(),
            agent_profiles=self._agent_repository.list_names(),
            recent_runs=self._repository.list_recent_run_ids(),
        )

    def active_agent_profile(self) -> AgentProfile:
        config = self._repository.load_config()
        return self._agent_repository.load(config.selected_agent_profile)

    def ai_policy_state(self, global_policy: AiPolicy) -> dict:
        config = self._repository.load_config()
        effective = config.ai_policy.effective(global_policy)
        return {
            "effective_ai_policy": effective,
            "global_ai_policy": global_policy,
            "workspace_ai_policy": config.ai_policy,
            "ai_policy_source": config.ai_policy.source(),
        }

    def save_ai_policy(self, global_policy: AiPolicy, inherit: bool, policy_values: Optional[dict] = None) -> dict:
        current = self._repository.load_config().ai_policy
        base = global_policy if current.inherit else current.policy
        policy = AiPolicy.from_dict(policy_values or {}, base=base)
        workspace_policy = WorkspaceAiPolicy(
            inherit=inherit,
            ai_generation=policy.ai_generation,
            ai_repair=policy.ai_repair,
            ai_explain=policy.ai_explain,
        )
        self._repository.save_ai_policy(workspace_policy)
        return self.ai_policy_state(global_policy)

    def validate(self) -> WorkspaceStatus:
        return self.status()

    def list_agent_profiles(self) -> List[AgentProfile]:
        return self._agent_repository.list_profiles()

    def get_agent_profile(self, name: str) -> AgentProfile:
        return self._agent_repository.load(name)

    def list_jobs(self) -> List[JobDefinition]:
        return self._job_repository.list_jobs()

    def get_job(self, name: str) -> JobDefinition:
        return self._job_repository.load(name)

    def list_runs(self, limit: int = 20) -> List[str]:
        if self._run_history_repository is None:
            return []
        return self._run_history_repository.list_ids(limit=limit)

    def get_run(self, history_id: str) -> dict:
        if self._run_history_repository is None:
            raise ValidationError("Run history is not configured")
        return self._run_history_repository.load(history_id)

    @staticmethod
    def _default_jobs() -> List[JobDefinition]:
        return [
            JobDefinition(name="generate-tests", mode="generate-tests", target_scope="repo", output_policy="preview"),
            JobDefinition(name="update-tests", mode="update-tests", target_scope="repo", output_policy="write"),
            JobDefinition(name="run-tests", mode="run-tests", target_scope="repo", output_policy="preview"),
            JobDefinition(name="generate-and-run", mode="generate-and-run", target_scope="repo", output_policy="write"),
            JobDefinition(name="fix-failed-tests", mode="fix-failed-tests", target_scope="repo", output_policy="write"),
        ]


class AgentOrchestrator:
    def __init__(self, source_loader, planner, ai_runner=None):
        self._source_loader = source_loader
        self._planner = planner
        self._ai_runner = ai_runner

    def orchestrate(
        self,
        workspace: WorkspaceConfig,
        profile: AgentProfile,
        source_paths: List[str],
        use_ai_generation: bool = False,
    ) -> List[GenerationArtifact]:
        planned_files = self._planner.plan_paths(workspace, source_paths)
        artifacts = []
        for planned in planned_files:
            analysis = self._analyze(planned.source_path)
            test_plan = self._plan(planned.source_path, planned.test_path, analysis)
            generated = self._generate(
                workspace,
                planned.source_path,
                planned.test_path,
                profile,
                use_ai_generation=use_ai_generation,
            )
            notes = generated.reviewer_notes + self._review(generated.generated_code, test_plan, profile)
            artifacts.append(
                GenerationArtifact(
                    source_path=planned.source_path,
                    test_path=planned.test_path,
                    generated_code=generated.generated_code,
                    reviewer_notes=notes,
                    ai_attempted=generated.ai_attempted,
                    ai_used=generated.ai_used,
                    ai_status=generated.ai_status,
                    ai_reason=generated.ai_reason,
                )
            )
        return artifacts

    def analyze_failures(self, run_output: str, write_plans, workspace: WorkspaceConfig, profile: AgentProfile) -> List[FailureAnalysisArtifact]:
        failed_lines = [line.strip() for line in run_output.splitlines() if line.strip().startswith("FAILED ")]
        failure_tests = self._extract_failure_tests(failed_lines)
        failure_categories = self._classify_failures(run_output, failed_lines, failure_tests)
        artifacts = []
        for plan in write_plans:
            recommendations = []
            for failure in failed_lines:
                if "ZeroDivision" in failure or "divide by zero" in failure.lower():
                    recommendations.append("Avoid zero values for divisor-like parameters.")
                if "OverflowError" in failure:
                    recommendations.append("Clamp extreme numeric edge cases for exponent-like parameters.")
            llm_context = None
            if failure_tests and self._has_ai_repair_candidates(failure_categories):
                llm_context = self._build_llm_fallback_context(
                    workspace=workspace,
                    profile=profile,
                    source_path=plan.source_path,
                    test_path=plan.test_path,
                    generated_content=plan.generated_content,
                    failure_tests=failure_tests,
                    recommendations=recommendations,
                    failure_categories=failure_categories,
                    run_output=run_output,
                )
            artifacts.append(
                FailureAnalysisArtifact(
                    test_path=plan.test_path,
                    failures=failed_lines,
                    recommendations=recommendations or ["Inspect generated edge cases and tighten parameter values."],
                    failure_tests=failure_tests,
                    llm_fallback_context=llm_context,
                    failure_categories=failure_categories,
                    run_output=run_output,
                )
            )
        return artifacts

    def _analyze(self, source_path: str) -> AnalysisArtifact:
        bundle = self._source_loader.load_file(source_path)
        tree = ast.parse(bundle.source_code)
        imports = []
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.append(ast.unparse(node))
        functions = [func.name for func in parse_functions(bundle.source_code)]
        classes = [cls.name for cls in parse_classes(bundle.source_code)]
        return AnalysisArtifact(
            source_path=source_path,
            source_code=bundle.source_code,
            functions=functions,
            classes=classes,
            imports=imports,
        )

    def _plan(self, source_path: str, test_path: str, analysis: AnalysisArtifact) -> TestPlanArtifact:
        cases = [f"basic:{name}" for name in analysis.functions]
        cases.extend(f"class:{name}" for name in analysis.classes)
        goals = ["function smoke coverage"] if analysis.functions else []
        return TestPlanArtifact(
            source_path=source_path,
            test_path=test_path,
            test_cases=cases,
            coverage_goals=goals,
        )

    def _generate(
        self,
        workspace: WorkspaceConfig,
        source_path: str,
        test_path: str,
        profile: AgentProfile,
        use_ai_generation: bool = False,
    ) -> GenerationArtifact:
        bundle = self._source_loader.load_file(source_path)
        functions = parse_functions(bundle.source_code)
        classes = parse_classes(bundle.source_code)
        test_code = generate_test_module(functions, classes)
        binding = build_source_binding_preamble(
            workspace.root_path,
            source_path,
            test_path,
            functions,
            classes,
            source_code=bundle.source_code,
        )
        reviewer_notes = []
        ai_test_code, ai_attempted, ai_used, ai_status, ai_reason = self._generate_with_ai(
            bundle.source_code,
            profile,
            use_ai_generation=use_ai_generation,
        )
        if ai_test_code:
            test_code = ai_test_code
            reviewer_notes.append("Generated with AI assistance.")
        conftest = generate_conftest(classes) if classes else ""
        managed = [MANAGED_HEADER]
        if reviewer_notes:
            managed.extend(f"# {note}" for note in reviewer_notes)
        if binding:
            managed.extend(["", binding.strip()])
        managed.extend(["", test_code.strip()])
        if conftest:
            managed.extend(["", "# Suggested conftest.py content", conftest.strip()])
        managed.extend(["", USER_BLOCK_BEGIN, USER_BLOCK_END, ""])
        return GenerationArtifact(
            source_path=source_path,
            test_path=test_path,
            generated_code="\n".join(managed),
            reviewer_notes=reviewer_notes,
            ai_attempted=ai_attempted,
            ai_used=ai_used,
            ai_status=ai_status,
            ai_reason=ai_reason,
        )

    def _generate_with_ai(self, source_code: str, profile: AgentProfile, use_ai_generation: bool = False):
        if not use_ai_generation:
            return "", False, False, "skipped", "AI generation was not requested."
        if self._ai_runner is None:
            return "", False, False, "skipped", "AI runner is not configured."
        if "generator" not in profile.roles_enabled:
            return "", False, False, "skipped", "Generator role is disabled for this agent profile."
        try:
            output = self._ai_runner.run(source_code).strip()
        except EnvironmentError as exc:
            reason = "API key is missing or AI environment is not configured."
            if str(exc) and "API_KEY" not in str(exc):
                reason = "AI environment error; local AST fallback was used."
            return "", True, False, "fallback", reason
        except Exception:
            return "", True, False, "fallback", "AI generation failed; local AST fallback was used."
        if not output or output.startswith("# No functions or classes found."):
            return "", True, False, "fallback", "AI returned no usable tests; local AST fallback was used."
        try:
            ast.parse(output)
        except SyntaxError:
            return "", True, False, "fallback", "AI output was invalid Python; local AST fallback was used."
        return output, True, True, "used", "AI output was used for this test file."

    @staticmethod
    def _review(generated_code: str, test_plan: TestPlanArtifact, profile: AgentProfile) -> List[str]:
        notes = []
        if "generator" not in profile.roles_enabled:
            notes.append("Generator role disabled; output is scaffold-only.")
        if not test_plan.test_cases:
            notes.append("No explicit test cases planned; review coverage manually.")
        if "assert result is not None" in generated_code:
            notes.append("Some assertions remain generic and may need tightening.")
        return notes

    @staticmethod
    def _extract_failure_tests(failed_lines: List[str]) -> List[str]:
        names = []
        for line in failed_lines:
            match = re.search(r"::([^\s\[]+)(?:\[[^\]]+\])?\s+-", line)
            if match:
                names.append(match.group(1))
        return names

    @staticmethod
    def _classify_failures(run_output: str, failed_lines: List[str], failure_tests: List[str]) -> List[dict]:
        lines = failed_lines or ([run_output.strip()] if run_output.strip() else [])
        categories = []
        for index, line in enumerate(lines):
            category = AgentOrchestrator._classify_failure_text(line, run_output)
            test_name = failure_tests[index] if index < len(failure_tests) else ""
            categories.append({
                "test": test_name,
                "category": category,
                "summary": line[:500],
                "ai_repair_candidate": category in AI_REPAIR_ELIGIBLE_CATEGORIES,
            })
        if not categories and run_output:
            category = AgentOrchestrator._classify_failure_text(run_output, run_output)
            categories.append({
                "test": "",
                "category": category,
                "summary": run_output[:500],
                "ai_repair_candidate": category in AI_REPAIR_ELIGIBLE_CATEGORIES,
            })
        return categories

    @staticmethod
    def _classify_failure_text(summary: str, run_output: str) -> str:
        category = AgentOrchestrator._classify_failure_chunk(summary)
        if category != "unknown":
            return category
        return AgentOrchestrator._classify_failure_chunk(f"{summary}\n{run_output}")

    @staticmethod
    def _classify_failure_chunk(text: str) -> str:
        if re.search(r"\b(NameError|ModuleNotFoundError|ImportError):", text):
            return "missing_import_or_name"
        if "Failed: DID NOT RAISE" in text or "DID NOT RAISE" in text:
            return "wrong_exception_type"
        if "pytest.raises" in text and re.search(
            r"\b(TypeError|ValueError|ZeroDivisionError|RuntimeError|AttributeError|KeyError|IndexError|OverflowError):",
            text,
        ):
            return "wrong_exception_type"
        if "AssertionError" in text:
            return "assertion_mismatch"
        if re.search(
            r"\b(TypeError|ValueError|ZeroDivisionError|RuntimeError|AttributeError|KeyError|IndexError|OverflowError):",
            text,
        ):
            return "runtime_error"
        return "unknown"

    @staticmethod
    def _has_ai_repair_candidates(categories: List[dict]) -> bool:
        return any(item.get("category") in AI_REPAIR_ELIGIBLE_CATEGORIES for item in categories)

    def suggest_ai_repairs(
        self,
        failure_artifacts: List[FailureAnalysisArtifact],
        workspace: WorkspaceConfig,
        profile: AgentProfile,
    ) -> List[dict]:
        if self._ai_runner is None or not hasattr(self._ai_runner, "repair"):
            return []
        suggestions = []
        for failure in failure_artifacts:
            if not self._has_ai_repair_candidates(failure.failure_categories):
                continue
            if not failure.llm_fallback_context:
                continue
            context = self._build_ai_repair_context(failure.llm_fallback_context, failure, workspace, profile)
            try:
                raw_suggestions = self._ai_runner.repair(context)
            except EnvironmentError:
                continue
            except Exception:
                continue
            suggestions.extend(self._normalize_ai_repair_suggestions(raw_suggestions, failure))
        return suggestions

    @staticmethod
    def _build_ai_repair_context(
        context: dict,
        failure: FailureAnalysisArtifact,
        workspace: WorkspaceConfig,
        profile: AgentProfile,
    ) -> dict:
        return {
            "workspace_root": workspace.root_path,
            "model": profile.model,
            "test_path": failure.test_path,
            "failure_categories": failure.failure_categories,
            "failure_tests": context.get("failure_tests", []),
            "traceback": context.get("traceback", ""),
            "actual_expected_summary": context.get("actual_expected_summary", ""),
            "source_snippets": context.get("source_snippets", []),
            "test_snippets": context.get("test_snippets", []),
            "generated_test_metadata": context.get("generated_test_metadata", {}),
            "recommendations": failure.recommendations,
        }

    @staticmethod
    def _normalize_ai_repair_suggestions(raw_suggestions: Any, failure: FailureAnalysisArtifact) -> List[dict]:
        if isinstance(raw_suggestions, dict):
            raw_suggestions = raw_suggestions.get("suggestions", [raw_suggestions])
        if not isinstance(raw_suggestions, list):
            return []
        normalized = []
        for item in raw_suggestions:
            if not isinstance(item, dict):
                continue
            action = item.get("action")
            if action not in AI_REPAIR_ACTIONS:
                action = "needs_human_decision"
            normalized.append({
                "action": action,
                "test_path": item.get("test_path") or failure.test_path,
                "test_name": item.get("test_name") or (failure.failure_tests[0] if failure.failure_tests else ""),
                "reason": item.get("reason") or item.get("summary") or "",
                "details": item.get("details") or item.get("suggestion") or "",
                "confidence": item.get("confidence"),
            })
        return normalized

    def _build_llm_fallback_context(
        self,
        workspace: WorkspaceConfig,
        profile: AgentProfile,
        source_path: str,
        test_path: str,
        generated_content: str,
        failure_tests: List[str],
        recommendations: List[str],
        failure_categories: Optional[List[dict]] = None,
        run_output: str = "",
    ) -> dict:
        source_bundle = self._source_loader.load_file(source_path)
        source_snippets = self._extract_relevant_source_snippets(source_bundle.source_code, failure_tests)
        test_snippets = self._extract_relevant_test_snippets(generated_content, failure_tests)
        context = {
            "source_path": source_path,
            "test_path": test_path,
            "failure_tests": failure_tests,
            "recommendations": recommendations,
            "failure_categories": failure_categories or [],
            "traceback": self._extract_relevant_traceback(run_output, failure_tests),
            "actual_expected_summary": self._extract_actual_expected_summary(run_output),
            "generated_test_metadata": {
                "managed": True,
                "source_path": source_path,
                "test_path": test_path,
            },
            "source_snippets": source_snippets,
            "test_snippets": test_snippets,
            "estimated_input_tokens": 0,
            "expected_output_tokens": profile.output_token_budget,
            "truncated": False,
        }
        context["estimated_input_tokens"] = self._estimate_context_tokens(context)
        while context["estimated_input_tokens"] > profile.input_token_budget:
            if not self._trim_fallback_context(context):
                break
            context["estimated_input_tokens"] = self._estimate_context_tokens(context)
        return context

    def _extract_relevant_source_snippets(self, source_code: str, failure_tests: List[str]) -> List[str]:
        inferred_names = {self._infer_source_name(test_name) for test_name in failure_tests}
        inferred_names.discard("")
        snippets = []
        tree = ast.parse(source_code)
        lines = source_code.splitlines()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in inferred_names:
                snippets.append("\n".join(lines[node.lineno - 1:node.end_lineno]))
            elif isinstance(node, ast.ClassDef) and node.name.lower() in inferred_names:
                snippets.append("\n".join(lines[node.lineno - 1:node.end_lineno]))
        if not snippets:
            snippets.append(source_code[:1200])
        return snippets

    @staticmethod
    def _extract_relevant_traceback(run_output: str, failure_tests: List[str]) -> str:
        if not run_output:
            return ""
        lines = run_output.splitlines()
        wanted = set(failure_tests)
        if not wanted:
            return "\n".join(lines[-80:])
        captured = []
        capture = False
        for line in lines:
            if any(test_name in line for test_name in wanted):
                capture = True
            if capture:
                captured.append(line)
            if capture and line.startswith("FAILED ") and captured:
                break
            if len(captured) >= 120:
                break
        return "\n".join(captured or lines[-80:])

    @staticmethod
    def _extract_actual_expected_summary(run_output: str) -> str:
        if not run_output:
            return ""
        summary_lines = []
        for line in run_output.splitlines():
            stripped = line.strip()
            if (
                "AssertionError" in stripped
                or "E       " in line
                or "DID NOT RAISE" in stripped
                or re.search(r"\b(TypeError|ValueError|ZeroDivisionError|RuntimeError):", stripped)
            ):
                summary_lines.append(stripped)
            if len(summary_lines) >= 20:
                break
        return "\n".join(summary_lines)

    @staticmethod
    def _extract_relevant_test_snippets(generated_content: str, failure_tests: List[str]) -> List[str]:
        tree = ast.parse(generated_content)
        lines = generated_content.splitlines()
        wanted = set(failure_tests)
        snippets = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted:
                snippets.append("\n".join(lines[node.lineno - 1:node.end_lineno]))
        if not snippets:
            snippets.append(generated_content[:1200])
        return snippets

    @staticmethod
    def _infer_source_name(test_name: str) -> str:
        name = test_name
        if name.startswith("test_"):
            name = name[5:]
        for suffix in ("_basic", "_defaults", "_parametrize", "_init"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
        return name.split("_")[0]

    @staticmethod
    def _estimate_context_tokens(context: dict) -> int:
        parts = [
            context.get("source_path", ""),
            context.get("test_path", ""),
            "\n".join(context.get("failure_tests", [])),
            "\n".join(context.get("recommendations", [])),
            "\n".join(item.get("category", "") for item in context.get("failure_categories", [])),
            context.get("traceback", ""),
            context.get("actual_expected_summary", ""),
            "\n\n".join(context.get("source_snippets", [])),
            "\n\n".join(context.get("test_snippets", [])),
            str(context.get("expected_output_tokens", "")),
        ]
        return max(1, sum(len(part) for part in parts if part) // 4)

    @staticmethod
    def _trim_fallback_context(context: dict) -> bool:
        context["truncated"] = True

        for key in ("traceback", "actual_expected_summary"):
            value = context.get(key, "")
            if len(value) > 80:
                context[key] = value[: max(80, len(value) // 2)]
                return True
            if value:
                context[key] = ""
                return True

        for key in ("test_snippets", "source_snippets"):
            snippets = context.get(key, [])
            if len(snippets) > 1:
                context[key] = snippets[:-1]
                return True

        for key in ("test_snippets", "source_snippets"):
            snippets = context.get(key, [])
            if not snippets:
                continue
            current = snippets[0]
            if len(current) > 80:
                next_length = max(80, len(current) // 2)
                if next_length < len(current):
                    context[key][0] = current[:next_length]
                    return True
            context[key] = []
            return True

        for key in ("recommendations", "failure_tests"):
            items = context.get(key, [])
            if len(items) > 1:
                context[key] = items[:1]
                return True

        for key in ("source_path", "test_path"):
            value = context.get(key, "")
            basename = os.path.basename(value)
            if basename and basename != value:
                context[key] = basename
                return True

        expected_output_tokens = int(context.get("expected_output_tokens", 0) or 0)
        if expected_output_tokens > 32:
            context["expected_output_tokens"] = max(32, expected_output_tokens // 2)
            return True

        return False


class WorkspaceJobService:
    def __init__(
        self,
        workspace_repository,
        job_repository,
        agent_repository,
        run_history_repository,
        source_loader,
        planner,
        writer,
        orchestrator,
        test_runner,
        global_ai_policy: Optional[AiPolicy] = None,
    ):
        self._workspace_repository = workspace_repository
        self._job_repository = job_repository
        self._agent_repository = agent_repository
        self._run_history_repository = run_history_repository
        self._source_loader = source_loader
        self._planner = planner
        self._writer = writer
        self._orchestrator = orchestrator
        self._test_runner = test_runner
        self._global_ai_policy = global_ai_policy or AiPolicy()
        self._preview_cache = {}

    def list_jobs(self) -> List[str]:
        return self._job_repository.list_names()

    def run_job(
        self,
        name: str,
        target_value: str = "",
        output_policy: str = "",
        use_ai_generation: bool = False,
        use_ai_repair: bool = False,
    ) -> JobRunResult:
        job = self._job_repository.load(name)
        if target_value or output_policy or use_ai_generation or use_ai_repair:
            job = JobDefinition(
                name=job.name,
                mode=job.mode,
                target_scope=job.target_scope,
                target_value=target_value or job.target_value,
                output_policy=output_policy or job.output_policy,
                run_pytest_args=job.run_pytest_args,
                coverage=job.coverage,
                timeout=job.timeout,
                agent_profile=job.agent_profile,
                use_ai_generation=use_ai_generation,
                use_ai_repair=use_ai_repair,
            )
        return self.execute(job)

    def execute(self, job: JobDefinition) -> JobRunResult:
        workspace = self._workspace_repository.load_config()
        profile = self._agent_repository.load(job.agent_profile)
        effective_ai_policy = workspace.ai_policy.effective(self._global_ai_policy)
        self._validate_ai_generation_request(job, effective_ai_policy)
        self._validate_ai_repair_request(job, effective_ai_policy)
        source_paths = self._resolve_target_paths(workspace, TestTarget(
            scope=job.target_scope,
            workspace_root=workspace.root_path,
            folder=job.target_value if job.target_scope == "folder" else "",
            paths=[path for path in job.target_value.split(",") if path] if job.target_scope == "files" else [],
        ))

        should_write = job.output_policy in {"write", "write-run"}
        if job.mode in {"generate-and-run", "fix-failed-tests"}:
            should_write = True
        planned_files = []
        written = []

        preview_cached = False
        if job.mode != "run-tests":
            planned_lookup = {
                item.source_path: item
                for item in self._planner.plan_paths(workspace, source_paths)
            }
            preview_key = self._preview_cache_key(job, workspace, profile, source_paths, list(planned_lookup.values()), effective_ai_policy)
            if preview_key:
                cached = self._preview_cache.get(preview_key)
                if cached is not None:
                    planned_files, written = cached
                    preview_cached = True
            if not preview_cached:
                artifacts = self._orchestrator.orchestrate(
                    workspace,
                    profile,
                    source_paths,
                    use_ai_generation=job.use_ai_generation,
                )
                for artifact in artifacts:
                    planned_files.append(
                        self._planner.build_write_plan(
                            planned_lookup[artifact.source_path],
                            artifact.generated_code,
                            ai_attempted=artifact.ai_attempted,
                            ai_used=artifact.ai_used,
                            ai_status=artifact.ai_status,
                            ai_reason=artifact.ai_reason,
                        )
                    )
                written = self._writer.apply(planned_files, write=should_write)
                if preview_key:
                    self._preview_cache[preview_key] = (
                        tuple(planned_files),
                        tuple(written),
                    )
        if job.mode == "run-tests":
            written = []
        elif should_write and preview_cached:
            written = self._writer.apply(planned_files, write=True)

        run_output = ""
        run_returncode = None
        run_coverage = None
        llm_fallback_contexts = []
        failure_categories = []
        ai_repair_suggestions = []
        ai_repair_requested = bool(job.use_ai_repair)
        ai_repair_used = False
        ai_repair_status = "skipped"
        ai_repair_reason = "AI repair was not needed."

        if job.mode in {"run-tests", "generate-and-run", "fix-failed-tests"}:
            if job.mode == "run-tests":
                run_result = self._run_workspace_tests(workspace, job)
            else:
                run_result = self._run_generated_tests(planned_files, workspace, job)
            run_output = run_result.output
            run_returncode = run_result.returncode
            run_coverage = run_result.coverage

            if job.mode == "fix-failed-tests" and run_returncode:
                failure_artifacts = self._orchestrator.analyze_failures(run_output, planned_files, workspace, profile)
                failure_categories = self._collect_failure_categories(failure_artifacts)
                ai_repair_suggestions, ai_repair_used, ai_repair_status, ai_repair_reason = self._maybe_suggest_ai_repairs(
                    job,
                    effective_ai_policy,
                    failure_artifacts,
                    workspace,
                    profile,
                )
                augmented = []
                for plan, failure in zip(planned_files, failure_artifacts):
                    fixed_content = self._apply_failure_fixes(plan.generated_content, failure)
                    advisory = "\n".join(f"# NOTE: {item}" for item in failure.recommendations)
                    augmented.append(
                        replace(
                            plan,
                            generated_content=fixed_content.rstrip() + "\n\n" + advisory + "\n",
                        )
                    )
                    if failure.llm_fallback_context:
                        llm_fallback_contexts.append(failure.llm_fallback_context)
                planned_files = augmented
                written = self._writer.apply(planned_files, write=True)
                rerun = self._run_generated_tests(planned_files, workspace, job)
                run_output = rerun.output
                run_returncode = rerun.returncode
                run_coverage = rerun.coverage

        result = JobRunResult(
            job_name=job.name,
            mode=job.mode,
            target_scope=job.target_scope,
            planned_files=planned_files,
            written_files=written,
            run_output=run_output,
            run_returncode=run_returncode,
            run_coverage=run_coverage,
            llm_fallback_contexts=llm_fallback_contexts,
            failure_categories=failure_categories,
            ai_repair_suggestions=ai_repair_suggestions,
            ai_repair_requested=ai_repair_requested,
            ai_repair_used=ai_repair_used,
            ai_repair_status=ai_repair_status,
            ai_repair_reason=ai_repair_reason,
        )
        history_id = self._run_history_repository.save(result)
        return JobRunResult(
            job_name=result.job_name,
            mode=result.mode,
            target_scope=result.target_scope,
            planned_files=result.planned_files,
            written_files=result.written_files,
            run_output=result.run_output,
            run_returncode=result.run_returncode,
            run_coverage=result.run_coverage,
            llm_fallback_contexts=result.llm_fallback_contexts,
            failure_categories=result.failure_categories,
            ai_repair_suggestions=result.ai_repair_suggestions,
            ai_repair_requested=result.ai_repair_requested,
            ai_repair_used=result.ai_repair_used,
            ai_repair_status=result.ai_repair_status,
            ai_repair_reason=result.ai_repair_reason,
            history_id=history_id,
        )

    def generate_tests(self, target: TestTarget, write: bool, use_ai_generation: bool = False) -> JobRunResult:
        job = JobDefinition(
            name="ad-hoc-generate",
            mode="generate-tests",
            target_scope=target.scope,
            target_value=self._target_value(target),
            output_policy="write" if write else "preview",
            use_ai_generation=use_ai_generation,
        )
        return self.execute(job)

    def update_tests(self, target: TestTarget, write: bool, use_ai_generation: bool = False) -> JobRunResult:
        job = JobDefinition(
            name="ad-hoc-update",
            mode="update-tests",
            target_scope=target.scope,
            target_value=self._target_value(target),
            output_policy="write" if write else "preview",
            use_ai_generation=use_ai_generation,
        )
        return self.execute(job)

    def fix_failed_tests(
        self,
        target: TestTarget,
        write: bool,
        use_ai_generation: bool = False,
        use_ai_repair: bool = False,
    ) -> JobRunResult:
        job = JobDefinition(
            name="ad-hoc-fix",
            mode="fix-failed-tests",
            target_scope=target.scope,
            target_value=self._target_value(target),
            output_policy="write" if write else "preview",
            use_ai_generation=use_ai_generation,
            use_ai_repair=use_ai_repair,
        )
        return self.execute(job)

    def run_tests(self, pytest_args: Optional[List[str]] = None, timeout: Optional[int] = None) -> JobRunResult:
        workspace = self._workspace_repository.load_config()
        job = JobDefinition(
            name="ad-hoc-run-tests",
            mode="run-tests",
            target_scope="repo",
            output_policy="preview",
            run_pytest_args=pytest_args or workspace.preferred_pytest_args,
            timeout=timeout or 30,
        )
        return self.execute(job)

    def _run_generated_tests(self, plans, workspace: WorkspaceConfig, job: JobDefinition) -> RunResult:
        if not plans:
            raise ValidationError("No test files were planned for this target")
        modules = []
        for plan in plans:
            source_code = self._source_loader.load_file(plan.source_path).source_code
            modules.append(source_code.rstrip() + "\n\n" + plan.generated_content.lstrip())
        if hasattr(self._test_runner, "run_multiple"):
            return self._test_runner.run_multiple(modules=modules, work_dir=workspace.root_path)
        return self._test_runner.run_tests(RunTestsRequest(test_code="\n\n".join(modules)))

    def _run_workspace_tests(self, workspace: WorkspaceConfig, job: JobDefinition) -> RunResult:
        args = [sys.executable, "-m", "pytest"] + (job.run_pytest_args or workspace.preferred_pytest_args)
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            cwd=workspace.root_path,
            timeout=job.timeout,
        )
        output = result.stdout + result.stderr
        coverage = None
        for line in output.splitlines():
            if line.strip().startswith("TOTAL"):
                parts = line.split()
                if parts:
                    coverage = parts[-1]
        return RunResult(output=output, returncode=result.returncode, coverage=coverage)

    def _resolve_target_paths(self, workspace: WorkspaceConfig, target: TestTarget) -> List[str]:
        if target.scope == "repo":
            return self._source_loader.list_python_files(workspace.root_path, include_tests=False)
        if target.scope == "folder":
            return self._source_loader.list_python_files(target.folder, include_tests=False)
        if target.scope == "files":
            return sorted(os.path.abspath(path) for path in target.paths)
        if target.scope == "changed":
            return self._changed_python_files(workspace.root_path)
        raise ValidationError(f"Unsupported target scope: {target.scope}")

    @staticmethod
    def _changed_python_files(workspace_root: str) -> List[str]:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            cwd=workspace_root,
        )
        paths = []
        for line in result.stdout.splitlines():
            if line.endswith(".py") and not os.path.basename(line).startswith("test_"):
                paths.append(os.path.abspath(os.path.join(workspace_root, line)))
        return sorted(paths)

    @staticmethod
    def _target_value(target: TestTarget) -> str:
        if target.scope == "folder":
            return target.folder
        if target.scope == "files":
            return ",".join(target.paths)
        return ""

    @staticmethod
    def _validate_ai_generation_request(job: JobDefinition, policy: AiPolicy) -> None:
        if not job.use_ai_generation:
            return
        if policy.ai_generation != "ask":
            raise ValidationError("AI generation is disabled by policy for this workspace.")

    @staticmethod
    def _validate_ai_repair_request(job: JobDefinition, policy: AiPolicy) -> None:
        if not job.use_ai_repair:
            return
        if policy.ai_repair == "off":
            raise ValidationError("AI repair is disabled by policy for this workspace.")

    @staticmethod
    def _collect_failure_categories(failure_artifacts: List[FailureAnalysisArtifact]) -> List[dict]:
        seen = set()
        categories = []
        for artifact in failure_artifacts:
            for item in artifact.failure_categories:
                key = (item.get("test", ""), item.get("category", ""), item.get("summary", ""))
                if key in seen:
                    continue
                seen.add(key)
                categories.append(item)
        return categories

    def _maybe_suggest_ai_repairs(
        self,
        job: JobDefinition,
        policy: AiPolicy,
        failure_artifacts: List[FailureAnalysisArtifact],
        workspace: WorkspaceConfig,
        profile: AgentProfile,
    ):
        has_candidates = any(
            AgentOrchestrator._has_ai_repair_candidates(artifact.failure_categories)
            for artifact in failure_artifacts
        )
        if not has_candidates:
            return [], False, "skipped", "No AI repair candidates were found."
        if policy.ai_repair == "off":
            return [], False, "blocked", "AI repair is disabled by policy for this workspace."
        if policy.ai_repair == "ask" and not job.use_ai_repair:
            return [], False, "skipped", "AI repair is available but was not requested."
        if policy.ai_repair not in {"ask", "auto"}:
            return [], False, "skipped", "AI repair policy does not allow this flow."

        suggestions = self._orchestrator.suggest_ai_repairs(failure_artifacts, workspace, profile)
        if suggestions:
            return suggestions, True, "used", "AI repair suggestions were generated."
        return [], False, "fallback", "AI repair could not produce suggestions; local repair guidance was used."

    def _preview_cache_key(
        self,
        job: JobDefinition,
        workspace: WorkspaceConfig,
        profile: AgentProfile,
        source_paths: List[str],
        planned_files,
        effective_ai_policy: AiPolicy,
    ) -> Optional[tuple]:
        if job.mode not in {"generate-tests", "update-tests"} or job.output_policy != "preview":
            return None
        source_state = tuple(self._path_signature(path) for path in source_paths)
        test_state = tuple(self._path_signature(item.test_path) for item in planned_files)
        profile_state = (
            profile.name,
            profile.model,
            tuple(profile.roles_enabled),
            profile.input_token_budget,
            profile.output_token_budget,
            profile.failure_mode,
        )
        workspace_state = (
            workspace.root_path,
            workspace.test_root,
            workspace.test_path_strategy,
            workspace.naming_strategy,
            tuple(workspace.source_include),
            tuple(workspace.source_exclude),
            workspace.selected_agent_profile,
            workspace.ai_policy.inherit,
            workspace.ai_policy.ai_generation,
            workspace.ai_policy.ai_repair,
            workspace.ai_policy.ai_explain,
        )
        return (
            job.mode,
            job.target_scope,
            job.target_value,
            job.use_ai_generation,
            job.use_ai_repair,
            tuple(effective_ai_policy.to_dict().items()),
            workspace_state,
            profile_state,
            source_state,
            test_state,
        )

    @staticmethod
    def _path_signature(path: str):
        absolute = os.path.abspath(path)
        if not os.path.exists(absolute):
            return absolute, None, None
        stat = os.stat(absolute)
        return absolute, stat.st_mtime_ns, stat.st_size

    @staticmethod
    def _apply_failure_fixes(content: str, failure: FailureAnalysisArtifact) -> str:
        tree = ast.parse(content)
        specs = WorkspaceJobService._parse_failure_specs(failure)
        lines = content.splitlines()
        replacements = []
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not WorkspaceJobService._matches_failure_test(node.name, failure.failure_tests):
                continue
            transformer = FailureFixTransformer(
                avoid_zero=any("Avoid zero values for divisor-like parameters." in item for item in failure.recommendations),
                clamp_extremes=any("Clamp extreme numeric edge cases for exponent-like parameters." in item for item in failure.recommendations),
                failure_specs=[spec for spec in specs if spec["test"] == node.name],
            )
            updated_node = ast.fix_missing_locations(transformer.visit(ast.fix_missing_locations(node)))
            replacement = ast.unparse(updated_node).splitlines()
            start_line = node.decorator_list[0].lineno - 1 if node.decorator_list else node.lineno - 1
            replacements.append((start_line, node.end_lineno, replacement))

        if not replacements:
            return content

        for start, end, replacement in sorted(replacements, reverse=True):
            lines[start:end] = replacement
        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _matches_failure_test(candidate_name: str, failure_tests: List[str]) -> bool:
        if candidate_name in failure_tests:
            return True
        candidate_core = AgentOrchestrator._infer_source_name(candidate_name)
        for failure_name in failure_tests:
            if candidate_name.startswith(failure_name):
                return True
            if candidate_core and candidate_core == AgentOrchestrator._infer_source_name(failure_name):
                return True
        return False

    @staticmethod
    def _parse_failure_specs(failure: FailureAnalysisArtifact) -> List[dict]:
        specs = []
        output = failure.run_output or "\n".join(failure.failures)
        for line in failure.failures:
            match = re.search(r"::(?P<test>[^\s\[]+)(?:\[(?P<params>[^\]]+)\])?(?:\s+-\s+(?P<reason>.*))?", line)
            if not match:
                continue
            test_name = match.group("test")
            reason = match.group("reason") or ""
            chunk = WorkspaceJobService._failure_chunk(output, test_name, match.group("params") or "")
            combined = "\n".join(part for part in (reason, chunk) if part)
            specs.append({
                "test": test_name,
                "params": match.group("params") or "",
                "reason": reason,
                "chunk": chunk,
                "category": AgentOrchestrator._classify_failure_text(reason or line, combined),
                "actual_literal": WorkspaceJobService._extract_assert_actual_literal(combined),
                "exception_name": WorkspaceJobService._extract_exception_name(combined),
                "did_not_raise": "DID NOT RAISE" in combined,
            })
        return specs

    @staticmethod
    def _failure_chunk(output: str, test_name: str, params: str) -> str:
        if not output:
            return ""
        lines = output.splitlines()
        needle = f"{test_name}[{params}]" if params else test_name
        start = 0
        for index, line in enumerate(lines):
            if needle in line or test_name in line:
                start = index
                break
        end = min(len(lines), start + 120)
        for index in range(start + 1, len(lines)):
            line = lines[index]
            if line.startswith("FAILED ") and test_name not in line:
                end = index
                break
            if line.startswith("________________") and index > start + 3:
                end = index
                break
        return "\n".join(lines[start:end])

    @staticmethod
    def _extract_assert_actual_literal(text: str):
        for line in text.splitlines():
            match = re.search(r"assert\s+(.+?)\s+==\s+(.+)", line.strip())
            if not match:
                continue
            actual_text = match.group(1).strip()
            try:
                return ast.literal_eval(actual_text)
            except (ValueError, SyntaxError):
                if actual_text == "None":
                    return None
        return _NO_REPAIR_VALUE

    @staticmethod
    def _extract_exception_name(text: str) -> str:
        for line in text.splitlines():
            if "DID NOT RAISE" in line:
                continue
            match = _EXCEPTION_NAME_PATTERN.search(line)
            if match:
                return match.group(1).split(".")[-1]
        return ""


_NO_REPAIR_VALUE = object()


class FailureFixTransformer(ast.NodeTransformer):
    def __init__(self, avoid_zero: bool, clamp_extremes: bool, failure_specs: Optional[List[dict]] = None):
        self._avoid_zero = avoid_zero
        self._clamp_extremes = clamp_extremes
        self._failure_specs = failure_specs or []
        self._changed_assert = False
        self._changed_exception = False

    def visit_FunctionDef(self, node):
        node = self._repair_parametrize_rows(node)
        node = self.generic_visit(node)
        if not self._changed_exception:
            node = self._repair_unhandled_exception(node)
        return node

    def visit_AsyncFunctionDef(self, node):
        return self.visit_FunctionDef(node)

    def visit_With(self, node):
        node = self.generic_visit(node)
        actual_exception = self._actual_exception_name()
        if actual_exception:
            for item in node.items:
                call = item.context_expr
                if not self._is_pytest_raises_call(call):
                    continue
                if self._has_did_not_raise():
                    return node.body
                call.args = [ast.Name(id=actual_exception, ctx=ast.Load())]
                self._changed_exception = True
        return node

    def visit_Assert(self, node):
        node = self.generic_visit(node)
        if self._changed_assert:
            return node
        actual = self._actual_literal()
        if actual is _NO_REPAIR_VALUE:
            return node
        if not isinstance(node.test, ast.Compare):
            return node
        if not any(isinstance(op, ast.Eq) for op in node.test.ops):
            return node
        left = node.test.left
        node.test = ast.Compare(
            left=left,
            ops=[ast.Eq()],
            comparators=[ast.Constant(value=actual)],
        )
        self._changed_assert = True
        return node

    def visit_Constant(self, node):
        value = node.value
        if self._avoid_zero and value in (0, 0.0):
            return ast.copy_location(ast.Constant(value=1.0 if isinstance(value, float) else 1), node)
        if self._clamp_extremes and isinstance(value, (int, float)) and abs(value) >= 1000:
            replacement = 10.0 if isinstance(value, float) else 3
            return ast.copy_location(ast.Constant(value=replacement), node)
        return node

    def _repair_parametrize_rows(self, node):
        failed_params = [spec["params"] for spec in self._failure_specs if spec.get("params")]
        if not failed_params:
            return node
        for decorator in node.decorator_list:
            call = decorator
            if not isinstance(call, ast.Call) or not self._is_parametrize_call(call):
                continue
            if len(call.args) < 2 or not isinstance(call.args[1], (ast.List, ast.Tuple)):
                continue
            rows = list(call.args[1].elts)
            kept = []
            changed = False
            for index, row in enumerate(rows):
                if any(self._row_matches_failure_params(row, params, index) for params in failed_params):
                    changed = True
                    continue
                kept.append(row)
            if changed:
                call.args[1].elts = kept
        return node

    def _repair_unhandled_exception(self, node):
        if any(spec.get("params") for spec in self._failure_specs):
            return node
        actual_exception = self._actual_exception_name()
        if not actual_exception or self._has_did_not_raise():
            return node
        if self._function_has_pytest_raises(node):
            return node
        repaired_body = []
        wrapped = False
        for statement in node.body:
            if not wrapped and self._statement_calls_subject(statement):
                repaired_body.append(
                    ast.With(
                        items=[
                            ast.withitem(
                                context_expr=ast.Call(
                                    func=ast.Attribute(value=ast.Name(id="pytest", ctx=ast.Load()), attr="raises", ctx=ast.Load()),
                                    args=[ast.Name(id=actual_exception, ctx=ast.Load())],
                                    keywords=[],
                                ),
                                optional_vars=None,
                            )
                        ],
                        body=[statement],
                    )
                )
                wrapped = True
                self._changed_exception = True
            else:
                repaired_body.append(statement)
        if wrapped:
            node.body = repaired_body
        return node

    @staticmethod
    def _is_parametrize_call(call) -> bool:
        return (
            isinstance(call.func, ast.Attribute)
            and call.func.attr == "parametrize"
            and isinstance(call.func.value, ast.Attribute)
            and call.func.value.attr == "mark"
            and isinstance(call.func.value.value, ast.Name)
            and call.func.value.value.id == "pytest"
        )

    @staticmethod
    def _is_pytest_raises_call(call) -> bool:
        return (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "raises"
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "pytest"
        )

    def _row_matches_failure_params(self, row, params: str, index: int) -> bool:
        if not params:
            return False
        if f"expected{index}" in params or f"raises{index}" in params:
            return True
        values = row.elts if isinstance(row, (ast.Tuple, ast.List)) else [row]
        rendered = [self._render_param_value(value) for value in values]
        if "-".join(rendered) == params:
            return True
        parts = params.split("-")
        return len(rendered) == len(parts) and all(part == "" or part == value for part, value in zip(parts, rendered))

    @staticmethod
    def _render_param_value(node) -> str:
        if isinstance(node, ast.Constant):
            return "None" if node.value is None else str(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant):
            return f"-{node.operand.value}"
        return ""

    def _actual_literal(self):
        for spec in self._failure_specs:
            if spec.get("params"):
                continue
            value = spec.get("actual_literal", _NO_REPAIR_VALUE)
            if value is not _NO_REPAIR_VALUE:
                return value
        return _NO_REPAIR_VALUE

    def _actual_exception_name(self) -> str:
        for spec in self._failure_specs:
            if spec.get("params") or spec.get("category") == "missing_import_or_name":
                continue
            value = spec.get("exception_name", "")
            if value:
                return value
        return ""

    def _has_did_not_raise(self) -> bool:
        return any(spec.get("did_not_raise") for spec in self._failure_specs)

    def _function_has_pytest_raises(self, node) -> bool:
        return any(
            self._is_pytest_raises_call(item.context_expr)
            for child in ast.walk(node)
            if isinstance(child, ast.With)
            for item in child.items
        )

    @staticmethod
    def _statement_calls_subject(statement) -> bool:
        if isinstance(statement, ast.Assign):
            return isinstance(statement.value, ast.Call)
        if isinstance(statement, ast.Expr):
            return isinstance(statement.value, ast.Call)
        return False
