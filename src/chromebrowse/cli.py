"""Command line interface for chromebrowse.

Examples::

    chromebrowse info
    chromebrowse install
    chromebrowse text https://example.com
    chromebrowse fetch https://example.com --json
    chromebrowse links https://example.com
    chromebrowse shot https://example.com out.png --full
    chromebrowse pdf https://example.com out.pdf
    chromebrowse eval https://example.com "document.title"
    chromebrowse open https://example.com            # interactive REPL
    chromebrowse session list
    chromebrowse session show mysession
    chromebrowse session delete mysession
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__
from .browser import Browser
from .config import BrowserConfig, platform_info, find_chromium
from .exceptions import BrowserError
from .session import Session, delete_session, list_sessions


# --------------------------------------------------------------------- helpers
def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--timeout", type=float, default=None, help="navigation timeout in ms")
    p.add_argument("--wait-until", default="load",
                   choices=["load", "domcontentloaded", "networkidle", "commit"],
                   help="load state to wait for (default: load)")
    p.add_argument("--no-js", action="store_true", help="disable JavaScript")
    p.add_argument("--show", action="store_true", help="run headful (visible window)")
    p.add_argument("--user-agent", default=None, help="override User-Agent")
    p.add_argument("--header", action="append", metavar="K:V", default=None,
                   help="extra HTTP header (repeatable)")
    p.add_argument("--proxy", default=None, help="proxy server URL")


def _config_from_args(args: argparse.Namespace) -> BrowserConfig:
    headers: Dict[str, str] = {}
    for h in (getattr(args, "header", None) or []):
        if ":" in h:
            k, v = h.split(":", 1)
            headers[k.strip()] = v.strip()
    cfg = BrowserConfig(
        headless=not getattr(args, "show", False),
        java_script_enabled=not getattr(args, "no_js", False),
        extra_headers=headers,
    )
    if getattr(args, "timeout", None):
        cfg.navigation_timeout = args.timeout
        cfg.default_timeout = args.timeout
    if getattr(args, "user_agent", None):
        cfg.user_agent = args.user_agent
    if getattr(args, "proxy", None):
        cfg.proxy = args.proxy
    return cfg


def _print_json(data: Any) -> None:
    json.dump(data, sys.stdout, indent=2, ensure_ascii=False, default=str)
    sys.stdout.write("\n")


# ------------------------------------------------------------------- commands
def cmd_info(args: argparse.Namespace) -> int:
    info = platform_info()
    info["chromebrowse"] = __version__
    _print_json(info)
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    """Download Chromium into a project-local .browsers directory."""
    from .config import default_install_dir, install_chromium

    target = Path(args.dir).expanduser().resolve() if args.dir else default_install_dir()

    existing = find_chromium()
    if existing and not args.force:
        print(f"Chromium already available: {existing}")
        print("Use --force to download a fresh copy anyway.")
        return 0

    print(f"Installing Chromium into {target} ...")
    try:
        exe = install_chromium(target, quiet=False)
    except BrowserError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print("Done. Chromium installed at:")
    print(" ", exe)
    return 0


def cmd_text(args: argparse.Namespace) -> int:
    with Browser(_config_from_args(args)) as b:
        page = b.open(args.url, wait_until=args.wait_until, timeout=args.timeout)
        text = page.text()
    if args.max_chars:
        text = text[: args.max_chars]
    print(text)
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    with Browser(_config_from_args(args)) as b:
        content = b.fetch(
            args.url,
            wait_until=args.wait_until,
            timeout=args.timeout,
            include_html=args.html,
            include_links=args.links,
            include_markdown=args.markdown,
        )
    if args.json:
        _print_json(content.as_dict())
    else:
        if args.title:
            print(content.title)
        output = content.markdown if args.markdown else content.text
        print(output[: args.max_chars] if args.max_chars else output)
    return 0


def cmd_links(args: argparse.Namespace) -> int:
    with Browser(_config_from_args(args)) as b:
        links = b.links(args.url, wait_until=args.wait_until, timeout=args.timeout)
    if args.json:
        _print_json([l.as_dict() for l in links])
    else:
        for l in links:
            label = l.text or l.href
            print(f"{label}\t{l.href}" if not args.href_only else l.href)
    return 0


def cmd_shot(args: argparse.Namespace) -> int:
    path = Path(args.output).expanduser()
    with Browser(_config_from_args(args)) as b:
        page = b.open(args.url, wait_until=args.wait_until, timeout=args.timeout)
        snap = page.snapshot(
            path=path,
            full_page=args.full,
            selector=args.selector,
            image_type=args.type,
            quality=args.quality,
        )
    print(f"saved {snap.path}")
    return 0


def cmd_pdf(args: argparse.Namespace) -> int:
    path = Path(args.output).expanduser()
    with Browser(_config_from_args(args)) as b:
        page = b.open(args.url, wait_until=args.wait_until, timeout=args.timeout)
        page.pdf(path)
    print(f"saved {path}")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    with Browser(_config_from_args(args)) as b:
        page = b.open(args.url, wait_until=args.wait_until, timeout=args.timeout)
        result = page.evaluate(args.script)
    _print_json(result) if args.json else print(result)
    return 0


def cmd_cookies(args: argparse.Namespace) -> int:
    with Browser(_config_from_args(args)) as b:
        page = b.open(args.url, wait_until=args.wait_until, timeout=args.timeout)
        cookies = page.cookies()
    if args.json:
        _print_json(cookies)
    else:
        for c in cookies:
            print(f"{c.get('name')}={c.get('value')}\t{c.get('domain','')}")
    return 0


def cmd_open(args: argparse.Namespace) -> int:
    """Interactive REPL driving a single browser page."""
    cfg = _config_from_args(args)
    with Browser(cfg) as b:
        page = b.open(args.url, wait_until=args.wait_until, timeout=args.timeout)
        print(f"Opened {page.current_url()}  ({page.title!r})")
        print("Commands: text, html, title, url, links, shot FILE, click SEL,")
        print("          fill SEL VALUE, wait SEL, goto URL, eval JS, back, quit")
        while True:
            try:
                line = input("cb> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            parts = line.split(None, 1)
            cmd = parts[0].lower()
            rest = parts[1] if len(parts) > 1 else ""
            try:
                if cmd in ("quit", "exit", "q"):
                    break
                elif cmd == "text":
                    print(page.text()[: args.max_chars or 2000])
                elif cmd == "html":
                    print(page.content()[: args.max_chars or 2000])
                elif cmd == "title":
                    print(page.title)
                elif cmd == "url":
                    print(page.current_url())
                elif cmd == "links":
                    for l in page.links()[:50]:
                        print(f"{l.text}\t{l.href}")
                elif cmd == "shot":
                    print("saved", page.snapshot(path=rest or "shot.png", full_page=True).path)
                elif cmd == "click":
                    page.click(rest)
                    print("clicked", rest)
                elif cmd == "fill":
                    sel, _, val = rest.partition(" ")
                    page.fill(sel, val)
                    print("filled", sel)
                elif cmd == "wait":
                    page.wait_for(rest)
                    print("ok")
                elif cmd == "goto":
                    page.goto(rest, wait_until=args.wait_until)
                    print("at", page.current_url())
                elif cmd == "eval":
                    print(page.evaluate(rest))
                elif cmd == "back":
                    page.go_back()
                    print("at", page.current_url())
                else:
                    print("unknown command:", cmd)
            except BrowserError as exc:
                print("error:", exc)
    return 0


def cmd_session(args: argparse.Namespace) -> int:
    if args.action == "list":
        rows = list_sessions(args.state_dir)
        if args.json:
            _print_json(rows)
        elif not rows:
            print("no saved sessions")
        else:
            for r in rows:
                print(f"{r['name']}\t{r['bytes']} bytes\t{r['modified']}")
        return 0
    if args.action == "delete":
        ok = delete_session(args.name, args.state_dir)
        print("deleted" if ok else "not found")
        return 0 if ok else 1
    if args.action == "show":
        # Inspect the persisted file directly. Starting a fresh browser here
        # would show an empty cookie jar rather than the saved session.
        state_file = Session(
            args.name, state_dir=args.state_dir, persist=False
        ).state_path
        if not state_file.is_file():
            print(f"session {args.name!r} not found", file=sys.stderr)
            return 1
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                raise ValueError("storage state must be a JSON object")
            cookies = state.get("cookies", [])
            if not isinstance(cookies, list):
                raise ValueError("'cookies' must be a list")
        except (OSError, ValueError) as exc:
            print(f"error reading session {args.name!r}: {exc}", file=sys.stderr)
            return 1
        if args.json:
            _print_json(cookies)
        else:
            print(f"session {args.name!r}: {len(cookies)} cookie(s)")
            for cookie in cookies:
                print(
                    f"  {cookie.get('name')}={cookie.get('value')}\t"
                    f"{cookie.get('domain', '')}"
                )
        return 0
    if args.action == "clear":
        # This command is a new process, so deleting the state file is enough;
        # don't launch Chromium merely to clear an empty in-memory context.
        ok = delete_session(args.name, args.state_dir)
        print("cleared" if ok else "not found")
        return 0 if ok else 1
    print("unknown session action", file=sys.stderr)
    return 2


# ---------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chromebrowse",
        description="Chromium-based browsing for Python from the command line.",
    )
    parser.add_argument("--version", action="version", version=f"chromebrowse {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("info", help="show runtime and Chromium diagnostics")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("install", help="download Chromium locally")
    p.add_argument("--dir", default=None, help="destination directory (default: auto-detected)")
    p.add_argument("--force", action="store_true", help="download even if Chromium is already available")
    p.set_defaults(func=cmd_install)

    p = sub.add_parser("text", help="print rendered page text")
    p.add_argument("url")
    p.add_argument("--max-chars", type=int, default=0)
    _add_common(p)
    p.set_defaults(func=cmd_text)

    p = sub.add_parser("fetch", help="extract structured page content")
    p.add_argument("url")
    p.add_argument("--json", action="store_true")
    p.add_argument("--html", action="store_true", help="include raw HTML")
    p.add_argument("--links", action="store_true", help="include links")
    p.add_argument("--markdown", action="store_true", help="include Markdown conversion")
    p.add_argument("--title", action="store_true", help="print title first")
    p.add_argument("--max-chars", type=int, default=0)
    _add_common(p)
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("links", help="list links on a page")
    p.add_argument("url")
    p.add_argument("--json", action="store_true")
    p.add_argument("--href-only", action="store_true")
    _add_common(p)
    p.set_defaults(func=cmd_links)

    p = sub.add_parser("shot", help="capture a screenshot")
    p.add_argument("url")
    p.add_argument("output")
    p.add_argument("--full", action="store_true", help="full page (default: viewport)")
    p.add_argument("--selector", default=None)
    p.add_argument("--type", default="png", choices=["png", "jpeg", "webp"])
    p.add_argument("--quality", type=int, default=None)
    _add_common(p)
    p.set_defaults(func=cmd_shot)

    p = sub.add_parser("pdf", help="render page to PDF")
    p.add_argument("url")
    p.add_argument("output")
    _add_common(p)
    p.set_defaults(func=cmd_pdf)

    p = sub.add_parser("eval", help="evaluate JavaScript on a page")
    p.add_argument("url")
    p.add_argument("script")
    p.add_argument("--json", action="store_true")
    _add_common(p)
    p.set_defaults(func=cmd_eval)

    p = sub.add_parser("cookies", help="dump cookies for a URL")
    p.add_argument("url")
    p.add_argument("--json", action="store_true")
    _add_common(p)
    p.set_defaults(func=cmd_cookies)

    p = sub.add_parser("open", help="interactive browser REPL")
    p.add_argument("url")
    p.add_argument("--max-chars", type=int, default=2000)
    _add_common(p)
    p.set_defaults(func=cmd_open)

    p = sub.add_parser("session", help="manage persisted sessions")
    p.add_argument("action", choices=["list", "show", "delete", "clear"])
    p.add_argument("name", nargs="?", default="default")
    p.add_argument("--json", action="store_true")
    p.add_argument("--state-dir", default=None)
    p.add_argument("--show", action="store_true")
    p.set_defaults(func=cmd_session)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except BrowserError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())