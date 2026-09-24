# -*- coding: utf-8 -*-
"""wayai selftest — pure helpers only.

No network: waybackurls/commoncrawlurls/check_url are never called.

Run:  python tools/wayai/selftest.py
"""

from __future__ import annotations

import importlib.util
import io
import os
import sys
from typing import List


def _load():
    """Load wayai.py once and cache it under its canonical name.

    Reuse from sys.modules on a second call so a caller (including the
    sabotage check) can monkeypatch attributes and have _selftest observe
    the patched object rather than a freshly re-executed module.
    """
    cached = sys.modules.get("wayai_mod")
    if cached is not None:
        return cached
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location("wayai_mod", os.path.join(here, "wayai.py"))
    assert spec is not None and spec.loader is not None, "cannot locate wayai.py"
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wayai_mod"] = mod
    spec.loader.exec_module(mod)
    return mod


def _selftest() -> int:
    checks: List[tuple[str, bool]] = []
    w = _load()

    # ------------------------------------------------- filter_urls
    urls = [
        "https://a.test/index.html",
        "https://a.test/app.js",
        "https://a.test/style.css",
        "https://a.test/api?x=1",
        "https://a.test/no-ext",
    ]

    checks.append(("filter no args keeps all", w.filter_urls(urls) == urls))
    checks.append(("filter exts keeps match", w.filter_urls(urls, exts=["js"]) == ["https://a.test/app.js"]))
    checks.append(("filter exts multiple", w.filter_urls(urls, exts=["js", "css"]) ==
                   ["https://a.test/app.js", "https://a.test/style.css"]))
    checks.append(("filter exts empty list keeps all", w.filter_urls(urls, exts=[]) == urls))
    checks.append(("filter with_params keeps query only", w.filter_urls(urls, with_params=True) == ["https://a.test/api?x=1"]))
    checks.append(("filter exts + with_params and", w.filter_urls(urls, exts=["api"], with_params=True) == ["https://a.test/api?x=1"]))
    checks.append(("filter case-insensitive ext", w.filter_urls(["https://a.test/A.JS"], exts=["js"]) == ["https://a.test/A.JS"]))
    checks.append(("filter matches ext before query", w.filter_urls(["https://a.test/x.php?y=1"], exts=["php"]) == ["https://a.test/x.php?y=1"]))
    checks.append(("filter empty input", w.filter_urls([], exts=["js"]) == []))
    checks.append(("filter does not mutate input", urls == [
        "https://a.test/index.html", "https://a.test/app.js", "https://a.test/style.css",
        "https://a.test/api?x=1", "https://a.test/no-ext"]))

    # ------------------------------------------------- extract_subdomains
    us = [
        "https://www.a.test/x",
        "https://api.a.test/y",
        "https://deep.api.a.test/z",
        "https://a.test/root",
        "https://nota.test/evil",
        "https://x.com/a",
    ]
    subs = w.extract_subdomains(us, "a.test")
    checks.append(("subdomains found", "www.a.test" in subs and "api.a.test" in subs))
    checks.append(("subdomains deep match present", "deep.api.a.test" in subs))
    checks.append(("subdomains excludes bare root host", "a.test" not in subs))
    checks.append(("subdomains excludes suffix attack", "nota.test" not in subs))
    checks.append(("subdomains excludes unrelated host", "x.com" not in subs))
    checks.append(("subdomains sorted", subs == sorted(subs)))
    checks.append(("subdomains deduped", len(subs) == len(set(subs))))
    checks.append(("subdomains lowercase", all(s == s.lower() for s in subs)))
    checks.append(("subdomains empty input", w.extract_subdomains([], "a.test") == []))
    checks.append(("subdomains no match", w.extract_subdomains(["https://other.test/a"], "a.test") == []))
    checks.append(("subdomains regex-safe root", w.extract_subdomains(["https://www.a-test.test/u"], "a-test.test") == ["www.a-test.test"]))

    # ------------------------------------------------- waybackurls shape (stubbed)
    # Verify the row-slicing contract: rows[0] is the CDX header, so it must be
    # dropped and column 2 taken as the URL.
    class _Resp:
        def __init__(self, payload):
            self._p = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._p

    orig_get = w.requests.get
    try:
        w.requests.get = lambda *a, **kw: _Resp([
            ["urlkey", "timestamp", "original"],
            ["com,a)/", "20200101000000", "https://a.test/x"],
            ["com,a)/b", "20200102000000", "https://a.test/y"],
        ])
        got = w.waybackurls("a.test")
        checks.append(("waybackurls drops header row", got == ["https://a.test/x", "https://a.test/y"]))

        w.requests.get = lambda *a, **kw: _Resp([])
        checks.append(("waybackurls empty payload", w.waybackurls("a.test") == []))

        def _boom(*a, **kw):
            raise RuntimeError("network down")
        w.requests.get = _boom
        checks.append(("waybackurls swallows errors", w.waybackurls("a.test") == []))
    finally:
        w.requests.get = orig_get

    # ------------------------------------------------- check_url shape (stubbed)
    class _Head:
        status_code = 200
        headers = {"Content-Length": "42"}

    try:
        w.requests.head = lambda *a, **kw: _Head()
        checks.append(("check_url ok tuple", w.check_url("https://a.test/x") == ("https://a.test/x", 200, "42")))

        class _NoLen:
            status_code = 403
            headers = {}
        w.requests.head = lambda *a, **kw: _NoLen()
        checks.append(("check_url missing length dash", w.check_url("https://a.test/x") == ("https://a.test/x", 403, "-")))

        def _boom(*a, **kw):
            raise RuntimeError("boom")
        w.requests.head = _boom
        checks.append(("check_url error tuple", w.check_url("https://a.test/x") == ("https://a.test/x", "ERR", "-")))
    finally:
        w.requests.head = orig_get.__class__ and __import__("requests").head

    # ------------------------------------------------- CLI parser contract
    checks.append(("main is callable", callable(w.main)))
    src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wayai.py")
    with open(src_path, encoding="utf-8") as fh:
        src = fh.read()
    for flag in ("--domain", "--from-date", "--to-date", "--exts", "--with-params",
                 "--include-commoncrawl", "--status", "--scan-subs", "--threads"):
        checks.append((f"cli flag {flag} declared", flag in src))
    checks.append(("cli --domain required", "\"--domain\", required=True" in src or "'--domain', required=True" in src))

    # ------------------------------------------------- report
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {name}")
    print(f"[+] wayai selftest: {len(checks) - len(failed)}/{len(checks)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
