"""수집 오케스트레이션: 채널→Apify→랭킹→저장→CSV 아카이브."""
import csv
from pathlib import Path
from datetime import datetime, timezone
from shopping_shorts.config import DB_PATH, WINDOW_HOURS
from shopping_shorts.channels import load_channels
from shopping_shorts.apify_client import fetch_reels
from shopping_shorts.ranking import build_items, apply_grades
from shopping_shorts.store import Store
from shopping_shorts.comment_gen import generate as _gen_comments

_CSV_FIELDS = ["name", "username", "category", "comments", "delta", "is_new",
               "speed", "accel", "density", "grade", "age_hours", "url", "inpock"]


def _export_csv(items, run_date):
    """수집분을 data/rankings/YYYY-MM-DD.csv로 저장 (소스 엑셀 미변경)."""
    out_dir = DB_PATH.parent / "rankings"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{run_date[:10]}.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=_CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(items)
    return path


def collect(limit_channels=None):
    """1회 수집 실행 → 지표·등급 채워진 항목 리스트 반환 + DB 저장.

    limit_channels: 테스트/절약용 채널 수 상한 (None=전체).
    """
    channels = load_channels()
    if limit_channels:
        channels = channels[:limit_channels]

    meta_by_user = {c["username"]: c for c in channels}
    usernames = list(meta_by_user.keys())

    reels = fetch_reels(usernames)  # 전체 채널 릴스 원본

    store = Store(DB_PATH)
    now = datetime.now(timezone.utc)
    all_items = []
    for r in reels:
        user = r.get("ownerUsername") or r.get("username")
        meta = meta_by_user.get(user)
        if not meta:
            continue
        items = build_items(
            [r], meta,
            prev_comments=store.prev_comments,
            prev_delta=store.prev_delta,
            now=now, window_hours=WINDOW_HOURS,
        )
        all_items.extend(items)

    apply_grades(all_items)

    # 댓글 draft 미리 생성 (기존 draft 없는 항목만 — 재수집 시 중복 호출·비용 방지)
    for it in all_items:
        sc = it["shortcode"]
        if not store.get_drafts(sc):
            drafts = _gen_comments(it.get("caption", ""), it.get("name"), it.get("category"))
            if drafts:
                store.save_drafts(sc, drafts)

    run_date = now.strftime("%Y-%m-%d %H:%M")
    store.save_run(run_date, [
        {"shortcode": i["shortcode"], "username": i["username"],
         "comments": i["comments"], "delta": i["delta"]}
        for i in all_items
    ])
    _export_csv(all_items, run_date)  # 날짜별 CSV 아카이브
    return all_items
