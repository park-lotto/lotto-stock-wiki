"""카테고리별 상위 영상의 유튜브 채널을 뽑아 벤치(account 시드)로 대량 등록 + csv.

렌즈(SerpApi) 안 씀 — 유튜브 검색 결과에 이미 channel_id가 붙어 있어 그대로 수확한다.
카테고리 프리셋 키워드로 검색 → 조회수 상위 N개 영상 → 소속 채널 유니크 → account 시드 등록.
사장님이 /refs에서 삭제·추가로 다듬는 걸 전제로 "먼저 많이" 모으는 1차 수집.

사용: python -m scripts.harvest_channels_by_category [top_n=30] [--dry]
  --dry: 등록 안 하고 csv/집계만(비용 미리보기)
"""
import sys
import csv
import io
from datetime import datetime, timezone, timedelta

from shopping_shorts import youtube_category_presets as presets
from shopping_shorts.youtube_client import search_shorts
from shopping_shorts.config import YOUTUBE_WINDOW_HOURS, YOUTUBE_MAX_PER_KW, DB_PATH
from shopping_shorts.store import Store


def harvest(top_n=30, dry=False):
    now = datetime.now(timezone.utc)
    after = (now - timedelta(hours=YOUTUBE_WINDOW_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    store = Store(DB_PATH)
    existing = {(s["value"] or "").lower() for s in store.list_seeds("youtube")
                if s["kind"] == "account"}

    # channel_id -> row(첫 등장 카테고리·최고조회 영상 기준)
    channels = {}
    per_cat = {}
    for cat in presets.CATEGORY_KEYWORDS:
        kws = presets.preset_keywords([cat])
        raw = search_shorts(kws, after, max_per_kw=YOUTUBE_MAX_PER_KW, lang="ko")
        # video_id 중복제거 후 조회수 상위 top_n 영상
        seen_v, vids = set(), []
        for r in sorted(raw, key=lambda x: x.get("views", 0), reverse=True):
            v = r.get("video_id")
            if not v or v in seen_v:
                continue
            seen_v.add(v)
            vids.append(r)
            if len(vids) >= top_n:
                break
        cat_ch = set()
        for r in vids:
            cid = r.get("channel_id")
            if not cid:
                continue
            cat_ch.add(cid)
            if cid not in channels:
                channels[cid] = {
                    "category": cat,
                    "channel_title": r.get("channel_title") or "",
                    "channel_id": cid,
                    "channel_url": f"https://www.youtube.com/channel/{cid}",
                    "top_views": r.get("views", 0),
                    "sample_title": (r.get("title") or "")[:60],
                }
        per_cat[cat] = len(cat_ch)

    added = 0
    for cid, row in channels.items():
        url = row["channel_url"]
        if url.lower() in existing:
            row["status"] = "이미있음"
            continue
        if not dry:
            store.add_seed("youtube", "account", url)
            existing.add(url.lower())
        added += 1
        row["status"] = "등록" if not dry else "등록예정"

    # csv 문자열
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["category", "channel_title", "channel_id", "channel_url",
                "top_views", "sample_title", "status"])
    for row in sorted(channels.values(), key=lambda x: (x["category"], -x["top_views"])):
        w.writerow([row["category"], row["channel_title"], row["channel_id"],
                    row["channel_url"], row["top_views"], row["sample_title"], row["status"]])
    return {"per_cat": per_cat, "total_channels": len(channels),
            "added": added, "csv": buf.getvalue()}


def harvest_from_ranking(dry=False):
    """저장된 last_run 랭킹에서 유니크 채널을 뽑아 등록(API/쿼터 0회).

    build_youtube_items가 username=channel_id를 이미 담아 저장하므로 재검색 없이
    수백 개 채널을 무료로 수확한다. 검색 기반 harvest보다 우선 쓰는 게 좋다."""
    store = Store(DB_PATH)
    items, _ = store.load_last_run_platform("youtube")
    existing = {(s["value"] or "").lower() for s in store.list_seeds("youtube")
                if s["kind"] == "account"}
    seen, added = set(), 0
    for i in items:
        cid = i.get("username")
        if not cid or cid in seen:
            continue
        seen.add(cid)
        url = f"https://www.youtube.com/channel/{cid}"
        if url.lower() in existing:
            continue
        if not dry:
            store.add_seed("youtube", "account", url)
            existing.add(url.lower())
        added += 1
    return {"unique": len(seen), "added": added}


def main(argv):
    top_n = 30
    dry = "--dry" in argv
    if "--from-ranking" in argv:
        r = harvest_from_ranking(dry=dry)
        print(f"[harvest] 저장 랭킹에서 수확{' (DRY)' if dry else ''}: "
              f"유니크 {r['unique']}개 · {'등록예정' if dry else '신규등록'} {r['added']}개")
        return 0
    for a in argv:
        if a.isdigit():
            top_n = int(a)
    res = harvest(top_n=top_n, dry=dry)
    print(f"[harvest] 카테고리별 상위 {top_n} 영상 → 채널 수확{' (DRY)' if dry else ''}")
    for cat, n in res["per_cat"].items():
        print(f"  {cat}: 채널 {n}개")
    print(f"유니크 채널 총 {res['total_channels']}개 · {'등록예정' if dry else '신규등록'} {res['added']}개")
    print("----CSV----")
    print(res["csv"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
