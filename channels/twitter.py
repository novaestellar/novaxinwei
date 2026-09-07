# -*- coding: utf-8 -*-
"""Twitter/X — standalone channel."""

from .base import Channel
from .utils import host_matches, probe_command


class TwitterChannel(Channel):
    name = "twitter"
    description = "Twitter/X posts, threads, and profiles"
    backends = ["curl"]
    tier = 0

    def can_handle(self, url: str) -> bool:
        return host_matches(url, "x.com", "twitter.com")

    def check(self, config=None):
        result = probe_command("curl")
        self.active_backend = "curl" if result["status"] == "ok" else None
        return self.active_backend is not None
