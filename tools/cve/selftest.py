# -*- coding: utf-8 -*-
"""CVE tool selftest — scraper feed shape and Novahaku cache export.

No network and no writes outside a temp dir: requests.get is stubbed and
the export destination is redirected with NOVAHAKU_PATHS patching.

Run:  python tools/cve/selftest.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import List

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name: str):
    cached = sys.modules.get(f"{name}_mod")
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(f"{name}_mod", os.path.join(_HERE, f"{name}.py"))
    assert spec is not None and spec.loader is not None, f"cannot locate {name}.py"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"{name}_mod"] = mod
    spec.loader.exec_module(mod)
    return mod


def _selftest() -> int:
    checks: List[tuple[str, bool]] = []
    scraper = _load("cve_scraper")
    exporter = _load("export_to_novahaku")

    # ------------------------------------------------- fetch_github_advisories
    class _Resp:
        def __init__(self, payload, status=200):
            self._p = payload
            self.status_code = status

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")
            return None

        def json(self):
            return self._p

    orig_get = scraper.requests.get
    try:
        raw = [{
            "cve_id": "CVE-2024-0001",
            "ghsa_id": "GHSA-xxxx-yyyy-zzzz",
            "summary": "test advisory",
            "severity": "high",
            "published_at": "2024-01-01T00:00:00Z",
            "html_url": "https://github.com/advisories/GHSA-xxxx-yyyy-zzzz",
            "vulnerabilities": [
                {"package": {"name": "left-pad"}},
                {"package": {"name": "right-pad"}},
                {"package": {}},
            ],
        }]
        scraper.requests.get = lambda *a, **kw: _Resp(raw)
        out = scraper.fetch_github_advisories()
        checks.append(("advisory parsed", len(out) == 1))
        a = out[0]
        checks.append(("cve_id mapped", a["cve_id"] == "CVE-2024-0001"))
        checks.append(("ghsa_id mapped", a["ghsa_id"] == "GHSA-xxxx-yyyy-zzzz"))
        checks.append(("severity mapped", a["severity"] == "high"))
        checks.append(("url mapped", a["url"].startswith("https://github.com/advisories/")))
        checks.append(("package names extracted", "left-pad" in a["affected_packages"]))
        checks.append(("package missing name -> None kept", None in a["affected_packages"]))

        # filters are forwarded as query params
        captured = {}

        def _cap(url, params=None, **kw):
            captured.update(params or {})
            return _Resp([])
        scraper.requests.get = _cap
        scraper.fetch_github_advisories(ecosystem="pip", severity="critical")
        checks.append(("ecosystem param forwarded", captured.get("ecosystem") == "pip"))
        checks.append(("severity param forwarded", captured.get("severity") == "critical"))
        checks.append(("per_page param set", captured.get("per_page") == 100))
        captured.clear()
        scraper.fetch_github_advisories()
        checks.append(("no filters -> no ecosystem key", "ecosystem" not in captured))

        # network error is swallowed and yields an empty feed
        def _boom(*a, **kw):
            raise RuntimeError("network down")
        scraper.requests.get = _boom
        checks.append(("advisory fetch swallows error", scraper.fetch_github_advisories() == []))

        # HTTP error path
        scraper.requests.get = lambda *a, **kw: _Resp([], status=500)
        checks.append(("advisory fetch swallows HTTP error", scraper.fetch_github_advisories() == []))

        # empty payload
        scraper.requests.get = lambda *a, **kw: _Resp([])
        checks.append(("advisory empty payload", scraper.fetch_github_advisories() == []))
    finally:
        scraper.requests.get = orig_get

    # ------------------------------------------------- fetch_hackerone_disclosed
    checks.append(("h1 no key -> empty", scraper.fetch_hackerone_disclosed() == []))
    checks.append(("h1 no key -> empty (explicit None)", scraper.fetch_hackerone_disclosed(None) == []))
    checks.append(("h1 key given -> still empty (deferred)", scraper.fetch_hackerone_disclosed("KEY") == []))

    # ------------------------------------------------- save_feed
    with tempfile.TemporaryDirectory() as td:
        orig_cache = scraper.CACHE_DIR
        cwd = os.getcwd()
        try:
            scraper.CACHE_DIR = os.path.join(td, "cve_cache")
            os.chdir(td)
            feed = {"stats": {"github_count": 1, "h1_count": 0}, "github_advisories": [{"cve_id": "x"}],
                    "updated_at": "2024-01-01T00:00:00Z", "source": "novaxinwei-cve-scraper"}
            path = scraper.save_feed(feed)
            checks.append(("save_feed returns path", os.path.isfile(path)))
            checks.append(("save_feed creates cache dir", os.path.isdir(scraper.CACHE_DIR)))
            with open(path, encoding="utf-8") as fh:
                back = json.load(fh)
            checks.append(("save_feed round-trips json", back == feed))
            checks.append(("save_feed default filename", os.path.basename(path) == "cve-feed.json"))
            path2 = scraper.save_feed({"a": 1}, filename="custom.json")
            checks.append(("save_feed custom filename", os.path.basename(path2) == "custom.json"))
            checks.append(("save_feed custom exists", os.path.isfile(path2)))
        finally:
            scraper.CACHE_DIR = orig_cache
            os.chdir(cwd)

    # ------------------------------------------------- export: path detection
    with tempfile.TemporaryDirectory() as td:
        # fake a novahaku tree: <td>/testing/hunt/hunt-cicd/cache/
        hunt_cicd = Path(td) / "testing" / "hunt" / "hunt-cicd"
        hunt_cicd.mkdir(parents=True)
        target = hunt_cicd / "cache"
        orig_paths = exporter.NOVAHAKU_PATHS
        cwd = os.getcwd()
        try:
            exporter.NOVAHAKU_PATHS = [target, Path(td) / "nonexistent" / "cache"]
            found = exporter.find_novahaku_cache()
            checks.append(("find cache picks existing parent", found == target))
            checks.append(("find cache creates cache dir", target.is_dir()))

            # export a real feed into it
            src = Path(td) / "feed.json"
            src.write_text(json.dumps({
                "stats": {"github_count": 7, "h1_count": 2},
                "updated_at": "2024-05-05T00:00:00Z",
            }), encoding="utf-8")
            os.chdir(td)
            ok = exporter.export_cve_feed(str(src))
            checks.append(("export returns True", ok is True))
            dest = target / "cve-feed.json"
            checks.append(("export wrote destination", dest.is_file()))
            with open(dest, encoding="utf-8") as fh:
                checks.append(("export content preserved", json.load(fh)["stats"]["github_count"] == 7))

            # missing source -> False
            checks.append(("export missing source -> False", exporter.export_cve_feed(str(Path(td) / "nope.json")) is False))
        finally:
            exporter.NOVAHAKU_PATHS = orig_paths
            os.chdir(cwd)

        # no novahaku tree at all -> None / False
        with tempfile.TemporaryDirectory() as td2:
            exporter.NOVAHAKU_PATHS = [Path(td2) / "a" / "cache", Path(td2) / "b" / "cache"]
            checks.append(("find cache None when absent", exporter.find_novahaku_cache() is None))

    # ------------------------------------------------- report
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {name}")
    print(f"[+] cve tools selftest: {len(checks) - len(failed)}/{len(checks)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
