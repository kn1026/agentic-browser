#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from agentic_browser.agent import Agent

def main():
    agent = Agent(dry_run=True, max_steps=5, receipts_dir=str(Path(__file__).resolve().parents[1] / "receipts"))
    result = agent.run("Open example.com and extract the main heading")
    agent.close()
    print("ok=", result.ok)
    print(result.final_reason)
    return 0 if result.ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
