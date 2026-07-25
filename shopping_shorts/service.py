"""수집 오케스트레이션: 채널→Apify→랭킹→저장→CSV 아카이브."""
import csv
from pathlib import Path
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from shopping_shorts.config import (DB_PATH, WINDOW_HOURS, DRAFT_BATCH_SIZE, MAX_CHANNELS,
                                    YOUTUBE_WINDOW_HOURS, YOUTUBE_MAX_PER_KW,
                                    DEAD_AFTER_DAYS, CENSUS_RESULTS_PER_CHANNEL)
from shopping_shorts.channels import load_channels, merge_tracked, select_tracked
from shopping_shorts.apify_client import fetch_reels
from shopping_shorts.ranking import build_items, build_youtube_items, build_tiktok_items, apply_grades
from shopping_shorts.store import Store
from shopping_shorts.comment_gen import generate as _gen_comments
from shopping_shorts import ai_categorize, topic_grouper
from shopping_shorts.youtube_client import search_shorts as yt_search, fetch_channel_shorts as yt_fetch_channel
from shopping_shorts.youtube_category_presets import preset_keywords
from shopping_shorts.tiktok_client import fetch_account_videos as tt_fetch
from shopping_shorts.tiktok_search import search_full as tt_search_full

TIKTOK_SEARCH_COUNT_DEFAULT = 50   # 언어당 fetch 개수(설정 tiktok_search_count로 오버라이드)
_TIKTOK_LANG_KINDS = {"ko", "en", "ja", "zh", "ru"}   # 키워드 시드의 언어코드 kind

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


def _collect_youtube(categories=None):
    """유튜브 카테고리 프리셋 + 수동 키워드 시드(발굴) + 계정 시드(채널기반) → 조회수 랭킹.

    categories=None → 프리셋 전 카테고리 union(전체 딸깍) / ["혼합형"] → 그 카테고리만.
    프리셋은 lang=ko로 검색. 수동 키워드 시드(kind=언어코드)·계정 시드는 항상 함께 수집.
    세 경로 raw를 video_id로 중복제거 후 공통 파이프라인."""
    store = Store(DB_PATH)
    seeds = store.list_seeds("youtube")
    _LANGS = {"ko", "en", "ja", "zh", "ru"}
    by_lang = {}
    accounts = []
    for s in seeds:
        if s["kind"] == "account":
            accounts.append(s["value"])
        else:
            lang = s["kind"] if s["kind"] in _LANGS else "ko"
            by_lang.setdefault(lang, []).append(s["value"])
    now = datetime.now(timezone.utc)
    after = (now - timedelta(hours=YOUTUBE_WINDOW_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw = []
    # 카테고리 프리셋(한국어) — 딸깍 수집의 핵심
    preset = preset_keywords(categories)
    if preset:
        raw.extend(yt_search(preset, after, max_per_kw=YOUTUBE_MAX_PER_KW, lang="ko"))
    # 수동 키워드 시드(언어별)
    for lang, kws in by_lang.items():
        raw.extend(yt_search(kws, after, max_per_kw=YOUTUBE_MAX_PER_KW, lang=lang))
    # 계정 시드(채널기반)
    for acc in accounts:
        raw.extend(yt_fetch_channel(acc, cache_get=store.yt_cache_get,
                                    cache_put=store.yt_cache_put))
    # video_id 중복제거(프리셋·수동·계정 겹칠 수 있음) — 첫 등장 우선
    seen, deduped = set(), []
    for r in raw:
        vid = r.get("video_id")
        if not vid or vid in seen:
            continue
        seen.add(vid)
        deduped.append(r)
    items = build_youtube_items(
        deduped,
        prev_base=lambda sc: store.prev_base_platform("youtube", sc),
        prev_delta=lambda sc: store.prev_delta_platform("youtube", sc),
        now=now, window_hours=YOUTUBE_WINDOW_HOURS,
    )
    apply_grades(items)
    run_date = now.strftime("%Y-%m-%d %H:%M")
    store.save_run_platform("youtube", run_date,
                            [{"shortcode": i["shortcode"], "base": i["base_count"], "delta": i["delta"]} for i in items])
    store.save_last_run_platform("youtube", items, now.isoformat())
    return items


def _collect_tiktok(include_paid_keywords=False):
    """틱톡 시드 계정(@handle)들의 최근 영상 → 조회수 기반 랭킹(무료 yt-dlp).

    include_paid_keywords=False(기본): **무료 경로만** — 계정 시드(yt-dlp)만 훑는다.
    키워드 시드 검색은 Apify 건당과금이라 자동 수집에서 뺐다(2026-07-24 "과금 없는 구조").
    코드는 지우지 않는다 — 관리자가 명시로 켤 때만(True) 돈다.
    """
    store = Store(DB_PATH)
    seeds = store.list_seeds("tiktok")
    if not seeds:
        return []
    now = datetime.now(timezone.utc)
    raw = []
    # 계정 시드(@handle) — yt-dlp 무료 수집(기존 경로)
    for acc in [s["value"] for s in seeds if s["kind"] == "account"]:
        raw.extend(tt_fetch(acc))          # 실패 계정은 tiktok_client가 빈 리스트 반환
    # 키워드 시드 — kind=언어코드(ko/en/ja/zh/ru)별로 저장된 값을 그대로 검색(2026-07-14).
    # 5개국어 자동확장이 아니라 사용자가 켠 언어만; 비한국어 시드는 등록 시 이미 그 언어로
    # 번역돼 저장됨(UI addSeed). 언어당 tiktok_search_count(기본 50)개. 계정 경로와 같은
    # raw 스키마라 아래 build_tiktok_items로 함께 흘러간다.
    lang_seeds = [s["value"] for s in seeds if s["kind"] in _TIKTOK_LANG_KINDS]
    if include_paid_keywords and lang_seeds:
        count = int(store.get_setting("tiktok_search_count", TIKTOK_SEARCH_COUNT_DEFAULT))
        for kw in lang_seeds:
            raw.extend(tt_search_full(kw, max_results=count))
    items = build_tiktok_items(
        raw,
        prev_base=lambda sc: store.prev_base_platform("tiktok", sc),
        prev_delta=lambda sc: store.prev_delta_platform("tiktok", sc),
        now=now, window_hours=YOUTUBE_WINDOW_HOURS,   # 틱톡도 14일 창(유튜브와 동일 근거)
    )
    apply_grades(items)
    run_date = now.strftime("%Y-%m-%d %H:%M")
    store.save_run_platform("tiktok", run_date,
                            [{"shortcode": i["shortcode"], "base": i["base_count"], "delta": i["delta"]} for i in items])
    store.save_last_run_platform("tiktok", items, now.isoformat())
    return items


def collect(platform="instagram", categories=None, limit_channels=None):
    """1회 수집 실행 → 지표·등급 채워진 항목 리스트 반환 + DB 저장.

    platform: "instagram"(기본, 엑셀 채널 기반) | "youtube"(키워드 시드 기반,
    _collect_youtube()로 분기).
    limit_channels: 테스트/절약용 채널 수 상한 (None=전체). 댓글 draft 생성은
    포함하지 않음 — 호출부(app.py)가 generate_missing_drafts()를 별도로(백그라운드)
    호출해야 한다.
    """
    if platform == "youtube":
        return _collect_youtube(categories)
    if platform == "tiktok":
        return _collect_tiktok()
    if platform != "instagram":
        return []   # 미구현 플랫폼이 인스타 Apify 스크레이프로 흘러들지 않게

    channels = load_channels()

    # 활동성 선별(2026-07-22): 생존+측정대기만 긁고 사망(센서스 판정)·수동제거는 뺀다.
    # 팔로워 컷 없음. 센서스 전(활동테이블 빈 상태)엔 전원 측정대기라 전 채널 = 초기 안전동작.
    # 엑셀 원본은 안 건드리는 소프트 관리 — 제외/추가/사망 모두 DB에서만.
    _store = Store(DB_PATH)
    channels = select_tracked(channels, _store.discovered_channels(),
                              removed=_store.removed_usernames(),
                              dead=_store.dead_usernames())

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

    # 같은 주제 모아보기(2026-07-13) — 부가기능이라 실패해도 수집 자체는 그대로.
    # run_tag=날짜 단위(하루 여러 번 돌려도 같은 그룹 접두어 유지).
    topic_map = topic_grouper.group_items(all_items, run_tag=now.strftime("%Y-%m-%d"))
    store.save_topic_groups(topic_map)

    run_date = now.strftime("%Y-%m-%d %H:%M")
    store.save_run(run_date, [
        {"shortcode": i["shortcode"], "username": i["username"],
         "comments": i["comments"], "delta": i["delta"]}
        for i in all_items
    ])
    _export_csv(all_items, run_date)  # 날짜별 CSV 아카이브
    return all_items


def _norm_u(username):
    return (username or "").strip().lstrip("@").lower()


def _record_activity(seen, username, item, reel):
    """센서스에서 본 릴스 1건으로 채널 활동레코드 갱신(채널당 최고 점수 + 최신 시각)."""
    u = _norm_u(username)
    views = item.get("views") or 0
    comments = item.get("comments") or 0
    density = (comments / views) if views > 0 else 0.0   # 참여밀도(조회 없으면 0)
    age = item.get("age_hours") or 0
    recency = max(0.0, 1 - age / (DEAD_AFTER_DAYS * 24))  # 최근일수록 1
    score = density * (1 + recency)
    ts = reel.get("timestamp")
    cur = seen.get(u)
    if cur is None:
        seen[u] = {"username": username, "alive": True, "last_post_at": ts,
                   "engagement_density": density, "activity_score": score}
        return
    if score > cur["activity_score"]:
        cur["activity_score"] = score
        cur["engagement_density"] = density
    if ts and (not cur["last_post_at"] or ts > cur["last_post_at"]):
        cur["last_post_at"] = ts


def census():
    """전수 센서스(2026-07-22) — 전 채널(팔로워/사망 필터 없음)을 긁어 활동성 판정.

    최근 DEAD_AFTER_DAYS일 내 릴스를 반환한 채널 = 생존, 0건 = 사망. 전체 랭킹과
    사망목록을 즉시 돌려주고, DB에 반영할 활동레코드(activity_records)도 함께 반환한다
    — 호출부(app.py)가 이걸 background로 upsert해 "정리를 뒤에서" 처리한다. 하드삭제 없음.
    Apify 실패 시 예외는 호출부로 전파(활동테이블 미갱신 → 사망 오판 안 함)."""
    store = Store(DB_PATH)
    excel = load_channels()
    # 마스터 = 엑셀 전체 ∪ 발굴/등록, 수동제거만 제외. 사망 채널도 포함해 재확인(=부활 기회).
    master = select_tracked(excel, store.discovered_channels(),
                            removed=store.removed_usernames(), dead=set())
    meta_by_user = {c["username"]: c for c in master}
    usernames = list(meta_by_user.keys())

    reels = fetch_reels(usernames, results_per_channel=CENSUS_RESULTS_PER_CHANNEL,
                        only_newer_than=f"{DEAD_AFTER_DAYS} days")

    now = datetime.now(timezone.utc)
    all_items = []
    seen_alive = {}   # 정규화 username -> 활동레코드
    for r in reels:
        user = r.get("ownerUsername") or r.get("username")
        meta = meta_by_user.get(user)
        if not meta:
            continue
        items = build_items([r], meta, prev_comments=store.prev_comments,
                            prev_delta=store.prev_delta, now=now,
                            window_hours=DEAD_AFTER_DAYS * 24)
        for it in items:
            # 전수조사 참여밀도 = (좋아요+댓글)/조회수 (영상별). build_items의 기본
            # density는 댓글÷팔로워인데 릴스 스크래퍼엔 팔로워가 없어 전부 0이 된다
            # → 조회수 기준으로 덮어써야 소형채널도 밀도로 상위에 오른다.
            v = it.get("views") or 0
            it["density"] = ((it.get("likes") or 0) + (it.get("comments") or 0)) / v if v else 0.0
            all_items.append(it)
            _record_activity(seen_alive, meta["username"], it, r)
    apply_grades(all_items)
    # 채널당 상한이 아니라 영상별 참여밀도 내림차순 → 소형채널의 뜨거운 영상이 안 밀린다.
    all_items.sort(key=lambda i: i.get("density") or 0.0, reverse=True)

    alive_norm = set(seen_alive.keys())
    dead_channels = [c for c in master if _norm_u(c["username"]) not in alive_norm]
    prior_dead = store.dead_usernames()
    revived_n = sum(1 for u in alive_norm if u in prior_dead)

    activity_records = list(seen_alive.values()) + [
        {"username": c["username"], "alive": False} for c in dead_channels]

    return {
        "items": all_items,
        "dead": dead_channels,
        "activity_records": activity_records,
        "scanned_n": len(usernames),
        "alive_n": len(alive_norm),
        "dead_n": len(dead_channels),
        "revived_n": revived_n,
    }
