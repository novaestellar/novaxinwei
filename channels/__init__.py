"""NovaXinWei channel registry — 11 platforms.

Channel contract:
    can_handle(url) → bool
    check(config)   → bool (sets active_backend)

After check(), agents call upstream tools directly.
"""

from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from .base import Channel
from .bilibili import BilibiliChannel
from .facebook import FacebookChannel
from .instagram import InstagramChannel
from .linkedin import LinkedInChannel
from .reddit import RedditChannel
from .rss import RSSChannel
from .twitter import TwitterChannel
from .v2ex import V2EXChannel
from .web import WebChannel
from .xiaohongshu import XiaoHongShuChannel
from .youtube import YouTubeChannel

ALL_CHANNELS: List[Channel] = [
    TwitterChannel(),
    YouTubeChannel(),
    RedditChannel(),
    FacebookChannel(),
    InstagramChannel(),
    BilibiliChannel(),
    XiaoHongShuChannel(),
    LinkedInChannel(),
    V2EXChannel(),
    RSSChannel(),
    WebChannel(),
]


def get_channel(name: str) -> Optional[Channel]:
    """Get a channel by name."""
    for ch in ALL_CHANNELS:
        if ch.name == name:
            return ch
    return None


def get_all_channels() -> List[Channel]:
    """Get all registered channels."""
    return ALL_CHANNELS


def fetch_parallel(urls: list[str], timeout: int = 15, max_workers: int = 5) -> dict:
    """Fetch multiple URLs in parallel using ThreadPoolExecutor.

    Returns: {url: {"ok": bool, "content": str, "error": str|None}}
    """
    from .engine.phase0 import route as phase0_route
    results = {}

    def _fetch_one(url: str) -> tuple[str, dict]:
        try:
            result = phase0_route(url, timeout=timeout)
            if result and result.get("ok"):
                return url, {"ok": True, "content": result["content"], "error": None}
            return url, {"ok": False, "content": "", "error": "phase0 route failed"}
        except Exception as e:
            return url, {"ok": False, "content": "", "error": str(e)}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_one, url): url for url in urls}
        for future in as_completed(futures):
            url, result = future.result()
            results[url] = result

    return results


__all__ = [
    "Channel",
    "ALL_CHANNELS",
    "get_channel",
    "get_all_channels",
    "fetch_parallel",
]
