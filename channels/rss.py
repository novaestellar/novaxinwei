# -*- coding: utf-8 -*-
"""RSS/Atom — standalone channel."""

from .base import Channel
from .utils import probe_command


class RSSChannel(Channel):
    name = "rss"
    description = "RSS/Atom feeds"
    backends = ["curl"]
    tier = 0

    def can_handle(self, url: str) -> bool:
        from urllib.parse import urlsplit
        path = urlsplit(url).path.lower()
        return path.endswith((".rss", ".xml", "/feed", "/rss")) or "feed" in path

    def check(self, config=None):
        result = probe_command("curl")
        self.active_backend = "curl" if result["status"] == "ok" else None
        return self.active_backend is not None
