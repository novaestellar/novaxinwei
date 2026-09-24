"""Append-only operational observations for profile tuning.

Route learning remains exclusively in ``learning.py``. This module only
records outcomes to ``observations/fetch-YYYY-MM-DD.jsonl`` so repeated
cross-site evidence can be reviewed before changing WAF profiles.

Env override: ``NOVAXINWEI_OBSERVATIONS_DIR``.
Logging is best-effort and never changes a fetch outcome.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

from .url_masking import mask_url

_SKILL_DIR = Path(__file__).resolve().parent.parent


def _obs_dir() -> Path:
    override = os.environ.get("NOVAXINWEI_OBSERVATIONS_DIR")
    return Path(override) if override else _SKILL_DIR / "observations"


def log_fetch(url: str, result) -> None:
    try:
        trace = getattr(result, "trace", []) or []
        winner = next(
            (a for a in reversed(trace) if getattr(a, "verdict", "") in ("strong_ok", "weak_ok")),
            None,
        )
        entry = {
            "ts": int(time.time()),
            "url": mask_url(url),
            "domain": (urlparse(url).hostname or "").lower(),
            "ok": bool(getattr(result, "ok", False)),
            "verdict": getattr(result, "verdict", ""),
            "profile_used": getattr(result, "profile_used", None),
            "attempts": len(trace),
            "planned_attempts": getattr(result, "planned_attempts", 0),
            "stop_reason": getattr(result, "stop_reason", ""),
        }
        if winner is not None:
            entry["winner"] = {
                "phase": getattr(winner, "phase", ""),
                "executor": getattr(winner, "executor", ""),
                "transform": getattr(winner, "url_transform", ""),
                "impersonate": getattr(winner, "impersonate", None),
                "referer": mask_url(getattr(winner, "referer", "")),
                "status": getattr(winner, "status", 0),
                "body_size": getattr(winner, "body_size", 0),
            }
        directory = _obs_dir()
        directory.mkdir(parents=True, exist_ok=True)
        day = time.strftime("%Y-%m-%d", time.gmtime())
        with open(directory / f"fetch-{day}.jsonl", "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        return


def _selftest() -> int:
    """Self-check logging writes a masked, well-shaped JSONL row. Uses a
    temp observation dir; never touches the real observations/ tree."""
    import tempfile
    from pathlib import Path

    checks: list[tuple[str, bool]] = []

    class Winner:
        verdict = "strong_ok"
        phase = "p2"
        executor = "curl"
        url_transform = "drop_www"
        impersonate = "chrome"
        referer = "https://site.test/a?token=SECRET"
        status = 200
        body_size = 1024

    class Result:
        trace = [Winner()]
        ok = True
        verdict = "strong_ok"
        profile_used = "default"
        planned_attempts = 3
        stop_reason = ""

    with tempfile.TemporaryDirectory() as td:
        import os
        os.environ["NOVAXINWEI_OBSERVATIONS_DIR"] = td
        try:
            log_fetch("https://site.test/path?api_key=LEAK", Result())
            files = list(Path(td).glob("fetch-*.jsonl"))
            checks.append(("writes one file", len(files) == 1))
            if files:
                line = files[0].read_text(encoding="utf-8").strip()
                entry = json.loads(line)
                checks.append(("json parses", isinstance(entry, dict)))
                checks.append(("url masked", "LEAK" not in entry["url"]))
                checks.append(("domain recorded", entry["domain"] == "site.test"))
                checks.append(("ok flag", entry["ok"] is True))
                checks.append(("winner verdict", entry["winner"]["phase"] == "p2"))
                checks.append(("winner referer masked", "SECRET" not in entry["winner"]["referer"]))
                checks.append(("attempts counted", entry["attempts"] == 1))
        finally:
            os.environ.pop("NOVAXINWEI_OBSERVATIONS_DIR", None)

    # no result object -> best-effort return without raising
    class Empty:
        pass
    with tempfile.TemporaryDirectory() as td:
        os.environ["NOVAXINWEI_OBSERVATIONS_DIR"] = td
        try:
            log_fetch("https://site.test/x", Empty())   # must not raise
            checks.append(("empty result tolerated", True))
        finally:
            os.environ.pop("NOVAXINWEI_OBSERVATIONS_DIR", None)

    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {name}")
    if failed:
        print(f"[!] observations_log selftest: {len(failed)}/{len(checks)} failed: {failed}")
        return 1
    print(f"[+] observations_log selftest: {len(checks)}/{len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
