#!/usr/bin/env python3
"""NovaXinWei CLI — unified entry point.

Usage:
    python -m novaxinwei fetch <url> [--timeout N] [--json]
    python -m novaxinwei dorks shodan <target>
    python -m novaxinwei dorks github <query>
    python -m novaxinwei check
    python -m novaxinwei fetch-parallel <url1> <url2> ... [--workers N] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Optional


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="novaxinwei",
        description="NovaXinWei — web recon with WAF bypass, parallel fetch, and dork databases.",
    )
    sub = p.add_subparsers(dest="command", help="Available commands")

    # fetch
    fetch_p = sub.add_parser("fetch", help="Fetch a URL through the WAF-bypass chain")
    fetch_p.add_argument("url", help="URL to fetch")
    fetch_p.add_argument("--timeout", type=int, default=25, help="Per-attempt timeout (default 25)")
    fetch_p.add_argument("--json", action="store_true", help="Output as JSON")
    fetch_p.add_argument("--trace", action="store_true", help="Print attempt trace to stderr")
    fetch_p.add_argument("--selector", "-s", action="append", default=None, dest="selectors", metavar="CSS")
    fetch_p.add_argument("--device", choices=("auto", "desktop", "mobile"), default="auto")
    fetch_p.add_argument("--no-playwright", action="store_true", help="Skip Playwright fallback")
    fetch_p.add_argument("--no-phase0", action="store_true", help="Skip Phase 0 API router")

    # fetch-parallel
    fp = sub.add_parser("fetch-parallel", help="Fetch multiple URLs in parallel")
    fp.add_argument("urls", nargs="+", help="URLs to fetch")
    fp.add_argument("--workers", type=int, default=5, help="Max parallel workers (default 5)")
    fp.add_argument("--timeout", type=int, default=25, help="Per-attempt timeout")
    fp.add_argument("--json", action="store_true", help="Output as JSON")

    # dorks
    dorks_p = sub.add_parser("dorks", help="Run dork databases")
    dorks_sub = dorks_p.add_subparsers(dest="dork_type", help="Dork type")
    shodan_p = dorks_sub.add_parser("shodan", help="Shodan dork lookup")
    shodan_p.add_argument("target", help="Target to dork")
    shodan_p.add_argument("--json", action="store_true")
    github_p = dorks_sub.add_parser("github", help="GitHub dork search")
    github_p.add_argument("query", help="Search query")
    github_p.add_argument("--json", action="store_true")

    # check
    sub.add_parser("check", help="Check channel availability")

    return p


def cmd_fetch(args: argparse.Namespace) -> int:
    from novaxinwei.engine.fetch_chain import fetch
    from novaxinwei.engine.url_masking import mask_url

    try:
        result = fetch(
            args.url,
            success_selectors=args.selectors,
            device_class=args.device,
            timeout=args.timeout,
            enable_playwright=not args.no_playwright,
            enable_phase0=not args.no_phase0,
        )
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    if args.trace:
        for att in result.trace:
            d = att.to_dict()
            print(f"[{d['phase']:<8}] {d['executor']:<18} status={d['status']:>4} verdict={d['verdict']}", file=sys.stderr)

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(result.to_untrusted_text(), end="")

    return 0 if result.ok else 1


def cmd_fetch_parallel(args: argparse.Namespace) -> int:
    from novaxinwei.channels import fetch_parallel
    results = fetch_parallel(args.urls, timeout=args.timeout, max_workers=args.workers)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for url, r in results.items():
            status = "✓" if r["ok"] else "✗"
            print(f"{status} {url[:80]}{'...' if len(url) > 80 else ''}")
    return 0


def cmd_dorks(args: argparse.Namespace) -> int:
    if args.dork_type == "shodan":
        return _cmd_shodan(args)
    elif args.dork_type == "github":
        return _cmd_github(args)
    print("Usage: novaxinwei dorks {shodan|github} ...", file=sys.stderr)
    return 2


def _cmd_shodan(args: argparse.Namespace) -> int:
    import yaml
    dorks_path = __import__("pathlib").Path(__file__).parent / "dorks" / "shodan-dorks.yaml"
    with open(dorks_path) as f:
        data = yaml.safe_load(f)
    target = args.target.lower()
    results = []
    for category, dorks in data.items():
        if not isinstance(dorks, list):
            continue
        for entry in dorks:
            content = entry.get("content", "")
            title = entry.get("title", "")
            if any(kw in target for kw in content.lower().split()):
                results.append({"category": category, "query": content, "description": title})
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for r in results:
            print(f"[{r['category']}] {r['query']} — {r['description']}")
    return 0


def _cmd_github(args: argparse.Namespace) -> int:
    dorks_path = __import__("pathlib").Path(__file__).parent / "dorks" / "github-dorks.txt"
    with open(dorks_path) as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    query = args.query.lower()
    matches = [l for l in lines if query in l.lower()]
    if args.json:
        print(json.dumps(matches, ensure_ascii=False, indent=2))
    else:
        for m in matches:
            print(m)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    from novaxinwei.channels import ALL_CHANNELS
    for ch in ALL_CHANNELS:
        ok = ch.check()
        status = "✓" if ok else "✗"
        backend = ch.active_backend or "none"
        print(f"{status} {ch.name:<15} backend={backend:<12} tier={ch.tier}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "fetch":
        return cmd_fetch(args)
    elif args.command == "fetch-parallel":
        return cmd_fetch_parallel(args)
    elif args.command == "dorks":
        return cmd_dorks(args)
    elif args.command == "check":
        return cmd_check(args)
    else:
        build_parser().print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
