"""Tiny stdlib static serve for the adaptive viewer HTML.

H-UI-static-serve-v1 — no SPA, no Flask/FastAPI/websocket.
Default bind is loopback only (127.0.0.1). Use at your own risk.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


class ViewerHTTPRequestHandler(SimpleHTTPRequestHandler):
    """Serve a directory; map `/` to a preferred viewer HTML when set."""

    # Set on the class via partial / subclass factory before server start.
    viewer_root: Path = Path(".")
    index_name: str = "index.html"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(self.viewer_root), **kwargs)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        # Quiet by default — lab demos should not spam stdout.
        return

    def translate_path(self, path: str) -> str:
        parsed = urlparse(path)
        raw = unquote(parsed.path)
        if raw in ("", "/"):
            preferred = self.viewer_root / self.index_name
            if preferred.is_file():
                return str(preferred.resolve())
            # Fall back to first *.html in root (deterministic sort).
            htmls = sorted(self.viewer_root.glob("*.html"))
            if htmls:
                return str(htmls[0].resolve())
        return super().translate_path(path)


def _make_handler(root: Path, preferred_index: str) -> type[ViewerHTTPRequestHandler]:
    resolved_root = root.resolve()
    index_file = preferred_index

    class _Handler(ViewerHTTPRequestHandler):
        viewer_root = resolved_root
        index_name = index_file

    return _Handler


@dataclass
class ViewerServer:
    """Running (or ready) stdlib viewer server — stop() is always safe."""

    host: str
    port: int
    root: Path
    index_name: str
    url: str
    _httpd: ThreadingHTTPServer | None = None
    _thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        return self.url.rstrip("/")

    def start(self, background: bool = True) -> "ViewerServer":
        if self._httpd is not None:
            return self
        handler = _make_handler(self.root, self.index_name)
        # Allow quick rebind in lab loops.
        ThreadingHTTPServer.allow_reuse_address = True
        httpd = ThreadingHTTPServer((self.host, self.port), handler)
        # If port was 0, capture the ephemeral assignment.
        self.port = int(httpd.server_address[1])
        self.url = f"http://{self.host}:{self.port}/"
        self._httpd = httpd
        if background:
            t = threading.Thread(target=httpd.serve_forever, name="viewer-serve", daemon=True)
            t.start()
            self._thread = t
            # Brief settle so accept() is ready for immediate clients.
            time.sleep(0.05)
        else:
            httpd.serve_forever()
        return self

    def stop(self) -> None:
        httpd = self._httpd
        self._httpd = None
        if httpd is None:
            return
        try:
            httpd.shutdown()
        except Exception:
            pass
        try:
            httpd.server_close()
        except Exception:
            pass
        t = self._thread
        self._thread = None
        if t is not None and t.is_alive():
            t.join(timeout=2.0)

    def __enter__(self) -> "ViewerServer":
        return self.start(background=True)

    def __exit__(self, *exc) -> None:
        self.stop()


def resolve_viewer_root(path: str | Path | None) -> tuple[Path, str]:
    """Return (directory_to_serve, preferred_index_filename).

    - file.html → (parent, file.name)
    - directory → (dir, first viewer_*.html or *.html or index.html)
    - None / missing → raise FileNotFoundError with a clear message
    """
    if path is None or str(path).strip() == "":
        # Prefer newest viewer under ./receipts, then cwd.
        candidates: list[Path] = []
        for base in (Path("receipts"), Path(".")):
            if base.is_dir():
                candidates.extend(sorted(base.glob("viewer*.html"), key=lambda p: p.stat().st_mtime, reverse=True))
                candidates.extend(sorted(base.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True))
        # de-dupe preserving order
        seen: set[Path] = set()
        ordered: list[Path] = []
        for c in candidates:
            rp = c.resolve()
            if rp not in seen and c.is_file():
                seen.add(rp)
                ordered.append(c)
        if not ordered:
            raise FileNotFoundError(
                "No viewer HTML found. Run with --viewer first, or pass a path: "
                "agentic-browser serve-viewer path/to/viewer.html"
            )
        path = ordered[0]

    p = Path(path).expanduser().resolve()
    if p.is_file():
        if p.suffix.lower() not in {".html", ".htm"}:
            raise FileNotFoundError(f"Not an HTML viewer file: {p}")
        return p.parent, p.name
    if p.is_dir():
        for name in ("index.html", "viewer.html"):
            if (p / name).is_file():
                return p, name
        htmls = sorted(p.glob("viewer*.html"), key=lambda x: x.stat().st_mtime, reverse=True)
        if not htmls:
            htmls = sorted(p.glob("*.html"), key=lambda x: x.stat().st_mtime, reverse=True)
        if not htmls:
            raise FileNotFoundError(f"No .html files in directory: {p}")
        return p, htmls[0].name
    raise FileNotFoundError(f"Viewer path does not exist: {p}")


def make_server(
    path: str | Path | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> ViewerServer:
    """Build a ViewerServer (not started). Defaults to loopback bind."""
    host = (host or DEFAULT_HOST).strip() or DEFAULT_HOST
    # Hard safety: empty host → loopback. Binding 0.0.0.0 is allowed only if explicit.
    if host in {"", "localhost"}:
        host = DEFAULT_HOST
    root, index_name = resolve_viewer_root(path)
    url = f"http://{host}:{port}/" if port else f"http://{host}/"
    return ViewerServer(host=host, port=int(port), root=root, index_name=index_name, url=url)


def serve_viewer(
    path: str | Path | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    background: bool = False,
    open_browser: bool = False,
) -> ViewerServer:
    """Start serving viewer HTML. foreground blocks; background returns running server."""
    server = make_server(path=path, host=host, port=port)
    server.start(background=background)
    if open_browser:
        try:
            import webbrowser

            webbrowser.open(server.url)
        except Exception:
            pass
    return server


def fetch_viewer_http(
    path: str | Path | None = None,
    host: str = DEFAULT_HOST,
    port: int = 0,
    request_path: str = "/",
    timeout: float = 2.0,
) -> tuple[int, str, str]:
    """Start ephemeral server, GET request_path, stop. Returns (status, body, url).

    Used by tests and dry demos — no long-lived process.
    """
    import urllib.error
    import urllib.request

    server = make_server(path=path, host=host, port=port)
    server.start(background=True)
    try:
        url = server.base_url + request_path.lstrip("/")
        if not request_path.startswith("/"):
            url = server.base_url + "/" + request_path
        else:
            url = server.base_url + request_path
        # Ensure trailing path join is clean when request_path is "/".
        if request_path == "/":
            url = server.url
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return int(resp.status), body, url
    finally:
        server.stop()
