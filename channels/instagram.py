# -*- coding: utf-8 -*-
"""Instagram — standalone channel with oembed support."""

from .base import Channel
from .utils import host_matches, probe_command


class InstagramChannel(Channel):
    name = "instagram"
    description = "Instagram posts, reels, and profiles"
    backends = ["curl"]
    tier = 0

    def can_handle(self, url: str) -> bool:
        return host_matches(url, "instagram.com")

    def check(self, config=None):
        result = probe_command("curl")
        self.active_backend = "curl" if result["status"] == "ok" else None
        return self.active_backend is not None
