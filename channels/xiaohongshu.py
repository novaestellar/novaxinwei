# -*- coding: utf-8 -*-
"""Xiaohongshu/XHS — standalone channel.

Provides can_handle() + check() for URL detection.
Fetch logic is in engine/phase0.py (_xiaohongshu route).
"""

import shutil

from .base import Channel
from .utils import host_matches, probe_command


class XiaoHongShuChannel(Channel):
    name = "xiaohongshu"
    description = "Xiaohongshu/XHS notes and posts"
    backends = ["curl", "yt-dlp"]
    tier = 1

    def can_handle(self, url: str) -> bool:
        return host_matches(url, "xiaohongshu.com", "xhslink.com")

    def check(self, config=None):
        result = probe_command("curl")
        self.active_backend = "curl" if result["status"] == "ok" else None
        return self.active_backend is not None
