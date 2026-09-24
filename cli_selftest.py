# -*- coding: utf-8 -*-
"""NovaXinWei CLI selftest — parser contract and command dispatch.

No network and no engagement writes: every command handler's heavy
dependency (fetch_chain, channels, enrichment, engagement_output) is
monkeypatched, and the parser is exercised on its own first.

Run:  python cli.py --selftest   or   python -m cli.selftest (via this file)
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import os
import sys
from typing import List

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_cli():
    cached = sys.modules.get("nvx_cli_mod")
    if cached is not None:
        return cached
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)
    spec = importlib.util.spec_from_file_location("nvx_cli_mod", os.path.join(_HERE, "cli.py"))
    assert spec is not None and spec.loader is not None, "cannot locate cli.py"
    mod = importlib.util.module_from_spec(spec)
    sys.modules["nvx_cli_mod"] = mod
    spec.loader.exec_module(mod)
    return mod


def _selftest() -> int:
    checks: List[tuple[str, bool]] = []
    cli = _load_cli()

    def _raises(exc, fn) -> bool:
        try:
            fn()
            return False
        except exc:
            return True

    def _parse(argv):
        return cli.build_parser().parse_args(argv)

    # ------------------------------------------------- source hygiene (BUG-27)
    with open(os.path.join(_HERE, "cli.py"), encoding="utf-8") as fh:
        src = fh.read()
    # Imports must not hardcode either layout: `novaxinwei.engine.x` breaks in
    # the repo, `engine.x` breaks in a Hermes skill install. Both go through
    # cli._submodule, which tries engine.x then novaxinwei.engine.x. The
    # docstring narrates the old broken form, so match statements only.
    bad_imports = [ln.strip() for ln in src.splitlines()
                   if ln.strip().startswith(("from novaxinwei", "import novaxinwei"))]
    checks.append(("no novaxinwei.* import statements", bad_imports == []))
    checks.append(("imports engine.fetch_chain via _submodule",
                   "_submodule('engine.fetch_chain')" in src))
    checks.append(("imports channels.fetch_parallel via _submodule",
                   "_submodule('channels')" in src))
    checks.append(("no bare engine./channels. imports left",
                   not any(ln.strip().startswith(("from engine.", "from channels."))
                           for ln in src.splitlines())))

    # ------------------------------------------------- build_parser
    p = cli.build_parser()
    checks.append(("parser prog name", p.prog == "novaxinwei"))
    sub = [a for a in p._actions if isinstance(a, argparse._SubParsersAction)][0]
    cmds = set(sub.choices)
    for c in ("fetch", "fetch-parallel", "dorks", "check", "enrich", "engagement", "chain"):
        checks.append((f"command {c} exists", c in cmds))
    checks.append(("no stray commands", len(cmds) == 7))

    # ------------------------------------------------- fetch defaults
    a = _parse(["fetch", "https://a.test/"])
    checks.append(("fetch url positional", a.url == "https://a.test/"))
    checks.append(("fetch timeout default 25", a.timeout == 25))
    checks.append(("fetch device default auto", a.device == "auto"))
    checks.append(("fetch json default off", a.json is False))
    checks.append(("fetch trace default off", a.trace is False))
    checks.append(("fetch selectors default None", a.selectors is None))
    checks.append(("fetch playwright on by default", a.no_playwright is False))
    checks.append(("fetch phase0 on by default", a.no_phase0 is False))
    checks.append(("fetch save_engagement default None", a.save_engagement is None))
    checks.append(("fetch enrich default off", a.enrich is False))

    a = _parse(["fetch", "https://a.test/", "--timeout", "5", "--json", "--trace",
                "--device", "mobile", "-s", "div.x", "-s", "span.y",
                "--no-playwright", "--no-phase0", "--save-engagement", "t.test", "--enrich"])
    checks.append(("fetch timeout override", a.timeout == 5))
    checks.append(("fetch json on", a.json is True))
    checks.append(("fetch trace on", a.trace is True))
    checks.append(("fetch device override", a.device == "mobile"))
    checks.append(("fetch selectors append", a.selectors == ["div.x", "span.y"]))
    checks.append(("fetch no-playwright flips", a.no_playwright is True))
    checks.append(("fetch no-phase0 flips", a.no_phase0 is True))
    checks.append(("fetch save_engagement set", a.save_engagement == "t.test"))
    checks.append(("fetch enrich set", a.enrich is True))
    checks.append(("fetch url required",
                   _raises(SystemExit, lambda: _parse(["fetch"]))))
    checks.append(("fetch device rejects junk",
                   _raises(SystemExit, lambda: _parse(["fetch", "https://a.test/", "--device", "toaster"]))))

    # ------------------------------------------------- fetch-parallel
    a = _parse(["fetch-parallel", "https://a.test/1", "https://a.test/2"])
    checks.append(("fetch-parallel takes many", a.urls == ["https://a.test/1", "https://a.test/2"]))
    checks.append(("fetch-parallel workers default 5", a.workers == 5))
    checks.append(("fetch-parallel requires at least one",
                   _raises(SystemExit, lambda: _parse(["fetch-parallel"]))))

    # ------------------------------------------------- dorks subcommands
    a = _parse(["dorks", "shodan", "example.test"])
    checks.append(("dorks shodan target", a.target == "example.test"))
    checks.append(("dorks shodan dork_type", a.dork_type == "shodan"))
    a = _parse(["dorks", "github", "filename:.npmrc"])
    checks.append(("dorks github query", a.query == "filename:.npmrc"))
    checks.append(("dorks github dork_type", a.dork_type == "github"))

    # ------------------------------------------------- enrich
    a = _parse(["enrich", "example.test"])
    checks.append(("enrich level default basic", a.level == "basic"))
    a = _parse(["enrich", "example.test", "--level", "full", "--json"])
    checks.append(("enrich level override", a.level == "full"))
    checks.append(("enrich rejects bad level",
                   _raises(SystemExit, lambda: _parse(["enrich", "x.test", "--level", "extreme"]))))

    # ------------------------------------------------- engagement
    for act in ("create", "list", "summary"):
        a = _parse(["engagement", act])
        checks.append((f"engagement action {act}", a.action == act))
    checks.append(("engagement rejects bad action",
                   _raises(SystemExit, lambda: _parse(["engagement", "destroy"]))))
    checks.append(("engagement base-dir option", _parse(["engagement", "list", "--base-dir", "X:/e"]).base_dir == "X:/e"))

    # ------------------------------------------------- chain
    checks.append(("chain target required",
                   _raises(SystemExit, lambda: _parse(["chain"]))))
    checks.append(("chain target parsed", _parse(["chain", "--target", "t.test"]).target == "t.test"))

    # ------------------------------------------------- dispatch: cmd_fetch success
    class _Att:
        def to_dict(self):
            return {"phase": "grid", "executor": "curl_cffi", "status": 200, "verdict": "ok"}

    class _Result:
        ok = True
        trace = [_Att()]

        def to_dict(self):
            return {"ok": True, "url": "https://a.test/"}

        def to_untrusted_text(self):
            return "BODY-TEXT"

    import engine.fetch_chain as fc
    import engine.url_masking as um

    orig_fetch = fc.fetch
    out, err = io.StringIO(), io.StringIO()
    o_out, o_err = sys.stdout, sys.stderr
    try:
        fc.fetch = lambda *a_, **kw: _Result()
        sys.stdout, sys.stderr = out, err
        rc = cli.cmd_fetch(_parse(["fetch", "https://a.test/"]))
        sys.stdout, sys.stderr = o_out, o_err
        checks.append(("cmd_fetch ok returns 0", rc == 0))
        checks.append(("cmd_fetch prints text body", "BODY-TEXT" in out.getvalue()))

        out, err = io.StringIO(), io.StringIO()
        sys.stdout, sys.stderr = out, err
        rc = cli.cmd_fetch(_parse(["fetch", "https://a.test/", "--json"]))
        sys.stdout, sys.stderr = o_out, o_err
        checks.append(("cmd_fetch --json emits parsed json", '"ok": true' in out.getvalue()))

        out, err = io.StringIO(), io.StringIO()
        sys.stdout, sys.stderr = out, err
        rc = cli.cmd_fetch(_parse(["fetch", "https://a.test/", "--trace"]))
        sys.stdout, sys.stderr = o_out, o_err
        checks.append(("cmd_fetch --trace goes to stderr", "grid" in err.getvalue()))
        checks.append(("cmd_fetch --trace keeps stdout clean", "grid" not in out.getvalue()))

        class _Fail:
            ok = False
            trace = []

            def to_dict(self):
                return {"ok": False}

            def to_untrusted_text(self):
                return ""
        fc.fetch = lambda *a_, **kw: _Fail()
        sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
        rc = cli.cmd_fetch(_parse(["fetch", "https://a.test/"]))
        sys.stdout, sys.stderr = o_out, o_err
        checks.append(("cmd_fetch not-ok returns 1", rc == 1))

        def _boom(*a_, **kw):
            raise RuntimeError("kaboom")
        fc.fetch = _boom
        out, err = io.StringIO(), io.StringIO()
        sys.stdout, sys.stderr = out, err
        rc = cli.cmd_fetch(_parse(["fetch", "https://a.test/"]))
        sys.stdout, sys.stderr = o_out, o_err
        checks.append(("cmd_fetch exception returns 1", rc == 1))
        checks.append(("cmd_fetch exception names the type", "RuntimeError" in err.getvalue()))
    finally:
        fc.fetch = orig_fetch
        sys.stdout, sys.stderr = o_out, o_err

    # ------------------------------------------------- dispatch: cmd_fetch_parallel
    import channels as ch
    orig_fp = ch.fetch_parallel
    try:
        ch.fetch_parallel = lambda urls, **kw: {u: {"ok": True, "content": "x", "error": None} for u in urls}
        out, err = io.StringIO(), io.StringIO()
        sys.stdout, sys.stderr = out, err
        rc = cli.cmd_fetch_parallel(_parse(["fetch-parallel", "https://a.test/1", "https://a.test/2", "--json"]))
        sys.stdout, sys.stderr = o_out, o_err
        checks.append(("cmd_fetch_parallel returns 0", rc == 0))
        checks.append(("cmd_fetch_parallel json has both urls",
                       "https://a.test/1" in out.getvalue() and "https://a.test/2" in out.getvalue()))

        ch.fetch_parallel = lambda urls, **kw: {u: {"ok": False, "content": "", "error": "nope"} for u in urls}
        sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
        rc = cli.cmd_fetch_parallel(_parse(["fetch-parallel", "https://a.test/1"]))
        sys.stdout, sys.stderr = o_out, o_err
        checks.append(("cmd_fetch_parallel all-failed returns 1", rc == 1))
    finally:
        ch.fetch_parallel = orig_fp
        sys.stdout, sys.stderr = o_out, o_err

    # ------------------------------------------------- dispatch: cmd_check
    import channels as ch2
    orig_all = ch2.ALL_CHANNELS
    try:
        class _Ch:
            def __init__(self, name, ok):
                self.name = name
                self.tier = 0
                self.backends = ["curl"]
                self.active_backend = "curl" if ok else None

            def check(self, config=None):
                return self.active_backend is not None

        ch2.ALL_CHANNELS = [_Ch("good", True), _Ch("bad", False)]
        out, err = io.StringIO(), io.StringIO()
        sys.stdout, sys.stderr = out, err
        rc = cli.cmd_check(_parse(["check"]))
        sys.stdout, sys.stderr = o_out, o_err
        checks.append(("cmd_check returns 0", rc == 0))
        checks.append(("cmd_check reports both channels",
                       "good" in out.getvalue() and "bad" in out.getvalue()))
    finally:
        ch2.ALL_CHANNELS = orig_all
        sys.stdout, sys.stderr = o_out, o_err

    # ------------------------------------------------- dispatch: cmd_chain
    # cmd_chain re-loads engine/chain_state.py via importlib into a FRESH module
    # object, so patching sys.modules['engine.chain_state'] would have no effect.
    # Drive the real path instead: write a chain.json into a temp engagements
    # root and pass --base-dir. Layout is <base_dir>/<target>/chain.json.
    import json as _json
    import tempfile
    o_out, o_err = sys.stdout, sys.stderr
    with tempfile.TemporaryDirectory() as td:
        tdir = os.path.join(td, "t.test")
        os.makedirs(tdir)
        with open(os.path.join(tdir, "chain.json"), "w", encoding="utf-8") as fh:
            _json.dump({
                "target": "t.test", "started_by": "novaxinwei", "state": {},
                "history": [],
            }, fh)
        out, err = io.StringIO(), io.StringIO()
        sys.stdout, sys.stderr = out, err
        rc = cli.cmd_chain(_parse(["chain", "--target", "t.test", "--base-dir", td]))
        sys.stdout, sys.stderr = o_out, o_err
        checks.append(("cmd_chain returns 0 when chain.json exists", rc == 0))
        checks.append(("cmd_chain prints target", "t.test" in out.getvalue()))

        out, err = io.StringIO(), io.StringIO()
        sys.stdout, sys.stderr = out, err
        rc = cli.cmd_chain(_parse(["chain", "--target", "t.test", "--base-dir", td, "--json"]))
        sys.stdout, sys.stderr = o_out, o_err
        checks.append(("cmd_chain --json is valid json", _json.loads(out.getvalue())["target"] == "t.test"))

        # no chain.json -> honest non-zero
        out, err = io.StringIO(), io.StringIO()
        sys.stdout, sys.stderr = out, err
        rc = cli.cmd_chain(_parse(["chain", "--target", "absent.test", "--base-dir", td]))
        sys.stdout, sys.stderr = o_out, o_err
        checks.append(("cmd_chain returns 1 without chain.json", rc == 1))
    sys.stdout, sys.stderr = o_out, o_err

    # ------------------------------------------------- no command -> help, rc 0
    out, err = io.StringIO(), io.StringIO()
    sys.stdout, sys.stderr = out, err
    rc = cli.main([])
    sys.stdout, sys.stderr = o_out, o_err
    checks.append(("main with no command is not an error", rc == 0))
    checks.append(("main with no command prints usage", "usage" in (out.getvalue() + err.getvalue()).lower()))

    # ------------------------------------------------- report
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {name}")
    print(f"[+] cli selftest: {len(checks) - len(failed)}/{len(checks)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
