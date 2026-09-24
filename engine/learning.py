"""U5: lightweight per-host self-learning store (`observations/learned.json`).

Records which fetch route (impersonate × referer × url-transform × phase) last
SUCCEEDED for a host, so the next visit promotes it to the probe / front of the
grid instead of rediscovering it from scratch. The store is bounded and
self-pruning so it can never grow without limit:

  * eviction on failure — a learned route that fails on a REAL block
    (`exhausted` / `challenge` / `blocked`) earns a strike; after
    ``EVICT_AFTER_FAILS`` consecutive real failures the entry is deleted.
    Transient outcomes (429 rate-limit, network/unknown error, budget cut) and
    URL-level outcomes (404/401) never strike — they are not the route's fault.
  * TTL — an entry unused for ``TTL_DAYS`` is pruned the next time the store is
    loaded (default 30 days).
  * cap — at most ``MAX_ENTRIES`` (default 500); on overflow the
    least-recently-used entries are dropped.

This is a DATA file, never code, so the No-Site-Name Rule (R3) holds: per-site
knowledge lives in JSON that both the engine and the agent can read, while the
fetch chain itself stays site-agnostic.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlsplit

TTL_DAYS = int(os.environ.get("NOVAXINWEI_LEARN_TTL_DAYS", "30"))
MAX_ENTRIES = int(os.environ.get("NOVAXINWEI_LEARN_MAX", "500"))
EVICT_AFTER_FAILS = 2

# stop_reason values that mean the access ROUTE genuinely failed (→ strike).
# Everything else (rate_limited / unknown / budget / auth_required / not_found /
# success / "") is transient or URL-level and never strikes the route.
PENALIZE_REASONS = frozenset({"exhausted", "challenge", "blocked"})


def enabled() -> bool:
    return os.environ.get("NOVAXINWEI_LEARN", "1") not in ("0", "false", "no")


def default_path() -> str:
    p = os.environ.get("NOVAXINWEI_LEARNED_PATH")
    if p:
        return p
    return os.path.join(os.path.expanduser("~"), ".novaxinwei", "learned.json")


def is_real_failure(stop_reason: str) -> bool:
    """True when `stop_reason` means the route itself was blocked (→ strike)."""
    return (stop_reason or "") in PENALIZE_REASONS


def key_for(url: str, device_class: str) -> str:
    # Use hostname (not netloc) so the learning key matches the session pool /
    # profile-dir host key (transport._host_of, executor._profile_dir_for),
    # which both drop port + userinfo. netloc kept them, so a URL with a port
    # (or credentials) learned under a different key than it fetched under.
    host = (urlsplit(url).hostname or "").lower()
    dev = "mobile" if device_class == "mobile" else "desktop"
    return f"{host}::{dev}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts: str) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(ts)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _prune(data: dict, now: Optional[datetime] = None) -> dict:
    """Drop TTL-expired entries, then enforce the LRU cap. Pure (in-memory)."""
    now = now or _now()
    cutoff = now - timedelta(days=TTL_DAYS)
    kept = {}
    for k, v in data.items():
        lu = _parse(v.get("last_used", "")) if isinstance(v, dict) else None
        if lu is None or lu >= cutoff:
            kept[k] = v
    if len(kept) > MAX_ENTRIES:
        # keep the MAX_ENTRIES most-recently-used
        ordered = sorted(
            kept.items(),
            key=lambda kv: _parse(kv[1].get("last_used", "")) or now,
            reverse=True,
        )
        kept = dict(ordered[:MAX_ENTRIES])
    return kept


def load(path: Optional[str] = None) -> dict:
    """Load the store, pruning TTL-expired + over-cap entries in memory.

    Pruning is not persisted here (write-on-read is wasteful); the next
    `record_*` save writes the pruned set back, so the file converges."""
    path = path or default_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return _prune(data)


def save(data: dict, path: Optional[str] = None) -> None:
    path = path or default_path()
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp, path)
    except OSError:
        pass  # learning is best-effort; never break a fetch on a write error


def lookup(url: str, device_class: str, path: Optional[str] = None,
           data: Optional[dict] = None) -> Optional[dict]:
    """Return the learned route dict for this host, or None."""
    data = load(path) if data is None else data
    entry = data.get(key_for(url, device_class))
    if isinstance(entry, dict):
        route = entry.get("route")
        if isinstance(route, dict):
            return route
    return None


def record_success(url: str, device_class: str, route: dict,
                   path: Optional[str] = None) -> None:
    """Upsert the winning route for this host (resets the failure strike)."""
    path = path or default_path()
    data = load(path)
    k = key_for(url, device_class)
    now = _now().isoformat()
    raw = data.get(k)
    entry = raw if isinstance(raw, dict) else {}
    same = entry.get("route") == route
    data[k] = {
        "route": route,
        "wins": int(entry.get("wins", 0)) + 1 if same else 1,
        "consecutive_fails": 0,
        "last_used": now,
        "last_success": now,
    }
    save(_prune(data), path)


def record_failure(url: str, device_class: str, penalize: bool,
                   path: Optional[str] = None) -> None:
    """Record that the learned route did not win this run.

    `penalize=True` (a real block) strikes the entry and deletes it after
    EVICT_AFTER_FAILS consecutive strikes. `penalize=False` (transient / URL
    issue) just refreshes `last_used` so an actively-retried host is not
    TTL-pruned. No-op when nothing was learned for this host."""
    path = path or default_path()
    data = load(path)
    k = key_for(url, device_class)
    entry = data.get(k)
    if not isinstance(entry, dict):
        return
    if penalize:
        entry["consecutive_fails"] = int(entry.get("consecutive_fails", 0)) + 1
        entry["last_used"] = _now().isoformat()
        if entry["consecutive_fails"] >= EVICT_AFTER_FAILS:
            del data[k]
    else:
        entry["last_used"] = _now().isoformat()
    save(_prune(data), path)


def _selftest() -> int:
    """Self-check. Uses a temp store file; never touches the real ~/.novaxinwei
    learned.json. No network egress."""
    import tempfile

    checks: list[tuple[str, bool]] = []

    # key_for normalizes host + device class
    checks.append(("key_for host only", key_for("https://Example.com:8443/x", "desktop") == "example.com::desktop"))
    checks.append(("key_for mobile", key_for("https://example.com/x", "mobile") == "example.com::mobile"))
    checks.append(("key_for non-mobile is desktop", key_for("https://example.com/x", "tablet") == "example.com::desktop"))

    # is_real_failure taxonomy
    for reason, expected in [("exhausted", True), ("challenge", True), ("blocked", True),
                             ("rate_limited", False), ("unknown", False), ("budget", False),
                             ("auth_required", False), ("not_found", False), ("success", False),
                             ("", False), (None, False)]:
        checks.append((f"is_real_failure {reason!r}", is_real_failure(reason) is expected))

    with tempfile.TemporaryDirectory() as td:
        store = os.path.join(td, "learned.json")

        # empty store: lookup None, load {}
        checks.append(("load missing -> {}", load(store) == {}))
        checks.append(("lookup empty -> None", lookup("https://x.test/", "desktop", path=store) is None))

        # record success + lookup roundtrip
        route = {"impersonate": "chrome", "phase": "p1"}
        record_success("https://x.test/a", "desktop", route, path=store)
        got = lookup("https://x.test/b", "desktop", path=store)   # same host, other path
        checks.append(("lookup returns route", got == route))
        data = load(store)
        e = data["x.test::desktop"]
        checks.append(("success resets fails", e["consecutive_fails"] == 0))
        checks.append(("success counts wins", e["wins"] == 1))
        checks.append(("last_success set", bool(e.get("last_success"))))

        # same route twice -> wins incremented, not reset
        record_success("https://x.test/c", "desktop", route, path=store)
        checks.append(("same route increments wins", load(store)["x.test::desktop"]["wins"] == 2))

        # different route -> wins reset to 1
        record_success("https://x.test/d", "desktop", {"impersonate": "safari", "phase": "p2"}, path=store)
        checks.append(("new route resets wins", load(store)["x.test::desktop"]["wins"] == 1))

        # failure strike: one penalize -> still present; second -> evicted
        record_success("https://x.test/e", "desktop", route, path=store)
        record_failure("https://x.test/f", "desktop", penalize=True, path=store)
        checks.append(("one strike keeps entry", "x.test::desktop" in load(store)))
        record_failure("https://x.test/g", "desktop", penalize=True, path=store)
        checks.append(("two strikes evict", "x.test::desktop" not in load(store)))

        # non-penalizing failure refreshes without evicting
        record_success("https://y.test/", "desktop", route, path=store)
        record_failure("https://y.test/n", "desktop", penalize=False, path=store)
        checks.append(("non-penalize keeps entry", "y.test::desktop" in load(store)))

        # record_failure on unknown host is a no-op (no crash)
        record_failure("https://z.test/", "desktop", penalize=True, path=store)
        checks.append(("failure on unknown host no-op", True))

        # corrupted store -> load {}
        with open(store, "w", encoding="utf-8") as f:
            f.write("{not json")
        checks.append(("corrupt store -> {}", load(store) == {}))

    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {name}")
    if failed:
        print(f"[!] learning selftest: {len(failed)}/{len(checks)} failed: {failed}")
        return 1
    print(f"[+] learning selftest: {len(checks)}/{len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
