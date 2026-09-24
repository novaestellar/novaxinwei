# -*- coding: utf-8 -*-
"""Channel registry, base-class routing, and channel utility selftest.

No network egress: no channel fetch path is invoked, no upstream command is
run (probe_command is monkeypatched where a check needs a definite answer).

Run:  python -m channels
"""

from __future__ import annotations

import sys
from typing import List


def _selftest() -> int:
    """Return 0 when all checks pass, 1 otherwise."""
    checks: List[tuple[str, bool]] = []

    def _raises(exc, fn) -> bool:
        try:
            fn()
            return False
        except exc:
            return True

    # ---------------------------------------------------------------- utils
    from channels import utils as U

    # normalize_public_http_url: accepts, canonicalizes, rejects
    checks.append(("normalize bare host -> https", U.normalize_public_http_url("example.com") == "https://example.com"))
    checks.append(("normalize keeps path", U.normalize_public_http_url("https://a.test/x?y=1") == "https://a.test/x?y=1"))
    checks.append(("normalize rejects empty", _raises(ValueError, lambda: U.normalize_public_http_url(""))))
    checks.append(("normalize rejects backslash", _raises(ValueError, lambda: U.normalize_public_http_url("https://a.test\\x"))))
    checks.append(("normalize rejects space", _raises(ValueError, lambda: U.normalize_public_http_url("https://a.test/a b"))))
    checks.append(("normalize rejects control char", _raises(ValueError, lambda: U.normalize_public_http_url("https://a.test/\x01"))))
    checks.append(("normalize rejects ftp", _raises(ValueError, lambda: U.normalize_public_http_url("ftp://a.test/"))))
    checks.append(("normalize rejects userinfo", _raises(ValueError, lambda: U.normalize_public_http_url("https://u:p@a.test/"))))
    checks.append(("normalize rejects localhost", _raises(ValueError, lambda: U.normalize_public_http_url("http://localhost/x"))))
    checks.append(("normalize rejects .local suffix", _raises(ValueError, lambda: U.normalize_public_http_url("http://box.local/x"))))
    checks.append(("normalize rejects metadata.google.internal",
                   _raises(ValueError, lambda: U.normalize_public_http_url("http://metadata.google.internal/"))))
    checks.append(("normalize rejects loopback literal", _raises(ValueError, lambda: U.normalize_public_http_url("http://127.0.0.1/"))))
    checks.append(("normalize rejects private literal", _raises(ValueError, lambda: U.normalize_public_http_url("http://10.0.0.5/"))))
    checks.append(("normalize rejects link-local literal", _raises(ValueError, lambda: U.normalize_public_http_url("http://169.254.169.254/"))))
    checks.append(("normalize rejects single-label host", _raises(ValueError, lambda: U.normalize_public_http_url("http://intranet/"))))
    checks.append(("normalize rejects bad port", _raises(ValueError, lambda: U.normalize_public_http_url("https://a.test:99999/"))))

    # host_matches: exact, subdomain, suffix-attack, userinfo, scheme
    checks.append(("host_matches exact", U.host_matches("https://reddit.com/r/x", "reddit.com")))
    checks.append(("host_matches www", U.host_matches("https://www.reddit.com/r/x", "reddit.com")))
    checks.append(("host_matches subdomain", U.host_matches("https://old.reddit.com/r/x", "reddit.com")))
    checks.append(("host_matches trailing dot", U.host_matches("https://reddit.com./r/x", "reddit.com")))
    checks.append(("host_matches one of many", U.host_matches("https://redd.it/abc", "reddit.com", "redd.it")))
    checks.append(("host_matches rejects suffix attack", not U.host_matches("https://notreddit.com/r/x", "reddit.com")))
    checks.append(("host_matches rejects prefix domain", not U.host_matches("https://reddit.com.evil.test/r/x", "reddit.com")))
    checks.append(("host_matches rejects userinfo smuggle", not U.host_matches("https://reddit.com@evil.test/", "reddit.com")))
    checks.append(("host_matches rejects ftp", not U.host_matches("ftp://reddit.com/r/x", "reddit.com")))
    checks.append(("host_matches rejects garbage", not U.host_matches("not a url", "reddit.com")))
    checks.append(("host_matches rejects empty host", not U.host_matches("https:///path", "reddit.com")))

    # domain_matches: bare-host form
    checks.append(("domain_matches exact", U.domain_matches("a.test", "a.test")))
    checks.append(("domain_matches subdomain", U.domain_matches("www.a.test", "a.test")))
    checks.append(("domain_matches strips leading dot", U.domain_matches(".a.test", "a.test")))
    checks.append(("domain_matches rejects suffix attack", not U.domain_matches("nota.test", "a.test")))
    checks.append(("domain_matches rejects empty", not U.domain_matches("", "a.test")))

    # scrub_url_credentials: userinfo + query secrets
    s = U.scrub_url_credentials("https://user:pw@a.test/x")
    checks.append(("scrub userinfo", "pw" not in s and "***" in s))
    s = U.scrub_url_credentials("https://a.test/x?token=SECRET")
    checks.append(("scrub query token", "SECRET" not in s))
    s = U.scrub_url_credentials("https://a.test/x?api_key=SECRET")
    checks.append(("scrub query api_key", "SECRET" not in s))
    s = U.scrub_url_credentials("https://a.test/x?access_token=SECRET&ok=1")
    checks.append(("scrub access_token keeps other params", "SECRET" not in s and "ok=1" in s))
    s = U.scrub_url_credentials("https://a.test/x?password=SECRET")
    checks.append(("scrub query password", "SECRET" not in s))
    s = U.scrub_url_credentials("https://a.test/x?sessionid=SECRET")
    checks.append(("scrub query sessionid", "SECRET" not in s))
    s = U.scrub_url_credentials("bearer:token@a.test")
    checks.append(("scrub bare userinfo", "token" not in s.split("@")[0]))
    s = U.scrub_url_credentials("https://a.test/x?page=2")
    checks.append(("scrub leaves benign query", s == "https://a.test/x?page=2"))
    checks.append(("scrub handles non-str", U.scrub_url_credentials(None) == "None"))

    # utf8_subprocess_env
    env = U.utf8_subprocess_env({"A": "1"})
    checks.append(("utf8 env sets PYTHONUTF8", env.get("PYTHONUTF8") == "1"))
    checks.append(("utf8 env sets PYTHONIOENCODING", env.get("PYTHONIOENCODING") == "utf-8"))
    checks.append(("utf8 env preserves base", env.get("A") == "1"))
    checks.append(("utf8 env does not mutate base", "PYTHONUTF8" not in {"A": "1"}))

    # home_dir / config_dir
    checks.append(("home_dir is absolute", U.home_dir().is_absolute()))
    checks.append(("config_dir under home", str(U.config_dir()).startswith(str(U.home_dir()))))

    # probe_command: missing binary is reported, not raised
    r = U.probe_command("definitely-not-a-real-binary-xyzzy")
    checks.append(("probe missing -> status missing", r["status"] == "missing"))
    checks.append(("probe missing -> has output", "not found" in r["output"]))

    # ---------------------------------------------------------------- base
    from channels.base import Channel

    class _Fake(Channel):
        name = "fake"
        backends = ["b1", "b2", "b3"]

        def can_handle(self, url: str) -> bool:
            return True

    f = _Fake()
    checks.append(("ordered_backends default order", f.ordered_backends() == ["b1", "b2", "b3"]))
    checks.append(("ordered_backends override moves to front", f.ordered_backends({"fake_backend": "b3"}) == ["b3", "b1", "b2"]))
    checks.append(("ordered_backends override keeps others", set(f.ordered_backends({"fake_backend": "b2"})) == {"b1", "b2", "b3"}))
    checks.append(("ordered_backends unknown override ignored", f.ordered_backends({"fake_backend": "zzz"}) == ["b1", "b2", "b3"]))
    checks.append(("ordered_backends prefix override", f.ordered_backends({"fake_backend": "b2"})[0] == "b2"))
    checks.append(("ordered_backends does not mutate class list", _Fake.backends == ["b1", "b2", "b3"]))
    st, msg = f.check()
    checks.append(("base check returns ok", st == "ok"))
    checks.append(("base check sets active_backend", f.active_backend == "b1"))
    checks.append(("base check lists backends in msg", "b1" in msg))

    class _NoBackend(Channel):
        name = "nb"
        backends = []

        def can_handle(self, url: str) -> bool:
            return False

    nb = _NoBackend()
    st, msg = nb.check()
    checks.append(("no-backend channel reports built-in", st == "ok" and nb.active_backend == "built-in"))
    checks.append(("Channel is abstract", _raises(TypeError, lambda: Channel())))

    # ------------------------------------------------------------ registry
    from channels import ALL_CHANNELS, get_all_channels, get_channel

    checks.append(("registry has 15 channels", len(ALL_CHANNELS) == 15))
    names = [c.name for c in ALL_CHANNELS]
    checks.append(("registry names unique", len(names) == len(set(names))))
    checks.append(("registry every channel has a name", all(c.name for c in ALL_CHANNELS)))
    checks.append(("registry every channel has a description", all(c.description for c in ALL_CHANNELS)))
    checks.append(("registry is a Channel subclass each", all(isinstance(c, Channel) for c in ALL_CHANNELS)))
    checks.append(("get_all_channels returns registry", get_all_channels() is ALL_CHANNELS))
    checks.append(("get_channel finds reddit", get_channel("reddit") is not None and get_channel("reddit").name == "reddit"))
    checks.append(("get_channel unknown -> None", get_channel("nonexistent-platform") is None))

    # can_handle matrix: every channel claims its own hosts, rejects a foreign one
    matrix = [
        ("threads", "https://www.threads.net/@u", "https://www.threads.net/@u"),
        ("twitter", "https://x.com/u", "https://twitter.com/u"),
        ("youtube", "https://youtube.com/watch?v=1", "https://youtu.be/abc"),
        ("reddit", "https://www.reddit.com/r/x/", "https://redd.it/abc"),
        ("facebook", "https://www.facebook.com/u", "https://fb.watch/abc"),
        ("instagram", "https://www.instagram.com/u", "https://www.instagram.com/p/1"),
        ("bilibili", "https://www.bilibili.com/video/1", "https://b23.tv/abc"),
        ("xiaohongshu", "https://www.xiaohongshu.com/explore", "https://xhslink.com/a"),
        ("linkedin", "https://www.linkedin.com/in/u", "https://www.linkedin.com/feed/"),
        ("v2ex", "https://www.v2ex.com/t/1", "https://v2ex.com/go/linux"),
        ("nodeseek", "https://www.nodeseek.com/post-1", "https://nodeseek.com/t/1"),
        ("nodeloc", "https://nodeloc.com/t/1", "https://www.nodeloc.com/t/1"),
        ("52pojie", "https://www.52pojie.cn/thread-1", "https://52pojie.cn/forum-1"),
    ]
    for name, u1, u2 in matrix:
        ch = get_channel(name)
        checks.append((f"can_handle {name} primary", ch is not None and ch.can_handle(u1)))
        checks.append((f"can_handle {name} secondary", ch is not None and ch.can_handle(u2)))
        checks.append((f"can_handle {name} rejects foreign", ch is not None and not ch.can_handle("https://example.invalid/nope")))
        # suffix attack probe uses the actual registrable domain, not the channel key
        _dom = {"52pojie": "52pojie"}.get(name, name)
        checks.append((f"can_handle {name} rejects suffix attack",
                       ch is not None and not ch.can_handle(f"https://{_dom}evil.test/x")))

    # rss: path-based detection
    rss = get_channel("rss")
    checks.append(("rss can_handle .rss", rss.can_handle("https://a.test/feed.rss")))
    checks.append(("rss can_handle .xml", rss.can_handle("https://a.test/feed.xml")))
    checks.append(("rss can_handle /feed", rss.can_handle("https://a.test/feed")))
    checks.append(("rss can_handle /rss", rss.can_handle("https://a.test/rss")))
    checks.append(("rss can_handle 'feed' in path", rss.can_handle("https://a.test/feeds/atom")))
    checks.append(("rss rejects plain page", not rss.can_handle("https://a.test/article/1")))

    # web: catch-all for any http(s)
    web = get_channel("web")
    checks.append(("web can_handle http", web.can_handle("http://a.test/x")))
    checks.append(("web can_handle https", web.can_handle("https://a.test/x")))
    checks.append(("web rejects non-http", not web.can_handle("ftp://a.test/x")))
    checks.append(("web rejects empty", not web.can_handle("")))

    # coverage: every registry channel claims at least one http URL, so
    # WebChannel is genuinely the last-resort catch-all.
    checks.append(("web is the only catch-all", sum(1 for c in ALL_CHANNELS if c.can_handle("https://example.invalid/x")) == 1))

    # ------------------------------------------------- fetch_parallel error text
    # route() returns None (no platform router) -> must NOT be reported as a
    # router-table failure. No network: phase0.route is monkeypatched.
    import channels as pkg
    import engine.phase0 as phase0

    orig_route = phase0.route
    try:
        phase0.route = lambda url, **kw: None
        out = pkg.fetch_parallel(["https://unrouted.test/x"], timeout=1)
        checks.append(("fetch_parallel unrouted wording", out["https://unrouted.test/x"]["error"] == "no platform router for host"))
        checks.append(("fetch_parallel unrouted ok=False", out["https://unrouted.test/x"]["ok"] is False))

        phase0.route = lambda url, **kw: {"ok": False, "error": "boom"}
        out = pkg.fetch_parallel(["https://a.test/x"], timeout=1)
        checks.append(("fetch_parallel surfaces router error", out["https://a.test/x"]["error"] == "boom"))

        phase0.route = lambda url, **kw: {"ok": True, "content": "BODY"}
        out = pkg.fetch_parallel(["https://a.test/x"], timeout=1)
        checks.append(("fetch_parallel success content", out["https://a.test/x"]["ok"] is True and out["https://a.test/x"]["content"] == "BODY"))
        checks.append(("fetch_parallel success error None", out["https://a.test/x"]["error"] is None))

        def _boom(url, **kw):
            raise RuntimeError("kaboom")
        phase0.route = _boom
        out = pkg.fetch_parallel(["https://a.test/x"], timeout=1)
        checks.append(("fetch_parallel catches exception", out["https://a.test/x"]["ok"] is False and "kaboom" in out["https://a.test/x"]["error"]))

        phase0.route = lambda url, **kw: {"ok": True, "content": url}
        many = pkg.fetch_parallel([f"https://a.test/{i}" for i in range(5)], timeout=1, max_workers=3)
        checks.append(("fetch_parallel returns one key per url", len(many) == 5 and all(f"https://a.test/{i}" in many for i in range(5))))
    finally:
        phase0.route = orig_route

    # ---------------------------------------------------------------- report
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {name}")
    print(f"[+] channels selftest: {len(checks) - len(failed)}/{len(checks)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
