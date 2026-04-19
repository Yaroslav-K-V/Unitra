import os

from src.application.exceptions import ValidationError
from src.application.workspace_models import JobDefinition
from src.infrastructure.simple_toml import dumps, loads


class JobRepository:
    def __init__(self, jobs_dir: str):
        self.jobs_dir = jobs_dir

    def save(self, job: JobDefinition) -> JobDefinition:
        os.makedirs(self.jobs_dir, exist_ok=True)
        path = os.path.join(self.jobs_dir, f"{job.name}.toml")
        content = dumps({
            "job": {
                "name": job.name,
                "mode": job.mode,
                "target_scope": job.target_scope,
                "target_value": job.target_value,
                "output_policy": job.output_policy,
                "run_pytest_args": job.run_pytest_args,
                "coverage": job.coverage,
                "timeout": job.timeout,
                "agent_profile": job.agent_profile,
                "use_ai_generation": job.use_ai_generation,
                "use_ai_repair": job.use_ai_repair,
            }
        })
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return job

    def load(self, name: str) -> JobDefinition:
        path = os.path.join(self.jobs_dir, f"{name}.toml")
        if not os.path.exists(path):
            raise ValidationError(f"Job `{name}` not found")
        raw = loads(self._read(path)).get("job", {})
        return JobDefinition(
            name=raw.get("name", name),
            mode=raw.get("mode", "generate-tests"),
            target_scope=raw.get("target_scope", "repo"),
            target_value=raw.get("target_value", ""),
            output_policy=raw.get("output_policy", "preview"),
            run_pytest_args=list(raw.get("run_pytest_args", [])),
            coverage=bool(raw.get("coverage", False)),
            timeout=int(raw.get("timeout", 30)),
            agent_profile=raw.get("agent_profile", "default"),
            use_ai_generation=bool(raw.get("use_ai_generation", False)),
            use_ai_repair=bool(raw.get("use_ai_repair", False)),
        )

    def list_names(self):
        if not os.path.isdir(self.jobs_dir):
            return []
        return sorted(filename[:-5] for filename in os.listdir(self.jobs_dir) if filename.endswith(".toml"))

    def list_jobs(self):
        return [self.load(name) for name in self.list_names()]

    @staticmethod
    def _read(path: str) -> str:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
