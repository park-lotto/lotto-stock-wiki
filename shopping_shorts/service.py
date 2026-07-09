"""수집 오케스트레이션: 채널→Apify→랭킹→저장→CSV 아카이브."""
import csv
from pathlib import Path
from datetime import datetime, timezone
from shopping_shorts.config import DB_PATH, WINDOW_HOURS, DRAFT_BATCH_SIZE
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


def draft_batch(items, batch, batch_size=DRAFT_BATCH_SIZE):
    """score(종합 랭킹) 내림차순으로 정렬 후 batch번째(1-indexed) 구간만 잘라 반환.
    수집 직후엔 batch=1(상위 랭킹)만 자동 생성, 나머지는 "댓글 더 생성" 버튼으로
    batch=2,3,... 을 필요할 때만 이어서 생성해 Gemini 쿼터를 아낀다(2026-07-09)."""
    ranked = sorted(items, key=lambda i: (i.get("score") or 0), reverse=True)
    start = (batch - 1) * batch_size
    return ranked[start:start + batch_size]


def generate_missing_drafts(items):
    """댓글 draft 미리 생성 (기존 draft 없는 항목만 — 재수집 시 중복 호출·비용 방지).

    Gemini 호출 1건당 최대 수십 초(쿼터 걸리면 62초 재시도 대기)라 항목이
    많으면(443채널 전체수집 시 수백 건) 통째로 몇 분~수십 분이 걸린다 — collect()의
    HTTP 응답을 막지 않도록 app.py에서 BackgroundTasks로 분리 호출한다(2026-07-09,
    "수집 버튼 눌렀는데 안 끝남" 사고 이후 분리).

    알려진 한계(2026-07-09 최종 리뷰): 수집 버튼에 쿨다운이 없어(직원 테스트용이라
    의도적으로 미적용) 이 백그라운드 작업이 끝나기 전에 「지금 수집」을 다시 누르면
    같은 shortcode에 대해 두 번째 generate_missing_drafts()가 동시에 돌 수 있다.
    get_drafts() 체크가 두 호출 모두 "없음"으로 볼 수 있어 Gemini 중복호출(비용 낭비)
    가능성 있음 — 다만 idempotent라 데이터 손상은 없고, 다음 수집에서 자연 정리됨."""
    store = Store(DB_PATH)
    for it in items:
        sc = it["shortcode"]
        if not store.get_drafts(sc):
            drafts = _gen_comments(it.get("caption", ""), it.get("name"), it.get("category"))
            if drafts:
                store.save_drafts(sc, drafts)


def collect(limit_channels=None):
    """1회 수집 실행 → 지표·등급 채워진 항목 리스트 반환 + DB 저장.

    limit_channels: 테스트/절약용 채널 수 상한 (None=전체). 댓글 draft 생성은
    포함하지 않음 — 호출부(app.py)가 generate_missing_drafts()를 별도로(백그라운드)
    호출해야 한다.
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

    run_date = now.strftime("%Y-%m-%d %H:%M")
    store.save_run(run_date, [
        {"shortcode": i["shortcode"], "username": i["username"],
         "comments": i["comments"], "delta": i["delta"]}
        for i in all_items
    ])
    _export_csv(all_items, run_date)  # 날짜별 CSV 아카이브
    return all_items
