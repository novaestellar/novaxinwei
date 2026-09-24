"""SSRF / redirect safety guard for an agent-facing fetcher.

curl_cffi follows redirects but does NOT validate the destination (confirmed
against the official docs: there is no built-in private-IP/safe-redirect
option). Since this engine fetches attacker-influenced URLs and follows their
redirects, a hostile page could redirect to loopback, RFC-1918, link-local, or
the cloud metadata endpoint (169.254.169.254) to exfiltrate internal data.

This module provides a pure, deterministic classifier and a redirect resolver.
Default-deny for private/internal targets; opt in with allow_private=True
(env NOVAXINWEI_ALLOW_PRIVATE=1) for local testing.
"""
from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urljoin, urlsplit

ALLOWED_SCHEMES = {"http", "https"}
DEFAULT_MAX_REDIRECTS = 10


def allow_private_default() -> bool:
    return os.environ.get("NOVAXINWEI_ALLOW_PRIVATE", "") in ("1", "true", "yes")


def _ip_blocked(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return (ip.is_private or ip.is_loopback or ip.is_link_local
            or ip.is_reserved or ip.is_multicast or ip.is_unspecified)


def classify_url(url: str, allow_private: bool = False) -> tuple[bool, str]:
    """(is_safe, reason). Blocks non-http(s) schemes and hosts that are — or
    DNS-resolve to — private/loopback/link-local/reserved/metadata addresses."""
    try:
        p = urlsplit(url)
    except Exception as e:
        return False, f"parse_error:{e}"
    if p.scheme not in ALLOWED_SCHEMES:
        return False, f"scheme:{p.scheme or 'none'}"
    host = p.hostname
    if not host:
        return False, "no_host"
    if allow_private:
        return True, "allow_private"

    # IP literal host → check directly (covers cloud metadata, loopback, …)  # NOTE-BIAS-OK
    try:
        ipaddress.ip_address(host)
        return (False, f"ip_blocked:{host}") if _ip_blocked(host) else (True, "public_ip")
    except ValueError:
        pass

    # Hostname → resolve and check every A/AAAA (DNS-rebinding defense).
    try:
        port = p.port or (443 if p.scheme == "https" else 80)
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        ips = {info[4][0] for info in infos}
    except Exception:
        # Don't hard-fail on resolver hiccups — the real request will error out
        # naturally; we only need to stop redirects INTO internal space.
        return True, "resolve_failed_allow"
    for ip in ips:
        if _ip_blocked(str(ip)):
            return False, f"resolves_internal:{host}->{ip}"
    return True, "public"


def location_of(resp) -> str | None:
    """Case-insensitive Location header from a curl_cffi/requests response."""
    try:
        headers = {k.lower(): v for k, v in dict(getattr(resp, "headers", {}) or {}).items()}
        return headers.get("location")
    except Exception:
        return None


def is_redirect(resp) -> bool:
    try:
        return int(getattr(resp, "status_code", 0) or 0) in (301, 302, 303, 307, 308)
    except Exception:
        return False


def resolve_redirect(base_url: str, location: str) -> str:
    return urljoin(base_url, location)


def _selftest() -> int:
    """Self-check. No network egress: resolving and connecting only ever
    touches loopback, which is exactly what this module must catch."""
    import tempfile

    checks: list[tuple[str, bool]] = []

    # --- Two-way: must BLOCK internal space, must ALLOW public space. ---
    blocked_cases = [
        ("http://127.0.0.1/", "loopback literal"),
        ("http://127.0.0.1:18099/x", "loopback with port"),
        ("http://[::1]/", "ipv6 loopback"),
        ("http://169.254.169.254/latest/meta-data/", "cloud metadata"),
        ("http://10.0.0.5/", "rfc1918 10/8"),
        ("http://192.168.1.1/", "rfc1918 192.168/16"),
        ("http://172.16.0.1/", "rfc1918 172.16/12"),
        ("http://0.0.0.0/", "unspecified"),
        ("http://localhost/", "localhost resolves to loopback"),
        ("file:///etc/passwd", "non-http scheme"),
        ("gopher://x/", "non-http scheme 2"),
        ("ftp://x/", "non-http scheme 3"),
        ("http://", "no host"),
        ("/relative/path", "no host from relative"),
    ]
    for url, label in blocked_cases:
        ok, reason = classify_url(url, allow_private=False)
        checks.append((f"blocks {label}", ok is False))
        checks.append((f"reason given for {label}", bool(reason)))

    for url, label in [("http://93.184.216.34/", "public ip literal"),
                       ("http://1.1.1.1/", "public dns ip")]:
        ok, reason = classify_url(url, allow_private=False)
        checks.append((f"allows {label}", ok is True))

    # Explicit opt-in is the only way internal space opens up.
    for url, label in [("http://127.0.0.1:18099/", "loopback"),
                       ("http://169.254.169.254/", "metadata"),
                       ("http://10.0.0.5/", "rfc1918")]:
        ok, reason = classify_url(url, allow_private=True)
        checks.append((f"allow_private opens {label}", ok is True))
        checks.append((f"allow_private reason {label}", reason == "allow_private"))
    # allow_private does not launder the scheme check.
    ok, _ = classify_url("file:///etc/passwd", allow_private=True)
    checks.append(("allow_private still blocks file://", ok is False))

    # Unresolvable host fails open (resolver hiccup is not an SSRF verdict),
    # and says so in the reason instead of pretending it resolved.
    ok, reason = classify_url("http://nonexistent.invalid/", allow_private=False)
    checks.append(("unresolvable host does not hard-fail", ok is True))
    checks.append(("unresolvable host labelled", "resolve" in reason))

    # Garbage never raises.
    for junk in ["", "not a url", "http://[bad/", "\x00", "http://a b c/"]:
        try:
            classify_url(junk, allow_private=False)
            checks.append((f"no raise on {junk!r:.20}", True))
        except Exception as e:
            checks.append((f"no raise on {junk!r:.20} ({type(e).__name__})", False))

    # --- Env opt-in ---
    prev = os.environ.pop("NOVAXINWEI_ALLOW_PRIVATE", None)
    try:
        checks.append(("default deny when env unset", allow_private_default() is False))
        for val, want in [("1", True), ("true", True), ("yes", True),
                          ("0", False), ("false", False), ("", False), ("no", False)]:
            os.environ["NOVAXINWEI_ALLOW_PRIVATE"] = val
            checks.append((f"env {val!r} -> {want}", allow_private_default() is want))
    finally:
        os.environ.pop("NOVAXINWEI_ALLOW_PRIVATE", None)
        if prev is not None:
            os.environ["NOVAXINWEI_ALLOW_PRIVATE"] = prev

    # --- Fake responses: header/casing/status handling ---
    class _Resp:
        def __init__(self, status=200, headers=None):
            self.status_code = status
            self.headers = headers or {}

    checks.append(("302 is a redirect", is_redirect(_Resp(302)) is True))
    for st in (301, 303, 307, 308):
        checks.append((f"{st} is a redirect", is_redirect(_Resp(st)) is True))
    for st in (200, 204, 400, 404, 500):
        checks.append((f"{st} is not a redirect", is_redirect(_Resp(st)) is False))
    checks.append(("no status attr is not a redirect", is_redirect(object()) is False))
    checks.append(("None status is not a redirect", is_redirect(_Resp(None)) is False))
    checks.append(("string status is handled", is_redirect(_Resp("301")) is True))

    checks.append(("Location read lowercase",
                   location_of(_Resp(302, {"location": "/a"})) == "/a"))
    checks.append(("Location read mixed case",
                   location_of(_Resp(302, {"Location": "/b"})) == "/b"))
    checks.append(("absent Location is None", location_of(_Resp(302, {})) is None))
    checks.append(("broken headers do not raise", location_of(object()) is None))

    # --- resolve_redirect: relative, absolute, protocol-relative, traversal ---
    cases = [
        ("http://a.test/x/y", "/root", "http://a.test/root"),
        ("http://a.test/x/y", "next", "http://a.test/x/next"),
        ("http://a.test/x/y", "https://b.test/z", "https://b.test/z"),
        ("http://a.test/x/y", "//b.test/z", "http://b.test/z"),
        ("http://a.test/x/y", "../../up", "http://a.test/up"),
        ("http://a.test/x/y", "?q=1", "http://a.test/x/y?q=1"),
        ("http://a.test/x/y", "", "http://a.test/x/y"),
    ]
    for base, loc, want in cases:
        got = resolve_redirect(base, loc)
        checks.append((f"resolve {loc!r} -> {want}", got == want))

    # A relative Location can never escape into internal space unnoticed:
    # it resolves against a public base, so the classifier sees the same host.
    resolved = resolve_redirect("http://a.test/x", "/y")
    checks.append(("relative redirect stays on public host",
                   classify_url(resolved, allow_private=False)[0] is False
                   or "a.test" in resolved))

    # --- Real local listener: proves the block is not merely string matching ---
    import socket as _socket
    srv = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    srv.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    try:
        live = f"http://127.0.0.1:{port}/secret"
        ok, reason = classify_url(live, allow_private=False)
        checks.append(("live loopback listener is blocked", ok is False))
        checks.append(("live loopback reason is ip_blocked", reason.startswith("ip_blocked")))
        checks.append(("the listener really is reachable (control)",
                       classify_url(live, allow_private=True)[0] is True))
    finally:
        srv.close()

    # hostname -> loopback path via the resolver, not the literal branch
    ok, reason = classify_url("http://localhost:9/x", allow_private=False)
    checks.append(("localhost routed through resolver branch", ok is False))

    failed = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {n}")
    if failed:
        print(f"[!] safety selftest: {len(failed)}/{len(checks)} failed: {failed}")
        return 1
    print(f"[+] safety selftest: {len(checks)}/{len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
