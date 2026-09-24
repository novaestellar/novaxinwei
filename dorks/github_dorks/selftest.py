# -*- coding: utf-8 -*-
"""github_dorks selftest — dork-file parsing, discovery, CSV output, CLI.

No network egress: `gh.search_code` is never reached. The functions that do
call it are exercised only through a stub client.

Run:  python -m dorks.github_dorks  (its own __main__)  or  python -m dorks
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
from typing import List


def _selftest() -> int:
    """Return 0 when all checks pass, 1 otherwise."""
    checks: List[tuple[str, bool]] = []

    def _raises(exc, fn) -> bool:
        try:
            fn()
            return False
        except exc:
            return True

    # This module is inside dorks/github_dorks/, so make both the package dir
    # and its parent importable regardless of invocation style.
    _here = os.path.dirname(os.path.abspath(__file__))
    _parent = os.path.dirname(os.path.dirname(_here))
    for p in (_parent, os.path.dirname(_here)):
        if p not in sys.path:
            sys.path.insert(0, p)

    import github_dorks
    import github_dorks.cli as C

    # ------------------------------------------------------------ packaging
    checks.append(("__version__ is set", bool(github_dorks.__version__)))
    checks.append(("__version__ is a string", isinstance(github_dorks.__version__, str)))
    checks.append(("cli imports __version__ from package",
                   C.__version__ == github_dorks.__version__ if hasattr(C, "__version__") else True))
    checks.append(("cli module imports cleanly", C is not None))
    checks.append(("main is callable", callable(C.main)))
    checks.append(("search is callable", callable(C.search)))
    checks.append(("metasearch is callable", callable(C.metasearch)))
    checks.append(("monit is callable", callable(C.monit)))
    checks.append(("search_wrapper is callable", callable(C.search_wrapper)))

    # ---------------------------------------------------- dorks file shipped
    pkg_dir = os.path.dirname(_here)          # dorks/
    dorks_txt = os.path.join(pkg_dir, "github-dorks.txt")
    checks.append(("github-dorks.txt ships with package", os.path.isfile(dorks_txt)))

    lines = []
    if os.path.isfile(dorks_txt):
        with open(dorks_txt, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    active = [l for l in lines if l.strip() and l.strip()[0] not in "#;"]
    checks.append(("dorks file has many active entries", len(active) > 50))
    checks.append(("dorks file has no NUL", "\x00" not in "\n".join(lines)))

    # ------------------------------------------------- file discovery (BUG-24)
    # Discovery must succeed with gh_dorks_file=None from any CWD, because the
    # package-relative candidate is checked. We assert on the resolved path by
    # calling search() with a stubbed client and capturing what it opened.
    opened_paths: List[str] = []

    class _FakeGH:
        class exceptions:
            class ForbiddenError(Exception): pass
            class GitHubError(Exception): pass

        def search_code(self, dork):
            return iter(())

        def rate_limit(self):
            return {"resources": {"search": {"remaining": 0, "reset": 0}}}

    real_open = io.open

    def _spy_open(path, *a, **kw):
        opened_paths.append(str(path))
        return real_open(path, *a, **kw)

    orig_gh = C.gh
    orig_stdout = sys.stdout
    cwd = os.getcwd()
    try:
        C.gh = _FakeGH()
        import builtins
        orig_builtin_open = builtins.open
        builtins.open = _spy_open
        try:
            for probe_cwd in (pkg_dir, os.path.dirname(pkg_dir)):
                opened_paths.clear()
                os.chdir(probe_cwd)
                sys.stdout = io.StringIO()
                C.search(repo_to_search="a/b")
                sys.stdout = orig_stdout
                hit = any(os.path.basename(p) == "github-dorks.txt" for p in opened_paths)
                checks.append((f"discovers dorks file from {os.path.basename(probe_cwd) or probe_cwd}", hit))
        finally:
            builtins.open = orig_builtin_open
            os.chdir(cwd)
            sys.stdout = orig_stdout
    finally:
        C.gh = orig_gh

    # ------------------------------------------- explicit bad path still raises
    checks.append(("invalid dork path raises", _raises(Exception, lambda: C.search(
        repo_to_search="a/b", gh_dorks_file="definitely-missing-dorks-file.txt"))))

    # ------------------------------------------- comment/blank lines are skipped
    # A dorks file of only comments and blanks must produce zero search calls.
    calls: List[str] = []
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        fh.write("# a comment\n; another comment\n\n   \n")
        comment_only = fh.name

    class _CountingGH(_FakeGH):
        def search_code(self, dork):
            calls.append(dork)
            return iter(())

    try:
        C.gh = _CountingGH()
        sys.stdout = io.StringIO()
        C.search(repo_to_search="a/b", gh_dorks_file=comment_only)
        sys.stdout = orig_stdout
        checks.append(("comment-only dorks file searches nothing", calls == []))
    finally:
        C.gh = orig_gh
        sys.stdout = orig_stdout
        os.unlink(comment_only)

    # ------------------------------------------- repo vs user qualifier added
    calls.clear()

    class _RecordingGH(_FakeGH):
        def search_code(self, dork):
            calls.append(dork)
            return iter(())

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        fh.write("filename:.npmrc _auth\n")
        one_dork = fh.name

    try:
        C.gh = _RecordingGH()
        sys.stdout = io.StringIO()
        C.search(repo_to_search="org/repo", gh_dorks_file=one_dork)
        sys.stdout = orig_stdout
        checks.append(("repo qualifier appended", calls and calls[0].endswith("repo:org/repo")))
        calls.clear()
        C.gh = _RecordingGH()
        sys.stdout = io.StringIO()
        C.search(user_to_search="someuser", gh_dorks_file=one_dork)
        sys.stdout = orig_stdout
        checks.append(("user qualifier appended", calls and calls[0].endswith("user:someuser")))
    finally:
        C.gh = orig_gh
        sys.stdout = orig_stdout
        os.unlink(one_dork)

    # ------------------------------------------- CSV writer writes a header
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as fh:
        csv_path = fh.name

    class _HitGH(_FakeGH):
        class _Hit:
            text_matches = "m"
            path = "p"
            score = 1.0
            html_url = "https://github.com/x/y/blob/1/p"

        def search_code(self, dork):
            return iter((self._Hit(),))

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        fh.write("filename:.npmrc _auth\n")
        hit_dork = fh.name

    try:
        C.gh = _HitGH()
        sys.stdout = io.StringIO()
        C.search(repo_to_search="a/b", gh_dorks_file=hit_dork, output_filename=csv_path)
        sys.stdout = orig_stdout
        # file was opened 'w' then written by the same handle; stdout stays empty
        captured = sys.stdout if False else None
        checks.append(("csv output path exists", os.path.isfile(csv_path)))
        # the header is written on the first pass; we re-read via a second call
        # using an explicit buffer instead of the file to assert the row shape.
    finally:
        C.gh = orig_gh
        sys.stdout = orig_stdout

    # CSV rows are written through the same open handle, so to inspect them we
    # run search once more against an in-memory file object.
    class _MemFile:
        def __init__(self):
            self.buf = io.StringIO()

        def write(self, s):
            self.buf.write(s)

    try:
        C.gh = _HitGH()
        mem = _MemFile()
        # swap the context manager: search() only needs .write()
        import contextlib as _ctx
        calls2: List[str] = []

        real_nullcontext = _ctx.nullcontext

        def fake_nullcontext(_):
            return _ctx.nullcontext(mem)

        # Easier: call search with output_filename pointing at a real temp file,
        # then read the file back.
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as fh:
            csv2 = fh.name
        sys.stdout = io.StringIO()
        C.search(repo_to_search="a/b", gh_dorks_file=hit_dork, output_filename=csv2)
        sys.stdout = orig_stdout
        with real_open(csv2, encoding="utf-8") as fh:
            body = fh.read()
        checks.append(("csv header written", "Issue Type (Dork)" in body))
        checks.append(("csv contains dork text", "filename:.npmrc _auth" in body))
        checks.append(("csv contains hit url", "https://github.com/x/y/blob/1/p" in body))
        checks.append(("csv has 2 rows", len([l for l in body.splitlines() if l.strip()]) == 2))
        os.unlink(csv2)
    finally:
        C.gh = orig_gh
        sys.stdout = orig_stdout
        os.unlink(hit_dork)
        os.unlink(csv_path)

    # ------------------------------------------- CLI argument wiring
    import argparse
    # main() parses sys.argv; verify the parser contract without running search
    argv_backup = sys.argv
    parsed: List[dict] = []
    orig_metasearch = C.metasearch
    try:
        C.metasearch = lambda **kw: parsed.append(kw)
        sys.argv = ["github-dorks", "-r", "org/repo", "-d", "somefile.txt", "-o", "out.csv"]
        C.main()
        checks.append(("cli repo flag wired", parsed and parsed[0].get("repo_to_search") == "org/repo"))
        checks.append(("cli dork flag wired", parsed and parsed[0].get("gh_dorks_file") == "somefile.txt"))
        checks.append(("cli output flag wired", parsed and parsed[0].get("output_filename") == "out.csv"))

        parsed.clear()
        sys.argv = ["github-dorks", "-u", "someone", "-d", "somefile.txt"]
        C.main()
        checks.append(("cli user flag wired", parsed and parsed[0].get("user_to_search") == "someone"))

        parsed.clear()
        sys.argv = ["github-dorks", "-m", "TOKEN", "-d", "somefile.txt"]
        C.main()
        checks.append(("cli monit flag wired", parsed and parsed[0].get("active_monit") == "TOKEN"))

        # mutually exclusive group: -r and -u together must be rejected
        sys.argv = ["github-dorks", "-r", "a/b", "-u", "c", "-d", "somefile.txt"]
        stderr_backup = sys.stderr
        sys.stderr = io.StringIO()
        rejected = _raises(SystemExit, C.main)
        sys.stderr = stderr_backup
        checks.append(("cli rejects -r with -u", rejected))

        # -d is required in practice (no default), and one of -r/-u/-m is required
        sys.argv = ["github-dorks", "-d", "somefile.txt"]
        sys.stderr = io.StringIO()
        rejected = _raises(SystemExit, C.main)
        sys.stderr = stderr_backup
        checks.append(("cli requires one of -r/-u/-m", rejected))
    finally:
        C.metasearch = orig_metasearch
        sys.argv = argv_backup

    # ------------------------------------------- metasearch dispatch
    dispatched: List[str] = []
    orig_search = C.search
    orig_monit = C.monit
    try:
        C.search = lambda *a, **kw: dispatched.append("search")
        C.monit = lambda *a, **kw: dispatched.append("monit")
        C.metasearch(repo_to_search="a/b", gh_dorks_file="f.txt")
        checks.append(("metasearch routes to search", dispatched == ["search"]))
        dispatched.clear()
        C.metasearch(active_monit="TOK", gh_dorks_file="f.txt")
        checks.append(("metasearch routes to monit", dispatched == ["monit"]))
    finally:
        C.search = orig_search
        C.monit = orig_monit

    # ------------------------------------------- report
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {name}")
    print(f"[+] github_dorks selftest: {len(checks) - len(failed)}/{len(checks)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
