"""FastAPI: 수집 API + 정적 프론트 서빙."""
import base64
import hmac
import hashlib
import ipaddress
import os
import re
import secrets
import shutil
import socket
import tempfile
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import requests
from fastapi import BackgroundTasks, FastAPI, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from shopping_shorts.service import collect, generate_missing_drafts, next_draft_targets
from shopping_shorts.outreach import build_queue
from shopping_shorts.store import Store
from shopping_shorts.auto_run import run_auto_job, default_stages
from shopping_shorts.config import DB_PATH, DRAFT_BATCH_SIZE, PUBLIC_BASE_URL
from shopping_shorts.frame_extract import (download_video, extract_frames,
                                           extract_frame_at, extract_grid_frames)
from shopping_shorts.script_extract import extract_script
from shopping_shorts.structure_analyze import analyze_structure
from shopping_shorts.categorize import categorize, KEYWORDS as CATEGORY_KEYWORDS
from shopping_shorts import script_generate
from shopping_shorts.apify_client import fetch_single_reel, fetch_reels, fetch_profiles
from shopping_shorts import discovery, instagram_search
from shopping_shorts.channels import load_channels, username_from_url
from shopping_shorts.video_analysis import (analyze_video, translate_keyword, cn_search_keyword,
                                            cn_search_keyword_vision, judge_same_product,
                                            cn_search_candidates)
from shopping_shorts.product_identify import fetch_lens_lines, identify_product_from_lines
from shopping_shorts.search_links import build_search_links, lens_search_url
from shopping_shorts import mix_pipeline
from shopping_shorts.mix_pipeline import (run_mix_job, run_render, run_preview, retype_mix_job,
                                          _source_video_id, resynth_tts_job, resynth_one_beat,
                                          run_clean_sources, _resolve_sources)
from shopping_shorts.lens_discover import search_similar_videos, upload_frame
from shopping_shorts import douyin_search, xiaohongshu_search
from shopping_shorts import youtube_search
from shopping_shorts.config import APIFY_TOKENS
from shopping_shorts.media_download import resolve_media_url, download_any, probe_grab_meta
from shopping_shorts import edit_plan as _edit_plan
from shopping_shorts import voice_presets, audio_post
from shopping_shorts.tts import synthesize_tts
from shopping_shorts import tts, asr_check
from shopping_shorts.narration_naturalize import naturalize as _naturalize
from shopping_shorts import frame_extract, scene_assets, scene_cut
from shopping_shorts import effect_match, remotion_render, points
from shopping_shorts import video_assemble
from shopping_shorts import seo_generate, seo_probe
from shopping_shorts import thumb_title
import uuid

app = FastAPI(title="쇼핑쇼츠 레퍼런스 랭킹")


@app.on_event("startup")
def _seed_voice_presets():
    """기동 시 큐레이션 프리셋을 DB로 upsert(idempotent)."""
    try:
        voice_presets.seed_presets(Store(DB_PATH))
    except Exception:
        pass  # seed 실패가 앱 기동을 막지 않게

# ── 틱톡 키워드검색 노브 기본값 + 비용 상수 (2026-07-14) ──
# clockworks/tiktok-scraper = $1.70/1,000건 → 1건 $0.0017 (조사확정).
_TIKTOK_SEARCH_COUNT_DEFAULT = 50      # 언어당 fetch 개수
_TIKTOK_DAILY_LIMIT_DEFAULT = 10       # 사용자별 하루 수집 횟수
_TIKTOK_MONTH_BUDGET_DEFAULT = 5.0     # 월 예산 상한($) — 넘으면 킬스위치
_TIKTOK_COST_PER_ITEM = 0.0017
_TIKTOK_LANG_KINDS = {"ko", "en", "ja", "zh", "ru"}   # 키워드 시드의 언어코드 kind

# ── 렌즈(SerpApi Google Lens) 유사영상 발굴 (2026-07-14) ──
_LENS_MONTH_LIMIT_DEFAULT = 100   # SerpApi 무료 100회/월


def _tiktok_knobs(store):
    """설정 3노브를 타입 정규화해 반환(없으면 기본값)."""
    return {
        "search_count": int(store.get_setting("tiktok_search_count", _TIKTOK_SEARCH_COUNT_DEFAULT)),
        "daily_limit": int(store.get_setting("tiktok_daily_limit", _TIKTOK_DAILY_LIMIT_DEFAULT)),
        "month_budget": float(store.get_setting("tiktok_month_budget", _TIKTOK_MONTH_BUDGET_DEFAULT)),
    }


_MEDIA_CODE_RE = re.compile(r"/(?:p|reel|reels)/([A-Za-z0-9_-]+)")


def _media_code(url):
    """인스타 URL에서 미디어코드만 추출("/p/"·"/reel/"·"/reels/" 전부 대응, 쿼리
    파라미터 무시) — 사용자가 인스타에서 그대로 복사한 URL(추적파라미터·reel
    형식 포함)이 저장된 shortcode(우리가 만든 url 형식)와 문자열이 달라도
    같은 항목으로 매칭되게 함(2026-07-09, "해당 항목 없음" 오탐 수정)."""
    m = _MEDIA_CODE_RE.search(url or "")
    return m.group(1) if m else (url or "")


@app.post("/api/collect")
def api_collect(request: Request, background_tasks: BackgroundTasks, limit: int | None = None, platform: str = "instagram"):
    """지금 수집 버튼. limit=채널 수 상한(테스트용). platform=플랫폼(기본 인스타).

    댓글 draft 생성(항목당 Gemini 호출, 쿼터 걸리면 62초 대기)은 응답 후
    백그라운드로 넘긴다 — 랭킹 결과는 Apify 수집 즉시 반환, 소통 큐 draft는
    뒤이어 채워짐(2026-07-09, 443채널 전체수집이 draft생성 때문에 응답을
    막아버리던 문제 수정).

    Gemini 쿼터 절약을 위해 draft는 랭킹 상위 40개만 자동 생성한다(2026-07-09).
    나머지(또는 실패해서 draft 없는 상위권 항목)는 /api/generate_drafts 버튼으로
    필요할 때만 이어서 생성.

    platform != "instagram"인 경우 댓글 draft/save_last_run(인스타 전용
    캐시)은 건너뛴다 — 유튜브 등은 _collect_youtube가 자체적으로 저장한다.

    platform == "tiktok"이면 키워드검색이 Apify 유료라 남용/비용 가드를 건다:
    ① 월예산 킬스위치(초과 시 429 budget_exceeded) ② 사용자별 하루 상한
    (초과 시 429 daily_limit). 통과 후 수집하면 하루카운트 +1, 추정비용 누적."""
    if platform == "tiktok":
        guard = Store(DB_PATH)
        knobs = _tiktok_knobs(guard)
        now = datetime.now(timezone.utc)
        month, day = now.strftime("%Y-%m"), now.strftime("%Y-%m-%d")
        cid = _cid(request)
        if guard.tiktok_month_spend(month) >= knobs["month_budget"]:
            return JSONResponse(status_code=429, content={
                "ok": False, "error_code": "budget_exceeded",
                "error": f"이번 달 틱톡 예산(${knobs['month_budget']:.2f})을 다 썼습니다"})
        if guard.tiktok_daily_count(cid, day) >= knobs["daily_limit"]:
            return JSONResponse(status_code=429, content={
                "ok": False, "error_code": "daily_limit",
                "error": f"오늘 틱톡 수집 한도({knobs['daily_limit']}회)를 다 썼습니다"})
    try:
        items = collect(platform=platform, limit_channels=limit)
        if platform == "tiktok":
            guard.bump_tiktok_daily(_cid(request), datetime.now(timezone.utc).strftime("%Y-%m-%d"))
            # 언어 시드 1개 = 1회 검색(그 언어로 search_count개). 지출 = 언어시드수 × 개수 × 단가.
            n_lang = len([s for s in guard.list_seeds("tiktok") if s["kind"] in _TIKTOK_LANG_KINDS])
            est = n_lang * knobs["search_count"] * _TIKTOK_COST_PER_ITEM
            if est:
                guard.add_tiktok_spend(datetime.now(timezone.utc).strftime("%Y-%m"), est)
        if platform != "instagram":
            _, collected_at = Store(DB_PATH).load_last_run_platform(platform)
            return {"ok": True, "count": len(items), "items": items,
                    "collected_at": collected_at}
        collected_at = datetime.now(timezone.utc).isoformat()
        store = Store(DB_PATH)
        store.save_last_run(items, collected_at)
        background_tasks.add_task(generate_missing_drafts, next_draft_targets(items, store))
        background_tasks.add_task(_tag_new_items, items)   # 신규 썸네일 비전 태깅(백그라운드)
        _attach_vision_tags(items, store)                  # 이미 태깅된 것(재수집)은 즉시 실어 보냄
        return {"ok": True, "count": len(items), "items": items,
                "collected_at": collected_at}
    except Exception as e:
        import re
        msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
        return JSONResponse(status_code=500, content={"ok": False, "error": msg})


_VISION_TAG_CAP = 60  # 1회 수집당 새 태깅 상한(비용 가드). 초과분은 다음 수집 때.


def _tag_new_items(items):
    """신규(태그 없는) 아이템 썸네일을 Gemini 비전 태깅해 vision_tags에 저장.
    shortcode로 캐시하므로 재수집 땐 재호출 안 함. 상한 초과분은 다음 수집으로 미룬다.
    실패(키 없음·썸네일 다운로드 실패)는 그냥 건너뜀 — 그 아이템은 캡션 백업으로 검색된다."""
    try:
        from shopping_shorts import video_analysis
    except Exception:
        return
    store = Store(DB_PATH)
    have = store.vision_tags_map([it.get("shortcode") for it in items])
    todo = [it for it in items if it.get("shortcode") and it.get("shortcode") not in have
            and it.get("thumbnail")]
    capped = todo[:_VISION_TAG_CAP]
    for it in capped:
        img = video_analysis.fetch_thumb_bytes(it.get("thumbnail"))
        if not img:
            continue
        tags = video_analysis.subject_tags_vision(img, it.get("caption", ""))
        if tags and (tags.get("subject") or tags.get("keywords")):
            store.save_vision_tags(it["shortcode"], tags.get("subject", ""), tags.get("keywords", []))
    if len(todo) > len(capped):
        print(f"[vision_tags] {len(todo) - len(capped)}건 다음 수집으로 미룸(상한 {_VISION_TAG_CAP})")


def _attach_vision_tags(items, store=None):
    """아이템에 저장된 vision_subject·vision_keywords를 실어 반환(있는 것만). 검색이 이걸 우선 매칭."""
    store = store or Store(DB_PATH)
    tmap = store.vision_tags_map([it.get("shortcode") for it in items])
    for it in items:
        t = tmap.get(it.get("shortcode"))
        if t:
            it["vision_subject"] = t.get("subject", "")
            it["vision_keywords"] = t.get("keywords", [])
    return items


@app.get("/api/tiktok/settings")
def api_tiktok_settings_get(request: Request):
    """틱톡 키워드검색 관리자 노브 3개 + 오늘 사용현황(remaining_today·month_spend) 조회.

    프론트가 '오늘 남은 N회'와 이번달 지출을 실제 카운트로 보여주기 위해 사용현황도
    함께 반환한다. 사용현황은 로그인 고객(_cid)·오늘 날짜 기준."""
    store = Store(DB_PATH)
    k = _tiktok_knobs(store)
    now = datetime.now(timezone.utc)
    used = store.tiktok_daily_count(_cid(request), now.strftime("%Y-%m-%d"))
    return {"ok": True, **k,
            "used_today": used,
            "remaining_today": max(0, k["daily_limit"] - used),
            "month_spend": store.tiktok_month_spend(now.strftime("%Y-%m"))}


@app.post("/api/tiktok/settings")
def api_tiktok_settings_set(body: dict):
    """틱톡 노브 저장. body: {search_count, daily_limit, month_budget} (부분 갱신 허용)."""
    store = Store(DB_PATH)
    if "search_count" in body:
        store.set_setting("tiktok_search_count", str(int(body["search_count"])))
    if "daily_limit" in body:
        store.set_setting("tiktok_daily_limit", str(int(body["daily_limit"])))
    if "month_budget" in body:
        store.set_setting("tiktok_month_budget", str(float(body["month_budget"])))
    return {"ok": True, **_tiktok_knobs(store)}


@app.post("/api/generate_drafts")
def api_generate_drafts(background_tasks: BackgroundTasks):
    """"댓글 더 생성" 버튼 — 랭킹 상위권 중 draft 없고 완료 처리도 안 된 항목을
    다시 계산해서 40개 생성. 고정 페이지네이션이 아니라 매번 재계산이므로
    실패했던 상위권 항목도 자동으로 재시도 대상에 포함된다(2026-07-09)."""
    store = Store(DB_PATH)
    items, _ = store.load_last_run()
    if not items:
        return JSONResponse(status_code=400, content={"ok": False, "error": "수집된 데이터 없음"})
    targets = next_draft_targets(items, store)
    if not targets:
        return {"ok": True, "count": 0, "message": "더 이상 생성할 항목이 없습니다"}
    background_tasks.add_task(generate_missing_drafts, targets)
    return {"ok": True, "count": len(targets)}


@app.get("/api/reference")
def api_reference(platform: str = "instagram"):
    """마지막 수집 결과 반환 (프론트 초기 로드용). platform=플랫폼(기본 인스타)."""
    store = Store(DB_PATH)
    if platform == "instagram":
        items, collected_at = store.load_last_run()
    else:
        items, collected_at = store.load_last_run_platform(platform)
    _attach_vision_tags(items, store)   # 백그라운드로 채워진 주제태그를 실어 보냄(검색 정확도 승격)
    return {"ok": True, "items": items, "collected_at": collected_at}


@app.get("/api/seeds")
def api_seeds(platform: str = "youtube"):
    """플랫폼별 시드(키워드/채널 등) 목록."""
    return {"ok": True, "items": Store(DB_PATH).list_seeds(platform)}


@app.post("/api/seeds")
def api_seeds_add(body: dict):
    """시드 추가. body: {platform, kind, value}."""
    p = (body.get("platform") or "").strip()
    v = (body.get("value") or "").strip()
    if not p or not v:
        return JSONResponse(status_code=422, content={"ok": False, "error": "platform·value 필요"})
    Store(DB_PATH).add_seed(p, (body.get("kind") or "keyword").strip(), v)
    return {"ok": True}


@app.delete("/api/seeds")
def api_seeds_remove(body: dict):
    """시드 제거. body: {platform, value}."""
    Store(DB_PATH).remove_seed((body.get("platform") or "").strip(), (body.get("value") or "").strip())
    return {"ok": True}


@app.get("/api/related")
def api_related(shortcode: str, platform: str = "instagram"):
    """"같은 주제 모아보기" — 같은 topic_group인 다른 영상들 반환(2026-07-13).
    플랫폼 무관하게 그룹 전체를 조회하므로 유튜브·틱톡 데이터가 나중에 붙어도
    코드 변경 없이 같이 나온다. 지금은 인스타 최근수집(last_run) 캐시에서만
    상세정보를 매칭한다 — 다른 플랫폼이 생기면 각자의 캐시 매칭을 추가해야 함."""
    store = Store(DB_PATH)
    related = store.related_shortcodes(platform, shortcode)
    if not related:
        return {"ok": True, "items": []}
    items, _ = store.load_last_run()
    by_sc = {i["shortcode"]: i for i in items}
    out = []
    for r in related:
        it = by_sc.get(r["shortcode"])
        if it:
            out.append({**it, "platform": r["platform"]})
    return {"ok": True, "items": out}


def _cid(request: Request) -> int:
    """요청의 로그인 고객 ID(2026-07-13 멀티테넌시). 인증 게이트를 안 거치는
    경로(_AUTH_ALLOW, 예: 유저스크립트 콜백)는 customer_id가 안 채워지므로
    LEGACY_CUSTOMER_ID(0)로 폴백."""
    return getattr(request.state, "customer_id", 0)


@app.get("/api/outreach")
def api_outreach(request: Request, sort: str = "latest", hide_done: bool = True,
                 rank_limit: int = DRAFT_BATCH_SIZE):
    """소통 큐 반환 — 마지막 수집 릴스 + draft 결합, 정렬·완료필터.

    rank_limit: 레퍼런스랭킹(score) 상위 N개만 큐 후보로 노출(2026-07-09).
    기본 40 — 프론트가 "댓글 더 생성" 클릭 시 40씩 늘려서 재요청한다."""
    store = Store(DB_PATH)
    items, _ = store.load_last_run()
    drafts = store.drafts_map([i["shortcode"] for i in items])
    commented = store.commented_set(customer_id=_cid(request))
    queue = build_queue(items, drafts_map=drafts, commented=commented,
                        sort=sort, hide_done=hide_done, rank_limit=rank_limit)
    return {"ok": True, "count": len(queue), "items": queue}


@app.post("/api/comment/done")
def api_comment_done(request: Request, shortcode: str):
    """소통 완료 기록."""
    store = Store(DB_PATH)
    store.mark_commented(shortcode, customer_id=_cid(request))
    return {"ok": True, "shortcode": shortcode}


@app.post("/api/save")
def api_save(request: Request, shortcode: str):
    """제품찾기 소스로 담기 (기능 ③에서 재사용)."""
    store = Store(DB_PATH)
    store.mark_saved(shortcode, customer_id=_cid(request))
    return {"ok": True, "shortcode": shortcode}


@app.get("/api/saved")
def api_saved(request: Request):
    """담긴 shortcode 목록."""
    store = Store(DB_PATH)
    return {"ok": True, "saved": sorted(store.saved_set(customer_id=_cid(request)))}


@app.post("/api/mix/basket/toggle")
def api_mix_basket_toggle(request: Request, body: dict, background_tasks: BackgroundTasks):
    """영상 믹싱 바구니 담기/담기취소 토글. body: {shortcode, url, thumbnail, name, caption}.
    담길 때(in=True)는 원클릭 담기와 같이 백그라운드로 메타(조회수·댓글 등)를 보강한다 —
    렌즈 유사영상에서 담은 항목도 즐겨찾기에서 랭킹처럼 정보가 뜨게(2026-07-18)."""
    sc = (body.get("shortcode") or "").strip()
    if not sc:
        return JSONResponse(status_code=422, content={"ok": False, "error": "shortcode 필요"})
    store = Store(DB_PATH)
    cid = _cid(request)
    url = body.get("url") or ""
    in_basket = store.mix_basket_toggle(
        sc,
        url=url,
        thumbnail=body.get("thumbnail") or "",
        name=body.get("name") or "",
        caption=body.get("caption") or "",
        customer_id=cid,
    )
    if in_basket:
        # 렌즈가 검색에서 이미 받은 메타를 즉시 저장(merge) — yt-dlp 재수집(유튜브 봇차단·
        # 샤오홍슈 무oEmbed로 자주 빈값)보다 신뢰도 높다. 재수집은 백그라운드 보조.
        meta = body.get("meta")
        if isinstance(meta, dict):
            clean = {k: meta[k] for k in ("views", "likes", "comments", "shares",
                                          "duration", "channel", "followers", "ts")
                     if meta.get(k) not in (None, "")}
            if clean:
                store.mix_basket_set_meta(sc, customer_id=cid, meta=clean)
        if url and _grab_platform(url):
            background_tasks.add_task(_enrich_grab, url, sc, cid)
    return {"ok": True, "in": in_basket, "count": len(store.mix_basket_shortcodes(customer_id=cid))}


@app.post("/api/mix/basket/remove")
def api_mix_basket_remove(request: Request, body: dict):
    """바구니에서 shortcode 제거."""
    sc = (body.get("shortcode") or "").strip()
    store = Store(DB_PATH)
    cid = _cid(request)
    store.mix_basket_remove(sc, customer_id=cid)
    return {"ok": True, "count": len(store.mix_basket_shortcodes(customer_id=cid))}


@app.get("/api/mix/basket")
def api_mix_basket(request: Request):
    """바구니 항목 목록(담은 순서) + shortcode 집합."""
    store = Store(DB_PATH)
    cid = _cid(request)
    return {"ok": True, "items": store.mix_basket_list(customer_id=cid),
            "shortcodes": sorted(store.mix_basket_shortcodes(customer_id=cid))}


def _err(e):
    """토큰 마스킹 후 500 JSON (수집 계열 공통)."""
    msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
    return JSONResponse(status_code=500, content={"ok": False, "error": msg})


def _known_usernames(store):
    """이미 추적 중인 채널(엑셀 + 발굴추가) username 집합. 엑셀 없으면(로컬 등)
    발굴목록만."""
    known = {d["username"] for d in store.discovered_channels()}
    try:
        known |= {c["username"] for c in load_channels()}
    except Exception:
        pass  # 엑셀 경로 없음(로컬) — 발굴은 계속 동작
    return known


# 발굴은 "최근 이틀 영상수"를 세야 해서 채널당 상한을 넉넉히(메인 랭킹의 3보다 큼).
def _discover_fetch(usernames):
    return fetch_reels(usernames, results_per_channel=12, only_newer_than="2 days")


def _save_discovery_snapshot(store, items):
    """발굴 결과를 snapshots에 저장 → 다음 업데이트 때 Δ·가속(accel) 계산 가능."""
    if not items:
        return
    from datetime import datetime, timezone
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    store.save_run(run_date, [
        {"shortcode": i["shortcode"], "username": i["username"],
         "comments": i["comments"], "delta": i["delta"]} for i in items
    ])


@app.get("/api/discover")
def api_discover(keyword: str, max_channels: int = 15):
    """🔎 채널 발굴 — 카테고리 키워드로 '내가 모르던 채널' 중 최근 48h 댓글이
    빠르게 쌓이는 릴스를 캐치(기존 랭킹엔진 재사용)."""
    keyword = (keyword or "").strip()
    if not keyword:
        return JSONResponse(status_code=422, content={"ok": False, "error": "키워드를 입력하세요"})
    store = Store(DB_PATH)
    try:
        items = discovery.discover(
            keyword, known=_known_usernames(store),
            search_fn=instagram_search.search_channels, fetch_reels_fn=_discover_fetch,
            profiles_fn=fetch_profiles,
            prev_comments=store.prev_comments, prev_delta=store.prev_delta,
            max_channels=max_channels,
        )
        _save_discovery_snapshot(store, items)
    except Exception as e:
        return _err(e)
    return {"ok": True, "count": len(items), "items": items, "keyword": keyword}


# 업데이트 버튼이 자동으로 도는 기본 카테고리(해시태그 형태 — 붙은 한국어
# 복합어는 액터가 0건이라 "#" 필수, 2026-07-12 실측). search_channels가 0건 시
# 자동 폴백도 하지만, 여기선 처음부터 해시태그로 넣어 1회 호출로 끝낸다.
_DISCOVER_CATEGORIES = ["#주방템", "#살림템", "#인테리어", "#자취템", "#생활꿀템", "#뷰티템"]


@app.get("/api/discover/update")
def api_discover_update(days: int = 2, max_total: int = 40, accumulate: bool = False):
    """🔄 업데이트 시작(비동기) — 몇 분 걸리는 수집을 백그라운드 스레드로 돌리고
    즉시 반환한다(2026-07-12, 동기처리 시 프론트가 몇 분 멈추고 배포 재시작에
    응답이 깨지던 문제). 프론트는 /api/discover/status를 폴링해 진행/결과 확인."""
    from shopping_shorts import discover_jobs
    days = max(1, min(int(days), 14))
    max_total = max(10, min(int(max_total), 120))
    st = discover_jobs.start(days, max_total, accumulate)
    return {"ok": True, **st, "categories": _DISCOVER_CATEGORIES,
            "days": days, "accumulate": accumulate}


@app.get("/api/discover/status")
def api_discover_status():
    """업데이트 백그라운드 잡 진행상황(running/done/error) + 완료 시 결과."""
    from shopping_shorts import discover_jobs
    return {"ok": True, **discover_jobs.status()}


@app.get("/api/discover/feed")
def api_discover_feed():
    """마지막 발굴 피드 반환(새로고침 시 복원 — 특히 누적 모드)."""
    items, updated_at = Store(DB_PATH).load_discovery_feed()
    return {"ok": True, "items": items, "updated_at": updated_at}


@app.post("/api/discover/add")
def api_discover_add(username: str, name: str = ""):
    """발굴 채널을 벤치마크 목록에 추가(이후 메인 랭킹에도 추적)."""
    Store(DB_PATH).add_discovered(username.strip().lstrip("@"), name)
    return {"ok": True, "username": username}


@app.get("/api/discover/added")
def api_discover_added():
    """발굴로 추가한 채널 목록."""
    return {"ok": True, "items": Store(DB_PATH).discovered_channels()}


@app.post("/api/reference/register")
def api_reference_register(url: str):
    """레퍼런스 채널을 URL 붙여넣기로 직접 등록(2026-07-18). 인스타 채널/릴스
    URL에서 username을 뽑아 discovered_channels에 소프트 추가 — 엑셀 원본은
    안 건드리고 다음 수집부터 랭킹에 포함(비용 0, 프로필 조회 안 함).
    이미 엑셀·발굴목록에 있으면 already=True로 알려주고 중복 추가하지 않는다."""
    username = username_from_url(url)
    if not username:
        low = (url or "").lower()
        if any(x in low for x in ("/reel/", "/reels/", "/p/", "/tv/", "/share/")):
            # 릴스·게시물 공유링크엔 채널 아이디가 없다(예약경로) — 프로필 주소 안내
            err = "릴스·게시물 주소엔 채널 아이디가 없어요 — 채널(프로필) 주소를 넣어주세요 (예: instagram.com/아이디)"
        else:
            err = "인스타 채널 URL이 아닙니다 (instagram.com/아이디 형태)"
        return JSONResponse(status_code=422, content={"ok": False, "error": err})
    store = Store(DB_PATH)
    key = username.strip().lstrip("@").lower()
    known = {u.strip().lstrip("@").lower() for u in _known_usernames(store)}
    if key in known:
        return {"ok": True, "username": username, "already": True}
    store.add_discovered(username)
    return {"ok": True, "username": username, "already": False}


@app.get("/api/prune/scan")
def api_prune_scan():
    """🧹 죽은 채널 정리 — 마지막 수집에서 릴스가 하나도 안 잡힌 엑셀 채널을
    삭제(추적 제외) 후보로 반환. 별도 Apify 호출 없이 최근 수집 결과 재사용
    (=삭제 전에 「지금 수집」을 먼저 돌려야 최신 판단)."""
    store = Store(DB_PATH)
    items, collected_at = store.load_last_run()
    if not items:
        return JSONResponse(status_code=400, content={
            "ok": False, "error": "수집 데이터 없음 — 레퍼런스 랭킹에서 「지금 수집」 먼저 실행"})
    try:
        channels = load_channels()
    except Exception as e:
        return _err(e)
    active = {i.get("username") for i in items if i.get("username")}
    removed = store.removed_usernames()
    inactive = [c for c in discovery.find_inactive(channels, active)
                if (c["username"] or "").strip().lstrip("@").lower() not in removed]
    return {"ok": True, "count": len(inactive), "items": inactive,
            "collected_at": collected_at, "total": len(channels), "active": len(active)}


@app.post("/api/prune/remove")
def api_prune_remove(username: str, name: str = ""):
    """죽은 채널 추적 제외(소프트 삭제 — 엑셀 원본 미변경, 복구 가능)."""
    Store(DB_PATH).remove_channel(username.strip().lstrip("@"), name)
    return {"ok": True, "username": username}


@app.post("/api/prune/restore")
def api_prune_restore(username: str):
    """추적 제외 해제(되돌리기)."""
    Store(DB_PATH).restore_channel(username.strip().lstrip("@"))
    return {"ok": True, "username": username}


@app.get("/api/prune/removed")
def api_prune_removed():
    """추적 제외된 채널 목록."""
    return {"ok": True, "items": Store(DB_PATH).removed_list()}


_FIND_TMP_DIR = Path(__file__).parent / "data" / "find_frames"
_MIX_WORK_DIR = Path(__file__).parent / "data" / "mix_jobs"
_WIKI_MEDIA_DIR = Path(__file__).parent / "data" / "wiki_media"   # 도서관 원본 영구보관
_SCENE_ASSETS_DIR = Path(__file__).parent / "data" / "scene_assets"  # 장면 라이브러리 자산 영구보관
_THUMB_DIR = Path(__file__).parent / "data" / "thumbs"   # 5단계 썸네일 프레임·산출물


@app.post("/api/extract_script")
def api_extract_script(shortcode: str):
    """카드 영상 1개 → 대본(세그먼트+전체텍스트) 온디맨드 추출. 캐시 우선.

    수집 때 전체를 뽑지 않고, 버튼 클릭한 영상만 다운로드→Gemini 추출→저장한다.
    한번 추출하면 캐시되어 재클릭은 즉시 반환. 인스타 CDN URL 만료 시 다운로드가
    실패할 수 있어(오래된 항목) 통째로 감싸 502로 안내한다."""
    store = Store(DB_PATH)
    items, _ = store.load_last_run()
    target_code = _media_code(shortcode)
    item = next((i for i in items if i["shortcode"] == shortcode
                 or _media_code(i["shortcode"]) == target_code), None)
    if not item:
        return JSONResponse(status_code=404, content={"ok": False, "error": "해당 항목 없음 — 재수집 필요"})
    code = item["shortcode"]

    cached = store.get_script(code)
    if cached:
        return {"ok": True, "cached": True, **cached}

    video_url = item.get("video_url")
    if not video_url:
        return JSONResponse(status_code=422, content={"ok": False, "error": "video_url 없음 — 재수집 필요"})
    # DB(수집분) 유래라 직접 입력은 아니지만, 오염된 수집물이 내부망을 찌르지 않게 같이 막는다.
    blocked = _ssrf_guard(video_url)
    if blocked:
        return blocked

    work_dir = _FIND_TMP_DIR / hashlib.sha1(code.encode()).hexdigest()[:16]
    try:
        video_path = download_video(video_url, work_dir)
    except (requests.RequestException, RuntimeError) as e:
        msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
        return JSONResponse(status_code=502, content={"ok": False, "error": f"영상 다운로드 실패(URL 만료 가능) — 재수집 필요: {msg}"})
    except Exception as e:
        msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
        return JSONResponse(status_code=500, content={"ok": False, "error": msg})

    try:
        result = extract_script(video_path, code, caption=item.get("caption", ""))
    except Exception as e:
        msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
        return JSONResponse(status_code=500, content={"ok": False, "error": msg})

    if not result.get("full_text") and not result.get("segments"):
        return JSONResponse(status_code=502, content={"ok": False, "error": "대본 추출 실패(Gemini 키 소진 또는 영상 인식 실패) — 잠시 후 재시도"})

    store.save_script(code, result, category=item.get("category"))
    return {"ok": True, "cached": False, **result}


def _backfill_extract_structure(db_path, shortcode, full_text):
    """캐시히트 응답 뒤에서 구조분석을 수행한다(I-2, 2026-07-15) — BackgroundTasks로
    호출돼 클릭 즉시 응답을 막지 않는다. Gemini 호출 실패가 이어져도 다음 클릭이
    또 동기 대기(최대 120s×3)하는 일이 없다. if structure: 가드는 그대로 유지
    (실패 시 저장 안 함 — {}를 저장하면 extracts_missing_structure 백필 대상에서
    영구 제외되므로 가드 자체는 옳다, 원 주석 참고).

    [2026-07-16 I-2 잔여] 실패해도 '시도했음'만 기록한다(structure_json은 NULL 유지).
    안 그러면 구조분석이 실패하는 영상은 클릭할 때마다 백그라운드에서 Gemini를 또
    불러 쿼터를 태운다. 재시도는 daily_batch(extracts_missing_structure)가 맡는다."""
    store = Store(db_path)
    try:
        structure = analyze_structure(full_text) or None
    except Exception:  # noqa: BLE001 — 백그라운드 실패는 무해(daily_batch가 재시도)
        structure = None
    if structure:
        store.save_extract_structure(shortcode, structure)
        _promote_category_from_structure(store, shortcode, structure)
    else:
        store.mark_structure_attempted(shortcode)


def _promote_category_from_structure(store, shortcode, structure):
    """구조분석이 함께 뽑아온 product_category로 키워드 추측을 승격한다(2026-07-16).

    왜: categorize()의 키워드 추측은 실측 정확도 54%(13건 중 7)인데 학습 코퍼스의
    다수를 차지해 통계를 오염시킨다. 같은 13건을 Gemini는 77%(10건) 맞혔고, 구조분석이
    어차피 같은 full_text를 보내므로 추가 비용은 사실상 0이다.

    우선순위 user > gemini > keyword — 사용자가 고른 값은 절대 덮지 않는다(덮으면
    교정 경로 자체가 무의미해진다). 통제 어휘 밖 값은 버린다(고아 학습 버킷 방지)."""
    cat = (structure or {}).get("product_category")
    if not cat or cat not in CATEGORY_KEYWORDS:
        return  # "기타"·미상·어휘 밖 → 손대지 않는다(기존 값 유지)
    cached = store.get_extract(shortcode)
    if cached and cached.get("category_source") == "user":
        return
    store.update_extract_category(shortcode, cat, source="gemini")


@app.get("/api/wiki/categories")
def api_wiki_categories():
    """카테고리 선택기용 통제 어휘(I-4, 2026-07-15) — categorize.KEYWORDS 키(인테리어·
    레시피·생활용품·가전·뷰티) + DB 실측값(distinct_extract_categories, 옛 값·'기타' 포함)
    합집합을 정렬해 내려준다. 프론트의 자유 입력(prompt) 폴백을 없애는 유일한 통로."""
    cats = set(CATEGORY_KEYWORDS.keys()) | set(Store(DB_PATH).distinct_extract_categories())
    return {"ok": True, "categories": sorted(cats)}


@app.post("/api/produce/category")
def api_produce_category(body: dict):
    """카테고리 교정 전용(Task 9, ②, 2026-07-15) — 사용자의 명시적 교정은 항상 이긴다.

    /api/produce/extract_from_url의 `if not cached.get("category")` 가드는 이미 추론값이
    채워진 뒤엔 절대 안 열려(설계상 재클릭 안정화용) — 그래서 사용자가 #finalCategory
    드롭다운으로 고쳐도 브라우저 상태(HANDOFF[i].category)만 바뀌고 DB(script_extracts)엔
    영영 안 써졌다. element_raw_values가 script_extracts.category=?로 학습 코퍼스를 직접
    필터하므로, 이대로면 I-3(교정 경로)이 없애려던 '틀린 버킷 오염'이 그대로 존속한다.

    body: {shortcode, category}. category는 통제 어휘(CATEGORY_KEYWORDS 키 ∪ DB 실측값)
    밖이면 422 — I-4(고아 학습 버킷 차단)를 백엔드에서도 지킨다(프론트만 믿지 않는다).
    store.update_extract_category만 쓴다 — category 컬럼만 UPDATE, script_json(원본 대본)은
    절대 안 건드린다(C-1 재발방지: save_script(code, cached, category=...)로 레코드를
    통째 재기록하는 패턴 금지, 원본 소실 사고 재발 방지).

    재학습(_relearn_category)은 여기서 걸지 않는다 — 드롭다운 change 이벤트마다(디바운스
    없이) BackgroundTasks를 걸면 사용자가 후보를 훑어보는 동안 클릭당 재학습이 반복 실행될
    수 있다. 교정은 저장 시점(save_to_wiki/api_wiki_save)의 _relearn_category 한 번으로
    이미 반영되므로, 여기서 또 거는 건 과하다고 판단."""
    shortcode = (body.get("shortcode") or "").strip()
    category = (body.get("category") or "").strip()
    if not shortcode or not category:
        return JSONResponse(status_code=422, content={"ok": False, "error": "shortcode·category 필요"})
    store = Store(DB_PATH)
    allowed = set(CATEGORY_KEYWORDS.keys()) | set(store.distinct_extract_categories())
    if category not in allowed:
        return JSONResponse(status_code=422, content={"ok": False, "error": f"통제 어휘 밖 카테고리: {category}"})
    store.update_extract_category(shortcode, category)
    return {"ok": True, "shortcode": shortcode, "category": category}


@app.post("/api/produce/extract_from_url")
def api_produce_extract_from_url(body: dict, background_tasks: BackgroundTasks):
    """영상 URL로 직접 대본 추출(영상제작소 역할배정 '대본용'). body: {url, caption?, shortcode?, category?, name?}.

    /api/extract_script는 현재 레퍼런스 랭킹 run(last_run)에서만 shortcode를 찾아,
    즐겨찾기에 예전 run 때 담긴 영상은 'last_run에 없음'으로 실패한다(2026-07-14 실버그).
    여기선 last_run을 안 거치고 저장된 URL을 download_any로 바로 받아 추출 → run 무관.
    shortcode가 있으면 대본 캐시(get_extract/save_script)를 재사용해 재클릭을 즉시화한다.

    2026-07-15(Task 6, I-1·I-2 배선 수정): 즐겨찾기 HANDOFF엔 category가 없다(name·caption뿐).
    category 없인 /api/wiki/element_options이 옵션 0개를 반환해 대본뽑기 모달의 학습소재
    선택 기능이 완전히 무력화됐다(라이브 실측). 우선순위 body.category → 저장된
    get_extract().category → categorize(name, caption)(레퍼런스 랭킹과 동일 함수) → None
    으로 고정 해결한다. structure도 get_extract()가 이미 반환하므로 같이 실어 보낸다
    (없으면 캐시히트 시엔 BackgroundTasks로 뒤에서 채우고, 새 영상 추출 시엔 즉석
    analyze_structure 1회로 채우고 캐시 — 다음부터 재분석 없이 재사용, extracts_missing_structure
    백필 대상에서도 빠짐). analyze_structure는 Gemini 호출이라 실패할 수 있으나 대본 추출
    응답 자체는 항상 성공시킨다(structure=None 폴백).

    2026-07-15(Task 8, I-2): 캐시히트 경로의 구조분석은 동기 호출하지 않는다 — 실패가
    이어지면 캐시히트마다 Gemini 재호출로 클릭당 최대 120s×3이 걸려 '재클릭 즉시화'가
    깨졌다(실측). BackgroundTasks로 미루고 응답은 캐시된 structure(없으면 None)로 즉시 준다."""
    url = (body.get("url") or "").strip()
    if not url:
        return JSONResponse(status_code=422, content={"ok": False, "error": "url 필요"})
    blocked = _ssrf_guard(url)        # download_any가 이 URL을 그대로 받는다
    if blocked:
        return blocked
    code = (body.get("shortcode") or "").strip() or hashlib.sha1(url.encode()).hexdigest()[:12]
    body_category = (body.get("category") or "").strip() or None
    name = body.get("name") or ""
    store = Store(DB_PATH)
    cached = store.get_extract(code)
    if cached:
        caption_for_infer = body.get("caption") or cached.get("full_text", "")
        category = body_category or cached.get("category") or categorize(name, caption_for_infer) or None
        # [2026-07-16] 출처를 남긴다: 사용자가 고른 값(body_category)은 user — 이후
        # Gemini 승격이 이걸 덮지 않는다. 자동 추측은 keyword로 남겨 승격 대상이 된다.
        if body_category:
            store.update_extract_category(code, body_category, source="user")
        elif not cached.get("category") and category:
            # 다음 클릭부터 안정(C-1: script_json은 안 건드림)
            store.update_extract_category(code, category, source="keyword")
        structure = cached.get("structure")
        # [2026-07-16 I-2 잔여] 한 번 시도해서 못 얻은 영상은 다시 예약하지 않는다 —
        # 안 그러면 클릭마다 Gemini를 또 부른다. 재시도는 daily_batch가 맡는다.
        if not structure and not cached.get("structure_analyzed_at"):
            background_tasks.add_task(_backfill_extract_structure, DB_PATH, code, cached.get("full_text", ""))
        return {"ok": True, "cached": True, **cached, "category": category, "structure": structure}
    work_dir = _FIND_TMP_DIR / hashlib.sha1(code.encode()).hexdigest()[:16]
    try:
        video_path, dl_caption = download_any(url, str(work_dir))
    except Exception as e:  # noqa: BLE001 — 다운로드 실패는 사용자에게 안내(치명 아님)
        msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
        return JSONResponse(status_code=502, content={
            "ok": False, "error": f"영상 다운로드 실패(URL 만료·비공개·프로필주소 가능): {msg}"})
    caption = (body.get("caption") or dl_caption or "")
    try:
        result = extract_script(video_path, code, caption=caption)
    except Exception as e:  # noqa: BLE001
        msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
        return JSONResponse(status_code=500, content={"ok": False, "error": msg})
    if not result.get("full_text") and not result.get("segments"):
        return JSONResponse(status_code=502, content={"ok": False, "error": "대본 추출 실패 — 잠시 후 재시도"})
    category = body_category or categorize(name, caption) or None
    store.save_script(code, result, category=category)
    structure = None
    try:
        structure = analyze_structure(result.get("full_text", "")) or None
    except Exception:  # noqa: BLE001 — 구조분석 실패해도 대본 응답은 성공시킨다
        structure = None
    if structure:
        store.save_extract_structure(code, structure)
    return {"ok": True, "cached": False, **result, "category": category, "structure": structure}


def _relearn_category(db_path, category):
    """위키 저장 직후 그 카테고리의 요소 카테고리를 즉시 재학습(백그라운드). 실패해도 무해."""
    if not category:
        return
    try:
        from shopping_shorts import daily_batch
        daily_batch.recompute_element_stats(Store(db_path), only_category=category)
    except Exception as e:  # noqa: BLE001 — 학습 실패는 저장 자체엔 영향 없음
        print(f"relearn 실패 {category}: {e}")


@app.post("/api/wiki/save")
def api_wiki_save(request: Request, shortcode: str, background_tasks: BackgroundTasks):
    """S급 대본을 위키(도서관)에 저장 — 대본 확보(캐시/즉석추출) → 구조분석 → 저장.
    저장 직후 그 카테고리를 즉시 재학습(예약 안 기다림, 2026-07-14)."""
    store = Store(DB_PATH)
    items, _ = store.load_last_run()
    target_code = _media_code(shortcode)
    item = next((i for i in items if i["shortcode"] == shortcode
                 or _media_code(i["shortcode"]) == target_code), None)
    if not item:
        return JSONResponse(status_code=404, content={"ok": False, "error": "해당 항목 없음 — 재수집 필요"})
    code = item["shortcode"]
    hashed = hashlib.sha1(code.encode()).hexdigest()[:16]
    work_dir = _FIND_TMP_DIR / hashed
    video_path = None

    script = store.get_script(code)
    if not script:                      # 아직 대본추출 안 했으면 즉석 추출
        video_url = item.get("video_url")
        if not video_url:
            return JSONResponse(status_code=422, content={"ok": False, "error": "video_url 없음 — 재수집 필요"})
        try:
            video_path = download_video(video_url, work_dir)
        except (requests.RequestException, RuntimeError) as e:
            msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
            return JSONResponse(status_code=502, content={"ok": False, "error": f"영상 다운로드 실패(URL 만료 가능): {msg}"})
        script = extract_script(video_path, code, caption=item.get("caption", ""))
        if not script.get("full_text") and not script.get("segments"):
            return JSONResponse(status_code=502, content={"ok": False, "error": "대본 추출 실패 — 잠시 후 재시도"})
        store.save_script(code, script, category=item.get("category"))

    # 원본 영상 영구보관(도서관 인라인 재생용) — 만료되는 CDN URL 대신 파일로 남긴다.
    media_target = _WIKI_MEDIA_DIR / f"{hashed}.mp4"
    if not media_target.exists():
        src = video_path
        if src is None and item.get("video_url"):
            try:
                src = download_video(item["video_url"], work_dir)
            except Exception:
                src = None
        if src and Path(src).exists():
            try:
                _WIKI_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copy(str(src), str(media_target))
            except Exception:
                pass  # 영상 보관 실패해도 대본·구조는 저장(치명적 아님)

    structure = analyze_structure(script.get("full_text", ""))
    store.save_to_wiki(item, script, structure, customer_id=_cid(request))
    # 학습 소스에도 구조 채우고(재분석 없이 재사용) 그 카테고리 즉시 재학습(백그라운드).
    store.save_extract_structure(code, structure)
    background_tasks.add_task(_relearn_category, DB_PATH, item.get("category"))
    return {"ok": True, "shortcode": code, "structure": structure, "has_video": media_target.exists()}


@app.post("/api/produce/save_to_wiki")
def api_produce_save_to_wiki(request: Request, body: dict, background_tasks: BackgroundTasks):
    """제작소(영상제작소)에서 지정한 '이 원본 영상'을 URL 기반으로 위키(도서관)에 담아
    학습에 반영한다 — /api/wiki/save와 같은 의미(항상 원본만 저장), 다만
    load_last_run() 대신 URL로 직접 동작한다는 점만 다르다.

    [2026-07-15 C-1 사고 수정] 예전엔 클라이언트가 리메이크로 확정한 script_text를
    원본 영상의 shortcode 키에 그대로 저장했다 — script_extracts(원본 캐시)가
    리메이크로 덮여 원본이 복구불가로 소실되고(extract_from_url은 캐시 히트 시
    재추출을 안 함), 위키(=S급 학습 창고)에도 리메이크가 들어가 학습 코퍼스가
    우리 출력을 재학습하는 루프가 됐다(실측: script_extracts['lens_instagram_
    1uwwsav'] 원본 소실). 이제 body.script_text/structure/segments는 파생물이라
    절대 쓰지 않고 무시한다. 원본은 캐시(get_extract)가 있으면 그걸 그대로 쓰고
    (텍스트는 손대지 않는다 — category만 다시 붙이려고 통째로 덮어쓰지 않음),
    없으면 URL에서 즉석 추출한다(/api/produce/extract_from_url과 같은 경로).
    클라이언트가 만든 리메이크는 이미 script_drafts에 남아있으므로 잃는 게 없다.

    body: {url, shortcode?, video_url?, caption?, category?, name?, followers?,
           comments?, density?, thumbnail?}."""
    url = (body.get("url") or "").strip()
    if not url:
        return JSONResponse(status_code=422, content={"ok": False, "error": "url 필요"})
    # video_url이 오면 download_any가 그걸 우선 쓴다 — 둘 다 검사해야 한다.
    blocked = _ssrf_guard(*[u for u in (url, body.get("video_url")) if u])
    if blocked:
        return blocked
    code = (body.get("shortcode") or "").strip() or hashlib.sha1(url.encode()).hexdigest()[:12]
    body_category = (body.get("category") or "").strip() or None  # 빈문자열→None (NULL/빈문자열 혼재 방지)
    store = Store(DB_PATH)
    hashed = hashlib.sha1(code.encode()).hexdigest()[:16]
    work_dir = _FIND_TMP_DIR / hashed
    video_path = None  # 추출 중 다운로드했으면 영상보관 때 재다운로드 없이 재사용

    cached = store.get_extract(code)
    if cached and (cached.get("full_text") or cached.get("segments")):
        script = {"full_text": cached.get("full_text", ""), "segments": cached.get("segments") or []}
        category = body_category or cached.get("category") or None
        structure = cached.get("structure")
    else:
        try:
            video_path, dl_caption = download_any(body.get("video_url") or url, str(work_dir))
        except Exception as e:  # noqa: BLE001 — 다운로드 실패는 사용자에게 안내(치명 아님)
            msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
            return JSONResponse(status_code=502, content={
                "ok": False, "error": f"영상 다운로드 실패(URL 만료·비공개 가능): {msg}"})
        caption = body.get("caption") or dl_caption or ""
        try:
            result = extract_script(video_path, code, caption=caption)
        except Exception as e:  # noqa: BLE001
            msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
            return JSONResponse(status_code=500, content={"ok": False, "error": msg})
        if not result.get("full_text") and not result.get("segments"):
            return JSONResponse(status_code=502, content={"ok": False, "error": "대본 추출 실패 — 잠시 후 재시도"})
        category = body_category or None
        script = {"full_text": result.get("full_text", ""), "segments": result.get("segments") or []}
        store.save_script(code, script, category=category)
        structure = None

    if not structure:
        try:
            structure = analyze_structure(script.get("full_text", "")) or None
        except Exception:  # noqa: BLE001 — 구조분석 실패해도 저장 자체는 성공시킨다
            structure = None

    # 원본 영상 영구보관(도서관 인라인 재생용) — 실패해도 대본·구조는 저장(무해).
    media_target = _WIKI_MEDIA_DIR / f"{hashed}.mp4"
    if not media_target.exists():
        src = video_path
        if src is None:
            try:
                src, _dl_caption = download_any(body.get("video_url") or url, str(work_dir))
            except Exception:
                src = None
        if src and Path(src).exists():
            try:
                _WIKI_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copy(str(src), str(media_target))
            except Exception:
                pass  # 다운로드 실패(URL 만료·비공개 등) — 치명적 아님

    item = {
        "shortcode": code,
        "name": body.get("name"),
        "category": category,
        "url": url,
        "followers": body.get("followers") or 0,
        "comments": body.get("comments") or 0,
        "density": body.get("density") or 0.0,
        "thumbnail": body.get("thumbnail") or "",
    }
    store.save_to_wiki(item, script, structure, customer_id=_cid(request))
    if structure:
        store.save_extract_structure(code, structure)
    background_tasks.add_task(_relearn_category, DB_PATH, category)
    return {"ok": True, "shortcode": code, "structure": structure, "has_video": media_target.exists()}


@app.get("/api/wiki/video")
def api_wiki_video(shortcode: str):
    """도서관에 영구보관한 원본 영상 서빙(인라인 재생). 없으면 404.
    FileResponse는 Range 요청을 지원해 탐색(seek)도 됨."""
    from fastapi.responses import FileResponse, Response
    f = _WIKI_MEDIA_DIR / f"{hashlib.sha1(shortcode.encode()).hexdigest()[:16]}.mp4"
    if not f.exists():
        return Response(status_code=404, content=b"")
    return FileResponse(str(f), media_type="video/mp4")


@app.get("/api/wiki/poster")
def api_wiki_poster(shortcode: str):
    """보관영상의 첫 프레임(JPEG). 대본선택 리스트 썸네일용. 없으면 404.

    이전엔 리스트가 <video preload=metadata>로 썸네일을 대신했는데, 위
    /api/wiki/video가 Range를 안 먹여 200으로 mp4 전체(수 MB)를 내려준다.
    10행이면 수십 MB를 동시에 받느라 메타데이터도 못 붙어 전부 검은칸이었다
    (2026-07-15 실측 readyState=0). 프레임 1장만 떠서 캐시해 준다."""
    from fastapi.responses import FileResponse, Response
    hashed = hashlib.sha1(shortcode.encode()).hexdigest()[:16]
    mp4 = _WIKI_MEDIA_DIR / f"{hashed}.mp4"
    poster = _WIKI_MEDIA_DIR / f"{hashed}.jpg"
    if not poster.exists():
        if not mp4.exists():
            return Response(status_code=404, content=b"")
        # 0.1초 지점 — 0초는 검은 첫 프레임인 영상이 있어 피한다.
        if not extract_frame_at(str(mp4), str(_WIKI_MEDIA_DIR), 0.1, filename=f"{hashed}.jpg"):
            return Response(status_code=404, content=b"")
    return FileResponse(str(poster), media_type="image/jpeg")


@app.get("/api/wiki/list")
def api_wiki_list(request: Request):
    """위키(도서관)에 담은 S급 대본 전체."""
    return {"ok": True, "items": Store(DB_PATH).wiki_list(customer_id=_cid(request))}


@app.post("/api/wiki/remove")
def api_wiki_remove(request: Request, shortcode: str):
    """위키에서 제거."""
    Store(DB_PATH).remove_from_wiki(shortcode, customer_id=_cid(request))
    return {"ok": True, "shortcode": shortcode}


@app.get("/api/wiki/element_options")
def api_wiki_element_options(category: str):
    """생성 모달이 열릴 때 그 대본의 카테고리로 학습된 요소별 옵션을 조회."""
    return {"ok": True, "options": Store(DB_PATH).get_element_options(category)}


@app.get("/api/wiki/subject")
def api_wiki_subject(request: Request, shortcode: str):
    """리메이크 모달 프리필용 — 위키 항목 원문에서 소재 한 줄 자동 감지."""
    store = Store(DB_PATH)
    it = store.get_wiki_item(shortcode, customer_id=_cid(request))
    if not it:
        return JSONResponse(status_code=404, content={"ok": False, "error": "위키에 없는 항목"})
    subject = script_generate.detect_subject(it.get("full_text") or "")
    return {"ok": True, "subject": subject}


@app.post("/api/wiki/generate")
def api_wiki_generate(request: Request, shortcode: str, body: dict):
    """도서관 S급 1개의 구조를 빌려 새 20초 대본 초안 생성(모드 remake/transplant, 4단 요소 모드).

    body: {mode: "remake"|"transplant"(구버전 "A"|"B" 하위호환), subject: str(remake 소재 고정),
           my_topic: str(transplant 이식 주제), n: int,
           elem_modes: {element_key: "keep"|"free"|"random"|"category:<label>"},
           structure?: dict, base_script?: str, category?: str}
    (2026-07-13, 기존 쿼리파라미터 keep=콤마문자열 방식에서 JSON body로 전환 —
    카테고리 지정 모드가 라벨 문자열까지 실어야 해서 콤마 목록으로는 표현이 안 됨)

    2026-07-15 폴백: 제작소(영상제작소) 직행 영상은 위키 저장 없이 대본을 뽑는다.
    위키에 shortcode가 없어도 body에 structure/base_script가 실려오면 그걸로 생성 진행
    (기존 위키 경로는 그대로 우선 — 있으면 위키 걸 쓴다, 하위호환 유지)."""
    store = Store(DB_PATH)
    it = store.get_wiki_item(shortcode, customer_id=_cid(request))
    if not it:
        _structure = body.get("structure")
        _base_script = body.get("base_script")
        if isinstance(_structure, dict) or (_base_script or "").strip():
            it = {
                "structure": _structure if isinstance(_structure, dict) else {},
                "full_text": _base_script or "",
                "category": body.get("category") or "",
            }
        else:
            return JSONResponse(status_code=404, content={"ok": False, "error": "위키에 없는 항목 — 먼저 S급으로 저장하세요"})
    if not (it.get("structure") or it.get("full_text")):
        return JSONResponse(status_code=422, content={"ok": False, "error": "구조분석/대본이 비어 생성 불가 — 재저장 필요"})
    mode = body.get("mode", "remake")
    my_topic = body.get("my_topic", "")
    subject = body.get("subject", "")
    try:
        n = int(body.get("n") or 3)
    except (TypeError, ValueError):
        n = 3
    _em = body.get("elem_modes")
    elem_modes = ({k: v for k, v in _em.items() if k in script_generate.ELEM_KEYS}
                  if isinstance(_em, dict) else {})
    category_lookup = store.get_element_options(it.get("category") or "")
    drafts = script_generate.generate_variations(
        it.get("structure") or {}, it.get("full_text") or "", elem_modes, category_lookup,
        mode=mode, my_topic=my_topic, subject=subject, n=n)
    if not drafts:
        return JSONResponse(status_code=502, content={"ok": False, "error": "생성 실패(Gemini 키 소진 또는 오류) — 잠시 후 재시도"})
    cid = _cid(request)
    for dr in drafts:
        draft_id = uuid.uuid4().hex[:12]
        store.save_draft(draft_id, cid, shortcode, None, dr.get("hook", ""), dr.get("script", ""), None, "generate")
        dr["draft_id"] = draft_id
    return {"ok": True, "drafts": drafts}


@app.post("/api/wiki/draft/analyze")
def api_wiki_draft_analyze(body: dict):
    """초안 텍스트 → 구조분석(도서관→제작소 다리, 2026-07-15). body: {script_text}.

    도서관 초안은 요소별 유지/변형으로 만들어져 원본 영상의 구조와 다르다(주변인물을
    '요리 고수 언니'로 바꿔 생성했다면 원본 구조의 주변인물과 어긋남). 그래서 원본
    구조를 재사용하지 않고 초안을 다시 분석한다(사용자 결정).

    구조분석 실패({})해도 200으로 응답한다 — 구조는 있으면 좋은 것이고, 여기서
    막으면 대본 이동 자체가 죽는다."""
    text = (body.get("script_text") or "").strip()
    if not text:
        return JSONResponse(status_code=422, content={"ok": False, "error": "script_text 필요"})
    try:
        structure = analyze_structure(text) or None
    except Exception:  # noqa: BLE001 — 구조분석 실패는 무해(대본은 넘어가야 함)
        structure = None
    return {"ok": True, "structure": structure}


@app.post("/api/wiki/draft/refine")
def api_draft_refine(request: Request, body: dict):
    """초안을 지시문으로 재생성(전체재작성 또는 부분수정) — 새 버전으로 저장.

    body: {draft_id, mode: "rewrite"|"partial", instruction, selected_text?(partial 필수)}"""
    store = Store(DB_PATH)
    draft_id = body.get("draft_id", "")
    mode = body.get("mode", "rewrite")
    instruction = (body.get("instruction") or "").strip()
    cur = store.get_draft(draft_id)
    if not cur:
        return JSONResponse(status_code=404, content={"ok": False, "error": "해당 초안 없음"})
    if not instruction:
        return JSONResponse(status_code=422, content={"ok": False, "error": "지시문을 입력하세요"})
    if mode == "partial":
        selected = (body.get("selected_text") or "").strip()
        if not selected:
            return JSONResponse(status_code=422, content={"ok": False, "error": "선택한 부분이 필요합니다"})
        new_text = script_generate.refine_draft_partial(cur["script_text"], selected, instruction)
    else:
        new_text = script_generate.refine_draft_rewrite(cur["script_text"], instruction)
    if not new_text:
        return JSONResponse(status_code=502, content={"ok": False, "error": "재생성 실패(Gemini 키 소진 또는 오류) — 잠시 후 재시도"})
    new_id = uuid.uuid4().hex[:12]
    store.save_draft(new_id, _cid(request), cur["source_shortcode"], draft_id, cur.get("hook", ""),
                      new_text, instruction, mode)
    return {"ok": True, "draft_id": new_id, "script_text": new_text}


@app.post("/api/wiki/draft/edit")
def api_draft_edit(request: Request, body: dict):
    """텍스트박스에서 직접 고친 내용을 AI 호출 없이 새 버전으로 저장.

    body: {draft_id, script_text}"""
    store = Store(DB_PATH)
    draft_id = body.get("draft_id", "")
    script_text = body.get("script_text", "")
    cur = store.get_draft(draft_id)
    if not cur:
        return JSONResponse(status_code=404, content={"ok": False, "error": "해당 초안 없음"})
    new_id = uuid.uuid4().hex[:12]
    store.save_draft(new_id, _cid(request), cur["source_shortcode"], draft_id, cur.get("hook", ""),
                      script_text, None, "manual")
    return {"ok": True, "draft_id": new_id}


@app.get("/api/wiki/draft/history")
def api_draft_history(draft_id: str):
    """초안의 버전 체인 전체(오래된 순)."""
    return {"ok": True, "history": Store(DB_PATH).get_draft_chain(draft_id)}


@app.post("/api/find/analyze")
def api_find_analyze(shortcode: str):
    """영상 다운로드 → 프레임 추출 → Gemini 분석 → 검색링크 생성, 결과 저장 후 반환.

    추적 채널(443개) 목록에서 온 항목이 아니어도(사용자가 인스타에서 직접
    발견한 URL) Apify 단일조회로 즉시 가져와 분석한다(2026-07-09, "우리
    목록에 없으면 분석 불가" 제약 제거 — tubefactory와 동일하게 임의 URL 지원).

    다운로드→추출→분석 구간은 각각 실패 가능(인스타 CDN 서명URL 만료로 인한
    다운로드 403/404, ffmpeg 실패, Gemini 키 미설정)해서 통째로 감싼다
    (2026-07-09, 최종 리뷰 Finding 1 — 무가드 상태로 raw 500이 나던 문제)."""
    store = Store(DB_PATH)
    items, _ = store.load_last_run()
    target_code = _media_code(shortcode)
    item = next((i for i in items if i["shortcode"] == shortcode
                 or _media_code(i["shortcode"]) == target_code), None)

    if not item:
        # 추적 목록에 없는 URL — Apify 단일조회로 즉시 가져오기 시도.
        # 인스타그램 URL이 아니면 Apify 호출 자체를 스킵 — 이 액터는 인스타 전용이라
        # 다른 플랫폼(유튭 등) URL을 넣으면 계정 7개를 전부 돌면서 매번 실패하고
        # "토큰 전부 소진"처럼 보이는 오해를 낳는다(2026-07-09, 실사용 중 발견 —
        # 실제로는 계정 소진이 아니라 "input.username is required" 구조적 거부였음).
        if "instagram.com" not in shortcode:
            return JSONResponse(status_code=422, content={
                "ok": False,
                "error": "인스타그램 URL만 지원합니다 (다른 플랫폼 URL은 분석 불가)",
            })
        try:
            raw = fetch_single_reel(shortcode)
        except (requests.RequestException, RuntimeError) as e:
            msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
            return JSONResponse(status_code=502, content={"ok": False, "error": msg})
        if not raw:
            return JSONResponse(status_code=404, content={"ok": False, "error": "해당 항목 없음(비공개 계정이거나 삭제된 게시물일 수 있음)"})
        item = {
            "shortcode": raw.get("url") or shortcode,
            "video_url": raw.get("videoUrl", ""),
            "caption": raw.get("caption", ""),
        }

    video_url = item.get("video_url")
    if not video_url:
        # video_url 필드 추가 이전에 저장된 last_run row 등 — KeyError 대신 명확한 에러
        return JSONResponse(status_code=422, content={"ok": False, "error": "video_url 없음 — 재수집 필요"})

    # 이후 저장·work_dir·응답은 전부 canonical shortcode(item["shortcode"]) 기준 —
    # 사용자가 입력한 원본 문자열(추적파라미터 등 붙은)이 아니라 우리가 저장한
    # 정식 shortcode로 통일해야 랭킹페이지 "담기"로 들어온 동일 영상과 같은
    # source_analysis 행을 공유한다(2026-07-09, 미디어코드 매칭 수정과 함께 정리).
    shortcode = item["shortcode"]
    work_dir = _FIND_TMP_DIR / hashlib.sha1(shortcode.encode()).hexdigest()[:16]
    try:
        video_path = download_video(video_url, work_dir)
        frame_paths = extract_frames(video_path, work_dir, max_frames=6)
    except (requests.RequestException, RuntimeError) as e:
        msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
        return JSONResponse(status_code=502, content={"ok": False, "error": msg})
    except Exception as e:
        msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
        return JSONResponse(status_code=500, content={"ok": False, "error": msg})

    frame_urls = [f"/api/find/frame/{work_dir.name}/{p.name}" for p in frame_paths]
    frame_abs_urls = [f"{PUBLIC_BASE_URL}{u}" for u in frame_urls]
    served_video_url = f"/api/find/frame/{work_dir.name}/{video_path.name}"

    # analyze_video(Gemini 비디오분석)와 fetch_lens_lines(SerpApi 렌즈검색으로
    # 정확한 제품명 후보 수집)는 서로 입력이 독립적(렌즈는 프레임 이미지만
    # 필요, category는 프롬프트 힌트일 뿐 필수 아님) — 순차 실행 시 두 단계
    # 시간이 그대로 더해져 "분석 버튼이 느리다"는 실사용 피드백(2026-07-11)의
    # 원인이었음. 병렬 실행으로 전체 소요시간을 둘 중 느린 쪽 하나로 줄인다.
    with ThreadPoolExecutor(max_workers=2) as ex:
        analysis_future = ex.submit(analyze_video, video_path, item.get("caption", ""))
        lens_future = ex.submit(fetch_lens_lines, frame_abs_urls)
        try:
            analysis = analysis_future.result()
        except (requests.RequestException, RuntimeError) as e:
            msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
            return JSONResponse(status_code=502, content={"ok": False, "error": msg})
        except Exception as e:
            msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
            return JSONResponse(status_code=500, content={"ok": False, "error": msg})
        try:
            lens_lines = lens_future.result()
        except Exception:
            lens_lines = []

    # 정확한 제품명 확인 후 키워드 최우선에 반영(2026-07-10, "제품 직접
    # 홍보형" 검색 정밀도 개선 — Gemini의 일반적인 키워드 추측보다 구글 렌즈로
    # 실제 브랜드/모델을 확인하면 같은 제품 영상을 더 정밀하게 찾을 수 있음).
    # 어디까지나 정밀도 "개선 시도"라 실패해도 분석 자체는 계속 진행한다.
    try:
        product_name = identify_product_from_lines(
            lens_lines, category=analysis["category"], caption=item.get("caption", ""),
        )
    except Exception:
        product_name = ""
    # ko/en에만 원어 그대로 추가 — zh/ja/ru까지 똑같은 문자열을 넣으면
    # 언어 드롭다운을 바꿔도 검색어 자체가 안 바뀌어 같은 결과만 나온다
    # (2026-07-10 실측 "언어 바꿔도 똑같은 영상" 버그). zh/ja/ru는 Gemini가
    # 이미 만들어둔 그 언어 고유 키워드를 그대로 첫 자리에 둔다.
    if product_name:
        for lang in ("ko", "en"):
            kws = analysis["keywords"].get(lang, [])
            if product_name not in kws:
                analysis["keywords"][lang] = [product_name] + kws

    store.save_source_analysis(
        shortcode, keywords=analysis["keywords"],
        frame_paths=[str(p) for p in frame_paths],
        analyzed_at=datetime.now(timezone.utc).isoformat(),
    )

    # Lens 역검색용 프레임은 장면전환 감지 프레임(frame_abs_urls)뿐 아니라,
    # Gemini가 영상 분석 중 함께 짚어준 "제품이 가장 선명한 순간"(lens_hint_sec)도
    # 하나 더 떠서 맨 앞에 추천으로 붙인다(2026-07-13, "Lens 역검색도 결과 없음이
    # 잦다" 피드백 대응 — 장면전환 프레임은 얼굴·손·배경이 섞여 역검색이 헛돌 때가
    # 있었음). 실패해도 조용히 기존 프레임만 사용.
    lens_frame_abs_urls = list(frame_abs_urls)
    hint_sec = analysis.get("lens_hint_sec")
    if isinstance(hint_sec, (int, float)):
        try:
            hint_path = extract_frame_at(video_path, work_dir, hint_sec)
        except Exception:
            hint_path = None
        if hint_path:
            hint_url = f"{PUBLIC_BASE_URL}/api/find/frame/{work_dir.name}/{hint_path.name}"
            lens_frame_abs_urls = [hint_url] + lens_frame_abs_urls

    return {
        "ok": True,
        "shortcode": shortcode,
        "keywords": analysis["keywords"],
        "category": analysis["category"],
        "frame_urls": frame_urls,
        "video_url": served_video_url,
        "search_links": build_search_links(analysis["keywords"]),
        "lens_links": [lens_search_url(u) for u in lens_frame_abs_urls],
        "lens_hint_used": lens_frame_abs_urls != frame_abs_urls,
    }


@app.post("/api/find/translate_keyword")
def api_find_translate_keyword(body: dict):
    """제품 찾기 화면에서 자동 분석이 영상 내용을 잘못 짚었을 때, 사용자가
    정확한 키워드를 한국어로 직접 넣으면 4개 언어로 번역해서 검색 링크까지
    만들어 반환한다(2026-07-13, "레시피 영상인데 조리도구로 키워드가 잡힘"
    피드백 대응)."""
    keyword = (body.get("keyword") or "").strip()
    if not keyword:
        return JSONResponse(status_code=422, content={"ok": False, "error": "키워드를 입력하세요"})
    translated = translate_keyword(keyword)
    return {
        "ok": True,
        "keywords": translated,
        "search_links": build_search_links({lang: [kw] for lang, kw in translated.items() if kw}),
    }


# 실수집(플랫폼당 5개 언어 전부 검색 + Gemini 유사도 채점) → 임베드 미리보기
# (/api/find/preview, 채점 없이 Apify로 직접 검색) 순으로 시도했으나 둘 다
# 폐기(2026-07-10). 임베드 미리보기도 실측 결과 정확한 키워드로도 관련성이
# 30~50%대였고("리마커블 2"로도 6개 중 2~3개만 관련), zh/ja/ru 키워드 자체가
# 비어 있어 중국어 플랫폼을 영어 문구로 검색하던 문제까지 겹쳤음. Apify
# 스크래퍼가 플랫폼 자체 검색 알고리즘을 완전히 복제할 수 없다는 구조적
# 한계로 판단, 경쟁사(tubefactory)처럼 언어별 키워드 후보 전부를 그 플랫폼
# 자체 검색 링크로 만들어 사용자가 직접 클릭하는 방식(build_search_links)
# 으로 전환. 결과 임베드가 없으니 이 한계 자체가 사라짐.


@app.get("/api/find/candidates")
def api_find_candidates(shortcode: str):
    store = Store(DB_PATH)
    return {"ok": True, "items": store.get_candidates(shortcode)}




@app.post("/api/find/save")
def api_find_save(candidate_id: int, shortcode: str):
    """확정 후보를 소스풀에 담기."""
    store = Store(DB_PATH)
    store.save_to_pool(shortcode, candidate_id)
    return {"ok": True}


@app.get("/api/find/frame/{work_id}/{filename}")
def api_find_frame(work_id: str, filename: str):
    path = (_FIND_TMP_DIR / work_id / filename).resolve()
    if not path.is_relative_to(_FIND_TMP_DIR.resolve()) or not path.exists():
        return JSONResponse(status_code=404, content={"ok": False})
    return FileResponse(path)


@app.post("/api/mix/start")
def api_mix_start(background_tasks: BackgroundTasks, body: dict):
    """믹스 job 시작. body: {urls, target_seconds, structure, subtitle_removal}."""
    urls = [u for u in (body.get("urls") or []) if u]
    if len(urls) < 2:
        return JSONResponse(status_code=422, content={"ok": False, "error": "레퍼런스 URL 2개 이상 필요"})
    blocked = _ssrf_guard(*urls)      # 이 URL들은 run_mix_job이 그대로 다운로드한다
    if blocked:
        return blocked
    target = int(body.get("target_seconds") or 30)
    structure = body.get("structure") if body.get("structure") in ("template", "free") else "template"
    subtitle_removal = bool(body.get("subtitle_removal", False))
    job_id = uuid.uuid4().hex[:12]
    Store(DB_PATH).create_mix_job(job_id, urls, target, structure, subtitle_removal=subtitle_removal)
    background_tasks.add_task(run_mix_job, job_id, DB_PATH, _MIX_WORK_DIR)
    return {"ok": True, "job_id": job_id}


@app.post("/api/settings/vmake_key")
def api_set_vmake_key(body: dict):
    key = (body.get("key") or "").strip()
    Store(DB_PATH).set_setting("vmake_api_key", key)
    return {"ok": True}


@app.get("/api/settings/vmake_key")
def api_get_vmake_key():
    key = Store(DB_PATH).get_setting("vmake_api_key", "")
    return {"ok": True, "configured": bool(key)}      # 원문은 노출하지 않음


# 매칭 파이프라인의 '진행 중' 단계들(run_mix_job: downloading→extracting→planning→tts).
# 각 단계가 update_mix_job으로 updated_at을 갱신하므로, 여기 오래 멈춰 있으면 죽은 잔해다.
_MIX_ACTIVE_STAGES = ("downloading", "extracting", "planning", "tts")


@app.get("/api/mix/status/{job_id}")
def api_mix_status(job_id: str):
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"ok": False, "error": "job 없음"})
    status, error = job["status"], job["error"]
    # ★매칭 단계 staleness 가드(2026-07-18 실사고). 사장님이 '영상 매칭 시작' 후 다운로드 도중
    # 배포 재시작으로 BackgroundTask가 죽으면 except가 못 돌아 DB엔 이 상태가 **영원히** 남고,
    # 프론트는 10분째 무한 ⏳(렌더 단계엔 _render_is_stale가 있었으나 매칭 단계엔 없었다).
    # GET이라 DB는 안 건드리고 응답에서만 failed로 알린다 — 재실행(새 job)이 유일한 복구다.
    if status in _MIX_ACTIVE_STAGES and _render_is_stale(job):
        status = "failed"
        error = "서버 재시작 등으로 중단되었습니다. 다시 시도해 주세요."
    return {"ok": True, "status": status, "error": error,
            # 1단계 미리보기(2026-07-17): 폴러를 둘로 만들지 않으려고 기존 응답에 얹는다(스펙 §6.3).
            # preview_path는 서버 내부 경로라 안 내보낸다 — 파일은 전용 라우트로만 서빙.
            "preview_status": job.get("preview_status"),
            "preview_error": job.get("preview_error"),
            "clean_status": job.get("clean_status"),
            "clean_error": job.get("clean_error")}


@app.get("/api/mix/result/{job_id}")
def api_mix_result(job_id: str):
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job or not job.get("edit_plan"):
        return JSONResponse(status_code=404, content={"ok": False, "error": "아직 결과 없음"})
    plan = job["edit_plan"]
    flags = {f["beat_idx"] for f in plan.get("plagiarism_flags", [])}
    beats = []
    for b in plan["beats"]:
        beats.append({**b, "plagiarism_flag": b["beat_idx"] in flags,
                      "tts_preview_url": f"/api/mix/tts/{job_id}/{b['beat_idx']}",
                      "cap_segments": video_assemble._caption_segments(b.get("narration", ""))})
    detected = plan.get("detected_type") or _edit_plan._DEFAULT_TYPE
    return {
        "ok": True, "structure": plan["structure"], "beats": beats,
        "detected_type": detected,
        "detected_type_label": _edit_plan.VIDEO_TYPES.get(detected, {}).get("label", detected),
        "affiliate_target": plan.get("affiliate_target", ""),
        "video_types": [{"key": k, "label": v["label"]} for k, v in _edit_plan.VIDEO_TYPES.items()],
        # 검수판(Task4) — scene_match.py가 채운 미채택 제안(threshold 미달)을 그대로 넘긴다.
        # {beat_idx, asset_id, score}[]. 자동배치(cutaway)는 이미 beats[].cutaway에 있다.
        "asset_suggestions": plan.get("asset_suggestions") or [],
    }


@app.post("/api/mix/retype")
def api_mix_retype(background_tasks: BackgroundTasks, body: dict):
    """사용자가 감지된 영상 유형을 바꾸면 저장된 extract로 EDL+TTS 재생성(재다운로드 없음)."""
    job_id = body.get("job_id"); video_type = body.get("video_type")
    if video_type not in _edit_plan.VIDEO_TYPES:
        return JSONResponse(status_code=422, content={"ok": False, "error": "알 수 없는 영상 유형"})
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job or not job.get("extract"):
        return JSONResponse(status_code=404, content={"ok": False, "error": "재생성할 데이터 없음"})
    background_tasks.add_task(retype_mix_job, job_id, video_type, DB_PATH, _MIX_WORK_DIR)
    return {"ok": True}


@app.post("/api/mix/adjust")
def api_mix_adjust(body: dict):
    """비트 primary를 다른 seg로 교체. start/end는 서버가 extract 인벤토리에서 되붙임."""
    job_id = body.get("job_id"); beat_idx = body.get("beat_idx"); seg_id = body.get("seg_id")
    store = Store(DB_PATH)
    job = store.get_mix_job(job_id)
    if not job or not job.get("edit_plan") or not job.get("extract"):
        return JSONResponse(status_code=404, content={"ok": False, "error": "job/데이터 없음"})
    # video_id는 신뢰 안 함 — seg_id만으로 인벤토리에서 실제 video_id/start/end를 되붙인다(클라 숫자 위조 방지)
    seg_map, _ = _edit_plan._build_inventory(list(job["extract"].values()))
    grounded = _edit_plan._ground_ref({"seg_id": seg_id}, seg_map)
    if grounded is None:
        return JSONResponse(status_code=422, content={"ok": False, "error": "존재하지 않는 seg_id"})
    plan = job["edit_plan"]
    matched = False
    for b in plan["beats"]:
        if b["beat_idx"] == beat_idx:
            b["primary"] = grounded
            b["fit"] = None   # 화면이 바뀌었으니 옛 매칭점수 무효(사람이 눈으로 고름)
            matched = True
            break
    if not matched:
        return JSONResponse(status_code=404, content={"ok": False, "error": "beat_idx 없음"})
    store.update_mix_job(job_id, edit_plan=plan)
    return {"ok": True}


@app.get("/api/mix/segments/{job_id}")
def api_mix_segments(job_id: str):
    """[다른 화면으로] 피커용 — 이 잡의 모든 소스 세그먼트.
    used=이미 어느 비트 primary로 쓰인 seg_id(피커에서 흐리게)."""
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job or not job.get("extract"):
        return JSONResponse(status_code=404, content={"ok": False, "error": "데이터 없음"})
    seg_map, _ = _edit_plan._build_inventory(list(job["extract"].values()))
    used = {b["primary"]["seg_id"]
            for b in (job.get("edit_plan") or {}).get("beats", [])
            if b.get("primary")}
    segs = [{
        "seg_id": sid, "video_id": seg["video_id"],
        "start": seg["start"], "end": seg["end"],
        "dur": round(seg["end"] - seg["start"], 1),
        "scene_desc": seg.get("scene_desc", ""), "text": seg.get("text", ""),
        "thumb_url": f"/api/mix/seg_thumb/{job_id}/{sid}",
        "used": sid in used,
    } for sid, seg in seg_map.items()]
    return {"ok": True, "segments": segs}


@app.get("/api/mix/seg_thumb/{job_id}/{seg_id}")
def api_mix_seg_thumb(job_id: str, seg_id: str):
    """[다른 화면으로] 피커용 seg 썸네일(중간지점 프레임 jpg, 캐시).
    seg_id는 인벤토리 검증 후에만 파일명에 쓴다(경로 방어)."""
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job or not job.get("extract"):
        return JSONResponse(status_code=404, content={"ok": False, "error": "데이터 없음"})
    seg_map, _ = _edit_plan._build_inventory(list(job["extract"].values()))
    seg = seg_map.get(seg_id)
    if not seg:
        return JSONResponse(status_code=404, content={"ok": False, "error": "없는 seg_id"})
    work = _MIX_WORK_DIR / job_id
    cached = work / "seg_thumbs" / f"{seg_id}.jpg"
    if not cached.exists():
        try:
            src = _resolve_sources(job, work)[seg["video_id"]]
        except Exception:
            return JSONResponse(status_code=404, content={"ok": False, "error": "소스 없음"})
        mid = (seg["start"] + seg["end"]) / 2
        frame = extract_frame_at(src, work / "seg_thumbs", mid, filename=f"{seg_id}.jpg")
        if not frame:
            return JSONResponse(status_code=404, content={"ok": False, "error": "프레임 추출 실패"})
    return FileResponse(str(cached), media_type="image/jpeg")


@app.post("/api/mix/render")
def api_mix_render(background_tasks: BackgroundTasks, body: dict):
    """최종 렌더 예약. 미리보기(/api/produce/mix/preview)와 같은 중복예약 가드를 건다 —
    이쪽이 오히려 **돈이 나가는** 경로다(subtitle_removal이 켜져 있으면 VMake 유료 호출).

    가드가 없으면 더블클릭·폴링 재시도로 run_render가 2개 예약돼 같은 work/final.mp4에
    ffmpeg 둘이 동시에 쓰고(잘린 mp4가 status='done'으로 통과) VMake 유료 호출도 2회 나간다.
    run_render 안의 status='rendering'은 응답을 보낸 뒤에야 돌기 때문에 가드가 못 된다 —
    수십 ms 간격의 POST 2건이 둘 다 아직 이전 status를 보고 통과한다(TOCTOU).
    → 여기서 **동기적으로** 선기록한다.
    """
    job_id = body.get("job_id")
    store = Store(DB_PATH)
    job = store.get_mix_job(job_id)
    if not job or not job.get("edit_plan"):
        return JSONResponse(status_code=404, content={"ok": False, "error": "렌더할 job 없음"})
    # removing_subtitles = VMake 유료 단계 진행 중. 여기서 재예약되면 그 돈이 두 번 나간다.
    if job.get("status") in ("rendering", "removing_subtitles") and not _render_is_stale(job):
        return {"ok": True, "status": job["status"]}
    store.update_mix_job(job_id, status="rendering", error=None)
    background_tasks.add_task(run_render, job_id, DB_PATH, _MIX_WORK_DIR)
    return {"ok": True, "status": "rendering"}


_PREVIEW_STALE_SEC = 600   # 10분 — 이보다 오래 'rendering'이면 죽은 렌더의 잔해로 본다.


def _render_is_stale(job) -> bool:
    """'rendering' 상태가 **죽은 렌더의 잔해**인가 (미리보기·최종렌더 공용).

    status/preview_status는 DB 영속 상태인데 TTL·하트비트가 없다. 렌더 중 서버가 재시작되면
    (auto_deploy 크론 3분 — shopping_shorts 변경 시 systemd 재시작이라 자주 일어난다)
    BackgroundTask가 죽어 except가 못 돌고 DB엔 'rendering'이 **영원히** 남는다. 그러면 다시
    눌러도 위 중복예약 가드에 걸려 무한 ⏳이고, 'failed'가 안 오니 스펙 §7.1 탈출구도 안 열려
    **다음 버튼이 영구 잠긴다**(복구는 재매칭뿐인데 화면에 힌트가 없다).
    → updated_at 기준 타임아웃으로 재예약을 허용해 탈출구를 연다.
    """
    ts = job.get("updated_at")
    if not ts:
        return True                      # 알 수 없으면 갇히는 쪽보다 재시도 쪽으로
    try:
        dt = datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return True
    if dt.tzinfo is None:                # 옛 행이 naive면 UTC로 본다(store는 UTC로 쓴다)
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() > _PREVIEW_STALE_SEC


@app.post("/api/produce/mix/preview")
def api_produce_mix_preview(background_tasks: BackgroundTasks, body: dict):
    """1단계 미리보기 렌더 예약 — 유료 자막제거 없이(0원). 스펙 §6.3.

    다음 단계(자막제거)가 VMake 유료 API라, 컷·대본이 틀린 채 넘어가면 그 돈이 날아간다.
    그래서 여기서 먼저 공짜로 보여주고 OK를 받는다."""
    job_id = body.get("job_id")
    store = Store(DB_PATH)
    job = store.get_mix_job(job_id)
    if not job or not job.get("edit_plan"):
        return JSONResponse(status_code=422, content={"ok": False, "error": "매칭 먼저 실행하세요"})
    if job.get("preview_status") == "rendering" and not _render_is_stale(job):
        return {"ok": True, "status": "rendering"}   # 더블클릭 — ffmpeg를 두 번 돌리지 않는다
    # ★'rendering'을 여기서 **동기적으로** 쓴다. run_preview 안에서 쓰면 그건 응답을 보낸 뒤에
    # 도는지라, 수십 ms 간격의 POST 2건이 둘 다 위 가드를 통과해(둘 다 아직 None을 본다)
    # run_preview가 두 번 예약되고 ffmpeg 두 개가 같은 work/preview.mp4에 쓴다 —
    # 잘린 mp4가 'ready'로 게이트를 통과할 수 있다(TOCTOU).
    store.update_mix_job(job_id, preview_status="rendering", preview_error=None)
    background_tasks.add_task(run_preview, job_id, DB_PATH, _MIX_WORK_DIR)
    return {"ok": True, "status": "rendering"}


@app.get("/api/produce/mix/preview/{job_id}")
def api_produce_mix_preview_file(job_id: str):
    """1단계 미리보기 mp4 서빙(/api/produce/mix/poster와 같은 성격 — job의 미디어 파일)."""
    job = Store(DB_PATH).get_mix_job(job_id)
    path = (job or {}).get("preview_path")
    if not job or job.get("preview_status") != "ready" or not path or not Path(path).exists():
        return JSONResponse(status_code=404, content={"ok": False, "error": "미리보기 없음"})
    return FileResponse(path, media_type="video/mp4")


@app.post("/api/produce/mix/clean")
def api_produce_mix_clean(background_tasks: BackgroundTasks, body: dict):
    """2단계 자막제거 미리보기 — 각 소스 원본을 VMake로 청소해 캐시(유료).
    preview 라우트와 같은 중복예약 가드·동기 상태기록 패턴을 쓴다."""
    job_id = body.get("job_id")
    store = Store(DB_PATH)
    job = store.get_mix_job(job_id)
    if not job or not job.get("edit_plan"):
        return JSONResponse(status_code=422, content={"ok": False, "error": "매칭 먼저 실행하세요"})
    if job.get("clean_status") == "cleaning" and not _render_is_stale(job):
        return {"ok": True, "status": "cleaning"}       # 더블클릭 — VMake를 두 번 안 돌린다
    # 'cleaning'을 여기서 동기 기록(응답 전) — run 안에서 쓰면 이중예약된다(preview 라우트 주석 참조)
    store.update_mix_job(job_id, clean_status="cleaning", clean_error=None)
    background_tasks.add_task(run_clean_sources, job_id, DB_PATH, _MIX_WORK_DIR)
    return {"ok": True, "status": "cleaning"}


@app.get("/api/produce/mix/clean_thumb/{job_id}")
def api_produce_mix_clean_thumb(job_id: str, kind: str = "original"):
    """대표 소스(첫 소스)의 중간지점 프레임 PNG. kind=original|clean.
    clean은 clean_status=ready + 클린파일 존재일 때만(아니면 404). 양쪽 같은 t로 정렬."""
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"ok": False, "error": "job 없음"})
    work = _MIX_WORK_DIR / job_id
    vid = _source_video_id(0)
    if kind == "clean":
        src = (job.get("clean_sources") or {}).get(vid)
        if job.get("clean_status") != "ready" or not src or not Path(src).exists():
            return JSONResponse(status_code=404, content={"ok": False, "error": "클린 소스 없음"})
    else:
        try:
            src = _resolve_sources(job, work)[vid]
        except Exception:
            return JSONResponse(status_code=404, content={"ok": False, "error": "소스 없음"})
    dur = frame_extract._probe_duration(src) or 2.0
    frame = frame_extract.extract_frame_at(src, work / "clean_thumb", dur / 2,
                                           filename=f"{kind}.jpg")
    if not frame:
        return JSONResponse(status_code=404, content={"ok": False, "error": "프레임 추출 실패"})
    return FileResponse(str(frame), media_type="image/jpeg")


@app.get("/api/mix/tts/{job_id}/{beat_idx}")
def api_mix_tts(job_id: str, beat_idx: int):
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job or not job.get("edit_plan"):
        return JSONResponse(status_code=404, content={"ok": False})
    for b in job["edit_plan"]["beats"]:
        if b["beat_idx"] == beat_idx and b.get("tts_path") and Path(b["tts_path"]).exists():
            return FileResponse(b["tts_path"])
    return JSONResponse(status_code=404, content={"ok": False})


@app.post("/api/mix/tts/{job_id}/{beat_idx}/regen")
def api_mix_tts_regen(job_id: str, beat_idx: int, body: dict, background_tasks: BackgroundTasks):
    """비트 하나만 톤/성우 바꿔 재생성(+자막 재동기). 렌더 중이면 거부(P1-9 방지).
    status 코드는 mix_pipeline.run_render가 실제로 쓰는 값으로 확인함(grep, 2026-07-18):
    "rendering"(302행) → "removing_subtitles"(314행, vmake 자막제거 단계)."""
    store = Store(DB_PATH)
    job = store.get_mix_job(job_id)
    if not job or not job.get("edit_plan"):
        return JSONResponse(status_code=404, content={"ok": False, "error": "작업 없음"})
    if job.get("status") in ("rendering", "removing_subtitles"):
        return JSONResponse(status_code=409, content={"ok": False, "error": "렌더 중에는 재생성할 수 없어요"})
    # job의 voice 스냅샷(model_id·silence_trim·naturalize_profile 등) 위에 UI가 보낸
    # 톤/성우 키만 덮어쓴다 — 통째로 새 dict를 만들면 _voice_params가 나머지를 기본값으로
    # 채워 재생성 비트만 소리가 달라진다("작업대 소리 ≠ 렌더 소리", mix_pipeline._voice_params
    # 문서 참고, 2026-07-18 리뷰).
    override = dict(job.get("voice") or {})
    for k in ("voice_id", "settings", "speed"):
        if body.get(k) is not None:
            override[k] = body.get(k)
    background_tasks.add_task(resynth_one_beat, job_id, beat_idx, override, DB_PATH, _MIX_WORK_DIR)
    return {"ok": True}


@app.post("/api/mix/caption_offset/{job_id}/{beat_idx}")
def api_mix_caption_offset(job_id: str, beat_idx: int, body: dict):
    """비트 자막의 수동 시각 보정값(초)을 저장. 최종 _burn_captions가 읽어 반영."""
    offset = max(-2.0, min(2.0, float(body.get("offset") or 0.0)))
    store = Store(DB_PATH)
    job = store.get_mix_job(job_id)
    if not job or not job.get("edit_plan"):
        return JSONResponse(status_code=404, content={"ok": False, "error": "작업 없음"})
    plan = job["edit_plan"]
    beat = next((b for b in plan["beats"] if b["beat_idx"] == beat_idx), None)
    if beat is None:
        return JSONResponse(status_code=404, content={"ok": False, "error": "비트 없음"})
    beat["cap_offset"] = offset
    store.update_mix_job(job_id, edit_plan=plan)
    return {"ok": True, "offset": offset}


@app.get("/api/voice-presets")
def api_voice_presets(lang: str = "KR"):
    """성우별 그룹 목록(유저 노출용 — source_ref는 내부 전용이라 제외).

    성우 1명당 stable(기본 노출)/natural/expressive를 variants에 묶어 반환하고,
    베스트 5명은 whisper까지 4톤이다(2026-07-16 청취 판정). best=베스트 성우 플래그로,
    프론트가 ⭐ 배지에 쓴다. **순서는 여기서 정하지 않는다** — Store.list_voice_presets의
    ORDER BY best DESC, created_at이 정본이고 이 함수는 그 순서를 보존만 한다."""
    rows = Store(DB_PATH).list_voice_presets(lang=lang)
    groups = {}
    for p in rows:
        # 튜닝 작업대가 만든 임시 프리셋(origin="tuned", :1526)은 카드에서 뺀다.
        # prune_voice_presets가 그 행을 **의도적으로** 안 지우므로(작업대엔 필요, 리뷰 S2)
        # 거르지 않으면 이름·설명·샘플이 다 빈 껍데기가 성우 카드로 뜬다 — 2026-07-17
        # 라이브 화면에서 kr-test·kr-snap이 실제로 그렇게 보였다(사장님이 화면을 보라고
        # 해서 브라우저로 직접 열어보고 발견). DB에 남는 건 맞고 카드에 나오는 게 틀렸다.
        # ⚠️ origin이 없는 옛 행은 **보이는 쪽으로** 실패시킨다 — 안 보이는 실패는
        # 아무도 못 잡고, 성우가 통째로 사라지는 쪽이 훨씬 나쁘다.
        if p.get("origin") == "tuned":
            continue
        gid = p["group_id"]
        g = groups.setdefault(gid, {
            "group_id": gid, "name": p["name"], "one_liner": p["one_liner"],
            "lang": p["lang"], "archetype": p["archetype"],
            # best는 성우(그룹)의 성질이라 첫 행에서 한 번만 집는다 — 같은 성우의
            # 3~4개 variant 행은 모두 같은 값이다. 순서는 Store가 이미 정해서
            # 줬고(ORDER BY best DESC), dict가 삽입 순서를 보존하므로 여기선 보존만 한다.
            "best": bool(p.get("best", False)),
            "default_variant": "stable", "variants": {},
        })
        g["variants"][p["variant"]] = {
            "preset_id": p["preset_id"], "voice_id": p["base_voice_id"],
            "voice_settings": p["voice_settings"], "default_speed": p["default_speed"],
            "default_silence_trim": p["default_silence_trim"],
            "sample_url": f"/api/voice-presets/{p['preset_id']}/sample" if p["sample_file"] else None,
        }
    return {"ok": True, "groups": list(groups.values())}


@app.get("/api/voice-presets/{preset_id}/sample")
def api_voice_preset_sample(preset_id: str):
    p = Store(DB_PATH).get_voice_preset(preset_id)
    if not p or not p.get("sample_file"):
        return JSONResponse(status_code=404, content={"ok": False})
    f = voice_presets.SAMPLES_DIR / p["sample_file"]
    if not f.exists():
        return JSONResponse(status_code=404, content={"ok": False})
    # no-cache = "캐시는 해도 되지만 쓰기 전에 반드시 서버에 물어봐라".
    # 샘플은 성우를 재튜닝할 때마다 **파일 내용이 바뀌는데 이름은 그대로**라, 헤더가 없으면
    # 브라우저가 옛것을 무기한 들려준다 — 2026-07-17 실사고: 47개를 새 속도로 재생성·배포한
    # 뒤에도 사장님 화면에선 옛 소리가 났다(미나 속삭임 브라우저 3.2초 vs 서버 7.1초).
    # FileResponse가 etag·last-modified를 붙이므로 안 바뀌었으면 304로 싸게 끝난다
    # (no-store가 아니다 — 매번 통째로 다시 받게 하면 그건 그것대로 낭비다).
    return FileResponse(str(f), media_type="audio/mpeg",
                        headers={"Cache-Control": "no-cache"})


_TUNE_CORPUS = Path(__file__).parent / "assets" / "tune_corpus.json"
_TUNE_CACHE = Path(__file__).parent / "data" / "voice_tune_cache"


@app.get("/api/voice-tune/corpus")
def api_voice_tune_corpus():
    """튜닝 작업대 회귀 코퍼스(고정 10줄) — role별 카드로 렌더링."""
    import json as _json
    lines = _json.loads(_TUNE_CORPUS.read_text(encoding="utf-8")) if _TUNE_CORPUS.exists() else []
    return {"lines": lines}


@app.post("/api/voice-tune/preview")
async def api_voice_tune_preview(req: Request):
    """합성 없이 naturalize만 실행해 변환텍스트를 실시간 미리보기."""
    body = await req.json()
    text = body.get("text", "")
    profile = body.get("profile") or {}
    out = _naturalize(text, profile, beat_role=body.get("beat_role"),
                      beat_index=body.get("beat_index"), beat_total=body.get("beat_total"))
    return {"text": out}


@app.post("/api/voice-tune/synth")
async def api_voice_tune_synth(req: Request):
    """코퍼스 한 줄을 **실제 렌더와 동일한 경로**로 합성 + ASR diff.

    성우·감도·속도·무음삭제·model_id를 전부 preset_id로 서버가 조회해 쓴다 — 클라이언트가
    일부만 보내던 탓에 작업대는 기본성우(Rachel)·1.0배속·후처리없음으로 합성돼 사장님이
    "튜닝해서 승인한 소리"와 영상 소리가 딴판이었다(2026-07-15 리뷰 S3/S5/S6/S8).
    캐시 키에 nonce를 포함해 '재롤'이 실제로 새 take를 뽑게 한다(S9)."""
    body = await req.json()
    profile = body.get("profile") or {}
    preset_id = body.get("preset_id", "adhoc")
    voice = _voice_snapshot(Store(DB_PATH), {"preset_id": preset_id,
                                             "speed": body.get("speed"),
                                             "silence_trim": body.get("silence_trim")})
    if body.get("speed") is None:      # 프리셋 기본 속도/무음삭제를 그대로 따른다(렌더와 동일)
        p = Store(DB_PATH).get_voice_preset(preset_id) or {}
        voice["speed"] = p.get("default_speed", 1.0)
        voice["silence_trim"] = p.get("default_silence_trim", "off")
    import json as _json
    key_src = (f"{body.get('text','')}|{_json.dumps(profile, sort_keys=True, ensure_ascii=False)}"
               f"|{voice.get('voice_id')}|{voice.get('speed')}|{body.get('nonce','')}")
    key = hashlib.sha1(key_src.encode()).hexdigest()[:16]
    _TUNE_CACHE.mkdir(parents=True, exist_ok=True)
    out = _TUNE_CACHE / f"{preset_id}_{body.get('line_id', 'x')}_{key}.mp3"
    if out.exists():
        text = _naturalize(body.get("text", ""), profile, beat_role=body.get("beat_role"),
                           beat_index=body.get("beat_index"), beat_total=body.get("beat_total"))
    else:
        text = mix_pipeline.synthesize_line(
            body.get("text", ""), out, voice=voice, profile=profile,
            beat_role=body.get("beat_role"), beat_index=body.get("beat_index"),
            beat_total=body.get("beat_total"),
            previous_text=body.get("previous_text"), next_text=body.get("next_text"),
        )
    hyp = asr_check.transcribe(str(out))
    diff = asr_check.diff_words(text, hyp) if hyp else {"ok": True, "words": [], "no_asr": True}
    return {"audio_url": f"/api/voice-tune/audio/{out.name}", "text": text, "diff": diff}


@app.get("/api/voice-tune/audio/{fname}")
def api_voice_tune_audio(fname: str):
    f = _TUNE_CACHE / fname
    if not f.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(str(f), media_type="audio/mpeg")


@app.get("/api/voice-tune/profile/{preset_id}")
def api_voice_tune_profile_get(preset_id: str):
    p = Store(DB_PATH).get_voice_preset(preset_id)
    return {"profile": (p or {}).get("naturalize_profile") if p else None}


@app.post("/api/voice-tune/profile/{preset_id}")
async def api_voice_tune_profile_save(preset_id: str, req: Request):
    """튜닝 작업대에서 완성한 프로파일을 프리셋에 동결 저장. 없는 preset_id면 작업대 임시 프리셋 생성."""
    body = await req.json()
    store = Store(DB_PATH)
    p = store.get_voice_preset(preset_id)
    if not p:
        # origin='tuned' — prune_voice_presets(curated 전용 삭제)가 이 행을 지우지 않게 한다(리뷰 S2).
        p = {"preset_id": preset_id, "name": preset_id, "lang": "KR",
             "base_voice_id": body.get("voice_id", "v"), "voice_settings": {},
             "model_id": "eleven_v3", "origin": "tuned"}
    prof = dict(body.get("profile") or {})
    prof["_frozen"] = bool(body.get("frozen"))
    p["naturalize_profile"] = prof
    store.upsert_voice_preset(p)
    return {"ok": True}


def _voice_snapshot(store, body):
    """UI 선택(body) + 프리셋 DB → job에 저장할 voice 스냅샷.

    **naturalize_profile·model_id는 반드시 프리셋에서 조회해 넣어야 한다.** 이게 빠지면
    튜닝 작업대에서 동결한 프로파일이 렌더에 도달하지 못하고, 에러 없이 기본값으로 조용히
    합성돼 "동결했는데 소리가 그대로"가 된다(2026-07-15 whole-branch 리뷰 S1).
    미리듣기(/api/mix/voice/preview)도 같은 스냅샷을 써야 미리듣기=렌더가 보장된다(S8).

    body.whisper_roles: 영상별 "이 영상은 속삭임을 훅에만" 오버라이드(2026-07-17). 설계문서
    §6은 "영상별 비트 토글은 새 저장층이 필요하다"고 적었지만 틀렸다 — 이 함수가 만드는
    voice 스냅샷이 이미 job(영상)마다 저장된다(app.py의 store.update_mix_job(job_id, voice=...)).
    그래서 새 테이블 없이 body 값을 naturalize_profile.whisper.roles에만 얹는다.
    없으면(None/누락) 프리셋의 원래 프로파일을 그대로 쓴다(하위호환 — 기존 호출부가 안 깨짐).
    프리셋 dict는 store가 매번 새로 만들어 주지만(json.loads), 혹시 캐싱하는 구현으로 바뀌어도
    안전하도록 **제자리 수정 없이** 얕은 복사 위에서만 whisper 키를 교체한다."""
    preset_id = body.get("preset_id")
    p = store.get_voice_preset(preset_id) if preset_id else None
    naturalize_profile = (p or {}).get("naturalize_profile")
    whisper_roles = body.get("whisper_roles")
    if whisper_roles is not None:
        naturalize_profile = dict(naturalize_profile) if naturalize_profile else {}
        naturalize_profile["whisper"] = dict(naturalize_profile.get("whisper") or {})
        naturalize_profile["whisper"]["roles"] = whisper_roles
    return {
        "preset_id": preset_id,
        "voice_id": body.get("voice_id") or (p or {}).get("base_voice_id"),
        "settings": body.get("settings") or (p or {}).get("voice_settings"),
        "speed": body.get("speed", 1.0),
        "silence_trim": body.get("silence_trim", "off"),
        "naturalize_profile": naturalize_profile,
        "model_id": (p or {}).get("model_id") or "eleven_v3",
    }


@app.post("/api/mix/voice")
def api_mix_voice(background_tasks: BackgroundTasks, body: dict):
    """프리셋 선택을 job에 스냅샷 저장 후 기존 plan에 대해 TTS 재생성(백그라운드).
    body: {job_id, preset_id?, voice_id, settings, speed, silence_trim}."""
    job_id = body.get("job_id")
    store = Store(DB_PATH)
    job = store.get_mix_job(job_id)
    if not job or not job.get("edit_plan"):
        return JSONResponse(status_code=404, content={"ok": False, "error": "job/plan 없음"})
    voice = _voice_snapshot(store, body)
    store.update_mix_job(job_id, voice=voice)
    background_tasks.add_task(resynth_tts_job, job_id, DB_PATH, _MIX_WORK_DIR)
    return {"ok": True}


@app.post("/api/mix/voice/preview")
def api_mix_voice_preview(body: dict):
    """첫 비트만 주어진 설정으로 즉시 합성해 미리듣기 mp3 반환('이 대본으로 다시 듣기')."""
    job_id = body.get("job_id")
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job or not job.get("edit_plan") or not job["edit_plan"].get("beats"):
        return JSONResponse(status_code=404, content={"ok": False, "error": "plan 없음"})
    beats = job["edit_plan"]["beats"]
    d = _MIX_WORK_DIR / job_id / "tts"
    d.mkdir(parents=True, exist_ok=True)
    out = d / "preview.mp3"
    # 렌더와 동일한 공유 경로(synthesize_line)로 합성한다 — 직접 synthesize_tts를 부르면
    # naturalize 미적용·model v2로 나가 "미리듣기랑 영상 소리가 다르다"가 된다(리뷰 S8).
    mix_pipeline.synthesize_line(
        beats[0]["narration"], out, voice=_voice_snapshot(Store(DB_PATH), body),
        beat_role=beats[0].get("role"), beat_index=0, beat_total=len(beats),
        next_text=beats[1]["narration"] if len(beats) > 1 else None,
    )
    return FileResponse(str(out), media_type="audio/mpeg")


@app.get("/api/mix/video/{job_id}")
def api_mix_video(job_id: str):
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job or not job.get("video_path") or not Path(job["video_path"]).exists():
        return JSONResponse(status_code=404, content={"ok": False})
    return FileResponse(job["video_path"])


def _thumb_dir(job_id: str):
    """job_id 검증 후 그 job의 썸네일 폴더. 경로순회를 여기서 한 번에 막는다.
    부적합하면 None — 호출부가 400으로 돌려준다(이 파일은 HTTPException을 안 쓴다)."""
    safe = os.path.basename(job_id)
    if not safe or safe != job_id or safe in (".", ".."):
        return None
    return _THUMB_DIR / safe


@app.post("/api/produce/thumb/frames")
def api_thumb_frames(body: dict):
    """5단계 썸네일 — 믹스 결과 영상을 등분해 후보 프레임 10장.

    자막이 박히지 않은 배경(자막제거본·미리보기)에서 뽑는다(설계 Q1) — 썸네일 텍스트는
    위에 새로 얹으므로 배경 자막은 방해다. 이미 뽑아뒀으면 재추출하지 않는다.
    """
    job_id = str(body.get("job_id") or "")
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"ok": False, "error": "job 없음"})
    # ★배경 영상 우선순위 — 썸네일 배경은 **자막이 없어야 한다**(설계 Q1: 제목을 위에 새로
    # 얹으니 배경 자막은 방해). 그래서 자막제거본(clean_video_path)·자막 없는 미리보기
    # (preview_path)를 먼저 쓰고, 최종 렌더(video_path)는 **최후 폴백**이다 — 최종은 우리
    # 나레이션 자막이 박혀 있어(사장님 제보 2026-07-19: "썸네일에 자막 필요없음") 배경으로 부적합했다.
    # 예전엔 video_path를 먼저 봐서 자막 박힌 프레임이 나왔다.
    # 셋 다 검사하므로 렌더 전(video_path 없음)에도 preview로 프레임을 뽑을 수 있다
    # (매칭 끝낸 작업이라도 최종 영상이 없어 "믹스 영상 없음"으로 막히던 것도 그대로 해소).
    video = None
    for cand in (job.get("clean_video_path"), job.get("preview_path"), job.get("video_path")):
        if cand and Path(cand).exists():
            video = cand
            break
    if not video:
        return JSONResponse(status_code=404, content={"ok": False, "error": "믹스 영상 없음"})

    out_dir = _thumb_dir(job_id)
    if out_dir is None:
        return JSONResponse(status_code=400, content={"ok": False, "error": "bad job_id"})

    # 재렌더 감지(리뷰 픽스1): mix_pipeline은 job_id로 결정적인 경로(work/job_id/final.mp4)에
    # 렌더하므로 재렌더는 "같은 파일"을 덮어쓴다 — video_path 문자열도 안 바뀐다.
    # n=10 고정이라 "개수가 같은가"만으로는 옛 프레임인지 절대 구분 못 한다.
    # 그래서 추출 시점 영상의 mtime_ns+size를 서명으로 같이 저장해두고 비교한다.
    # (해시는 과하다 — 영상이 수십 MB.)
    vstat = Path(video).stat()
    video_sig = f"{vstat.st_mtime_ns}:{vstat.st_size}"

    thumb = job.get("thumbnail") or {}
    existing = sorted(out_dir.glob("grid_*.jpg")) if out_dir.exists() else []
    if existing and thumb.get("video_sig") == video_sig:
        meta = thumb.get("frames") or []
        if len(meta) == len(existing):
            return {"ok": True, "frames": meta}

    # 재추출(재재조사 픽스1·2, 2026-07-17): 여기서 rmtree(out_dir)를 돌리면 안 된다.
    # 같은 out_dir을 T4(썸네일 저장, task-4-brief.md)가 써서 사용자가 고른
    # thumb_N.png를 저장한다 — rmtree는 그것까지 통째로 지워 재렌더 한 번에
    # "고른 썸네일이 증발 + DB는 죽은 파일명을 계속 가리킴(깨진 이미지)"이 났다(실측).
    # 게다가 grid_{i:02d}.jpg는 n=10 고정의 결정적 파일명이라 애초에 지울 필요가
    # 없다 — 재추출이 그냥 덮어쓴다. rmtree를 추출 *전에* 돌리는 것도 문제였다:
    # 추출이 RuntimeError로 실패하면(ffmpeg 일시 오류 등) 폴더는 이미 비었는데 DB의
    # frames는 죽은 URL 10개를 그대로 들고 있어 "실패하면 이전보다 나빠짐"이 됐다.
    try:
        pairs = extract_grid_frames(video, out_dir, n=10)
    except RuntimeError as e:
        return JSONResponse(status_code=502, content={"ok": False, "error": str(e)})

    # 추출 *성공 후에만*, 우리 소유 파일(grid_*.jpg)만, 개별로 고아를 정리한다.
    # 부분 실패(extract_frame_at은 실패 시 조용히 None -- 기존 계약)로 새 결과에
    # 없는 옛 grid_*.jpg가 남으면 existing(glob) vs meta(frames) 개수가 영영 안
    # 맞아 매 요청마다 재추출이 돈다. thumb_*.png(T4 소유, 사용자가 고른 썸네일)는
    # 이 정리 대상에 절대 넣지 않는다 — 우리가 만든 게 아니다.
    new_names = {p.name for p, _ in pairs}
    for old in out_dir.glob("grid_*.jpg"):
        if old.name not in new_names:
            old.unlink(missing_ok=True)

    frames = [{"url": f"/api/produce/thumb/file/{job_id}/{p.name}", "ts": round(ts, 2)}
              for p, ts in pairs]
    thumb["frames"] = frames
    thumb["video_sig"] = video_sig
    Store(DB_PATH).update_mix_job(job_id, thumbnail=thumb)
    return {"ok": True, "frames": frames}


@app.get("/api/produce/thumb/file/{job_id}/{name}")
def api_thumb_file(job_id: str, name: str):
    """프레임·썸네일 파일 서빙. 파일명은 basename으로 강제한다."""
    safe_name = os.path.basename(name)
    d = _thumb_dir(job_id)
    # safe_name in (".",".."): os.path.basename("..") == ".." 라 위 등가검사만으론
    # 안 걸린다(2026-07-17 실측) — job_id 쪽 _thumb_dir과 동일하게 명시 차단.
    if d is None or not safe_name or safe_name != name or safe_name in (".", ".."):
        return JSONResponse(status_code=400, content={"ok": False, "error": "bad path"})
    path = d / safe_name
    # exists()가 아니라 is_file()이어야 한다(리뷰 픽스2, 2026-07-17 실측): name=" "이면
    # 윈도우가 경로 끝 공백을 잘라내 path가 d 자신이 되어 exists()는 True를 내지만
    # 파일이 아니라 디렉터리라 FileResponse가 RuntimeError를 던져 잡히지 않고 500이 나간다.
    if not path.is_file():
        return JSONResponse(status_code=404, content={"ok": False})
    return FileResponse(str(path))


@app.post("/api/produce/thumb/save")
async def api_thumb_save(job_id: str = Form(...), meta: str = Form(...),
                         file: UploadFile = File(...)):
    """브라우저 canvas가 합성한 PNG를 받아 저장한다(설계 Q3 — 서버는 합성하지 않는다).

    ★파일명은 서버가 부여한다. 클라이언트가 준 file.filename은 쓰지 않는다
    (경로순회 재료). meta(레이어·프레임)는 같은 thumbnail_json에 함께 보존한다.
    """
    import json as _json          # app.py 관례(:1448·:1482) — 최상위 import 아님
    store = Store(DB_PATH)
    job = store.get_mix_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"ok": False, "error": "job 없음"})

    data = await file.read()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):     # PNG 시그니처
        return JSONResponse(status_code=400, content={"ok": False, "error": "PNG가 아님"})
    try:
        meta_obj = _json.loads(meta)
    except (ValueError, TypeError):
        return JSONResponse(status_code=400, content={"ok": False, "error": "meta 파싱 실패"})
    if not isinstance(meta_obj, dict):
        return JSONResponse(status_code=400, content={"ok": False, "error": "meta는 dict여야 합니다"})

    out_dir = _thumb_dir(job_id)
    if out_dir is None:
        return JSONResponse(status_code=400, content={"ok": False, "error": "bad job_id"})
    out_dir.mkdir(parents=True, exist_ok=True)
    thumb = job.get("thumbnail") or {}
    results = list(thumb.get("results") or [])
    name = f"thumb_{len(results) + 1}.png"
    while (out_dir / name).exists():               # 갤러리 삭제 이력이 있어도 안 덮어쓴다
        name = f"thumb_{len(results) + 1}_{uuid.uuid4().hex[:4]}.png"
    (out_dir / name).write_bytes(data)

    results.append(name)
    # ★meta를 통째로 합치지 않는다. frames(Task 3이 만든 후보목록)·results·selected는
    #  서버 소유라 클라이언트가 덮으면 안 된다 — 편집 상태만 화이트리스트로 받는다.
    for k in ("frame_ts", "frame_url", "layers"):
        if k in meta_obj:
            thumb[k] = meta_obj[k]
    thumb["results"] = results
    store.update_mix_job(job_id, thumbnail=thumb)
    return {"ok": True, "name": name,
            "url": f"/api/produce/thumb/file/{job_id}/{name}"}


@app.post("/api/produce/thumb/select")
def api_thumb_select(body: dict):
    """최종 썸네일 1장 지정. results에 있는 이름만 허용한다."""
    job_id = str(body.get("job_id") or "")
    name = str(body.get("name") or "")
    store = Store(DB_PATH)
    job = store.get_mix_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"ok": False, "error": "job 없음"})
    thumb = job.get("thumbnail") or {}
    if name not in (thumb.get("results") or []):
        return JSONResponse(status_code=400, content={"ok": False, "error": "없는 썸네일"})
    thumb["selected"] = name
    store.update_mix_job(job_id, thumbnail=thumb)
    return {"ok": True}


def _reject_cdn_proxy(url: str, allowed_hosts) -> bool:
    """CDN 프록시(/api/thumb·/api/video)에 들어온 url이 거부 대상인가.

    ★부분문자열 검사(`h in url`)를 쓰면 안 된다. 그건 URL 문자열 아무 데나 허용호스트
    이름이 들어있기만 하면 통과시키므로
        http://169.254.169.254/latest/meta-data/...?x=cdninstagram.com
    이 화이트리스트를 뚫고, 서버가 AWS 메타데이터에 GET을 보내 응답 본문을 그대로
    돌려준다(이 서버는 Lightsail — IAM 크리덴셜 직결). 반드시 파싱한 hostname으로
    정확일치/서브도메인 일치만 허용하고, 내부망 차단(_reject_ssrf)도 함께 건다.
    """
    if _reject_ssrf(url) is not None:
        return True
    try:
        host = (urllib.parse.urlparse(url).hostname or "").lower()
    except ValueError:
        return True
    if not host:
        return True
    return not any(host == h or host.endswith("." + h) for h in allowed_hosts)


def _ssrf_guard(*urls):
    """URL을 받아 다운로드하는 라우트의 공통 전처리. 문제 있으면 422 응답, 없으면 None.

    P0-3: _reject_ssrf가 /api/scene/save/prepare 한 곳에만 걸려 있어서, 임의 URL을
    download_any/download_video로 그대로 fetch하는 나머지 라우트(mix/start·
    extract_from_url·save_to_wiki·wiki/save)는 전부 무방비였다. 가드가 "어떤 라우트엔
    있고 어떤 라우트엔 없는" 상태 자체가 결함이라, 호출부를 하나로 모은다.
    """
    for u in urls:
        err = _reject_ssrf(u)
        if err:
            return JSONResponse(status_code=422, content={"ok": False, "error": err})
    return None


# 허용 CDN 도메인만 프록시 (SSRF 방지 — 임의 URL 프록시 금지).
# 인스타 + 유튜브(ytimg) + 틱톡(tiktokcdn) 썸네일 호스트.
_ALLOWED_THUMB_HOSTS = ("cdninstagram.com", "fbcdn.net", "ytimg.com",
                        "ggpht.com", "tiktokcdn.com", "tiktokcdn-us.com",
                        # 샤오훙슈(rednote) 커버 CDN — lens/grab로 담은 영상 썸네일.
                        # 없으면 /api/thumb가 400→제작소 재료 카드에서 샤오훙슈 썸네일만 안 뜸(실측 2026-07-19).
                        "xhscdn.com")
_ALLOWED_VIDEO_HOSTS = ("cdninstagram.com", "fbcdn.net")


@app.get("/api/thumb")
def api_thumb(url: str):
    """인스타 CDN 썸네일 프록시 (핫링크 차단 우회). url=원본 이미지 주소."""
    import requests
    from fastapi.responses import Response
    if _reject_cdn_proxy(url, _ALLOWED_THUMB_HOSTS):
        return Response(status_code=400, content=b"invalid host")
    # 호스트에 맞는 Referer로 핫링크 차단을 우회한다. xhscdn은 인스타 referer로도 200이
    # 오지만(실측), 만료토큰형 URL 대비 정확한 출처를 보낸다. tiktok도 자기 도메인으로.
    ref = "https://www.instagram.com/"
    if "xhscdn.com" in url:
        ref = "https://www.xiaohongshu.com/"
    elif "tiktokcdn" in url:
        ref = "https://www.tiktok.com/"
    try:
        r = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": ref,
        })
        r.raise_for_status()
        ctype = r.headers.get("Content-Type", "image/jpeg")
        return Response(content=r.content, media_type=ctype,
                        headers={"Cache-Control": "public, max-age=86400"})
    except Exception:
        return Response(status_code=404, content=b"")


@app.get("/api/video")
def api_video(url: str):
    """인스타 CDN 릴스 영상 프록시 (핫링크 차단 우회) — 썸네일 인라인 재생용.
    /api/thumb와 동일 패턴(Referer 헤더). 릴스는 수 MB라 통째로 프록시."""
    import requests
    from fastapi.responses import Response
    if _reject_cdn_proxy(url, _ALLOWED_VIDEO_HOSTS):
        return Response(status_code=400, content=b"invalid host")
    try:
        r = requests.get(url, timeout=30, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.instagram.com/",
        })
        r.raise_for_status()
        ctype = r.headers.get("Content-Type", "video/mp4")
        return Response(content=r.content, media_type=ctype,
                        headers={"Cache-Control": "public, max-age=3600"})
    except Exception:
        return Response(status_code=404, content=b"")


@app.get("/api/media")
def api_media(platform: str, id: str):
    """유튜브/틱톡 영상 → 진행형 mp4 direct URL(프론트 <video>가 embed 대신 이 URL로
    재생 → same-origin canvas 캡처 가능, 2026-07-14). 실패 시 ok:false(프론트 embed 폴백)."""
    url = resolve_media_url(platform, id)
    return {"ok": bool(url), "url": url}


@app.post("/api/lens/search")
async def api_lens_search(request: Request, frame: UploadFile = File(...),
                           source_caption: str = Form("")):
    """멈춘 프레임 캡처 이미지 → 구글렌즈 → 5플랫폼 유사영상. 월 호출가드(429 lens_limit).

    캡처본을 find_frames/lens/{uuid}.jpg로 저장하고 기존 /api/find/frame 서빙
    (SerpApi가 쿠키없이 fetch 가능한 _AUTH_ALLOW 경로)으로 공개 URL을 만든다."""
    store = Store(DB_PATH)
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    limit = int(store.get_setting("lens_month_limit", _LENS_MONTH_LIMIT_DEFAULT))
    if store.lens_month_count(month) >= limit:
        return JSONResponse(status_code=429, content={
            "ok": False, "error_code": "lens_limit",
            "error": f"이번 달 렌즈 검색 한도({limit}회)를 다 썼습니다"})
    raw = await frame.read()
    # Google Lens는 갓 호스팅된 우리서버 이미지를 인덱싱 전이라 못 읽어 0개를 준다(실측).
    # imgbb·imgur은 Google이 상시 크롤링하는 도메인이라 즉시 매칭 → imgbb(전용키) 1순위,
    # imgur(공유 공개ID) 2순위로 업로드, 실패 시에만 우리서버 URL 폴백(2026-07-14).
    image_url = upload_frame(raw)
    if not image_url:
        work_dir = _FIND_TMP_DIR / "lens"
        work_dir.mkdir(parents=True, exist_ok=True)
        name = uuid.uuid4().hex + ".jpg"
        (work_dir / name).write_bytes(raw)
        image_url = f"{PUBLIC_BASE_URL}/api/find/frame/lens/{name}"
    items = search_similar_videos(image_url, source_caption=source_caption)
    store.bump_lens(month)
    return {"ok": True, "items": items, "count": len(items)}


# 캡션 → 중국 플랫폼 검색어. 구글렌즈는 시각검색이라 키워드가 없지만 샤오홍슈/도우인은
# 키워드 검색이라 캡션에서 핵심어를 뽑아야 한다. 앞쪽 의미토큰 2개를 붙여 쓴다(제품명이
# 보통 캡션 앞에 온다). 불용어·해시태그 기호는 제거.
_CN_STOP = {"그리고", "진짜", "완전", "오늘", "이거", "저거", "제가", "너무", "정말",
            "이번", "우리", "해서", "하는", "있는", "같은", "위한", "shorts", "reels",
            "the", "and", "for", "with", "this", "that", "from"}
_CN_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]{2,}")


def _cn_keyword(caption):
    """캡션 → 검색어(앞쪽 의미토큰 3개). 없으면 ''."""
    if not caption:
        return ""
    toks = [t for t in _CN_TOKEN_RE.findall(caption) if t.lower() not in _CN_STOP]
    return " ".join(toks[:3])


# ⚠️ 2026-07-18: 프론트가 더 이상 호출하지 않음(Apify 과금 회피). 나머지 4개 플랫폼은
# 바로가기+담기로 대체. 엔드포인트·테스트는 유지(완전 삭제는 별도 정리 태스크).
@app.post("/api/lens/cn")
async def api_lens_cn(request: Request, frame: UploadFile = File(None),
                       source_caption: str = Form(""), max_results: int = Form(8)):
    """프레임+캡션으로 샤오홍슈+도우인을 검색 → 렌즈 결과에 합류할 항목. 두 '장치'로 정확도를 높인다:

    ★장치1(비전 추출): 렌즈가 캡처한 프레임(썸네일)을 Gemini 비전이 보고 화면 글자(제품명
      'LED 물총')·생김새+캡션을 종합해 '바로 그 제품'을 특정하고 중국어 검색어를 만든다
      (서버 실측: 리모와 캐리어→日默瓦, 청소용 퍼미스 스톤→浮石清洁块). 프레임 없음/실패 시
      캡션 소재 키워드(cn_search_keyword) → 앞토큰 직역 순으로 폴백.
    ★장치2(유사도 판정): 검색 결과 제목들을 추출 제품과 대조해 Gemini가 same/similar/no로
      판정(오탐 많던 2그램 대체) → same을 위로 정렬, no엔 프론트 ⚠️배지.

    Apify·Gemini가 느리고 유료라 렌즈 결과가 뜬 뒤 프론트가 비동기로 이 API를 호출해 합친다."""
    if not (source_caption or "").strip() and frame is None:
        return {"ok": True, "items": [], "count": 0, "note": "프레임·캡션이 없어 검색어를 만들 수 없습니다"}
    if not APIFY_TOKENS:
        return {"ok": True, "items": [], "count": 0, "note": "APIFY 토큰 없음"}
    product, keyword = "", ""
    if frame is not None:                              # 장치1: 프레임 비전 추출
        try:
            raw = await frame.read()
            v = cn_search_keyword_vision(raw, source_caption)
            product, keyword = v.get("product", ""), v.get("zh", "")
        except Exception:
            product, keyword = "", ""
    if not keyword:                                    # 폴백: 캡션 소재 키워드 → 앞토큰 직역
        try:
            keyword = cn_search_keyword(source_caption)
        except Exception:
            keyword = ""
    if not keyword:
        ko = _cn_keyword(source_caption)
        try:
            keyword = (translate_keyword(ko).get("zh") or "").strip() or ko
        except Exception:
            keyword = ko
    if not keyword:
        return {"ok": True, "items": [], "count": 0, "note": "검색어를 만들지 못했습니다"}
    # 실측(2026-07-18): 액터는 maxResults=40도 raw=video=40을 ~14초에 준다(8과 지연 차 거의 없음).
    # 웹검색 대비 개수 부족 제보로 상한을 60까지 열어둔다(프론트 기본 40). 결과당 과금이라 비용은 비례.
    n = max(1, min(int(max_results or 8), 60))

    def _run(platform, mod):
        try:
            rows = mod.search(keyword, max_results=n)
        except Exception:
            return []
        for r in rows:
            r["platform"] = platform
            r["match"] = None
        return rows

    with ThreadPoolExecutor(max_workers=2) as ex:
        fx = ex.submit(_run, "xiaohongshu", xiaohongshu_search)
        fd = ex.submit(_run, "douyin", douyin_search)
        items = fx.result() + fd.result()

    # 장치2: 유사도 판정 + same 우선 정렬
    if product and items:
        try:
            verdicts = judge_same_product(product, [i.get("title", "") for i in items])
        except Exception:
            verdicts = []
        if len(verdicts) == len(items):
            for i, vd in zip(items, verdicts):
                i["sim"] = vd
                i["match"] = True if vd == "same" else (False if vd == "no" else None)
            rank = {"same": 0, "similar": 1, "no": 2}
            items.sort(key=lambda i: rank.get(i.get("sim"), 1))
    return {"ok": True, "items": items, "count": len(items),
            "keyword": keyword, "product": product}


@app.post("/api/lens/cn/keywords")
async def api_lens_cn_keywords(request: Request, frame: UploadFile = File(None),
                                source_caption: str = Form("")):
    """프레임(+캡션) → 중국어 후보 검색어 리스트. Gemini 비전 1회, Apify 안 부름.
    프론트가 렌즈 열 때 호출해 후보 버튼을 그린다(2026-07-19)."""
    if frame is None and not (source_caption or "").strip():
        return {"ok": True, "product": "", "candidates": []}
    raw = None
    if frame is not None:
        try:
            raw = await frame.read()
        except Exception:
            raw = None
    try:
        v = cn_search_candidates(raw, source_caption)
    except Exception:
        v = {}
    return {"ok": True, "product": v.get("product", ""),
            "candidates": v.get("candidates", [])}


@app.post("/api/lens/cn/search")
async def api_lens_cn_search(request: Request, keyword: str = Form(""),
                              max_results: int = Form(8)):
    """중국어 검색어 1개 → 샤오홍슈+도우인 병렬 검색. Gemini 안 부름(후보는 사람이 고름).
    프론트가 후보 버튼 클릭 시 호출한다(2026-07-19)."""
    kw = (keyword or "").strip()
    if not kw:
        return {"ok": True, "items": [], "count": 0, "keyword": ""}
    if not APIFY_TOKENS:
        return {"ok": True, "items": [], "count": 0, "keyword": kw, "note": "APIFY 토큰 없음"}
    n = max(1, min(int(max_results or 8), 60))

    def _run(platform, mod):
        try:
            rows = mod.search(kw, max_results=n)
        except Exception:
            return []
        for r in rows:
            r["platform"] = platform
            r["match"] = None
        return rows

    with ThreadPoolExecutor(max_workers=2) as ex:
        fx = ex.submit(_run, "xiaohongshu", xiaohongshu_search)
        fd = ex.submit(_run, "douyin", douyin_search)
        items = fx.result() + fd.result()
    return {"ok": True, "items": items, "count": len(items), "keyword": kw}


@app.post("/api/lens/yt")
async def api_lens_yt(request: Request, frame: UploadFile = File(None),
                       source_caption: str = Form(""), max_results: int = Form(40)):
    """프레임+캡션으로 유튜브를 키워드 검색해 렌즈 결과에 합류할 항목. YouTube Data API라
    무료(쿼터 내) → 월 호출가드 없음. 검색어는 cn_search_keyword_vision의 product
    (프롬프트가 '한국어 제품명'을 명시) → 캡션 앞토큰(_cn_keyword) 폴백."""
    keyword = ""
    if frame is not None:
        try:
            raw = await frame.read()
            v = cn_search_keyword_vision(raw, source_caption)
            keyword = (v.get("product") or "").strip()
        except Exception:
            keyword = ""
    if not keyword:
        keyword = _cn_keyword(source_caption)
    if not keyword:
        return {"ok": True, "items": [], "count": 0, "note": "검색어를 만들지 못했습니다"}
    n = max(1, min(int(max_results or 40), 60))
    try:
        rows = youtube_search.search(keyword, max_results=n)
    except Exception:
        rows = []
    for r in rows:
        r["platform"] = "youtube"
        r["match"] = None
    return {"ok": True, "items": rows, "count": len(rows), "keyword": keyword}


@app.get("/healthz")
def api_healthz():
    return {"ok": True}


# ── 로그인 게이트 (멀티테넌시, 2026-07-13 — 고객별 계정) ──
# 기존 단일 관리자 계정(DASH_USER/DASH_PASS)은 그대로 유지하고 LEGACY_CUSTOMER_ID(0)로
# 로그인되게 하위호환(기존 작업물 보존). 신규 고객은 customers 테이블(회원가입) 계정.
DASH_USER = os.environ.get("DASH_USER", "admin")
DASH_PASS = os.environ.get("DASH_PASS", "")  # 비어있으면 인증 OFF(로컬 개발)
def _load_dash_secret() -> str:
    """세션쿠키 HMAC 서명키. env가 최우선, 없으면 data/ 밑에 랜덤 생성해 영속화.

    ★소스에 기본값을 박지 않는다. 예전엔 "shopping-shorts-local-secret"이 기본값이라
    운영에서 DASH_PASS만 넣고 DASH_SECRET env 한 줄을 빠뜨리면, 소스에 공개된 그 값으로
    누구나 `customer_id:expiry:sig` 쿠키를 위조해 관리자(cid=0) 포함 임의 고객을 사칭할 수
    있었다. _AUTH_ON은 DASH_PASS 유무만 보므로 시크릿 누락을 감지조차 못한다.
    기본값을 없애면 그 실수 자체가 성립하지 않는다.
    """
    env = os.environ.get("DASH_SECRET", "").strip()
    if env:
        return env
    path = Path(DB_PATH).parent / ".session_secret"
    try:
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    except OSError:
        pass
    generated = secrets.token_hex(32)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(generated, encoding="utf-8")
        os.chmod(path, 0o600)
    except OSError:
        pass  # 영속화 실패해도 이번 프로세스는 랜덤키로 뜬다(재기동 시 재로그인될 뿐).
    return generated


DASH_SECRET = _load_dash_secret()
_AUTH_ON = bool(DASH_PASS)
_AUTH_ALLOW = ("/login", "/api/login", "/signup", "/api/signup", "/favicon.ico", "/healthz",
               "/insta_fill_comment.user.js",
               # 유저스크립트(insta_fill_comment)가 인스타 탭에서 전송 감지 시 GM_xmlhttpRequest로
               # 완료기록을 POST한다. 인증쿠키 없이 오므로 허용. 마킹은 저위험(되돌리기 가능).
               "/api/comment/done",
               # 원클릭 담기: /grab(북마클릿 설치안내)는 공개, /api/grab(팝업)은 자체적으로
               # 세션쿠키를 검증해 고객을 식별한다(_cid 폴백이 legacy라 여기선 직접 검증). 미들웨어
               # 401을 피해 친절한 팝업 응답을 주려고 allowlist에 둔다.
               "/grab", "/api/grab", "/grab.user.js", "/grab_logic.js")
_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30일


def _sign_session(customer_id: int, expiry: int) -> str:
    payload = f"{customer_id}:{expiry}"
    sig = hmac.new(DASH_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def _verify_session(cookie: str):
    """쿠키 문자열 → customer_id(int) 또는 None(위조·만료·형식오류)."""
    if not cookie:
        return None
    try:
        cid_s, exp_s, sig = cookie.split(":")
        expiry = int(exp_s)
    except ValueError:
        return None
    if datetime.now(timezone.utc).timestamp() > expiry:
        return None
    expected = hmac.new(DASH_SECRET.encode(), f"{cid_s}:{exp_s}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        return int(cid_s)
    except ValueError:
        return None


def _set_session_cookie(response, customer_id: int):
    expiry = int(datetime.now(timezone.utc).timestamp()) + _COOKIE_MAX_AGE
    response.set_cookie("dash_auth", _sign_session(customer_id, expiry),
                         max_age=_COOKIE_MAX_AGE, httponly=True, samesite="lax")


_LOGIN_HTML = """<!doctype html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>쇼핑쇼츠 로그인</title>
<style>body{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
background:#0b0b0e;font-family:system-ui,'Noto Sans KR',sans-serif}
.box{background:#16161c;border:1px solid #2a2a30;border-radius:14px;padding:32px 28px;width:280px}
h1{color:#4f9dfa;font-size:18px;margin:0 0 18px;text-align:center;letter-spacing:1px}
input{width:100%;box-sizing:border-box;margin:6px 0;padding:11px 12px;background:#0e0e12;
border:1px solid #333;border-radius:8px;color:#eee;font-size:14px}
button{width:100%;margin-top:12px;padding:11px;background:#4f9dfa;color:#111;border:0;
border-radius:8px;font-weight:700;font-size:14px;cursor:pointer}
a{color:#7db4ff;font-size:12px;text-decoration:none}
.err{color:#e74c3c;font-size:12px;text-align:center;margin-top:10px;min-height:14px}
.foot{text-align:center;margin-top:14px}</style></head>
<body><form class=box method=post action=/api/login>
<h1>🛍️ 쇼핑쇼츠</h1>
<input name=user placeholder=아이디 autocomplete=username autofocus>
<input name=pass type=password placeholder=비밀번호 autocomplete=current-password>
<button>로그인</button>
<div class=err>__ERR__</div>
<div class=foot><a href=/signup>계정이 없으신가요? 가입하기</a></div>
</form></body></html>"""

_SIGNUP_HTML = """<!doctype html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>쇼핑쇼츠 가입</title>
<style>body{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
background:#0b0b0e;font-family:system-ui,'Noto Sans KR',sans-serif}
.box{background:#16161c;border:1px solid #2a2a30;border-radius:14px;padding:32px 28px;width:280px}
h1{color:#4f9dfa;font-size:18px;margin:0 0 18px;text-align:center;letter-spacing:1px}
input{width:100%;box-sizing:border-box;margin:6px 0;padding:11px 12px;background:#0e0e12;
border:1px solid #333;border-radius:8px;color:#eee;font-size:14px}
button{width:100%;margin-top:12px;padding:11px;background:#4f9dfa;color:#111;border:0;
border-radius:8px;font-weight:700;font-size:14px;cursor:pointer}
a{color:#7db4ff;font-size:12px;text-decoration:none}
.err{color:#e74c3c;font-size:12px;text-align:center;margin-top:10px;min-height:14px}
.foot{text-align:center;margin-top:14px}</style></head>
<body><form class=box method=post action=/api/signup>
<h1>🛍️ 쇼핑쇼츠 가입</h1>
<input name=user placeholder=아이디(영문/숫자) autocomplete=username autofocus>
<input name=pass type=password placeholder=비밀번호 autocomplete=new-password>
<button>가입하기</button>
<div class=err>__ERR__</div>
<div class=foot><a href=/login>이미 계정이 있으신가요? 로그인</a></div>
</form></body></html>"""


@app.get("/login", response_class=HTMLResponse)
def _login_page(e: str = ""):
    return _LOGIN_HTML.replace("__ERR__", "아이디 또는 비밀번호가 틀렸습니다" if e else "")


@app.get("/signup", response_class=HTMLResponse)
def _signup_page(e: str = ""):
    return _SIGNUP_HTML.replace("__ERR__", e or "")


@app.post("/api/login")
async def _api_login(req: Request):
    body = (await req.body()).decode("utf-8", "ignore")
    form = urllib.parse.parse_qs(body)
    u = (form.get("user") or [""])[0]
    p = (form.get("pass") or [""])[0]
    if not _AUTH_ON:
        return RedirectResponse("/", status_code=303)
    # 기존 단일 관리자 계정(env) — 하위호환, LEGACY_CUSTOMER_ID(0)로 로그인.
    if hmac.compare_digest(u, DASH_USER) and hmac.compare_digest(p, DASH_PASS):
        r = RedirectResponse("/", status_code=303)
        _set_session_cookie(r, 0)
        return r
    # 신규 고객 계정(DB).
    customer_id = Store(DB_PATH).verify_customer(u, p)
    if customer_id is not None:
        r = RedirectResponse("/", status_code=303)
        _set_session_cookie(r, customer_id)
        return r
    return RedirectResponse("/login?e=1", status_code=303)


@app.post("/api/signup")
async def _api_signup(req: Request):
    body = (await req.body()).decode("utf-8", "ignore")
    form = urllib.parse.parse_qs(body)
    u = (form.get("user") or [""])[0].strip()
    p = (form.get("pass") or [""])[0]
    if len(u) < 3 or len(p) < 4:
        return RedirectResponse("/signup?e=" + urllib.parse.quote("아이디 3자·비밀번호 4자 이상"), status_code=303)
    try:
        customer_id = Store(DB_PATH).create_customer(u, p)
    except ValueError:
        return RedirectResponse("/signup?e=" + urllib.parse.quote("이미 존재하는 아이디입니다"), status_code=303)
    r = RedirectResponse("/", status_code=303)
    _set_session_cookie(r, customer_id)
    return r


@app.middleware("http")
async def _auth_guard(request: Request, call_next):
    if not _AUTH_ON:
        request.state.customer_id = 0
        return await call_next(request)
    path = request.url.path
    # /api/find/frame/*는 Google Lens·SerpApi 등 외부 이미지검색 크롤러가 인증
    # 쿠키 없이 fetch해야 해서 예외 처리(2026-07-09, SerpApi 연동 시도 중
    # 401로 전부 막혀있던 것을 발견 — 경로 자체는 path traversal 방어된
    # 랜덤 work_id 해시라 노출 위험 낮음).
    # ⚠️ /api/voice-tune/*는 인증 예외로 두지 말 것. "운영자 전용 로컬 도구"라는 전제로
    # allowlist에 있었으나 이 앱은 shoppingshorts.duckdns.org로 공개 서비스 중이라,
    # 외부인이 /synth를 반복 호출해 ElevenLabs·GROQ 크레딧을 태우고 /profile/{임의id}로
    # voice_presets에 임의 행을 넣을 수 있었다(2026-07-15 리뷰 S7). 운영자는 대시보드
    # 로그인 세션으로 접근한다.
    if path in _AUTH_ALLOW or path.startswith("/static") or path.startswith("/api/find/frame/"):
        return await call_next(request)
    customer_id = _verify_session(request.cookies.get("dash_auth"))
    if customer_id is not None:
        request.state.customer_id = customer_id
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return RedirectResponse("/login")


@app.get("/insta_fill_comment.user.js", include_in_schema=False)
def _serve_userscript():
    """댓글 자동채우기 유저스크립트 — Tampermonkey가 이 URL로 설치·자동업데이트한다.
    (인증 없이 접근 가능하도록 _AUTH_ALLOW에 등록됨)"""
    p = Path(__file__).parent / "userscript" / "insta_fill_comment.user.js"
    return FileResponse(p, media_type="text/javascript; charset=utf-8")


@app.get("/grab.user.js", include_in_schema=False)
def _serve_grab_userscript():
    """원클릭 담기 유저스크립트 — Tampermonkey가 이 URL로 설치·자동업데이트.
    드래그 없이 플랫폼 영상 페이지에 '📥 담기' 버튼을 띄운다."""
    p = Path(__file__).parent / "userscript" / "grab.user.js"
    return FileResponse(p, media_type="text/javascript; charset=utf-8")


@app.get("/grab_logic.js", include_in_schema=False)
def _serve_grab_logic():
    """원클릭 담기 '로직' — grab.user.js(로더)가 GM_xmlhttpRequest로 매번 불러와 실행한다.
    이 파일을 고치면 모든 사용자가 다음 새로고침에 자동 반영(재설치 불필요)."""
    p = Path(__file__).parent / "userscript" / "grab_logic.js"
    return FileResponse(p, media_type="text/javascript; charset=utf-8",
                        headers={"Cache-Control": "public, max-age=60"})


# ── 원클릭 담기: 네이티브 플랫폼(유튜브·틱톡·샤오홍슈·도우인) 영상 → 모음집 즉시 담기 ──
# (2026-07-18) 렌즈 Apify 검색은 유료·개수제한, 네이티브 검색은 무료·무제한이지만 담을 때
# 번거롭다는 제보. 해결=플랫폼 영상 페이지에서 북마클릿(무설치) 또는 유저스크립트(카드버튼)로
# 한 번 눌러 URL·썸네일·제목을 우리 서버로 보내 담는다. 다운로드는 제작소에서 yt-dlp(무료).
_GRAB_DOMAINS = [
    ("youtube", ("youtube.com", "youtu.be")),
    ("tiktok", ("tiktok.com",)),
    ("instagram", ("instagram.com",)),
    ("xiaohongshu", ("xiaohongshu.com", "xhslink.com", "rednote.com")),
    ("douyin", ("douyin.com", "iesdouyin.com")),
]


def _grab_platform(url):
    host = (urllib.parse.urlparse(url or "").hostname or "").lower()
    for name, doms in _GRAB_DOMAINS:
        if any(host == d or host.endswith("." + d) for d in doms):
            return name
    return ""


def _grab_popup_html(ok, msg, sub=""):
    """팝업창에 뜨는 결과 화면 — 성공 시 잠깐 뒤 자동으로 닫힌다."""
    icon = "✅" if ok else "⚠️"
    color = "#1f9d55" if ok else "#e0623d"
    delay = 1200 if ok else 3000
    return HTMLResponse(f"""<!doctype html><meta charset="utf-8"><title>담기</title>
<body style="margin:0;font-family:system-ui,sans-serif;background:#111;color:#eee;text-align:center;padding:28px 16px">
<div style="font-size:44px">{icon}</div>
<div style="font-size:17px;margin-top:6px;color:{color};font-weight:700">{msg}</div>
<div style="font-size:13px;color:#999;margin-top:8px">{sub}</div>
<script>setTimeout(function(){{window.close();}}, {delay});</script></body>""")


def _enrich_grab(url, sc, cid):
    """백그라운드: yt-dlp/oEmbed로 썸네일·제목·조회수·좋아요·댓글·길이·채널을 보강해 저장.
    틱톡 썸네일 빔·정보 없음 제보 대응(2026-07-18). 실패해도 담긴 항목엔 지장 없음."""
    meta = probe_grab_meta(url)
    if not meta:
        return
    Store(DB_PATH).mix_basket_set_meta(
        sc, customer_id=cid,
        thumbnail=meta.get("thumbnail"), name=meta.get("title"),
        meta={k: meta[k] for k in
              ("views", "likes", "comments", "shares", "duration", "channel", "followers", "ts")
              if k in meta})


@app.get("/api/grab", include_in_schema=False)
def api_grab(request: Request, background_tasks: BackgroundTasks,
             url: str = "", thumbnail: str = "", title: str = ""):
    """북마클릿/유저스크립트가 여는 팝업 대상. 세션쿠키로 고객을 직접 식별(_AUTH_ALLOW라
    미들웨어가 customer_id를 안 채우므로 여기서 검증). 영상 즐겨찾기(mix_basket)에 멱등 추가하고
    백그라운드로 메타(썸네일·조회수 등)를 보강한다(팝업은 즉시 반환)."""
    cid = _verify_session(request.cookies.get("dash_auth")) if _AUTH_ON else 0
    if cid is None:
        return _grab_popup_html(False, "로그인이 필요해요",
                                "shoppingshorts.duckdns.org에 먼저 로그인하세요")
    platform = _grab_platform(url)
    if not platform:
        return _grab_popup_html(False, "담을 수 없는 링크예요", "유튜브·틱톡·샤오홍슈·도우인 영상 페이지에서 눌러주세요")
    sc = "grab_" + platform + "_" + hashlib.sha1(url.encode("utf-8", "ignore")).hexdigest()[:12]
    added = Store(DB_PATH).mix_basket_add(
        sc, url=url, thumbnail=thumbnail or "", name=(title or "")[:120],
        caption=(title or "")[:200], customer_id=cid)
    background_tasks.add_task(_enrich_grab, url, sc, cid)   # 썸네일·조회수 등 보강
    return _grab_popup_html(True, "영상 즐겨찾기에 담겼어요!" if added else "이미 담겨 있어요",
                            f"{platform} · 왼쪽 ⭐영상 즐겨찾기에서 확인")


# 북마클릿 본문(플랫폼 페이지에서 실행) — 따옴표 충돌을 피해 base64로 실어 페이지에서 atob.
# ★설치페이지(우리 도메인)에서 '클릭'하면 자기 URL을 담으려다 실패해 헷갈린다 → 우리 도메인
# 에서 실행되면 담지 말고 '드래그하세요' 안내만 띄운다(사장님 첫 사용 혼동, 2026-07-18).
_GRAB_BOOKMARKLET = r'''javascript:(function(){var h=location.host||"";if(/shoppingshorts|localhost|127\.0\.0\.1/.test(h)){alert("❗ 이 버튼은 '눌러서' 쓰는 게 아니라, 마우스로 북마크바에 끌어다(드래그) 저장하는 거예요.\n\n저장한 뒤, 유튜브·틱톡·샤오홍슈·도우인에서 영상을 열고 그 북마크를 누르세요.");return;}var q=function(s){var e=document.querySelector(s);return e?e.content:"";};var th=q('meta[property="og:image"]');var ti=q('meta[property="og:title"]')||document.title||"";window.open("__BASE__/api/grab?url="+encodeURIComponent(location.href)+"&thumbnail="+encodeURIComponent(th)+"&title="+encodeURIComponent(ti.slice(0,120)),"ss_grab","width=380,height=220");})();'''


@app.get("/grab", include_in_schema=False)
def grab_setup(request: Request):
    """원클릭 담기 설치 안내(공개). '📥 담기' 버튼을 북마크바로 드래그하면 끝(확장 설치 불필요)."""
    base = (PUBLIC_BASE_URL or "").rstrip("/")
    bm64 = base64.b64encode(_GRAB_BOOKMARKLET.replace("__BASE__", base).encode()).decode()
    return HTMLResponse(f"""<!doctype html><meta charset="utf-8"><title>원클릭 담기 설치</title>
<body style="font-family:system-ui,sans-serif;max-width:640px;margin:36px auto;padding:0 18px;line-height:1.7;color:#222">
<h2>📥 원클릭 담기</h2>
<p>네이티브 검색(무료·무제한)으로 보다가, 마음에 드는 영상을 <b>클릭 한 번</b>으로 모음집에 담는 기능입니다. 두 가지 방법 중 편한 걸 고르세요.</p>

<div style="background:#eafaf0;border:2px solid #1f9d55;border-radius:12px;padding:18px;margin:16px 0">
  <div style="font-weight:800;color:#1f7a44;font-size:16px;margin-bottom:6px">✅ 방법 1 (추천·제일 쉬움) — 버튼이 영상 위에 저절로 떠요</div>
  <div style="font-size:14px;color:#555;margin-bottom:10px">Tampermonkey에 설치하면, 유튜브·틱톡·샤오홍슈·도우인 영상을 볼 때 오른쪽 아래에 <b>📥 담기</b> 버튼이 자동으로 떠요. 드래그도, 북마크도 필요 없이 <b>그 버튼만 누르면 끝</b>입니다.</div>
  <ol style="margin:0 0 6px 18px;color:#444;font-size:14px">
    <li>크롬에 <b>Tampermonkey</b> 확장이 없으면 먼저 설치(웹스토어에서 "Tampermonkey").</li>
    <li>아래 링크를 누르면 Tampermonkey 설치창이 떠요 → <b>설치</b> 클릭.<br>
        <a href="/grab.user.js" style="display:inline-block;margin-top:6px;padding:10px 18px;background:#1f9d55;color:#fff;border-radius:9px;text-decoration:none;font-weight:800">📥 담기 버튼 설치하기</a></li>
    <li>이제 틱톡·샤오홍슈에서 영상을 열면 오른쪽 아래 <b>📥 담기</b> 버튼을 누르기만 하면 담김.</li>
  </ol>
</div>

<details style="margin:12px 0">
<summary style="cursor:pointer;color:#666;font-weight:700">방법 2 — 설치 없이 북마클릿으로 (조금 번거로움)</summary>
<div style="background:#fff7e6;border:1px solid #f0c36d;border-radius:12px;padding:18px;margin:10px 0">
  <div style="font-weight:800;margin-bottom:4px;color:#a86">① 아래 파란 버튼을 <span style="color:#c0392b">누르지 말고</span>, 마우스로 <u>북마크바에 끌어다(드래그)</u> 놓으세요</div>
  <div style="font-size:13px;color:#888;margin-bottom:10px">북마크바가 안 보이면 <b>Ctrl+Shift+B</b>로 켜세요. 드래그 = 버튼을 마우스로 꾹 눌러 위쪽 북마크바까지 끌고 가서 놓기.</div>
  <a id="bm" draggable="true" href="#" title="이 버튼을 위쪽 북마크바로 드래그하세요"
     style="display:inline-block;padding:12px 22px;background:#1f6feb;color:#fff;border-radius:10px;text-decoration:none;font-weight:800;cursor:grab;font-size:16px">📥 담기</a>
  <span style="color:#888;font-size:13px;margin-left:8px">↖ 이걸 <b>끌어서</b> 북마크바에 놓기</span>
</div>
<div style="font-weight:700">② 유튜브·틱톡·샤오홍슈·도우인에서 <u>영상을 열고</u>(검색결과 그리드 말고 영상 클릭해 들어간 뒤), 방금 만든 북마크를 누르면 끝</div>
</div>
</details>
<p style="color:#666;margin-top:14px">담긴 영상은 <a href="/collection">🎬 모음집</a>에서 확인 · 실제 다운로드는 제작소에서 자동(무료).</p>
<p style="color:#999;font-size:13px">※ 검색 결과 <b>그리드</b>가 아니라 <b>영상 상세 페이지</b>에서 눌러야 그 영상이 담깁니다. · shoppingshorts에 로그인된 상태여야 해요.</p>
<script>document.getElementById("bm").setAttribute("href", atob("{bm64}"));</script>
</body>""")


# ── 영상제작 위저드(produce) ─────────────────────────────────
@app.post("/api/produce/script/mix")
def api_produce_script_mix(request: Request, body: dict):
    """1단계 대본 · 우리믹스(Feature B) — 선택한 도서관 S급 대본들 강점 조합 → 새 대본.

    body에 `sources`(인라인 대본 리스트, {shortcode?, name?, category?, full_text})가 오면
    위키 조회 없이 그대로 쓴다 — 레퍼런스랭킹에서 담은 임시 대본(위키 미등록)도 조합 가능하게.
    없으면 기존 shortcode→위키 경로(하위호환).
    """
    inline = body.get("sources") or []
    if inline:
        sources = [s for s in inline if (s.get("full_text") or "").strip()]
    else:
        shortcodes = body.get("shortcodes") or []
        if len(shortcodes) < 2:
            return JSONResponse(status_code=422, content={"ok": False, "error": "도서관 대본 2개 이상 선택"})
        wiki = {w["shortcode"]: w for w in Store(DB_PATH).wiki_list(customer_id=_cid(request))}
        sources = [wiki[sc] for sc in shortcodes if sc in wiki]
    if len(sources) < 2:
        return JSONResponse(status_code=422, content={"ok": False, "error": "선택한 대본을 찾을 수 없음"})
    drafts = script_generate.generate_mix(
        sources, target_seconds=body.get("target_seconds") or 20, n=body.get("n") or 3)
    if not drafts:
        return JSONResponse(status_code=502,
                            content={"ok": False, "error": "생성 실패(키 소진 또는 응답 오류)"})
    return {"ok": True, "drafts": drafts}


@app.post("/api/produce/picks/toggle")
def api_produce_picks_toggle(request: Request, body: dict):
    """도서관 대본을 영상제작 목록에 담기/빼기 토글. body: {shortcode}."""
    sc = (body.get("shortcode") or "").strip()
    if not sc:
        return JSONResponse(status_code=422, content={"ok": False, "error": "shortcode 필요"})
    picked = Store(DB_PATH).produce_pick_toggle(sc, customer_id=_cid(request))
    return {"ok": True, "picked": picked}


@app.get("/api/produce/picks")
def api_produce_picks(request: Request):
    """영상제작에 담긴 도서관 대본(전체 데이터). 우리믹스 탭 기본 목록."""
    store = Store(DB_PATH)
    cid = _cid(request)
    picks = store.produce_pick_shortcodes(customer_id=cid)
    items = [w for w in store.wiki_list(customer_id=cid) if w["shortcode"] in picks]
    return {"ok": True, "items": items, "shortcodes": sorted(picks)}


# ── 제작소 작업파일(2026-07-17) ──────────────────────────
# 사장님 제보: "뒤로가기 하니까 작업물이 지워진다 ... 내일 다시 들어와도 이어서."
# 작업상태(state)는 클라이언트 스키마 그대로 오간다 — 서버가 모양을 해석하지 않는다.
@app.post("/api/produce/works")
def api_produce_works_save(request: Request, body: dict):
    state = body.get("state")
    if not isinstance(state, dict):
        return JSONResponse(status_code=422, content={"ok": False, "error": "state 없음"})
    # ★body에 있는 필드만 넘긴다. 스토어는 **안 넘어온 필드를 보존**하는데(update_mix_job과
    # 같은 관례), 여기서 기본값을 채워 넣으면 그 보존이 통째로 무의미해진다 —
    # 대본만 고쳐 저장했을 때 job_id가 날아가고 step이 0으로 되감긴다(T1 리뷰 Important).
    kw = {}
    if "job_id" in body:
        kw["job_id"] = body.get("job_id") or None
    if "step" in body:
        # ★int가 아니면(bool 포함 — isinstance(True, int)는 True다) kw에 아예 넣지 않는다.
        # 예전엔 0으로 되감았는데, step="3" 같은 오타 하나로 진행 단계를 파괴했다(T2 리뷰).
        # 안 넣으면 위 job_id와 같은 "보존" 경로를 타 기존 값이 유지된다.
        step = body.get("step")
        if isinstance(step, int) and not isinstance(step, bool):
            kw["step"] = step
    wid = Store(DB_PATH).upsert_produce_work(body.get("work_id") or None, state,
                                             customer_id=_cid(request), **kw)
    if not wid:
        # 남의 work_id — get/delete와 같은 404(스토어는 예외를 안 던진다, 2026-07-17 재리뷰)
        return JSONResponse(status_code=404, content={"ok": False, "error": "작업 없음"})
    return {"ok": True, "work_id": wid}


@app.post("/api/pick_log")
def api_pick_log(request: Request, body: dict):
    # 픽로그(트랙1) — 사장님이 고른 것/버린 것을 남긴다. 부가 기능이라 stage만 필수.
    stage = body.get("stage")
    if not stage:
        return JSONResponse(status_code=422, content={"ok": False, "error": "stage 없음"})
    eid = Store(DB_PATH).log_pick_event(
        stage,
        picked=body.get("picked"),
        rejected=body.get("rejected"),
        candidates=body.get("candidates"),
        edit_diff=body.get("edit_diff"),
        job_id=body.get("job_id") or None,
        customer_id=_cid(request),
    )
    return {"ok": True, "id": eid}


@app.post("/api/auto/start")
def api_auto_start(request: Request, body: dict, background: BackgroundTasks):
    # 러너 트리거(트랙4) — auto_job 생성 후 백그라운드로 S1~S3 관통. 동시 1 job 가정.
    import uuid as _uuid
    store = Store(DB_PATH)
    job_id = _uuid.uuid4().hex[:12]
    store.create_auto_job(job_id, customer_id=_cid(request))
    stages = default_stages(DB_PATH, _MIX_WORK_DIR)
    background.add_task(run_auto_job, job_id, store, stages=stages)
    return {"ok": True, "job_id": job_id}


@app.get("/api/auto/{job_id}")
def api_auto_status(job_id: str):
    job = Store(DB_PATH).get_auto_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"ok": False, "error": "없음"})
    return job


@app.get("/api/produce/works")
def api_produce_works_list(request: Request):
    return {"ok": True, "works": Store(DB_PATH).list_produce_works(customer_id=_cid(request))}


@app.get("/api/produce/works/{work_id}")
def api_produce_works_get(request: Request, work_id: str):
    st = Store(DB_PATH)
    w = st.get_produce_work(work_id, customer_id=_cid(request))
    if not w:
        return JSONResponse(status_code=404, content={"ok": False, "error": "작업 없음"})
    # ★렌더설정(꾸미기·자막제거)의 주인은 작업파일이 아니라 **job**이다 — 작업파일에 복제하면
    # 진실의 원천이 둘이 되어 새 불일치를 만든다. 그래서 여기서 job을 읽어 같이 내려준다.
    # 이게 없으면 복원이 STATE를 빈 채로 두고, renderFinal 직전 saveHeadcopy()가 그 빈 STATE를
    # 그대로 job에 POST해 **서버의 꾸미기를 null로 덮는다**. 게다가 subtitle_removal은 job에
    # 남아 유료 VMake가 도는데 화면은 "꺼짐"이라 표시한다(최종 whole-branch 리뷰 C-2).
    # 이 라우트는 _cid로 소유자를 이미 확인했으므로 여기 얹는 게 안전하다 —
    # /api/mix/status는 인증이 없어(job_id만 알면 열림) 거기 실으면 남의 창작물이 샌다.
    settings = None
    if w["job_id"]:
        job = st.get_mix_job(w["job_id"])
        if job:
            settings = {"headcopy": job.get("headcopy"),
                        "caption_style": job.get("caption_style"),
                        "deco": job.get("deco"),
                        "subtitle_removal": job.get("subtitle_removal")}
    return {"ok": True, "state": w["state"], "job_id": w["job_id"], "step": w["step"],
            "settings": settings}


@app.post("/api/produce/works/{work_id}/delete")
def api_produce_works_delete(request: Request, work_id: str):
    if not Store(DB_PATH).delete_produce_work(work_id, customer_id=_cid(request)):
        return JSONResponse(status_code=404, content={"ok": False, "error": "작업 없음"})
    return {"ok": True}


@app.post("/api/produce/mix/start")
def api_produce_mix_start(background_tasks: BackgroundTasks, body: dict):
    """2단계 영상믹스 — 확정 대본(given_script)을 소스영상 장면에 매칭하는 job 시작.
    리뷰·렌더는 기존 /api/mix/{status,result,adjust,render,video}를 그대로 쓴다.
    body: {script, urls, target_seconds, subtitle_removal, script_structure}.
    script_structure: 도서관 초안 구조분석 dict|None(2026-07-15, /api/wiki/draft/analyze
    결과를 그대로 보관용으로 전달) — mix_jobs.structure(4번째 위치인자, template/free
    모드 플래그 문자열)와는 이름만 비슷할 뿐 전혀 다른 값이니 섞지 말 것."""
    script = (body.get("script") or "").strip()
    urls = [u for u in (body.get("urls") or []) if u]
    if not script:
        return JSONResponse(status_code=422, content={"ok": False, "error": "확정 대본이 비어 있습니다(1단계)"})
    if len(urls) < 1:
        return JSONResponse(status_code=422, content={"ok": False, "error": "소스 영상 URL이 필요합니다"})
    blocked = _ssrf_guard(*urls)      # /api/mix/start와 같은 경로로 다운로드된다
    if blocked:
        return blocked
    # 1개면 그 영상 안에서 구간 순서편집(재배치), 2개 이상이면 여러 영상을 섞는
    # 믹스 — build_edit_plan(edit_plan.py)의 세그먼트 인벤토리 매칭이 소스 개수와
    # 무관하게 동작해서 이 유효성검사만 완화하면 별도 분기 없이 그대로 지원된다(2026-07-14).
    target = int(body.get("target_seconds") or 30)
    subtitle_removal = bool(body.get("subtitle_removal", False))
    script_structure = body.get("script_structure") or None
    if not isinstance(script_structure, dict):
        script_structure = None   # 잘못된 형식은 조용히 버린다(보관 전용이라 무해)
    job_id = uuid.uuid4().hex[:12]
    Store(DB_PATH).create_mix_job(job_id, urls, target, "free",
                                  subtitle_removal=subtitle_removal, given_script=script,
                                  script_structure=script_structure)
    background_tasks.add_task(run_mix_job, job_id, DB_PATH, _MIX_WORK_DIR)
    return {"ok": True, "job_id": job_id}


@app.post("/api/produce/mix/settings")
def api_produce_mix_settings(body: dict):
    """3단계 자막제거 등 렌더 전 설정 갱신. body: {job_id, subtitle_removal}."""
    job_id = (body.get("job_id") or "").strip()
    store = Store(DB_PATH)
    if not job_id or not store.get_mix_job(job_id):
        return JSONResponse(status_code=404, content={"ok": False, "error": "job 없음"})
    fields = {}
    if "subtitle_removal" in body:
        fields["subtitle_removal"] = bool(body.get("subtitle_removal"))
    if "headcopy" in body:
        fields["headcopy"] = body.get("headcopy")  # dict or None
    if "caption_style" in body:
        fields["caption_style"] = body.get("caption_style")  # dict or None
    if "deco" in body:
        fields["deco"] = body.get("deco")  # 워터마크·추가텍스트·오버레이·BGM dict or None
    if "seo" in body:
        fields["seo"] = body.get("seo")  # 6단계 SEO 일습 dict or None
    if fields:
        store.update_mix_job(job_id, **fields)
    return {"ok": True}


@app.post("/api/produce/mix/bgm")
async def api_produce_mix_bgm(job_id: str = Form(...), file: UploadFile = File(...)):
    """BGM 오디오 업로드 → job work dir에 bgm.{ext}로 저장. deco.bgm.file로 참조·렌더 시 믹스."""
    store = Store(DB_PATH)
    if not job_id or not store.get_mix_job(job_id):
        return JSONResponse(status_code=404, content={"ok": False, "error": "job 없음"})
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".mp3", ".wav", ".m4a", ".aac", ".ogg"):
        ext = ".mp3"
    d = _MIX_WORK_DIR / job_id
    d.mkdir(parents=True, exist_ok=True)
    name = "bgm" + ext
    (d / name).write_bytes(await file.read())
    return {"ok": True, "file": name}


@app.post("/api/produce/mix/overlay")
async def api_produce_mix_overlay(job_id: str = Form(...), file: UploadFile = File(...)):
    """오버레이 이미지(PNG/JPG) 업로드 → job work dir에 overlay.{ext}로 저장. deco.overlay.file로 참조."""
    store = Store(DB_PATH)
    if not job_id or not store.get_mix_job(job_id):
        return JSONResponse(status_code=404, content={"ok": False, "error": "job 없음"})
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        ext = ".png"
    d = _MIX_WORK_DIR / job_id
    d.mkdir(parents=True, exist_ok=True)
    name = "overlay" + ext
    (d / name).write_bytes(await file.read())
    return {"ok": True, "file": name}


@app.post("/api/produce/mix/{job_id}/cutaway")
def api_produce_mix_cutaway(job_id: str, request: Request, body: dict):
    """검수판에서 비트의 컷어웨이를 설정(asset_id) 또는 제거(null). plan에 되쓴다.

    ⚠️ mix_jobs에는 customer_id 컬럼이 없다(다른 /api/produce/mix/... 라우트와 동일하게
    job 존재 여부만 본다) — 진짜 소유권 경계는 scene_assets 쪽 customer_id 격리다.
    남의 asset_id를 붙이려 하면 get_scene_asset이 못 찾아 422로 막는다."""
    store = Store(DB_PATH)
    job = store.get_mix_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"ok": False, "error": "작업 없음"})
    plan = job.get("edit_plan") or {}
    beats = plan.get("beats") or []
    try:
        bi = int(body.get("beat_idx"))
    except (TypeError, ValueError):
        return JSONResponse(status_code=422, content={"ok": False, "error": "beat_idx 필요"})
    hit = next((b for b in beats if b.get("beat_idx") == bi), None)
    if hit is None:
        return JSONResponse(status_code=422, content={"ok": False, "error": "beat_idx 범위 밖"})
    aid = body.get("asset_id")
    if aid is None:
        hit.pop("cutaway", None)
    else:
        asset = store.get_scene_asset(int(aid), customer_id=_cid(request))
        if not asset:
            return JSONResponse(status_code=422, content={"ok": False, "error": "자산 없음"})
        hit["cutaway"] = {"asset_id": int(aid), "match_type": "manual"}
    store.update_mix_job(job_id, edit_plan=plan)
    return {"ok": True}


@app.get("/api/produce/mix/poster/{job_id}")
def api_produce_mix_poster(job_id: str):
    """미리보기 실장면 배경용 — 매칭된 첫 소스 영상의 한 프레임을 9:16으로 잘라 JPG 서빙(캐시)."""
    import subprocess
    store = Store(DB_PATH)
    job = store.get_mix_job(job_id)
    if not job or not job.get("edit_plan"):
        return JSONResponse(status_code=404, content={"ok": False, "error": "매칭 먼저"})
    work = _MIX_WORK_DIR / job_id
    poster = work / "poster.jpg"
    if not poster.exists():
        beats = (job["edit_plan"] or {}).get("beats") or []
        src, ss = None, 0.0
        if beats:
            pr = beats[0].get("primary") or {}
            vid = pr.get("video_id")
            ss = float(pr.get("start") or 0)
            if vid:
                src = next((work / vid).glob("*.mp4"), None)
        if src is None:  # 폴백: 이미 렌더된 결과물
            src = next(work.glob("final.mp4"), None) or next(work.glob("mix_raw.mp4"), None)
        if src is None:
            return JSONResponse(status_code=404, content={"ok": False, "error": "소스 영상 없음"})
        subprocess.run(["ffmpeg", "-y", "-ss", str(ss), "-i", str(src),
                        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                        "-frames:v", "1", str(poster)], capture_output=True)
    if not poster.exists():
        return JSONResponse(status_code=404, content={"ok": False})
    return FileResponse(str(poster), media_type="image/jpeg")


def _extract_beat_frame(work, beat, out_path):
    """beat.primary 클립의 start 시각 프레임 1장을 9:16(1080x1920)로 out_path에 저장.
    소스 영상이 없으면 False(파일 안 만듦). 프로덕션 poster 로직을 비트 단위로 일반화."""
    import subprocess
    pr = beat.get("primary") or {}
    vid = pr.get("video_id")
    ss = float(pr.get("start") or 0)
    src = None
    if vid:
        src = next((work / vid).glob("*.mp4"), None)
    if src is None:
        src = next(work.glob("final.mp4"), None) or next(work.glob("mix_raw.mp4"), None)
    if src is None:
        return False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(ss), "-i", str(src),
         "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
         "-frames:v", "1", str(out_path)],
        capture_output=True, stdin=subprocess.DEVNULL)
    return out_path.exists()


@app.get("/api/produce/mix/beats_preview/{job_id}")
def api_produce_mix_beats_preview(job_id: str):
    """꾸미기 프리뷰용 — 비트별 자막(narration)과 개수. 프레임은 beatframe 라우트가 따로 서빙.
    매칭(edit_plan) 전이면 빈 목록."""
    job = Store(DB_PATH).get_mix_job(job_id)
    beats = ((job or {}).get("edit_plan") or {}).get("beats") or []
    total = len(beats)
    # ★자막 미리보기가 실제 영상과 어긋나던 것 수정(2026-07-18 사장님 실측): 예전엔 narration
    # 문장 전체를 caption으로 줘서 미리보기가 통째로 떴는데, 실제 영상은 _caption_segments로
    # 2~3어절씩 쪼갠다. 그래서 "미리보기는 안 끊기는데 실제론 끊긴다"였다. 이제 실제 렌더와
    # 같은 구절 분할(segs)과, 있으면 실제 표시시간(cap_durs)을 함께 내려 미리보기가 순차 재생한다.
    out = []
    for idx, b in enumerate(beats):
        narr = b.get("narration", "")
        out.append({
            "i": idx, "total": total,
            "caption": narr,                                        # 폴백·호환용(통째)
            "segs": video_assemble._caption_segments(narr),         # 실제 렌더와 같은 구절 분할
            "durs": b.get("cap_durs"),                              # 구절별 실제 표시시간(없으면 None)
        })
    return {"beats": out}


@app.get("/api/produce/mix/beatframe/{job_id}/{i}")
def api_produce_mix_beatframe(job_id: str, i: int):
    """i번째 비트의 영상 프레임 1장(캐시). 없으면 404 → 프론트는 흰 배경 폴백."""
    job = Store(DB_PATH).get_mix_job(job_id)
    beats = ((job or {}).get("edit_plan") or {}).get("beats") or []
    if i < 0 or i >= len(beats):
        return JSONResponse(status_code=404, content={"ok": False})
    work = _MIX_WORK_DIR / job_id
    out = work / "beatframes" / f"{i}.jpg"
    if not out.exists():
        _extract_beat_frame(work, beats[i], out)
    if not out.exists():
        return JSONResponse(status_code=404, content={"ok": False})
    return FileResponse(str(out), media_type="image/jpeg")


# ── 장면 라이브러리(재사용 짤 뱅크, 2026-07-15) ──
# 저장은 2스텝: prepare(구간컷+Gemini 태그초안) → 사람 확인 → commit(DB 확정).
# 재추출이 없고, 확인 없이 저장되지 않는다.
_SCENE_TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")
# clip은 여기서 뺐다 — clip은 save/prepare→save/commit 경로로만 들어오고 거기서
# make_clip이 규격(720x1280/30fps/libx264/aac)을 강제한다. 업로드로 임의 mp4가 들어오면
# 규격 정규화를 안 거쳐 페이즈2 concat -c copy 렌더가 깨진다(리뷰 Important I-2).
_SCENE_EXT = {"overlay": (".png", ".jpg", ".jpeg", ".webp", ".gif"),
              "sfx": (".mp3", ".wav", ".m4a", ".aac")}
_SCENE_MIME = {".mp4": "video/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav",
               ".m4a": "audio/mp4", ".aac": "audio/aac", ".png": "image/png",
               ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
               ".gif": "image/gif"}
# 업로드 크기 상한 — await file.read() 통짜 읽기는 무제한 RAM 적재라 라이브 박스 OOM
# 위험(리뷰 Important I-1). sfx·overlay 용도면 20MB면 충분.
_SCENE_UPLOAD_MAX = 20 * 1024 * 1024


def _scene_token_path(token, ext=".mp4"):
    """토큰 → 서버가 재구성한 자산 경로. 클라이언트 문자열을 경로로 쓰지 않기 위한 관문.
    토큰이 32자 hex가 아니면 None(호출부가 422)."""
    if not token or not _SCENE_TOKEN_RE.match(str(token)):
        return None
    return _SCENE_ASSETS_DIR / f"{token}{ext}"


def _validate_render_mode(asset_type, render_mode):
    """render_mode 화이트리스트 검증 — commit·update 공용 헬퍼(리뷰 Important I-1: 이 규칙이
    commit에만 있고 update엔 없어 sfx에 render_mode='banana'가 그대로 저장되는 뒷문이 있었다).
    clip이면 replace/cutaway/None만, clip이 아니면 None만 허용(스펙 §4 — sfx/overlay는
    render_mode가 없다). 문제 없으면 None, 있으면 에러메시지."""
    if asset_type == "clip":
        if render_mode not in ("replace", "cutaway", None):
            return "render_mode는 replace/cutaway만"
    elif render_mode is not None:
        return "render_mode는 clip에만 허용됨"
    return None


def _validate_keep_original_audio(koa):
    """keep_original_audio 정규화 — commit·update 공용 헬퍼. DB의 int(0/1) 컬럼이라
    검증 없이 넘기면 int("yes")가 ValueError→500이 난다(리뷰 실증). 불리언/0/1/None만 허용.
    반환: (정규화된 int, 에러메시지|None)."""
    if koa is None:
        return 0, None
    if isinstance(koa, bool):
        return int(koa), None
    if koa in (0, 1):
        return int(koa), None
    return None, "keep_original_audio는 0/1/불리언만"


# SQLite INTEGER 상한 — 부호있는 64비트. 이보다 큰 값은 파이썬 int()는 받아줘도
# sqlite3 바인딩에서 OverflowError가 난다.
_SQLITE_INT_MAX = 2 ** 63 - 1


def _normalize_source_start_frame(raw):
    """source_start_frame 정규화 — commit 전용. 편집 편의용 부가 메타라 없어도 안전하다
    (설계 의도) — 그래서 -5·12.5·"abc" 같은 쓰레기 값은 거부하지 않고 조용히 None으로
    흘린다(손해가 대칭이라 저장을 막는 게 더 나쁘다). 문제는 10**19처럼 SQLite INTEGER
    상한을 넘는 값 — str().isdigit()도 int()도 통과해 store.py의 INSERT에서
    OverflowError→500이 났다(리뷰 I-1, 실증됨). 상한 밖이면 다른 쓰레기 값과 같은
    대접(None)을 받는 게 이 픽스다 — 별도로 거부하지 않는다."""
    s = str(raw if raw is not None else "").strip()
    if not s.isdigit():
        return None
    n = int(s)
    return n if n <= _SQLITE_INT_MAX else None


def _reject_ssrf(url):
    """내부망·클라우드 메타데이터(169.254.169.254 등, 이 서버는 AWS Lightsail) 접근 차단.
    문제 없으면 None, 문제 있으면 에러 메시지 문자열.
    호스트 allowlist는 안 쓴다 — 레퍼런스 원본 URL의 호스트가 인스타/틱톡/유튜브 CDN 등
    다양하고 자주 바뀌어 allowlist는 정상 기능을 깨뜨린다(리뷰 Important I-4).
    ⚠️ 1차 방어일 뿐이다 — TOCTOU·리다이렉트 추적까지 막지는 못한다. 완전 차단은 별도 트랙."""
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return "URL 파싱 실패"
    if parsed.scheme not in ("http", "https"):
        return "http/https URL만 허용"
    host = parsed.hostname
    if not host:
        return "호스트 없음"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # 호스트가 IP 리터럴이 아니라 도메인이면 실제 접속에 쓰일 IP로 해석해서 검사
        # (DNS가 사설 IP를 가리키는 rebinding에 대한 1차 방어).
        try:
            ip = ipaddress.ip_address(socket.gethostbyname(host))
        except (socket.gaierror, ValueError):
            return "호스트 해석 실패"
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
        return "내부망/예약 IP는 접근할 수 없음"
    return None


def _scene_wiki_source(body: dict):
    """도서관 영구보관 릴스를 장면 소스로 쓸 때의 **로컬 경로**. (경로, 에러응답) 반환.

    왜 URL이 아니라 로컬 경로인가: 서버가 자기 자신을 HTTP로 다시 부르면 SSRF
    방어(루프백 차단)에 스스로 막힌다. 애초에 같은 디스크에 있는 파일이라
    네트워크를 탈 이유가 없다.

    왜 이 다리가 필요한가: 랭킹 다리는 구조적으로 임시다 — 인스타 CDN 주소는
    DB에 저장되지 않고(source_pool 0행) 요청 때마다 새로 받아오며 만료된다.
    도서관은 mp4를 영구보관하므로 언제든 담을 수 있다.

    경로조작은 구조적으로 불가능하다 — shortcode를 파일명에 쓰지 않고 sha1
    해시로 바꾼다(/api/wiki/video와 같은 규칙). 그래서 별도 검증이 없다.
    """
    sc = (body.get("wiki_shortcode") or "").strip()
    if not sc:
        return None, None
    f = _WIKI_MEDIA_DIR / f"{hashlib.sha1(sc.encode()).hexdigest()[:16]}.mp4"
    if not f.exists():
        return None, JSONResponse(status_code=404, content={
            "ok": False, "error": "도서관에 보관된 영상이 없다 — 먼저 도서관에 저장할 것"})
    return f, None


@app.post("/api/scene/split")
def api_scene_split(request: Request, body: dict):
    """소스 영상 → 컷 목록 + 컷별 포스터. **DB에 아무것도 안 쓴다.**

    사장님이 보고 고르는 게 A안이다(설계 §4.1) — AI가 거르지 않는다. AI의
    '짤로 쓸 만한가' 판단은 검증된 적이 없다(실측: 짜집기/촬영원본 판정 3편
    전부 '촬영원본/확신 높음' 상수 출력). 저장은 기존 prepare→commit이 한다.

    ffmpeg 지식(fps·프레임·컷 경계·포스터)은 이 라우트가 아니라 scene_cut에
    있다 — app.py는 라우팅만, ffmpeg 호출은 scene_cut/scene_assets가 진다는
    이 파일의 기존 배선(prepare가 scene_assets.make_clip/make_poster를 쓰는
    것과 동일한 이유)을 그대로 따른 것. 그래서 app.py에 subprocess import가
    추가로 필요 없다."""
    wiki_src, wiki_err = _scene_wiki_source(body)
    if wiki_err:
        return wiki_err
    src_url = (body.get("src_url") or "").strip()
    if not wiki_src:
        if not src_url:
            return JSONResponse(status_code=422,
                                content={"ok": False, "error": "src_url 또는 wiki_shortcode 필요"})
        ssrf_err = _reject_ssrf(src_url)  # SSRF 1차 방어 — 내부망·169.254.169.254 등 차단
        if ssrf_err:
            return JSONResponse(status_code=422, content={"ok": False, "error": ssrf_err})
    token = uuid.uuid4().hex
    # ★_SCENE_SPLIT_DIR를 모듈 상수로 빼면 안 된다 — 모듈 임포트 시점 값이 굳어
    # test client의 monkeypatch(_SCENE_ASSETS_DIR)를 안 따라간다. 매번 여기서 계산한다.
    split_dir = _SCENE_ASSETS_DIR / "_split"
    out_dir = split_dir / token
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory() as td:
            # 도서관 소스는 이미 디스크에 있다 — 받지 않는다. td 밖에 있으므로
            # 이 블록이 끝나며 청소돼도 원본은 안 지워진다.
            src = str(wiki_src) if wiki_src else frame_extract.download_video(src_url, td)
            fps = scene_cut.video_fps(src)
            total = scene_cut.video_frame_count(src)
            cuts = scene_cut.detect_cuts(src)
            out = []
            for i, (a, b) in enumerate(cuts):
                poster = out_dir / f"{i}.jpg"
                # 컷 대표 프레임 = 시작에서 3프레임 뒤(전환 잔상 회피)
                scene_cut.extract_poster(src, a + 3, fps, poster)
                out.append({
                    "i": i, "start_frame": a, "end_frame": b,
                    "start": round(a / fps, 3), "end": round(b / fps, 3),
                    "duration": round((b - a) / fps, 3),
                    "poster_url": f"/api/scene/split/{token}/{i}/poster",
                })
    except Exception as e:  # noqa: BLE001 — 다운로드/ffmpeg 실패는 그대로 알림
        return JSONResponse(status_code=502, content={"ok": False, "error": f"분할 실패: {e}"})
    return {"ok": True, "token": token, "fps": fps, "total_frames": total, "cuts": out}


@app.get("/api/scene/split/{token}/{i}/poster")
def api_scene_split_poster(token: str, i: int):
    """분할 미리보기 썸네일. 토큰은 hex 검증 — 경로조작 차단."""
    if not re.fullmatch(r"[0-9a-f]{32}", token or ""):
        return Response(status_code=404, content=b"")
    split_dir = _SCENE_ASSETS_DIR / "_split"  # ★여기도 함수 안에서 계산(위와 같은 이유)
    p = split_dir / token / f"{i}.jpg"
    if not p.exists():
        return Response(status_code=404, content=b"")
    return FileResponse(str(p), media_type="image/jpeg")


@app.post("/api/scene/save/prepare")
def api_scene_save_prepare(request: Request, body: dict):
    """구간컷 + Gemini 다축 태그 초안 → 모달 프리필용. 아직 DB 저장 안 함.
    body: {source_kind, source_ref, src_url|wiki_shortcode, start, end, category?, caption?, script?}"""
    wiki_src, wiki_err = _scene_wiki_source(body)
    if wiki_err:
        return wiki_err
    src_url = (body.get("src_url") or "").strip()
    if not wiki_src:
        if not src_url:
            return JSONResponse(status_code=422,
                                content={"ok": False, "error": "src_url 또는 wiki_shortcode 필요"})
        ssrf_err = _reject_ssrf(src_url)  # SSRF 1차 방어 — 내부망·169.254.169.254 등 차단
        if ssrf_err:
            return JSONResponse(status_code=422, content={"ok": False, "error": ssrf_err})
    try:
        start, end = float(body.get("start") or 0), float(body.get("end") or 0)
    except (TypeError, ValueError):
        return JSONResponse(status_code=422, content={"ok": False, "error": "start/end 숫자 필요"})
    if end - start <= 0:
        return JSONResponse(status_code=422, content={"ok": False, "error": "구간이 잘못됨"})
    token = uuid.uuid4().hex
    _SCENE_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    clip = _SCENE_ASSETS_DIR / f"{token}.mp4"
    poster = _SCENE_ASSETS_DIR / f"{token}.jpg"
    src_start_frame = None
    try:
        with tempfile.TemporaryDirectory() as td:
            # 도서관 소스는 이미 디스크에 있다(td 밖) — 받지도, 청소로 지우지도 않는다.
            src = str(wiki_src) if wiki_src else frame_extract.download_video(src_url, td)
            # ★소스의 fps로 — 클립은 -r 30으로 통일되므로 클립 fps를 쓰면 원본이
            # 30fps가 아닐 때 틀린 프레임 번호가 저장된다. 소스는 이 블록이 끝나면
            # (TemporaryDirectory 청소로) 지워지므로 fps는 반드시 블록 안에서 구한다.
            src_start_frame = round(start * scene_cut.video_fps(src))
            scene_assets.make_clip(src, start, end, clip)
    except Exception as e:  # noqa: BLE001 — 다운로드/ffmpeg 실패는 사용자에게 그대로 알림
        return JSONResponse(status_code=502, content={"ok": False, "error": f"구간컷 실패: {e}"})
    scene_assets.make_poster(clip, poster)
    draft = scene_assets.autotag([poster] if poster.exists() else [], {
        "category": body.get("category"), "caption": body.get("caption"),
        "script": body.get("script"),
    })
    return {"ok": True, "token": token, "start_frame": src_start_frame,
            "duration": scene_assets.probe_duration(clip),
            "poster_url": f"/api/scene/prepared/{token}/poster", "draft": draft}


@app.get("/api/scene/prepared/{token}/poster")
def api_scene_prepared_poster(token: str):
    """commit 전 미리보기 썸네일. 토큰은 hex 검증 — 경로조작 차단."""
    p = _scene_token_path(token, ".jpg")
    if p is None or not p.exists():
        return Response(status_code=404, content=b"")
    return FileResponse(str(p), media_type="image/jpeg")


@app.post("/api/scene/save/commit")
def api_scene_save_commit(request: Request, body: dict):
    """사람이 확인·수정한 태그로 자산 확정 저장. media_path는 **토큰으로만** 재구성 —
    body의 media_path는 있어도 무시한다(경로조작 차단)."""
    p = _scene_token_path(body.get("token"))
    if p is None:
        return JSONResponse(status_code=422, content={"ok": False, "error": "token 형식 오류"})
    if not p.exists():
        return JSONResponse(status_code=404, content={"ok": False, "error": "준비된 클립 없음"})
    title = (body.get("title") or "").strip()
    if not title:
        return JSONResponse(status_code=422, content={"ok": False, "error": "title 필요"})

    # ★'모름'과 미지정을 모두 막는다(설계 §7.2). AI 판정은 실측 탈락했고
    # (정답 아는 시험지에서 3편 전부 '촬영원본/확신 높음'), 사람만 안다. 스토어엔
    # 값 검증이 전혀 없으므로(실측: source_start_frame=-5.7도 그대로 저장됨) 여기가
    # 유일한 방어선이다 — 손해가 비대칭이다(짤 하나 잃는 것보다 남의 촬영분이 라이브에
    # 들어가는 게 훨씬 나쁘다).
    origin = (body.get("source_origin") or "").strip()
    if origin not in ("짜집기", "촬영원본"):
        return JSONResponse(status_code=422, content={
            "ok": False, "error": "출처를 골라야 저장됩니다(짜집기/촬영원본)"})

    asset_type = body.get("asset_type") or "clip"
    # 검증 없이 asset_type을 받으면 임의 문자열이 DB에 그대로 저장되고, 이게 프론트 HTML
    # 속성 컨텍스트(onclick='...')로 그대로 흘러 XSS 체인이 닫힌다(리뷰 실증) — 화이트리스트로 막는다.
    if asset_type not in ("clip", "sfx", "overlay"):
        return JSONResponse(status_code=422,
                            content={"ok": False, "error": "asset_type은 clip/sfx/overlay만"})

    # render_mode는 clip에서만 의미가 있고 값도 두 가지뿐 — 원시값을 그대로 흘리면 나중에
    # 렌더 분기에서 예기치 못한 값을 만난다. clip일 때만 화이트리스트로 막는다(422).
    # (비clip은 기존과 동일하게 검증하지 않고 아래에서 무조건 None으로 저장한다 — 이 자리에서
    # 새로 거부하면 sfx에 render_mode를 실어보내는 기존 클라이언트 호출이 깨진다.)
    render_mode = body.get("render_mode")
    if asset_type == "clip":
        # 페이즈1 리뷰 잔여 — render_mode 없이 저장되면 배지가 NULL을 '컷어웨이'로
        # 거짓 표기한다(설계 §8). clip은 반드시 골라야 한다.
        if not render_mode:
            return JSONResponse(status_code=422,
                                content={"ok": False, "error": "clip은 render_mode가 필요합니다"})
        err = _validate_render_mode(asset_type, render_mode)
        if err:
            return JSONResponse(status_code=422, content={"ok": False, "error": err})

    koa, err = _validate_keep_original_audio(body.get("keep_original_audio"))
    if err:
        return JSONResponse(status_code=422, content={"ok": False, "error": err})

    # 토큰을 여기서 단일사용으로 소비한다(리뷰 Critical C-1) — prepare가 남긴 토큰 파일을
    # 커밋 시점에 즉시 새 이름으로 rename한다. 같은 토큰으로 commit을 두 번 하면 두 번째
    # 요청은 위 `p.exists()` 체크에서 이미 원본이 없어 자연히 404가 되므로, 서로 다른 자산이
    # 같은 media_path를 공유할 구조적 여지가 없어진다. 스펙 §4의 `<id>.<ext>` 규약이 이상적이나
    # 이 시점엔 아직 id를 모르므로(add_scene_asset 이전) 새 uuid로 우선 소비한다(리뷰가 권고한 방식).
    consumed = uuid.uuid4().hex
    old_poster = p.with_suffix(".jpg")
    media = _SCENE_ASSETS_DIR / f"{consumed}{p.suffix}"
    try:
        p.rename(media)
    except OSError:
        return JSONResponse(status_code=404, content={"ok": False, "error": "준비된 클립 없음"})
    poster = _SCENE_ASSETS_DIR / f"{consumed}.jpg"
    if old_poster.exists():
        try:
            old_poster.rename(poster)
        except OSError:
            poster = None
    else:
        poster = None
    if asset_type == "sfx":
        # 스펙 §5.3 — 효과음은 업로드 말고 **화면짤에서 오디오만 뽑는** 경로도 있다.
        # 같은 구간컷을 재사용하므로 재추출이 없다.
        try:
            media = scene_assets.extract_audio(media, media.with_suffix(".mp3"))
        except RuntimeError as e:
            return JSONResponse(status_code=502,
                                content={"ok": False, "error": f"오디오 추출 실패: {e}"})
        poster = None
    aid = Store(DB_PATH).add_scene_asset({
        "asset_type": asset_type,
        "render_mode": render_mode if asset_type == "clip" else None,
        "media_path": str(media),
        "poster_path": str(poster) if (poster and poster.exists()) else None,
        "duration": scene_assets.probe_duration(media),
        "keep_original_audio": koa,
        "title": title, "scene_desc": body.get("scene_desc"), "role": body.get("role"),
        "category": body.get("category"), "subject": body.get("subject"),
        "tone": body.get("tone"), "keywords": body.get("keywords"),
        "source_kind": body.get("source_kind"), "source_ref": body.get("source_ref"),
        "source_origin": origin,
        "source_start_frame": _normalize_source_start_frame(body.get("source_start_frame")),
    }, customer_id=_cid(request))
    return {"ok": True, "id": aid}


@app.post("/api/scene/upload")
async def api_scene_upload(request: Request, asset_type: str = Form(...),
                           title: str = Form(...), file: UploadFile = File(...),
                           category: str = Form(""), role: str = Form(""),
                           subject: str = Form(""), tone: str = Form("")):
    """효과음·오버레이 직접 업로드. 확장자 화이트리스트 밖은 거부."""
    if not (title or "").strip():
        return JSONResponse(status_code=422, content={"ok": False, "error": "title 필요"})
    allowed = _SCENE_EXT.get(asset_type)
    if not allowed:
        return JSONResponse(status_code=422, content={"ok": False, "error": "asset_type 오류"})
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed:
        return JSONResponse(status_code=422,
                            content={"ok": False, "error": f"{asset_type}는 {'/'.join(allowed)}만"})
    token = uuid.uuid4().hex
    _SCENE_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    dest = _SCENE_ASSETS_DIR / f"{token}{ext}"
    # 청크 단위로 읽으며 누적 크기를 잰다 — await file.read()로 통째 읽은 뒤 len()으로
    # 재는 방식은 이미 메모리에 다 올린 뒤라 방어가 안 됨(리뷰 Important I-1, OOM 위험).
    total = 0
    too_big = False
    with open(dest, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > _SCENE_UPLOAD_MAX:
                too_big = True
                break
            f.write(chunk)
    if too_big:
        dest.unlink(missing_ok=True)
        return JSONResponse(status_code=413,
                            content={"ok": False, "error": "파일이 너무 큼(최대 20MB)"})
    poster = None
    if asset_type == "overlay":
        # `_poster` 접미사 필수 — ext가 이미 .jpg인 업로드(png/jpg/jpeg 전부 허용됨)라면
        # `{token}.jpg`는 dest와 **같은 경로**가 된다. make_poster가 그 경로에 ffmpeg를
        # 태우면 사용자 업로드 원본을 제자리에서 재인코딩·파괴한다(리뷰 Important I-3, 실증됨).
        pp = _SCENE_ASSETS_DIR / f"{token}_poster.jpg"
        poster = scene_assets.make_poster(dest, pp)
    aid = Store(DB_PATH).add_scene_asset({
        "asset_type": asset_type, "media_path": str(dest),
        "poster_path": str(poster) if poster else None,
        "duration": scene_assets.probe_duration(dest),
        "title": title.strip(), "category": category or None, "role": role or None,
        "subject": subject or None, "tone": tone or None,
        "source_kind": "upload", "source_ref": file.filename or "",
    }, customer_id=_cid(request))
    return {"ok": True, "id": aid}


@app.get("/api/scene/list")
def api_scene_list(request: Request, type: str = "", category: str = "", role: str = ""):
    """이 고객의 장면 자산 목록(필터 옵션)."""
    items = Store(DB_PATH).list_scene_assets(
        customer_id=_cid(request), asset_type=type or None,
        category=category or None, role=role or None)
    return {"ok": True, "items": items}


@app.post("/api/scene/{asset_id}/update")
def api_scene_update(request: Request, asset_id: int, body: dict):
    """다축 태그 편집. store가 화이트리스트로 media_path 등을 걸러낸다."""
    # keywords는 list가 정상(store가 콤마문자열로 정규화)이라 예외. 그 밖에 dict/list 등
    # 비-스칼라 값이 오면 sqlite에 그대로 넘어가 InterfaceError→500이 난다(리뷰 I-3, 실증됨).
    for k, v in body.items():
        if k != "keywords" and isinstance(v, (dict, list)):
            return JSONResponse(status_code=422,
                                content={"ok": False, "error": f"{k}는 스칼라 값만"})
    cid = _cid(request)
    store = Store(DB_PATH)
    body = dict(body)
    # render_mode·keep_original_audio는 commit 라우트와 같은 규칙으로 검증한다(리뷰 Important
    # I-1) — commit에만 있고 여기 없어 sfx에 render_mode='banana', keep_original_audio='yes'가
    # 그대로 저장되는 뒷문이 있었다. render_mode는 대상 자산의 asset_type이 필요해 먼저 조회한다.
    if "render_mode" in body:
        asset = store.get_scene_asset(asset_id, customer_id=cid)
        if not asset:
            return JSONResponse(status_code=404, content={"ok": False, "error": "자산 없음"})
        # commit은 clip에 render_mode를 필수로 강제한다(설계 §8, 페이즈1 리뷰 잔여) —
        # update가 같은 자산을 render_mode=None으로 되돌리면 그 불변식이 뒷문으로 풀린다
        # (리뷰 I-2, 실증됨: 200으로 통과하고 배지가 NULL을 '컷어웨이'로 거짓 표기).
        # commit과 동일하게 clip에서만 None을 거부 — sfx/overlay는 원래 render_mode가
        # 없는 게 정상(스펙 §4)이라 계속 허용해야 한다.
        if asset["asset_type"] == "clip" and not body.get("render_mode"):
            return JSONResponse(status_code=422,
                                content={"ok": False, "error": "clip은 render_mode가 필요합니다"})
        err = _validate_render_mode(asset["asset_type"], body.get("render_mode"))
        if err:
            return JSONResponse(status_code=422, content={"ok": False, "error": err})
    if "keep_original_audio" in body:
        koa, err = _validate_keep_original_audio(body.get("keep_original_audio"))
        if err:
            return JSONResponse(status_code=422, content={"ok": False, "error": err})
        body["keep_original_audio"] = koa
    ok = store.update_scene_asset(asset_id, body, customer_id=cid)
    if not ok:
        return JSONResponse(status_code=404, content={"ok": False, "error": "자산 없음"})
    return {"ok": True}


@app.post("/api/scene/{asset_id}/delete")
def api_scene_delete(request: Request, asset_id: int):
    """DB row 삭제 + 디스크 물리파일(media/poster) 정리.
    순서: (1) 지우기 전에 경로 확보(지운 뒤엔 알 수 없음) → (2) DB 삭제 →
    (3) 삭제가 내 자산이었을 때만(True) 파일 unlink. 404(남의 자산·없는 id)면
    파일에 손대지 않는다 — 소유권 확인 없이 지우면 남의 파일을 지울 위험."""
    store = Store(DB_PATH)
    asset = store.get_scene_asset(asset_id, customer_id=_cid(request))
    ok = store.delete_scene_asset(asset_id, customer_id=_cid(request))
    if not ok:
        return JSONResponse(status_code=404, content={"ok": False, "error": "자산 없음"})
    if asset:
        for path_key in ("media_path", "poster_path"):
            p = asset.get(path_key)
            if not p:
                continue
            try:
                Path(p).unlink()
            except OSError:
                # 파일이 이미 없거나 권한 문제여도 DB 삭제는 끝났으므로 요청은 성공 처리
                pass
    return {"ok": True}


@app.get("/api/scene/{asset_id}/media")
def api_scene_media(request: Request, asset_id: int):
    """자산 미디어 서빙(FileResponse가 Range를 처리해 seek 됨).
    DB로 소유권을 먼저 확인 — 남의 id를 찍어도 404."""
    a = Store(DB_PATH).get_scene_asset(asset_id, customer_id=_cid(request))
    if not a or not a.get("media_path"):
        return Response(status_code=404, content=b"")
    f = Path(a["media_path"])
    if not f.exists():
        return Response(status_code=404, content=b"")
    return FileResponse(str(f), media_type=_SCENE_MIME.get(f.suffix.lower(),
                                                           "application/octet-stream"))


@app.get("/api/scene/{asset_id}/poster")
def api_scene_poster(request: Request, asset_id: int):
    a = Store(DB_PATH).get_scene_asset(asset_id, customer_id=_cid(request))
    if not a or not a.get("poster_path") or not Path(a["poster_path"]).exists():
        return Response(status_code=404, content=b"")
    return FileResponse(a["poster_path"], media_type="image/jpeg")


# ── 자동매칭 고급효과 엔진(2026-07-17, Task5) — suggest/render/status ────────
# ⚠️ mix_jobs는 beats/dur_frames/category를 직접 안 준다(브리프 가정과 실측이 다름).
# 실제로는 job["edit_plan"]["beats"](역할·나레이션·target_seconds 계획값, 렌더 후엔
# tts_path도 채워짐)와 job["script_structure"]["product_category"]에서 뽑아 쓴다 —
# 아래 두 어댑터가 그 변환을 맡는다.
FX_RENDER_COST = 10


def _fx_timeline_from_job(job):
    """job["edit_plan"]["beats"] → effect_match.suggest용 [{s,e,text}] 리스트.

    타이밍 우선순위: 모든 비트에 tts_path가 있으면(=이미 한 번 렌더돼 TTS mp3가 work
    폴더에 있음) video_assemble._beat_timeline으로 ffprobe 실측 길이를 쓴다(실제 조립본과
    정확히 일치). 하나라도 없으면(아직 렌더 전, 또는 work 폴더 정리로 mp3가 사라진 경우)
    target_seconds(EDL 계획값) 누적으로 폴백한다 — 계획값은 실제 TTS 길이와 미세
    드리프트가 있을 수 있다(v1 수용 — 자막·모션 싱크가 아니라 효과 배치 미리보기라
    실용상 허용오차 안, Task5 보고 참고)."""
    plan = job.get("edit_plan") or {}
    beats = plan.get("beats") or []
    if not beats:
        return []
    tts_paths = {b["beat_idx"]: b["tts_path"] for b in beats if b.get("tts_path")}
    if len(tts_paths) == len(beats):
        try:
            timeline = video_assemble._beat_timeline(plan, tts_paths)
            return [{"s": t["t0"], "e": t["t0"] + t["dur"], "text": t["narration"]} for t in timeline]
        except Exception:
            pass  # ffprobe 실패 등 — 아래 target_seconds 폴백으로 이어간다
    t0 = 0.0
    out = []
    for b in beats:
        dur = float(b.get("target_seconds") or 0.0)
        out.append({"s": t0, "e": t0 + dur, "text": b.get("narration", "")})
        t0 += dur
    return out


def _fx_dur_frames(job, timeline, fps=30):
    """전체 프레임 수. video_path를 ffprobe로 실측(가장 정확) → 실패 시 타임라인
    끝값으로 폴백(video_path 없음/ffprobe 미설치 등)."""
    vp = job.get("video_path")
    if vp:
        try:
            return round(video_assemble._probe_duration(vp) * fps)
        except Exception:
            pass
    if timeline:
        return round(timeline[-1]["e"] * fps)
    return 0


@app.post("/api/produce/seo/generate")
def api_seo_generate(body: dict):
    """확정 대본으로 SEO 일습 생성 + 키워드 유튜브 실측.

    DB에 기록하지 않는다(무과금 미리보기 — fx/suggest와 같은 규약). 사장님이
    화면에서 다듬고 /mix/settings로 확정 저장한다. 생성할 때마다 덮어쓰면
    손으로 고친 걸 날린다.

    only가 있으면 부분 재생성 — 측정(100유닛/키워드)을 다시 하지 않고
    호출부가 준 keyword_stats를 프롬프트에 되먹인다.
    """
    job_id = (body.get("job_id") or "").strip()
    store = Store(DB_PATH)
    job = store.get_mix_job(job_id) if job_id else None
    if not job:
        return JSONResponse(status_code=404, content={"ok": False, "error": "job 없음"})

    only = body.get("only") or None
    locked = body.get("locked") or {}
    captions = body.get("captions") or []
    stats = body.get("keyword_stats") or []

    seo = seo_generate.generate(job, captions=captions, only=only,
                                locked=locked, keyword_stats=stats)
    if not seo:
        return JSONResponse(status_code=502, content={"ok": False, "error": "생성 실패"})

    if not only:
        # 전체 생성일 때만 측정한다 — search.list가 100유닛이고 발굴과 키풀을 나눠 쓴다.
        stats = seo_probe.probe_keywords(seo_generate.seed_keywords(seo), store)
    seo["keyword_stats"] = stats
    seo["generated_at"] = datetime.now(timezone.utc).isoformat()
    return {"seo": seo}


@app.post("/api/produce/thumb/titles")
def api_thumb_titles(body: dict):
    """확정 대본으로 썸네일에 얹을 짧은 제목 후보를 뽑는다. DB 기록 안 함(무과금 미리보기 —
    seo/generate·fx/suggest와 같은 규약). 사장님이 후보를 눌러 레이어에 얹고 다듬는다."""
    job_id = (body.get("job_id") or "").strip()
    job = Store(DB_PATH).get_mix_job(job_id) if job_id else None
    if not job:
        return JSONResponse(status_code=404, content={"ok": False, "error": "job 없음"})
    titles = thumb_title.generate(job)
    if titles is None:
        return JSONResponse(status_code=502,
                            content={"ok": False, "error": "제목 생성 실패 — 잠시 후 다시 눌러보세요"})
    return {"ok": True, "titles": titles}


@app.get("/api/produce/seo/get")
def api_seo_get(job_id: str = ""):
    """저장된 SEO 복원용(6단계 재진입·새로고침). 없으면 seo: null."""
    job = Store(DB_PATH).get_mix_job((job_id or "").strip()) or {}
    return {"seo": job.get("seo")}


@app.post("/api/produce/fx/suggest")
def api_fx_suggest(request: Request, body: dict):
    """믹스 job의 비트+카테고리로 효과 배치 플랜을 미리 만든다. DB에 기록하지
    않는다(무과금 미리보기 — 확정은 /render에서 포인트를 내고 한다).
    보유 포인트도 함께 반환한다 — 프런트가 렌더 전에 잔액을 보여줘 402를 미리 막는다."""
    store = Store(DB_PATH)
    job = store.get_mix_job(body.get("job_id") or "") or {}
    timeline = _fx_timeline_from_job(job)
    category = body.get("category") or (job.get("script_structure") or {}).get("product_category") or ""
    dur_frames = _fx_dur_frames(job, timeline)
    plan = effect_match.suggest(timeline, category, job.get("video_path", ""), dur_frames, client=None)
    return {"plan": plan, "points": points.balance(store, _cid(request)), "cost": FX_RENDER_COST}


def _fx_render_job(job_id, plan, cid):
    """백그라운드 최종 렌더. 실패하면 차감된 포인트를 환불하고 fx_status=failed로
    남긴다 — 실패했는데 포인트만 날아가면 신뢰가 깨진다."""
    store = Store(DB_PATH)
    try:
        job = store.get_mix_job(job_id) or {}
        # 고급효과는 꾸미기(4단계)에서 건다 — video_path(최종 조립본)는 맨 마지막 단계에서야
        # 채워지므로 이 시점엔 대개 None이다. 배경은 그 단계에 실제로 존재하는 것부터:
        # 최종본 > 자막제거본 > 조립 프리뷰 순.
        bg = job.get("video_path") or job.get("clean_video_path") or job.get("preview_path")
        if not bg:
            raise RuntimeError("배경 영상 없음(video_path·clean_video_path·preview_path 모두 비어있음)")
        out = str(_MIX_WORK_DIR / job_id / "fx.mp4")
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        remotion_render.render(plan, bg, out)
        store.update_mix_job(job_id, fx_status="done", fx_path=out)
    except Exception:
        # 조용한 except가 실패 원인을 통째로 삼켜 진단을 막았다 — stderr(systemd 저널)로 남긴다.
        import traceback
        traceback.print_exc()
        points.refund(store, cid, FX_RENDER_COST)
        store.update_mix_job(job_id, fx_status="failed")


@app.post("/api/produce/fx/render")
def api_fx_render(request: Request, body: dict, background_tasks: BackgroundTasks):
    """확정된 플랜으로 렌더당 정액(FX_RENDER_COST) 차감 후 백그라운드 렌더 예약.
    잔액 부족이면 402(차감 자체를 안 함 — 아무 상태도 안 건드림)."""
    job_id = body.get("job_id")
    if not job_id:
        return JSONResponse(status_code=422, content={"error": "job_id 필요"})
    cid = _cid(request)
    store = Store(DB_PATH)
    if not points.deduct(store, cid, FX_RENDER_COST):
        return JSONResponse(status_code=402, content={"error": "포인트 부족"})
    plan = body.get("plan") or {}
    store.update_mix_job(job_id, fx_status="queued", fx_plan=plan)
    background_tasks.add_task(_fx_render_job, job_id, plan, cid)
    return {"status": "queued"}


@app.get("/api/produce/fx/status/{job_id}")
def api_fx_status(job_id: str):
    job = Store(DB_PATH).get_mix_job(job_id) or {}
    out = {"fx_status": job.get("fx_status")}
    if job.get("fx_status") == "done":
        out["fx_url"] = f"/api/produce/fx/file/{job_id}"
    return out


@app.get("/api/produce/fx/file/{job_id}")
def api_fx_file(job_id: str):
    """완성된 효과영상 서빙(status가 준 fx_url이 가리키는 곳)."""
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job or not job.get("fx_path") or not Path(job["fx_path"]).exists():
        return JSONResponse(status_code=404, content={"ok": False})
    return FileResponse(job["fx_path"])


# 정적 프론트 (마운트는 맨 마지막)
_STATIC = Path(__file__).parent / "static"

# 클린 URL — /library, /mix 등 확장자(.html) 없이 접근. (index는 루트 '/'로 자동)
# 기존 /xxx.html 경로도 아래 StaticFiles 마운트로 계속 동작(백워드 호환).
# no-cache: UI 배포 후 브라우저가 옛 HTML을 캐시로 재사용해 "고쳤는데 안 바뀜"이
# 반복됨(2026-07-14 역할배정·사이드바 등 실사고) → 매 요청 서버 재검증 강제.
_NOCACHE = {"Cache-Control": "no-cache, must-revalidate"}
for _pg in ("discover", "find", "library", "mix", "outreach", "produce", "collection",
            "scene_library"):
    app.add_api_route(
        f"/{_pg}",
        (lambda n=_pg: FileResponse(_STATIC / f"{n}.html", media_type="text/html",
                                    headers=_NOCACHE)),
        include_in_schema=False,
    )

# ★C-1(2026-07-16 라이브 실증): 위 _NOCACHE는 /produce 등 "클린 URL" 라우트에만 붙는다.
# /sidebar.js 같은 정적 JS/CSS/HTML은 아래 StaticFiles 마운트가 헤더 없이 그대로 서빙해서
# 브라우저가 무기한 캐시했다 — 실측: 서버는 새 sidebar.js(mountWorks 포함, 5957바이트)를
# 주는데 performance 엔트리는 transferSize:0/cached:true, 화면엔 .ss-work가 0개.
# Ctrl+Shift+R로는 바로 떴다 = 캐시 문제, 배포 문제가 아니었다.
#
# 방식: StaticFiles 서브클래스로 file_response()를 오버라이드(미들웨어 대신 이걸 고른 이유:
# 전역 미들웨어는 /api/* JSON 응답까지 건드리게 되거나, 이 마운트 하나만 골라내려면 결국
# 경로 접두사를 다시 검사해야 해서 오히려 이 마운트 안에서 바로 처리하는 게 범위가 좁고 명확
# 하다). js/css/html에만 no-cache를 씌운다 — 폰트(otf/ttf)는 내용이 안 바뀌므로 그대로 영구
# 캐시(빠지면 사장님 화면이 매번 폰트를 다시 받는다).
#
# Starlette 1.3.1의 StaticFiles.file_response()를 그대로 재현하되 응답 생성 직후·
# is_not_modified() 판정 전에 헤더를 얹는다 — super() 뒤에 붙이면 이미 304
# NotModifiedResponse로 바뀐 뒤라 늦는다(NotModifiedResponse는 원본 응답 헤더 중
# cache-control만 골라 옮기므로, 원본에 미리 있어야 304에도 살아남는다).
_NOCACHE_STATIC_EXTS = (".js", ".css", ".html")


class _NoCacheStaticFiles(StaticFiles):
    def file_response(self, full_path, stat_result, scope, status_code=200):
        from starlette.datastructures import Headers
        from starlette.staticfiles import NotModifiedResponse

        request_headers = Headers(scope=scope)
        response = FileResponse(full_path, status_code=status_code, stat_result=stat_result)
        if str(full_path).endswith(_NOCACHE_STATIC_EXTS):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        if self.is_not_modified(response.headers, request_headers):
            return NotModifiedResponse(response.headers)
        return response


app.mount("/", _NoCacheStaticFiles(directory=str(_STATIC), html=True), name="static")
