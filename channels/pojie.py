# -*- coding: utf-8 -*-
"""52pojie — standalone channel."""

from .base import Channel
from .utils import host_matches


class PoJieChannel(Channel):
    name = "52pojie"
    description = "52 reverse engineering forum"
    backends = ["curl", "playwright"]
    tier = 0

    def can_handle(self, url: str) -> bool:
        return host_matches(url, "52pojie.cn")

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
