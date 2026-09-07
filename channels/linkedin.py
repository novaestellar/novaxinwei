# -*- coding: utf-8 -*-
"""LinkedIn — standalone channel with oembed support."""

from .base import Channel
from .utils import host_matches, probe_command


class LinkedInChannel(Channel):
    name = "linkedin"
    description = "LinkedIn posts and profiles"
    backends = ["curl"]
    tier = 1

    def can_handle(self, url: str) -> bool:
        return host_matches(url, "linkedin.com")

    def check(self, config=None):
        result = probe_command("curl")
        self.active_backend = "curl" if result["status"] == "ok" else None
        return self.active_backend is not None
