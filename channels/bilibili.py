# -*- coding: utf-8 -*-
"""Bilibili — standalone channel."""

from .base import Channel
from .utils import host_matches, probe_command


class BilibiliChannel(Channel):
    name = "bilibili"
    description = "Bilibili videos and posts"
    backends = ["curl", "yt-dlp"]
    tier = 0

    def can_handle(self, url: str) -> bool:
        return host_matches(url, "bilibili.com", "b23.tv")

    def check(self, config=None):
        result = probe_command("curl")
        self.active_backend = "curl" if result["status"] == "ok" else None
        return self.active_backend is not None
