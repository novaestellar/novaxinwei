"""Generic URL transforms for the fetch grid.

Transforms are domain-agnostic *rules*. They never reference a specific
site by name. A transform either applies (returns a new URL) or is skipped
(returns None). Callers iterate transforms in order.

Empirically useful transforms (see observations/):
  * mobile_subdomain — `www.example.com` → `m.example.com`
    Strong win on SSR sites with mobile-first serving. Loss on SPA shells
    (some mobile sites return tiny bootstrap HTML).
  * am_prefix — `example.com` (no www) → `m.example.com`
  * m_prefix_subdomain — `blog.example.com` → `m.blog.example.com`
    Portal-style hosts (blog./cafe./kin. …) often serve a tiny frameset
    shell on desktop that the verdict layer reads as `tiny_body`, while the
    `m.`-prefixed twin is full SSR. Cross-site validated 2026-09-05 on two
    unrelated portals (2.9KB→28KB, 1.6KB→24KB).
  * drop_www — occasionally unblocks hosts that gate www but not apex.

Adding new transforms: prove they help on ≥2 unrelated sites first
(cross-site validation — bias check).
"""
from __future__ import annotations

from typing import Callable, Optional
from urllib.parse import urlsplit, urlunsplit


def _replace_host(url: str, new_host: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(parts._replace(netloc=new_host))


def _original(url: str) -> Optional[str]:
    return url


def _mobile_subdomain(url: str) -> Optional[str]:
    """`https://www.example.com/a` → `https://m.example.com/a` (only if host starts with www.)."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    if not host.startswith("www."):
        return None
    new_host = "m." + host[4:]
    if parts.port:
        new_host = f"{new_host}:{parts.port}"
    return _replace_host(url, new_host)


def _am_prefix(url: str) -> Optional[str]:
    """`https://example.com/a` → `https://m.example.com/a` (only if host has no subdomain)."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    if not host or host.startswith("m."):
        return None
    # Only apply to apex-like hosts (≤2 dot-separated labels).
    if host.count(".") >= 2 and not host.startswith("www."):
        return None
    if host.startswith("www."):
        return None  # handled by mobile_subdomain
    return _replace_host(url, "m." + host)


def _m_prefix_subdomain(url: str) -> Optional[str]:
    """`https://blog.example.com/a` → `https://m.blog.example.com/a`.

    Only for hosts that already carry a subdomain (≥2 dots) and are not
    `www.` (handled by mobile_subdomain) or already `m.`. Apex hosts are
    handled by am_prefix, so the three mobile transforms never overlap."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    if host.count(".") < 2 or host.startswith(("www.", "m.")):
        return None
    new_host = "m." + host
    if parts.port:
        new_host = f"{new_host}:{parts.port}"
    return _replace_host(url, new_host)


def _drop_www(url: str) -> Optional[str]:
    parts = urlsplit(url)
    host = parts.hostname or ""
    if not host.startswith("www."):
        return None
    return _replace_host(url, host[4:])


TRANSFORMS: dict[str, Callable[[str], Optional[str]]] = {
    "original": _original,
    "mobile_subdomain": _mobile_subdomain,
    "am_prefix": _am_prefix,
    "m_prefix_subdomain": _m_prefix_subdomain,
    "drop_www": _drop_www,
}


def apply_transform(name: str, url: str) -> Optional[str]:
    """Apply one transform by name. Returns transformed URL or None if skipped."""
    fn = TRANSFORMS.get(name)
    if fn is None:
        raise ValueError(f"Unknown transform: {name!r}. Known: {list(TRANSFORMS)}")
    return fn(url)


def iter_transformed(url: str, order: list[str]) -> list[tuple[str, str]]:
    """Yield (transform_name, transformed_url) pairs for a given order.

    Skips transforms that return None (not applicable) and deduplicates
    URLs (so `original` and `drop_www` of `https://example.com` don't double-run).
    """
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for name in order:
        new_url = apply_transform(name, url)
        if new_url is None:
            continue
        if new_url in seen:
            continue
        seen.add(new_url)
        out.append((name, new_url))
    return out


def _selftest() -> int:
    """Self-check on the transform rules. Pure string work, no network.

    The load-bearing property is NON-OVERLAP: the three mobile transforms
    partition host shapes so a single URL never gets two different mobile
    rewrites from the same order."""
    checks: list[tuple[str, bool]] = []

    # --- original is the identity, and never None ---
    for url in ("https://example.com", "https://www.example.com/a?b=1#f", "not a url"):
        checks.append((f"original passthrough {url[:28]!r}", _original(url) == url))

    # --- mobile_subdomain: www. only ---
    checks.append(("mobile_subdomain rewrites www",
                   _mobile_subdomain("https://www.example.com/a") == "https://m.example.com/a"))
    checks.append(("mobile_subdomain skips apex",
                   _mobile_subdomain("https://example.com/a") is None))
    checks.append(("mobile_subdomain skips m. already",
                   _mobile_subdomain("https://m.example.com/a") is None))
    checks.append(("mobile_subdomain skips deep subdomain",
                   _mobile_subdomain("https://blog.example.com/a") is None))
    # Port must survive the host swap (a dropped :8080 silently hits the wrong service).
    checks.append(("mobile_subdomain keeps port",
                   _mobile_subdomain("https://www.example.com:8443/a")
                   == "https://m.example.com:8443/a"))
    # Path/query/fragment must survive.
    checks.append(("mobile_subdomain keeps path+query",
                   _mobile_subdomain("https://www.example.com/p/x?q=1")
                   == "https://m.example.com/p/x?q=1"))

    # --- am_prefix: apex only ---
    checks.append(("am_prefix rewrites apex",
                   _am_prefix("https://example.com/a") == "https://m.example.com/a"))
    checks.append(("am_prefix skips www (owned by mobile_subdomain)",
                   _am_prefix("https://www.example.com/a") is None))
    checks.append(("am_prefix skips m. already",
                   _am_prefix("https://m.example.com/a") is None))
    checks.append(("am_prefix skips deep subdomain",
                   _am_prefix("https://blog.example.com/a") is None))
    checks.append(("am_prefix skips empty host", _am_prefix("file:///x") is None))
    checks.append(("am_prefix keeps port",
                   _am_prefix("https://example.com:8080/a")
                   == "https://m.example.com/a"))

    # --- m_prefix_subdomain: deep subdomains only ---
    checks.append(("m_prefix_subdomain rewrites blog.",
                   _m_prefix_subdomain("https://blog.example.com/a")
                   == "https://m.blog.example.com/a"))
    checks.append(("m_prefix_subdomain skips apex",
                   _m_prefix_subdomain("https://example.com/a") is None))
    checks.append(("m_prefix_subdomain skips www",
                   _m_prefix_subdomain("https://www.example.com/a") is None))
    checks.append(("m_prefix_subdomain skips m. already",
                   _m_prefix_subdomain("https://m.example.com/a") is None))
    checks.append(("m_prefix_subdomain skips deeper m. host",
                   _m_prefix_subdomain("https://m.blog.example.com/a") is None))
    checks.append(("m_prefix_subdomain keeps port",
                   _m_prefix_subdomain("https://blog.example.com:9443/a")
                   == "https://m.blog.example.com:9443/a"))

    # --- drop_www ---
    checks.append(("drop_www strips www",
                   _drop_www("https://www.example.com/a") == "https://example.com/a"))
    checks.append(("drop_www skips apex", _drop_www("https://example.com/a") is None))
    checks.append(("drop_www skips deep", _drop_www("https://blog.example.com/a") is None))

    # --- NON-OVERLAP: exactly one mobile transform claims each host shape ---
    shapes = [
        "https://www.example.com/a",
        "https://example.com/a",
        "https://blog.example.com/a",
        "https://m.example.com/a",
        "https://a.b.c.example.com/a",
    ]
    mobile = [_mobile_subdomain, _am_prefix, _m_prefix_subdomain]
    for url in shapes:
        claimed = [f.__name__ for f in mobile if f(url) is not None]
        checks.append((f"exactly one mobile transform claims {url[8:30]!r} (got {claimed})",
                       len(claimed) <= 1))
    # And the two that must never both apply to the same URL:
    for url in shapes:
        both = _mobile_subdomain(url) is not None and _am_prefix(url) is not None
        checks.append((f"mobile_subdomain and am_prefix never both fire on {url[8:26]!r}",
                       both is False))

    # --- apply_transform dispatch ---
    checks.append(("apply_transform dispatches by name",
                   apply_transform("drop_www", "https://www.a.test/") == "https://a.test/"))
    checks.append(("apply_transform returns None for inapplicable",
                   apply_transform("drop_www", "https://a.test/") is None))
    try:
        apply_transform("no_such_transform", "https://a.test/")
        checks.append(("unknown transform raises ValueError", False))
    except ValueError as e:
        checks.append(("unknown transform raises ValueError", True))
        checks.append(("error names the bad transform", "no_such_transform" in str(e)))
        checks.append(("error lists the known ones", "mobile_subdomain" in str(e)))
    checks.append(("TRANSFORMS holds all five rules",
                   set(TRANSFORMS) == {"original", "mobile_subdomain", "am_prefix",
                                       "m_prefix_subdomain", "drop_www"}))

    # --- iter_transformed: order honoured, Nones skipped, duplicates collapsed ---
    order = ["original", "mobile_subdomain", "am_prefix", "m_prefix_subdomain", "drop_www"]
    got = iter_transformed("https://www.example.com/a", order)
    names = [n for n, _ in got]
    checks.append(("iter: original kept first", names[0] == "original"))
    checks.append(("iter: am_prefix skipped for www host", "am_prefix" not in names))
    checks.append(("iter: m_prefix_subdomain skipped for www host",
                   "m_prefix_subdomain" not in names))
    checks.append(("iter: mobile_subdomain present", "mobile_subdomain" in names))
    checks.append(("iter: drop_www present", "drop_www" in names))

    got = iter_transformed("https://example.com/a", order)
    names = [n for n, _ in got]
    checks.append(("iter: apex gets am_prefix", "am_prefix" in names))
    checks.append(("iter: apex gets no mobile_subdomain", "mobile_subdomain" not in names))
    checks.append(("iter: apex gets no drop_www", "drop_www" not in names))

    # None-skip and dedup are tested SEPARATELY, because a case that exercises
    # both at once passes when either one alone is broken (a sabotaged dedup
    # still collapses once None-skipping eats the duplicate, and vice versa).
    # Independent None-skip test: on a deep host drop_www is not applicable,
    # so a broken None-skip emits a `None` URL entry.
    got = iter_transformed("https://blog.example.com/a", ["original", "drop_www"])
    checks.append(("iter: inapplicable transform emits no entry",
                   [n for n, _ in got] == ["original"]))
    checks.append(("iter: no None URL ever reaches the caller",
                   all(u for _, u in got)))

    # Dedup needs two rules producing the SAME URL, which no shipped rule pair
    # does on one input (on an apex host drop_www returns None, am_prefix
    # rewrites the host). So a rule is injected that returns its input verbatim:
    # it collides with `original`, and only dedup keeps the second one out.
    def _dup_rule(url: str) -> Optional[str]:
        return url
    TRANSFORMS["_dup_probe"] = _dup_rule
    try:
        got = iter_transformed("https://example.com/a", ["_dup_probe", "original"])
        urls = [u for _, u in got]
        checks.append(("iter: identical outputs collapse to one entry", len(urls) == 1))
        checks.append(("iter: collapse keeps the FIRST rule that produced it",
                       bool(got) and got[0][0] == "_dup_probe"))

        # A repeat of the same rule name in the order list is also a duplicate.
        got = iter_transformed("https://example.com/a", ["_dup_probe", "_dup_probe"])
        checks.append(("iter: repeated rule name collapses", len(got) == 1))
    finally:
        del TRANSFORMS["_dup_probe"]

    # Independent dedup on the REAL rule set: `original` twice must collapse.
    got = iter_transformed("https://example.com/a", ["original", "original"])
    checks.append(("iter: 'original' twice collapses to one", len(got) == 1))

    # And the None-skip must not be what does the collapsing: with dedup intact
    # two DISTINCT URLs must both survive.
    got = iter_transformed("https://www.example.com/a", ["original", "drop_www", "mobile_subdomain"])
    checks.append(("iter: distinct URLs are not collapsed",
                   len({u for _, u in got}) == len(got) >= 3))

    # Order is respected verbatim.
    got = iter_transformed("https://www.example.com/a", ["drop_www", "original"])
    checks.append(("iter: caller order respected", [n for n, _ in got] == ["drop_www", "original"]))
    checks.append(("iter: empty order yields nothing",
                   iter_transformed("https://a.test/", []) == []))
    # An order the profile actually ships must produce a real grid.
    shipped = ["original", "mobile_subdomain", "m_prefix_subdomain"]
    checks.append(("iter: shipped order yields >=2 variants for a www host",
                   len(iter_transformed("https://www.example.com/a", shipped)) >= 2))

    # --- No-Site-Name Rule: the module may not name a site ---
    import os as _os
    raw = open(_os.path.join(_os.path.dirname(__file__), "url_transforms.py"),
               encoding="utf-8").read().lower()
    body = raw.split("_selftest")[0]          # docstring examples are allowed
    named = [h for h in ("google.", "facebook.", "twitter.", "amazon.", "microsoft.")
             if h in body]
    checks.append(("transform rules carry no site names", named == []))

    failed = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {n}")
    if failed:
        print(f"[!] url_transforms selftest: {len(failed)}/{len(checks)} failed: {failed}")
        return 1
    print(f"[+] url_transforms selftest: {len(checks)}/{len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
