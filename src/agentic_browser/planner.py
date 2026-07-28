from __future__ import annotations

from agentic_browser.types import Observation, Step


class Planner:
    """Deterministic v0 planner.

    Good enough to drive the loop and demos before an LLM planner lands.
    """

    def next_step(self, goal: str, obs: Observation | None, step_i: int, max_steps: int) -> Step:
        g = (goal or "").lower()
        if step_i >= max_steps - 1:
            return Step(kind="done", reason="max steps reached — wrapping up")

        if obs is None or obs.url in ("", "about:blank"):
            url = self._guess_url(goal)
            return Step(kind="goto", target=url, reason="need a page before acting")

        if "extract" in g or "heading" in g or "title" in g or "find" in g:
            if step_i == 1:
                return Step(kind="extract_text", reason="goal asks for page content")
            return Step(
                kind="done",
                reason=f"extracted from {obs.url}: {obs.text_preview[:120]}",
            )

        if "click" in g and obs.interactive:
            name = obs.interactive[0].get("name") or "first-interactive"
            return Step(kind="click", target=str(name), reason="goal mentions click")

        if step_i == 0:
            return Step(kind="goto", target=self._guess_url(goal), reason="start at likely URL")

        return Step(
            kind="done",
            reason=f"stub complete at {obs.url} — title={obs.title!r}",
        )

    def _guess_url(self, goal: str) -> str:
        g = goal or ""
        for token in g.split():
            t = token.strip().strip("\"'")
            if t.startswith("http://") or t.startswith("https://"):
                return t
            if "." in t and " " not in t and not t.endswith("."):
                # crude domain detection
                if any(t.endswith(s) for s in (".com", ".org", ".net", ".io", ".dev", ".ai")):
                    return "https://" + t.lstrip("@")
        if "example" in g.lower():
            return "https://example.com"
        return "https://example.com"
