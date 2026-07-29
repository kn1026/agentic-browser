#!/usr/bin/env python3
"""Serve adaptive viewer HTML on 127.0.0.1 (stdlib only).

Usage:
  python scripts/serve_viewer.py path/to/viewer.html
  python scripts/serve_viewer.py receipts/   # newest viewer*.html
  python scripts/serve_viewer.py --port 0    # ephemeral port

Zinley agent controlled (zinley.com). Use at your own risk.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agentic_browser.serve import DEFAULT_HOST, DEFAULT_PORT, serve_viewer


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Serve agentic-browser adaptive viewer (loopback)")
    p.add_argument(
        "path",
        nargs="?",
        default="",
        help="viewer HTML file or directory (default: newest receipts/viewer*.html)",
    )
    p.add_argument("--host", default=DEFAULT_HOST, help=f"bind host (default {DEFAULT_HOST})")
    p.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"bind port (default {DEFAULT_PORT}; 0 = ephemeral)",
    )
    p.add_argument("--open", action="store_true", help="open default browser")
    args = p.parse_args(argv)

    path = args.path or None
    try:
        server = serve_viewer(
            path=path,
            host=args.host,
            port=args.port,
            background=True,
            open_browser=bool(args.open),
        )
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    print(f"serving {server.root / server.index_name}")
    print(f"url: {server.url}")
    print("Zinley agent controlled · use at your own risk · zinley.com")
    print("Ctrl+C to stop")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        server.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
