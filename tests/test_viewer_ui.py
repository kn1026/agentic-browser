"""H-UI-adaptive-viewer + live progressive + trust surface tests."""

from pathlib import Path

from agentic_browser.agent import Agent, AgentResult
from agentic_browser.types import Observation, Receipt, Step
from agentic_browser.viewer import (
    build_frame,
    frames_across_run,
    render_html,
    write_viewer,
    write_viewer_progress,
)


def _receipt(
    kind: str,
    ok: bool = True,
    detail: str = "",
    target: str = "",
    reason: str = "",
) -> Receipt:
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
    step_reason = reason if reason else detail
    return Receipt(
        step=Step(kind=kind, target=target, reason=step_reason),
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


def test_live_progressive_viewer_writes_multi_phase(tmp_path: Path):
    """H-UI-live-progressive-v1: mid-run HTML/jsonl updates with ≥2 phase or density values."""
    out = tmp_path / "live_viewer.html"
    agent = Agent(dry_run=True, write_viewer=True, viewer_path=out, receipts_dir=tmp_path)
    try:
        result = agent.run("click More information then extract heading")
    finally:
        agent.close()
    assert result.ok
    assert result.viewer_frame_writes >= 2
    phases = set(result.viewer_phases_seen)
    dens = set(result.viewer_densities_seen)
    assert len(phases) >= 2 or len(dens) >= 2
    live = out.with_suffix(".live.jsonl")
    assert live.is_file()
    rows = [ln for ln in live.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(rows) >= 2
    import json

    parsed = [json.loads(r) for r in rows]
    live_phases = {r["phase"] for r in parsed}
    live_dens = {r["density"] for r in parsed}
    assert len(live_phases) >= 2 or len(live_dens) >= 2
    # Final HTML is settled adaptive chrome, not empty
    body = out.read_text(encoding="utf-8")
    assert 'data-phase="' in body and 'data-density="' in body
    assert "Zinley agent" in body
    # frame.json includes live_progress trail
    meta = out.with_suffix(".frame.json")
    assert meta.is_file()
    payload = json.loads(meta.read_text(encoding="utf-8"))
    assert payload.get("live_progress")
    assert len(payload["live_progress"]) >= 2


def test_write_viewer_progress_rewrites_html(tmp_path: Path):
    path = tmp_path / "prog.html"
    nav = AgentResult(
        goal="open",
        ok=False,
        final_reason="",
        receipts=[_receipt("goto")],
        steps_ok=1,
        steps_failed=0,
    )
    f1 = write_viewer_progress(nav, path, write_index=0, terminal=False)
    assert f1.phase == "navigate"
    assert path.is_file()
    html1 = path.read_text(encoding="utf-8")
    assert 'data-phase="navigate"' in html1 or "navigate" in html1
    # Mid-run trust surface: meta refresh + structured action
    assert 'http-equiv="refresh"' in html1
    assert 'id="trust-panel"' in html1 or "trust-panel" in html1

    act = AgentResult(
        goal="click More information",
        ok=False,
        final_reason="",
        receipts=[
            _receipt("goto"),
            _receipt(
                "click",
                target="More information...",
                reason="matched goal tokens",
                detail="clicked More information...",
            ),
        ],
        steps_ok=2,
        steps_failed=0,
    )
    f2 = write_viewer_progress(act, path, write_index=1, terminal=False)
    assert f2.phase == "act"
    assert f2.density != f1.density or f2.phase != f1.phase
    assert f2.last_target.startswith("More information")
    assert f2.auto_refresh_seconds > 0
    html2 = path.read_text(encoding="utf-8")
    assert "act" in html2 or 'data-phase="act"' in html2
    assert "More information" in html2
    assert "trust-panel" in html2
    assert 'http-equiv="refresh"' in html2
    live = path.with_suffix(".live.jsonl")
    assert live.is_file()
    assert len(live.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_trust_surface_html_has_action_target_reason_and_chip():
    """H-UI-trust-surface-v1: structured trust panel, not generic copy only."""
    result = AgentResult(
        goal="click More information then extract heading",
        ok=True,
        final_reason="extracted",
        receipts=[
            _receipt("goto", target="https://example.com", reason="open start url"),
            _receipt(
                "click",
                target="More information...",
                reason="name matched goal",
                detail="clicked More information...",
            ),
            _receipt("extract_text", detail="Example Domain", reason="read heading"),
            _receipt("done", detail="extracted", reason="extracted"),
        ],
        steps_ok=4,
        steps_failed=0,
        summary="ok",
    )
    # Mid-run act frame: target + reason + conf chip + refresh
    mid = AgentResult(
        goal=result.goal,
        ok=False,
        final_reason="",
        receipts=result.receipts[:2],
        steps_ok=2,
        steps_failed=0,
    )
    f_mid = build_frame(mid)
    assert f_mid.phase == "act"
    assert f_mid.last_step_kind == "click"
    assert "More information" in f_mid.last_target
    assert f_mid.last_reason
    assert f_mid.why_step
    assert f_mid.last_ok is True
    assert f_mid.auto_refresh_seconds > 0
    html_mid = render_html(f_mid)
    assert 'id="trust-panel"' in html_mid
    assert 'id="last-kind"' in html_mid
    assert "More information" in html_mid
    assert 'id="last-target"' in html_mid
    assert 'id="last-reason"' in html_mid or "name matched" in html_mid
    assert 'id="conf-chip"' in html_mid or "trust " in html_mid
    assert 'http-equiv="refresh"' in html_mid
    assert "Zinley agent" in html_mid

    # Terminal settle: no meta refresh; outcome visible; trust still structured
    f_done = build_frame(result, auto_refresh_seconds=0)
    assert f_done.phase == "done"
    assert f_done.auto_refresh_seconds == 0
    html_done = render_html(f_done)
    assert 'http-equiv="refresh"' not in html_done
    assert 'id="trust-panel"' in html_done
    assert "trust " in html_done
    assert f_done.confidence >= 0.5


def test_trust_surface_fail_shows_status_and_reason():
    result = AgentResult(
        goal="click the missing button",
        ok=False,
        final_reason="no interactive target matched click goal",
        receipts=[
            _receipt("goto", target="https://example.com"),
            _receipt(
                "fail",
                ok=False,
                detail="no interactive target matched click goal",
                reason="no interactive target matched click goal",
            ),
        ],
        steps_ok=1,
        steps_failed=1,
    )
    frame = build_frame(result, auto_refresh_seconds=0)
    assert frame.phase == "fail"
    assert frame.last_ok is False or frame.ok is False
    assert frame.status_label == "fail"
    html_out = render_html(frame)
    assert "trust-panel" in html_out
    assert "fail" in html_out
    assert "no interactive target" in html_out or "Stopped" in html_out
    assert 'http-equiv="refresh"' not in html_out


def test_write_viewer_terminal_strips_refresh(tmp_path: Path):
    result = AgentResult(
        goal="extract heading",
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
    path = write_viewer(result, tmp_path / "term.html")
    body = path.read_text(encoding="utf-8")
    assert 'http-equiv="refresh"' not in body
    assert "trust-panel" in body
    meta = (tmp_path / "term.frame.json").read_text(encoding="utf-8")
    assert "why_step" in meta
    assert "last_target" in meta


def test_static_serve_returns_viewer_html_200(tmp_path: Path):
    """H-UI-static-serve-v1: stdlib loopback serve returns viewer HTML (no SPA)."""
    from agentic_browser.serve import fetch_viewer_http, make_server, resolve_viewer_root

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
    html_path = write_viewer(result, tmp_path / "viewer_serve.html")
    assert html_path.is_file()

    root, index_name = resolve_viewer_root(html_path)
    assert root == html_path.parent
    assert index_name == "viewer_serve.html"

    status, body, url = fetch_viewer_http(path=html_path, host="127.0.0.1", port=0)
    assert status == 200
    assert "127.0.0.1" in url
    assert "Open example.com and extract the main heading" in body
    assert 'data-phase="' in body
    assert "trust-panel" in body
    assert "Zinley agent" in body
    assert "use at your own risk" in body.lower()

    # Directory root + preferred index
    status2, body2, _ = fetch_viewer_http(path=tmp_path, host="127.0.0.1", port=0)
    assert status2 == 200
    assert "trust-panel" in body2

    # Context manager stop is clean
    srv = make_server(path=html_path, host="127.0.0.1", port=0)
    with srv:
        assert srv.port > 0
        assert srv._httpd is not None
    assert srv._httpd is None


def test_cli_serve_viewer_version_and_missing_path():
    """CLI exposes serve-viewer subcommand; missing file → exit 2."""
    from agentic_browser.cli import main
    import io
    from contextlib import redirect_stderr, redirect_stdout

    out = io.StringIO()
    with redirect_stdout(out):
        code = main(["serve-viewer", "--version"])
    assert code == 0
    assert out.getvalue().strip()

    out2 = io.StringIO()
    err2 = io.StringIO()
    with redirect_stdout(out2), redirect_stderr(err2):
        code2 = main(["serve-viewer", "/tmp/agentic-browser-no-such-viewer-xyz.html"])
    assert code2 == 2
    assert "error" in err2.getvalue().lower() or "not" in err2.getvalue().lower()
