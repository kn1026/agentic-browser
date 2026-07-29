"""H-UI-adaptive-viewer-v1 — adaptive chrome transforms with phase/density."""

from pathlib import Path

from agentic_browser.agent import Agent, AgentResult
from agentic_browser.types import Observation, Receipt, Step
from agentic_browser.viewer import (
    build_frame,
    frames_across_run,
    render_html,
    write_viewer,
)


def _receipt(kind: str, ok: bool = True, detail: str = "", target: str = "") -> Receipt:
    obs = None
    if kind in ("goto", "click", "type", "extract_text"):
        obs = Observation(
            url="https://example.com/",
            title="Example Domain",
            text_preview="Example Domain. This domain is for use in documentation examples.",
            interactive=(
                [
                    {
                        "role": "link",
                        "name": "More information...",
                        "selector": 'a[href="https://iana.org/domains/example"]',
                    }
                ]
                if kind == "goto"
                else []
            ),
            note="fake" if kind != "extract_text" else "extract: heading",
        )
    return Receipt(
        step=Step(kind=kind, target=target, reason=detail),
        ok=ok,
        detail=detail or kind,
        observation=obs,
    )


def test_build_frame_phase_and_density_shift():
    # navigate-only partial
    nav = AgentResult(
        goal="open example.com",
        ok=False,
        final_reason="",
        receipts=[_receipt("goto", detail="opened")],
        steps_ok=1,
        steps_failed=0,
    )
    f_nav = build_frame(nav)
    assert f_nav.phase == "navigate"
    assert f_nav.density == "calm"

    # act after click (non-terminal)
    act = AgentResult(
        goal="click More information",
        ok=False,
        final_reason="",
        receipts=[
            _receipt("goto", detail="opened"),
            _receipt("click", detail="clicked", target="More information..."),
        ],
        steps_ok=2,
        steps_failed=0,
    )
    f_act = build_frame(act)
    assert f_act.phase == "act"
    assert f_act.density == "focus"

    # extract
    ext = AgentResult(
        goal="extract heading",
        ok=False,
        final_reason="",
        receipts=[
            _receipt("goto"),
            _receipt("extract_text", detail="Example Domain"),
        ],
        steps_ok=2,
        steps_failed=0,
    )
    f_ext = build_frame(ext)
    assert f_ext.phase == "extract"
    assert f_ext.density in ("dense", "focus")

    # done settle
    done = AgentResult(
        goal="extract heading",
        ok=True,
        final_reason="got heading",
        receipts=[
            _receipt("goto"),
            _receipt("extract_text", detail="Example Domain"),
            _receipt("done", detail="got heading"),
        ],
        steps_ok=3,
        steps_failed=0,
        summary="ok",
    )
    f_done = build_frame(done)
    assert f_done.phase == "done"
    assert f_done.density == "settle"
    assert f_done.ok is True


def test_frames_across_run_has_at_least_two_densities():
    result = AgentResult(
        goal="click More information then extract heading",
        ok=True,
        final_reason="extracted",
        receipts=[
            _receipt("goto"),
            _receipt("click", target="More information..."),
            _receipt("extract_text", detail="Example Domain"),
            _receipt("done", detail="extracted"),
        ],
        steps_ok=4,
        steps_failed=0,
        summary="compound ok",
    )
    frames = frames_across_run(result)
    dens = {f.density for f in frames}
    phases = {f.phase for f in frames}
    assert len(frames) >= 3
    assert len(dens) >= 2
    assert "navigate" in phases or "act" in phases
    assert "done" in phases or "extract" in phases


def test_render_html_includes_goal_phase_adaptive_attrs(tmp_path: Path):
    result = AgentResult(
        goal="Open example.com and extract the main heading",
        ok=True,
        final_reason="Example Domain",
        receipts=[
            _receipt("goto"),
            _receipt("extract_text", detail="Example Domain"),
            _receipt("done", detail="Example Domain"),
        ],
        steps_ok=3,
        steps_failed=0,
    )
    frame = build_frame(result)
    html_out = render_html(frame)
    assert "Open example.com and extract the main heading" in html_out
    assert 'data-phase="' in html_out
    assert 'data-density="' in html_out
    assert "phase ·" in html_out
    assert "layout ·" in html_out
    assert "Zinley agent" in html_out
    assert "use at your own risk" in html_out.lower() or "use at your own risk" in html_out

    path = write_viewer(result, tmp_path / "viewer.html")
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert frame.phase in text
    assert (tmp_path / "viewer.frame.json").is_file()


def test_agent_viewer_flag_writes_artifact(tmp_path: Path):
    out = tmp_path / "run_viewer.html"
    agent = Agent(dry_run=True, write_viewer=True, viewer_path=out, receipts_dir=tmp_path)
    try:
        result = agent.run("Open example.com and extract the main heading")
    finally:
        agent.close()
    assert result.ok
    assert result.viewer_path
    p = Path(result.viewer_path)
    assert p.is_file()
    body = p.read_text(encoding="utf-8")
    assert "extract" in body.lower() or "done" in body.lower()
    assert 'data-density="' in body
    assert result.goal in body
