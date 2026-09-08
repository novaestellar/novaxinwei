"""Phase 0 — official public-API router (the SANCTIONED exception to No-Site-Name).

Per SKILL.md R5, platforms that publish official no-auth public endpoints get a
deterministic route tried BEFORE the generic WAF grid. This is the *enforced,
in-engine* version of what used to be agent-driven curl snippets in SKILL.md —
so the agent can no longer silently skip it (which is exactly how Reddit/X were
wrongly declared "blocked": the grid 403'd on `.json` and nobody tried `.rss`).

This file is the ONLY engine/ module allowed to name platform hosts; it is
exempted in `bias_check.EXPLICIT_ALLOW_FILES`. Do NOT add per-site logic to any
other engine file — generic WAF handling stays site-agnostic.

Supported platforms (15):
    reddit, x, youtube, threads, xiaohongshu, bilibili, v2ex, facebook, instagram, linkedin,
    cnblogs, csdn, segmentfault, so_gitee, codeberg

Contract:
    route(url) -> Optional[dict]
      None              → url is not a recognised Phase-0 platform; caller runs
                          the generic grid as usual.
      {"platform","ok","route","content","final_url","attempts":[...]}
                        → recognised platform. `ok` says whether an official
                          route succeeded. Even on ok=False the caller should
                          fall through to the grid, but `attempts` is recorded
                          so failure is never silent.

Each attempt dict: {"route","platform","ok","status","bytes","note"}.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from typing import Optional
from urllib.parse import urlsplit


# --- low-level helpers -------------------------------------------------------
def _cffi_get(url: str, *, impersonate: str = "safari", timeout: int = 15):
    from curl_cffi import requests as r  # lazy: engine works even if missing
    import time as _time
    last_err = None
    for _attempt in range(3):
        try:
            return r.get(
                url,
                impersonate=impersonate,  # type: ignore[arg-type]
                timeout=timeout,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
                },
                allow_redirects=True,
            )
        except Exception as e:
            last_err = e
            if _attempt < 2:
                _time.sleep(0.5 * (_attempt + 1))
    raise last_err  # type: ignore[misc]


def _host(url: str) -> str:
    h = (urlsplit(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h  # strip the literal "www." prefix only


def _attempt(platform: str, route: str, ok: bool, status: int, body: str, note: str = "") -> dict:
    return {"platform": platform, "route": route, "ok": ok, "status": status,
            "bytes": len(body or ""), "note": note}


# --- platform detectors ------------------------------------------------------
def _detect(url: str) -> Optional[str]:
    h = _host(url)
    if not h:
        return None
    if "reddit.com" in h or h == "redd.it":
        return "reddit"
    if h in ("x.com", "twitter.com") or h.endswith(".x.com") or h.endswith(".twitter.com"):
        return "x"
    if "youtube.com" in h or h == "youtu.be":
        return "youtube"
    if h in ("threads.com", "threads.net") or h.endswith((".threads.com", ".threads.net")):
        return "threads"
    if "xiaohongshu.com" in h or "xhslink.com" in h:
        return "xiaohongshu"
    if "bilibili.com" in h or "b23.tv" in h:
        return "bilibili"
    if "v2ex.com" in h:
        return "v2ex"
    if "facebook.com" in h or "fb.com" in h or "fb.watch" in h:
        return "facebook"
    if "instagram.com" in h:
        return "instagram"
    if "linkedin.com" in h:
        return "linkedin"
    if "cnblogs.com" in h:
        return "cnblogs"
    if "csdn.net" in h:
        return "csdn"
    if "segmentfault.com" in h:
        return "segmentfault"
    if "so.gitee.com" in h or h == "so.gitee.com":
        return "so_gitee"
    if "codeberg.org" in h:
        return "codeberg"
    return None


# --- reddit ------------------------------------------------------------------
def _reddit(url: str, timeout: int) -> dict:
    attempts: list[dict] = []
    base = url.split("?", 1)[0].rstrip("/")
    rss_url = base + ("/.rss" if "/comments/" not in base else ".rss")
    json_url = base + ("/.json" if "/comments/" not in base else ".json")

    # Route 1: RSS
    try:
        x = _cffi_get(rss_url, timeout=timeout)
        ok = x.status_code == 200 and ("<rss" in x.text or "<feed" in x.text)
        attempts.append(_attempt("reddit", "rss", ok, x.status_code, x.text,
                                 "feed" if ok else "no-feed-markers"))
        if ok:
            return {"platform": "reddit", "ok": True, "route": "rss",
                    "content": x.text, "final_url": rss_url, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("reddit", "rss", False, 0, "", f"{type(e).__name__}"))

    # Route 2: JSON
    try:
        x = _cffi_get(json_url, timeout=timeout)
        ok = x.status_code == 200 and x.text.lstrip().startswith(("{", "["))
        attempts.append(_attempt("reddit", "json", ok, x.status_code, x.text,
                                 "json" if ok else f"status={x.status_code}"))
        if ok:
            return {"platform": "reddit", "ok": True, "route": "json",
                    "content": x.text, "final_url": json_url, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("reddit", "json", False, 0, "", f"{type(e).__name__}"))

    # Route 3: oembed (public posts only)
    try:
        oembed_url = f"https://www.reddit.com/oembed?url={url}"
        x = _cffi_get(oembed_url, timeout=timeout)
        ok = x.status_code == 200 and '"html"' in x.text
        attempts.append(_attempt("reddit", "oembed", ok, x.status_code, x.text,
                                 "html" if ok else f"status={x.status_code}"))
        if ok:
            return {"platform": "reddit", "ok": True, "route": "oembed",
                    "content": x.text, "final_url": oembed_url, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("reddit", "oembed", False, 0, "", f"{type(e).__name__}"))

    return {"platform": "reddit", "ok": False, "route": None, "content": "",
            "final_url": url, "attempts": attempts}


# --- x / twitter -------------------------------------------------------------
_TWEET_ID_RE = re.compile(r"/status(?:es)?/(\d+)")


def _x(url: str, timeout: int) -> dict:
    attempts: list[dict] = []
    m = _TWEET_ID_RE.search(url)

    if not m:
        # Profile URL — try oembed
        try:
            ourl = f"https://publish.twitter.com/oembed?url={url}&omit_script=1"
            x = _cffi_get(ourl, timeout=timeout)
            d = x.json() if x.status_code == 200 else {}
            ok = bool(d.get("html"))
            attempts.append(_attempt("x", "oembed-profile", ok, x.status_code, x.text,
                                     "has-html" if ok else f"status={x.status_code}"))
            if ok:
                return {"platform": "x", "ok": True, "route": "oembed-profile",
                        "content": d["html"], "final_url": url, "attempts": attempts}
        except Exception as e:
            attempts.append(_attempt("x", "oembed-profile", False, 0, "", f"{type(e).__name__}"))
        return {"platform": "x", "ok": False, "route": None, "content": "",
                "final_url": url, "attempts": attempts}

    if m:
        tid = m.group(1)
        try:
            x = _cffi_get(f"https://cdn.syndication.twimg.com/tweet-result?id={tid}&token=a", timeout=timeout)
            d = x.json() if x.status_code == 200 else {}
            ok = bool(d.get("text"))
            attempts.append(_attempt("x", "tweet-result", ok, x.status_code, x.text,
                                     "has-text" if ok else f"status={x.status_code}"))
            if ok:
                return {"platform": "x", "ok": True, "route": "tweet-result",
                        "content": x.text, "final_url": url, "attempts": attempts}
        except Exception as e:
            attempts.append(_attempt("x", "tweet-result", False, 0, "", f"{type(e).__name__}"))
        try:
            ourl = f"https://publish.twitter.com/oembed?url=https://twitter.com/i/status/{tid}&omit_script=1"
            x = _cffi_get(ourl, timeout=timeout)
            d = x.json() if x.status_code == 200 else {}
            ok = bool(d.get("html"))
            attempts.append(_attempt("x", "oembed", ok, x.status_code, x.text,
                                     "has-html" if ok else f"status={x.status_code}"))
            if ok:
                return {"platform": "x", "ok": True, "route": "oembed",
                        "content": x.text, "final_url": ourl, "attempts": attempts}
        except Exception as e:
            attempts.append(_attempt("x", "oembed", False, 0, "", f"{type(e).__name__}"))
    else:
        handle = urlsplit(url).path.strip("/").split("/")[0]
        _reserved = {"i", "search", "home", "explore", "messages", "notifications", "settings", "hashtag"}
        if handle and handle.lower() not in _reserved:
            surl = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{handle}"
            for attempt_no in range(2):
                try:
                    x = _cffi_get(surl, timeout=timeout)
                    ok = x.status_code == 200 and "__NEXT_DATA__" in x.text
                    attempts.append(_attempt("x", f"syndication-timeline#{attempt_no+1}", ok,
                                             x.status_code, x.text,
                                             "timeline" if ok else f"status={x.status_code}"))
                    if ok:
                        return {"platform": "x", "ok": True, "route": "syndication-timeline",
                                "content": x.text, "final_url": surl, "attempts": attempts}
                except Exception as e:
                    attempts.append(_attempt("x", f"syndication-timeline#{attempt_no+1}", False, 0, "", f"{type(e).__name__}"))

    return {"platform": "x", "ok": False, "route": None, "content": "",
            "final_url": url, "attempts": attempts}


# --- youtube -----------------------------------------------------------------
def _ytdlp_argv() -> Optional[list[str]]:
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    if importlib.util.find_spec("yt_dlp") is not None:
        return [sys.executable, "-m", "yt_dlp"]
    return None


def _youtube(url: str, timeout: int) -> dict:
    attempts: list[dict] = []
    argv = _ytdlp_argv()
    if argv is None:
        attempts.append(_attempt("youtube", "yt-dlp", False, 0, "", "yt-dlp not installed"))
        return {"platform": "youtube", "ok": False, "route": None, "content": "",
                "final_url": url, "attempts": attempts}
    try:
        p = subprocess.run(
            argv + ["--dump-json", "--skip-download", url],
            capture_output=True, text=True, timeout=max(timeout, 60),
        )
        ok = p.returncode == 0 and p.stdout.strip().startswith("{")
        note = "json" if ok else (p.stderr or "").strip()[:80]
        attempts.append(_attempt("youtube", "yt-dlp", ok, 200 if ok else 0, p.stdout, note))
        if ok:
            return {"platform": "youtube", "ok": True, "route": "yt-dlp",
                    "content": p.stdout, "final_url": url, "attempts": attempts}
    except FileNotFoundError:
        attempts.append(_attempt("youtube", "yt-dlp", False, 0, "", "yt-dlp not installed"))
    except Exception as e:
        attempts.append(_attempt("youtube", "yt-dlp", False, 0, "", f"{type(e).__name__}"))
    return {"platform": "youtube", "ok": False, "route": None, "content": "",
            "final_url": url, "attempts": attempts}


# --- threads -----------------------------------------------------------------
_THREADS_POST_RE = re.compile(r"/post/([A-Za-z0-9_-]+)")


def _threads(url: str, timeout: int) -> dict:
    attempts: list[dict] = []
    m = _THREADS_POST_RE.search(url.split("?", 1)[0])
    if not m:
        attempts.append(_attempt("threads", "inline-json", False, 0, "", "no-post-shortcode"))
        return {"platform": "threads", "ok": False, "route": None, "content": "",
                "final_url": url, "attempts": attempts}
    code = m.group(1)
    try:
        x = _cffi_get(url, timeout=timeout)
        raw = x.text if x.status_code == 200 else ""
        code_pos = [c.start() for c in re.finditer(r'"code"\s*:\s*"%s"' % re.escape(code), raw)]
        blocks = list(re.finditer(r'"video_versions"\s*:\s*\[(.*?)\]', raw))
        if not code_pos or not blocks:
            note = (f"status={x.status_code}" if x.status_code != 200
                    else ("no-code-marker" if not code_pos else "no-video_versions"))
            attempts.append(_attempt("threads", "inline-json", False, x.status_code, raw, note))
            # Fallback: extract text/meta from HTML
            try:
                title_m = re.search(r'<title[^>]*>([^<]+)</title>', x.text)
                desc_m = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]+)"', x.text)
                if title_m or desc_m:
                    content = json.dumps({
                        "post_code": code,
                        "title": title_m.group(1).strip() if title_m else "",
                        "description": desc_m.group(1).strip() if desc_m else ""
                    }, ensure_ascii=False)
                    attempts.append(_attempt("threads", "meta", True, x.status_code, content, "meta-tags"))
                    return {"platform": "threads", "ok": True, "route": "meta",
                            "content": content, "final_url": url, "attempts": attempts}
            except Exception as e2:
                attempts.append(_attempt("threads", "meta", False, 0, "", f"{type(e2).__name__}"))
            return {"platform": "threads", "ok": False, "route": None, "content": "",
                    "final_url": url, "attempts": attempts}
        best = min(blocks, key=lambda b: min(abs(b.start() - c) for c in code_pos))
        urls: list[str] = []
        for u in re.findall(r'"url"\s*:\s*"([^"]+)"', best.group(1)):
            u = u.replace("\\/", "/").encode().decode("unicode_escape")
            if u not in urls:
                urls.append(u)
        if not urls:
            attempts.append(_attempt("threads", "inline-json", False, x.status_code, raw, "empty-video_versions"))
            return {"platform": "threads", "ok": False, "route": None, "content": "",
                    "final_url": url, "attempts": attempts}
        content = json.dumps({"post_code": code, "video_urls": urls}, ensure_ascii=False)
        attempts.append(_attempt("threads", "inline-json", True, x.status_code, content,
                                 f"{len(urls)} video url(s)"))
        return {"platform": "threads", "ok": True, "route": "inline-json",
                "content": content, "final_url": url, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("threads", "inline-json", False, 0, "", f"{type(e).__name__}"))
        return {"platform": "threads", "ok": False, "route": None, "content": "",
                "final_url": url, "attempts": attempts}


# --- xiaohongshu -------------------------------------------------------------
_XHS_NOTE_RE = re.compile(r"/explore/([a-f0-9]+)|/discovery/item/([a-f0-9]+)|/note/([a-f0-9]+)")


def _xiaohongshu(url: str, timeout: int) -> dict:
    """Xiaohongshu/XHS — try mobile API endpoint for note content."""
    attempts: list[dict] = []
    m = _XHS_NOTE_RE.search(url)
    if not m:
        attempts.append(_attempt("xiaohongshu", "mobile-api", False, 0, "", "no-note-id"))
        return {"platform": "xiaohongshu", "ok": False, "route": None, "content": "",
                "final_url": url, "attempts": attempts}
    note_id = next(g for g in m.groups() if g)
    api_url = f"https://edith.xiaohongshu.com/api/sns/web/v1/note/{note_id}"
    try:
        x = _cffi_get(api_url, impersonate="chrome", timeout=timeout)
        ok = x.status_code == 200 and '"title"' in x.text
        attempts.append(_attempt("xiaohongshu", "mobile-api", ok, x.status_code, x.text,
                                 "json" if ok else f"status={x.status_code}"))
        if ok:
            return {"platform": "xiaohongshu", "ok": True, "route": "mobile-api",
                    "content": x.text, "final_url": api_url, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("xiaohongshu", "mobile-api", False, 0, "", f"{type(e).__name__}"))
    # Fallback: direct HTML scrape
    try:
        x = _cffi_get(url, impersonate="chrome", timeout=timeout)
        ok = x.status_code == 200 and len(x.text) > 1000
        attempts.append(_attempt("xiaohongshu", "html", ok, x.status_code, x.text[:200],
                                 "html" if ok else f"status={x.status_code}"))
        if ok:
            return {"platform": "xiaohongshu", "ok": True, "route": "html",
                    "content": x.text, "final_url": url, "attempts": attempts}
    except Exception as e2:
        attempts.append(_attempt("xiaohongshu", "html", False, 0, "", f"{type(e2).__name__}"))
    return {"platform": "xiaohongshu", "ok": False, "route": None, "content": "",
            "final_url": url, "attempts": attempts}


# --- bilibili ----------------------------------------------------------------
_BILI_video_RE = re.compile(r"/video/(BV\w+)")
_BILI_watch_RE = re.compile(r"/watch\?bvid=(BV\w+)")


def _bilibili(url: str, timeout: int) -> dict:
    """Bilibili — use public API for video metadata."""
    attempts: list[dict] = []
    m = _BILI_video_RE.search(url) or _BILI_watch_RE.search(url)
    if not m:
        attempts.append(_attempt("bilibili", "api", False, 0, "", "no-bv-id"))
        return {"platform": "bilibili", "ok": False, "route": None, "content": "",
                "final_url": url, "attempts": attempts}
    bvid = m.group(1)
    api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    try:
        x = _cffi_get(api_url, timeout=timeout, impersonate="chrome", headers={"Referer": "https://www.bilibili.com/", "Cookie": "buvid3=test"})
        ok = x.status_code == 200 and '"data"' in x.text
        attempts.append(_attempt("bilibili", "api", ok, x.status_code, x.text,
                                 "json" if ok else f"status={x.status_code}"))
        if ok:
            return {"platform": "bilibili", "ok": True, "route": "api",
                    "content": x.text, "final_url": api_url, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("bilibili", "api", False, 0, "", f"{type(e).__name__}"))
    return {"platform": "bilibili", "ok": False, "route": None, "content": "",
            "final_url": url, "attempts": attempts}


# --- v2ex --------------------------------------------------------------------
def _v2ex(url: str, timeout: int) -> dict:
    """V2EX — use public API for topic content."""
    attempts: list[dict] = []
    topic_match = re.search(r"/t/(\d+)", url)
    if not topic_match:
        attempts.append(_attempt("v2ex", "api", False, 0, "", "no-topic-id"))
        return {"platform": "v2ex", "ok": False, "route": None, "content": "",
                "final_url": url, "attempts": attempts}
    tid = topic_match.group(1)
    api_url = f"https://www.v2ex.com/api/topics/show.json?id={tid}"
    try:
        x = _cffi_get(api_url, timeout=timeout)
        ok = x.status_code == 200 and x.text.lstrip().startswith("[")
        attempts.append(_attempt("v2ex", "api", ok, x.status_code, x.text,
                                 "json" if ok else f"status={x.status_code}"))
        if ok:
            return {"platform": "v2ex", "ok": True, "route": "api",
                    "content": x.text, "final_url": api_url, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("v2ex", "api", False, 0, "", f"{type(e).__name__}"))
    return {"platform": "v2ex", "ok": False, "route": None, "content": "",
            "final_url": url, "attempts": attempts}


# --- facebook ----------------------------------------------------------------
def _facebook(url: str, timeout: int) -> dict:
    """Facebook — try oembed then direct HTML scrape."""
    attempts: list[dict] = []
    # 1) oembed
    oembed_url = f"https://www.facebook.com/plugins/post/oembed?url={url}"
    try:
        x = _cffi_get(oembed_url, timeout=timeout)
        ok = x.status_code == 200 and '"html"' in x.text
        attempts.append(_attempt("facebook", "oembed", ok, x.status_code, x.text,
                                 "html" if ok else f"status={x.status_code}"))
        if ok:
            return {"platform": "facebook", "ok": True, "route": "oembed",
                    "content": x.text, "final_url": oembed_url, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("facebook", "oembed", False, 0, "", f"{type(e).__name__}"))
    # 2) direct HTML
    try:
        x = _cffi_get(url, timeout=timeout)
        ok = x.status_code == 200 and len(x.text) > 1000
        attempts.append(_attempt("facebook", "html", ok, x.status_code, x.text[:200],
                                 "html" if ok else f"status={x.status_code}"))
        if ok:
            return {"platform": "facebook", "ok": True, "route": "html",
                    "content": x.text, "final_url": url, "attempts": attempts}
    except Exception as e2:
        attempts.append(_attempt("facebook", "html", False, 0, "", f"{type(e2).__name__}"))
    return {"platform": "facebook", "ok": False, "route": None, "content": "",
            "final_url": url, "attempts": attempts}


# --- instagram ---------------------------------------------------------------
def _instagram(url: str, timeout: int) -> dict:
    """Instagram — try oembed then direct scrape."""
    attempts: list[dict] = []
    oembed_url = f"https://api.instagram.com/oembed/?url={url}"
    try:
        x = _cffi_get(oembed_url, timeout=timeout)
        ok = x.status_code == 200 and '"html"' in x.text
        attempts.append(_attempt("instagram", "oembed", ok, x.status_code, x.text,
                                 "html" if ok else f"status={x.status_code}"))
        if ok:
            return {"platform": "instagram", "ok": True, "route": "oembed",
                    "content": x.text, "final_url": oembed_url, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("instagram", "oembed", False, 0, "", f"{type(e).__name__}"))
    # Fallback: direct HTML
    try:
        x = _cffi_get(url, timeout=timeout)
        ok = x.status_code == 200 and len(x.text) > 1000
        attempts.append(_attempt("instagram", "html", ok, x.status_code, x.text[:200],
                                 "html" if ok else f"status={x.status_code}"))
        if ok:
            return {"platform": "instagram", "ok": True, "route": "html",
                    "content": x.text, "final_url": url, "attempts": attempts}
    except Exception as e2:
        attempts.append(_attempt("instagram", "html", False, 0, "", f"{type(e2).__name__}"))
    return {"platform": "instagram", "ok": False, "route": None, "content": "",
            "final_url": url, "attempts": attempts}


# --- linkedin ----------------------------------------------------------------
def _linkedin(url: str, timeout: int) -> dict:
    """LinkedIn — try oembed then direct scrape with chrome."""
    attempts: list[dict] = []
    oembed_url = f"https://www.linkedin.com/noashare?url={url}"
    try:
        x = _cffi_get(oembed_url, timeout=timeout)
        ok = x.status_code == 200 and "<blockquote" in x.text
        attempts.append(_attempt("linkedin", "oembed", ok, x.status_code, x.text,
                                 "blockquote" if ok else f"status={x.status_code}"))
        if ok:
            return {"platform": "linkedin", "ok": True, "route": "oembed",
                    "content": x.text, "final_url": oembed_url, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("linkedin", "oembed", False, 0, "", f"{type(e).__name__}"))
    # Fallback: direct HTML with chrome impersonation
    try:
        x = _cffi_get(url, impersonate="chrome", timeout=timeout)
        ok = x.status_code == 200 and len(x.text) > 1000
        attempts.append(_attempt("linkedin", "html", ok, x.status_code, x.text[:200],
                                 "html" if ok else f"status={x.status_code}"))
        if ok:
            return {"platform": "linkedin", "ok": True, "route": "html",
                    "content": x.text, "final_url": url, "attempts": attempts}
    except Exception as e2:
        attempts.append(_attempt("linkedin", "html", False, 0, "", f"{type(e2).__name__}"))
    return {"platform": "linkedin", "ok": False, "route": None, "content": "",
            "final_url": url, "attempts": attempts}


# --- cnblogs ------------------------------------------------------------------
def _cnblogs(url: str, timeout: int) -> dict:
    """cnblogs — RSS feed available on most blogs."""
    attempts: list[dict] = []
    base = url.split("?", 1)[0].rstrip("/")
    rss_url = base + "/rss"
    try:
        x = _cffi_get(rss_url, timeout=timeout)
        ok = x.status_code == 200 and ("<rss" in x.text or "<feed" in x.text)
        attempts.append(_attempt("cnblogs", "rss", ok, x.status_code, x.text,
                                 "feed" if ok else "no-feed-markers"))
        if ok:
            return {"platform": "cnblogs", "ok": True, "route": "rss",
                    "content": x.text, "final_url": rss_url, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("cnblogs", "rss", False, 0, "", f"{type(e).__name__}"))
    # fallback: direct HTML
    try:
        x = _cffi_get(url, timeout=timeout)
        ok = x.status_code == 200 and len(x.text) > 500
        attempts.append(_attempt("cnblogs", "html", ok, x.status_code, x.text,
                                 "html" if ok else f"status={x.status_code}"))
        if ok:
            return {"platform": "cnblogs", "ok": True, "route": "html",
                    "content": x.text, "final_url": url, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("cnblogs", "html", False, 0, "", f"{type(e).__name__}"))
    return {"platform": "cnblogs", "ok": False, "route": None, "content": "",
            "final_url": url, "attempts": attempts}


# --- csdn ----------------------------------------------------------------------
def _csdn(url: str, timeout: int) -> dict:
    """CSDN — direct HTML fetch."""
    attempts: list[dict] = []
    try:
        x = _cffi_get(url, timeout=timeout)
        ok = x.status_code == 200 and len(x.text) > 500
        attempts.append(_attempt("csdn", "html", ok, x.status_code, x.text,
                                 "html" if ok else f"status={x.status_code}"))
        if ok:
            return {"platform": "csdn", "ok": True, "route": "html",
                    "content": x.text, "final_url": url, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("csdn", "html", False, 0, "", f"{type(e).__name__}"))
    return {"platform": "csdn", "ok": False, "route": None, "content": "",
            "final_url": url, "attempts": attempts}


# --- segmentfault -------------------------------------------------------------
def _segmentfault(url: str, timeout: int) -> dict:
    """SegmentFault — API for articles/questions."""
    attempts: list[dict] = []
    # try direct HTML first
    try:
        x = _cffi_get(url, timeout=timeout)
        ok = x.status_code == 200 and len(x.text) > 500
        attempts.append(_attempt("segmentfault", "html", ok, x.status_code, x.text,
                                 "html" if ok else f"status={x.status_code}"))
        if ok:
            return {"platform": "segmentfault", "ok": True, "route": "html",
                    "content": x.text, "final_url": url, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("segmentfault", "html", False, 0, "", f"{type(e).__name__}"))
    return {"platform": "segmentfault", "ok": False, "route": None, "content": "",
            "final_url": url, "attempts": attempts}


# --- so.gitee ------------------------------------------------------------------
def _so_gitee(url: str, timeout: int) -> dict:
    """so.gitee.com — Gitee code search."""
    attempts: list[dict] = []
    # Root URL redirects to search
    if url.rstrip("/") in ("https://so.gitee.com", "https://so.gitee.com/"):
        url = "https://so.gitee.com/search?q=python"
    try:
        x = _cffi_get(url, timeout=timeout)
        ok = x.status_code == 200 and len(x.text) > 500
        attempts.append(_attempt("so_gitee", "html", ok, x.status_code, x.text,
                                 "html" if ok else f"status={x.status_code}"))
        if ok:
            return {"platform": "so_gitee", "ok": True, "route": "html",
                    "content": x.text, "final_url": url, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("so_gitee", "html", False, 0, "", f"{type(e).__name__}"))
    return {"platform": "so_gitee", "ok": False, "route": None, "content": "",
            "final_url": url, "attempts": attempts}


# --- codeberg ------------------------------------------------------------------
def _codeberg(url: str, timeout: int) -> dict:
    """Codeberg — Gitea-based, try RSS then HTML."""
    attempts: list[dict] = []
    base = url.split("?", 1)[0].rstrip("/")
    rss_url = base + ".rss"
    try:
        x = _cffi_get(rss_url, timeout=timeout)
        ok = x.status_code == 200 and ("<rss" in x.text or "<feed" in x.text)
        attempts.append(_attempt("codeberg", "rss", ok, x.status_code, x.text,
                                 "feed" if ok else "no-feed-markers"))
        if ok:
            return {"platform": "codeberg", "ok": True, "route": "rss",
                    "content": x.text, "final_url": rss_url, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("codeberg", "rss", False, 0, "", f"{type(e).__name__}"))
    # fallback: Gitea API
    api_url = f"https://codeberg.org/api/v1/repos{urlsplit(url).path}"
    try:
        x = _cffi_get(api_url, timeout=timeout)
        ok = x.status_code == 200 and x.text.lstrip().startswith("{")
        attempts.append(_attempt("codeberg", "api", ok, x.status_code, x.text,
                                 "json" if ok else f"status={x.status_code}"))
        if ok:
            return {"platform": "codeberg", "ok": True, "route": "api",
                    "content": x.text, "final_url": api_url, "attempts": attempts}
    except Exception as e:
        attempts.append(_attempt("codeberg", "api", False, 0, "", f"{type(e).__name__}"))
    return {"platform": "codeberg", "ok": False, "route": None, "content": "",
            "final_url": url, "attempts": attempts}


# --- router table ------------------------------------------------------------
_ROUTERS = {
    "reddit": _reddit,
    "x": _x,
    "youtube": _youtube,
    "threads": _threads,
    "xiaohongshu": _xiaohongshu,
    "bilibili": _bilibili,
    "v2ex": _v2ex,
    "facebook": _facebook,
    "instagram": _instagram,
    "linkedin": _linkedin,
    "cnblogs": _cnblogs,
    "csdn": _csdn,
    "segmentfault": _segmentfault,
    "so_gitee": _so_gitee,
    "codeberg": _codeberg,
}


# --- public entrypoint -------------------------------------------------------
def route(url: str, *, timeout: int = 15) -> Optional[dict]:
    platform = _detect(url)
    if platform is None:
        return None
    return _ROUTERS[platform](url, timeout)
