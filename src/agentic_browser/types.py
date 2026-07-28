from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


StepKind = Literal[
    "goto",
    "click",
    "type",
    "extract_text",
    "screenshot",
    "wait",
    "done",
    "fail",
    "think",
]


@dataclass
class Observation:
    url: str
    title: str
    text_preview: str
    interactive: list[dict[str, Any]] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Step:
    kind: StepKind
    target: str = ""
    value: str = ""
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Receipt:
    step: Step
    ok: bool
    detail: str = ""
    observation: Observation | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step.to_dict(),
            "ok": self.ok,
            "detail": self.detail,
            "observation": self.observation.to_dict() if self.observation else None,
        }
