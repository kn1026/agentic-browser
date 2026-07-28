# agentic-browser

Open-source **agentic browser from scratch**.

A small autonomous browser agent:
observe the page → plan the next step → act (click/type/navigate) → leave receipts.

Built in public by [@khoi_danny](https://x.com/khoi_danny).

## Status
**M0/M1 in progress** — scaffold + Playwright backend class.
Next: `playwright install chromium` then `--live` demo.

## Install (dev)
```bash
cd /home/daytona/workspace/agentic-browser
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
# later: playwright install chromium
```

## CLI (current stub)
```bash
python -m agentic_browser "Open example.com and extract the main heading"
python -m agentic_browser --dry-run "Search docs for pricing"
```

## Design
- `Browser` — thin Playwright wrapper (goto, click, type, extract, screenshot)
- `Observer` — DOM snapshot + accessibility-ish summary
- `Planner` — turns goal + observation into one next step
- `Actor` — executes step, returns receipt
- `Agent` — loop until done / max steps / blocked
- `Receipts` — JSONL log of every step for debug + BIP posts

## Why not wrap an existing agent browser?
Learning surface area. Own the loop, the tools, the failure modes.
Will steal good ideas from Browser-use / Stagehand / Playwright MCP — but ship a tiny core first.

## Roadmap
- [x] M0 scaffold + CLI
- [x] M1 Playwright backend class + --live path (install chromium to use)
- [ ] M2 planner quality + step receipts UI/log
- [ ] M3 OSS polish + demo + public link

## License
MIT (planned)
