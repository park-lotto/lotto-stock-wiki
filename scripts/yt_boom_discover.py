# -*- coding: utf-8 -*-
"""유튜브 **대박 채널** 발굴 — 최근 7일 한국 쇼츠 중 조회수 10만+ 를 올린 채널을 수집 대상으로 넣는다.

★왜 (2026-09-15 사장님)
  "기본 터진다는 건 10만은 당연히 넘고 빠르게 100만 정도까지 가는 채널이다"
  "수집이 되면 우리 자산으로 놓고 어차피 랭킹 안에서 경합해서 위로 뜨는 거니까"

★실험으로 고른 방법 (2026-09-15)
  ① 추천 피드 따라가기(harvest_by_feed) — 우리 쇼핑 히트작 15편의 추천이 **뉴스·예능 채널**로 샜다
     (서버 IP·가정 IP 둘 다 같음 → 로그아웃 쇼츠 추천은 흔한 인기영상을 섞는다).
  ② 최근 7일 쇼츠를 **조회수순 검색**(키워드 20개) → 1,606편 중 10만+ 68편·채널 59개.
     등록 안 된 대박 채널(오렌지귤 구독 2,160에 육아템 70만·54만 등)이 잡혔다. → ②를 쓴다.

★자산으로 넣는 길은 **하나뿐**이다(0순위-B)
  채널을 유튜브 시드(platform_seeds youtube/account, 값=https://www.youtube.com/channel/UC…)로
  등록만 한다. 영상은 다음 매일 수집(daily_youtube_collect)이 가져와 랭킹에서 경합한다.
  랭킹 스냅샷을 여기서 직접 고치지 않는다 — 수집이 덮어써 두 벌이 어긋난다.

★거르는 것
  - 3분 넘는 영상, 제목·채널명에 한글이 없는 것
  - 사장님이 랭킹에서 🚫차단한 채널(removed_channels)
  - 채널 최근 업로드 25편 중 우리 카테고리(기타 제외)가 30% 미만인 채널
    ⚠️영상 제목 한 개로 가르지 않는다 — 실측 오렌지귤은 같은 채널 두 영상이 '기타'/'홈템'으로 갈렸다.

비용: 검색 20회×100 units + 조회 몇 콜 ≈ 2,100 units/일(키 1개 무료 한도 10,000 안).

사용:  python3 -m scripts.yt_boom_discover           # 미리보기(등록 안 함)
       python3 -m scripts.yt_boom_discover --apply   # 등록
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from scripts.harvest_by_feed import api            # noqa: E402 — 키 풀·403 로테이션은 한 곳에서
from shopping_shorts import categorize as cz        # noqa: E402
from shopping_shorts.config import DB_PATH          # noqa: E402
from shopping_shorts.store import Store             # noqa: E402

LOG = "/tmp/yt_boom_discover.log"
REPORT = os.path.join(BASE, "shopping_shorts", "data", "yt_boom_last.json")

QUERIES = ["다이소 꿀템", "살림템", "주방 꿀템", "발명품", "천재 발명품", "생활꿀팁", "청소 꿀팁", "자동차 꿀템",
           "신기한 제품", "쿠팡 추천템", "알리 꿀템", "캠핑 꿀템", "욕실 꿀템", "정리 꿀팁", "육아템", "자취 꿀템",
           "이거 모르면 손해", "절대 하지마세요", "역대급 아이템", "요리 꿀팁"]
MIN_VIEWS = 100_000          # 사장님 기준 "10만은 당연히 넘고"
DAYS = 7
MAX_DUR = 180
# 최근 25편 중 우리 카테고리 비율. ★0.4였다가 0.3으로(2026-09-15 서버 미리보기 실측):
#   오렌지귤(육아템 70만·54만)이 4/13=31%로 떨어졌다 — 분류기가 '육아템·천재 식집사' 제목을 '기타'로 본다.
#   0.3이어도 ChoiRakuLife 16%·연예인그거어디꺼 28%·알통맨 8%는 그대로 걸러진다.
CHANNEL_MIN_RATIO = 0.3
_HAN = re.compile(r"[가-힣]")


def log(msg):
    line = "[%s] %s" % (time.strftime("%m-%d %H:%M"), msg)
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _dur(iso):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    return (int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)) if m else 0


def find_boom_videos(now):
    after = (now - timedelta(days=DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids = {}
    for q in QUERIES:
        tok = None
        for _ in range(2):
            p = dict(part="snippet", type="video", q=q, order="viewCount", publishedAfter=after,
                     videoDuration="short", regionCode="KR", relevanceLanguage="ko", maxResults=50)
            if tok:
                p["pageToken"] = tok
            r = api("search", **p)
            if not r:
                break
            for it in r.get("items", []):
                ids.setdefault(it["id"]["videoId"], q)
            tok = r.get("nextPageToken")
            if not tok:
                break
    out = []
    idl = list(ids)
    for i in range(0, len(idl), 50):
        r = api("videos", part="snippet,statistics,contentDetails", id=",".join(idl[i:i + 50]))
        for v in (r or {}).get("items", []):
            sn = v["snippet"]
            views = int(v["statistics"].get("viewCount") or 0)
            if views < MIN_VIEWS or _dur(v["contentDetails"].get("duration")) > MAX_DUR:
                continue
            if not _HAN.search(sn["title"] + sn.get("channelTitle", "")):
                continue
            pub = datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00"))
            age_d = max((now - pub).total_seconds() / 86400, 0.25)
            out.append({"video_id": v["id"], "title": sn["title"], "channel_id": sn["channelId"],
                        "channel": sn.get("channelTitle", ""), "views": views, "age_d": round(age_d, 2),
                        "per_day": int(views / age_d), "query": ids[v["id"]]})
    log("검색 %d개 → 영상 %d편 중 %s+ %d편" % (len(QUERIES), len(ids), format(MIN_VIEWS, ","), len(out)))
    return out


def channel_ok(cid):
    """(통과, 채널명, 구독자, 우리카테고리 편수, 표본수)."""
    ch = api("channels", part="contentDetails,snippet,statistics", id=cid)
    if not ch or not ch.get("items"):
        return False, "", 0, 0, 0
    it = ch["items"][0]
    name = it["snippet"]["title"]
    subs = int(it["statistics"].get("subscriberCount") or 0)
    up = it["contentDetails"]["relatedPlaylists"].get("uploads")
    pl = api("playlistItems", part="snippet", playlistId=up, maxResults=25) if up else None
    titles = [x["snippet"]["title"] for x in (pl or {}).get("items", [])]
    if len(titles) < 5:
        return False, name, subs, 0, len(titles)
    good = sum(1 for t in titles if cz.categorize(name, t) != "기타")
    return good / len(titles) >= CHANNEL_MIN_RATIO, name, subs, good, len(titles)


def main():
    apply = "--apply" in sys.argv
    now = datetime.now(timezone.utc)
    store = Store(DB_PATH)
    seeds = {(s.get("value") or "").lower() for s in store.list_seeds("youtube") if s.get("kind") == "account"}
    removed = store.removed_usernames()
    vids = find_boom_videos(now)
    by_ch = {}
    for v in vids:
        by_ch.setdefault(v["channel_id"], []).append(v)
    report = {"at": now.isoformat(), "apply": apply, "channels": []}
    added = 0
    for cid, vs in sorted(by_ch.items(), key=lambda kv: -max(x["per_day"] for x in kv[1])):
        url = "https://www.youtube.com/channel/" + cid
        row = {"channel_id": cid, "channel": vs[0]["channel"], "videos": vs,
               "best_per_day": max(x["per_day"] for x in vs)}
        if url.lower() in seeds:
            row["status"] = "이미 등록"
        elif cid.lower() in removed:
            row["status"] = "차단된 채널"
        else:
            ok, name, subs, good, n = channel_ok(cid)
            row.update({"subs": subs, "shop": "%d/%d" % (good, n)})
            if not ok:
                row["status"] = "우리 카테고리 아님(%d/%d)" % (good, n)
            elif apply:
                store.add_seed("youtube", "account", url)
                seeds.add(url.lower())
                row["status"] = "등록"
                added += 1
            else:
                row["status"] = "등록 예정(미리보기)"
        report["channels"].append(row)
        log("  %-16s %-18s 하루 %9s회 · %s" % (row["status"][:16], row["channel"][:18],
                                            format(row["best_per_day"], ","), vs[0]["title"][:30]))
    try:
        with open(REPORT, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False)
    except OSError as e:
        log("리포트 저장 실패: %r" % (e,))
    log("끝 — 채널 %d개 · 새로 등록 %d개%s" % (len(by_ch), added, "" if apply else " (미리보기)"))


if __name__ == "__main__":
    main()
