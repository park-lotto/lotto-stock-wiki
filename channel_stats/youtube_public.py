# -*- coding: utf-8 -*-
"""유튜브 공개 데이터(YouTube Data API v3, 키만 — 채널 허용 불필요). collect() 가 부른다.
채널 → 업로드 재생목록 → 영상 전부(Buffer 이전 것까지) → 제목·길이·게시일·조회/좋아요/댓글.
★시청시간·유지율·유입경로는 여기 없다(유튜브 애널리틱스 = 채널 허용 필요, 2단계).
"""
import json, os, re, urllib.parse, urllib.request

API = "https://www.googleapis.com/youtube/v3/"


def api_keys(env_path):
    """.env 의 YOUTUBE_API_KEY* (쿼터가 키마다 따로라 차례로 돈다)."""
    try:
        txt = open(env_path, encoding="utf-8").read()
    except FileNotFoundError:
        return []
    return [v.strip().strip('"') for _, v in re.findall(r"^(YOUTUBE_API_KEY[_0-9]*)=(.+)$", txt, re.M) if v.strip()]


class YT:
    def __init__(self, keys):
        self.keys, self.i = list(keys), 0

    def get(self, ep, **q):
        last = None
        for _ in range(len(self.keys)):
            q["key"] = self.keys[self.i]
            try:
                with urllib.request.urlopen(API + ep + "?" + urllib.parse.urlencode(q), timeout=30) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                last = e
                if e.code in (403, 429):          # 쿼터·키 문제 → 다음 키
                    self.i = (self.i + 1) % len(self.keys)
                    continue
                raise
        raise RuntimeError(f"유튜브 키 전부 실패: {last}")

    def channel(self, cid):
        it = self.get("channels", part="snippet,statistics,contentDetails", id=cid)["items"][0]
        return {"title": it["snippet"]["title"], "uploads": it["contentDetails"]["relatedPlaylists"]["uploads"],
                "subs": int(it["statistics"].get("subscriberCount", 0)), "views": int(it["statistics"].get("viewCount", 0)),
                "videos": int(it["statistics"].get("videoCount", 0)), "thumb": it["snippet"]["thumbnails"]["default"]["url"]}

    def upload_ids(self, playlist):
        ids, tok = [], None
        while True:
            q = dict(part="contentDetails", playlistId=playlist, maxResults=50)
            if tok:
                q["pageToken"] = tok
            r = self.get("playlistItems", **q)
            ids += [x["contentDetails"]["videoId"] for x in r["items"]]
            tok = r.get("nextPageToken")
            if not tok:
                return ids

    def videos(self, ids):
        out = []
        for i in range(0, len(ids), 50):
            r = self.get("videos", part="snippet,contentDetails,statistics", id=",".join(ids[i:i + 50]))
            for it in r["items"]:
                st, sn = it["statistics"], it["snippet"]
                out.append({"id": it["id"], "title": sn["title"], "published": sn["publishedAt"],
                            "duration": _secs(it["contentDetails"]["duration"]),
                            "thumb": (sn["thumbnails"].get("medium") or sn["thumbnails"]["default"])["url"],
                            "views": int(st.get("viewCount", 0)), "likes": int(st.get("likeCount", 0)),
                            "comments": int(st.get("commentCount", 0))})
        return out


def _secs(iso):
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def video_id(link):
    m = re.search(r"(?:shorts/|v=|youtu\.be/)([\w-]{11})", link or "")
    return m.group(1) if m else None
