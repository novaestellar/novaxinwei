#!/usr/bin/env python
"""Run every in-file `_selftest()` in engine/ as a module.

Separate from run_all_selftests.py because these are a different convention:
`python -m engine.<mod>` where the module itself carries a `_selftest()` guarded
by __main__, versus a sidecar or directory harness file. Both conventions are
real, and a change to shared import machinery can break one without the other,
so both sweeps exist.

Usage: python run_engine_selftests.py
Exit 0 only when every module passes.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "engine")
COUNT_RE = re.compile(r"(\d+)/(\d+) checks passed")


def discover() -> list[str]:
    mods = []
    for f in sorted(os.listdir(ENGINE)):
        if not f.endswith(".py") or f == "__init__.py":
            continue
        stem = f[:-3]
        if stem.endswith("selftest") or stem.endswith("_selftest") or stem.startswith("test_"):
            continue
        with open(os.path.join(ENGINE, f), encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
        if "def _selftest(" in text and '__name__ == "__main__"' in text:
            mods.append(stem)
    return mods


def main() -> int:
    parent = os.path.dirname(HERE)
    package = os.path.basename(HERE)
    targets = discover()
    print(f"in-file _selftest modules in engine/: {len(targets)}")
    failed = []
    for mod in targets:
        proc = subprocess.run(
            [sys.executable, "-m", f"{package}.engine.{mod}"],
            capture_output=True, text=True, timeout=900, cwd=parent,
        )
        out = proc.stdout + proc.stderr
        m = COUNT_RE.search(out)
        label = f"{m.group(1)}/{m.group(2)}" if m else f"rc={proc.returncode}"
        ok = proc.returncode == 0
        print(f"  [{'OK  ' if ok else 'FAIL'}] engine.{mod:<28} {label}")
        if not ok:
            failed.append(mod)
            print("         " + "\n         ".join(
                l for l in out.splitlines() if "FAIL" in l)[:400])
    print(f"\n{len(targets) - len(failed)}/{len(targets)} engine modules passed")
    if failed:
        print("FAILED: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
