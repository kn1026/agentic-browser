#!/usr/bin/env python3
"""Quick demo: dry-run by default, --live for real Chromium."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from agentic_browser.agent import Agent


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="agentic-browser demo")
    p.add_argument("--live", action="store_true", help="use Playwright Chromium")
    p.add_argument(
        "goal",
        nargs="?",
        default="Open example.com and extract the main heading",
    )
    args = p.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    agent = Agent(
        dry_run=not args.live,
        max_steps=5,
        receipts_dir=str(root / "receipts"),
    )
    try:
        result = agent.run(args.goal)
    finally:
        agent.close()

    print("live=", args.live)
    print("ok=", result.ok)
    print(result.final_reason)
    if result.receipts:
        last = result.receipts[-1]
        if last.observation and last.observation.interactive:
            print("interactive=", last.observation.interactive[:5])
        # show backend note from first successful page obs
        for r in result.receipts:
            if r.observation and r.observation.note:
                print("backend_note=", r.observation.note)
                break
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
