"""Redact secret-bearing parts of URLs before they reach logs or stdout.

The 2026-09-03 credential sweep found zero real leaks in the engine's own
artifacts, but three sinks print request URLs verbatim: the ``--trace`` attempt
log, the observations jsonl, and the ``source_url`` header on wrapped content.
A URL that arrives carrying a token in its query string would land in all
three. Masking values while keeping parameter names leaves those records
diagnosable without recording the secret itself.

Scope is deliberately narrow (owner decision 2026-09-04): mask URLs at the
output boundary only. No general-purpose scrub utility, no changes to what the
fetch chain sends over the wire.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

REDACTED = "REDACTED"

# Matched against the parameter name. Each name is a WHOLE TOKEN: it must sit at
# the start or end of the name, or be delimited by ``-`` / ``_``. That is what
# separates a real secret from an innocent name that merely contains one —
# ``access_token`` and ``X-Auth-Token`` still match, while ``tokens_count``,
# ``authorname``, ``passwordless`` and ``sessionnotes`` do not. Substring
# matching was the earlier behaviour and redacted those innocent names, which
# destroyed the diagnosability the log exists to provide.
_SENSITIVE_NAMES = frozenset({
    "token", "secret", "password", "passwd", "credential", "signature",
    "bearer", "session", "auth", "sig", "key", "pwd", "sid", "access",
    "refresh", "sessionid", "authorization", "authorisation", "apikey",
    "accesskey",
})
# ``code`` and ``state`` are ordinary English words that also appear inside
# innocent names (``country_code``, ``code_name``, ``stateful``). Unlike the
# names above they are only a secret when they TRAIL a recognised secret
# prefix (``auth_code``, ``oauth_state``), so they are matched as a
# suffix against the whole normalised name rather than as a free-standing piece.
_SENSITIVE_TRAILING = ("code", "state")


def _is_sensitive(name: str) -> bool:
    """True when ``name`` carries a whole-token secret marker.

    The name is split on ``-`` / ``_`` and every piece is compared to the
    marker list as a WHOLE word. That is what keeps a real secret
    (``access_token``, ``X-Auth-Token`` -> ``token``) while letting an innocent
    name through (``tokens_count`` -> ``tokens``/``count``; ``authorname`` ->
    one piece that is not ``auth``). Substring matching was the earlier
    behaviour: it redacted those innocent names and the trace stopped
    explaining itself.

    ``code`` / ``state`` are matched only as a trailing suffix, because on
    their own they are ordinary words (``country_code`` is a country, not a
    credential) while trailing a secret prefix they are not (``auth_code``).
    """
    if not name:
        return False
    lowered = name.lower()
    pieces = re.split(r"[-_]", lowered)
    for piece in pieces:
        if piece in _SENSITIVE_NAMES:
            return True
    # ``api_key`` arrives as two pieces; the joined form is a marker itself.
    if "".join(pieces) in _SENSITIVE_NAMES:
        return True
    # ``auth_code`` / ``oauth_state``: a trailing word is a secret only when a
    # secret prefix sits in front of it. Without that check ``country_code``
    # would be redacted (``code`` as the last piece) which is the very
    # over-redaction this fix removes.
    if pieces[-1] in _SENSITIVE_TRAILING and len(pieces) > 1:
        prefix = "".join(pieces[:-1])
        if any(p in _SENSITIVE_NAMES for p in pieces[:-1]):
            return True
        if prefix.endswith(("auth", "oauth")) or prefix in _SENSITIVE_NAMES:
            return True
    return False


def _mask_query(query: str) -> str:
    if not query:
        return query
    pairs = parse_qsl(query, keep_blank_values=True)
    masked = [
        (name, REDACTED if value and _is_sensitive(name) else value)
        for name, value in pairs
    ]
    if masked == pairs:
        # Nothing to hide. Return the original text rather than the re-encoded
        # round trip, so a query we parsed loosely (or not at all) is never
        # silently reshaped by logging.
        return query
    return urlencode(masked)


def mask_url(url: str) -> str:
    """Return ``url`` with credential-shaped values replaced by ``REDACTED``.

    Masks sensitive query-parameter values and any ``user:pass@`` userinfo.
    Host, path and non-sensitive parameters survive untouched so the result
    still identifies the request. Never raises: an unparseable URL is returned
    as-is, because logging must not change a fetch outcome.
    """
    if not url or "?" not in url and "@" not in url:
        return url
    try:
        parts = urlsplit(url)
    except ValueError:
        return url

    netloc = parts.netloc
    if "@" in netloc:
        _, _, host = netloc.rpartition("@")
        netloc = f"{REDACTED}@{host}"

    return urlunsplit(
        (parts.scheme, netloc, parts.path, _mask_query(parts.query), parts.fragment)
    )


def _selftest() -> int:
    """Self-check on the redaction boundary. Pure string work, no network.

    Two directions, both mandatory: every credential shape must be masked
    (no leak), and every harmless parameter must survive (no over-redaction
    that destroys diagnosability)."""
    checks: list[tuple[str, bool]] = []

    # --- Direction A: secrets MUST be masked ---
    # Bare ``code`` / ``state`` are deliberately absent, and ``country_code``
    # proves why: no name-based rule separates a country code from an OAuth
    # code. Owner decision 2026-09-24. Prefixed forms are covered further down.
    secret_params = [
        "token", "access_token", "api_key", "apikey", "api-key",
        "secret", "client_secret", "password", "passwd", "pwd",
        "credential", "signature", "bearer", "session", "sessionid",
        "auth", "authorization", "access_key", "sig", "key", "sid",
        "access", "refresh",
    ]
    for name in secret_params:
        out = mask_url(f"https://a.test/p?{name}=SUPERSECRETVALUE")
        ok = "SUPERSECRETVALUE" not in out and REDACTED in out
        checks.append((f"masks {name}", ok))

    # Case-insensitivity: a scanner or a caller may send any casing.
    for name in ["TOKEN", "Access_Token", "API_KEY", "PassWord", "SIG"]:
        out = mask_url(f"https://a.test/p?{name}=SUPERSECRETVALUE")
        checks.append((f"masks {name} (case)", "SUPERSECRETVALUE" not in out))

    # Param name is preserved so the record stays diagnosable.
    out = mask_url("https://a.test/p?token=abc123")
    checks.append(("parameter name survives", "token=" in out))
    checks.append(("value replaced", out.endswith("token=" + REDACTED)))

    # Multiple secrets in one query — all must go.
    out = mask_url("https://a.test/p?token=aaa&api_key=bbb&secret=ccc")
    checks.append(("masks every secret in a multi-secret query",
                   all(s not in out for s in ("aaa", "bbb", "ccc"))))

    # Mixed: one secret, one harmless param. Both must land correctly.
    out = mask_url("https://a.test/p?token=SECRETVAL&page=7")
    checks.append(("mixed query hides the secret", "SECRETVAL" not in out))
    checks.append(("mixed query keeps the innocuous param", "page=7" in out))

    # --- userinfo: user:pass@ must never survive ---
    out = mask_url("https://user:hunter2@a.test/p")
    checks.append(("masks userinfo password", "hunter2" not in out))
    checks.append(("userinfo host survives", "a.test" in out))
    checks.append(("userinfo marked redacted", REDACTED in out))
    out = mask_url("https://onlyuser@a.test/p")
    checks.append(("bare userinfo is redacted too", "onlyuser" not in out))

    # --- Direction B: harmless input MUST survive byte-identical ---
    harmless = [
        "https://a.test/p",
        "https://a.test/p?a=1&b=2",
        "https://a.test/",
        "https://a.test",
        "https://a.test/p#frag",
        "https://a.test/deep/path/with/many/segments",
    ]
    for url in harmless:
        checks.append((f"untouched {url[8:34]!r}", mask_url(url) == url))

    # Lookalikes: these contain sensitive SUBSTRINGS but are not secrets. This is
    # the over-redaction guard the whole-token split exists for.
    # ``signature_help`` / ``auth_help`` are deliberately NOT here: under the
    # chosen (b) semantics ``signature`` and ``auth`` are whole secret words,
    # so those two legitimately stay redacted.
    lookalikes = [
        "authorname", "secretofquality", "passwordless", "sessionnotes",
        "tokens_count", "keyword", "country_code", "code_name", "keyboard",
        "stateful", "my_tokens", "notakey",
    ]
    for name in lookalikes:
        url = f"https://a.test/p?{name}=harmlessvalue"
        out = mask_url(url)
        checks.append((f"does NOT over-redact {name}", "harmlessvalue" in out))

    # Bare ``code`` / ``state`` are NO LONGER masked (owner decision 2026-09-24):
    # they are indistinguishable by name from ``country_code``, so masking them
    # meant redacting country names. The residual — an OAuth ``?code=`` reaching
    # the log — is accepted and recorded here so the trade-off is explicit.
    checks.append(("'state' exact survives (accepted residual)",
                   "V" in mask_url("https://a.test/p?state=V")))
    checks.append(("'code' exact survives (accepted residual)",
                   "V" in mask_url("https://a.test/p?code=V")))
    # ...but a secret prefix re-enables it, which is the guard that keeps
    # ``auth_code`` / ``oauth_state`` masked.
    checks.append(("'auth_code' IS masked", "V" not in mask_url("https://a.test/p?auth_code=V")))
    checks.append(("'oauth_state' IS masked", "V" not in mask_url("https://a.test/p?oauth_state=V")))
    checks.append(("'country_code' is not masked",
                   "ID" in mask_url("https://a.test/p?country_code=ID")))
    checks.append(("'stateful' is not masked",
                   "V" in mask_url("https://a.test/p?stateful=V")))

    # --- Never raises, never mangles ---
    for junk in ["", "not a url", "https://", "://x", "https://a.test/p?a=1&b",
                 "\x00", "https://a.test/p?" ]:
        try:
            mask_url(junk)
            checks.append((f"no raise on {junk!r:.22}", True))
        except Exception as e:
            checks.append((f"no raise on {junk!r:.22} ({type(e).__name__})", False))

    # Empty URL and URL without query/userinfo return identical object value
    # fast-path (the guard exists so ordinary logging is untouched).
    for url in ["", "https://a.test/plain"]:
        checks.append((f"fast path returns input unchanged {url[:24]!r}",
                       mask_url(url) == url))

    # Empty secret VALUE: nothing to hide, and the param must not be invented.
    out = mask_url("https://a.test/p?token=")
    checks.append(("empty secret value is left as an empty value",
                   "token=" in out and REDACTED not in out))

    # A secret with a blank value alongside a real secret: only the real one goes.
    out = mask_url("https://a.test/p?token=REAL&key=")
    checks.append(("blank value not replaced, real one is",
                   "REAL" not in out and "key=" in out))

    # Encoding round-trip: an encoded secret must not slip through unencoded.
    out = mask_url("https://a.test/p?token=%41%42%43")
    checks.append(("percent-encoded secret is masked", "%41%42%43" not in out))

    # Repeated same-name params are all masked (parse_qsl keeps duplicates).
    out = mask_url("https://a.test/p?token=one&token=two")
    checks.append(("duplicate param both masked",
                   "one" not in out and "two" not in out))

    # Fragment and path are NOT scrubbed (scope decision: output boundary only
    # covers query + userinfo). Documented here so the limit is explicit.
    out = mask_url("https://a.test/token=abc?x=1")
    checks.append(("path is intentionally out of scope", "token=abc" in out))

    # Matcher sanity: the whole-token rule behaves as the docstring claims.
    # The list is deliberately ordered secrets-first, then the lookalikes that
    # must now survive (this is the BUG-21 fix under test).
    matcher_cases = [
        # real secrets — must match
        ("token", True), ("access_token", True), ("X-Auth-Token", True),
        ("api-key", True), ("apikey", True), ("API_KEY", True),
        ("client_secret", True), ("signature", True), ("auth", True),
        ("session", True), ("sid", True), ("access_key", True),
        ("sessionid", True), ("authorization", True), ("auth_code", True),
        ("oauth_state", True),
        # bare ``code`` / ``state`` DO NOT match: they are ordinary words whose
        # secret meaning cannot be told apart from ``country_code`` by name
        # alone. Owner decision 2026-09-24: keep them out, accept the residual
        # (an OAuth ``?code=`` in a URL will reach the log). Documented so the
        # trade-off stays visible instead of looking like an oversight.
        ("code", False), ("state", False),
        # innocent names — must NOT match (the 7 from BUG-21, plus anchors).
        # ``signature_help`` and ``auth_help`` legitimately DO match under the
        # chosen (b) semantics: ``signature`` / ``auth`` are whole secret words.
        ("authorname", False), ("secretofquality", False),
        ("passwordless", False), ("sessionnotes", False), ("tokens_count", False),
        ("keyword", False), ("country_code", False),
        ("stateful", False), ("code_name", False), ("keyboard", False),
        ("my_tokens", False), ("notakey", False),
    ]
    for name, want in matcher_cases:
        got = _is_sensitive(name)
        checks.append((f"_is_sensitive({name!r}) == {want}", got is want))

    # Multi-marker names must still be caught (whole-token split, no overlap
    # trickery needed): every delimiter-separated piece is compared.
    for name in ["api_key_token", "token_key", "auth_key_secret",
                 "X-Api-Key", "my_access_token", "session_sig"]:
        checks.append((f"multi-marker {name!r} is caught", _is_sensitive(name) is True))

    # Normalisation: case and delimiter style must not change the verdict.
    for a, b in [("TOKEN", "token"), ("Access-Token", "access_token"),
                 ("API_KEY", "api-key"), ("SIG", "sig")]:
        checks.append((f"{a!r} and {b!r} agree", _is_sensitive(a) == _is_sensitive(b)))

    # Empty / odd input never raises and never claims a secret.
    for junk in ["", "-", "_", "---", "__", "a", "?", "%20"]:
        checks.append((f"no false positive on {junk!r}", _is_sensitive(junk) is False))


    failed = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {n}")
    if failed:
        print(f"[!] url_masking selftest: {len(failed)}/{len(checks)} failed: {failed}")
        return 1
    print(f"[+] url_masking selftest: {len(checks)}/{len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
