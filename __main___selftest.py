"""Selftest for __main__.py, the CLI entry shim.

__main__.py is 34 lines but it is the module `python -m novaxinwei` and
`python __main__.py` both land on, and it carries a two-branch import fallback
(`from .cli` for the package case, an importlib lookup by directory name for
direct execution). Nothing tested it, so a broken fallback would only show as
"the CLI does not start" in whichever layout the author did not try.

Both layouts are exercised for real, in subprocesses, because the whole point
of the shim is how it resolves imports under different interpreters-of-entry:

    layout A (repo)    cd <pkg-dir> && python __main__.py check
    layout B (install) cd <parent>  && python -m novaxinwei check

Assertions are on exit codes and the shape of stdout — not on live network
results — so the test does not depend on any channel being reachable. `check`
is the command used because it prints one line per channel and needs no
network argument.

Run: python __main___selftest.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)


def _run(args, cwd, timeout=180):
    proc = subprocess.run(args, capture_output=True, text=True,
                          timeout=timeout, cwd=cwd)
    return proc.returncode, proc.stdout, proc.stderr


def _selftest() -> int:
    checks: list[tuple[str, bool]] = []

    checks.append(("__main__.py exists", os.path.isfile(os.path.join(_HERE, "__main__.py"))))

    src = open(os.path.join(_HERE, "__main__.py"), encoding="utf-8").read()
    checks.append(("delegates to cli.main", "main" in src))
    checks.append(("has both entry forms", "_parent" in src and "_here" in src))
    checks.append(("exits with cli's return code", "sys.exit(main())" in src))

    pkg_name = os.path.basename(_HERE)

    # ---- layout A: run the file directly from inside the package directory.
    rc, out, err = _run([sys.executable, "__main__.py", "check"], _HERE)
    checks.append(("layout A: exit 0 on `check`", rc == 0))
    checks.append(("layout A: prints channel lines", bool(re.search(r"^✓ ", out, re.M))))
    checks.append(("layout A: no traceback on stderr", "Traceback" not in err))

    # ---- layout B: run as a package module from the parent directory.
    rc_b, out_b, err_b = _run([sys.executable, "-m", pkg_name, "check"], _PARENT)
    checks.append((f"layout B: exit 0 on `-m {pkg_name} check`", rc_b == 0))
    checks.append(("layout B: prints channel lines", bool(re.search(r"^✓ ", out_b, re.M))))
    checks.append(("layout B: no traceback on stderr", "Traceback" not in err_b))

    # Both layouts must produce the same channel set, not merely both "work".
    def channels(text):
        return sorted(re.findall(r"^✓ (\S+)", text, re.M))

    checks.append(("both layouts list the same channels", channels(out) == channels(out_b)))
    checks.append(("channel list is non-empty", len(channels(out)) > 0))

    # ---- argument handling: argparse must reject an unknown command with 2.
    rc, out, err = _run([sys.executable, "__main__.py", "definitely-not-a-command"], _HERE)
    checks.append(("bad command exits 2 (argparse)", rc == 2))
    checks.append(("bad command explains itself", "invalid choice" in err))

    # ---- no args: the parser prints usage and must NOT look like a crash.
    rc, out, err = _run([sys.executable, "__main__.py"], _HERE)
    checks.append(("no args does not traceback", "Traceback" not in err))
    checks.append(("no args prints usage", "usage" in (out + err).lower()))

    # ---- the five documented subcommands are all reachable from the shim.
    for cmd in ("fetch", "fetch-parallel", "dorks", "check", "chain"):
        rc, out, err = _run([sys.executable, "__main__.py", cmd, "--help"], _HERE, timeout=120)
        checks.append((f"`{cmd} --help` exits 0", rc == 0))

    failed = sum(1 for _n, ok in checks if not ok)
    for name, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {name}")
    total = len(checks)
    print(f"[{'+' if not failed else '-'}] __main__: {total - failed}/{total} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_selftest())
