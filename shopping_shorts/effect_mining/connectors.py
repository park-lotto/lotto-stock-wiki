"""Discovery connector contracts and repository-backed adapters."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse


def external_id_from_url(platform, url):
    parsed = urlparse(url or "")
    path = parsed.path.rstrip("/")
    if platform == "youtube":
        if parsed.hostname in ("youtu.be", "www.youtu.be"):
            return path.rsplit("/", 1)[-1]
        match = re.search(r"/(?:shorts|embed)/([A-Za-z0-9_-]+)", path)
        if match:
            return match.group(1)
        return (parse_qs(parsed.query).get("v") or [""])[0]
    if platform == "instagram":
        match = re.search(r"/(?:reel|reels|p)/([A-Za-z0-9_-]+)", path)
        return match.group(1) if match else ""
    if platform == "tiktok":
        match = re.search(r"/video/(\d+)", path)
        return match.group(1) if match else ""
    return path.rsplit("/", 1)[-1]


class ConnectorRegistry:
    def __init__(self, connectors=None):
        self._connectors = dict(connectors or {})

    def get(self, platform):
        try:
            return self._connectors[platform]
        except KeyError as exc:
            raise ValueError(f"unsupported mining platform: {platform}") from exc


class YouTubeKeywordConnector:
    def __init__(self, max_results=25, language="ko"):
        self.max_results = int(max_results)
        self.language = language

    def discover(self, source):
        if source["source_kind"] != "keyword":
            raise ValueError("youtube connector currently supports keyword sources only")
        from shopping_shorts import youtube_search

        rows = youtube_search.search(
            source["query"], max_results=self.max_results,
            duration="short", language=self.language,
        )
        out = []
        for row in rows:
            external_id = external_id_from_url("youtube", row.get("url", ""))
            if external_id:
                out.append({**row, "external_id": external_id})
        return out


def production_connectors():
    return ConnectorRegistry({"youtube": YouTubeKeywordConnector()})
