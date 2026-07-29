from __future__ import annotations

import argparse
import json
import sys

from agentic_browser import __version__
from agentic_browser.agent import Agent


def _build_run_parser(p: argparse.ArgumentParser) -> None:
    p.add_argument("goal", nargs="?", default="Open example.com and extract the main heading")
    p.add_argument("--dry-run", action="store_true", default=True, help="use fake browser (default)")
    p.add_argument("--live", action="store_true", help="use Playwright Chromium if installed")
    p.add_argument("--max-steps", type=int, default=6)
    p.add_argument("--json", action="store_true", help="print full JSON result")
    p.add_argument(
        "--viewer",
        action="store_true",
        help="write adaptive human-focus HTML viewer (phase/density transform)",
    )
    p.add_argument(
        "--viewer-path",
        default="",
        help="optional path for viewer HTML (implies --viewer)",
    )
    p.add_argument(
        "--serve-viewer",
        action="store_true",
        help="after run, serve viewer HTML on 127.0.0.1 (implies --viewer; Ctrl+C to stop)",
    )
    p.add_argument(
        "--serve-host",
        default="127.0.0.1",
        help="bind host for --serve-viewer / serve-viewer (default 127.0.0.1)",
    )
    p.add_argument(
        "--serve-port",
        type=int,
        default=8765,
        help="bind port for --serve-viewer / serve-viewer (default 8765; 0 = ephemeral)",
    )


def _run_agent(args: argparse.Namespace) -> int:
    dry = not args.live
    viewer_path = args.viewer_path or None
    write_viewer = bool(args.viewer or viewer_path or getattr(args, "serve_viewer", False))
    agent = Agent(
        dry_run=dry,
        max_steps=args.max_steps,
        write_viewer=write_viewer,
        viewer_path=viewer_path,
    )
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
        if result.viewer_path:
            print(f"viewer: {result.viewer_path}")

    if getattr(args, "serve_viewer", False) and result.viewer_path:
        from agentic_browser.serve import serve_viewer

        host = getattr(args, "serve_host", "127.0.0.1") or "127.0.0.1"
        port = int(getattr(args, "serve_port", 8765))
        print(f"serving viewer at http://{host}:{port}/ (Ctrl+C to stop)")
        print("Zinley agent controlled · use at your own risk · zinley.com")
        try:
            serve_viewer(
                path=result.viewer_path,
                host=host,
                port=port,
                background=False,
            )
        except KeyboardInterrupt:
            print("\nstopped.")
    return 0 if result.ok else 1


def _serve_viewer_cmd(args: argparse.Namespace) -> int:
    from agentic_browser.serve import serve_viewer

    path = args.path or None
    host = args.serve_host or "127.0.0.1"
    port = int(args.serve_port)
    try:
        server = serve_viewer(path=path, host=host, port=port, background=True)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"serving {server.root / server.index_name}")
    print(f"url: {server.url}")
    print("Zinley agent controlled · use at your own risk · zinley.com")
    print("Ctrl+C to stop")
    try:
        while True:
            import time

            time.sleep(3600)
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        server.stop()
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # Subcommand: serve-viewer (shareable local adaptive demo)
    if argv and argv[0] in {"serve-viewer", "serve"}:
        sp = argparse.ArgumentParser(
            prog="agentic-browser serve-viewer",
            description="Serve adaptive viewer HTML on loopback (stdlib only, no SPA)",
        )
        sp.add_argument(
            "path",
            nargs="?",
            default="",
            help="viewer.html file or directory (default: newest under receipts/ or cwd)",
        )
        sp.add_argument("--host", dest="serve_host", default="127.0.0.1")
        sp.add_argument("--port", dest="serve_port", type=int, default=8765)
        sp.add_argument("--version", action="store_true")
        sargs = sp.parse_args(argv[1:])
        if sargs.version:
            print(__version__)
            return 0
        return _serve_viewer_cmd(sargs)

    p = argparse.ArgumentParser(prog="agentic-browser", description="Agentic browser from scratch")
    _build_run_parser(p)
    p.add_argument("--version", action="store_true")
    args = p.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    return _run_agent(args)


if __name__ == "__main__":
    raise SystemExit(main())
