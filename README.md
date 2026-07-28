# agentic-browser

Open-source **agentic browser from scratch**.

A small autonomous browser agent:
observe the page → plan the next step → act (click/type/navigate) → leave receipts.

Built in public by [@khoi_danny](https://x.com/khoi_danny).

## Status
**M1 done** — real Playwright Chromium `goto` / `extract_text` on public pages, with interactive target listing and multi-strategy click/type.
Next: M2 planner quality + richer receipts.

## Install (dev)
```bash
cd agentic-browser
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[browser,dev]"
playwright install chromium
```

## CLI
```bash
# fake browser (default, offline)
python -m agentic_browser "Open example.com and extract the main heading"

# real Chromium
python -m agentic_browser --live "Open example.com and extract the main heading"
python -m agentic_browser --live --json "Open example.com and extract the main heading"

# demo script
python scripts/demo_example.py
python scripts/demo_example.py --live
```

## Design
- `Browser` / `PlaywrightBrowser` — thin wrapper (goto, click, type, extract, screenshot)
- `Planner` — turns goal + observation into one next step (deterministic v0)
- `Agent` — observe/plan/act loop until done / max steps
- `Receipts` — JSON log of every step under `receipts/`

## Why not wrap an existing agent browser?
Learning surface area. Own the loop, the tools, the failure modes.
Will steal good ideas from Browser-use / Stagehand / Playwright MCP — but ship a tiny core first.

## Roadmap
- [x] M0 scaffold + CLI
- [x] M1 Playwright Chromium + `--live` on public site + tighter selectors
- [ ] M2 planner quality + step receipts UI/log
- [ ] M3 OSS polish + demo + public link

## License
MIT (planned)

## Repo
https://github.com/kn1026/agentic-browser
