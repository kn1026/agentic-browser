from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from agentic_browser.browser import Browser

try:
    from agentic_browser.browser import PlaywrightBrowser
except Exception:  # pragma: no cover
    PlaywrightBrowser = None  # type: ignore
from agentic_browser.planner import Planner
from agentic_browser.types import Observation, Receipt, Step


@dataclass
class AgentResult:
    goal: str
    ok: bool
    final_reason: str
    receipts: list[Receipt] = field(default_factory=list)
    steps_ok: int = 0
    steps_failed: int = 0
    summary: str = ""
    viewer_path: str = ""

    def to_dict(self) -> dict:
        d = {
            "goal": self.goal,
            "ok": self.ok,
            "final_reason": self.final_reason,
            "steps_ok": self.steps_ok,
            "steps_failed": self.steps_failed,
            "summary": self.summary,
            "receipts": [r.to_dict() for r in self.receipts],
        }
        if self.viewer_path:
            d["viewer_path"] = self.viewer_path
        return d


class Agent:
    def __init__(
        self,
        dry_run: bool = True,
        max_steps: int = 6,
        receipts_dir: str | Path | None = None,
        write_viewer: bool = False,
        viewer_path: str | Path | None = None,
    ) -> None:
        if (not dry_run) and PlaywrightBrowser is not None:
            try:
                self.browser = PlaywrightBrowser()
            except Exception:
                self.browser = Browser(dry_run=True)
        else:
            self.browser = Browser(dry_run=True)
        self.planner = Planner()
        self.max_steps = max_steps
        self.receipts_dir = Path(receipts_dir or "receipts")
        self.receipts_dir.mkdir(parents=True, exist_ok=True)
        self.write_viewer = write_viewer
        self.viewer_path = Path(viewer_path) if viewer_path else None

    def run(self, goal: str) -> AgentResult:
        obs: Observation | None = None
        receipts: list[Receipt] = []
        last_receipt: Receipt | None = None
        final = "no steps"
        ok = False

        for i in range(self.max_steps):
            step = self.planner.next_step(
                goal, obs, i, self.max_steps, last_receipt=last_receipt
            )
            receipt = self._act(step)
            receipts.append(receipt)
            last_receipt = receipt
            if receipt.observation is not None:
                obs = receipt.observation
            if step.kind in ("done", "fail"):
                ok = step.kind == "done" and receipt.ok
                final = step.reason or receipt.detail
                break
        else:
            final = "exhausted steps"
            ok = False

        steps_ok = sum(1 for r in receipts if r.ok)
        steps_failed = sum(1 for r in receipts if not r.ok)
        kinds = [r.step.kind for r in receipts]
        summary = (
            f"steps={len(receipts)} ok={steps_ok} failed={steps_failed} "
            f"kinds={kinds} final={final[:160]}"
        )
        result = AgentResult(
            goal=goal,
            ok=ok,
            final_reason=final,
            receipts=receipts,
            steps_ok=steps_ok,
            steps_failed=steps_failed,
            summary=summary,
        )
        self._write_receipts(result)
        if self.write_viewer:
            from agentic_browser.viewer import default_viewer_path, write_viewer

            path = self.viewer_path or default_viewer_path(self.receipts_dir)
            out = write_viewer(result, path)
            result.viewer_path = str(out)
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
