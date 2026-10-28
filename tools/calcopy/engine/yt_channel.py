# -*- coding: utf-8 -*-
"""유튜브 채널 읽기 — 채널 쇼츠 목록·조회·RSS·캐시(관제 234: channel_find 에서 떼어 냄).
고객 설치팩 엔진 묶음은 채널 기준 소재 찾기(topic_find.channel_candidates)에 이것만 쓴다 — 채널 '판정' 노하우(channel_find)는 묶음에 안 간다.
channel_find 는 이 모듈을 그대로 가져다 쓴다(함수 한 벌)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import statistics
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

CACHE = Path(os.environ.get("CHANNEL_FIND_CACHE", "C:/숏템_칼카피/channel_find"))
UA = {"User-Agent": "Mozilla/5.0", "Accept-Language": "ko-KR,ko;q=0.9"}
NS = {"a": "http://www.w3.org/2005/Atom", "m": "http://search.yahoo.com/mrss/", "yt": "http://www.youtube.com/xml/schemas/2015"}
COST = {"serpapi_calls_new": 0, "serpapi_calls_cached": 0, "gemini_calls": 0, "gemini_failed": 0,
        "ytsearch": 0, "channel_stats": 0, "oembed": 0, "audio_downloads": 0, "audio_bytes": 0}
_LOCK = threading.Lock()

def _bump(k, n=1):
    with _LOCK:
        COST[k] = COST.get(k, 0) + n


def _cache_path(kind: str, key: str) -> Path:
    h = hashlib.md5(key.encode("utf-8")).hexdigest()[:16]
    p = CACHE / kind / f"{h}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _cached(kind: str, key: str, fn, max_age_h: float = 48):
    p = _cache_path(kind, key)
    if p.exists() and (time.time() - p.stat().st_mtime) < max_age_h * 3600:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            pass
    v = fn()
    if v is not None:
        p.write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
    return v


def _get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def ko_ratio(titles: list[str]) -> float:
    """제목 글자 중 한글 비율(해시태그·숫자·기호 뺌). 0~1."""
    s = " ".join(re.sub(r"#\S+", " ", t or "") for t in titles)
    han = len(re.findall(r"[가-힣]", s))
    other = len(re.findall(r"[A-Za-z\u3040-\u30ff\u4e00-\u9fff\u0e00-\u0e7f\u0400-\u04ff]", s))
    return han / (han + other) if (han + other) else 0.0


def lang_of(titles: list[str]) -> str:
    s = " ".join(re.sub(r"#\S+", " ", t or "") for t in titles)
    cnt = {"ko": len(re.findall(r"[가-힣]", s)), "ja": len(re.findall(r"[\u3040-\u30ff]", s)),
           "zh": len(re.findall(r"[\u4e00-\u9fff]", s)), "en": len(re.findall(r"[A-Za-z]", s)) / 3}
    if not any(cnt.values()):
        return "?"
    if cnt["ko"] and cnt["ko"] >= 0.5 * sum(cnt.values()):
        return "ko"
    return max(cnt, key=cnt.get)


def _ydl(opts=None, ko=False):
    """ko=True 면 한국어 제목(번역 제목 포함)을 받는다 — 대신 조회수(view_count)가 빠진다(10-18 실측). 조회는 ko=False 로."""
    import yt_dlp
    o = {"extract_flat": True, "quiet": True, "no_warnings": True, "skip_download": True, "noprogress": True}
    if ko:
        o["extractor_args"] = {"youtube": {"lang": ["ko"]}}
    o.update(opts or {})
    return yt_dlp.YoutubeDL(o)


def rss(channel_id: str) -> list[dict]:
    """RSS 최신 15업로드(원제목 — yt-dlp ko 는 번역 제목을 줄 수 있어 언어 판정은 이것으로)."""
    def go():
        try:
            x = _get(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}", 20).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            return {"entries": [], "_fail": True}
        root = ET.fromstring(x)
        out = []
        for e in root.findall("a:entry", NS):
            link = e.find("a:link", NS).get("href", "")
            out.append({"id": e.findtext("yt:videoId", "", NS), "title": e.findtext("a:title", "", NS),
                        "published": e.findtext("a:published", "", NS), "short": "/shorts/" in link})
        return {"entries": out}
    return (_cached("rss", channel_id, go, 24) or {}).get("entries", [])


def channel_stats(ref: str, n: int = 30) -> dict | None:
    """채널(주소·@핸들·UC id) → 최근 쇼츠 n편 조회 중앙/최대·제목·구독·업로드 빈도. 실패면 None."""
    if ref.startswith("UC") and len(ref) == 24:
        url = f"https://www.youtube.com/channel/{ref}"
    elif ref.startswith("@"):
        url = f"https://www.youtube.com/{ref}"
    else:
        url = ref.rstrip("/")
    url = re.sub(r"/(shorts|videos|featured)$", "", url)

    def go():
        _bump("channel_stats")
        d = None
        for tab in ("/shorts", "/videos"):
            try:
                with _ydl({"playlistend": n}) as y:
                    d = y.extract_info(url + tab, download=False)
                if d and d.get("entries"):
                    break
            except Exception:  # noqa: BLE001 — 쇼츠 탭이 없으면 동영상 탭
                d = None
        if not d:
            return {"_fail": True}
        ents = [e for e in (d.get("entries") or []) if e.get("id")][:n]
        ko_t = {}
        try:   # 같은 탭을 한국어로 한 번 더 — 제목만(조회는 위 호출 값)
            with _ydl({"playlistend": n}, ko=True) as y:
                dk = y.extract_info(url + tab, download=False)
            ko_t = {e.get("id"): e.get("title") for e in (dk.get("entries") or [])}
        except Exception:  # noqa: BLE001 — 실패하면 기본 제목 그대로
            pass
        for e in ents:
            e["title"] = ko_t.get(e["id"]) or e.get("title")
        return {"name": d.get("channel") or d.get("uploader"), "channel_id": d.get("channel_id"),
                "handle": d.get("uploader_id"), "subs": d.get("channel_follower_count"),
                "videos": [{"id": e.get("id"), "title": e.get("title"), "views": e.get("view_count")} for e in ents]}
    st = _cached("stats2", url, go, 24)
    if not st or st.get("_fail") or not st.get("channel_id"):
        return None
    st = dict(st)
    views = [v["views"] for v in st["videos"] if isinstance(v.get("views"), (int, float))]
    st["n"] = len(st["videos"])
    st["median_views"] = statistics.median(views) if views else None
    st["max_views"] = max(views) if views else None
    feed = rss(st["channel_id"])
    st["rss_titles"] = [e["title"] for e in feed]
    shorts = [e for e in feed if e.get("short")]
    dates = sorted(_dt(e["published"]) for e in shorts if e.get("published"))
    if len(dates) >= 2:
        span = max((dates[-1] - dates[0]).total_seconds() / 86400, 1.0)
        st["per_week"] = round(len(dates) / span * 7, 1)
    else:
        st["per_week"] = None
    st["last_upload"] = dates[-1].date().isoformat() if dates else None
    lang_titles = st["rss_titles"] or [v["title"] for v in st["videos"]]
    st["lang"] = lang_of(lang_titles)
    st["ko_ratio"] = round(ko_ratio(lang_titles), 2)
    st["url"] = f"https://www.youtube.com/channel/{st['channel_id']}"
    return st


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


