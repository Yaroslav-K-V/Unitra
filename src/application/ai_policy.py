from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

from src.application.exceptions import ValidationError


GENERATION_MODES = {"off", "ask"}
ASSIST_MODES = {"off", "ask", "auto"}


@dataclass(frozen=True)
class AiPolicy:
    ai_generation: str = "off"
    ai_repair: str = "ask"
    ai_explain: str = "ask"

    def __post_init__(self):
        self.validate()

    @classmethod
    def from_dict(cls, raw: Optional[Mapping[str, Any]], base: Optional["AiPolicy"] = None) -> "AiPolicy":
        base = base or cls()
        raw = raw or {}
        return cls(
            ai_generation=str(raw.get("ai_generation", base.ai_generation)),
            ai_repair=str(raw.get("ai_repair", base.ai_repair)),
            ai_explain=str(raw.get("ai_explain", base.ai_explain)),
        )

    def to_dict(self) -> Dict[str, str]:
        return {
            "ai_generation": self.ai_generation,
            "ai_repair": self.ai_repair,
            "ai_explain": self.ai_explain,
        }

    def validate(self) -> None:
        if self.ai_generation not in GENERATION_MODES:
            raise ValidationError("ai_generation must be one of: off, ask")
        if self.ai_repair not in ASSIST_MODES:
            raise ValidationError("ai_repair must be one of: off, ask, auto")
        if self.ai_explain not in ASSIST_MODES:
            raise ValidationError("ai_explain must be one of: off, ask, auto")


@dataclass(frozen=True)
class WorkspaceAiPolicy:
    inherit: bool = True
    ai_generation: str = "off"
    ai_repair: str = "ask"
    ai_explain: str = "ask"

    def __post_init__(self):
        self.policy.validate()

    @property
    def policy(self) -> AiPolicy:
        return AiPolicy(
            ai_generation=self.ai_generation,
            ai_repair=self.ai_repair,
            ai_explain=self.ai_explain,
        )

    @classmethod
    def from_dict(
        cls,
        raw: Optional[Mapping[str, Any]],
        base: Optional[AiPolicy] = None,
    ) -> "WorkspaceAiPolicy":
        raw = raw or {}
        base = base or AiPolicy()
        inherit = bool(raw.get("inherit", True))
        policy = AiPolicy.from_dict(raw, base=base)
        return cls(
            inherit=inherit,
            ai_generation=policy.ai_generation,
            ai_repair=policy.ai_repair,
            ai_explain=policy.ai_explain,
        )

    def effective(self, global_policy: AiPolicy) -> AiPolicy:
        return global_policy if self.inherit else self.policy

    def source(self) -> str:
        return "global" if self.inherit else "workspace"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "inherit": self.inherit,
            "ai_generation": self.ai_generation,
            "ai_repair": self.ai_repair,
            "ai_explain": self.ai_explain,
        }
