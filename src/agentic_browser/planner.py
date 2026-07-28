from __future__ import annotations

import re
from typing import Any

from agentic_browser.types import Observation, Receipt, Step

_STOP = {
    "a",
    "an",
    "the",
    "on",
    "in",
    "into",
    "to",
    "for",
    "and",
    "or",
    "of",
    "at",
    "with",
    "from",
    "by",
    "open",
    "go",
    "goto",
    "navigate",
    "visit",
    "page",
    "site",
    "website",
    "http",
    "https",
    "www",
    "com",
    "org",
    "net",
    "io",
    "please",
    "main",
    "that",
    "this",
    "then",
}


class Planner:
    """Deterministic v1 planner.

    Scores obs.interactive against goal tokens, prefers act over bare extract
    when click/type verbs are present, consumes last_receipt for fail-soft,
    and emits type steps when asked.
    """

    MATCH_THRESHOLD = 0.15

    def next_step(
        self,
        goal: str,
        obs: Observation | None,
        step_i: int,
        max_steps: int,
        last_receipt: Receipt | None = None,
    ) -> Step:
        g = (goal or "").lower()
        if step_i >= max_steps - 1:
            return Step(kind="done", reason="max steps reached — wrapping up")

        if obs is None or obs.url in ("", "about:blank"):
            url = self._guess_url(goal)
            return Step(kind="goto", target=url, reason="need a page before acting")

        # Fail-soft: never blind-repeat the same failed click/type target.
        if last_receipt is not None and not last_receipt.ok:
            return self._after_failure(goal, obs, last_receipt)

        wants_click = bool(re.search(r"\b(click|tap|press)\b", g))
        wants_type = bool(re.search(r"\b(type|fill|enter|input|write)\b", g))
        wants_extract = bool(
            re.search(r"\b(extract|heading|title|read|scrape|summarize)\b", g)
            or ("find" in g and not wants_click and not wants_type)
        )
        # "find and click X" is an act goal, not extract.
        if "find" in g and wants_click:
            wants_extract = False

        # After a successful act step that satisfied click/type intent, finish.
        if last_receipt is not None and last_receipt.ok:
            lk = last_receipt.step.kind
            if wants_click and lk == "click" and not wants_extract:
                return Step(
                    kind="done",
                    reason=f"clicked {last_receipt.step.target!r} ok",
                )
            if wants_type and lk == "type" and not wants_extract and not wants_click:
                return Step(
                    kind="done",
                    reason=f"typed into {last_receipt.step.target!r} ok",
                )

        if wants_type:
            typed = self._plan_type(goal, obs)
            if typed is not None:
                return typed

        if wants_click:
            clicked = self._plan_click(goal, obs, exclude=set())
            if clicked is not None:
                return clicked
            if wants_extract:
                return self._plan_extract(obs, step_i)
            # If we already clicked successfully earlier in-loop, done was handled above.
            return Step(
                kind="fail",
                reason="no interactive target matched click goal",
            )

        if wants_extract or "find" in g:
            return self._plan_extract(obs, step_i)

        if step_i == 0:
            return Step(kind="goto", target=self._guess_url(goal), reason="start at likely URL")

        return Step(
            kind="done",
            reason=f"stub complete at {obs.url} — title={obs.title!r}",
        )

    def _after_failure(self, goal: str, obs: Observation, last_receipt: Receipt) -> Step:
        g = (goal or "").lower()
        failed = last_receipt.step
        exclude: set[str] = set()
        if failed.kind in ("click", "type") and failed.target:
            exclude.add(failed.target.strip().lower())

        if failed.kind == "click" or re.search(r"\b(click|tap|press)\b", g):
            alt = self._plan_click(goal, obs, exclude=exclude)
            if alt is not None:
                alt.reason = f"fail-soft alternate after {failed.target!r}: {alt.reason}"
                return alt
            return Step(
                kind="fail",
                reason=(
                    f"click blocked on {failed.target!r}"
                    f" ({last_receipt.detail}); no alternate interactive match"
                ),
            )

        if failed.kind == "type" or re.search(r"\b(type|fill|enter|input|write)\b", g):
            alt = self._plan_type(goal, obs, exclude=exclude)
            if alt is not None:
                alt.reason = f"fail-soft alternate after {failed.target!r}: {alt.reason}"
                return alt
            return Step(
                kind="fail",
                reason=(
                    f"type blocked on {failed.target!r}"
                    f" ({last_receipt.detail}); no alternate textbox"
                ),
            )

        return Step(
            kind="fail",
            reason=f"step {failed.kind} failed: {last_receipt.detail}",
        )

    def _plan_extract(self, obs: Observation, step_i: int) -> Step:
        # step_i==0 is usually goto; first on-page extract at step_i>=1
        if step_i <= 1 and not (obs.text_preview and len(obs.text_preview) > 20):
            return Step(kind="extract_text", reason="goal asks for page content")
        if step_i == 1:
            return Step(kind="extract_text", reason="goal asks for page content")
        # After an extract_text receipt, obs usually has text — finish.
        if obs.note.startswith("extract") or (obs.text_preview and step_i >= 2):
            return Step(
                kind="done",
                reason=f"extracted from {obs.url}: {obs.text_preview[:120]}",
            )
        return Step(kind="extract_text", reason="goal asks for page content")

    def _plan_click(self, goal: str, obs: Observation, exclude: set[str]) -> Step | None:
        match = self._best_interactive(
            goal,
            obs.interactive,
            prefer_roles=("link", "button"),
            exclude_names=exclude,
        )
        if match is None:
            return None
        name = str(match.get("name") or match.get("selector") or "target")
        score = float(match.get("_score") or 0.0)
        return Step(
            kind="click",
            target=name,
            reason=f"goal-token match score={score:.2f} on interactive",
        )

    def _plan_type(
        self,
        goal: str,
        obs: Observation,
        exclude: set[str] | None = None,
    ) -> Step | None:
        exclude = exclude or set()
        fields = [
            el
            for el in obs.interactive
            if str(el.get("role") or "").lower()
            in ("textbox", "searchbox", "input", "textarea", "combobox")
            or str(el.get("selector") or "").lower().startswith("input")
            or str(el.get("selector") or "").lower().startswith("textarea")
        ]
        pool = fields or [
            el
            for el in obs.interactive
            if "search" in str(el.get("name") or "").lower()
            or "search" in str(el.get("selector") or "").lower()
        ]
        if not pool:
            return Step(
                kind="fail",
                reason="no textbox interactive for type/fill goal",
            )

        match = self._best_interactive(
            goal,
            pool,
            prefer_roles=("textbox", "searchbox", "input", "textarea", "combobox"),
            exclude_names=exclude,
            allow_weak=True,
        )
        if match is None:
            # still have a field — use first not excluded
            for el in pool:
                n = str(el.get("name") or el.get("selector") or "").strip()
                if n.lower() not in exclude:
                    match = dict(el)
                    match["_score"] = 0.0
                    break
        if match is None:
            return Step(
                kind="fail",
                reason="no textbox interactive for type/fill goal",
            )

        name = str(match.get("name") or match.get("selector") or "textbox")
        value = self._extract_type_value(goal)
        return Step(
            kind="type",
            target=name,
            value=value,
            reason=f"type/fill branch → {name!r}",
        )

    def _extract_type_value(self, goal: str) -> str:
        g = goal or ""
        m = re.search(
            r"""(?:type|fill|enter|input|write)\s+["']([^"']+)["']""",
            g,
            re.I,
        )
        if m:
            return m.group(1)
        m = re.search(
            r"""(?:type|fill|enter|input|write)\s+(\S+?)(?:\s+into|\s+in\b|\s+on\b|$)""",
            g,
            re.I,
        )
        if m:
            return m.group(1).strip(".,!")
        return "hello"

    def _goal_tokens(self, goal: str) -> set[str]:
        raw = re.findall(r"[a-z0-9]{2,}", (goal or "").lower())
        return {t for t in raw if t not in _STOP and not t.isdigit()}

    def _best_interactive(
        self,
        goal: str,
        elements: list[dict[str, Any]],
        prefer_roles: tuple[str, ...] = (),
        exclude_names: set[str] | None = None,
        allow_weak: bool = False,
    ) -> dict[str, Any] | None:
        exclude_names = exclude_names or set()
        tokens = self._goal_tokens(goal)
        # Drop pure-action tokens so "click More information" focuses on name parts.
        actionish = {
            "click",
            "tap",
            "press",
            "type",
            "fill",
            "enter",
            "input",
            "write",
            "find",
            "search",
            "button",
            "link",
            "example",
        }
        focus = tokens - actionish
        if not focus:
            focus = tokens

        best: dict[str, Any] | None = None
        best_score = -1.0
        for el in elements:
            name = str(el.get("name") or "").strip()
            sel = str(el.get("selector") or "").strip()
            role = str(el.get("role") or "").strip().lower()
            key = name.lower()
            if key in exclude_names or (sel and sel.lower() in exclude_names):
                continue
            hay = f"{name} {sel} {role}".lower()
            hay_tokens = set(re.findall(r"[a-z0-9]{2,}", hay))
            if not hay_tokens and not name:
                continue
            overlap = focus & hay_tokens
            # partial substring boost (e.g. goal "more" vs name "More information")
            sub = 0.0
            for t in focus:
                if t in hay:
                    sub += 1.0
            score = (2.0 * len(overlap) + sub) / max(len(focus), 1)
            if prefer_roles and role in prefer_roles:
                score += 0.05
            # Prefer longer name when scores tie (more specific label).
            score += min(len(name), 40) / 1000.0
            if score > best_score:
                best_score = score
                best = dict(el)
                best["_score"] = score

        if best is None:
            return None
        if best_score < self.MATCH_THRESHOLD and not allow_weak:
            # If goal names nothing usable but only one interactive exists and
            # goal is a bare "click" without a named target, still refuse.
            return None
        if best_score < self.MATCH_THRESHOLD and allow_weak:
            return best
        if best_score < self.MATCH_THRESHOLD:
            return None
        return best

    def _guess_url(self, goal: str) -> str:
        g = goal or ""
        for token in g.split():
            t = token.strip().strip("\"'")
            if t.startswith("http://") or t.startswith("https://"):
                return t
            if "." in t and " " not in t and not t.endswith("."):
                if any(t.endswith(s) for s in (".com", ".org", ".net", ".io", ".dev", ".ai")):
                    return "https://" + t.lstrip("@")
        if "example" in g.lower():
            return "https://example.com"
        return "https://example.com"
