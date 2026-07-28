from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from agentic_browser.browser import Browser
from agentic_browser.planner import Planner
from agentic_browser.types import Observation, Receipt, Step


@dataclass
class AgentResult:
    goal: str
    ok: bool
    final_reason: str
    receipts: list[Receipt] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "ok": self.ok,
            "final_reason": self.final_reason,
            "receipts": [r.to_dict() for r in self.receipts],
        }


class Agent:
    def __init__(
        self,
        dry_run: bool = True,
        max_steps: int = 6,
        receipts_dir: str | Path | None = None,
    ) -> None:
        self.browser = Browser(dry_run=dry_run)
        self.planner = Planner()
        self.max_steps = max_steps
        self.receipts_dir = Path(receipts_dir or "receipts")
        self.receipts_dir.mkdir(parents=True, exist_ok=True)

    def run(self, goal: str) -> AgentResult:
        obs: Observation | None = None
        receipts: list[Receipt] = []
        final = "no steps"
        ok = False

        for i in range(self.max_steps):
            step = self.planner.next_step(goal, obs, i, self.max_steps)
            receipt = self._act(step)
            receipts.append(receipt)
            if receipt.observation is not None:
                obs = receipt.observation
            if step.kind in ("done", "fail"):
                ok = step.kind == "done" and receipt.ok
                final = step.reason or receipt.detail
                break
        else:
            final = "exhausted steps"
            ok = False

        result = AgentResult(goal=goal, ok=ok, final_reason=final, receipts=receipts)
        self._write_receipts(result)
        return result

    def _act(self, step: Step) -> Receipt:
        try:
            if step.kind == "goto":
                obs = self.browser.goto(step.target)
                return Receipt(step=step, ok=True, detail=f"opened {obs.url}", observation=obs)
            if step.kind == "extract_text":
                obs = self.browser.extract_text()
                return Receipt(step=step, ok=True, detail=obs.text_preview[:200], observation=obs)
            if step.kind == "click":
                obs = self.browser.click(step.target)
                return Receipt(step=step, ok=True, detail=f"clicked {step.target}", observation=obs)
            if step.kind == "type":
                obs = self.browser.type_text(step.target, step.value)
                return Receipt(step=step, ok=True, detail=f"typed into {step.target}", observation=obs)
            if step.kind == "screenshot":
                path = self.browser.screenshot(step.target or "shot.png")
                return Receipt(step=step, ok=True, detail=f"screenshot {path}")
            if step.kind == "wait":
                return Receipt(step=step, ok=True, detail="waited")
            if step.kind == "think":
                return Receipt(step=step, ok=True, detail=step.reason)
            if step.kind == "done":
                return Receipt(step=step, ok=True, detail=step.reason)
            if step.kind == "fail":
                return Receipt(step=step, ok=False, detail=step.reason or "failed")
            return Receipt(step=step, ok=False, detail=f"unknown step {step.kind}")
        except Exception as e:
            return Receipt(step=step, ok=False, detail=str(e))

    def _write_receipts(self, result: AgentResult) -> Path:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self.receipts_dir / f"run_{ts}.json"
        path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        return path

    def close(self) -> None:
        self.browser.close()
