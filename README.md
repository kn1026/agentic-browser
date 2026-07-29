# agentic-browser

**Adaptive agentic UI browser** — not another browser-use clone.

The browser should feel alive for a human: UI that transforms to the viewer and the task, fast and smooth, agentic where it helps and quiet where it does not. Breakthrough goal is adaptive interface + agent loop together, not "yet another click bot."

Built in public by [@khoi_danny](https://x.com/khoi_danny).

## ⚠️ Who runs this repo

This repository is **100% run and controlled by a Zinley agent** ([zinley.com](https://zinley.com)) on Zinley's Computer — research, builds, tests, commits, and BIP posts.

**Use at your own risk.** Expect rapid autonomous commits, experimental APIs, and breaking changes. Do not treat this as a stable product or unattended production dependency.

Agent / model labels on lab posts: Zinley agent · zinley.com · model: Grok 4.5 (update if runtime changes).

## North star (breakthrough)

| Not this | This |
|----------|------|
| Generic browser-use / RPA wrapper | Adaptive **agentic UI** that reshapes to the human + goal |
| Dump full page chrome forever | Surface only what the viewer needs, when they need it |
| Slow multi-step thrash | Fast, smooth, human-focus paths |
| Feature parity with browser-use | Creative UI transforms + solid observe→plan→act core |

Core loop still matters as substrate:
observe → plan → act (click/type/navigate) → receipts — then **adapt the UI layer** so a human can watch, steer, and trust it.

## Status

**M2 foundation in progress** (planner v1 + compound phase). Next product arc: **adaptive viewer UI** on top of the loop (live task surface, progressive disclosure, human-focus chrome), not more "browser automation for automation's sake."

- M1 Playwright path green
- M2: goal-token match, type/fill, fail-soft receipts, click/type→extract phase-advance
- Next: match harden → adaptive UI viewer (transform layout/controls to task + human)

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

# demo
python scripts/demo_example.py
python scripts/demo_example.py --live
```

## Design

- `Browser` / `PlaywrightBrowser` — thin wrapper (goto, click, type, extract, screenshot)
- `Planner` — goal + observation → one next step
- `Agent` — observe/plan/act until done / max steps
- `Receipts` — JSON step log under `receipts/`
- **Upcoming:** adaptive UI shell — viewer that morphs with goal, confidence, and human attention (not a fixed debugger panel forever)

## Why not wrap browser-use / Stagehand / agent-browser?

Those are great. This lab is building a different bet: **human-facing adaptive UI + agent loop**, owned end-to-end, tiny core first. We steal good ideas; we do not rebrand another automation SDK.

## Roadmap

- [x] M0 scaffold + CLI
- [x] M1 Playwright Chromium + `--live`
- [ ] M2 planner quality + receipts (in progress)
- [ ] **M2.5 / M3 direction: adaptive agentic UI** — UI transforms to viewer/task; fast human-focus surface; demo that feels new, not "browser-use with a different README"
- [ ] M3 OSS polish + shareable adaptive demo

## License

MIT (planned)

## Repo

https://github.com/kn1026/agentic-browser

Again: **Zinley agent controlled · use at your own risk.**
