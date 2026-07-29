from agentic_browser.agent import Agent
from agentic_browser.planner import Planner
from agentic_browser.types import Observation, Receipt, Step


def _example_obs(extra_interactive=None) -> Observation:
    interactive = [
        {
            "role": "link",
            "name": "More information...",
            "selector": 'a[href="https://iana.org/domains/example"]',
        },
    ]
    if extra_interactive:
        interactive.extend(extra_interactive)
    return Observation(
        url="https://example.com",
        title="Example Domain",
        text_preview="Example Domain. This domain is for use in documentation examples.",
        interactive=interactive,
        note="fake-browser",
    )


def test_click_name_match_not_first_only():
    p = Planner()
    obs = _example_obs(
        [
            {"role": "button", "name": "Subscribe", "selector": "button.subscribe"},
            {"role": "link", "name": "Learn more", "selector": "a.learn"},
        ]
    )
    # After goto would be step_i=1 with a page.
    step = p.next_step("click Learn more on example.com", obs, step_i=1, max_steps=6)
    assert step.kind == "click"
    assert "learn more" in step.target.lower()


def test_click_more_information_match():
    p = Planner()
    obs = _example_obs()
    step = p.next_step(
        "click More information on example.com", obs, step_i=1, max_steps=6
    )
    assert step.kind == "click"
    assert "more information" in step.target.lower()


def test_find_and_click_prefers_click_over_extract():
    p = Planner()
    obs = _example_obs()
    step = p.next_step(
        "find and click More information", obs, step_i=1, max_steps=6
    )
    assert step.kind == "click"
    assert "more information" in step.target.lower()


def test_type_intent_or_explicit_fail():
    p = Planner()
    # No textbox on example.com — must fail soft with clear reason, not silent done.
    obs = _example_obs()
    step = p.next_step(
        "type hello into search on example.com", obs, step_i=1, max_steps=6
    )
    assert step.kind in ("type", "fail")
    if step.kind == "fail":
        assert "textbox" in (step.reason or "").lower() or "type" in (
            step.reason or ""
        ).lower()
    else:
        assert step.value.lower() == "hello"

    # With a search field, must emit type.
    obs2 = _example_obs(
        [{"role": "textbox", "name": "Search", "selector": "input[name=q]"}]
    )
    step2 = p.next_step(
        "type hello into search on example.com", obs2, step_i=1, max_steps=6
    )
    assert step2.kind == "type"
    assert step2.value.lower() == "hello"
    assert "search" in step2.target.lower()


def test_fail_soft_no_identical_reclick():
    p = Planner()
    obs = _example_obs(
        [
            {"role": "link", "name": "Learn more", "selector": "a.learn"},
            {"role": "button", "name": "Accept", "selector": "button.accept"},
        ]
    )
    failed = Receipt(
        step=Step(kind="click", target="More information...", reason="first try"),
        ok=False,
        detail="element not found",
        observation=obs,
    )
    nxt = p.next_step(
        "click More information on example.com",
        obs,
        step_i=2,
        max_steps=6,
        last_receipt=failed,
    )
    assert not (
        nxt.kind == "click" and nxt.target.strip().lower() == "more information..."
    )
    # Either alternate click or fail — never identical re-click.
    if nxt.kind == "click":
        assert nxt.target.strip().lower() != "more information..."
    else:
        assert nxt.kind == "fail"


def test_extract_regression_agent_loop():
    agent = Agent(dry_run=True, max_steps=5, receipts_dir="/tmp/agentic-browser-m2-receipts")
    result = agent.run("Open example.com and extract the main heading")
    agent.close()
    assert result.ok
    kinds = [r.step.kind for r in result.receipts]
    assert "goto" in kinds
    assert "extract_text" in kinds or "done" in kinds
    assert result.summary
    assert result.steps_ok >= 1


def test_dry_run_named_click_loop():
    agent = Agent(dry_run=True, max_steps=6, receipts_dir="/tmp/agentic-browser-m2-receipts")
    result = agent.run("click More information on example.com")
    agent.close()
    kinds = [r.step.kind for r in result.receipts]
    assert "goto" in kinds
    assert "click" in kinds
    click_steps = [r.step for r in result.receipts if r.step.kind == "click"]
    assert click_steps
    assert "more information" in click_steps[0].target.lower()
    # single-intent: no forced extract after successful click
    assert "extract_text" not in kinds
    assert result.ok


def test_compound_click_then_extract_loop():
    agent = Agent(dry_run=True, max_steps=8, receipts_dir="/tmp/agentic-browser-m2-receipts")
    result = agent.run("click More information then extract heading on example.com")
    agent.close()
    kinds = [r.step.kind for r in result.receipts]
    assert "goto" in kinds
    assert "click" in kinds
    assert "extract_text" in kinds
    assert kinds.index("click") < kinds.index("extract_text")
    assert result.ok
    click_steps = [r.step for r in result.receipts if r.step.kind == "click"]
    assert click_steps and "more information" in click_steps[0].target.lower()


def test_compound_phase_after_click_receipt():
    p = Planner()
    obs = Observation(
        url="https://example.com",
        title="Example Domain",
        text_preview="(stub click on More information...)",
        interactive=[],
        note="clicked:More information...",
    )
    ok_click = Receipt(
        step=Step(kind="click", target="More information...", reason="match"),
        ok=True,
        detail="clicked",
        observation=obs,
    )
    nxt = p.next_step(
        "click More information then extract heading on example.com",
        obs,
        step_i=2,
        max_steps=8,
        last_receipt=ok_click,
    )
    assert nxt.kind == "extract_text"
    assert "post-click" in (nxt.reason or "").lower() or "extract" in (
        nxt.reason or ""
    ).lower()


def test_single_click_still_done_without_extract():
    p = Planner()
    obs = Observation(
        url="https://example.com",
        title="Example Domain",
        text_preview="(stub click on More information...)",
        interactive=[],
        note="clicked:More information...",
    )
    ok_click = Receipt(
        step=Step(kind="click", target="More information...", reason="match"),
        ok=True,
        detail="clicked",
        observation=obs,
    )
    nxt = p.next_step(
        "click More information on example.com",
        obs,
        step_i=2,
        max_steps=6,
        last_receipt=ok_click,
    )
    assert nxt.kind == "done"
    assert "click" in (nxt.reason or "").lower()


def test_missing_named_target_fails_soft():
    """H-M2-match-harden: do not invent success when no name tokens match."""
    p = Planner()
    obs = _example_obs(
        [
            {"role": "link", "name": "Learn more", "selector": "a.learn"},
            {"role": "button", "name": "Subscribe", "selector": "button.subscribe"},
        ]
    )
    step = p.next_step(
        "click the missing button that does not exist on example.com",
        obs,
        step_i=1,
        max_steps=6,
    )
    assert step.kind == "fail"
    assert "no interactive" in (step.reason or "").lower() or "match" in (
        step.reason or ""
    ).lower()


def test_role_only_and_bare_click_refuse():
    """Role words / empty name tokens must not pick a random control."""
    p = Planner()
    obs = _example_obs(
        [
            {"role": "link", "name": "Learn more", "selector": "a.learn"},
            {"role": "button", "name": "Subscribe", "selector": "button.subscribe"},
        ]
    )
    for goal in (
        "click button on example.com",
        "click link on example.com",
        "click the on example.com",
        "click submit on example.com",
    ):
        step = p.next_step(goal, obs, step_i=1, max_steps=6)
        assert step.kind == "fail", f"{goal!r} -> {step.kind} {step.target!r}"


def test_weak_substring_alone_does_not_win():
    """Substring-only 'more' must not beat a no-overlap refuse vs unrelated labels
    when a better full-token match is absent; named Learn more still wins on full tokens.
    """
    p = Planner()
    obs = _example_obs(
        [
            {"role": "button", "name": "Subscribe", "selector": "button.subscribe"},
            {"role": "link", "name": "Learn more", "selector": "a.learn"},
        ]
    )
    # Full name tokens still match.
    ok = p.next_step("click Learn more on example.com", obs, step_i=1, max_steps=6)
    assert ok.kind == "click"
    assert "learn more" in ok.target.lower()
    # Ultra-short single token alone is weak; still ok if full token 'more' overlaps
    # name_tokens of Learn more / More information — require at least one full token.
    weak = p.next_step("click more on example.com", obs, step_i=1, max_steps=6)
    assert weak.kind == "click"
    assert "more" in weak.target.lower()
    # Unrelated name: no content overlap → fail
    miss = p.next_step("click checkout on example.com", obs, step_i=1, max_steps=6)
    assert miss.kind == "fail"
