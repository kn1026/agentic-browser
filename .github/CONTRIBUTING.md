# Contributing

Thanks for wanting to help. This repo is an **adaptive agentic UI browser** experiment (not another browser-use clone).

## Rules of the road

1. **Never push to `main`.** Open a pull request from a branch or fork.
2. **`main` is protected.** Merges only after review. A Zinley agent (zinley.com) reviews PRs carefully before any merge consideration.
3. **Use at your own risk.** The project is agent-run and moves fast.
4. Prefer changes that move **adaptive UI / human-focus / transform-to-viewer**. Skip drive-by browser-automation feature dumps.

## PR checklist (you)

- Small, focused diff
- Tests pass: `python -m pytest -q` (with venv + optional Playwright)
- No secrets, no opaque payloads, no unexplained binary blobs
- Fill out the PR template

## What the agent checks before merge

- Open PRs every lab run
- Diff for malware / supply-chain smell (secrets, reverse shells, `curl|bash`, suspicious base64, unexpected binary assets, silent dependency swaps)
- Whether the change makes product sense (adaptive UI north star) — **nonsense PRs are closed/skipped**
- CI green when available
- Agent may request changes, close junk, or escalate to Khoi. Agent does **not** auto-merge untrusted PRs without a careful review pass.

## Branch naming

`feat/...`, `fix/...`, `docs/...`, `chore/...`
