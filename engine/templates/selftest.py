"""Contract selftest for the two Python browser templates.

These templates are stdin/stdout subprocess programs — executor._run_python_template
runs `sys.executable <template>` with `input=json.dumps(args)` and reads stdout as
HTML. That contract is testable without Chrome and without nodriver/patchright
installed: stub the driver module in sys.modules, feed stdin, assert stdout/exit.

What is NOT covered: whether a real Chrome actually clears a real Cloudflare
challenge. That needs the drivers plus a live gate and is not a unit test.

Run: python -m engine.templates.nodriver_fetch --selftest
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import types


def _check_nodriver() -> list[tuple[str, bool]]:
    """Fake nodriver drives the template's real main() through stdin/stdout."""
    checks: list[tuple[str, bool]] = []
    calls: dict = {}

    class FakeTab:
        async def sleep(self, _s):
            calls["slept"] = True

        async def select(self, sel, timeout=None):
            calls["select"] = (sel, timeout)
            if sel == "#never":
                raise RuntimeError("selector timeout")

        async def get_content(self):
            return "<html>NODRIVER-OK</html>"

    class FakeBrowser:
        async def get(self, url):
            calls["url"] = url
            return FakeTab()

        def stop(self):
            calls["stopped"] = True

    fake = types.ModuleType("nodriver")

    async def start(headless=False, **kw):
        calls["headless"] = headless
        return FakeBrowser()

    fake.start = start

    here = os.path.dirname(os.path.abspath(__file__))
    src = open(os.path.join(here, "nodriver_fetch.py"), encoding="utf-8").read()

    def run(args: dict):
        """Execute the template source with the fake driver installed."""
        saved = sys.modules.get("nodriver")
        sys.modules["nodriver"] = fake
        stdin_saved = sys.stdin
        out, err = [], []
        try:
            sys.stdin = types.SimpleNamespace(read=lambda: json.dumps(args))
            import io
            stdout_saved, stderr_saved = sys.stdout, sys.stderr
            sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
            try:
                ns = {"__name__": "__main__"}
                try:
                    exec(compile(src, "nodriver_fetch.py", "exec"), ns)
                    rc = 0
                except SystemExit as e:
                    rc = e.code or 0
                except Exception as e:  # pragma: no cover - reported as a check
                    rc = 1
                    err.append(f"{type(e).__name__}: {e}")
                out.append(sys.stdout.getvalue())
                err.append(sys.stderr.getvalue())
            finally:
                sys.stdout, sys.stderr = stdout_saved, stderr_saved
        finally:
            sys.stdin = stdin_saved
            if saved is not None:
                sys.modules["nodriver"] = saved
            else:
                sys.modules.pop("nodriver", None)
        return rc, out[0], err[0]

    rc, out, _err = run({"url": "https://x.test/a", "timeout": 5000})
    checks.append(("exit 0 on success", rc == 0))
    checks.append(("stdout is the page HTML", out == "<html>NODRIVER-OK</html>"))
    checks.append(("url passed through to browser.get", calls.get("url") == "https://x.test/a"))

    calls.clear()
    rc, out, _err = run({"url": "https://x.test/a", "timeout": 5000, "headless": True})
    checks.append(("headless flag honoured", calls.get("headless") is True))

    calls.clear()
    rc, out, _err = run({"url": "https://x.test/a", "timeout": 5000})
    checks.append(("headless defaults to False (headful)", calls.get("headless") is False))

    rc, out, _err = run({"url": "https://x.test/a", "timeout": 5000, "waitSelector": "#x"})
    checks.append(("waitSelector is selected", calls.get("select", (None,))[0] == "#x"))

    # A failing waitSelector is best-effort: stderr note, but content still ships.
    rc, out, err = run({"url": "https://x.test/a", "timeout": 5000, "waitSelector": "#never"})
    checks.append(("best-effort waitSelector still exits 0", rc == 0))
    checks.append(("best-effort waitSelector still returns content", "NODRIVER-OK" in out))
    checks.append(("best-effort waitSelector notes stderr", "waitSelector failed" in err))

    checks.append(("browser.stop() called (no leaked Chrome)",
                   calls.get("stopped") is True))

    # Missing driver: the entry block must turn it into exit 1 + stderr naming
    # the failure, because executor._run_python_template reads the return code.
    # Blocked deterministically with a sitecustomize-free import hook so the
    # check means the same thing whether or not nodriver is installed locally.
    hook = (
        "import sys\n"
        "class _Block:\n"
        "    def find_module(self, name, path=None):\n"
        "        return None\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name == 'nodriver' or name.startswith('nodriver.'):\n"
        "            raise ImportError('nodriver blocked by selftest')\n"
        "        return None\n"
        "sys.meta_path.insert(0, _Block())\n"
    )
    env = dict(os.environ, PYTHONSTARTUP="")
    blocked_src = open(os.path.join(here, "nodriver_fetch.py"), encoding="utf-8").read()
    # Force __main__ semantics under -c, where __name__ is already "__main__".
    proc = subprocess.run(
        [sys.executable, "-c", hook + blocked_src.replace('if __name__ == "__main__":', "if True:")],
        input=json.dumps({"url": "https://x.test/a"}),
        capture_output=True, text=True, timeout=60, cwd=here, env=env,
    )
    checks.append(("blocked driver exits 1", proc.returncode == 1))
    checks.append(("blocked driver reports ImportError",
                   "ImportError" in proc.stderr or "ModuleNotFoundError" in proc.stderr))
    checks.append(("blocked driver keeps stdout clean", proc.stdout == ""))

    # Malformed stdin must exit 1, not hang or print a traceback as content.
    proc = subprocess.run(
        [sys.executable, os.path.join(here, "nodriver_fetch.py")],
        input="not json", capture_output=True, text=True, timeout=60, cwd=here,
    )
    checks.append(("malformed stdin exits 1", proc.returncode == 1))
    checks.append(("malformed stdin keeps stdout clean", proc.stdout == ""))

    return checks


def _check_patchright() -> list[tuple[str, bool]]:
    checks: list[tuple[str, bool]] = []
    here = os.path.dirname(os.path.abspath(__file__))
    src = open(os.path.join(here, "patchright_fetch.py"), encoding="utf-8").read()

    # Patchright is a sync API; a stub on sys.modules exercises main() directly
    # without launching Chrome.
    calls: dict = {}

    class FakePage:
        def goto(self, url, timeout=None, wait_until=None):
            calls["url"] = url
            calls["timeout"] = timeout
            calls["wait_until"] = wait_until

        def wait_for_timeout(self, ms):
            calls["waited"] = ms

        def wait_for_selector(self, sel, timeout=None):
            calls["select"] = (sel, timeout)
            if sel == "#never":
                raise RuntimeError("selector timeout")

        def content(self):
            return "<html>PATCHRIGHT-OK</html>"

    class FakeBrowser:
        def new_page(self):
            return FakePage()

        def close(self):
            calls["closed"] = True

    class FakeChromium:
        def launch(self, channel=None, headless=None):
            calls["channel"] = channel
            calls["headless"] = headless
            return FakeBrowser()

    class FakeP:
        chromium = FakeChromium()

    class FakeCtx:
        def __enter__(self):
            return FakeP()

        def __exit__(self, *a):
            return False

    pr = types.ModuleType("patchright")
    sync_mod = types.ModuleType("patchright.sync_api")
    sync_mod.sync_playwright = lambda: FakeCtx()
    pr.sync_api = sync_mod

    def run(args: dict):
        import io
        saved = {k: sys.modules.get(k) for k in ("patchright", "patchright.sync_api")}
        sys.modules["patchright"] = pr
        sys.modules["patchright.sync_api"] = sync_mod
        stdin_saved = sys.stdin
        out = io.StringIO()
        err = io.StringIO()
        stdout_saved, stderr_saved = sys.stdout, sys.stderr
        try:
            sys.stdin = types.SimpleNamespace(read=lambda: json.dumps(args))
            sys.stdout, sys.stderr = out, err
            ns = {"__name__": "__main__"}
            try:
                exec(compile(src, "patchright_fetch.py", "exec"), ns)
                rc = 0
            except SystemExit as e:
                rc = e.code or 0
            except Exception:
                rc = 1
        finally:
            sys.stdin = stdin_saved
            sys.stdout, sys.stderr = stdout_saved, stderr_saved
            for k, v in saved.items():
                if v is not None:
                    sys.modules[k] = v
                else:
                    sys.modules.pop(k, None)
        return rc, out.getvalue(), err.getvalue()

    rc, out, _err = run({"url": "https://x.test/b", "timeout": 3000})
    checks.append(("exit 0 on success", rc == 0))
    checks.append(("stdout is the page HTML", out == "<html>PATCHRIGHT-OK</html>"))
    checks.append(("uses system Chrome, not bundled Chromium",
                   calls.get("channel") == "chrome"))
    checks.append(("headless defaults to False (headful)", calls.get("headless") is False))
    checks.append(("timeout forwarded to goto as ms", calls.get("timeout") == 3000))
    checks.append(("waits domcontentloaded, not networkidle",
                   calls.get("wait_until") == "domcontentloaded"))

    calls.clear()
    rc, out, _err = run({"url": "https://x.test/b", "timeout": 3000, "headless": True})
    checks.append(("headless flag honoured", calls.get("headless") is True))

    rc, _out, _err = run({"url": "https://x.test/b", "timeout": 3000, "waitSelector": "#never"})
    checks.append(("best-effort waitSelector still exits 0", rc == 0))
    checks.append(("best-effort waitSelector notes stderr",
                   "waitSelector failed" in _err))

    checks.append(("browser.close() called (no leaked Chrome)",
                   calls.get("closed") is True))

    # No `timeout` key: the template declares 60000 as its default.
    calls.clear()
    rc, _out, _err = run({"url": "https://x.test/b"})
    checks.append(("default timeout 60000 ms", calls.get("timeout") == 60000))
    checks.append(("missing timeout still exits 0", rc == 0))

    proc = subprocess.run(
        [sys.executable, os.path.join(here, "patchright_fetch.py")],
        input="not json", capture_output=True, text=True, timeout=60, cwd=here,
    )
    checks.append(("malformed stdin exits 1", proc.returncode == 1))
    checks.append(("malformed stdin keeps stdout clean", proc.stdout == ""))

    return checks


def _check_parity() -> list[tuple[str, bool]]:
    """Both templates must honour the same stdin contract."""
    checks: list[tuple[str, bool]] = []
    here = os.path.dirname(os.path.abspath(__file__))
    for name in ("nodriver_fetch.py", "patchright_fetch.py"):
        src = open(os.path.join(here, name), encoding="utf-8").read()
        checks.append((f"{name} reads stdin as JSON", "json.load(sys.stdin)" in src))
        checks.append((f"{name} writes HTML to stdout", "sys.stdout.write(" in src))
        checks.append((f"{name} returns 0 on success", "return 0" in src))
        checks.append((f"{name} has an exit-1 handler", "sys.exit(1)" in src))
        checks.append((f"{name} accepts url/timeout/headless/waitSelector",
                       all(k in src for k in ('args["url"]', '"timeout"', "headless", "waitSelector"))))
    return checks


def _selftest() -> int:
    checks = _check_nodriver() + _check_patchright() + _check_parity()
    failed = 0
    for name, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {name}")
        if not ok:
            failed += 1
    total = len(checks)
    print(f"[{'+' if not failed else '-'}] engine.templates: {total - failed}/{total} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_selftest())
