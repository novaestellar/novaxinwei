# -*- coding: utf-8 -*-
"""NodeLoc — standalone channel."""

from .base import Channel
from .utils import host_matches


class NodeLocChannel(Channel):
    name = "nodeloc"
    description = "NodeLoc developer forum"
    backends = ["curl", "playwright"]
    tier = 0

    def can_handle(self, url: str) -> bool:
        return host_matches(url, "nodeloc.com")

    def check(self, config=None):
        from .utils import probe_command
        for backend in self.backends:
            if backend == "playwright":
                result = probe_command("npx")
            else:
                result = probe_command(backend)
            if result["status"] == "ok":
                self.active_backend = backend
                return True
        return False
