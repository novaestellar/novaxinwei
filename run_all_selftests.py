#!/usr/bin/env python
"""Full-regression runner for every novaxinwei .py harness.

The individual selftests are in the repo; this is the sweep that proves they
still all pass TOGETHER after a refactor touched shared import machinery —
the failure mode a per-module run cannot see. It also runs the package from
the parent directory (layout B), which is how a Hermes skill install imports
it, so a change that only works in the repo is caught here.

Usage: python run_all_selftests.py [--parent <dir>]
Exit 0 only when every harness passes.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COUNT_RE = re.compile(r"(\d+)/(\d+) checks passed")


def discover() -> list[str]:
    """Module paths to run, as `python -m` targets relative to the parent."""
    mods = []
    for root, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git", "node_modules"}]
        rel = os.path.relpath(root, HERE).replace("\\", "/")
        prefix = "" if rel == "." else rel.replace("/", ".") + "."
        for f in sorted(files):
            if not f.endswith(".py"):
                continue
            stem = f[:-3]
            if f == "__main__.py":
                continue  # driven via -m <pkg>, covered by __main___selftest
            if stem == "__init__":
                # sidecars and package harnesses are run by filename separately
                continue
            if stem.endswith("_selftest") or stem == "selftest" or stem.startswith("test_"):
                # `<stem>_selftest.py` is itself a harness; `selftest.py` is the
                # directory-level one, added once per dir below.
                if stem != "selftest":
                    mods.append(prefix + stem)
            elif os.path.isfile(os.path.join(root, f"{stem}_selftest.py")):
                # Per-module sidecar, e.g. cli.py -> cli_selftest.py.
                mods.append(prefix + stem + "_selftest")
        # A directory-level selftest.py covers every module in that directory.
        if os.path.isfile(os.path.join(root, "selftest.py")):
            pkg_path = prefix.rstrip(".") if prefix else ""
            mods.append(f"{pkg_path}.selftest" if pkg_path else "selftest")
    return sorted(set(mods))


def run_one(mod_dotted: str, cwd_root: str, package: str) -> tuple[str, bool, str]:
    proc = subprocess.run(
        [sys.executable, "-m", f"{package}.{mod_dotted}"],
        capture_output=True, text=True, timeout=600, cwd=cwd_root,
    )
    out = proc.stdout + proc.stderr
    m = COUNT_RE.search(out)
    label = f"{m.group(1)}/{m.group(2)}" if m else f"rc={proc.returncode}"
    ok = proc.returncode == 0 and (not m or m.group(1) == m.group(2))
    return label, ok, out


def main() -> int:
    parent = os.path.dirname(HERE)
    package = os.path.basename(HERE)
    if "--parent" in sys.argv:
        parent = sys.argv[sys.argv.index("--parent") + 1]
        package = os.path.basename(HERE)

    targets = discover()
    print(f"package={package}  cwd={parent}  harnesses={len(targets)}")
    results = []
    for mod in targets:
        label, ok, out = run_one(mod, parent, package)
        status = "OK  " if ok else "FAIL"
        print(f"  [{status}] {mod:<52} {label}")
        if not ok:
            tail = "\n".join(l for l in out.splitlines() if "FAIL" in l)[:600]
            if tail:
                print("         " + tail.replace("\n", "\n         "))
        results.append({"module": mod, "checks": label, "ok": ok})

    failed = [r for r in results if not r["ok"]]
    print(f"\n{len(results) - len(failed)}/{len(results)} harnesses passed")
    if failed:
        print("FAILED: " + ", ".join(r["module"] for r in failed))
    print(json.dumps({"total": len(results), "failed": len(failed)}, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
