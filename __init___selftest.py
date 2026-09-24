"""Selftest for the root package __init__.py.

The root __init__.py holds only a docstring and __version__, which is exactly
why it went untested and exactly why it is worth a check: __version__ is the
one value the whole project reports as its identity, and it is read by tooling
(packagers, the release notes, this repo's own tracker) that will not notice a
value that is present but malformed.

Deliberately NOT asserted: the docstring's wording, or the capability list
inside it. Those are prose that legitimately changes; pinning them would make
this harness fail on documentation edits, which trains people to ignore it.
What is asserted is the machine-readable part of the contract: the version
exists, parses as dotted integers, and matches the version declared wherever
else the project states it (SKILL.md front matter, if present).

Run: python __init___selftest.py
"""
from __future__ import annotations

import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# Importable name depends on layout: repo dir may be named anything, a Hermes
# skill install is `novaxinwei`. Import by directory name so this works in both.
_PKG = os.path.basename(_HERE)


def _read_version_from_file(path: str) -> str | None:
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("__version__"):
                return line.split("=", 1)[1].strip().strip("\"'")
    return None


def _selftest() -> int:
    checks: list[tuple[str, bool]] = []

    src_path = os.path.join(_HERE, "__init__.py")
    checks.append(("__init__.py exists", os.path.isfile(src_path)))

    src = open(src_path, encoding="utf-8").read()
    checks.append(("module docstring present", src.lstrip().startswith('"""')))
    checks.append(("declares __version__", "__version__" in src))

    # The declared value, read statically — no import, so this cannot be fooled
    # by an import-time fallback that assigns a different value.
    declared = _read_version_from_file(src_path)
    checks.append(("__version__ has a literal value", bool(declared)))
    checks.append(("__version__ is a dotted integer version",
                   bool(declared) and bool(re.fullmatch(r"\d+(\.\d+)+", declared or ""))))

    # Read through a real import too, and require it to equal the literal: a
    # value that differs between source and import means something reassigns it.
    # Layout A (repo): this directory IS the package, so the git checkout root is
    #   the parent of a repo named differently on disk — import only works if the
    #   dir basename is importable, so fall back to loading __init__.py directly.
    # Layout B (skill install): parent is on sys.path and the dir basename is the
    #   package name, so the plain import works.
    mod = None
    sys.path.insert(0, os.path.dirname(_HERE))
    try:
        mod = __import__(_PKG)
    except ImportError:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_root_init_probe", src_path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
    finally:
        sys.path.pop(0)
    imported = getattr(mod, "__version__", None) if mod else None
    checks.append(("imported __version__ matches the literal", imported == declared))
    checks.append(("imported __version__ is a string", isinstance(imported, str)))

    # No side effects at import time: importing a package must not print, and
    # must not require network/credentials. A stray print here corrupts any
    # consumer that parses this package's output.
    import io
    import contextlib
    buf_out, buf_err = io.StringIO(), io.StringIO()
    saved = sys.modules.pop(_PKG, None)
    try:
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            sys.path.insert(0, os.path.dirname(_HERE))
            try:
                __import__(_PKG)
            except ImportError:
                import importlib.util
                spec = importlib.util.spec_from_file_location("_root_init_probe2", src_path)
                if spec and spec.loader:
                    m2 = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(m2)
            finally:
                sys.path.pop(0)
    finally:
        if saved is not None:
            sys.modules[_PKG] = saved
    checks.append(("import is silent on stdout", buf_out.getvalue() == ""))
    checks.append(("import is silent on stderr", buf_err.getvalue() == ""))

    # Cross-check against SKILL.md front matter when the file is present. Kept
    # conditional: this package is also deployed as a skill where SKILL.md
    # carries its own version field, and a mismatch there is a real drift bug.
    skill = os.path.join(_HERE, "SKILL.md")
    if os.path.isfile(skill):
        with open(skill, encoding="utf-8") as fh:
            head = fh.read(2000)
        m = re.search(r"^version:\s*[\"']?([0-9][0-9.]*)[\"']?\s*$", head, re.M)
        if m:
            checks.append((f"SKILL.md version matches __init__ ({m.group(1)})",
                           m.group(1) == declared))

    failed = sum(1 for _n, ok in checks if not ok)
    for name, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {name}")
    total = len(checks)
    print(f"[{'+' if not failed else '-'}] __init__: {total - failed}/{total} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_selftest())
