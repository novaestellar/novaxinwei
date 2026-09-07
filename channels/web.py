# -*- coding: utf-8 -*-
"""Generic web — catch-all channel for any HTTP URL."""

from .base import Channel
from .utils import probe_command


class WebChannel(Channel):
    name = "web"
    description = "Generic web pages"
    backends = ["curl"]
    tier = 0

    def can_handle(self, url: str) -> bool:
        return url.startswith(("http://", "https://"))

    def check(self, config=None):
        result = probe_command("curl")
        self.active_backend = "curl" if result["status"] == "ok" else None
        return self.active_backend is not None
