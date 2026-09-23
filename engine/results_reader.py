"""
NovaXinWei Results Reader

Reads what Novahaku's engagement run produced, so NovaXinWei can build on real
test results instead of re-testing blind.

This is the outgoing direction of the integration. It is a read-only consumer:
nothing here writes into Novahaku's tree.

The envelope is fixed by Novahaku's publish_results():

    {
      "version": "novaxinwei.results.v1",   <- named for this consumer
      "target": "example.com",
      "timestamp": "2026-09-23T06:04:40Z",
      "source": "novahaku-engagement",
      "engagement": {"phase","phases_completed","status","forced_transitions"},
      "results": {"findings_count","by_severity","by_confidence",
                  "evidence_files","stats","findings":[...]},
      "metadata": {"generator","schema_version"}
    }

Every accessor tolerates a missing, partial, corrupt, or wrong-type file and
returns an empty value instead of raising. Recon runs unattended; a bad results
file must not break a fetch that already succeeded.

No cross-skill imports. Stdlib only.
"""

import json
import os
import sys
from typing import Any, Dict, List, Optional

RESULTS_VERSION = "novaxinwei.results.v1"
RESULTS_FILENAME = "results.json"
CSV_FILENAME = "results.csv"


def _default_root() -> str:
    """Shared engagements root: NOVAHAKU_ENGAGEMENT_DIR, else ./engagements.

    Same precedence as chain_state._default_root and engagement_output. Read-only
    callers used os.getcwd() only, so with the env var set a reader looked in a
    different root than the writer had used and reported a real engagement's
    results.json as absent - which reads as "no results yet", not as an error.
    """
    env = os.environ.get("NOVAHAKU_ENGAGEMENT_DIR", "").strip()
    return os.path.abspath(env) if env else os.path.join(os.getcwd(), "engagements")


def _results_path(target: str, base_dir: Optional[str] = None) -> str:
    root = os.path.abspath(base_dir) if base_dir else _default_root()
    return os.path.join(root, target, RESULTS_FILENAME)


def read_results(target: str, base_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Read results.json. None when absent, unreadable, or not an object.

    An engagement Novahaku never published to, or one from before this file
    existed, simply has no results - that is a normal state, not an error.
    """
    path = _results_path(target, base_dir)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, IOError, UnicodeDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None

    # Symmetric with ReconReader.load(): a *wrong* version is rejected, an
    # *absent* one is accepted. Without this, a payload from a future format
    # (version="bogus.v9") would be read as if its findings were trustworthy.
    declared = data.get("version")
    if declared is not None and declared != RESULTS_VERSION:
        print(f"Warning: {path} declares version {declared!r}, "
              f"expected {RESULTS_VERSION!r} - ignoring")
        return None
    return data


def results_exist(target: str, base_dir: Optional[str] = None) -> bool:
    """True when a readable results.json is present."""
    return read_results(target, base_dir) is not None


def results_version(target: str, base_dir: Optional[str] = None) -> Optional[str]:
    """The envelope version, or None. Lets a caller detect a format change."""
    data = read_results(target, base_dir)
    if not isinstance(data, dict):
        return None
    value = data.get("version")
    return value if isinstance(value, str) else None


def get_findings(target: str, base_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """The finding records, or [] when there are none.

    Returns [] rather than None so callers can iterate without a None guard.
    """
    data = read_results(target, base_dir)
    if not isinstance(data, dict):
        return []
    results = data.get("results")
    if not isinstance(results, dict):
        return []
    records = results.get("findings")
    if not isinstance(records, list):
        return []
    return [r for r in records if isinstance(r, dict)]


def get_finding_titles(target: str, base_dir: Optional[str] = None) -> List[str]:
    """Finding titles only - handy for a one-line summary."""
    return [
        str(r.get("title"))
        for r in get_findings(target, base_dir)
        if r.get("title") is not None
    ]


def get_severity_counts(target: str, base_dir: Optional[str] = None) -> Dict[str, int]:
    """Findings per severity. Recomputed from records rather than trusting the
    precomputed count, so a stale by_severity block cannot mislead a caller."""
    counts: Dict[str, int] = {}
    for rec in get_findings(target, base_dir):
        sev = str(rec.get("severity", "info")).lower()
        counts[sev] = counts.get(sev, 0) + 1
    return counts


def get_phase(target: str, base_dir: Optional[str] = None) -> Optional[str]:
    """Which engagement phase Novahaku reached."""
    data = read_results(target, base_dir)
    if not isinstance(data, dict):
        return None
    engagement = data.get("engagement")
    if not isinstance(engagement, dict):
        return None
    value = engagement.get("phase")
    return value if isinstance(value, str) else None


def get_stats(target: str, base_dir: Optional[str] = None) -> Dict[str, Any]:
    """The run statistics block, or {}."""
    data = read_results(target, base_dir)
    if not isinstance(data, dict):
        return {}
    results = data.get("results")
    if not isinstance(results, dict):
        return {}
    stats = results.get("stats")
    return stats if isinstance(stats, dict) else {}


def get_evidence_files(target: str, base_dir: Optional[str] = None) -> List[str]:
    """Evidence filenames Novahaku attached, or []."""
    data = read_results(target, base_dir)
    if not isinstance(data, dict):
        return []
    results = data.get("results")
    if not isinstance(results, dict):
        return []
    files = results.get("evidence_files")
    if not isinstance(files, list):
        return []
    return [str(f) for f in files if isinstance(f, (str, int, float))]


def summarize(target: str, base_dir: Optional[str] = None) -> str:
    """One-line human summary. Never raises, even with no results at all."""
    data = read_results(target, base_dir)
    if not isinstance(data, dict):
        return f"{target}: no engagement results"
    phase = get_phase(target, base_dir) or "unknown"
    counts = get_severity_counts(target, base_dir)
    if not counts:
        return f"{target}: phase={phase}, no findings"
    parts = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    return f"{target}: phase={phase}, findings={len(get_findings(target, base_dir))} ({parts})"


def _selftest() -> int:
    """Self-check in a temp dir. Touches nothing real."""
    import shutil
    import tempfile

    base = tempfile.mkdtemp(prefix="novaxinwei-results-selftest-")
    target = "results.example"
    edir = os.path.join(base, target)
    checks = []
    try:
        checks.append(("absent results returns None", read_results(target, base) is None))
        checks.append(("absent results_exist false", results_exist(target, base) is False))
        checks.append(("absent findings returns []", get_findings(target, base) == []))
        checks.append(("absent severity counts {}", get_severity_counts(target, base) == {}))
        checks.append(("absent phase None", get_phase(target, base) is None))
        checks.append(("absent stats {}", get_stats(target, base) == {}))
        checks.append(("absent evidence []", get_evidence_files(target, base) == []))
        checks.append(("absent version None", results_version(target, base) is None))
        checks.append(("absent summary is safe",
                       "no engagement results" in summarize(target, base)))

        # Root precedence: env var must be honoured, and absence must still fall
        # back to CWD. Without this a reader silently disagrees with the writer
        # whenever NOVAHAKU_ENGAGEMENT_DIR is set.
        env_root = tempfile.mkdtemp(prefix="novaxinwei-results-env-")
        old = os.environ.get("NOVAHAKU_ENGAGEMENT_DIR")
        try:
            os.environ["NOVAHAKU_ENGAGEMENT_DIR"] = env_root
            checks.append(("env var selects root",
                           _results_path(target).startswith(os.path.abspath(env_root))))
            del os.environ["NOVAHAKU_ENGAGEMENT_DIR"]
            checks.append(("absent env falls back to cwd",
                           _results_path(target) ==
                           os.path.join(os.getcwd(), "engagements", target, RESULTS_FILENAME)))
        finally:
            if old is not None:
                os.environ["NOVAHAKU_ENGAGEMENT_DIR"] = old
            else:
                os.environ.pop("NOVAHAKU_ENGAGEMENT_DIR", None)
            shutil.rmtree(env_root, ignore_errors=True)

        os.makedirs(edir, exist_ok=True)
        payload = {
            "version": RESULTS_VERSION,
            "target": target,
            "timestamp": "2026-09-23T06:04:40Z",
            "source": "novahaku-engagement",
            "engagement": {
                "phase": "report",
                "phases_completed": ["init", "recon", "race", "test"],
                "status": "active",
                "forced_transitions": [],
            },
            "results": {
                "findings_count": 2,
                "by_severity": {"high": 1, "low": 1},
                "by_confidence": {"confirmed": 1, "possible": 1},
                "evidence_files": ["f1.txt"],
                "stats": {"modules_tested": 6},
                "findings": [
                    {"id": "F-001", "title": "Missing X-Frame-Options", "severity": "High",
                     "confidence": "confirmed", "category": "headers", "asset": target,
                     "module": "webtest", "remediation": "Add the header."},
                    {"id": "F-002", "title": "Server banner disclosure", "severity": "Low",
                     "confidence": "possible", "category": "info", "asset": target,
                     "module": "webtest", "remediation": "Suppress the banner."},
                ],
            },
            "metadata": {"generator": "novahaku", "schema_version": "1.0"},
        }
        with open(os.path.join(edir, RESULTS_FILENAME), "w", encoding="utf-8") as fh:
            json.dump(payload, fh)

        checks.append(("read_results returns dict", isinstance(read_results(target, base), dict)))
        checks.append(("results_exist true", results_exist(target, base) is True))
        checks.append(("version matches", results_version(target, base) == RESULTS_VERSION))
        checks.append(("phase read", get_phase(target, base) == "report"))
        checks.append(("stats read", get_stats(target, base).get("modules_tested") == 6))
        checks.append(("evidence read", get_evidence_files(target, base) == ["f1.txt"]))
        checks.append(("two findings", len(get_findings(target, base)) == 2))
        checks.append(("titles read",
                       get_finding_titles(target, base) ==
                       ["Missing X-Frame-Options", "Server banner disclosure"]))
        checks.append(("severity counted from records",
                       get_severity_counts(target, base) == {"high": 1, "low": 1}))
        checks.append(("summary mentions counts",
                       "high=1" in summarize(target, base) and "findings=2" in summarize(target, base)))

        # A lying precomputed count must not win over the records.
        payload["results"]["by_severity"] = {"critical": 99}
        with open(os.path.join(edir, RESULTS_FILENAME), "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        checks.append(("stale by_severity ignored",
                       get_severity_counts(target, base) == {"high": 1, "low": 1}))

        # Corrupt / empty / binary / wrong type: never raise.
        rp = os.path.join(edir, RESULTS_FILENAME)
        with open(rp, "w", encoding="utf-8") as fh:
            fh.write("{broken")
        checks.append(("corrupt returns None", read_results(target, base) is None))
        checks.append(("corrupt findings []", get_findings(target, base) == []))
        checks.append(("corrupt summary safe", isinstance(summarize(target, base), str)))

        open(rp, "w").close()
        checks.append(("empty returns None", read_results(target, base) is None))

        with open(rp, "wb") as fh:
            fh.write(bytes([0xFF, 0xFE, 0x00, 0x01, 0x80, 0x90]))
        checks.append(("binary returns None", read_results(target, base) is None))

        for label, blob in [("array", "[1,2,3]"), ("string", '"nope"'), ("null", "null")]:
            with open(rp, "w", encoding="utf-8") as fh:
                fh.write(blob)
            checks.append((f"{label} returns None", read_results(target, base) is None))
            checks.append((f"{label} findings []", get_findings(target, base) == []))

        # Partial payload: missing blocks must degrade, not raise.
        with open(rp, "w", encoding="utf-8") as fh:
            json.dump({"target": target}, fh)
        checks.append(("partial findings []", get_findings(target, base) == []))
        checks.append(("partial phase None", get_phase(target, base) is None))
        checks.append(("partial version None", results_version(target, base) is None))
        checks.append(("partial summary safe", isinstance(summarize(target, base), str)))

        # Wrong types inside otherwise valid JSON.
        with open(rp, "w", encoding="utf-8") as fh:
            json.dump({"results": {"findings": "not-a-list", "evidence_files": 5,
                                   "stats": [1, 2]}, "engagement": {"phase": 7}}, fh)
        checks.append(("wrong-type findings []", get_findings(target, base) == []))
        checks.append(("wrong-type evidence []", get_evidence_files(target, base) == []))
        checks.append(("wrong-type stats {}", get_stats(target, base) == {}))
        checks.append(("wrong-type phase None", get_phase(target, base) is None))

        # Findings entries that are not dicts are skipped, not crashed on.
        with open(rp, "w", encoding="utf-8") as fh:
            json.dump({"results": {"findings": [{"title": "ok", "severity": "info"}, "junk",
                                                None, 42]}}, fh)
        checks.append(("non-dict findings skipped", len(get_findings(target, base)) == 1))
    finally:
        shutil.rmtree(base, ignore_errors=True)

    failed = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {n}")
    if failed:
        print(f"[!] results_reader selftest: {len(failed)}/{len(checks)} failed: {failed}")
        return 1
    print(f"[+] results_reader selftest: {len(checks)}/{len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest())
