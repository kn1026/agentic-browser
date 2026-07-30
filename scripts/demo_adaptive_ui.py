#!/usr/bin/env python3
"""M3 one-command adaptive demo tour (run → frames → index → serve hint).

Usage:
  python scripts/demo_adaptive_ui.py
  python scripts/demo_adaptive_ui.py --serve
  python scripts/demo_adaptive_ui.py --dir /tmp/ab-tour --json

Zinley agent controlled (zinley.com). Use at your own risk.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agentic_browser.demo import DEFAULT_TOUR_GOAL, run_demo_tour
from agentic_browser.serve import DEFAULT_HOST, DEFAULT_PORT, serve_viewer


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="agentic-browser adaptive UI demo tour (M3)")
    p.add_argument("goal", nargs="?", default=DEFAULT_TOUR_GOAL)
    p.add_argument("--live", action="store_true", help="use Playwright Chromium")
    p.add_argument("--dir", default="", help="output tour directory")
    p.add_argument("--json", action="store_true")
    p.add_argument("--serve", action="store_true", help="serve tour on loopback")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--open", action="store_true", help="open default browser when serving")
    args = p.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    out = args.dir or None
    tour = run_demo_tour(
        args.goal,
        out_dir=out,
        dry_run=not args.live,
        max_steps=8,
        receipts_dir=root / "receipts",
    )

    if args.json:
        print(json.dumps(tour.to_dict(), indent=2))
    else:
        print("adaptive demo tour (H-UI-m3-demo-tour-v1)")
        print(f"ok={tour.ok}")
        print(f"goal={tour.goal}")
        print(f"dir={tour.out_dir}")
        print(f"index={tour.tour_index_path}")
        print(f"viewer={tour.viewer_path}")
        print(f"frames={len(tour.frame_paths)} phases={' → '.join(tour.phases)}")
        print(f"densities={sorted(set(tour.densities))}")
        print("--- serve one-liner ---")
        print(tour.serve_hint)
        print("Zinley agent controlled · use at your own risk · zinley.com")

    if not args.serve:
        return 0 if tour.ok else 1

    try:
        server = serve_viewer(
            path=tour.out_dir,
            host=args.host,
            port=int(args.port),
            background=True,
            open_browser=bool(args.open),
        )
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    print(f"url: {server.url}")
    print("Ctrl+C to stop")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        server.stop()
    return 0 if tour.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
