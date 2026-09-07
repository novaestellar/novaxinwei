# -*- coding: utf-8 -*-
"""Facebook — standalone channel with oembed support."""

from .base import Channel
from .utils import host_matches, probe_command


class FacebookChannel(Channel):
    name = "facebook"
    description = "Facebook posts, pages, and groups"
    backends = ["curl"]
    tier = 0

    def can_handle(self, url: str) -> bool:
        return host_matches(url, "facebook.com", "fb.com", "fb.watch")

    def check(self, config=None):
        result = probe_command("curl")
        self.active_backend = "curl" if result["status"] == "ok" else None
        return self.active_backend is not None
