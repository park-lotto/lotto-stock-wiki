"""자막 조사용 영상 고르기 — 채널별 상위 쇼츠 N편의 videoId를 뽑는다.

★키는 config.YOUTUBE_API_KEYS를 그대로 쓴다(0순위-B: 키 고르는 곳을 새로 만들지 않는다).
★search.list는 채널당 100유닛이라 20채널이면 2,000유닛 — 하루 한도(10,000) 안이다.

    py tools/caption_survey_pick.py C:/tmp/yt20.json C:/tmp/yt60.json 3
"""
import json
import sys
import time

import requests

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from shopping_shorts import config  # noqa: E402

SEARCH = "https://www.googleapis.com/youtube/v3/search"


def top_shorts(cid, n, keys):
    """채널의 조회수 상위 쇼츠 n편. 키가 막히면 다음 키로 넘어간다."""
    for k in keys:
        try:
            r = requests.get(SEARCH, params={
                "part": "snippet", "channelId": cid, "type": "video",
                "videoDuration": "short", "order": "viewCount",
                "maxResults": min(n * 3, 50), "key": k}, timeout=30)
        except Exception:
            continue
        if r.status_code == 403:      # 이 키 소진/권한 → 다음 키
            continue
        if r.status_code != 200:
            return []
        out = []
        for it in r.json().get("items", []):
            vid = (it.get("id") or {}).get("videoId")
            if vid:
                out.append({"video_id": vid,
                            "title": (it.get("snippet") or {}).get("title", "")})
            if len(out) >= n:
                break
        return out
    return []


def main():
    src, dst = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    keys = list(config.YOUTUBE_API_KEYS)
    if not keys:
        raise SystemExit("유튜브 키가 없다 — shopping_shorts/.env 확인")
    rows = json.load(open(src, encoding="utf-8"))
    out, miss = [], []
    for i, ch in enumerate(rows, 1):
        vids = top_shorts(ch["cid"], n, keys)
        if not vids:
            miss.append(ch["channel"])
        for v in vids:
            out.append({"channel": ch["channel"], "cid": ch["cid"], **v})
        print(f"[{i}/{len(rows)}] {ch['channel']}: {len(vids)}편", flush=True)
        time.sleep(0.2)
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n총 {len(out)}편 → {dst}")
    if miss:
        print(f"★못 가져온 채널 {len(miss)}: {', '.join(miss)}")


if __name__ == "__main__":
    main()
