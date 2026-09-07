# -*- coding: utf-8 -*-
"""YouTube — standalone channel."""

from .base import Channel
from .utils import host_matches, probe_command


class YouTubeChannel(Channel):
    name = "youtube"
    description = "YouTube videos, playlists, and channels"
    backends = ["yt-dlp", "curl"]
    tier = 0

    def can_handle(self, url: str) -> bool:
        return host_matches(url, "youtube.com", "youtu.be")

    def check(self, config=None):
        result = probe_command("yt-dlp")
        if result["status"] == "ok":
            self.active_backend = "yt-dlp"
            return True
        result = probe_command("curl")
        self.active_backend = "curl" if result["status"] == "ok" else None
        return self.active_backend is not None
