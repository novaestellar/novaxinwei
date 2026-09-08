# -*- coding: utf-8 -*-
"""Threads — standalone channel (Meta, Instagram-based)."""

from .base import Channel
from .utils import host_matches, probe_command


class ThreadsChannel(Channel):
    name = "threads"
    description = "Threads posts and profiles (Meta)"
    backends = ["curl"]
    tier = 0

    def can_handle(self, url: str) -> bool:
        return host_matches(url, "threads.net")

    def check(self, config=None):
        result = probe_command("curl")
        self.active_backend = "curl" if result["status"] == "ok" else None
        return self.active_backend is not None
