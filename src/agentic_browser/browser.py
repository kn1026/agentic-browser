from __future__ import annotations

from agentic_browser.types import Observation


class Browser:
    """Thin browser facade.

    M0: in-memory fake session so the agent loop is testable offline.
    M1+: Playwright Chromium implementation behind the same API.
    """

    def __init__(self, dry_run: bool = True) -> None:
        self.dry_run = dry_run
        self.url = "about:blank"
        self.title = ""
        self._pages: dict[str, tuple[str, str]] = {
            "https://example.com": (
                "Example Domain",
                "Example Domain. This domain is for use in documentation examples "
                "without needing permission. Avoid use in operations.",
            ),
            "https://example.com/": (
                "Example Domain",
                "Example Domain. This domain is for use in documentation examples "
                "without needing permission. Avoid use in operations.",
            ),
        }

    def goto(self, url: str) -> Observation:
        if not url.startswith("http"):
            url = "https://" + url
        title, text = self._pages.get(url, (url, f"(stub page body for {url})"))
        self.url = url
        self.title = title
        return Observation(
            url=self.url,
            title=self.title,
            text_preview=text[:500],
            interactive=[{"role": "link", "name": "More information...", "selector": "a"}],
            note="fake-browser" if self.dry_run else "live",
        )

    def extract_text(self) -> Observation:
        title, text = self._pages.get(self.url, (self.title or self.url, ""))
        return Observation(
            url=self.url,
            title=title,
            text_preview=text[:800],
            interactive=[],
            note="extract",
        )

    def click(self, target: str) -> Observation:
        return Observation(
            url=self.url,
            title=self.title,
            text_preview=f"(stub click on {target})",
            interactive=[],
            note=f"clicked:{target}",
        )

    def type_text(self, target: str, value: str) -> Observation:
        return Observation(
            url=self.url,
            title=self.title,
            text_preview=f"(stub type into {target}: {value})",
            interactive=[],
            note=f"typed:{target}",
        )

    def screenshot(self, path: str = "shot.png") -> str:
        return path

    def close(self) -> None:
        return None
