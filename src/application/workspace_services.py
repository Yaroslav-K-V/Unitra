import ast
import os
import re
import subprocess
from dataclasses import replace
from typing import Dict, List, Optional

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
    def __init__(self, source_loader, planner):
        self._source_loader = source_loader
        self._planner = planner

    def orchestrate(self, workspace: WorkspaceConfig, profile: AgentProfile, source_paths: List[str]) -> List[GenerationArtifact]:
        planned_files = self._planner.plan_paths(workspace, source_paths)
        artifacts = []
        for planned in planned_files:
            analysis = self._analyze(planned.source_path)
            test_plan = self._plan(planned.source_path, planned.test_path, analysis)
            generated = self._generate(planned.source_path, planned.test_path)
            notes = self._review(generated.generated_code, test_plan, profile)
            artifacts.append(
                GenerationArtifact(
                    source_path=planned.source_path,
                    test_path=planned.test_path,
                    generated_code=generated.generated_code,
                    reviewer_notes=notes,
                )
            )
        return artifacts

    def analyze_failures(self, run_output: str, write_plans, workspace: WorkspaceConfig, profile: AgentProfile) -> List[FailureAnalysisArtifact]:
        failed_lines = [line.strip() for line in run_output.splitlines() if line.strip().startswith("FAILED ")]
        failure_tests = self._extract_failure_tests(failed_lines)
        artifacts = []
        for plan in write_plans:
            recommendations = []
            for failure in failed_lines:
                if "ZeroDivision" in failure or "divide by zero" in failure.lower():
                    recommendations.append("Avoid zero values for divisor-like parameters.")
                if "OverflowError" in failure:
                    recommendations.append("Clamp extreme numeric edge cases for exponent-like parameters.")
            llm_context = None
            if failure_tests:
                llm_context = self._build_llm_fallback_context(
                    workspace=workspace,
                    profile=profile,
                    source_path=plan.source_path,
                    test_path=plan.test_path,
                    generated_content=plan.generated_content,
                    failure_tests=failure_tests,
                    recommendations=recommendations,
                )
            artifacts.append(
                FailureAnalysisArtifact(
                    test_path=plan.test_path,
                    failures=failed_lines,
                    recommendations=recommendations or ["Inspect generated edge cases and tighten parameter values."],
                    failure_tests=failure_tests,
                    llm_fallback_context=llm_context,
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

    def _generate(self, source_path: str, test_path: str) -> GenerationArtifact:
        bundle = self._source_loader.load_file(source_path)
        functions = parse_functions(bundle.source_code)
        classes = parse_classes(bundle.source_code)
        test_code = generate_test_module(functions, classes)
        conftest = generate_conftest(classes) if classes else ""
        managed = [
            MANAGED_HEADER,
            "",
            test_code.strip(),
        ]
        if conftest:
            managed.extend(["", "# Suggested conftest.py content", conftest.strip()])
        managed.extend(["", USER_BLOCK_BEGIN, USER_BLOCK_END, ""])
        return GenerationArtifact(
            source_path=source_path,
            test_path=test_path,
            generated_code="\n".join(managed),
            reviewer_notes=[],
        )

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

    def _build_llm_fallback_context(
        self,
        workspace: WorkspaceConfig,
        profile: AgentProfile,
        source_path: str,
        test_path: str,
        generated_content: str,
        failure_tests: List[str],
        recommendations: List[str],
    ) -> dict:
        source_bundle = self._source_loader.load_file(source_path)
        source_snippets = self._extract_relevant_source_snippets(source_bundle.source_code, failure_tests)
        test_snippets = self._extract_relevant_test_snippets(generated_content, failure_tests)
        context = {
            "source_path": source_path,
            "test_path": test_path,
            "failure_tests": failure_tests,
            "recommendations": recommendations,
            "source_snippets": source_snippets,
            "test_snippets": test_snippets,
            "estimated_input_tokens": 0,
            "expected_output_tokens": profile.output_token_budget,
            "truncated": False,
        }
        context["estimated_input_tokens"] = self._estimate_tokens(str(context))
        while context["estimated_input_tokens"] > profile.input_token_budget and (context["source_snippets"] or context["test_snippets"]):
            context["truncated"] = True
            if len(context["test_snippets"]) > 1:
                context["test_snippets"] = context["test_snippets"][:-1]
            elif len(context["source_snippets"]) > 1:
                context["source_snippets"] = context["source_snippets"][:-1]
            elif context["source_snippets"]:
                context["source_snippets"][0] = context["source_snippets"][0][: max(200, len(context["source_snippets"][0]) // 2)]
            elif context["test_snippets"]:
                context["test_snippets"][0] = context["test_snippets"][0][: max(200, len(context["test_snippets"][0]) // 2)]
            context["estimated_input_tokens"] = self._estimate_tokens(str(context))
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
    def _estimate_tokens(text: str) -> int:
        return max(1, len(text) // 4)


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
        self._preview_cache = {}

    def list_jobs(self) -> List[str]:
        return self._job_repository.list_names()

    def run_job(self, name: str, target_value: str = "", output_policy: str = "") -> JobRunResult:
        job = self._job_repository.load(name)
        if target_value:
            job = JobDefinition(
                name=job.name,
                mode=job.mode,
                target_scope=job.target_scope,
                target_value=target_value,
                output_policy=output_policy or job.output_policy,
                run_pytest_args=job.run_pytest_args,
                coverage=job.coverage,
                timeout=job.timeout,
                agent_profile=job.agent_profile,
            )
        return self.execute(job)

    def execute(self, job: JobDefinition) -> JobRunResult:
        workspace = self._workspace_repository.load_config()
        profile = self._agent_repository.load(job.agent_profile)
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
            preview_key = self._preview_cache_key(job, workspace, profile, source_paths, list(planned_lookup.values()))
            if preview_key:
                cached = self._preview_cache.get(preview_key)
                if cached is not None:
                    planned_files, written = cached
                    preview_cached = True
            if not preview_cached:
                artifacts = self._orchestrator.orchestrate(workspace, profile, source_paths)
                for artifact in artifacts:
                    planned_files.append(
                        self._planner.build_write_plan(
                            planned_lookup[artifact.source_path],
                            artifact.generated_code,
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
            history_id=history_id,
        )

    def generate_tests(self, target: TestTarget, write: bool) -> JobRunResult:
        job = JobDefinition(
            name="ad-hoc-generate",
            mode="generate-tests",
            target_scope=target.scope,
            target_value=self._target_value(target),
            output_policy="write" if write else "preview",
        )
        return self.execute(job)

    def update_tests(self, target: TestTarget, write: bool) -> JobRunResult:
        job = JobDefinition(
            name="ad-hoc-update",
            mode="update-tests",
            target_scope=target.scope,
            target_value=self._target_value(target),
            output_policy="write" if write else "preview",
        )
        return self.execute(job)

    def fix_failed_tests(self, target: TestTarget, write: bool) -> JobRunResult:
        job = JobDefinition(
            name="ad-hoc-fix",
            mode="fix-failed-tests",
            target_scope=target.scope,
            target_value=self._target_value(target),
            output_policy="write" if write else "preview",
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
        args = ["pytest"] + (job.run_pytest_args or workspace.preferred_pytest_args)
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

    def _preview_cache_key(self, job: JobDefinition, workspace: WorkspaceConfig, profile: AgentProfile, source_paths: List[str], planned_files) -> Optional[tuple]:
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
        )
        return (
            job.mode,
            job.target_scope,
            job.target_value,
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
            )
            updated_node = transformer.visit(ast.fix_missing_locations(node))
            replacement = ast.unparse(updated_node).splitlines()
            replacements.append((node.lineno - 1, node.end_lineno, replacement))

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


class FailureFixTransformer(ast.NodeTransformer):
    def __init__(self, avoid_zero: bool, clamp_extremes: bool):
        self._avoid_zero = avoid_zero
        self._clamp_extremes = clamp_extremes

    def visit_Constant(self, node):
        value = node.value
        if self._avoid_zero and value in (0, 0.0):
            return ast.copy_location(ast.Constant(value=1.0 if isinstance(value, float) else 1), node)
        if self._clamp_extremes and isinstance(value, (int, float)) and abs(value) >= 1000:
            replacement = 10.0 if isinstance(value, float) else 3
            return ast.copy_location(ast.Constant(value=replacement), node)
        return node
