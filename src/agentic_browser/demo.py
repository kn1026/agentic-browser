"""M3 shareable adaptive demo tour — run → viewer frames → tour index → serve.

H-UI-m3-demo-tour-v1: one-command path with no tribal knowledge.
Static multi-frame progressive disclosure (no SPA/React/websocket).
Tour patterns: step walkthrough + progressive disclosure (Guideflow / NN-style
ideas applied as static HTML sections + frame pages, not a product-tour SDK).
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_browser.agent import Agent, AgentResult
from agentic_browser.viewer import (
    ViewerFrame,
    build_frame,
    frames_across_run,
    render_html,
    write_viewer,
)

DEFAULT_TOUR_GOAL = (
    "Open example.com, click More information then extract the main heading"
)

# Human-readable beat copy for the tour (phase → one line).
_PHASE_BEAT: dict[str, str] = {
    "idle": "Waiting — chrome stays quiet until a goal lands.",
    "navigate": "Calm open — light chrome while the page loads.",
    "act": "Focus — only the matched control and why it was chosen.",
    "extract": "Dense read — preview expands after a real extract receipt.",
    "done": "Settle — quiet outcome, trust the result not the thrash.",
    "fail": "Stopped — failure is visible so a human can steer.",
}


@dataclass
class DemoTourResult:
    """Artifacts from a polished adaptive demo tour run."""

    ok: bool
    goal: str
    out_dir: Path
    viewer_path: Path
    tour_index_path: Path
    frame_paths: list[Path] = field(default_factory=list)
    agent_result: AgentResult | None = None
    phases: list[str] = field(default_factory=list)
    densities: list[str] = field(default_factory=list)
    serve_hint: str = ""
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "goal": self.goal,
            "out_dir": str(self.out_dir),
            "viewer_path": str(self.viewer_path),
            "tour_index_path": str(self.tour_index_path),
            "frame_paths": [str(p) for p in self.frame_paths],
            "phases": list(self.phases),
            "densities": list(self.densities),
            "serve_hint": self.serve_hint,
            "summary": self.summary,
        }


def _safe_slug(goal: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (goal or "tour").strip().lower()).strip("-")
    return (s[:40] or "tour")


def default_tour_dir(base: str | Path | None = None) -> Path:
    root = Path(base or "receipts")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return root / f"demo_tour_{ts}"


def _frame_filename(i: int, frame: ViewerFrame) -> str:
    return f"frame_{i:02d}_{frame.phase}_{frame.density}.html"


def render_tour_index(
    *,
    goal: str,
    frames: list[ViewerFrame],
    frame_hrefs: list[str],
    live_viewer_href: str,
    final_ok: bool | None,
    agent_summary: str = "",
) -> str:
    """Static progressive tour landing — multi-frame, no SPA.

    Progressive disclosure via linked frame pages + in-page beats (details/summary
    + section anchors). Prefer existing server-rendered markup over client apps.
    """
    g = html.escape(goal)
    n = len(frames)
    dens = sorted({f.density for f in frames})
    phases = [f.phase for f in frames]
    ok_label = "ok" if final_ok is True else ("fail" if final_ok is False else "running")
    beats_li = []
    for i, fr in enumerate(frames):
        href = html.escape(frame_hrefs[i] if i < len(frame_hrefs) else "#")
        beat = html.escape(_PHASE_BEAT.get(fr.phase, fr.trust_line or fr.phase))
        conf = int(round(fr.confidence * 100))
        beats_li.append(
            f'''<li class="beat" data-phase="{html.escape(fr.phase)}" data-density="{html.escape(fr.density)}">
  <a class="beat-link" href="{href}">
    <span class="n">{i + 1:02d}</span>
    <span class="ph">phase · {html.escape(fr.phase)}</span>
    <span class="dn">layout · {html.escape(fr.density)}</span>
    <span class="cf">trust {conf}%</span>
  </a>
  <p class="beat-copy">{beat}</p>
  <p class="beat-meta">{html.escape(fr.last_step_kind or "—")} · {html.escape((fr.last_target or fr.next_action or "—")[:80])}</p>
</li>'''
        )
    beats_html = "\n".join(beats_li) if beats_li else "<li>No frames.</li>"
    dens_badges = " ".join(
        f'<span class="badge">layout · {html.escape(d)}</span>' for d in dens
    )
    phase_path = html.escape(" → ".join(phases) if phases else "—")
    summary_e = html.escape((agent_summary or "")[:240])
    live_e = html.escape(live_viewer_href)

    # Embedded mini-previews: progressive disclosure of each frame's trust line
    details_blocks = []
    for i, fr in enumerate(frames):
        href = html.escape(frame_hrefs[i] if i < len(frame_hrefs) else "#")
        open_attr = " open" if i == 0 else ""
        details_blocks.append(
            f'''<details class="frame-peek" data-phase="{html.escape(fr.phase)}"{open_attr}>
  <summary>Frame {i + 1}: {html.escape(fr.phase)} / {html.escape(fr.density)} — {html.escape(fr.last_step_kind or "start")}</summary>
  <p class="peek-trust">{html.escape(fr.trust_line)}</p>
  <p class="peek-why">{html.escape(fr.why_step or "")}</p>
  <p><a href="{href}">Open full adaptive chrome →</a></p>
</details>'''
        )
    details_html = "\n".join(details_blocks)

    return f"""<!DOCTYPE html>
<html lang="en" data-tour="m3" data-ok="{html.escape(ok_label)}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Adaptive demo tour · agentic-browser</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #f7f7f5;
      --fg: #141414;
      --muted: #6b6b6b;
      --line: #e4e4e0;
      --card: #ffffff;
      --radius: 14px;
      --max: 42rem;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #0e0e0e;
        --fg: #f2f2f0;
        --muted: #9a9a96;
        --line: #2a2a28;
        --card: #161616;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font: 15px/1.45 ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
      background: var(--bg);
      color: var(--fg);
      padding: 2rem 1.25rem 3rem;
    }}
    .shell {{
      max-width: var(--max);
      margin: 0 auto;
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 1.35rem 1.35rem 1.5rem;
    }}
    .eyebrow {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin: 0 0 0.4rem;
    }}
    h1 {{
      font-size: 1.25rem;
      font-weight: 600;
      letter-spacing: -0.02em;
      margin: 0 0 0.75rem;
      line-height: 1.3;
    }}
    .goal {{
      color: var(--muted);
      font-size: 0.95rem;
      margin: 0 0 1rem;
    }}
    .row {{ display: flex; flex-wrap: wrap; gap: 0.45rem; align-items: center; margin-bottom: 1rem; }}
    .badge {{
      font-size: 12px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 0.2rem 0.65rem;
    }}
    section {{
      margin-top: 1.15rem;
      padding-top: 1rem;
      border-top: 1px solid var(--line);
    }}
    section h2 {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin: 0 0 0.55rem;
      font-weight: 600;
    }}
    ol.beats {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 0.85rem; }}
    .beat-link {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
      align-items: center;
      color: inherit;
      text-decoration: none;
      font-weight: 600;
      font-size: 0.92rem;
    }}
    .beat-link:hover .ph {{ text-decoration: underline; }}
    .n {{
      font-variant-numeric: tabular-nums;
      color: var(--muted);
      font-size: 12px;
      min-width: 1.6rem;
    }}
    .beat-copy {{ margin: 0.35rem 0 0.15rem; font-size: 0.95rem; }}
    .beat-meta {{ margin: 0; color: var(--muted); font-size: 0.85rem; }}
    .path {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.82rem; word-break: break-word; }}
    .cta {{
      display: inline-block;
      margin: 0.35rem 0.5rem 0.35rem 0;
      padding: 0.45rem 0.85rem;
      border: 1px solid var(--fg);
      border-radius: 999px;
      color: var(--fg);
      text-decoration: none;
      font-size: 0.9rem;
      font-weight: 600;
    }}
    .cta.secondary {{ border-color: var(--line); font-weight: 500; color: var(--muted); }}
    details.frame-peek {{
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 0.55rem 0.75rem;
      margin: 0.45rem 0;
    }}
    details.frame-peek summary {{ cursor: pointer; font-weight: 600; font-size: 0.9rem; }}
    .peek-trust {{ color: var(--muted); margin: 0.5rem 0 0.25rem; }}
    .peek-why {{ margin: 0 0 0.5rem; font-size: 0.92rem; }}
    footer {{
      margin: 1.25rem auto 0;
      max-width: var(--max);
      text-align: center;
      color: var(--muted);
      font-size: 11px;
    }}
    footer a {{ color: inherit; }}
    .note {{ color: var(--muted); font-size: 0.88rem; margin: 0.5rem 0 0; }}
  </style>
</head>
<body>
  <main class="shell" id="demo-tour">
    <p class="eyebrow">M3 · Adaptive agentic UI demo tour</p>
    <h1>UI that transforms with the task</h1>
    <p class="goal">{g}</p>
    <div class="row">
      <span class="badge">frames · {n}</span>
      <span class="badge">run · {html.escape(ok_label)}</span>
      {dens_badges}
    </div>
    <p class="path">phase path: {phase_path}</p>

    <section id="start">
      <h2>One-liner path</h2>
      <a class="cta" href="{live_e}">Open live viewer (final)</a>
      <a class="cta secondary" href="{html.escape(frame_hrefs[0]) if frame_hrefs else live_e}">Start at frame 01</a>
      <p class="note">Stdlib loopback serve only — no SPA. Zinley agent controlled · use at your own risk.</p>
    </section>

    <section id="beats">
      <h2>Tour beats</h2>
      <p class="note">Each beat is a real adaptive chrome snapshot (phase + density + trust). Not a click-bot log dump.</p>
      <ol class="beats">
{beats_html}
      </ol>
    </section>

    <section id="disclosure">
      <h2>Progressive peek</h2>
      <p class="note">Open a beat without leaving the tour index — full chrome stays one click away.</p>
{details_html}
    </section>

    <section id="substrate">
      <h2>Substrate (not the product)</h2>
      <p class="note">observe → plan → act → receipts powers the loop. The differentiator is the human surface above.</p>
      <p class="path">{summary_e or "—"}</p>
    </section>
  </main>
  <footer>
    agentic-browser · Zinley agent (<a href="https://zinley.com">zinley.com</a>) controlled · use at your own risk
  </footer>
</body>
</html>
"""


def write_demo_tour_artifacts(
    result: AgentResult,
    out_dir: str | Path,
    *,
    also_live_viewer: bool = True,
) -> DemoTourResult:
    """Write tour index + per-phase frame HTML + final viewer into out_dir."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    frames = frames_across_run(result)
    if not frames:
        frames = [build_frame(result, auto_refresh_seconds=0)]

    frame_paths: list[Path] = []
    frame_hrefs: list[str] = []
    phases: list[str] = []
    dens: list[str] = []

    for i, fr in enumerate(frames):
        # Frame pages are terminal snapshots of that prefix — no meta refresh thrash.
        fr.auto_refresh_seconds = 0
        name = _frame_filename(i, fr)
        path = out / name
        title = f"tour frame {i + 1:02d} · {fr.phase}"
        path.write_text(render_html(fr, title=title), encoding="utf-8")
        frame_paths.append(path)
        frame_hrefs.append(name)
        phases.append(fr.phase)
        dens.append(fr.density)

    viewer_path = out / "viewer_final.html"
    if also_live_viewer:
        write_viewer(result, viewer_path, also_json=True)
        # Prefer copying progressive trail if agent already wrote one alongside
    else:
        viewer_path.write_text(
            render_html(build_frame(result, auto_refresh_seconds=0)),
            encoding="utf-8",
        )

    # If agent produced a live viewer elsewhere, keep final as source of truth here.
    live_href = "viewer_final.html"

    index_path = out / "index.html"
    index_html = render_tour_index(
        goal=result.goal,
        frames=frames,
        frame_hrefs=frame_hrefs,
        live_viewer_href=live_href,
        final_ok=result.ok,
        agent_summary=result.summary or result.final_reason or "",
    )
    index_path.write_text(index_html, encoding="utf-8")

    # Machine-readable tour manifest for tests / BIP evidence
    manifest = {
        "goal": result.goal,
        "ok": result.ok,
        "frames": [
            {
                "i": i,
                "file": frame_hrefs[i],
                "phase": frames[i].phase,
                "density": frames[i].density,
                "confidence": frames[i].confidence,
                "last_step_kind": frames[i].last_step_kind,
                "last_target": frames[i].last_target,
            }
            for i in range(len(frames))
        ],
        "phases": phases,
        "densities": dens,
        "viewer_final": live_href,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "agent": "Zinley agent (zinley.com)",
        "hypothesis": "H-UI-m3-demo-tour-v1",
    }
    (out / "tour.manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    serve_hint = (
        f"python -m agentic_browser serve-viewer {out} --port 8765\n"
        f"# or: agentic-browser serve-viewer {out}\n"
        f"# open http://127.0.0.1:8765/  → tour index (adaptive frames)"
    )

    return DemoTourResult(
        ok=bool(result.ok),
        goal=result.goal,
        out_dir=out,
        viewer_path=viewer_path,
        tour_index_path=index_path,
        frame_paths=frame_paths,
        agent_result=result,
        phases=phases,
        densities=dens,
        serve_hint=serve_hint,
        summary=(
            f"tour frames={len(frames)} phases={phases} dens={sorted(set(dens))} "
            f"ok={result.ok} index={index_path}"
        ),
    )


def run_demo_tour(
    goal: str | None = None,
    *,
    out_dir: str | Path | None = None,
    dry_run: bool = True,
    max_steps: int = 8,
    receipts_dir: str | Path | None = None,
) -> DemoTourResult:
    """Run agent (default dry) with viewer, then write multi-frame tour artifacts."""
    goal = (goal or DEFAULT_TOUR_GOAL).strip()
    base_receipts = Path(receipts_dir or "receipts")
    base_receipts.mkdir(parents=True, exist_ok=True)
    out = Path(out_dir) if out_dir else default_tour_dir(base_receipts)
    out.mkdir(parents=True, exist_ok=True)

    # Live progressive viewer inside the tour dir for realism
    viewer_live = out / "viewer_live.html"
    agent = Agent(
        dry_run=dry_run,
        max_steps=max_steps,
        receipts_dir=base_receipts,
        write_viewer=True,
        viewer_path=viewer_live,
    )
    try:
        result = agent.run(goal)
    finally:
        agent.close()

    tour = write_demo_tour_artifacts(result, out, also_live_viewer=True)
    # Prefer the progressive live file as alternate link if present
    if viewer_live.is_file() and tour.tour_index_path.is_file():
        # Keep both; index already points at viewer_final. Optional symlink-style copy note in manifest.
        man_path = out / "tour.manifest.json"
        try:
            man = json.loads(man_path.read_text(encoding="utf-8"))
            man["viewer_live"] = "viewer_live.html"
            man["viewer_frame_writes"] = result.viewer_frame_writes
            man["viewer_phases_seen"] = list(result.viewer_phases_seen)
            man_path.write_text(json.dumps(man, indent=2), encoding="utf-8")
        except Exception:
            pass
    return tour
