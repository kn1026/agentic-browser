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
    viewer_frame_writes: int = 0
    viewer_phases_seen: list[str] = field(default_factory=list)
    viewer_densities_seen: list[str] = field(default_factory=list)

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
        if self.viewer_frame_writes:
            d["viewer_frame_writes"] = self.viewer_frame_writes
            d["viewer_phases_seen"] = list(self.viewer_phases_seen)
            d["viewer_densities_seen"] = list(self.viewer_densities_seen)
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
        phases_seen: list[str] = []
        dens_seen: list[str] = []
        frame_writes = 0
        viewer_out: Path | None = None

        if self.write_viewer:
            from agentic_browser.viewer import default_viewer_path

            viewer_out = self.viewer_path or default_viewer_path(self.receipts_dir)
            # Fresh progressive log for this run (same path may be reused).
            live_path = viewer_out.with_suffix(".live.jsonl")
            if live_path.is_file():
                live_path.unlink()

        for i in range(self.max_steps):
            step = self.planner.next_step(
                goal, obs, i, self.max_steps, last_receipt=last_receipt
            )
            receipt = self._act(step)
            receipts.append(receipt)
            last_receipt = receipt
            if receipt.observation is not None:
                obs = receipt.observation

            terminal = step.kind in ("done", "fail")
            if terminal:
                ok = step.kind == "done" and receipt.ok
                final = step.reason or receipt.detail

            if self.write_viewer and viewer_out is not None:
                from agentic_browser.viewer import write_viewer_progress

                partial_ok = ok if terminal else False
                partial = AgentResult(
                    goal=goal,
                    ok=partial_ok,
                    final_reason=final if terminal else (receipt.detail or step.kind),
                    receipts=list(receipts),
                    steps_ok=sum(1 for r in receipts if r.ok),
                    steps_failed=sum(1 for r in receipts if not r.ok),
                    summary="",
                )
                # Mid-run frames stay non-terminal for chrome; final write settles.
                fr = write_viewer_progress(
                    partial,
                    viewer_out,
                    write_index=frame_writes,
                    terminal=terminal,
                    final_result=None,
                )
                frame_writes += 1
                phases_seen.append(fr.phase)
                dens_seen.append(fr.density)

            if terminal:
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
            viewer_frame_writes=frame_writes,
            viewer_phases_seen=phases_seen,
            viewer_densities_seen=dens_seen,
        )
        self._write_receipts(result)
        if self.write_viewer and viewer_out is not None:
            from agentic_browser.viewer import write_viewer, write_viewer_progress

            # Final adaptive snapshot + full frame JSON (end-of-run trust surface).
            out = write_viewer(result, viewer_out, also_json=True)
            # Append terminal progress line with settled frame (dedupe index).
            write_viewer_progress(
                result,
                out,
                write_index=frame_writes,
                terminal=True,
                final_result=result,
                html=False,
            )
            result.viewer_path = str(out)
            result.viewer_frame_writes = frame_writes + 1
            # Re-read settled phase/density onto the seen lists if missing.
            from agentic_browser.viewer import build_frame

            settled = build_frame(result)
            if not phases_seen or phases_seen[-1] != settled.phase:
                result.viewer_phases_seen = list(phases_seen) + [settled.phase]
                result.viewer_densities_seen = list(dens_seen) + [settled.density]
            else:
                result.viewer_phases_seen = list(phases_seen)
                result.viewer_densities_seen = list(dens_seen)
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
