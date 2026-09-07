# -*- coding: utf-8 -*-
"""Reddit — standalone channel."""

from .base import Channel
from .utils import host_matches, probe_command


class RedditChannel(Channel):
    name = "reddit"
    description = "Reddit posts, subreddits, and comments"
    backends = ["curl"]
    tier = 0

    def can_handle(self, url: str) -> bool:
        return host_matches(url, "reddit.com", "redd.it")

    def check(self, config=None):
        result = probe_command("curl")
        self.active_backend = "curl" if result["status"] == "ok" else None
        return self.active_backend is not None
