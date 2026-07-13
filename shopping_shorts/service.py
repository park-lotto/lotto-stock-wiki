"""수집 오케스트레이션: 채널→Apify→랭킹→저장→CSV 아카이브."""
import csv
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from shopping_shorts.config import DB_PATH, WINDOW_HOURS, DRAFT_BATCH_SIZE, MAX_CHANNELS
from shopping_shorts.channels import load_channels
from shopping_shorts.apify_client import fetch_reels
from shopping_shorts.ranking import build_items, apply_grades
from shopping_shorts.store import Store
from shopping_shorts.comment_gen import generate as _gen_comments
from shopping_shorts import ai_categorize

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


def next_draft_targets(items, store, limit=DRAFT_BATCH_SIZE):
    """랭킹 상위권 중 "아직 draft 없고 완료(댓글 단 것) 처리도 안 된" 항목을
    score 내림차순으로 limit개 골라 반환(2026-07-09).

    고정된 페이지네이션(41~80번 다음 배치 식)이 아니라 매번 다시 계산하는
    이유: 상위 40개 중 일부가 완료 처리돼 큐에서 빠지거나, Gemini 실패로
    draft가 안 생긴 항목이 있으면 다음 "댓글 더 생성" 클릭 때 그 자리를
    채워야 한다 — 41~80번을 고정으로 넘어가버리면 실패한 상위권 항목이
    영영 재시도되지 않는다."""
    commented = store.commented_set()
    ranked = sorted(items, key=lambda i: (i.get("score") or 0), reverse=True)
    pending = [
        i for i in ranked
        if i["shortcode"] not in commented and not store.get_drafts(i["shortcode"])
    ]
    return pending[:limit]


_DRAFT_WORKERS = 4  # Gemini "general" 그룹 계정 풀 크기(APIFY_TOKENS와 별개)와 맞춤


def _generate_one(it):
    """항목 하나 처리 — 이미 draft 있으면 스킵, 생성되면 저장. 스레드풀에서 병렬 호출됨."""
    store = Store(DB_PATH)
    sc = it["shortcode"]
    if store.get_drafts(sc):
        return
    drafts = _gen_comments(it.get("caption", ""), it.get("name"), it.get("category"))
    if drafts:
        store.save_drafts(sc, drafts)


def generate_missing_drafts(items):
    """댓글 draft 미리 생성 (기존 draft 없는 항목만 — 재수집 시 중복 호출·비용 방지).
    항목들을 스레드풀로 병렬 처리한다(2026-07-09) — 순차 처리 시 한 항목이
    쿼터에 걸려 재시도하는 동안 나머지가 전부 대기해야 했던 문제 완화, Gemini
    계정 풀(4개)을 동시에 활용해 처리 속도도 개선.

    Gemini 호출 1건당 최대 수십 초(쿼터 걸리면 재시도 대기)라 항목이 많으면
    (443채널 전체수집 시 수백 건) 시간이 걸린다 — collect()의 HTTP 응답을 막지
    않도록 app.py에서 BackgroundTasks로 분리 호출한다(2026-07-09, "수집 버튼
    눌렀는데 안 끝남" 사고 이후 분리).

    알려진 한계(2026-07-09 최종 리뷰): 수집 버튼에 쿨다운이 없어(직원 테스트용이라
    의도적으로 미적용) 이 백그라운드 작업이 끝나기 전에 「지금 수집」을 다시 누르면
    같은 shortcode에 대해 두 번째 generate_missing_drafts()가 동시에 돌 수 있다.
    get_drafts() 체크가 두 호출 모두 "없음"으로 볼 수 있어 Gemini 중복호출(비용 낭비)
    가능성 있음 — 다만 idempotent라 데이터 손상은 없고, 다음 수집에서 자연 정리됨."""
    with ThreadPoolExecutor(max_workers=_DRAFT_WORKERS) as pool:
        list(pool.map(_generate_one, items))


def collect(limit_channels=None):
    """1회 수집 실행 → 지표·등급 채워진 항목 리스트 반환 + DB 저장.

    limit_channels: 테스트/절약용 채널 수 상한 (None=전체). 댓글 draft 생성은
    포함하지 않음 — 호출부(app.py)가 generate_missing_drafts()를 별도로(백그라운드)
    호출해야 한다.
    """
    channels = load_channels()

    # 발굴로 추가한 채널을 엑셀 목록과 union하고, 죽은(추적제외) 채널은 뺀다
    # (2026-07-12). 엑셀 원본은 안 건드리는 소프트 관리 — 제외/추가 모두 DB에서만.
    _store = Store(DB_PATH)
    known = {c["username"].strip().lstrip("@").lower() for c in channels}
    for d in _store.discovered_channels():
        if d["username"].strip().lstrip("@").lower() not in known:
            channels.append(d)
    removed = _store.removed_usernames()
    if removed:
        channels = [c for c in channels
                    if c["username"].strip().lstrip("@").lower() not in removed]

    # 엑셀(load_channels에서 이미 MAX_CHANNELS 캡됨)+발굴채널 union 후 다시 캡
    # (2026-07-13) — union으로 발굴채널이 계속 늘면 엑셀 캡을 우회해 무한정
    # 커지던 구멍. 순서(엑셀 먼저, 발굴채널은 최신 추가순)를 유지한 채 자르므로
    # 엑셀은 그대로 유지되고 오래된 발굴채널부터 자연스럽게 빠진다.
    if len(channels) > MAX_CHANNELS:
        channels = channels[:MAX_CHANNELS]

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

    # 캡션 기반 AI 재분류(주). 키워드(build_items)의 stray-단어 오판을 교정한다.
    # 실패·무키면 no-op → 키워드 결과 유지(폴백). (2026-07-13)
    ai_categorize.reclassify(all_items)

    run_date = now.strftime("%Y-%m-%d %H:%M")
    store.save_run(run_date, [
        {"shortcode": i["shortcode"], "username": i["username"],
         "comments": i["comments"], "delta": i["delta"]}
        for i in all_items
    ])
    _export_csv(all_items, run_date)  # 날짜별 CSV 아카이브
    return all_items
