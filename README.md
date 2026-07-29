# agentic-browser

**Adaptive agentic UI browser** — not another browser-use clone.

The browser should feel alive for a human: UI that transforms to the viewer and the task, fast and smooth, agentic where it helps and quiet where it does not. Breakthrough goal is adaptive interface + agent loop together, not "yet another click bot."

Built in public by [@khoi_danny](https://x.com/khoi_danny).

## ⚠️ Who runs this repo

This repository is **100% run and controlled by a Zinley agent** ([zinley.com](https://zinley.com)) on Zinley's Computer — research, builds, tests, commits, and BIP posts.

**Use at your own risk.** Expect rapid autonomous commits, experimental APIs, and breaking changes. Do not treat this as a stable product or unattended production dependency.

Agent / model labels on lab posts: Zinley agent · zinley.com · model: Grok 4.5 (update if runtime changes).

## Contributing / PRs

- **Do not push to `main`.** Open a pull request (see [CONTRIBUTING.md](.github/CONTRIBUTING.md)).
- `main` is meant to stay protected; merges only after review.
- Before every lab task, the Zinley agent **checks open PRs**, runs malware/secret smell scans, and may skip/close nonsense PRs. Suspicious PRs are never auto-merged.
- CI: `.github/workflows/pr-guard.yml` (pytest + diff smell scan).

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

**M2 foundation landed** + **first adaptive viewer slice (H-UI-adaptive-viewer-v1)**. Product arc stays human-focus UI transform, not more automation wrappers.

- M1 Playwright path green
- M2: goal-token match, type/fill, fail-soft receipts, click/type→extract phase-advance, stricter name-token match (no role-only / bare click invent)
- M2.5 start: adaptive HTML viewer — phase/density chrome from receipts (`--viewer`)

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

# adaptive human-focus viewer (HTML snapshot; layout shifts with phase)
python -m agentic_browser --viewer "Open example.com and extract the main heading"
python -m agentic_browser --viewer --viewer-path /tmp/viewer.html "click More information then extract heading"

# demo
python scripts/demo_example.py
python scripts/demo_example.py --live
```

## Design

- `Browser` / `PlaywrightBrowser` — thin wrapper (goto, click, type, extract, screenshot)
- `Planner` — goal + observation → one next step
- `Agent` — observe/plan/act until done / max steps
- `Receipts` — JSON step log under `receipts/`
- `Viewer` — adaptive HTML chrome from `AgentResult` (phase · density · trust); not a static debug dump

## Why not wrap browser-use / Stagehand / agent-browser?

Those are great. This lab is building a different bet: **human-facing adaptive UI + agent loop**, owned end-to-end, tiny core first. We steal good ideas; we do not rebrand another automation SDK.

## Roadmap

- [x] M0 scaffold + CLI
- [x] M1 Playwright Chromium + `--live`
- [x] M2 planner quality + receipts (match harden done; keep green)
- [x] M2.5 slice: adaptive viewer v1 (`viewer.py`, `--viewer`, density/phase transform)
- [ ] M2.5 polish: live progressive disclosure + stronger trust surfaces mid-run
- [ ] M3 OSS polish + shareable adaptive demo

## License

MIT (planned)

## Repo

https://github.com/kn1026/agentic-browser

Again: **Zinley agent controlled · use at your own risk.**
