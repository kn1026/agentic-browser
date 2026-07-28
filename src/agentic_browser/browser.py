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


class PlaywrightBrowser:
    """Optional live Chromium backend (requires: pip install playwright && playwright install chromium)."""

    def __init__(self) -> None:
        self._pw = None
        self._browser = None
        self._page = None
        self.url = "about:blank"
        self.title = ""

    def _ensure(self):
        if self._page is not None:
            return
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        self._page = self._browser.new_page()

    def goto(self, url: str):
        from agentic_browser.types import Observation

        if not url.startswith("http"):
            url = "https://" + url
        self._ensure()
        self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        self.url = self._page.url
        self.title = self._page.title()
        body = self._page.inner_text("body")[:800]
        return Observation(
            url=self.url,
            title=self.title,
            text_preview=body,
            interactive=[],
            note="playwright",
        )

    def extract_text(self):
        from agentic_browser.types import Observation

        self._ensure()
        body = self._page.inner_text("body")[:1200]
        return Observation(
            url=self._page.url,
            title=self._page.title(),
            text_preview=body,
            interactive=[],
            note="playwright-extract",
        )

    def click(self, target: str):
        from agentic_browser.types import Observation

        self._ensure()
        # try text selector then css
        try:
            self._page.get_by_text(target, exact=False).first.click(timeout=5000)
        except Exception:
            self._page.click(target, timeout=5000)
        return Observation(
            url=self._page.url,
            title=self._page.title(),
            text_preview=self._page.inner_text("body")[:400],
            interactive=[],
            note=f"pw-click:{target}",
        )

    def type_text(self, target: str, value: str):
        from agentic_browser.types import Observation

        self._ensure()
        try:
            self._page.get_by_label(target, exact=False).fill(value, timeout=5000)
        except Exception:
            self._page.fill(target, value, timeout=5000)
        return Observation(
            url=self._page.url,
            title=self._page.title(),
            text_preview=f"typed into {target}",
            interactive=[],
            note=f"pw-type:{target}",
        )

    def screenshot(self, path: str = "shot.png") -> str:
        self._ensure()
        self._page.screenshot(path=path, full_page=True)
        return path

    def close(self) -> None:
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass

