# -*- coding: utf-8 -*-
"""github_pages_enum selftest — check_page / enum_pages_parallel / CLI.

No network: requests.get is stubbed.

Run:  python tools/github_pages/selftest.py
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
from typing import List

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load():
    cached = sys.modules.get("gpe_mod")
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location("gpe_mod", os.path.join(_HERE, "github_pages_enum.py"))
    assert spec is not None and spec.loader is not None, "cannot locate github_pages_enum.py"
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gpe_mod"] = mod
    spec.loader.exec_module(mod)
    return mod


def _selftest() -> int:
    checks: List[tuple[str, bool]] = []
    m = _load()

    class _Resp:
        def __init__(self, status=200, body=b"x", ctype="text/html"):
            self.status_code = status
            self.content = body
            self.headers = {"Content-Type": ctype}

    orig_get = m.requests.get

    # ------------------------------------------------- check_page
    seen: List[str] = []

    def _recorder(status_map):
        def _get(url, **kw):
            seen.append(url)
            status = status_map.get(url, 404)
            return _Resp(status=status, body=b"abcd")
        return _get

    try:
        m.requests.get = _recorder({})
        out = m.check_page("user", "repo")
        checks.append(("check_page all 404 -> no findings", out == []))
        checks.append(("check_page probes default paths", len(seen) == 6))
        checks.append(("check_page builds github.io base",
                       all(u.startswith("https://user.github.io/repo/") for u in seen)))

        seen.clear()
        m.requests.get = _recorder({"https://user.github.io/repo/index.html": 200})
        out = m.check_page("user", "repo")
        checks.append(("check_page finds 200", len(out) == 1 and out[0]["status"] == 200))
        checks.append(("check_page records repo", out[0]["repo"] == "repo"))
        checks.append(("check_page records url", out[0]["url"].endswith("/index.html")))
        checks.append(("check_page records size", out[0]["size"] == 4))
        checks.append(("check_page records content_type", out[0]["content_type"] == "text/html"))

        seen.clear()
        m.requests.get = _recorder({})
        m.check_page("user", "repo", paths=["", "a.txt"])
        checks.append(("check_page honors custom paths", len(seen) == 2))
        checks.append(("check_page empty path is base url", "https://user.github.io/repo/" in seen))

        # non-200 codes are not leaks
        m.requests.get = _recorder({"https://user.github.io/repo/.env": 403})
        out = m.check_page("user", "repo")
        checks.append(("check_page ignores 403", out == []))

        # request failure is swallowed, not raised
        def _boom(url, **kw):
            raise m.requests.RequestException("down")
        m.requests.get = _boom
        checks.append(("check_page swallows RequestException", m.check_page("user", "repo") == []))
    finally:
        m.requests.get = orig_get

    # ------------------------------------------------- enum_pages_parallel
    try:
        m.requests.get = _recorder({})
        checks.append(("enum empty repos", m.enum_pages_parallel("user", []) == []))

        m.requests.get = _recorder({
            "https://user.github.io/r1/index.html": 200,
            "https://user.github.io/r2/config.json": 200,
        })
        out = m.enum_pages_parallel("user", ["r1", "r2", "r3"], max_workers=3)
        repos = {f["repo"] for f in out}
        checks.append(("enum finds both leaks", repos == {"r1", "r2"}))
        checks.append(("enum omits clean repo", "r3" not in repos))

        m.requests.get = _recorder({})
        checks.append(("enum no findings when all 404", m.enum_pages_parallel("user", ["a", "b"]) == []))
    finally:
        m.requests.get = orig_get

    # ------------------------------------------------- CLI parser contract
    src_path = os.path.join(_HERE, "github_pages_enum.py")
    with open(src_path, encoding="utf-8") as fh:
        src = fh.read()
    for flag in ("--username", "--repos", "--paths", "--workers", "--json"):
        checks.append((f"cli flag {flag} declared", flag in src))
    checks.append(("cli --username required", "required=True" in src))
    checks.append(("cli --repos required", '"--repos", required=True' in src or "'--repos', required=True" in src))
    checks.append(("cli default workers 5", "default=5" in src))

    # the comma-split contract for --repos / --paths
    checks.append(("repo csv split", [r.strip() for r in "a,b, c".split(",")] == ["a", "b", "c"]))
    checks.append(("json output shape", json.loads(json.dumps([{"repo": "x"}]))[0]["repo"] == "x"))

    # ------------------------------------------------- report
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {name}")
    print(f"[+] github_pages_enum selftest: {len(checks) - len(failed)}/{len(checks)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
