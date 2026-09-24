"""WAF-product detection from a live response.

Returns a *ranking* of (profile_id, confidence) pairs — never a single verdict.
Single-answer detectors cause cascading wrong plans when misfiring (Codex's
critique). Planner consumes the ranking and tries top candidates in order.

All detectors operate on WAF-vendor artifacts (cookies / headers / body
strings) — never site hostnames. See engine/waf_profiles.yaml for the
profile definitions.
"""
from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import dataclass
from typing import Optional

try:
    import yaml  # PyYAML
except ImportError:
    yaml = None  # type: ignore


PROFILES_PATH = os.path.join(os.path.dirname(__file__), "waf_profiles.yaml")


# In-code safety net — used when waf_profiles.yaml is missing / invalid
# or PyYAML isn't installed. Keeps fetch() working in a degraded-but-sane
# mode. Must stay site-agnostic (No-Site-Name Rule).
_DEFAULT_PROFILES: dict = {
    "unknown_challenge": {
        "detectors": {},
        "confidence_rules": {"strong": 0, "weak": 0},
        "capabilities_needed": ["needs_js_exec"],
        "tls_impersonate_candidates": [
            ["safari", "chrome", "firefox"],
            ["safari_ios", "chrome_android"],
        ],
        "referer_strategies": ["self_root", "google_search", "none"],
        "url_transform_order": ["original", "mobile_subdomain", "m_prefix_subdomain"],
        "fallback_when_challenge": ["playwright_mcp", "playwright_real_chrome"],
        "notes": "in-code default — waf_profiles.yaml unavailable",
    },
}


# Module-level sticky error. Readers call `last_load_error()` after each
# `_load_profiles()` call to surface YAML problems in FetchResult.trace.
_LAST_LOAD_ERROR: Optional[str] = None


@dataclass
class DetectionHit:
    profile_id: str
    confidence: float
    signals: list[str]


def last_load_error() -> Optional[str]:
    """Return the most recent profile-loader error (or None if clean)."""
    return _LAST_LOAD_ERROR


def _load_profiles(path: str = PROFILES_PATH) -> dict:
    """Load profiles with graceful fallback.

    Never raises. On any failure (PyYAML missing, file missing, parse error,
    unexpected shape) it returns a copy of `_DEFAULT_PROFILES` and stores
    the reason in `_LAST_LOAD_ERROR` for the caller to surface.
    """
    global _LAST_LOAD_ERROR
    _LAST_LOAD_ERROR = None

    if yaml is None:
        _LAST_LOAD_ERROR = "PyYAML not installed — using in-code default profile"
        return dict(_DEFAULT_PROFILES)
    try:
        with open(path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
    except FileNotFoundError:
        _LAST_LOAD_ERROR = f"waf_profiles.yaml not found at {path}"
        return dict(_DEFAULT_PROFILES)
    except yaml.YAMLError as e:
        _LAST_LOAD_ERROR = f"YAML parse error: {type(e).__name__}: {str(e)[:200]}"
        return dict(_DEFAULT_PROFILES)
    except Exception as e:
        _LAST_LOAD_ERROR = f"profile loader: {type(e).__name__}: {str(e)[:200]}"
        return dict(_DEFAULT_PROFILES)

    if not isinstance(loaded, dict) or not any(k for k in loaded if not k.startswith("_")):
        _LAST_LOAD_ERROR = f"waf_profiles.yaml has no usable profiles"
        return dict(_DEFAULT_PROFILES)

    return loaded


def _cookies_dict(resp) -> dict:
    try:
        return {c.name: c.value for c in resp.cookies.jar}
    except Exception:
        try:
            return dict(resp.cookies) if hasattr(resp, "cookies") else {}
        except Exception:
            return {}


def _headers_dict(resp) -> dict:
    try:
        return {k.lower(): v for k, v in dict(resp.headers).items()}
    except Exception:
        return {}


def _match_patterns(haystack_keys: list[str], patterns: list[str]) -> list[str]:
    """Match literal names or fnmatch patterns (for wildcards like `X-Akamai-*`)."""
    hits: list[str] = []
    lowered_keys = [k.lower() for k in haystack_keys]
    for pat in patterns or []:
        pat_l = pat.lower()
        if any(c in pat for c in "*?["):
            for key in lowered_keys:
                if fnmatch.fnmatchcase(key, pat_l):
                    hits.append(pat)
                    break
        else:
            if pat_l in lowered_keys:
                hits.append(pat)
    return hits


def _score_profile(profile_id: str, profile: dict, resp) -> Optional[DetectionHit]:
    """Apply profile detectors to resp. Returns hit or None."""
    if profile_id.startswith("_"):
        return None
    detectors = profile.get("detectors") or {}
    if not detectors and profile_id != "unknown_challenge":
        return None

    cookies = _cookies_dict(resp)
    headers = _headers_dict(resp)
    body = (getattr(resp, "text", "") or "").lower()
    server = headers.get("server", "")

    signals: list[str] = []

    # Cookie detectors
    cookie_pats = detectors.get("cookie") or []
    for hit in _match_patterns(list(cookies.keys()), cookie_pats):
        signals.append(f"cookie:{hit}")

    # Header detectors
    header_pats = detectors.get("header") or []
    for hit in _match_patterns(list(headers.keys()), header_pats):
        signals.append(f"header:{hit}")

    # Server substring
    for needle in detectors.get("server_contains") or []:
        if needle.lower() in server:
            signals.append(f"server:{needle}")

    # Body markers
    for needle in detectors.get("body") or []:
        if needle.lower() in body:
            signals.append(f"body:{needle}")

    if not signals:
        return None

    rules = profile.get("confidence_rules") or {"strong": 2, "weak": 1}
    n = len(signals)
    if n >= rules.get("strong", 2):
        conf = 0.9
    elif n >= rules.get("weak", 1):
        conf = 0.6
    else:
        conf = 0.3

    return DetectionHit(profile_id=profile_id, confidence=conf, signals=signals)


def detect(resp, *, profiles: Optional[dict] = None, min_confidence: float = 0.0) -> list[DetectionHit]:
    """Return ranked list of detection hits (best first).

    When nothing fires, the returned list contains a single `unknown_challenge`
    hit with confidence 0.1 — caller can use its conservative settings.
    """
    if profiles is None:
        profiles = _load_profiles()

    hits: list[DetectionHit] = []
    for profile_id, profile in profiles.items():
        if profile_id.startswith("_"):
            continue
        h = _score_profile(profile_id, profile, resp)
        if h and h.confidence >= min_confidence:
            hits.append(h)

    hits.sort(key=lambda x: x.confidence, reverse=True)

    if not hits:
        hits.append(DetectionHit(
            profile_id="unknown_challenge",
            confidence=0.1,
            signals=["fallback"],
        ))
    return hits


def load_profile(profile_id: str, *, profiles: Optional[dict] = None) -> dict:
    """Get one profile by id, resolving `unknown_challenge` if missing."""
    if profiles is None:
        profiles = _load_profiles()
    return profiles.get(profile_id) or profiles.get("unknown_challenge") or {}


def _selftest() -> int:
    """Self-check. Fixtures are built from the REAL waf_profiles.yaml, so a
    drift in the profile file breaks this test instead of silently reducing
    detection quality. No network access."""
    import tempfile
    import os as _os

    checks: list[tuple[str, bool]] = []

    class _Cookie:
        def __init__(self, name, value=""):
            self.name = name
            self.value = value

    class _Jar:
        def __init__(self, names):
            self.jar = [_Cookie(n) for n in names]

    class _Resp:
        """Minimal curl_cffi-shaped response."""
        def __init__(self, cookies=(), headers=None, body=""):
            self.cookies = _Jar(list(cookies))
            self.headers = headers or {}
            self.text = body
            self.status_code = 200

    # --- Loader: real file present, profiles usable ---
    profiles = _load_profiles()
    checks.append(("real yaml loads without error", last_load_error() is None))
    checks.append(("yaml yields profiles", isinstance(profiles, dict) and len(profiles) >= 8))
    checks.append(("_meta is a key", "_meta" in profiles))

    # --- Two-way, per vendor: the real signal fires, a clean response does not ---
    # Each tuple: (profile_id, cookie, header, body) taken from waf_profiles.yaml.
    vendors = [
        ("akamai_bot_manager", "_abck", "X-Akamai-Session-Info", "", None),
        ("cloudflare_turnstile", "cf_clearance", "cf-ray", "", None),
        ("f5_big_ip", "BigIPServerPOOL", "", "The requested URL was rejected", None),
        ("aws_waf", "aws-waf-token", "", "", None),
        ("datadome_probable", "datadome", "", "", None),
        ("perimeterx_human", "_px3", "", "", None),
        ("kasada_ips", "", "x-kpsdk-ct", "", None),
        ("imperva_incapsula", "incap_ses_123", "x-iinfo", "", None),
    ]
    for pid, cookie, header, body, _ in vendors:
        prof = profiles.get(pid)
        if prof is None:
            checks.append((f"{pid} exists in profiles", False))
            continue
        det = prof.get("detectors") or {}
        # Prefer a cookie signal when the profile declares one, else a header.
        if det.get("cookie"):
            want = det["cookie"][0].replace("*", "suffix")
            r = _Resp(cookies=[want])
        elif det.get("header"):
            want = det["header"][0].replace("*", "suffix")
            r = _Resp(headers={want: "1"})
        else:
            want = det["body"][0]
            r = _Resp(body=want)
        hits = detect(r, profiles=profiles)
        top = hits[0]
        checks.append((f"{pid}: real signal detected", top.profile_id == pid))
        checks.append((f"{pid}: signal named", bool(top.signals)))

        # Negative direction: an unrelated response must NOT claim this vendor.
        clean = _Resp(cookies=["sessionid"], headers={"server": "nginx"},
                      body="<html>hello</html>")
        clean_hits = [h for h in detect(clean, profiles=profiles) if h.profile_id == pid]
        checks.append((f"{pid}: silent on clean response", clean_hits == []))

    # --- Wildcard matching: the point of fnmatch patterns ---
    r = _Resp(headers={"X-Akamai-Session-Info": "v"})
    akamai_hits = [h for h in detect(r, profiles=profiles) if h.profile_id == "akamai_bot_manager"]
    checks.append(("X-Akamai-* wildcard matches", len(akamai_hits) == 1))
    # A prefix that merely resembles the pattern must not match.
    r = _Resp(headers={"XAkamaiFoo": "v"})
    akamai_hits = [h for h in detect(r, profiles=profiles) if h.profile_id == "akamai_bot_manager"]
    checks.append(("wildcard needs the literal prefix", akamai_hits == []))

    # --- Confidence ladder from confidence_rules ---
    # akamai declares strong=2 / weak=1: one signal -> 0.6, two -> 0.9.
    one = _Resp(cookies=["_abck"])
    h1 = [h for h in detect(one, profiles=profiles) if h.profile_id == "akamai_bot_manager"]
    checks.append(("one akamai signal -> confidence 0.6",
                   bool(h1) and h1[0].confidence == 0.6))
    two = _Resp(cookies=["_abck", "bm_sz"])
    h2 = [h for h in detect(two, profiles=profiles) if h.profile_id == "akamai_bot_manager"]
    checks.append(("two akamai signals -> confidence 0.9",
                   bool(h2) and h2[0].confidence == 0.9))

    # --- Ranking: strongest first, and a mixed response names the right winner ---
    mixed = _Resp(cookies=["cf_clearance", "cf-ray"], headers={"server": "cloudflare"},
                  body="Just a moment...")
    hits = detect(mixed, profiles=profiles)
    checks.append(("mixed response ranks cloudflare first",
                   hits[0].profile_id == "cloudflare_turnstile"))
    checks.append(("ranking is descending",
                   all(hits[i].confidence >= hits[i + 1].confidence
                       for i in range(len(hits) - 1))))
    checks.append(("cloudflare confidence is 0.9 on three signals",
                   hits[0].confidence == 0.9))

    # A response carrying two vendors' marks must surface both, not pick one.
    both = _Resp(cookies=["_abck", "datadome"])
    ids = {h.profile_id for h in detect(both, profiles=profiles)}
    checks.append(("two vendors both reported", {"akamai_bot_manager",
                                                 "datadome_probable"} <= ids))

    # --- Unknown fallback: the contract callers rely on ---
    nothing = _Resp(cookies=["random"], headers={"server": "nginx"}, body="ok")
    fb = detect(nothing, profiles=profiles)
    checks.append(("clean response falls back to unknown_challenge",
                   len(fb) == 1 and fb[0].profile_id == "unknown_challenge"))
    checks.append(("fallback confidence is 0.1",
                   len(fb) == 1 and fb[0].confidence == 0.1))
    checks.append(("fallback is marked as such",
                   len(fb) == 1 and fb[0].signals == ["fallback"]))
    # detect() must NEVER return an empty list — callers index [0] directly.
    checks.append(("detect never returns an empty list",
                   len(detect(nothing, profiles=profiles)) >= 1))

    # unknown_challenge itself never wins on its own profile (detectors empty
    # and strong=0/weak=0 must not be read as an automatic hit).
    ids = {h.profile_id for h in detect(nothing, profiles=profiles)}
    checks.append(("empty-detector profile never self-fires",
                   ids == {"unknown_challenge"}))

    # --- min_confidence filter ---
    checks.append(("min_confidence 0.9 keeps only strong hits",
                   all(h.confidence >= 0.9 for h in detect(mixed, profiles=profiles,
                                                           min_confidence=0.9))))
    checks.append(("high min_confidence falls back rather than returning []",
                   len(detect(nothing, profiles=profiles, min_confidence=0.9)) == 1))

    # --- Security-relevant: _-prefixed keys must never be treated as profiles ---
    poisoned = dict(profiles)
    poisoned["_internal_note"] = {"detectors": {"cookie": ["anything"]},
                                  "confidence_rules": {"strong": 1, "weak": 1}}
    r = _Resp(cookies=["anything"])
    ids = {h.profile_id for h in detect(r, profiles=poisoned)}
    checks.append(("underscore keys skipped by detect", "_internal_note" not in ids))
    checks.append(("_score_profile refuses underscore ids",
                   _score_profile("_x", {"detectors": {"cookie": ["a"]}},
                                  _Resp(cookies=["a"])) is None))

    # --- Resilience: odd responses must not raise ---
    for label, resp in [
        ("no cookies/headers/text", _Resp()),
        ("headers as list of tuples", _Resp(headers=[("cf-ray", "x")])),
        ("cookie jar is a plain dict", type("R", (), {
            "cookies": {"cf_clearance": "1"}, "headers": {}, "text": "", "status_code": 200})()),
        ("bare object", object()),
    ]:
        try:
            detect(resp, profiles=profiles)
            checks.append((f"detect survives {label}", True))
        except Exception as e:
            checks.append((f"detect survives {label} ({type(e).__name__}: {e})", False))

    # --- Loader failure modes: degrade visibly, never raise ---
    bogus = _os.path.join(tempfile.mkdtemp(prefix="nxw-waf-"), "nope.yaml")
    got = _load_profiles(bogus)
    checks.append(("missing yaml returns the in-code default", got == _DEFAULT_PROFILES))
    checks.append(("missing yaml records a reason", "not found" in (last_load_error() or "")))

    bad_dir = tempfile.mkdtemp(prefix="nxw-waf-bad-")
    bad_path = _os.path.join(bad_dir, "broken.yaml")
    with open(bad_path, "w", encoding="utf-8") as fh:
        fh.write("key: [unclosed\n")
    got = _load_profiles(bad_path)
    checks.append(("unparseable yaml returns the default", got == _DEFAULT_PROFILES))
    checks.append(("unparseable yaml records a reason",
                   "parse error" in (last_load_error() or "").lower()))

    empty_path = _os.path.join(bad_dir, "empty.yaml")
    with open(empty_path, "w", encoding="utf-8") as fh:
        fh.write("_meta:\n  note: nothing here\n")
    got = _load_profiles(empty_path)
    checks.append(("underscore-only yaml returns the default", got == _DEFAULT_PROFILES))
    checks.append(("underscore-only yaml records a reason",
                   "no usable profiles" in (last_load_error() or "")))

    # The default profile must still be detectable-with-safely (fallback path).
    got = _load_profiles(bogus)
    fb = detect(_Resp(body="whatever"), profiles=got)
    checks.append(("default profile still yields a fallback",
                   bool(fb) and fb[0].profile_id == "unknown_challenge"))

    # A clean load must CLEAR a previous error (no sticky false alarm).
    _load_profiles(bogus)
    checks.append(("error was set by the bad load", last_load_error() is not None))
    _load_profiles(PROFILES_PATH)
    checks.append(("successful load clears the error", last_load_error() is None))

    # --- load_profile resolution ---
    checks.append(("load_profile finds a real vendor",
                   bool(load_profile("cloudflare_turnstile",
                                     profiles=profiles).get("detectors"))))
    unknown = load_profile("does_not_exist", profiles=profiles)
    checks.append(("load_profile resolves unknown to the default",
                   unknown == profiles.get("unknown_challenge")))
    checks.append(("load_profile on empty profiles returns {}",
                   load_profile("x", profiles={}) == {}))

    # --- No-Site-Name Rule: the profile file may not branch on hostnames ---
    raw = open(PROFILES_PATH, encoding="utf-8").read().lower()
    hostnames = [h for h in ("google.com", "facebook.com", "twitter.com",
                             "amazon.com", "microsoft.com") if h in raw]
    checks.append(("profile file carries no site names", hostnames == []))

    failed = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {n}")
    if failed:
        print(f"[!] waf_detector selftest: {len(failed)}/{len(checks)} failed: {failed}")
        return 1
    print(f"[+] waf_detector selftest: {len(checks)}/{len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
