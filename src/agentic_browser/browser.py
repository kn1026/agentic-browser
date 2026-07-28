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
    """Live Chromium backend via Playwright (pip install playwright && playwright install chromium)."""

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

    def _list_interactive(self, limit: int = 12) -> list[dict]:
        """Collect a small set of clickable/typeable targets with stable-ish selectors."""
        assert self._page is not None
        script = """
        (limit) => {
          const out = [];
          const push = (el, role) => {
            if (out.length >= limit) return;
            const name = (el.innerText || el.getAttribute('aria-label') || el.getAttribute('name') || el.getAttribute('placeholder') || el.id || '').trim().slice(0, 80);
            let selector = '';
            if (el.id) selector = '#' + CSS.escape(el.id);
            else if (el.getAttribute('name')) selector = el.tagName.toLowerCase() + '[name="' + el.getAttribute('name') + '"]';
            else if (el.getAttribute('href')) selector = 'a[href="' + el.getAttribute('href') + '"]';
            else selector = el.tagName.toLowerCase();
            out.push({ role, name: name || role, selector });
          };
          document.querySelectorAll('a[href]').forEach(el => push(el, 'link'));
          document.querySelectorAll('button, [role="button"]').forEach(el => push(el, 'button'));
          document.querySelectorAll('input, textarea, select').forEach(el => {
            const t = (el.getAttribute('type') || 'text').toLowerCase();
            if (['hidden', 'submit', 'button'].includes(t) && el.tagName.toLowerCase() === 'input') return;
            push(el, el.tagName.toLowerCase() === 'textarea' ? 'textbox' : (t === 'checkbox' || t === 'radio' ? t : 'textbox'));
          });
          return out.slice(0, limit);
        }
        """
        try:
            return list(self._page.evaluate(script, limit) or [])
        except Exception:
            return []

    def _obs(self, note: str, text_limit: int = 800) -> Observation:
        assert self._page is not None
        self.url = self._page.url
        self.title = self._page.title()
        try:
            body = self._page.inner_text("body")[:text_limit]
        except Exception:
            body = ""
        heading = ""
        try:
            h = self._page.locator("h1").first
            if h.count() > 0:
                heading = (h.inner_text(timeout=2000) or "").strip()
        except Exception:
            heading = ""
        preview = f"{heading}. {body}".strip() if heading and heading not in body[:120] else body
        return Observation(
            url=self.url,
            title=self.title,
            text_preview=preview[:text_limit],
            interactive=self._list_interactive(),
            note=note,
        )

    def goto(self, url: str) -> Observation:
        if not url.startswith("http"):
            url = "https://" + url
        self._ensure()
        assert self._page is not None
        self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        return self._obs("playwright")

    def extract_text(self) -> Observation:
        self._ensure()
        return self._obs("playwright-extract", text_limit=1200)

    def click(self, target: str) -> Observation:
        self._ensure()
        assert self._page is not None
        t = (target or "").strip()
        last_err: Exception | None = None
        strategies = []
        if t.startswith("#") or t.startswith(".") or "[" in t or t.startswith("text="):
            strategies.append(("css_or_text", t))
        strategies.extend(
            [
                ("get_by_role_link", t),
                ("get_by_role_button", t),
                ("get_by_text", t),
                ("css", t),
            ]
        )
        for kind, val in strategies:
            try:
                if kind == "get_by_role_link":
                    self._page.get_by_role("link", name=val, exact=False).first.click(timeout=4000)
                elif kind == "get_by_role_button":
                    self._page.get_by_role("button", name=val, exact=False).first.click(timeout=4000)
                elif kind == "get_by_text":
                    self._page.get_by_text(val, exact=False).first.click(timeout=4000)
                else:
                    self._page.click(val, timeout=4000)
                return self._obs(f"pw-click:{t}", text_limit=400)
            except Exception as e:
                last_err = e
                continue
        raise RuntimeError(f"click failed for {t!r}: {last_err}")

    def type_text(self, target: str, value: str) -> Observation:
        self._ensure()
        assert self._page is not None
        t = (target or "").strip()
        last_err: Exception | None = None
        for attempt in (
            lambda: self._page.get_by_label(t, exact=False).fill(value, timeout=4000),
            lambda: self._page.get_by_placeholder(t, exact=False).fill(value, timeout=4000),
            lambda: self._page.locator(t).fill(value, timeout=4000),
            lambda: self._page.fill(t, value, timeout=4000),
        ):
            try:
                attempt()
                return Observation(
                    url=self._page.url,
                    title=self._page.title(),
                    text_preview=f"typed into {t}",
                    interactive=self._list_interactive(),
                    note=f"pw-type:{t}",
                )
            except Exception as e:
                last_err = e
                continue
        raise RuntimeError(f"type failed for {t!r}: {last_err}")

    def screenshot(self, path: str = "shot.png") -> str:
        self._ensure()
        assert self._page is not None
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
        self._page = None
        self._browser = None
        self._pw = None
