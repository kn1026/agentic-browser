from __future__ import annotations

import argparse
import json
import sys

from agentic_browser import __version__
from agentic_browser.agent import Agent


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="agentic-browser", description="Agentic browser from scratch")
    p.add_argument("goal", nargs="?", default="Open example.com and extract the main heading")
    p.add_argument("--dry-run", action="store_true", default=True, help="use fake browser (default)")
    p.add_argument("--live", action="store_true", help="reserved for Playwright session (M1)")
    p.add_argument("--max-steps", type=int, default=6)
    p.add_argument("--json", action="store_true", help="print full JSON result")
    p.add_argument("--version", action="store_true")
    args = p.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    dry = not args.live
    agent = Agent(dry_run=dry, max_steps=args.max_steps)
    try:
        result = agent.run(args.goal)
    finally:
        agent.close()

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"goal: {result.goal}")
        print(f"ok: {result.ok}")
        print(f"final: {result.final_reason}")
        print("steps:")
        for i, r in enumerate(result.receipts, 1):
            s = r.step
            print(f"  {i}. {s.kind} {s.target} -> {'ok' if r.ok else 'fail'} ({r.detail[:100]})")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
