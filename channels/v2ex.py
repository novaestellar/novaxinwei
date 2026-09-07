# -*- coding: utf-8 -*-
"""V2EX — standalone channel."""

from .base import Channel
from .utils import host_matches, probe_command


class V2EXChannel(Channel):
    name = "v2ex"
    description = "V2EX tech community topics"
    backends = ["curl"]
    tier = 0

    def can_handle(self, url: str) -> bool:
        return host_matches(url, "v2ex.com")

    def check(self, config=None):
        result = probe_command("curl")
        self.active_backend = "curl" if result["status"] == "ok" else None
        return self.active_backend is not None
