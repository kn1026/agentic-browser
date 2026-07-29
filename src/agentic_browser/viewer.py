"""Adaptive human-focus viewer — transforms with goal / phase / confidence.

Not a static debug dump. Density and layout shift as the agent moves
navigate → act → extract → done|fail. Substrate receipts feed the surface;
the product bet is the transform, not more RPA chrome.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from agentic_browser.agent import AgentResult
from agentic_browser.types import Receipt

Phase = Literal["navigate", "act", "extract", "done", "fail", "idle"]

_PHASE_ORDER = ("idle", "navigate", "act", "extract", "done", "fail")


@dataclass
class ViewerFrame:
    """One adaptive chrome state derived from a run (or mid-run snapshot)."""

    goal: str
    phase: Phase
    confidence: float
    ok: bool | None
    next_action: str
    last_step_kind: str
    last_detail: str
    step_index: int
    step_total: int
    steps_ok: int
    steps_failed: int
    kinds: list[str] = field(default_factory=list)
    preview: str = ""
    url: str = ""
    final_reason: str = ""
    density: str = "calm"  # calm | focus | dense | settle
    trust_line: str = ""
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "phase": self.phase,
            "confidence": self.confidence,
            "ok": self.ok,
            "next_action": self.next_action,
            "last_step_kind": self.last_step_kind,
            "last_detail": self.last_detail,
            "step_index": self.step_index,
            "step_total": self.step_total,
            "steps_ok": self.steps_ok,
            "steps_failed": self.steps_failed,
            "kinds": list(self.kinds),
            "preview": self.preview,
            "url": self.url,
            "final_reason": self.final_reason,
            "density": self.density,
            "trust_line": self.trust_line,
            "summary": self.summary,
        }


def _clip(s: str, n: int = 220) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[: n - 1].rstrip() + "…"


def _phase_from_receipts(receipts: list[Receipt], terminal_ok: bool | None) -> Phase:
    if not receipts:
        return "idle"
    kinds = [r.step.kind for r in receipts]
    last = kinds[-1]
    if last == "fail" or (terminal_ok is False and last in ("fail", "done")):
        if last == "fail" or terminal_ok is False:
            # done with ok=False still settle as fail surface
            if last == "fail" or terminal_ok is False:
                return "fail" if (last == "fail" or terminal_ok is False) else "done"
    if last == "done":
        return "done" if terminal_ok is not False else "fail"
    if last == "fail":
        return "fail"
    if last == "extract_text":
        return "extract"
    if last in ("click", "type", "screenshot", "wait", "think"):
        return "act"
    if last == "goto":
        return "navigate"
    # fall back to dominant progress
    if "extract_text" in kinds:
        return "extract"
    if any(k in kinds for k in ("click", "type")):
        return "act"
    if "goto" in kinds:
        return "navigate"
    return "idle"


def _confidence(receipts: list[Receipt], phase: Phase, ok: bool | None) -> float:
    if not receipts:
        return 0.15
    last = receipts[-1]
    base = 0.72 if last.ok else 0.28
    # successful streak lifts trust; failures pull it down
    streak = 0
    for r in reversed(receipts):
        if r.ok:
            streak += 1
        else:
            break
    base += min(0.18, streak * 0.04)
    if phase == "done" and ok:
        base = max(base, 0.9)
    if phase == "fail" or ok is False:
        base = min(base, 0.35)
    if phase == "navigate":
        base = min(base, 0.55) if last.ok else base
    return round(max(0.05, min(0.99, base)), 2)


def _density_for(phase: Phase, confidence: float) -> str:
    if phase in ("done", "fail"):
        return "settle"
    if phase == "navigate":
        return "calm"
    if phase == "act":
        return "focus"
    if phase == "extract":
        return "dense" if confidence >= 0.5 else "focus"
    return "calm"


def _trust_line(phase: Phase, confidence: float, ok: bool | None, last: Receipt | None) -> str:
    if phase == "idle":
        return "Waiting for a goal."
    if phase == "navigate":
        return "Opening the page — chrome stays light until we land."
    if phase == "act":
        if last and last.ok:
            return "Action landed. Showing only the move that matters."
        if last and not last.ok:
            return "Action missed — surface the failure, no blind retry theater."
        return "Acting on a matched control."
    if phase == "extract":
        return "Reading the page — denser preview, still human-first."
    if phase == "done" and ok:
        return "Done. Quiet settle state — trust the outcome, not the thrash."
    if phase == "fail" or ok is False:
        return "Stopped. Failure is visible so you can steer."
    return f"Confidence {int(confidence * 100)}%."


def _next_action(receipts: list[Receipt], phase: Phase, result: AgentResult) -> str:
    if phase == "done":
        return "settled"
    if phase == "fail":
        return "stopped"
    if not receipts:
        return "start"
    last = receipts[-1]
    kind = last.step.kind
    if kind == "goto":
        return "observe / decide next act"
    if kind == "click":
        return "phase-advance or finish"
    if kind == "type":
        return "confirm field / continue"
    if kind == "extract_text":
        return "finish on extract"
    return result.summary.split("final=")[-1][:80] if result.summary else kind


def build_frame(result: AgentResult) -> ViewerFrame:
    """Derive adaptive chrome from a finished (or partial) AgentResult."""
    receipts = list(result.receipts or [])
    terminal_ok: bool | None
    if receipts and receipts[-1].step.kind in ("done", "fail"):
        terminal_ok = result.ok
    elif receipts:
        terminal_ok = None
    else:
        terminal_ok = None

    phase = _phase_from_receipts(receipts, terminal_ok)
    # If last is done but ok False, prefer fail surface
    if receipts and receipts[-1].step.kind == "done" and result.ok is False:
        phase = "fail"
    if receipts and receipts[-1].step.kind == "fail":
        phase = "fail"

    conf = _confidence(receipts, phase, result.ok if terminal_ok is not None else None)
    density = _density_for(phase, conf)
    last = receipts[-1] if receipts else None
    kinds = [r.step.kind for r in receipts]
    preview = ""
    url = ""
    if last and last.observation is not None:
        preview = _clip(last.observation.text_preview or "", 280)
        url = last.observation.url or ""
    elif last:
        preview = _clip(last.detail or "", 200)

    return ViewerFrame(
        goal=result.goal,
        phase=phase,
        confidence=conf,
        ok=result.ok if terminal_ok is not None else None,
        next_action=_next_action(receipts, phase, result),
        last_step_kind=(last.step.kind if last else ""),
        last_detail=_clip(last.detail if last else "", 180),
        step_index=len(receipts),
        step_total=max(len(receipts), 1),
        steps_ok=result.steps_ok,
        steps_failed=result.steps_failed,
        kinds=kinds,
        preview=preview,
        url=url,
        final_reason=_clip(result.final_reason or "", 200),
        density=density,
        trust_line=_trust_line(phase, conf, result.ok if terminal_ok is not None else None, last),
        summary=result.summary or "",
    )


def frames_across_run(result: AgentResult) -> list[ViewerFrame]:
    """Replay prefixes of receipts so density/layout shifts are testable."""
    out: list[ViewerFrame] = []
    acc: list[Receipt] = []
    for r in result.receipts:
        acc.append(r)
        terminal = r.step.kind in ("done", "fail")
        partial = AgentResult(
            goal=result.goal,
            ok=result.ok if terminal else False,
            final_reason=result.final_reason if terminal else (r.detail or r.step.kind),
            receipts=list(acc),
            steps_ok=sum(1 for x in acc if x.ok),
            steps_failed=sum(1 for x in acc if not x.ok),
            summary=result.summary if terminal else "",
        )
        if not terminal:
            # mid-run: ok unknown
            partial.ok = False
            # build_frame uses last kind; force non-terminal interpretation
            fr = build_frame(partial)
            # override ok to None for mid frames
            fr.ok = None
            if fr.phase in ("done", "fail") and r.step.kind not in ("done", "fail"):
                # should not happen
                pass
            out.append(fr)
        else:
            out.append(build_frame(result))
    if not out:
        out.append(build_frame(result))
    return out


def render_html(frame: ViewerFrame, *, title: str = "agentic-browser viewer") -> str:
    """Minimal premium HTML — phase drives data-phase + density class (layout shifts)."""
    g = html.escape(frame.goal)
    phase = html.escape(frame.phase)
    density = html.escape(frame.density)
    conf_pct = int(round(frame.confidence * 100))
    trust = html.escape(frame.trust_line)
    nxt = html.escape(frame.next_action)
    last_k = html.escape(frame.last_step_kind or "—")
    last_d = html.escape(frame.last_detail or "—")
    preview = html.escape(frame.preview or "")
    url = html.escape(frame.url or "")
    final = html.escape(frame.final_reason or "")
    kinds = html.escape(" → ".join(frame.kinds) if frame.kinds else "—")
    ok_label = (
        "ok"
        if frame.ok is True
        else ("fail" if frame.ok is False else "running")
    )
    show_preview = frame.density in ("dense", "settle", "focus") and bool(frame.preview)
    show_steps = frame.density in ("focus", "dense", "settle")
    show_final = frame.density == "settle" or frame.phase in ("done", "fail")

    preview_block = (
        f'<section class="preview" data-show="1"><h2>Page</h2><p class="url">{url}</p>'
        f'<p class="body">{preview}</p></section>'
        if show_preview
        else '<section class="preview" data-show="0" hidden></section>'
    )
    steps_block = (
        f'<section class="steps" data-show="1"><h2>Path</h2><p class="kinds">{kinds}</p>'
        f"<p class=\"meta\">{frame.steps_ok} ok · {frame.steps_failed} failed · "
        f"step {frame.step_index}</p></section>"
        if show_steps
        else '<section class="steps" data-show="0" hidden></section>'
    )
    final_block = (
        f'<section class="final" data-show="1"><h2>Outcome</h2><p>{final}</p></section>'
        if show_final and final
        else '<section class="final" data-show="0" hidden></section>'
    )

    return f"""<!DOCTYPE html>
<html lang="en" data-phase="{phase}" data-density="{density}" data-ok="{html.escape(ok_label)}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #f7f7f5;
      --fg: #141414;
      --muted: #6b6b6b;
      --line: #e4e4e0;
      --card: #ffffff;
      --accent: #141414;
      --ok: #1a1a1a;
      --bad: #4a4a4a;
      --radius: 14px;
      --pad: 1.25rem;
      --max: 40rem;
      --track: 0.35;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #0e0e0e;
        --fg: #f2f2f0;
        --muted: #9a9a96;
        --line: #2a2a28;
        --card: #161616;
        --accent: #f2f2f0;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font: 15px/1.45 ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
      background: var(--bg);
      color: var(--fg);
      min-height: 100vh;
    }}
    /* density = layout transform (not a static dump) */
    body {{ padding: 2rem 1.25rem 3rem; }}
    [data-density="calm"] .shell {{ max-width: 28rem; }}
    [data-density="focus"] .shell {{ max-width: 34rem; }}
    [data-density="dense"] .shell {{ max-width: var(--max); }}
    [data-density="settle"] .shell {{ max-width: 30rem; }}
    [data-density="calm"] .steps,
    [data-density="calm"] .preview {{ display: none !important; }}
    [data-density="focus"] .preview .body {{
      display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
    }}
    [data-density="dense"] .preview .body {{ -webkit-line-clamp: 8; }}
    [data-density="settle"] .action {{ opacity: 0.85; }}
    [data-phase="fail"] .badge {{ letter-spacing: 0.04em; }}
    [data-phase="done"] .hero {{ border-bottom-width: 2px; }}
    .shell {{
      margin: 0 auto;
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: var(--pad);
      transition: max-width 160ms ease;
    }}
    header.hero {{
      border-bottom: 1px solid var(--line);
      padding-bottom: 1rem;
      margin-bottom: 1rem;
    }}
    .eyebrow {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin: 0 0 0.4rem;
    }}
    h1 {{
      font-size: 1.15rem;
      font-weight: 600;
      letter-spacing: -0.02em;
      margin: 0 0 0.75rem;
      line-height: 1.3;
    }}
    .row {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      align-items: center;
    }}
    .badge {{
      font-size: 12px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 0.2rem 0.65rem;
      color: var(--fg);
    }}
    .conf {{
      flex: 1 1 8rem;
      min-width: 7rem;
    }}
    .conf .bar {{
      height: 4px;
      background: var(--line);
      border-radius: 999px;
      overflow: hidden;
      margin-top: 0.25rem;
    }}
    .conf .bar > i {{
      display: block;
      height: 100%;
      width: {conf_pct}%;
      background: var(--accent);
      opacity: calc(0.45 + {frame.confidence} * 0.55);
    }}
    .conf label {{ font-size: 11px; color: var(--muted); }}
    .trust {{
      margin: 1rem 0 0;
      color: var(--muted);
      font-size: 0.92rem;
    }}
    section {{
      margin-top: 1rem;
      padding-top: 0.85rem;
      border-top: 1px solid var(--line);
    }}
    section h2 {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin: 0 0 0.45rem;
      font-weight: 600;
    }}
    .action strong {{ font-weight: 600; }}
    .kinds, .meta, .url, .body {{ margin: 0.25rem 0; }}
    .url {{ color: var(--muted); font-size: 0.85rem; word-break: break-all; }}
    .body {{ white-space: pre-wrap; word-break: break-word; }}
    footer {{
      margin: 1.25rem auto 0;
      max-width: var(--max);
      text-align: center;
      color: var(--muted);
      font-size: 11px;
    }}
    footer a {{ color: inherit; }}
  </style>
</head>
<body>
  <main class="shell" id="viewer"
        data-phase="{phase}"
        data-density="{density}"
        data-confidence="{frame.confidence}">
    <header class="hero">
      <p class="eyebrow">Adaptive agentic UI · human focus</p>
      <h1>{g}</h1>
      <div class="row">
        <span class="badge" id="phase-badge">phase · {phase}</span>
        <span class="badge" id="density-badge">layout · {density}</span>
        <span class="badge" id="ok-badge">{html.escape(ok_label)}</span>
        <div class="conf" title="confidence">
          <label>trust {conf_pct}%</label>
          <div class="bar"><i></i></div>
        </div>
      </div>
      <p class="trust" id="trust-line">{trust}</p>
    </header>
    <section class="action">
      <h2>Now</h2>
      <p><strong id="next-action">{nxt}</strong></p>
      <p class="meta"><span id="last-kind">{last_k}</span> — <span id="last-detail">{last_d}</span></p>
    </section>
    {steps_block}
    {preview_block}
    {final_block}
  </main>
  <footer>
    agentic-browser · Zinley agent (zinley.com) controlled · use at your own risk
  </footer>
</body>
</html>
"""


def write_viewer(
    result: AgentResult,
    path: str | Path,
    *,
    also_json: bool = True,
) -> Path:
    """Write adaptive HTML (and optional frame JSON) for a run."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = build_frame(result)
    path.write_text(render_html(frame), encoding="utf-8")
    if also_json:
        meta = path.with_suffix(".frame.json")
        payload = {
            "frame": frame.to_dict(),
            "phases_replay": [f.to_dict() for f in frames_across_run(result)],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "agent": "Zinley agent (zinley.com)",
        }
        meta.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def default_viewer_path(receipts_dir: str | Path | None = None) -> Path:
    base = Path(receipts_dir or "receipts")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return base / f"viewer_{ts}.html"


def _safe_name(goal: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (goal or "run").strip().lower()).strip("-")
    return (s[:48] or "run")
