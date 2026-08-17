"""FastAPI: 수집 API + 정적 프론트 서빙."""
import asyncio
import base64
import functools
import hmac
import hashlib
import ipaddress
import json
import os
import re
import secrets
import shutil
import socket
import tempfile
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests
from fastapi import BackgroundTasks, FastAPI, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, FileResponse, Response, StreamingResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from shopping_shorts import service
from shopping_shorts.service import collect, census, generate_missing_drafts, next_draft_targets, youtube_channel_board
from shopping_shorts.outreach import build_queue
from shopping_shorts.instagram_parse import shortcode_to_timestamp
from shopping_shorts.store import Store
from shopping_shorts import vision_tagging
from shopping_shorts.auto_run import run_auto_job, default_stages
from shopping_shorts import config
from shopping_shorts.config import DB_PATH, DRAFT_BATCH_SIZE, PUBLIC_BASE_URL
from shopping_shorts.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
from shopping_shorts.frame_extract import (download_video, extract_frames,
                                           extract_frame_at, extract_grid_frames)
from shopping_shorts.script_extract import (extract_script, extract_auto, storable,
                                            KeyPoolExhausted, has_usable_result)
from shopping_shorts.structure_analyze import analyze_structure
from shopping_shorts import backbone
from shopping_shorts.aipick import build_aipick
from shopping_shorts.categorize import categorize, KEYWORDS as CATEGORY_KEYWORDS
from shopping_shorts import script_generate
from shopping_shorts.apify_client import fetch_single_reel, fetch_reels, fetch_profiles
from shopping_shorts import discovery, instagram_search
from shopping_shorts.channels import load_channels, username_from_url, merge_tracked
from shopping_shorts import video_analysis
from shopping_shorts.video_analysis import (analyze_video, translate_keyword, cn_search_keyword,
                                            cn_search_keyword_vision, judge_same_product,
                                            cn_search_candidates, expand_search_keywords,
                                            subject_tags_vision)
from shopping_shorts.product_identify import fetch_lens_lines, identify_product_from_lines
from shopping_shorts.search_links import build_search_links, lens_search_url
from shopping_shorts import coupang_partners
from shopping_shorts import mix_pipeline
from shopping_shorts.mix_pipeline import (run_mix_job, run_render, run_preview, retype_mix_job,
                                          _source_video_id, resynth_tts_job, resynth_one_beat,
                                          run_clean_sources, _resolve_sources)
from shopping_shorts.lens_discover import search_similar_videos, upload_frame
from shopping_shorts import cn_search, kw_search, douyin_search, xiaohongshu_search
from shopping_shorts import youtube_search
from shopping_shorts.config import APIFY_TOKENS
from shopping_shorts.media_download import (resolve_media_url, download_any, probe_grab_meta,
                                            _is_direct_video, DouyinBusy)
from shopping_shorts import edit_plan as _edit_plan
from shopping_shorts import edit_plan
from shopping_shorts import voice_presets, audio_post
from shopping_shorts import pron_corrections
from shopping_shorts.tts import synthesize_tts
from shopping_shorts import tts, asr_check
from shopping_shorts import export_bundle
from shopping_shorts import qr_svg
from shopping_shorts import capcut_draft
from shopping_shorts.youtube_client import enrich_youtube
from shopping_shorts.youtube_client import channels_from_video_urls as yt_channels_from_videos
from shopping_shorts.video_assemble import _beat_timeline
from shopping_shorts.audio_post import detect_edge_silence
from shopping_shorts.video_assemble import _probe_duration, _effective_dur, _TRIM_FLOOR
from shopping_shorts.narration_naturalize import naturalize as _naturalize
from shopping_shorts import frame_extract, scene_assets, scene_cut
from shopping_shorts import effect_match, remotion_render, points
from shopping_shorts import keycrypt, keyroute, pricing      # BYOK(사용자 키·포인트). points는 위에서 이미 import
from shopping_shorts import video_assemble
from shopping_shorts import seo_generate, seo_probe
from shopping_shorts import pattern_bank
from shopping_shorts import bank_assemble
from shopping_shorts import thumb_title
import uuid

app = FastAPI(title="숏템메이커 레퍼런스 랭킹")   # /docs 노출 제목 — 브랜드 통일(2026-07-25)

# 응답 gzip 압축(2026-07-30) — 유튜브 랭킹이 느리게 뜨던 직접 원인.
# /api/reference?platform=youtube 응답이 **3.34MB**였다(6,113건, 인스타는 0.30MB/289건).
# nginx는 gzip on이지만 gzip_types가 주석 처리돼 있어 application/json은 그대로 나갔다
# (서버 /etc/nginx/nginx.conf:53 실측). nginx 설정을 손으로 고치면 git에 안 남아
# 다음 배포 때 사라지므로, 앱에서 압축한다. JSON은 보통 8~10배 줄어든다.
# minimum_size: 작은 응답은 압축이 오히려 손해라 1KB 미만은 그대로 보낸다.
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.on_event("startup")
def _seed_voice_presets():
    """기동 시 큐레이션 프리셋을 DB로 upsert(idempotent)."""
    try:
        voice_presets.seed_presets(Store(DB_PATH))
    except Exception:
        pass  # seed 실패가 앱 기동을 막지 않게


@app.on_event("startup")
def _prune_activity_logs():
    """기동 시 오래된 활동·접속 로그 정리(2026-07-24) — customer_activity/customer_access는
    append만 돼 무한증가한다. 30일 지난 행을 지워 DB 비대를 막는다(best-effort, 실패 무시).
    재시작마다 도는 것으로 충분 — 표는 최근 트레일·7일 공유감지에만 쓰여 30일이면 넉넉하다."""
    try:
        n_act, n_acc = Store(DB_PATH).prune_activity(keep_days=30)
        if n_act or n_acc:
            import sys as _sys
            print(f"[prune] activity -{n_act}, access -{n_acc}", file=_sys.stderr)
    except Exception:
        pass  # 정리 실패가 앱 기동을 막지 않게


@app.on_event("startup")
def _warn_missing_contact():
    """유료게이트가 켜졌는데(_AUTH_ON) 연락처가 비어 있으면 기동 경고.
    수동 승격 모델에선 '무료 체험 끝' 모달이 결제 유입 경로의 전부다 — 연락처가 비면
    만료된 시니어가 '결제 문의 수단 없는 막다른 모달'을 본다. DASH_PASS 미설정(fail-open)
    경고와 같은 계열의 '배포하다 한 줄 빠뜨림' 방어(설계 재검토 2026-07-19)."""
    if not _AUTH_ON:
        return
    try:
        st = Store(DB_PATH)
        k = (st.get_setting("contact_kakao", "") or "").strip()
        p = (st.get_setting("contact_phone", "") or "").strip()
    except Exception:
        return
    if not k and not p:
        import sys as _sys
        print("⚠️ [유료게이트] contact_kakao·contact_phone 둘 다 비었습니다 → 체험 만료 고객이 "
              "결제 문의 수단 없는 모달을 봅니다. /admin에서 연락처를 설정하세요.", file=_sys.stderr)

# ── 틱톡 키워드검색 노브 기본값 + 비용 상수 (2026-07-14) ──
# clockworks/tiktok-scraper = $1.70/1,000건 → 1건 $0.0017 (조사확정).
_TIKTOK_SEARCH_COUNT_DEFAULT = 50      # 언어당 fetch 개수
_TIKTOK_DAILY_LIMIT_DEFAULT = 10       # 사용자별 하루 수집 횟수
_TIKTOK_MONTH_BUDGET_DEFAULT = 5.0     # 월 예산 상한($) — 넘으면 킬스위치
_TIKTOK_COST_PER_ITEM = 0.0017
_TIKTOK_LANG_KINDS = {"ko", "en", "ja", "zh", "ru"}   # 키워드 시드의 언어코드 kind

# ── 렌즈(SerpApi Google Lens) 유사영상 발굴 (2026-07-14) ──
# SerpApi 계정당 월 한도. ★실측값이다(2026-08-16, account API로 직접 확인):
#   키1 플랜 250회 · 키2 플랜 250회 → 계정당 250회.
#   예전 값 100은 실제와 달라, 우리 카운터가 200에 닿으면 **아직 300회가 남았는데도**
#   렌즈를 막았다. 플랜이 바뀌면 이 값도 같이 고쳐야 한다
#   (더 정확한 방법: https://serpapi.com/account?api_key= 로 실잔량을 읽는 것.
#    지금은 렌즈 호출 경로에 매번 왕복을 더하고 싶지 않아 상수로 둔다 — 환경변수로 조절).
_LENS_MONTH_LIMIT_PER_KEY = int(os.environ.get("LENS_MONTH_LIMIT_PER_KEY", "250"))


def _lens_month_limit(store):
    """이번 달 렌즈 월 상한. 설정(lens_month_limit)이 있으면 그 값, 없으면 SerpApi 키
    개수 × 100(무료 계정당 100회/월). 키가 소진되면 다음 키로 로테이션(lens_discover)되므로
    키를 추가하면 한도도 자동으로 늘어야 한다(2026-07-26: 2번째 키를 넣어도 한도가 100
    고정이라 101번째부터 막히던 문제 — 키 개수에 맞춰 자동 스케일)."""
    from shopping_shorts.config import SERPAPI_KEYS
    override = store.get_setting("lens_month_limit", "")
    if override:
        return int(override)
    return _LENS_MONTH_LIMIT_PER_KEY * max(1, len(SERPAPI_KEYS))


def _lens_quota_guard(store, month):
    """렌즈 월 가드 — 막아야 하면 429 JSONResponse, 통과면 None.

    ★판정을 여기 한 곳에서만 한다(0순위-B). /api/lens/search와 /api/lens/trace_url
    두 곳이 같은 판정을 따로 적고 있었다.

    순서: ① SerpApi **실잔량**(있으면 이게 진실) → ② 못 읽으면 우리 카운터 × 상수.
    ①이 필요한 이유는 `lens_discover.account_searches_left` 독스트링 참조 —
    우리 카운터는 클릭당 1인데 실제로는 최대 3회가 나가 어긋난다."""
    from shopping_shorts import lens_discover
    left = lens_discover.account_searches_left()
    if left is not None and left <= 0:
        return JSONResponse(status_code=429, content={
            "ok": False, "error_code": "lens_limit",
            "error": "이번 달 렌즈 검색 한도를 다 썼습니다(SerpApi 잔량 0)"})
    limit = _lens_month_limit(store)
    if store.lens_month_count(month) >= limit:
        return JSONResponse(status_code=429, content={
            "ok": False, "error_code": "lens_limit",
            "error": f"이번 달 렌즈 검색 한도({limit}회)를 다 썼습니다"})
    return None


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
def api_collect(request: Request, background_tasks: BackgroundTasks, limit: int | None = None, platform: str = "instagram", category: str | None = None):
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

    platform == "tiktok"이면 남용 방지 가드를 건다: 사용자별 하루 상한(초과 시
    429 daily_limit). 통과 후 수집하면 하루카운트 +1.

    ⚠️ 월예산 킬스위치(budget_exceeded)·추정지출 누적(add_tiktok_spend)은
    2026-07-24부로 건너뛴다 — 키워드검색(Apify 유료)이 옵트인으로 빠져
    _collect_tiktok()이 기본 include_paid_keywords=False(무료 yt-dlp 계정 시드만)라
    실제 지출이 없다. 그런데도 예산 게이트가 남아있으면 유령 지출이 쌓여
    무료 수집조차 budget_exceeded로 막혀버린다(이번 Fix 2 사유). 코드는
    지우지 않는다 — 나중에 유료 키워드검색을 다시 켤 때 이 블록도 함께
    되살릴 것(예산 체크 + est 계산 + add_tiktok_spend 복원).
    daily_limit(일일 횟수 제한)은 비용과 무관한 남용 방지 가드라 계속 유지한다.

    ★관리자(사장님 cid0) 전용(2026-07-22) — 수집=크롤 비용이 드는 운영 액션이라
    구독자(pro 포함)에겐 화면·API 모두 막는다. 화면 숨김만으론 pro가 직접 호출 가능."""
    denied = _require_admin(request)
    if denied:
        return denied
    if platform == "tiktok":
        guard = Store(DB_PATH)
        knobs = _tiktok_knobs(guard)
        now = datetime.now(timezone.utc)
        day = now.strftime("%Y-%m-%d")
        cid = _cid(request)
        # 월예산 킬스위치는 건너뜀 — 위 docstring 참고(유료 검색 꺼져 있어 실지출 없음).
        if guard.tiktok_daily_count(cid, day) >= knobs["daily_limit"]:
            return JSONResponse(status_code=429, content={
                "ok": False, "error_code": "daily_limit",
                "error": f"오늘 틱톡 수집 한도({knobs['daily_limit']}회)를 다 썼습니다"})
    # ★비동기(2026-07-25): 200채널 Apify를 요청 안에서 동기로 돌리면 ~40분 걸려
    # 게이트웨이 타임아웃 500이 난다(인스타 지금수집이 안 되던 근본원인). census와
    # 같은 job 패턴으로 접수만 하고 job_id를 즉시 돌려준 뒤 실제 수집은 백그라운드에서.
    # 프론트는 /api/collect/status/{job_id}를 폴링해 진행/결과를 받는다.
    job_id = uuid.uuid4().hex[:12]
    Store(DB_PATH).create_collect_job(job_id)
    background_tasks.add_task(_run_collect_job, job_id, platform, category, limit, _cid(request))
    return {"ok": True, "job_id": job_id, "async": True}


def _run_collect_job(job_id, platform, category, limit, cid):
    """background: collect() 실행 → (인스타)last_run 저장 → 결과를 job에 담아 done.
    실패는 민감정보 마스킹 후 error로 기록. 프론트는 status 폴링으로 결과/에러를 받는다.

    ★진행률(2026-07-28): 채널마다 result_json에 부분 payload를 쓴다. 예전엔 아무것도
    안 써서 50분간 화면이 그대로였고 사장님이 "멈췄다"고 판단해 취소했다(실사고).
    스키마 변경 없이 기존 폴링 경로에 그대로 실린다.
    """
    store = Store(DB_PATH)

    def _on_progress(done, total, items_so_far, tally):
        store.update_collect_job(job_id, result={
            "phase": "collecting", "done": done, "total": total,
            "items_so_far": items_so_far, "tally": tally,
        })

    try:
        items = collect(platform=platform,
                        categories=([category] if category else None),
                        limit_channels=limit, on_progress=_on_progress)
    except Exception as e:
        import re
        msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
        store.update_collect_job(job_id, status="error", error=msg)
        return
    try:
        if platform == "tiktok":
            store.bump_tiktok_daily(cid, datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        if platform != "instagram":
            _, collected_at = store.load_last_run_platform(platform)
        else:
            collected_at = datetime.now(timezone.utc).isoformat()
            store.save_last_run(items, collected_at)
            _attach_vision_tags(items, store)              # 이미 태깅된 것(재수집)은 즉시 실어 보냄
        # tally(채널별 성공/로그인벽/오류)를 결과에 남긴다 — 부계정(B안) 도입 판단 근거.
        payload = {"count": len(items), "items": items, "collected_at": collected_at,
                   "tally": dict(getattr(service, "LAST_COLLECT_TALLY", {}) or {})}
        store.update_collect_job(job_id, status="done", result=payload)
    except Exception as e:
        import re
        msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
        store.update_collect_job(job_id, status="error", error=msg)
        return
    # done 이후 느린 인스타 후속(초안·비전태깅·번역·대본은행) — 실패해도 결과엔 영향 없음(삼킨다).
    if platform == "instagram":
        try:
            generate_missing_drafts(next_draft_targets(items, store))
            _tag_new_items(items)
            # 비전태그로 카테고리 재분류 → 화면 캐시에 반영(크론 경로와 같은 동작).
            _changed = vision_tagging.recategorize_by_vision(items, DB_PATH)
            _changed += vision_tagging.apply_channel_category(items, DB_PATH)
            if _changed:
                store.save_last_run(items, collected_at)
            _translate_new_subjects(items)
            _bank_ingest_collected_bg(DB_PATH, items, collected_at)
        except Exception:
            pass


# playwright 경로는 채널마다 진행률을 써서 updated_at이 갱신된다 — 진짜로 멈춘 경우만
# stale로 잡히게 짧게 둔다(2026-07-28). apify 경로는 on_progress 콜백이 없어
# update_collect_job(done)이 완료 시점까지 한 번도 안 불린다 — updated_at이 생성 시각에
# 고정되므로 짧은 임계값을 쓰면 정상 진행 중인 수집(실측 28분 소요)이 중단으로 오판된다.
# 반드시 config.INSTAGRAM_SCRAPER 값으로 분기할 것 — 하나로 합치면 이 회귀가 재발한다.
_COLLECT_STALE_MIN_PLAYWRIGHT = 15
_COLLECT_STALE_MIN_APIFY = 60


def _collect_stale_min() -> int:
    if config.INSTAGRAM_SCRAPER == "playwright":
        return _COLLECT_STALE_MIN_PLAYWRIGHT
    return _COLLECT_STALE_MIN_APIFY


@app.get("/api/collect/status/{job_id}")
def api_collect_status(job_id: str):
    """수집 잡 상태/결과 폴링. running/done/error. done이면 count·items·collected_at 포함."""
    job = Store(DB_PATH).get_collect_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"ok": False, "error": "job 없음"})
    status = job["status"]
    if status == "running":
        try:
            age_min = (datetime.now(timezone.utc)
                       - datetime.fromisoformat(job["updated_at"])).total_seconds() / 60
        except Exception:
            age_min = 0
        if age_min > _collect_stale_min():
            return {"ok": True, "status": "error",
                    "error": "서버 재시작 등으로 중단되었습니다. 다시 시도해 주세요."}
        # ★진행률(2026-07-28): result_json에 채널마다 쓰인 phase 페이로드를 running 응답에도
        # 실어야 화면이 읽는다 — 전엔 여기서 누락돼 화면에 아무 변화가 없었다.
        return {"ok": True, "status": "running", "result": job["result"]}
    if status == "error":
        return {"ok": True, "status": "error", "error": job["error"] or "실패"}
    return {"ok": True, "status": "done", **(job["result"] or {})}


@app.get("/api/bank/ingest_report")
def api_bank_ingest_report():
    """'지금 수집' 후 은행 적재 결과 + 생성 순응 검열(usage_audit)을 함께 보고."""
    import json as _json
    store = Store(DB_PATH)
    raw = store.get_setting("bank_ingest_last", "")
    report = {"status": "none"}
    if raw:
        try:
            report = _json.loads(raw)
        except Exception:
            report = {"status": "none"}
    ua_raw = store.get_setting("bank_usage_audit_last", "")
    if ua_raw:
        try:
            report["usage_audit"] = _json.loads(ua_raw)
        except Exception:
            pass
    return {"ok": True, "report": report}


def _apply_activity(records):
    """센서스 활동레코드를 DB에 반영(생존/사망/부활). background_tasks로 실행."""
    store = Store(DB_PATH)
    for rec in records:
        store.upsert_activity(**rec)


@app.post("/api/census")
def api_census(request: Request, background_tasks: BackgroundTasks):
    """🔬 전수 센서스(비동기, 2026-07-22) — 전 채널(팔로워/사망 필터 없음)을 긁어 활동성
    판정. census가 수분 걸려 동기 응답은 모바일에서 Failed to fetch가 났다(서버는 완료해도
    화면만 실패). 그래서 잡을 접수하고 job_id만 즉시 돌려준 뒤 실제 작업은 background에서
    돌린다. 프론트는 /api/census/status/{job_id}를 폴링해 진행/결과를 받는다.

    ★관리자(사장님 cid0) 전용(2026-07-22) — 전 채널 크롤=고비용 운영 액션."""
    denied = _require_admin(request)
    if denied:
        return denied
    job_id = uuid.uuid4().hex[:12]
    Store(DB_PATH).create_census_job(job_id)
    background_tasks.add_task(_run_census_job, job_id)
    return {"ok": True, "job_id": job_id}


def _run_census_job(job_id):
    """background: census() 실행 → last_run 저장·활동반영·비전태그 → 결과를 job에 담아 done.
    느린 후속(초안·신규 비전태깅)은 done 뒤에 돌려 결과 응답을 늦추지 않는다. 실패는
    민감정보 마스킹 후 error로 기록 — 프론트는 status 폴링으로 이 결과/에러를 받는다."""
    store = Store(DB_PATH)
    try:
        result = census()
    except Exception as e:
        import re
        msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
        store.update_census_job(job_id, status="error", error=msg)
        return
    try:
        items = result["items"]
        collected_at = datetime.now(timezone.utc).isoformat()
        store.save_last_run(items, collected_at)          # 레퍼런스 랭킹 캐시도 갱신
        _apply_activity(result["activity_records"])       # 생존/사망/부활 DB반영
        _attach_vision_tags(items, store)                 # 기존 비전 태그 실어 보냄
        payload = {"count": len(items), "items": items,
                   "collected_at": collected_at, "dead": result["dead"],
                   "scanned_n": result["scanned_n"], "alive_n": result["alive_n"],
                   "dead_n": result["dead_n"], "revived_n": result["revived_n"]}
        store.update_census_job(job_id, status="done", result=payload)
    except Exception as e:
        import re
        msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
        store.update_census_job(job_id, status="error", error=msg)
        return
    # done 이후 느린 후속 — 실패해도 이미 저장된 결과엔 영향 없음(삼킨다).
    try:
        generate_missing_drafts(next_draft_targets(items, store))
        _tag_new_items(items)
        # 비전태그로 카테고리 재분류 → 캐시 재저장(수집 경로와 같은 동작).
        # 이게 빠져 있어서 전수조사가 마지막 갱신이면 캡션 없는 릴스가 전부
        # 채널 최빈 카테고리로 남았다(2026-08-03 실사고: 뎁덕 요리영상이 뷰티로).
        _changed = vision_tagging.recategorize_by_vision(items, DB_PATH)
        _changed += vision_tagging.apply_channel_category(items, DB_PATH)
        if _changed:
            store.save_last_run(items, collected_at)
    except Exception:
        pass


# 전수조사 잡이 이 분(min)간 갱신 없이 running이면 서버 재시작 등으로 죽은 잔해 → failed 통보.
_CENSUS_STALE_MIN = 20


@app.get("/api/census/status/{job_id}")
def api_census_status(job_id: str):
    """전수조사 잡 상태/결과 폴링. running/done/error. done이면 결과 payload를 함께 준다.
    running인데 오래 갱신이 없으면(서버 재시작 등) error로 알린다 — 무한 대기 방지."""
    job = Store(DB_PATH).get_census_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"ok": False, "error": "job 없음"})
    status = job["status"]
    if status == "running":
        try:
            age_min = (datetime.now(timezone.utc)
                       - datetime.fromisoformat(job["updated_at"])).total_seconds() / 60
        except Exception:
            age_min = 0
        if age_min > _CENSUS_STALE_MIN:
            return {"ok": True, "status": "error",
                    "error": "서버 재시작 등으로 중단되었습니다. 다시 시도해 주세요."}
        return {"ok": True, "status": "running"}
    if status == "error":
        return {"ok": True, "status": "error", "error": job["error"] or "실패"}
    return {"ok": True, "status": "done", **(job["result"] or {})}


# ── 유튜브 로컬 릴레이(2026-07-24) ── 서버 데이터센터 IP가 유튜브에 봇차단당해, 사장님 PC의
# 에이전트(youtube_relay_agent.py)가 큐를 폴링→주거용 IP로 다운로드→여기로 업로드한다.
def _relay_auth_ok(key):
    """에이전트 인증 — YT_RELAY_KEY 일치. 키 미설정이면 릴레이 자체를 잠근다(항상 거부)."""
    return bool(config.YT_RELAY_KEY) and hmac.compare_digest(key or "", config.YT_RELAY_KEY)


@app.get("/api/yt_relay/next")
def api_yt_relay_next(key: str = ""):
    """PC 에이전트가 폴링 — 처리할 pending 유튜브 요청 1건 {req_id, url} 또는 {}."""
    if not _relay_auth_ok(key):
        return JSONResponse(status_code=403, content={"ok": False, "error": "인증 실패"})
    job = Store(DB_PATH).next_pending_yt_relay()
    return {"ok": True, "job": job}


@app.post("/api/yt_relay/deliver/{req_id}")
async def api_yt_relay_deliver(req_id: str, key: str = Form(""),
                               file: UploadFile = File(None), error: str = Form("")):
    """에이전트가 결과 회신 — mp4 업로드(성공) 또는 error 문자열(실패). 파일은
    YT_RELAY_DIR에 저장하고 store에 done/failed 기록 → 서버 폴링(_download_via_relay)이 회수."""
    if not _relay_auth_ok(key):
        return JSONResponse(status_code=403, content={"ok": False, "error": "인증 실패"})
    store = Store(DB_PATH)
    if error and not file:
        store.finish_yt_relay(req_id, error=error[:500])
        return {"ok": True, "status": "failed"}
    if not file:
        return JSONResponse(status_code=400, content={"ok": False, "error": "파일·error 둘 다 없음"})
    config.YT_RELAY_DIR.mkdir(parents=True, exist_ok=True)
    ext = (Path(file.filename or "").suffix or ".mp4")
    out_path = config.YT_RELAY_DIR / (req_id + ext)
    with open(out_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    store.finish_yt_relay(req_id, out_path=str(out_path))
    return {"ok": True, "status": "done"}


# 채널에 못 박을 수 있는 카테고리 = categorize()의 topic 어휘와 1:1(2026-07-31).
# 여기 없는 값이 들어오면 화면 필터(TOPIC_CTYPE)에서 매핑이 없어 어느 버튼에도 안 뜬다.
_PINNABLE_CATEGORIES = ("홈템", "레시피", "뷰티", "기타")   # 2026-07-31 가전→홈템 병합

_VISION_TAG_CAP = 60  # 1회 수집당 새 태깅 상한(비용 가드). 초과분은 다음 수집 때.
_TRANSLATE_CAP = 40      # 수집직후 백그라운드 소재 번역(_translate_new_subjects, Task3)의 1회 상한. 이 엔드포인트는 안 씀.
_TRANSLATE_MAXLEN = 40   # 번역 요청 소재 길이 상한(비정상 입력 방어).


def _tag_new_items(items):
    """신규(태그 없는) 아이템 썸네일을 Gemini 비전 태깅 → vision_tags 저장.
    본체는 vision_tagging 모듈에 있다(2026-07-31) — systemd 타이머 수집 스크립트도
    같은 코드를 써야 해서 분리했다. 여기 두면 크론이 FastAPI 앱을 통째로 import해야 한다."""
    # cap을 넘겨준다 — _VISION_TAG_CAP이 여전히 이 앱의 노브다(테스트가 이걸 monkeypatch한다).
    vision_tagging.tag_new_items(items, DB_PATH, cap=_VISION_TAG_CAP)


def _translate_new_subjects(items):
    """수집 직후 백그라운드: 새 vision_subject를 한→중 번역해 translations 캐시에 채운다.
    이미 번역된 건 skip. 상한(_TRANSLATE_CAP) 초과분은 다음 수집으로 미룬다.
    비전태그가 먼저 채워져야 subject가 생기므로 1수집 지연은 정상(트렌드는 회차 누적)."""
    store = Store(DB_PATH)
    subjects = []
    seen = set()
    for it in items:
        s = (it.get("vision_subject") or "").strip()
        if s and s not in seen:
            seen.add(s)
            subjects.append(s)
    have = store.translations_map(subjects)
    todo = [s for s in subjects if s not in have]
    for s in todo[:_TRANSLATE_CAP]:
        try:
            zh = (video_analysis.translate_keyword(s) or {}).get("zh", "") or ""
        except Exception:
            zh = ""
        store.save_translation(s, zh)
    if len(todo) > _TRANSLATE_CAP:
        print(f"[translations] {len(todo) - _TRANSLATE_CAP}건 다음 수집으로 미룸(상한 {_TRANSLATE_CAP})")


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


@app.get("/api/translate")
def api_translate(q: str = ""):
    """트렌드카드용 한→중 소재 번역(캐시 우선). 미스면 translate_keyword 1회 후 저장.

    빈/과다 입력은 zh="" 로 안전 반환(딥링크는 ko 폴백). 캐시 히트는 Gemini 호출 0."""
    ko = (q or "").strip()
    if not ko:
        return {"ok": True, "ko": "", "zh": ""}
    if len(ko) > _TRANSLATE_MAXLEN:
        return {"ok": False, "ko": ko, "zh": "", "error": "too_long"}
    store = Store(DB_PATH)
    cached = store.get_translation(ko)
    if cached is not None:
        return {"ok": True, "ko": ko, "zh": cached}
    zh = ""
    try:
        zh = (video_analysis.translate_keyword(ko) or {}).get("zh", "") or ""
    except Exception:
        zh = ""
    store.save_translation(ko, zh)   # 빈 zh도 저장 → 반복 호출 방지
    return {"ok": True, "ko": ko, "zh": zh}


def _attach_posted_at(items):
    """인스타 항목에 발행시각 posted_at(ISO UTC)을 실어 보낸다(2026-08-03).

    age_hours는 수집 시점에 계산된 스냅샷이라 화면의 'X시간 전'이 다음 수집까지
    고정된다('계속 0시간 전' 제보). shortcode에 발행시각이 인코딩돼 있으므로
    (instagram_parse.shortcode_to_timestamp) 조회 경로에서 복원해 실어 주면
    프론트가 현재 시각 기준으로 나이를 계산할 수 있다. 인스타 전용 —
    유튜브 video id도 같은 알파벳이라 엉뚱한 시각으로 디코드될 수 있어 호출부가
    인스타 목록에만 쓴다."""
    for i in items:
        if not i.get("posted_at"):
            ts = shortcode_to_timestamp(i.get("shortcode") or "")
            if ts:
                i["posted_at"] = ts
    return items


def _attach_durations(items, store):
    """길이 캐시(reel_durations)를 실어 보내고, 빈 곳이 있으면 백필을 예약한다(2026-08-04).

    인스타 목록 수집엔 길이가 아예 없다(그리드 GraphQL 실측) — duration_backfill이
    yt-dlp 메타로 shortcode당 평생 1회 채운 캐시를 여기서 결합한다. 백필 예약은
    1시간에 1번 + 큐에 이미 있으면 스킵 — 조회 경로가 크롤을 몰아치지 않게."""
    missing = False
    if items:
        durs = store.duration_map([i.get("shortcode") for i in items])
        for i in items:
            if i.get("duration") in (None, "", 0):
                d = durs.get(i.get("shortcode"))
                if d is not None:
                    i["duration"] = d
                else:
                    missing = True
    global _DURFILL_LAST
    now = time.time()
    if missing and now - _DURFILL_LAST > 3600 \
            and not store.queue_has_pending("durfill", "k", "1"):
        _DURFILL_LAST = now
        store.enqueue("durfill", {"k": "1"})
    return items


_DURFILL_LAST = 0.0


@app.get("/api/reference")
def api_reference(platform: str = "instagram", days: int = 0, min_comments: int = 500,
                  archive: int = 0):
    """마지막 수집 결과 반환 (프론트 초기 로드용). platform=플랫폼(기본 인스타).

    days>0이면 '최근 N일 중 터진 것'을 대신 준다(2026-08-17) — 추가 크롤 0이고
    이미 받아둔 reel_history를 다시 보여줄 뿐이다. 등급제로 상단(48시간)이 얇아져도
    이 줄이 재고를 메운다. days=0(기본)은 종전과 완전히 같은 동작이다.

    archive=1이면 누적 아카이브(20만건)에서 역대 히트작을 준다. 이쪽도 추가 크롤 0
    (수집이 끝나 크론도 꺼져 있다). days보다 먼저 본다 — 둘 다 오면 아카이브가 이긴다."""
    store = Store(DB_PATH)
    if archive:
        if platform != "instagram":
            return {"ok": True, "items": [], "collected_at": None}
        items, collected_at = store.archive_hits(min_comments=min_comments), None
    elif days > 0:
        if platform != "instagram":
            return {"ok": True, "items": [], "collected_at": None}
        items, collected_at = store.hits_since(days, min_comments=min_comments), None
    elif platform == "instagram":
        items, collected_at = store.load_last_run()
    else:
        items, collected_at = store.load_last_run_platform(platform)
    # 🚫 영구차단(2026-07-30) — 카드의 차단 버튼이 넣은 removed_channels를 여기서 걸러낸다.
    # 수집(merge_tracked)도 같은 목록을 보지만, 이미 저장된 last_run에는 남아 있어
    # 차단 후 새로고침·업데이트 때 다시 뜨는 걸 막으려면 이 조회 경로에서도 잘라야 한다.
    blocked = store.removed_usernames()
    if blocked:
        items = [i for i in items
                 if (i.get("username") or "").strip().lstrip("@").lower() not in blocked]
    _attach_vision_tags(items, store)   # 백그라운드로 채워진 주제태그를 실어 보냄(검색 정확도 승격)
    _attach_durations(items, store)     # ⏱ 영상 길이 캐시 결합 + 빈 곳 백필 예약
    if platform == "instagram":
        _attach_posted_at(items)        # 'X시간 전' 실시간 계산용 발행시각
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


@app.get("/api/youtube/channels")
def api_youtube_channels(sort: str = "views"):
    """등록 유튜브 채널 리더보드(레퍼런스 랭킹식 지표: 조회수·속도·참여율·가속)."""
    return {"ok": True, **youtube_channel_board(sort=sort)}


@app.post("/api/seeds/from_youtube_videos")
def api_seeds_from_youtube_videos(body: dict):
    """렌즈 유사영상 유튜브 결과(영상 URL들) → 소속 채널을 account 시드로 대량 벤치등록.
    body: {urls:[영상URL,...]}. 같은 채널 1개로, 이미 등록된 채널은 duplicate로 집계.
    반환: {ok, added, duplicate, channels:[{channel_url, channel_title, dup}]}."""
    urls = [u for u in (body.get("urls") or []) if isinstance(u, str) and u.strip()]
    if not urls:
        return JSONResponse(status_code=422, content={"ok": False, "error": "urls 필요"})
    channels = yt_channels_from_videos(urls)
    store = Store(DB_PATH)
    existing = {(s["value"] or "").lower() for s in store.list_seeds("youtube")
                if s["kind"] == "account"}
    added = duplicate = 0
    out = []
    for ch in channels:
        url = ch["channel_url"]
        dup = url.lower() in existing
        if dup:
            duplicate += 1
        else:
            store.add_seed("youtube", "account", url)
            existing.add(url.lower())
            added += 1
        out.append({"channel_url": url, "channel_title": ch.get("channel_title", ""), "dup": dup})
    return {"ok": True, "added": added, "duplicate": duplicate, "channels": out}


@app.delete("/api/seeds")
def api_seeds_remove(body: dict):
    """시드 제거. body: {platform, value}."""
    Store(DB_PATH).remove_seed((body.get("platform") or "").strip(), (body.get("value") or "").strip())
    return {"ok": True}


# ── 샤오홍슈 계정 발굴(리더보드·담기·삭제) ──
@app.get("/api/xhs/discover")
def api_xhs_discover(min_notes: int = 2):
    """샤오홍슈 '카테고리별 잘하는 계정' 리더보드. 검색발굴을 작성자별 집계·참여도순.
    블랙리스트 제외, is_registered로 이미 담긴 계정 표시."""
    # 경합 가드: 해외HOT 수집이 도는 중이면 같은 로그인 세션을 다퉈 조용히 0건 위험 →
    # 아예 안 돌리고 잠시 후로 안내(무료 크롤끼리 세션 공유, 2026-07-29 실측).
    from shopping_shorts import overseas_hot_jobs
    if overseas_hot_jobs.status().get("status") == "running":
        return JSONResponse(status_code=200, content={"ok": False,
            "error": "지금 해외HOT 수집이 도는 중이라 발굴을 건너뛰었어요(세션이 겹치면 0건). 수집이 끝나면 다시 눌러주세요."})
    try:
        return {"ok": True, "items": service.discover_xiaohongshu_accounts(min_notes=min_notes)}
    except Exception as e:
        # 발굴 실패(무료 크롤 브라우저 닫힘·해외HOT 수집과 세션 경합 등)를 500이 아니라
        # 프론트가 이해할 JSON으로 돌려준다. 프론트는 이 메시지를 그대로 띄운다.
        return JSONResponse(status_code=200, content={"ok": False,
            "error": "발굴 실패(크롤이 막혔거나 해외HOT 수집과 겹쳤을 수 있어요). 잠시 후 다시 눌러보세요."})


@app.post("/api/xhs/adopt")
def api_xhs_adopt(body: dict):
    """[담기] — 발굴 계정을 레퍼런스 계정 시드로 등록. body: {profile_url, userid}."""
    url = (body.get("profile_url") or "").strip()
    if not url:
        return JSONResponse(status_code=422, content={"ok": False, "error": "profile_url 필요"})
    return service.adopt_xiaohongshu_account(url, userid=body.get("userid"))


@app.post("/api/xhs/blacklist")
def api_xhs_blacklist(body: dict):
    """[삭제] — 계정 시드 제거 + 영구 블랙리스트. body: {userid, profile_url}."""
    uid = (str(body.get("userid") or "")).strip()
    if not uid:
        return JSONResponse(status_code=422, content={"ok": False, "error": "userid 필요"})
    return service.blacklist_xiaohongshu_account(uid, profile_url=body.get("profile_url"))


@app.post("/api/xhs/followers")
def api_xhs_followers(body: dict):
    """[팔로워 대비] — 주어진 프로필들의 팔로워 수를 크롤해 {userid: follower}로 반환.
    계정마다 프로필 1회 크롤이라 느리고 세션을 점유 → 해외HOT 수집 중이면 거부.
    body: {profile_urls: [...]}  (프론트가 상위 N개만 보냄)."""
    from shopping_shorts import overseas_hot_jobs, xiaohongshu_playwright
    if overseas_hot_jobs.status().get("status") == "running":
        return JSONResponse(status_code=200, content={"ok": False,
            "error": "해외HOT 수집 중이라 팔로워 조회를 건너뛰었어요. 수집이 끝나면 다시 눌러주세요."})
    urls = [u for u in (body.get("profile_urls") or []) if isinstance(u, str) and u.strip()][:25]
    if not urls:
        return JSONResponse(status_code=422, content={"ok": False, "error": "profile_urls 필요"})
    try:
        return {"ok": True, "followers": xiaohongshu_playwright.fetch_follower_counts(urls)}
    except Exception:
        return JSONResponse(status_code=200, content={"ok": False,
            "error": "팔로워 조회 실패(크롤이 막혔을 수 있어요). 잠시 후 다시."})


@app.get("/api/xhs/latest")
def api_xhs_latest():
    """마지막 발굴 결과(캐시)를 크롤 없이 반환 — 다른 페이지 갔다 와도 바로 다시 띄운다."""
    return {"ok": True, **service.cached_xiaohongshu_accounts()}


@app.get("/api/xhs/auto")
def api_xhs_auto_get():
    """백그라운드 자동 발굴 on/off 상태 + 주기."""
    on = Store(DB_PATH).get_setting("xhs_bg_auto", "off") == "on"
    return {"ok": True, "on": on, "interval_min": config.XIAOHONGSHU_BG_INTERVAL_MIN}


@app.post("/api/xhs/auto")
def api_xhs_auto_set(body: dict):
    """백그라운드 자동 발굴 켜기/끄기. body: {on: bool}. 켜면 창을 닫아도 서버가
    주기적으로 발굴해 누적을 쌓는다(해외HOT 수집 중엔 자동 건너뜀)."""
    on = bool(body.get("on"))
    Store(DB_PATH).set_setting("xhs_bg_auto", "on" if on else "off")
    return {"ok": True, "on": on, "interval_min": config.XIAOHONGSHU_BG_INTERVAL_MIN}


@app.on_event("startup")
def _start_xhs_bg_discover_loop():
    """서버 백그라운드 발굴 루프 — DB 설정 'xhs_bg_auto'가 on이면 주기적으로 발굴해
    누적(xhs_discovery_log)을 쌓는다. 창이 닫혀 있어도 돈다. 해외HOT 수집 중이면 건너뛰어
    세션 경합을 피하고, 발굴은 등록은 안 하고 누적만 쌓는다(등록은 daily_batch가 하루 1회)."""
    if not getattr(config, "XIAOHONGSHU_BG_ENABLED", False):
        return
    import threading, time as _t, sys as _sys

    def _loop():
        interval = max(5, config.XIAOHONGSHU_BG_INTERVAL_MIN) * 60
        while True:
            _t.sleep(interval)
            try:
                if Store(DB_PATH).get_setting("xhs_bg_auto", "off") != "on":
                    continue
                from shopping_shorts import overseas_hot_jobs
                if overseas_hot_jobs.status().get("status") == "running":
                    continue  # 세션 경합 회피 — 다음 주기에 다시 시도
                if Store(DB_PATH).heavy_job_active():
                    continue  # ★렌더 양보(2026-07-30) — ffmpeg와 겹치면 서버가 swap으로 밀린다
                n = len(service.discover_xiaohongshu_accounts())   # 누적만 쌓음(등록 X)
                print(f"[xhs_bg] 발굴 누적 {n}계정", file=_sys.stderr)
            except Exception as e:              # noqa: BLE001 — 루프가 죽지 않게
                print(f"[xhs_bg] skip: {e}", file=_sys.stderr)

    threading.Thread(target=_loop, daemon=True).start()


@app.get("/api/discover/instagram")
def api_ig_discover(min_posts: int = 2):
    """인스타 '카테고리별 잘하는 계정' 리더보드(참여도=좋아요+댓글 합산, 2026-07-30, xhs 패턴 동일).
    무료 로그인세션 크롤(Playwright) — 인스타 릴스 수집과 같은 세션을 쓰므로
    수집이 도는 중이면 세션 경합으로 0건이 나올 수 있다(발굴 실패 메시지로 안내)."""
    try:
        return {"ok": True, "items": service.discover_instagram_accounts(min_posts=min_posts)}
    except Exception:
        return JSONResponse(status_code=200, content={"ok": False,
            "error": "발굴 실패(크롤이 막혔거나 인스타 수집과 세션이 겹쳤을 수 있어요). 잠시 후 다시 눌러보세요."})


@app.post("/api/discover/instagram/adopt")
def api_ig_discover_adopt(body: dict):
    """[담기] — 발굴 계정을 레퍼런스 추적목록(discovered_channels)에 등록.
    body: {username, full_name}."""
    username = (body.get("username") or "").strip()
    if not username:
        return JSONResponse(status_code=422, content={"ok": False, "error": "username 필요"})
    return service.adopt_instagram_discovery_account(username, full_name=body.get("full_name") or "")


@app.post("/api/discover/instagram/blacklist")
def api_ig_discover_blacklist(body: dict):
    """[삭제] — 추적목록 제거 + 영구 블랙리스트. body: {username}."""
    username = (body.get("username") or "").strip()
    if not username:
        return JSONResponse(status_code=422, content={"ok": False, "error": "username 필요"})
    return service.blacklist_instagram_discovery_account(username)


@app.get("/api/discover/instagram/latest")
def api_ig_discover_latest():
    """마지막 인스타 발굴 결과(캐시)를 크롤 없이 반환."""
    return {"ok": True, **service.cached_instagram_discovery()}


@app.get("/api/discover/instagram/auto")
def api_ig_discover_auto_get():
    """백그라운드 자동 발굴 on/off 상태 + 주기."""
    on = Store(DB_PATH).get_setting("ig_discovery_bg_auto", "off") == "on"
    return {"ok": True, "on": on, "interval_min": config.XIAOHONGSHU_BG_INTERVAL_MIN}


@app.post("/api/discover/instagram/auto")
def api_ig_discover_auto_set(body: dict):
    """백그라운드 자동 발굴 켜기/끄기. body: {on: bool}."""
    on = bool(body.get("on"))
    Store(DB_PATH).set_setting("ig_discovery_bg_auto", "on" if on else "off")
    return {"ok": True, "on": on, "interval_min": config.XIAOHONGSHU_BG_INTERVAL_MIN}


@app.on_event("startup")
def _start_ig_bg_discover_loop():
    """서버 백그라운드 발굴 루프 — DB 설정 'ig_discovery_bg_auto'가 on이면 주기적으로
    발굴해 누적(ig_discovery_log)을 쌓는다(xhs 백그라운드 루프와 동일 패턴, 2026-07-30).
    등록은 안 하고 누적만 쌓는다(등록은 daily_batch가 하루 1회, 킬스위치 필요)."""
    import threading, time as _t, sys as _sys

    def _loop():
        interval = max(5, config.XIAOHONGSHU_BG_INTERVAL_MIN) * 60
        while True:
            _t.sleep(interval)
            try:
                if Store(DB_PATH).get_setting("ig_discovery_bg_auto", "off") != "on":
                    continue
                if Store(DB_PATH).heavy_job_active():
                    continue  # ★렌더 양보(2026-07-30) — Playwright는 브라우저라 메모리가 크다
                n = len(service.discover_instagram_accounts())   # 누적만 쌓음(등록 X)
                print(f"[ig_discovery_bg] 발굴 누적 {n}계정", file=_sys.stderr)
            except Exception as e:              # noqa: BLE001 — 루프가 죽지 않게
                print(f"[ig_discovery_bg] skip: {e}", file=_sys.stderr)

    threading.Thread(target=_loop, daemon=True).start()


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
    _attach_posted_at(queue)   # 인스타 큐 — 'X시간 전' 실시간 계산용
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


def _enqueue_prewarm(store, shortcode, url, *, caption="", customer_id="0", category=None):
    """담긴 영상의 사전분석(추출+구조분석)을 워커 큐에 걸어 제작소 1단계 로딩을 없앤다
    (2026-07-30, 설계 `2026-07-29-추출속도-3종묶음-design.md` §2①).

    여기서 걸러야 하는 것들(큐를 더럽히지 않는다):
      · URL 없음 — 워커가 다운로드할 게 없다.
      · 이미 유효 캐시 — 예열할 이유가 없다(제미니 재과금 방지).
      · 같은 shortcode가 이미 큐에 있음 — 담기취소·재담기 연타로 중복 적재 방지.
    래치·크레딧·일일상한은 워커 쪽 `prewarm.run_prewarm`이 최종 판단한다(서버는 얇게).
    실패는 조용히 — 예열이 안 걸려도 제작소가 그때 추출하므로 기능은 그대로다."""
    try:
        if not (shortcode and (url or "").strip()):
            return False
        cached = store.get_extract(shortcode)
        # ★'유효 캐시'의 기준은 한 곳에서만 정한다(2026-08-16 리뷰). 여기만 full_text로
        #   보고 있어, 무자막 영상(화면 태깅만 있는 것)은 이미 저장돼 있는데도 매번
        #   "캐시 없음"으로 큐에 다시 들어갔다. 워커가 걸러 재과금은 없지만 큐가 더러워진다.
        if has_usable_result(cached):
            return False
        if store.queue_has_pending("prewarm", "shortcode", shortcode):
            return False
        store.enqueue("prewarm", {"shortcode": shortcode, "url": url, "caption": caption,
                                  "customer_id": str(customer_id), "category": category})
        return True
    except Exception as e:  # noqa: BLE001 — 예열 실패는 담기를 막지 않는다
        print(f"prewarm enqueue 실패(무해) {shortcode}: {e}", file=sys.stderr)
        return False


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
        _enqueue_prewarm(store, sc, url, caption=body.get("caption") or "", customer_id=cid)
    return {"ok": True, "in": in_basket, "count": len(store.mix_basket_shortcodes(customer_id=cid))}


@app.post("/api/mix/basket/remove")
def api_mix_basket_remove(request: Request, body: dict):
    """바구니에서 shortcode 제거."""
    sc = (body.get("shortcode") or "").strip()
    store = Store(DB_PATH)
    cid = _cid(request)
    store.mix_basket_remove(sc, customer_id=cid)
    return {"ok": True, "count": len(store.mix_basket_shortcodes(customer_id=cid))}


@app.post("/api/mix/basket/reprobe")
def api_mix_basket_reprobe(request: Request, body: dict, background_tasks: BackgroundTasks):
    """즐겨찾기 카드의 보강메타(조회수·좋아요·댓글·팔로워 등)를 다시 수집한다
    (2026-07-21 사장님 요청). 담을 때 메타가 안 넘어왔거나 백그라운드 probe가
    실패해 카드가 비어 보이는 항목을 사장님이 카드에서 직접 재수집한다 —
    자동 재수집은 Apify/토큰 비용이 들어 안 돌리고 버튼으로만(원하는 것만).
    담기(toggle)와 같은 `_enrich_grab` 경로를 재사용하므로 팔로워를 안 주는
    플랫폼(틱톡)은 여전히 조회수·좋아요·댓글까지만 채워진다(그건 플랫폼 한계)."""
    sc = (body.get("shortcode") or "").strip()
    if not sc:
        return JSONResponse(status_code=422, content={"ok": False, "error": "shortcode 필요"})
    store = Store(DB_PATH)
    cid = _cid(request)
    item = next((x for x in store.mix_basket_list(customer_id=cid)
                 if x.get("shortcode") == sc), None)
    if not item:
        return JSONResponse(status_code=404, content={"ok": False, "error": "담긴 항목이 아닙니다"})
    url = item.get("url") or ""
    if not (url and _grab_platform(url)):
        return JSONResponse(status_code=400,
                            content={"ok": False, "error": "재수집할 수 없는 링크입니다"})
    background_tasks.add_task(_enrich_grab, url, sc, cid)
    return {"ok": True}


@app.get("/api/mix/basket")
def api_mix_basket(request: Request):
    """바구니 항목 목록(담은 순서) + shortcode 집합."""
    store = Store(DB_PATH)
    cid = _cid(request)
    items = store.mix_basket_list(customer_id=cid)
    # 담을 때 저장한 인스타 CDN 썸네일은 며칠이면 만료(403)되어 검은칸이 된다
    # (2026-08-09 실측). 아카이브 크롤이 매일 새 URL을 받아오므로 있으면 그걸로 바꿔서 준다.
    try:
        codes = [i.get("shortcode") for i in items if i.get("shortcode")]
        if codes:
            with store._conn() as c:
                q = ",".join("?" * len(codes))
                fresh = dict(c.execute(
                    f"SELECT shortcode, thumbnail FROM channel_archive "
                    f"WHERE shortcode IN ({q}) AND thumbnail!=''", codes).fetchall())
            for i in items:
                t = fresh.get(i.get("shortcode"))
                if t:
                    i["thumbnail"] = t
    except Exception as e:  # noqa: BLE001 — 썸네일 보강 실패가 목록을 막지 않는다
        print(f"basket 썸네일 보강 실패(무해): {e}", file=sys.stderr)
    _attach_durations(items, store)   # ⏱ 길이(2026-08-09 — 랭킹·히트작과 동일)
    return {"ok": True, "items": items,
            "shortcodes": sorted(store.mix_basket_shortcodes(customer_id=cid))}


@app.post("/api/enrich")
def api_enrich(request: Request, body: dict):
    """레퍼런스(바구니 카드 등)의 소스 링크를 보강정보(채널명·구독자·조회수·인기댓글 등)로
    채운다. 유튜브는 API 무료쿼터라 누구나 자동 조회+7일 캐시. 비유튜브(틱톡 등)는 실조회가
    Apify 유료라 기본은 needs_manual만 반환하고, force=true(관리자 전용)일 때만 실조회를
    시도한다 — 비관리자가 force로 남의 크레딧을 태우지 못하게 게이트(2026-07-22)."""
    url = (body.get("url") or "").strip()
    platform = (body.get("platform") or "").lower()
    force = bool(body.get("force"))
    if not url:
        return {"status": "no_data"}
    store = Store(DB_PATH)
    cached = store.get_enrichment(url)
    if cached:
        return {"ok": True, **cached}
    now = datetime.utcnow().isoformat()
    if platform == "youtube" or "youtu" in url:
        data = enrich_youtube(url)
        if not data:
            store.upsert_enrichment(url, platform, {}, "no_data", now)
            return {"status": "no_data"}
        if data.get("status") == "quota":
            return {"status": "quota"}          # 쿼터소진은 캐시하지 않음(다음 시도가 다른 키로 성공할 수 있음)
        store.upsert_enrichment(url, "youtube", data, "ok", now)
        return {"ok": True, "status": "ok", **data}
    if not force:
        return {"status": "needs_manual"}
    denied = _require_admin(request)   # 비유튜브 실조회는 관리자만(브라우저·크레딧 보호)
    if denied:
        return denied
    # 인스타 force(관리자): Apify 없이 우리 세션의 릴 상세 조회로 채운다(2026-08-10
    # 사장님 "렌즈 인스타 카드에 몇초짜리인지 정보가 없다"). 같은 응답의
    # video_dash_manifest에서 길이(⏱)까지 뽑아 reel_durations에 영구 저장 —
    # 이후 렌즈·히트작·랭킹 어디서든 재조회 없이 뜬다.
    m = _IG_SC_RE.search(url)
    if (platform == "instagram" or "instagram.com" in url) and m:
        sc = m.group(1)
        try:
            from shopping_shorts.duration_backfill import _manifest_duration
            from shopping_shorts.instagram_parse import shortcode_to_pk
            from shopping_shorts.instagram_playwright import (_detail_context,
                                                              _fetch_reel_detail)
            node = None
            pk = shortcode_to_pk(sc)
            if pk:
                with _detail_context() as ctx:
                    node = _fetch_reel_detail(ctx, pk, sc)
            if node:
                user = node.get("user") if isinstance(node.get("user"), dict) else {}
                cap = node.get("caption") if isinstance(node.get("caption"), dict) else {}
                dur = _manifest_duration(node)
                if dur:
                    store.set_reel_duration(sc, dur)
                ts = node.get("taken_at")
                data = {k: v for k, v in {
                    "channel_name": (user or {}).get("username") or "",
                    "channel_url": ("https://www.instagram.com/%s/" % user["username"]) if (user or {}).get("username") else "",
                    "views": node.get("play_count") or node.get("view_count"),
                    "likes": node.get("like_count"),
                    "comment_count": node.get("comment_count"),
                    "duration": dur,
                    "upload_date": datetime.utcfromtimestamp(ts).isoformat() if isinstance(ts, (int, float)) and ts > 0 else "",
                    "caption": ((cap or {}).get("text") or "")[:1000],
                }.items() if v not in (None, "")}
                store.upsert_enrichment(url, "instagram", data, "ok", now)
                return {"ok": True, "status": "ok", **data}
        except Exception:                  # noqa: BLE001 — 조회 실패는 no_data로(검색은 계속)
            pass
        return {"status": "no_data"}       # 실패는 캐시 안 함 — 다음 클릭이 성공할 수 있다
    # 그 외 비유튜브(틱톡 등) force: Apify 경로 — 현 단계는 미구현 스텁(후속 계획)
    return {"status": "no_data"}


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
    known |= store.removed_usernames()   # 🚫 차단 채널 = 재발굴 금지(discover_jobs와 동일)
    return known


# 발굴은 "최근 이틀 영상수"를 세야 해서 채널당 상한을 넉넉히(메인 랭킹의 3보다 큼).
# 경로 선택은 discover_jobs와 동일 킬스위치(config.INSTAGRAM_SCRAPER)를 공유(2026-07-30).
def _discover_fetch(usernames):
    from shopping_shorts import config
    if config.INSTAGRAM_SCRAPER == "playwright":
        from shopping_shorts import instagram_playwright
        return instagram_playwright.fetch_reels(usernames)
    return fetch_reels(usernames, results_per_channel=12, only_newer_than="2 days")


def _discover_search_fn():
    from shopping_shorts import config
    if config.INSTAGRAM_SCRAPER == "playwright":
        from shopping_shorts import instagram_playwright
        return instagram_playwright.search_channels
    return instagram_search.search_channels


def _discover_profiles_fn():
    from shopping_shorts import config
    if config.INSTAGRAM_SCRAPER == "playwright":
        from shopping_shorts import instagram_playwright
        return instagram_playwright.fetch_profiles
    return fetch_profiles


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
def api_discover(request: Request, keyword: str, max_channels: int = 15):
    """🔎 채널 발굴 — 카테고리 키워드로 '내가 모르던 채널' 중 최근 48h 댓글이
    빠르게 쌓이는 릴스를 캐치(기존 랭킹엔진 재사용).

    ★관리자(사장님 cid0) 전용(2026-07-23) — 검색+릴스수집+프로필 = Apify 유료
    크롤이라 수집·전수조사와 같은 관리자 가드를 건다."""
    denied = _require_admin(request)
    if denied:
        return denied
    keyword = (keyword or "").strip()
    if not keyword:
        return JSONResponse(status_code=422, content={"ok": False, "error": "키워드를 입력하세요"})
    store = Store(DB_PATH)
    try:
        items = discovery.discover(
            keyword, known=_known_usernames(store),
            search_fn=_discover_search_fn(), fetch_reels_fn=_discover_fetch,
            profiles_fn=_discover_profiles_fn(),
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
def api_discover_update(request: Request, days: int = 2, max_total: int = 40,
                        accumulate: bool = False, auto_register: bool = False):
    """🔄 업데이트 시작(비동기) — 몇 분 걸리는 수집을 백그라운드 스레드로 돌리고
    즉시 반환한다(2026-07-12, 동기처리 시 프론트가 몇 분 멈추고 배포 재시작에
    응답이 깨지던 문제). 프론트는 /api/discover/status를 폴링해 진행/결과 확인.

    ★관리자(사장님 cid0) 전용(2026-07-23) — 무료 Playwright 경로 기본(2026-07-30,
    config.INSTAGRAM_SCRAPER)이라 과금 걱정은 없지만, 여전히 몇 분~1시간대 크롤이라
    관리자 가드는 유지. 결과 피드는 전 회원 공유라 회원이 눌러야 할 이유도 없다
    (보기는 /api/discover/feed로 그대로 열림). max_total 상한 300(2026-07-30 확대,
    기존 120 — 무료 전환 후 채널당 크롤이 아무리 늘어도 과금이 안 붙어 상향 가능해짐).
    auto_register=True면 발굴 전부를 사람 확인 없이 discovered_channels에 자동 등록
    (매일 07시 크론 전용 — 화면 수동 버튼은 기본 false로 [목록추가] 확인 후 등록)."""
    denied = _require_admin(request)
    if denied:
        return denied
    from shopping_shorts import discover_jobs
    days = max(1, min(int(days), 14))
    max_total = max(10, min(int(max_total), 300))
    st = discover_jobs.start(days, max_total, accumulate, auto_register=auto_register)
    return {"ok": True, **st, "categories": _DISCOVER_CATEGORIES,
            "days": days, "accumulate": accumulate}


@app.get("/api/discover/status")
def api_discover_status():
    """업데이트 백그라운드 잡 진행상황(running/done/error) + 완료 시 결과."""
    from shopping_shorts import discover_jobs
    return {"ok": True, **discover_jobs.status()}


@app.get("/api/discover/feed")
def api_discover_feed():
    """마지막 발굴 피드 반환(새로고침 시 복원 — 특히 누적 모드).
    🚫 영구차단(2026-07-30): 카드의 차단 버튼이 넣은 removed_channels를 걸러낸다.
    다음 발굴은 known 제외로 안 담지만, 이미 저장된 피드에는 남아 있어 여기서도 잘라야
    차단 후 새로고침에 다시 뜨지 않는다(/api/reference와 같은 처리)."""
    store = Store(DB_PATH)
    items, updated_at = store.load_discovery_feed()
    blocked = store.removed_usernames()
    # ➕ 추적목록에 있는 채널은 피드에서 숨긴다(2026-08-03 사장님 지시 재적용) —
    # [목록추가]를 누르면 새로고침 후에도 다시 안 뜬다. 오전의 '피드 통째 소실'은
    # 07시 크론 자동등록이 원인이었고, 같은 날 auto_register=False로 껐으므로
    # 이제 숨겨도 피드가 비지 않는다(발굴분은 사람이 추가하기 전까지 미등록).
    added = {(d.get("username") or "").strip().lstrip("@").lower()
             for d in store.discovered_channels()}
    hide = blocked | added
    if hide:
        items = [i for i in items
                 if (i.get("username") or "").strip().lstrip("@").lower() not in hide]
    _attach_posted_at(items)   # 발굴 피드도 인스타 릴스 — 'X시간 전' 실시간 계산용
    _attach_durations(items, store)   # ⏱ 길이(2026-08-09 — 랭킹·히트작과 동일)
    return {"ok": True, "items": items, "updated_at": updated_at}


@app.get("/api/overseas/update")
def api_overseas_update():
    """해외HOT 수집 시작(백그라운드). 프론트는 /api/overseas/status 폴링."""
    from shopping_shorts import overseas_hot_jobs
    return {"ok": True, **overseas_hot_jobs.start()}


@app.get("/api/overseas/status")
def api_overseas_status():
    from shopping_shorts import overseas_hot_jobs
    return {"ok": True, **overseas_hot_jobs.status()}


@app.get("/api/overseas/feed")
def api_overseas_feed():
    items, updated_at = Store(DB_PATH).load_overseas_feed()
    return {"ok": True, "items": items, "updated_at": updated_at}


@app.post("/api/overseas/pickup")
def api_overseas_pickup(request: Request, body: dict):
    """무료크롤로 고른 틱톡 URL을 '픽업' 카테고리로 담는다(관리자 전용, Apify postURLs 픽업).

    body: {"urls": [...]} 또는 {"text": "줄바꿈/콤마로 구분한 URL들"}. 지정 URL만 과금."""
    denied = _require_admin(request)
    if denied:
        return denied
    from shopping_shorts import overseas_hot_jobs
    raw = body.get("urls") or body.get("text") or ""
    if isinstance(raw, str):
        urls = [u for u in re.split(r"[\s,]+", raw) if u.startswith("http")]
    else:
        urls = [u for u in raw if isinstance(u, str) and u.startswith("http")]
    if not urls:
        return {"ok": False, "error": "URL이 없어요"}
    try:
        added = overseas_hot_jobs.add_pickup(urls)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "added": added}


@app.post("/api/discover/add")
def api_discover_add(request: Request, username: str, name: str = ""):
    """발굴 채널을 벤치마크 목록에 추가(이후 메인 랭킹에도 추적).

    ★관리자(사장님 cid0) 전용(2026-07-23) — 클릭 자체 비용은 0이지만, 추가된 채널이
    전 회원 공유 추적목록에 들어가 다음날부터 매일 자동수집(Apify 유료)이 늘어난다.
    발굴 실행·레퍼런스 URL 등록과 같은 관리자 가드를 건다(피드 보기는 전 회원 유지)."""
    denied = _require_admin(request)
    if denied:
        return denied
    Store(DB_PATH).add_discovered(username.strip().lstrip("@"), name)
    return {"ok": True, "username": username}


@app.get("/api/discover/add_by_url", response_class=HTMLResponse)
def api_discover_add_by_url(request: Request, url: str = "", username: str = ""):
    """인스타 담기 유저스크립트의 '📌 채널등록' 버튼용(2026-08-03 사장님 요청).

    브라우저가 popup으로 여는 GET이라 세션 쿠키가 실려 관리자 가드가 그대로 먹는다
    (POST /api/discover/add를 instagram.com에서 fetch하면 CORS/쿠키로 막힘 — 그래서
    /api/grab과 같은 popup 방식). username이 오면 즉시 등록(프로필 페이지),
    url만 오면 yt-dlp로 게시물의 채널을 해석해 등록(릴스/게시물 페이지)."""
    denied = _require_admin(request)
    if denied:
        return HTMLResponse(_chadd_html("⛔ 관리자 로그인 필요",
                                        "shoppingshorts.duckdns.org에 관리자로 로그인 후 다시 눌러주세요."))
    store = Store(DB_PATH)
    # 틱톡(2026-08-03 사장님 '틱톡도 동일하게'): 틱톡 채널은 인스타 추적목록
    # (discovered_channels)이 아니라 시드(seeds, kind=account)로 등록해야 랭킹 수집이
    # 잡는다 — 테이블을 섞으면 인스타 수집이 틱톡 핸들을 긁으려다 실패한다.
    if "tiktok.com" in (url or ""):
        m = re.search(r"tiktok\.com/@([\w.\-]+)", url or "")
        tname = (username or (m.group(1) if m else "")).strip().lstrip("@")
        if not tname:
            return HTMLResponse(_chadd_html("❌ 채널을 못 찾았어요", "틱톡 영상/프로필 화면에서 눌러주세요."))
        existing = {s2.get("value", "").lstrip("@").lower()
                    for s2 in store.list_seeds("tiktok") if s2.get("kind") == "account"}
        if tname.lower() in existing:
            return HTMLResponse(_chadd_html("✔ 이미 등록된 채널", f"@{tname} — 틱톡 시드로 추적 중입니다."))
        store.add_seed("tiktok", "account", tname)
        return HTMLResponse(_chadd_html("✅ 틱톡 채널 등록 완료",
                                        f"@{tname} — 다음 틱톡 수집부터 랭킹에 잡힙니다."))
    uname, disp = (username or "").strip().lstrip("@"), ""
    if not uname and url:
        try:
            import subprocess, sys, json
            r = subprocess.run([sys.executable, "-m", "yt_dlp", "-j", "--no-warnings", url],
                               capture_output=True, text=True, timeout=60)
            d = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else {}
            uname = (d.get("uploader_id") or "").strip().lstrip("@")
            # 인스타는 uploader_id가 숫자 pk로 오기도 한다 → channel(핸들)을 우선
            ch = (d.get("channel") or "").strip().lstrip("@")
            if ch and not ch.isdigit():
                disp = (d.get("uploader") or "").strip()
                if uname.isdigit() or not uname:
                    uname = ch
            else:
                disp = (d.get("uploader") or "").strip()
        except Exception:
            pass
    if not uname or uname.isdigit():
        return HTMLResponse(_chadd_html("❌ 채널을 못 찾았어요", "게시물/릴스 화면에서 다시 눌러주세요."))
    key = uname.lower()
    if key in {(d.get("username") or "").strip().lstrip("@").lower()
               for d in store.discovered_channels()}:
        return HTMLResponse(_chadd_html("✔ 이미 등록된 채널", f"@{uname} — 레퍼런스 추적 중입니다."))
    was_blocked = key in store.removed_usernames()
    store.add_discovered(uname, name=disp)   # add_discovered가 차단도 해제한다
    tail = " (차단 해제됨)" if was_blocked else ""
    return HTMLResponse(_chadd_html("✅ 채널 등록 완료" + tail,
                                    f"@{uname}{'·' + disp if disp else ''} — 다음 수집(09/15/21시)부터 랭킹에 잡힙니다."))


# 유저스크립트 시크바용 조회수·댓글수 캐시 — URL당 1회만 yt-dlp를 태운다.
# 사장님이 릴스를 훑는 속도만큼 호출되므로, 캐시 없으면 인스타 429 예산(수집분)을 갉아먹는다.
_MEDIA_STATS_CACHE = {}
_MEDIA_STATS_MAX = 500


@app.get("/api/media_stats")
def api_media_stats(url: str = ""):
    """인스타/틱톡 게시물의 조회수·좋아요·댓글수(2026-08-03 사장님 '조회수랑 댓글수도').
    yt-dlp -j 메타만 조회(다운로드 없음). 페이지 DOM엔 이 수치가 안정적으로 없어서
    (인스타 모달은 '여러 명이 좋아합니다'로 숨김) 서버 해석이 유일한 신뢰 경로."""
    m = re.search(r"(instagram\.com/(?:reel|reels|p|tv)/[A-Za-z0-9_-]+|tiktok\.com/@[\w.\-]+/video/\d+)",
                  url or "")
    if not m:
        return JSONResponse(status_code=400, content={"ok": False, "error": "지원하지 않는 URL"})
    key = m.group(1)
    if key in _MEDIA_STATS_CACHE:
        return _MEDIA_STATS_CACHE[key]
    try:
        import subprocess, sys, json
        r = subprocess.run([sys.executable, "-m", "yt_dlp", "-j", "--no-warnings",
                            "https://www." + key], capture_output=True, text=True, timeout=45)
        d = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else {}
        out = {"ok": True, "views": d.get("view_count"),
               "likes": d.get("like_count"), "comments": d.get("comment_count")}
        if not (out["views"] is None and out["likes"] is None and out["comments"] is None):
            if len(_MEDIA_STATS_CACHE) >= _MEDIA_STATS_MAX:
                _MEDIA_STATS_CACHE.clear()
            _MEDIA_STATS_CACHE[key] = out   # 실패·전부 None은 캐시 안 함(다음에 재시도)
        return out
    except Exception:
        return JSONResponse(status_code=502, content={"ok": False, "error": "조회 실패"})


def _chadd_html(title, body):
    return ("<html><body style='font-family:system-ui;background:#111;color:#eee;"
            "display:flex;flex-direction:column;align-items:center;justify-content:center;"
            "height:90vh;margin:0;text-align:center'>"
            f"<div style='font-size:20px;font-weight:800;margin-bottom:10px'>{title}</div>"
            f"<div style='font-size:13px;color:#aaa;padding:0 14px'>{body}</div>"
            "<button onclick='window.close()' style='margin-top:16px;background:#1f6feb;color:#fff;"
            "border:none;border-radius:8px;padding:8px 18px;cursor:pointer'>닫기</button></body></html>")


@app.get("/api/discover/added")
def api_discover_added():
    """발굴로 추가한 채널 목록."""
    return {"ok": True, "items": Store(DB_PATH).discovered_channels()}


@app.get("/api/refs/instagram")
def api_refs_instagram(request: Request):
    """관리페이지용 인스타 레퍼런스 통합 목록(2026-07-24) — 엑셀 기본 채널 + 손등록을
    union(제외 반영)하고 활동여부를 붙인다. **Apify 조회 없음(무료)**: 구독자수는 엑셀에
    이미 있는 값만, 활동일(last_active)은 수집이력(reel_history)에서. 그래서 사장님이
    '엑셀에 원래 있던 채널까지 한 표에서, 살아있는지 보고' 관리할 수 있다."""
    denied = _require_admin(request)
    if denied:
        return denied
    store = Store(DB_PATH)
    try:
        excel = load_channels()          # 엑셀 벤치마킹 채널(서버에만 있음 — 로컬은 빈 목록)
    except Exception:
        excel = []
    excel_norm = {store._norm_username(c["username"]) for c in excel}
    disc = store.discovered_channels()
    removed = store.removed_usernames()
    # 관리 목록은 수집비 cap과 무관하게 '등록된 전부'를 보여준다(수집은 별도로 cap 적용).
    merged = merge_tracked(excel, disc, removed, max_channels=10 ** 9)
    act = store.instagram_activity_map()
    added = {store._norm_username(d["username"]): d.get("added_at", "") for d in disc}
    pinned = store.channel_category_map()
    items = []
    for ch in merged:
        u = store._norm_username(ch["username"])
        a = act.get(u, {})
        items.append({
            "username": (ch["username"] or "").lstrip("@"),
            "name": a.get("name") or ch.get("name") or "",
            "followers": int(ch.get("followers") or 0),
            "last_active": a.get("last") or "",   # ""=수집된 적 없음
            "added_at": added.get(u, ""),
            "source": "excel" if u in excel_norm else "manual",
            "category": pinned.get(u, ""),      # 사람이 지정한 것만(빈값=자동판정)
        })
    return {"ok": True, "items": items}


@app.post("/api/refs/category")
def api_refs_set_category(request: Request, username: str, category: str = ""):
    """채널 카테고리 지정/해제(관리자 전용, 2026-07-31).
    category 빈값이면 해제 → 자동판정으로 되돌아간다.
    ★이 값은 비전태그가 없는 영상에만 적용되는 **폴백**이다(vision_tagging 주석 참조)."""
    denied = _require_admin(request)
    if denied:
        return denied
    cat = (category or "").strip()
    if cat and cat not in _PINNABLE_CATEGORIES:
        return JSONResponse(status_code=422, content={
            "ok": False, "error": f"알 수 없는 카테고리: {cat}"})
    Store(DB_PATH).set_channel_category(username, cat)
    return {"ok": True, "username": username, "category": cat}


@app.post("/api/reference/register")
def api_reference_register(request: Request, url: str):
    """레퍼런스 채널을 URL 붙여넣기로 직접 등록(2026-07-18). 인스타 채널/릴스
    URL에서 username을 뽑아 discovered_channels에 소프트 추가 — 엑셀 원본은
    안 건드리고 다음 수집부터 랭킹에 포함(비용 0, 프로필 조회 안 함).
    이미 엑셀·발굴목록에 있으면 already=True로 알려주고 중복 추가하지 않는다.

    ★관리자(사장님 cid0) 전용(2026-07-22) — 랭킹 대상(레퍼런스 목록) 편집은 운영 액션."""
    denied = _require_admin(request)
    if denied:
        return denied
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


@app.get("/api/channel/history")
def api_channel_history(username: str, exclude: str = ""):
    """채널 검색 시 '지난 한 달'(2026-07-22) — 그 채널의 누적 히스토리(reel_history)를
    last_seen 최신순으로 반환. exclude=지금 48h 랭킹에 이미 뜬 shortcode 쉼표목록
    (중복 카드 방지). 조회 전용이라 무료 등급도 허용(랭킹 열람의 연장)."""
    excl = [s for s in (exclude or "").split(",") if s.strip()]
    items = Store(DB_PATH).channel_history(username, exclude=excl)
    return {"ok": True, "username": username, "items": items, "count": len(items)}


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
def api_prune_remove(request: Request, username: str, name: str = ""):
    """죽은 채널 추적 제외(소프트 삭제 — 엑셀 원본 미변경, 복구 가능).
    랭킹 카드의 🚫 차단 버튼도 이 경로를 쓴다 → 전체 사용자에게 영향 가는 운영 액션이라 관리자만."""
    denied = _require_admin(request)
    if denied:
        return denied
    Store(DB_PATH).remove_channel(username.strip().lstrip("@"), name)
    return {"ok": True, "username": username}


@app.post("/api/prune/restore")
def api_prune_restore(request: Request, username: str):
    """추적 제외 해제(되돌리기). 차단 해제도 같은 경로 → 관리자만."""
    denied = _require_admin(request)
    if denied:
        return denied
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


def _download_item_video(item, work_dir):
    """수집 항목(item) → 영상 파일 경로. video_url이 없으면 릴스 페이지에서 받는다.

    2026-07-30부터 수집이 직접 mp4(video_versions)를 안 담는다 — 그걸 채우려고 릴스마다
    media info REST를 부르던 게 429의 주범이었다(instagram_playwright 주석 참고). 대신
    실제로 필요할 때(담기·대본추출) 릴스 페이지 URL로 한 건만 받는다. 옛 항목엔 아직
    video_url이 남아 있으므로 있으면 그대로 쓴다(빠르다).
    """
    url = (item.get("video_url") or "").strip()
    if url:
        return download_video(url, work_dir)
    page = (item.get("url") or "").strip()
    if not page and item.get("shortcode"):
        page = f"https://www.instagram.com/reel/{item['shortcode']}/"
    if not page:
        raise RuntimeError("영상 주소가 없습니다 — 재수집 필요")
    path, _caption = download_any(page, str(work_dir))
    return path


@app.post("/api/extract_script")
def api_extract_script(request: Request, shortcode: str):
    """카드 영상 1개 → 대본(세그먼트+전체텍스트) 온디맨드 추출. 캐시 우선.

    수집 때 전체를 뽑지 않고, 버튼 클릭한 영상만 다운로드→Gemini 추출→저장한다.
    한번 추출하면 캐시되어 재클릭은 즉시 반환. 인스타 CDN URL 만료 시 다운로드가
    실패할 수 있어(오래된 항목) 통째로 감싸 502로 안내한다.

    유료게이트(2026-07-19): Gemini 추출은 실제 비용 → 캐시미스에만 'script' 크레딧을 건다.
    캐시히트는 무료. 다운로드·추출이 실패하면 예약한 크레딧을 환불한다(성공 저장만 과금)."""
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
        return {"ok": True, "cached": True, **cached}     # 캐시히트 = 무료

    # ── 여기부터 실제 Gemini 비용 → 'script' 크레딧(캐시미스에만). ──
    cid = getattr(request.state, "customer_id", 0)
    if _global_over_cap("script"):
        return JSONResponse(status_code=429, content={
            "ok": False, "error_code": "global_limit",
            "error": "지금 대본 추출 이용이 많아요. 잠시 후 다시 시도해 주세요."})
    if not check_and_count(cid, "script"):
        return JSONResponse(status_code=429, content={
            "ok": False, "error_code": "daily_limit",
            "error": "오늘 대본 추출 횟수를 다 썼어요. 결제하면 더 쓸 수 있어요."})
    _denied = _charge_or_402(cid, pricing.OP_SCRIPT, keyroute.SVC_GEMINI)
    if _denied:
        return _denied
    global_incr_and_alert("script")
    ok = False
    try:
        # video_url이 비어 있으면 릴스 페이지에서 받는다(2026-07-30 — 수집이 더 이상
        # 직접 mp4를 담지 않는다, _download_item_video 주석 참고).
        # DB(수집분) 유래라 직접 입력은 아니지만, 오염된 수집물이 내부망을 찌르지 않게 같이 막는다.
        blocked = _ssrf_guard(*[u for u in (item.get("video_url"), item.get("url")) if u])
        if blocked:
            return blocked

        work_dir = _FIND_TMP_DIR / hashlib.sha1(code.encode()).hexdigest()[:16]
        try:
            video_path = _download_item_video(item, work_dir)
        except (requests.RequestException, RuntimeError) as e:
            msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
            return JSONResponse(status_code=502, content={"ok": False, "error": f"영상 다운로드 실패(URL 만료 가능) — 재수집 필요: {msg}"})
        except Exception as e:
            msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
            return JSONResponse(status_code=500, content={"ok": False, "error": msg})

        try:
            result = extract_auto(video_path, code, caption=item.get("caption", ""))
        except Exception as e:
            msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
            return JSONResponse(status_code=500, content={"ok": False, "error": msg})

        if not result.get("full_text") and not result.get("segments"):
            return JSONResponse(status_code=502, content={"ok": False, "error": "대본 추출 실패(Gemini 키 소진 또는 영상 인식 실패) — 잠시 후 재시도"})

        store.save_script(code, result, category=item.get("category"))
        ok = True
        return {"ok": True, "cached": False, **result}
    finally:
        if not ok:
            refund_credit(cid, "script")   # 실패·미달 → 크레딧 되돌림(전역 하드캡이 재시도 남용을 캡)
            _refund_points(cid, pricing.OP_SCRIPT, keyroute.SVC_GEMINI)


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
def api_produce_extract_from_url(request: Request, body: dict, background_tasks: BackgroundTasks):
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
    # ── 캐시미스 → 실제 Gemini 비용 → 'script' 크레딧. 실패 시 환불(성공 저장만 과금). ──
    cid = getattr(request.state, "customer_id", 0)
    if _global_over_cap("script"):
        return JSONResponse(status_code=429, content={
            "ok": False, "error_code": "global_limit",
            "error": "지금 대본 추출 이용이 많아요. 잠시 후 다시 시도해 주세요."})
    if not check_and_count(cid, "script"):
        return JSONResponse(status_code=429, content={
            "ok": False, "error_code": "daily_limit",
            "error": "오늘 대본 추출 횟수를 다 썼어요. 결제하면 더 쓸 수 있어요."})
    _denied = _charge_or_402(cid, pricing.OP_SCRIPT, keyroute.SVC_GEMINI)
    if _denied:
        return _denied
    global_incr_and_alert("script")
    ok = False
    try:
        work_dir = _FIND_TMP_DIR / hashlib.sha1(code.encode()).hexdigest()[:16]
        try:
            video_path, dl_caption = download_any(url, str(work_dir))
        except Exception as e:  # noqa: BLE001 — 다운로드 실패는 사용자에게 안내(치명 아님)
            msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
            return JSONResponse(status_code=502, content={
                "ok": False, "error": f"영상 다운로드 실패(URL 만료·비공개·프로필주소 가능): {msg}"})
        caption = (body.get("caption") or dl_caption or "")
        try:
            result = extract_auto(video_path, code, caption=caption)
        except KeyPoolExhausted:
            # 영상 문제가 아니라 서버 AI 키가 잠깐 다 찬 상태 — 사용자에게 그대로 알린다
            # (2026-08-07: 예전엔 "대본 추출 실패 — 잠시 후 재시도"로 뭉뚱그려져
            #  사장님이 영상을 의심하게 만들었다).
            return JSONResponse(status_code=503, content={
                "ok": False, "error": "AI 키가 일시적으로 모두 사용 중입니다 — "
                                      "잠시 후(또는 자정 이후) 다시 시도해 주세요."})
        except Exception as e:  # noqa: BLE001
            msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
            return JSONResponse(status_code=500, content={"ok": False, "error": msg})
        if not result.get("full_text") and not result.get("segments"):
            return JSONResponse(status_code=502, content={"ok": False, "error": "대본 추출 실패 — 잠시 후 재시도"})
        category = body_category or categorize(name, caption) or None
        store.save_script(code, result, category=category)
        ok = True    # 저장 성공 = 과금 확정. 아래 구조분석은 실패해도 응답·과금엔 영향 없음.
        structure = None
        try:
            structure = analyze_structure(result.get("full_text", "")) or None
        except Exception:  # noqa: BLE001 — 구조분석 실패해도 대본 응답은 성공시킨다
            structure = None
        if structure:
            store.save_extract_structure(code, structure)
        return {"ok": True, "cached": False, **result, "category": category, "structure": structure}
    finally:
        if not ok:
            refund_credit(cid, "script")
            _refund_points(cid, pricing.OP_SCRIPT, keyroute.SVC_GEMINI)


def _relearn_category(db_path, category):
    """위키 저장 직후 그 카테고리의 요소 카테고리를 즉시 재학습(백그라운드). 실패해도 무해."""
    if not category:
        return
    try:
        from shopping_shorts import daily_batch
        daily_batch.recompute_element_stats(Store(db_path), only_category=category)
    except Exception as e:  # noqa: BLE001 — 학습 실패는 저장 자체엔 영향 없음
        print(f"relearn 실패 {category}: {e}")


def _ingest_pattern_bank(db_path, full_text, url, category):
    """위키에 담을 때마다 그 대본의 훅·어미·부사·CTA를 부품은행에 자동 적재(계속 쌓기).
    스타일 부품은 즉시 자동승인 → 바로 생성에 반영(표현력↑). 백그라운드·실패 무해."""
    if not (full_text or "").strip():
        return
    try:
        store = Store(db_path)
        pattern_bank.ingest_script(store, full_text, source="wiki", url=url or "",
                                   product_category=category, category_source="user")
        store.auto_approve_style_buckets()
        store.auto_approve_content_buckets()   # 전개 템플릿(근거·갈등·감정)도 즉시 생성 반영(2026-07-23)
    except Exception as e:  # noqa: BLE001 — 은행 적재 실패는 위키 저장엔 영향 없음
        print(f"pattern_bank ingest 실패: {e}")


def _bank_ingest_collected_bg(db_path, items, collected_at):
    """'지금 수집' 후 백그라운드: 랭킹 상위 표본을 부품은행에 자동 분해·적재하고
    결과 리포트를 설정에 남긴다(수집 화면이 /api/bank/ingest_report로 읽어 보고).
    소스당 Gemini 1콜이라 요청을 막지 않게 백그라운드로 돈다. 실패 무해."""
    import json as _json
    from datetime import datetime as _dt, timezone as _tz
    try:
        store = Store(db_path)
    except Exception as e:  # noqa: BLE001
        print(f"bank ingest(store) 실패: {e}")
        return
    day = (collected_at or "")[:10] or _dt.now(_tz.utc).strftime("%Y-%m-%d")
    store.set_setting("bank_ingest_last", _json.dumps(
        {"status": "running", "date": day, "collected_at": collected_at}, ensure_ascii=False))
    try:
        rep = pattern_bank.ingest_collected(store, items)
        # 훅수확 이관(2026-07-23): 밤4시 크론이 아니라 수집 버튼이 우승작 훅을 즉시 수확한다.
        try:
            from shopping_shorts import daily_batch
            rep["harvested_hooks"] = daily_batch.harvest_hooks(store)
        except Exception as he:  # noqa: BLE001
            print(f"bank ingest(harvest_hooks) 실패: {he}")
            rep["harvested_hooks"] = 0
        store.auto_approve_style_buckets()   # 스타일 부품 즉시 사용가능(위키 적재와 동일)
        store.auto_approve_content_buckets()   # 전개 템플릿(근거·갈등·감정)도 즉시 생성 반영(2026-07-23)
        rep.update({"status": "done", "date": day, "collected_at": collected_at})
        store.set_setting("bank_ingest_last", _json.dumps(rep, ensure_ascii=False))
        # 검열은 따로도 저장(패널이 흡수리포트와 분리해 읽기 쉽게).
        audit = rep.get("gemini_audit")
        if audit is not None:
            store.set_setting("gemini_audit_last", _json.dumps(
                {**audit, "date": day, "collected_at": collected_at}, ensure_ascii=False))
    except Exception as e:  # noqa: BLE001
        print(f"bank ingest(collected) 실패: {e}")
        store.set_setting("bank_ingest_last", _json.dumps(
            {"status": "error", "date": day, "error": str(e)}, ensure_ascii=False))


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
        try:
            video_path = _download_item_video(item, work_dir)
        except (requests.RequestException, RuntimeError) as e:
            msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
            return JSONResponse(status_code=502, content={"ok": False, "error": f"영상 다운로드 실패(URL 만료 가능): {msg}"})
        script = extract_auto(video_path, code, caption=item.get("caption", ""))
        if not script.get("full_text") and not script.get("segments"):
            return JSONResponse(status_code=502, content={"ok": False, "error": "대본 추출 실패 — 잠시 후 재시도"})
        store.save_script(code, script, category=item.get("category"))

    # 원본 영상 영구보관(도서관 인라인 재생용) — 만료되는 CDN URL 대신 파일로 남긴다.
    media_target = _WIKI_MEDIA_DIR / f"{hashed}.mp4"
    if not media_target.exists():
        src = video_path
        if src is None:
            try:
                src = _download_item_video(item, work_dir)
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
    # 부품은행 자동 적재(훅·어미·부사·CTA 계속 쌓기 + 스타일 자동승인 → 표현력↑).
    background_tasks.add_task(_ingest_pattern_bank, DB_PATH, script.get("full_text", ""),
                             item.get("video_url", ""), item.get("category"))
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
            result = extract_auto(video_path, code, caption=caption)
        except KeyPoolExhausted:
            # 영상 문제가 아니라 서버 AI 키가 잠깐 다 찬 상태 — 사용자에게 그대로 알린다
            # (2026-08-07: 예전엔 "대본 추출 실패 — 잠시 후 재시도"로 뭉뚱그려져
            #  사장님이 영상을 의심하게 만들었다).
            return JSONResponse(status_code=503, content={
                "ok": False, "error": "AI 키가 일시적으로 모두 사용 중입니다 — "
                                      "잠시 후(또는 자정 이후) 다시 시도해 주세요."})
        except Exception as e:  # noqa: BLE001
            msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
            return JSONResponse(status_code=500, content={"ok": False, "error": msg})
        if not result.get("full_text") and not result.get("segments"):
            return JSONResponse(status_code=502, content={"ok": False, "error": "대본 추출 실패 — 잠시 후 재시도"})
        category = body_category or None
        script = storable(result)   # 손으로 추리면 tag_qa가 저장에서 샌다(2026-08-01)
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
    # 부품은행 주입 — 승인된 스파인·부품(훅·어미·부사·CTA)을 프롬프트에 실어 표현력↑.
    # 마스터 스위치(ping_pong_enabled)가 켜져 있으면 자동 주입(위키담기로 쌓인 걸 바로 활용).
    _gen_kw = dict(mode=mode, my_topic=my_topic, subject=subject, n=n)
    _use_bank = body.get("use_bank") or (store.get_setting("ping_pong_enabled", "") == "1")
    _bank_ctx = ""
    if _use_bank:
        _bank = bank_assemble.assemble_bank_context(store, it.get("category") or "")
        if _bank:
            _gen_kw["bank_context"] = _bank
            _bank_ctx = _bank
    # ★스타일 강제 경로(2026-08-15) — style_ids가 오면 스타일마다 1안씩 만들고 script_gate로
    #   구조를 대조한다. 안 오면 기존 경로 그대로라 회귀 0(호출부가 안 보내면 아무 일도 없다).
    #   기존 경로와 다른 점: 같은 프롬프트를 n번 굴리는 게 아니라 **스타일마다 프롬프트가 갈려**
    #   서로 다른 구조가 보장되고, 어긴 결과는 재작성이 걸린다.
    _style_ids = [int(x) for x in (body.get("style_ids") or []) if str(x).isdigit()]
    # ★'AI에게 맡김'도 스타일 경로를 탄다(2026-08-17 사장님 제보 "AI로 뽑으면 이모티콘 없어짐").
    #   스타일을 안 고르면 옛 생성기로 가는데, 그 경로는 **칸(beats)을 안 준다** → 화면이
    #   어느 줄이 훅인지 몰라 역할 라벨이 빈다. 그러면 이 화면의 존재 이유가 통째로 죽는다.
    #   "맡긴다"는 **고르기 귀찮다**는 뜻이지 품질을 포기한다는 뜻이 아니다 —
    #   추천 순서(검증 먼저, 그다음 실적순 = list_style_spines 정렬) 상위에서 자동으로 집는다.
    #   ⚠️ auto_style을 보내는 호출부에서만 동작한다(도서관 pmRunGen 등 기존 경로는 회귀 0).
    if not _style_ids and body.get("auto_style"):
        try:
            _n_auto = max(1, min(int(body.get("n") or 2), 2))
        except (TypeError, ValueError):
            _n_auto = 2
        _auto = store.list_style_spines(category=it.get("category") or None) \
            or store.list_style_spines(category=None)
        _style_ids = [s["id"] for s in _auto[:_n_auto]]
    if _style_ids:
        # ★카테고리로 거르지 않는다(2026-08-17 사장님 제보로 수정).
        #   화면 방침은 2026-08-15에 **잠금 해제 → 등급 표시**(✅검증/⚠️타소재)로 바뀌어
        #   타소재도 고를 수 있게 보여주는데, 여기만 옛 잠금이 남아 **고른 스타일이 조용히
        #   사라졌다** — 사장님이 2개를 골랐는데 1안만 나왔다(실측: ⚠️타소재 2개가 버려지고
        #   ✅검증 1개만 생성). 같은 판단이 화면과 서버 두 곳에 다르게 적혀 있던 것(0순위-B).
        #   경고는 화면이 이미 했다. 고른 건 그대로 존중한다.
        _by_id = {s["id"]: s for s in store.list_style_spines(category=None)}
        _picked = [_by_id[i] for i in _style_ids if i in _by_id]
        if not _picked:
            return JSONResponse(status_code=422, content={
                "ok": False, "error": "고른 스타일을 쓸 수 없음(승인·구조·카테고리 확인)"})
        # ★재료를 **담긴 영상 전부**로 넓힌다(2026-08-17 사장님 지시).
        #   여기는 원래 `[{...}]` 하나뿐이었는데 바로 아래 `_mix_source_block`은 `sources[:3]`
        #   으로 3편까지 받게 돼 있었다 — **3개 그릇에 1개만 넣고 있었다.**
        #   그래서 "어느 대본을 씨앗으로 골랐냐"가 결과를 좌우했다(사장님: "하나의 대본을
        #   지정하면 편협하게 나온다 / 사용자는 뭐가 좋은 대본인지 모르고 잘못 고르면 낭패").
        #   담긴 것을 전부 넣으면 그 복불복 자체가 사라진다.
        # 재료 조립은 `_materials_for_generate`가 한 곳에서 정한다(0순위-B) —
        # [바꾸기] 부분 재생성(/api/script/beat/regen)도 **같은 함수**를 쓴다.
        _src, _facts_block, _job, _jid, _scene_block = _materials_for_generate(
            it, body, store, _cid(request))
        _styled = script_generate.generate_by_styles(
            _src, _picked, target_seconds=body.get("target_seconds") or 30,
            bank_context=_bank_ctx, facts_block=_facts_block)
        if not _styled:
            return JSONResponse(status_code=502, content={
                "ok": False, "error": "생성 실패(키 소진 또는 응답 오류) — 잠시 후 재시도"})
        _cid_ = _cid(request)
        for dr in _styled:
            did = uuid.uuid4().hex[:12]
            store.save_draft(did, _cid_, shortcode, None, dr.get("hook", ""),
                             dr.get("script", ""), None, "style")
            dr["draft_id"] = did
            store.record_script_usage(hook=dr.get("hook", ""), spine_id=dr.get("style_id"))
        # ★무엇을 재료로 썼는지 화면에 돌려준다(2026-08-17 사장님 제보 "대본이 무슨
        #   영상인지 모르겠다"). 재료가 어긋나도 화면이 말을 안 하면 아무도 모른다 —
        #   대본만 보고는 "어느 영상에서 나온 건지" 판별할 방법이 없다.
        return {"ok": True, "drafts": _styled, "mode": "style",
                "materials": {
                    "sources": [{"chars": len(s.get("full_text") or ""),
                                 "head": (s.get("full_text") or "")[:40]} for s in _src],
                    "scene_points": _scene_block.count("\n· ") if _scene_block else 0,
                    "product_facts": bool(_facts_block_for_job(_jid, store)),
                    "styles": [s.get("name") for s in _picked],
                }}
    drafts = script_generate.generate_variations(
        it.get("structure") or {}, it.get("full_text") or "", elem_modes, category_lookup, **_gen_kw)
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


@app.post("/api/wiki/draft/upgrade")
def api_draft_upgrade(request: Request, body: dict):
    """초안을 '요소 단위'로 업그레이드 — 고른 요소만 변형, 나머지 유지해 재생성.

    body: {draft_id, elements: [element_key, ...]}. element_key는 ELEM_KEYS 중 하나.
    초안을 analyze_structure로 요소 분해 → 고른 요소만 free(변형) → generate_variations(n=1)
    → 새 버전으로 저장(parent=draft_id, mode="upgrade")."""
    store = Store(DB_PATH)
    draft_id = body.get("draft_id", "")
    elements = [e for e in (body.get("elements") or []) if e in script_generate.ELEM_KEYS]
    cur = store.get_draft(draft_id)
    if not cur:
        return JSONResponse(status_code=404, content={"ok": False, "error": "해당 초안 없음"})
    if not elements:
        return JSONResponse(status_code=422, content={"ok": False, "error": "바꿀 요소를 하나 이상 고르세요"})
    base = cur.get("script_text") or ""
    structure = analyze_structure(base) or {}
    category_lookup = store.get_element_options(structure.get("product_category") or "")
    elem_modes = {e: "free" for e in elements}
    drafts = script_generate.generate_variations(
        structure, base, elem_modes, category_lookup, mode="remake", subject="", n=1)
    if not drafts:
        return JSONResponse(status_code=502, content={"ok": False, "error": "재생성 실패(Gemini 키 소진 또는 오류) — 잠시 후 재시도"})
    dr = drafts[0]
    new_id = uuid.uuid4().hex[:12]
    labels = ", ".join(script_generate.ELEM_LABELS[e] for e in elements)
    store.save_draft(new_id, _cid(request), cur.get("source_shortcode"), draft_id,
                      dr.get("hook", ""), dr.get("script", ""), "요소변형: " + labels, "upgrade")
    return {"ok": True, "draft_id": new_id, "script_text": dr.get("script", ""), "hook": dr.get("hook", "")}


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
def api_mix_start(request: Request, background_tasks: BackgroundTasks, body: dict):
    """믹스 job 시작. body: {urls, target_seconds, structure, subtitle_removal}."""
    urls = [u for u in (body.get("urls") or []) if u]
    if len(urls) < 2:
        return JSONResponse(status_code=422, content={"ok": False, "error": "레퍼런스 URL 2개 이상 필요"})
    # 유료게이트: 렌더는 최고비용(VMake 크레딧). ★검증(SSRF·파싱)을 먼저 통과시킨 뒤 과금한다 —
    # 잘못된 요청에 크레딧을 태우면 무료 유저의 하루 2회가 헛되이 날아가고 환불 경로도 없다(리뷰 G1).
    blocked = _ssrf_guard(*urls)      # 이 URL들은 run_mix_job이 그대로 다운로드한다
    if blocked:
        return blocked
    target = int(body.get("target_seconds") or 30)
    structure = body.get("structure") if body.get("structure") in ("template", "free") else "template"
    subtitle_removal = bool(body.get("subtitle_removal", False))
    scene_first = bool(body.get("scene_first", False))
    cid = getattr(request.state, "customer_id", 0)
    if _global_over_cap("render"):
        return JSONResponse(status_code=429, content={
            "ok": False, "error_code": "global_limit",
            "error": "지금 영상 만들기 이용이 많아요. 잠시 후 다시 시도해 주세요."})
    if not check_and_count(cid, "render"):
        return JSONResponse(status_code=429, content={
            "ok": False, "error_code": "daily_limit",
            "error": "오늘 영상 만들기 횟수를 다 썼어요. 결제하면 더 만들 수 있어요."})
    _denied = _charge_or_402(cid, pricing.OP_MIX, keyroute.SVC_GEMINI)
    if _denied:
        return _denied
    global_incr_and_alert("render")
    job_id = uuid.uuid4().hex[:12]
    # render_charge_day: '오늘 render를 과금했다'는 표식(+환불할 날짜). run_mix_job이 실패하면 딱
    # 이 날짜로 환불한다. 과금 안 하는 다른 create_mix_job 경로는 이 값을 비워 오환불을 막는다(리뷰 B).
    Store(DB_PATH).create_mix_job(job_id, urls, target, structure, subtitle_removal=subtitle_removal,
                                  customer_id=cid,
                                  render_charge_day=("trial" if _is_trial(cid) else _today_utc()),
                                  scene_first=scene_first)
    Store(DB_PATH).enqueue("mix", {"job_id": job_id})
    return {"ok": True, "job_id": job_id}


@app.post("/api/mix/candidate")
def api_mix_candidate(body: dict):
    """장면 우선 대본 모드(2026-07-20, Task6): 후보 선택 — 고른 후보의 plan을 edit_plan으로
    세팅한다(미리보기/렌더가 이걸 읽는다).

    narrations(2026-08-10, 선택): 카드에서 사장님이 **직접 고쳐 쓴** 문장 배열. 있으면 그
    후보 plan의 beats[].narration에 덮어쓴다. 안 보내면(=편집 안 함) 종전과 100% 동일.

    ★길이가 beats와 다르면 통째로 무시한다. 화면 배정(beats[].covers)은 문장 개수·순서에
      묶여 있어서 문장이 늘거나 줄면 컷 매핑이 어긋난다 — 프론트가 칸을 문장 수만큼 고정해
      두지만 서버도 스스로 지킨다(클라 신뢰 금지).
    ★빈 문자열은 그 문장을 건너뛴다(원문 유지) — 실수로 칸을 비운 채 고르면 그 비트의 TTS가
      무음이 되고 렌더가 죽는다.
    ★TTS 재합성은 저절로 된다: 렌더 경로가 나레이션 **내용 해시**로 mp3 경로를 만들므로
      (mix_pipeline._beat_tts_path) 글자가 바뀌면 tts_path가 안 맞아 그 비트만 다시 합성된다.
      그래서 여기선 tts_path를 지울 필요도, 별도 재합성을 부를 필요도 없다.
    """
    job_id = (body.get("job_id") or "").strip()
    idx = int(body.get("index") or 0)
    store = Store(DB_PATH)
    cands = store.get_mix_candidates(job_id)
    if not cands or not (0 <= idx < len(cands)):
        return JSONResponse(status_code=404, content={"ok": False, "error": "후보 없음"})
    plan = cands[idx]["plan"]
    beats = plan.get("beats") or []
    narrations = body.get("narrations")
    edited = False
    if isinstance(narrations, list) and len(narrations) == len(beats) and beats:
        for b, n in zip(beats, narrations):
            if not isinstance(n, str):
                continue
            n = n.strip()
            if not n or n == (b.get("narration") or "").strip():
                continue
            b["narration"] = n
            # ★대본이 바뀌면 옛 자막 메타를 반드시 버린다(2026-08-15). 안 지우면 렌더가
            #   옛 대본 기준 caption_lines·cap_durs·cap_lead로 자막을 그려 음성과 어긋난다
            #   (실사고 409f894230c6: 구절 수 전 칸 불일치 + 낡은 lead → 자막이 mp3보다 늦게 끝남).
            mix_pipeline.invalidate_caption_meta(b)
            edited = True
    # ★고친 대본을 **후보 목록에도** 되쓴다(2026-08-10). 안 하면 다른 후보를 눌렀다 돌아오는
    #   순간 이 endpoint가 DB의 원본 plan을 다시 꽂아 편집이 조용히 날아간다(같은 이유로
    #   새로고침 복원·카드 재렌더도 원문으로 되돌아간다).
    if edited:
        store.set_mix_candidates(job_id, cands)
    # ★고른 후보를 plan에 새긴다(2026-07-30 사장님 "완료 갔다 오면 대본이 리셋된다").
    #   후보 자체는 job_id별로 DB에 남아 있는데(set_mix_candidates), 복원 경로가 "지금 무엇을
    #   골랐나"를 알 길이 없어 카드를 다시 그릴 수 없었다. 컬럼 추가 없이 edit_plan(JSON)에
    #   실어 마이그레이션 없이 복원한다 — 렌더는 이 키를 안 읽으므로 무해.
    plan["candidate_index"] = idx
    store.update_mix_job(job_id, edit_plan=plan)
    return {"ok": True, "edited": edited}


def _clone_mix_work_sources(src_job, new_job, n_urls):
    """복제본 work 폴더에 **소스 mp4만** 옮겨 붙인다(2026-07-30).

    _resolve_sources(mix_pipeline)는 work/{sN}/*.mp4를 **찾기만** 하고 없으면 다운로드하지
    않는다 — 그래서 복제본에 소스를 안 깔면 '소스 영상을 하나도 찾지 못했습니다'로 죽는다.
    소스는 읽기 전용 입력이라 하드링크면 충분하다(디스크 0바이트). 같은 볼륨이 아니거나
    OS가 거부하면 복사로 내려간다.

    ⚠️ tts/preview/final/seg_thumbs는 **일부러 안 가져온다** — 복제본은 다른 대본으로 새로
    만드는 것이라 그 산출물이 섞이면 옛 영상이 새 작업의 결과처럼 보인다(덮어쓰기 사고의 재료).
    """
    src_dir, dst_dir = _MIX_WORK_DIR / src_job, _MIX_WORK_DIR / new_job
    copied = 0
    for i in range(n_urls):
        vid = f"s{i}"
        s = src_dir / vid
        if not s.is_dir():
            continue
        (dst_dir / vid).mkdir(parents=True, exist_ok=True)
        for mp4 in s.glob("*.mp4"):
            target = dst_dir / vid / mp4.name
            if target.exists():
                continue
            try:
                os.link(str(mp4), str(target))       # 하드링크(같은 볼륨) — 디스크 안 먹는다
            except OSError:
                shutil.copy2(str(mp4), str(target))  # 다른 볼륨·미지원 FS면 복사
            copied += 1
    return copied


@app.post("/api/mix/candidate/clone")
def api_mix_candidate_clone(request: Request, body: dict):
    """고른 후보를 **별도 작업으로 복제**한다 — 대본 3개를 3편으로 다 뽑기 위한 경로.

    사장님 요청(2026-07-30): "이 화면에 대본이 3개인데 3개 다 만들고 싶다".
    같은 job에서 후보만 바꿔 렌더하면 출력이 work/{job_id}/final.mp4 **고정 경로**라
    (mix_pipeline.run_render) 다음 렌더가 앞 영상을 덮어쓴다. 그래서 후보별로 job을 갈라
    각자 자기 final.mp4를 갖게 한다.

    재매칭(/api/produce/mix/start)과 다른 점: 대본을 **다시 생성하지 않는다**. 지금 화면의
    A/B/C를 그대로 물려주므로 사장님이 고른 그 문장이 그대로 영상이 된다.
    """
    job_id = (body.get("job_id") or "").strip()
    try:
        idx = int(body.get("index"))
    except (TypeError, ValueError):
        return JSONResponse(status_code=422, content={"ok": False, "error": "후보 번호가 필요합니다"})
    store = Store(DB_PATH)
    src = store.get_mix_job(job_id)
    if not src:
        return JSONResponse(status_code=404, content={"ok": False, "error": "job 없음"})
    cands = store.get_mix_candidates(job_id)
    if not cands or not (0 <= idx < len(cands)):
        return JSONResponse(status_code=404, content={"ok": False, "error": "후보 없음"})
    # 유료게이트(2026-07-20 E와 동일): 복제본도 결국 렌더로 돈이 나간다. 여기서 안 걸면
    # "후보 복제"가 하루 상한·전역 상한을 통째로 우회하는 뒷문이 된다.
    cid = getattr(request.state, "customer_id", 0)
    if _global_over_cap("render"):
        return JSONResponse(status_code=429, content={
            "ok": False, "error_code": "global_limit",
            "error": "지금 영상 만들기 이용이 많아요. 잠시 후 다시 시도해 주세요."})
    if not check_and_count(cid, "render"):
        return JSONResponse(status_code=429, content={
            "ok": False, "error_code": "daily_limit",
            "error": "오늘 영상 만들기 횟수를 다 썼어요. 결제하면 더 만들 수 있어요."})
    _denied = _charge_or_402(cid, pricing.OP_MIX, keyroute.SVC_GEMINI)
    if _denied:
        return _denied
    global_incr_and_alert("render")
    urls = src.get("urls") or []
    new_id = uuid.uuid4().hex[:12]
    store.create_mix_job(new_id, urls, src.get("target_seconds") or 30,
                         src.get("structure") or "free",
                         subtitle_removal=bool(src.get("subtitle_removal")),
                         given_script=src.get("given_script"),
                         script_structure=src.get("script_structure"),
                         customer_id=cid,
                         render_charge_day=("trial" if _is_trial(cid) else _today_utc()),
                         scene_first=bool(src.get("scene_first")),
                         backbone_main=src.get("backbone_main"))
    _clone_mix_work_sources(job_id, new_id, len(urls))
    # 후보 목록을 그대로 물려준다 — 복제본에서도 A/B/C를 비교·전환할 수 있다(또 복제도 가능).
    store.set_mix_candidates(new_id, cands)
    plan = cands[idx]["plan"]
    plan["candidate_index"] = idx
    # status는 'ready_for_review' — 매칭(run_mix_job)을 다시 돌리지 않는다. 대본·컷이 이미
    # 정해져 있으므로 큐에 넣지 않고 바로 리뷰/미리보기/렌더로 갈 수 있는 상태로 만든다.
    # ★extract도 물려준다(2026-08-03): 안 주면 복제본이 원본 분석 없이 시작해 쿠팡
    #   "화면으로 정확히" 등 extract를 읽는 후속 기능이 빈손이 된다(실측 job 6c649edecdd8).
    store.update_mix_job(new_id, edit_plan=plan, status="ready_for_review",
                         extract=src.get("extract"),
                         voice=src.get("voice"), deco=src.get("deco"))
    return {"ok": True, "job_id": new_id}


@app.post("/api/settings/vmake_key")
def api_set_vmake_key(body: dict):
    key = (body.get("key") or "").strip()
    Store(DB_PATH).set_setting("vmake_api_key", key)
    return {"ok": True}


@app.get("/api/settings/vmake_key")
def api_get_vmake_key():
    key = Store(DB_PATH).get_setting("vmake_api_key", "")
    return {"ok": True, "configured": bool(key)}      # 원문은 노출하지 않음


# ─────────────────────────────────────────────────────────────────────
# BYOK — 사용자가 자기 API 키를 등록하면 포인트를 안 깎는다 (2026-08-17)
#
# ★위 /api/settings/vmake_key 와 헷갈리지 마라. 저건 **사장님 전역 키**(회사 부담)이고
#   아래는 **고객별 키**다. 둘 다 살아있어야 한다 — keyroute.keys_for가 사용자 키가
#   없을 때 전역 키로 내려간다(keyroute._owner_vmake_key).
#
# ★평문은 GET으로 절대 안 나간다. list_customer_keys가 key_enc를 아예 안 싣고,
#   평문 경로는 keyroute.keys_for(→get_customer_keys_plain) 하나뿐이다.
# ─────────────────────────────────────────────────────────────────────

def _probe_user_key(service: str, key: str) -> bool:
    """등록된 키가 실제로 도는가. 판정만 하고 예외를 밖으로 안 흘린다.

    ★gemini는 comment_gen._probe_key_alive(REST)를 그대로 쓴다 — SDK models.list는
      살아있는 키도 전부 실패로 만든다(2026-08-07 실측, comment_gen.py:95 주석).
      같은 판단을 여기 또 적으면 어긋난다(CLAUDE.md 0순위-B).
    ★vmake는 형식만 본다. 실호출이 크레딧을 먹으므로 '확인' 버튼이 돈을 쓰면 안 된다.
    """
    if service == keyroute.SVC_GEMINI:
        from shopping_shorts.comment_gen import _probe_key_alive
        return _probe_key_alive(key)
    if service == keyroute.SVC_VMAKE:
        return ":" in key           # ak:sk 형식. 실호출 안 함(크레딧 소모)
    if service == keyroute.SVC_ELEVENLABS:
        url, kw = "https://api.elevenlabs.io/v1/user", {"headers": {"xi-api-key": key}}
    elif service == keyroute.SVC_YOUTUBE:
        url = ("https://www.googleapis.com/youtube/v3/videos"
               f"?part=id&id=dQw4w9WgXcQ&key={urllib.parse.quote(key)}")
        kw = {}
    elif service == keyroute.SVC_SERPAPI:
        # ★계정 정보 조회(account.json)로 확인한다 — 검색을 실제로 돌리면 '확인'
        #   버튼 한 번이 월 250회 무료분을 깎는다. 이 엔드포인트는 검색이 아니다.
        url = f"https://serpapi.com/account.json?api_key={urllib.parse.quote(key)}"
        kw = {}
    else:
        raise ValueError(f"모르는 service: {service!r}")
    try:
        return requests.get(url, timeout=10, **kw).status_code == 200
    except requests.RequestException:
        # ★네트워크 실패는 '검증 실패'라는 판정이지 버그 은폐가 아니다.
        #   requests 예외만 잡는다 — 코드 오류(TypeError 등)까지 삼키면 원인을 못 찾는다.
        return False


def _key_status(service: str, key: str) -> str:
    """화면에 박을 상태 문자열: ok / empty / bad. **여기서만 정한다**(0순위-B).

    ★왜 empty가 필요한가 (2026-08-17 라이브 실측):
      SerpApi 키가 이번 달 250회를 다 쓴 상태(plan_searches_left=0)여도
      account.json은 200을 준다 → '● 정상'으로 떴다. 그런데 검색을 걸면
      첫 호출에서 소진 판정이 나 **0건**이 돌아온다. 폴백이 없으니(설계상
      의도) 사장님 키로도 안 넘어간다 = "정상이라며 왜 결과가 없냐"가 된다.
      키는 멀쩡하므로 'bad'(키가 틀렸습니다)도 거짓이다. 그래서 셋으로 가른다.

    잔량 조회가 실패하면 ok로 둔다 — 확인 못 한 것을 소진으로 단정하지 않는다."""
    if not _probe_user_key(service, key):
        return "bad"
    if service == keyroute.SVC_SERPAPI:
        try:
            d = requests.get("https://serpapi.com/account.json",
                             params={"api_key": key}, timeout=10).json()
            left = d.get("total_searches_left", d.get("plan_searches_left"))
            if left is not None and int(left) <= 0:
                return "empty"
        except (requests.RequestException, ValueError, TypeError):
            pass
    return "ok"


def _svc_or_err(body: dict):
    """(service, 에러응답) — 모르는 값이면 (None, 422 응답).

    ★그냥 받으면 customer_keys에 영영 안 쓰이는 쓰레기 행이 쌓인다.
    ★이 파일은 HTTPException을 안 쓴다(app.py:4486 주석) — JSONResponse로 맞춘다."""
    service = (body.get("service") or "").strip()
    if service not in keyroute.SERVICES:
        return None, JSONResponse(status_code=422, content={
            "ok": False, "error": f"모르는 서비스입니다 (가능: {', '.join(keyroute.SERVICES)})"})
    return service, None


@app.get("/api/settings/keys")
def api_list_keys(request: Request):
    """등록된 키 목록. ★label(마스킹)만 나가고 평문·암호문은 안 나간다."""
    store = Store(DB_PATH)
    cid = keyroute.as_cid(_cid(request))
    return {"ok": True, "enabled": keycrypt.enabled(),
            "keys": store.list_customer_keys(cid)}


@app.post("/api/settings/keys")
def api_add_keys(request: Request, body: dict):
    """키 등록. gemini만 여러 개를 한 번에 받는다.

    ★gemini 외에는 쪼개지 않는다 — vmake는 'ak:sk' 한 덩어리라 구분자로 자르면
      반쪽짜리 키 두 개가 저장되고, 화면엔 등록된 것처럼 보이는데 실제로는 안 된다."""
    if not keycrypt.enabled():
        # 평문 저장으로 조용히 폴백하지 않는다(keycrypt.py 주석과 같은 원칙).
        return JSONResponse(status_code=503, content={
            "ok": False, "error": "키 저장이 설정되지 않았습니다 (관리자 문의)"})
    service, err = _svc_or_err(body)
    if err:
        return err
    raw = (body.get("key") or "").strip()
    if not raw:
        return JSONResponse(status_code=422,
                            content={"ok": False, "error": "키를 입력하세요"})

    if service == keyroute.SVC_GEMINI:
        parts = [p.strip() for p in re.split(r"[\s,]+", raw) if p.strip()]
    else:
        parts = [raw]

    store = Store(DB_PATH)
    cid = keyroute.as_cid(_cid(request))
    added = sum(1 for p in parts if store.add_customer_key(cid, service, p))
    return {"ok": True, "added": added, "keys": store.list_customer_keys(cid)}


@app.post("/api/settings/keys/delete")
def api_delete_key(request: Request, body: dict):
    store = Store(DB_PATH)
    cid = keyroute.as_cid(_cid(request))
    # store가 customer_id를 DELETE 조건에 넣는다 → id만 알아도 남의 키는 못 지운다.
    store.delete_customer_key(cid, int(body.get("id") or 0))
    return {"ok": True, "keys": store.list_customer_keys(cid)}


@app.post("/api/settings/keys/verify")
def api_verify_keys(request: Request, body: dict):
    """등록한 키가 실제로 도는지 확인하고 status를 박는다.

    ★keyroute.keys_for로 가져온다 — '어떤 키를 쓰는가'의 판단처가 하나여야
      "확인은 통과했는데 정작 다른 키로 돈다"가 안 생긴다."""
    service, err = _svc_or_err(body)
    if err:
        return err
    store = Store(DB_PATH)
    cid = keyroute.as_cid(_cid(request))
    # 키 목록 자체는 아래에서 id와 짝으로 다시 받는다 — 여기선 '내 키인가'만 본다.
    _keys, is_user = keyroute.keys_for(store, cid, service)
    if not is_user:
        # 사장님 키는 고객이 검증할 대상이 아니다(남의 키 상태를 알려줄 이유도 없다).
        return {"ok": True, "results": [], "keys": store.list_customer_keys(cid)}

    # ★id와 평문을 짝으로 받는다 — 화면 목록과 zip으로 맞추면 복호 실패한 행이
    #   평문 쪽에서만 빠져 순서가 밀리고 **엉뚱한 키에 상태가 박힌다**(0순위-B).
    labels = {r["id"]: r["label"] for r in store.list_customer_keys(cid, service)}
    results = []
    for key_id, plain in store.get_customer_keys_with_id(cid, service):
        status = _key_status(service, plain)
        store.set_customer_key_status(key_id, status)
        # ★평문은 안 싣는다. 화면은 label로 어느 키인지 알아본다.
        # ok는 "쓸 수 있는가" — 무료분이 바닥난 키(empty)는 검색이 0건이라 False다.
        results.append({"id": key_id, "label": labels.get(key_id, ""),
                        "ok": status == "ok", "status": status})
    return {"ok": True, "results": results, "keys": store.list_customer_keys(cid)}


@app.get("/api/settings/points")
def api_points(request: Request):
    """잔액·단가표·최근 사용내역. ★전부 화면용 단위로 바꿔서 내보낸다 —
    내부값(포인트×100)을 그대로 주면 5P가 500으로 보인다."""
    store = Store(DB_PATH)
    cid = keyroute.as_cid(_cid(request))
    ops = (pricing.OP_VMAKE, pricing.OP_MIX, pricing.OP_TTS,
           pricing.OP_LENS, pricing.OP_SCRIPT)
    history = [{**h, "delta": pricing.to_display(h["delta"])}
               for h in store.points_history(cid, 20)]
    return {"ok": True,
            "balance": pricing.to_display(points.balance(store, cid)),
            "prices": {op: pricing.to_display(pricing.cost(store, op)) for op in ops},
            "history": history}


@app.get("/api/settings/smart_mix")
def api_get_smart_mix():
    """스마트 믹스(부품은행+반복회피+핑퐁) 마스터 스위치 상태. bank_enabled로 대표."""
    return {"ok": True, "on": Store(DB_PATH).get_setting("bank_enabled", "") == "1"}


@app.post("/api/settings/smart_mix")
def api_set_smart_mix(body: dict):
    """딸깍 하나로 부품은행 주입(bank_enabled)·반복회피(novelty)·핑퐁(ping_pong_enabled)·
    백본-베이스(backbone_base_enabled, 백본 흐름 위 100% 우리 대본)를 함께 켜고 끈다.
    전부 scene_first 믹스에서만 작동하고 기본 off라 켜기 전엔 라이브 무변화."""
    val = "1" if body.get("on") else "0"
    store = Store(DB_PATH)
    store.set_setting("bank_enabled", val)
    store.set_setting("ping_pong_enabled", val)
    store.set_setting("backbone_base_enabled", val)
    return {"ok": True, "on": val == "1"}


# 매칭 파이프라인의 '진행 중' 단계들(run_mix_job: downloading→extracting→planning→tts).
# 각 단계가 update_mix_job으로 updated_at을 갱신하므로, 여기 오래 멈춰 있으면 죽은 잔해다.
_MIX_ACTIVE_STAGES = ("downloading", "extracting", "planning", "tts")


# 내부 사정이 드러나는 조각들 → 일반 사용자용 문장으로 갈아끼운다(관리자는 원문을 본다).
# "무엇이 막혔고 사용자가 뭘 하면 되는지"만 남긴다. 벤더명·토큰수·경로·스택은 전부 감춘다.
_USER_ERROR_RULES = (
    (("apify", "instagram", "인스타", "다운로드 실패", "영상을 받지"),
     "영상을 가져오지 못했습니다. 원본이 비공개·삭제되었거나 일시적인 문제일 수 있어요. "
     "잠시 후 다시 시도해 주세요. (계속되면 관리자에게 알려주세요)"),
    (("gemini", "키 소진", "edl 비어", "quota", "permission_denied", "api key"),
     "대본을 만드는 데 실패했습니다. 잠시 후 다시 시도해 주세요. "
     "(계속되면 관리자에게 알려주세요)"),
    (("서버 재시작", "중단되었습니다"),
     "작업이 중단되었습니다. 다시 시도해 주세요."),
)


def _user_facing_error(msg):
    """실패 사유를 일반 사용자에게 보여줄 문장으로 바꾼다. 관리자에겐 쓰지 않는다."""
    low = (msg or "").lower()
    for keys, friendly in _USER_ERROR_RULES:
        if any(k in low for k in keys):
            return friendly
    return "처리 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."


def _script_hash(text):
    """대본의 지문 — "이 job이 지금 화면의 대본으로 만들어진 것인가"만 판별한다.

    ★프론트(produce.html `_scriptHash`)와 **같은 규칙이어야 한다**(0순위-B: 짝으로
      움직이는 값). 규칙이 어긋나면 항상 '바뀐 것'으로 보여 매칭이 무한 재실행되고,
      매칭은 과금(render 1회 차감)이라 그대로 요금이 된다.
    규칙: 앞뒤 공백 제거 + 줄바꿈 정규화(CRLF→LF) + 줄별 끝공백 제거 → sha1 앞 16자.
    (줄 끝 공백·CRLF는 편집기·저장 경로에 따라 저절로 생겼다 사라진다. 그걸로
     "대본이 바뀌었다"고 보면 안 된다 — 사람이 보기에 같은 글이면 같아야 한다.)
    """
    s = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    s = "\n".join(line.rstrip() for line in s.split("\n"))
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16] if s else ""


@app.get("/api/mix/status/{job_id}")
def api_mix_status(job_id: str, request: Request):
    store = Store(DB_PATH)
    job = store.get_mix_job(job_id)
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
    # ★clean/preview 단계도 같은 staleness 가드(2026-07-23 실사고). 배포 재시작이 진행 중이던
    # 2단계 자막제거(clean) BackgroundTask를 죽이면 except가 못 돌아 clean_status='cleaning'이
    # DB에 영원히 남고, 프론트가 "AI가 자막 영역을 복원하는 중"을 무한 표시한다. status(위)엔 이미
    # 이 가드가 있었으나 clean/preview에는 없어 같은 사고가 이 단계에서 재발했다. GET이라 DB는
    # 안 건드리고 응답에서만 failed로 알려 pollClean이 재시도 UI를 연다(_render_is_stale는
    # updated_at 기반·단계무관, 이미 clean 재실행 가드에서 쓰인다).
    clean_status, clean_error = job.get("clean_status"), job.get("clean_error")
    if clean_status == "cleaning" and _render_is_stale(job):
        clean_status = "failed"
        clean_error = clean_error or "서버 재시작 등으로 중단되었습니다. 다시 시도해 주세요."
    preview_status, preview_error = job.get("preview_status"), job.get("preview_error")
    if preview_status == "rendering" and _render_is_stale(job):
        preview_status = "failed"
        preview_error = preview_error or "서버 재시작 등으로 중단되었습니다. 다시 시도해 주세요."
    # 장면 우선 대본 모드(2026-07-20, Task7): 후보 요약만 내려준다 — 전체 plan(beats 등)을
    # 실으면 남의 창작물이 새는 것과 같은 노출 문제(§3981)가 나므로 카드 렌더용 필드만 뽑는다.
    # script(2026-07-24): 후보 대본 '전체 나레이션'은 사장님이 A/B/C를 비교해 고르는 자기 산출물이라
    # 카드에서 통째로 보여준다 — 소스 plan(컷·seg_ids 등)이 아니라 말할 문장만 이어붙인다(edit_plan §561과 동일).
    # lines(2026-08-10): 카드에서 **문장별로** 고쳐 쓰기 위한 나레이션 배열. script를 그냥
    #   안 이어붙인 것뿐이라 새로 새는 정보는 없다(위 노출 원칙 그대로). 문장 단위로 내리는
    #   이유는 화면 배정(beats[].covers)이 **문장 개수·순서에 묶여** 있어서다 — 통짜 텍스트로
    #   편집시키면 사장님이 문장을 쪼개거나 합치는 순간 컷 매핑이 어긋난다. 칸을 문장 수만큼
    #   고정해 두면 글자만 고치게 되어 covers가 항상 유효하다.
    candidates = [{"index": i, "score": c.get("score"), "recommended": bool(c.get("recommended")),
                   "hook": (c.get("story") or {}).get("hook", ""),
                   "story_person": (c.get("story") or {}).get("story_person", ""),
                   "lines": [(b.get("narration") or "").strip()
                             for b in ((c.get("plan") or {}).get("beats") or [])],
                   "script": " ".join((b.get("narration") or "").strip()
                                       for b in ((c.get("plan") or {}).get("beats") or [])).strip()}
                  for i, c in enumerate(store.get_mix_candidates(job_id))]
    # ★추출이 조용히 실패한 소스를 알린다(2026-07-31 사장님: "실제 영상은 20초가 넘는데
    #   추출이 실패한 거라 사용자는 알 수가 없다"). 실측 job 8226822c5b09: 21초 영상이
    #   2구간 7.4초로 나와 재료가 없었는데 화면엔 표시가 없어 "왜 A로만?"으로만 보였다.
    #   mix_pipeline이 커버리지를 재서 weak_extract를 심어둔다 — 여기선 소스 번호만 내보낸다
    #   (원본 URL·경로는 안 싣는다: 아래 candidates 주석과 같은 노출 원칙).
    weak = []
    try:
        for i, (vid, ex) in enumerate(sorted((job.get("extract") or {}).items()), 1):
            if isinstance(ex, dict) and ex.get("weak_extract"):
                cov = ex.get("coverage")
                weak.append({"n": i, "coverage": round(cov, 2) if cov is not None else None})
    except Exception:
        weak = []
    # ★실패 사유는 관리자만(2026-08-04 사장님 지시). 08-03 사고 때 사용자 화면에
    # "apify 토큰 17개 전부 실패…" 같은 내부 사정이 그대로 떴다 — 사용자는 알 수도 없고
    # 알 필요도 없는 정보다. 반대로 **관리자에겐 원문 그대로** 보여야 사고를 빨리 잡는다
    # (그날 13:45부터 죽고 있었는데 아무도 몰랐던 이유가 사유가 안 보여서였다).
    error_detail = None
    if error and _is_admin(getattr(request.state, "customer_id", None)):
        error_detail = error
    if error:
        error = _user_facing_error(error)
    # ★순서 대기 표시(2026-08-06 사장님): 큐에서 기다리는 중인데 '다운로드 중'으로 보여
    #   멈춘 것처럼 보였다. 아직 워커가 안 집었으면(queue의 mix 항목이 queued) 개수를 내려
    #   프론트가 '순서 대기 중 — 내 앞 N개'를 띄운다.
    queue_ahead = (store.mix_queue_ahead(job_id)
                   if status in _MIX_ACTIVE_STAGES else None)
    return {"ok": True, "status": status, "error": error,
            "error_detail": error_detail,   # 관리자에게만 채워진다(일반 사용자는 None)
            "queue_ahead": queue_ahead,     # None=대기 아님 / 0=다음 차례 / N=내 앞 N개
            "weak_sources": weak,
            # 1단계 미리보기(2026-07-17): 폴러를 둘로 만들지 않으려고 기존 응답에 얹는다(스펙 §6.3).
            # preview_path는 서버 내부 경로라 안 내보낸다 — 파일은 전용 라우트로만 서빙.
            "preview_status": preview_status,
            "preview_error": preview_error,
            "clean_status": clean_status,
            "clean_error": clean_error,
            # 지워진 자막 위치(2026-07-25): 5단계 꾸미기가 자막 자동정렬·'원본 자막 있던 자리' 마커에 쓴다.
            # 좌표(%)뿐이라 안전 — 소스 경로 등 내부정보는 안 실린다.
            "clean_regions": job.get("clean_regions"),
            # 지금 고른 후보(2026-07-30). 다른 단계 갔다 돌아온 복원 경로가 카드를 원래 선택 상태로
            # 다시 그리는 데 쓴다. 아직 아무것도 안 골랐으면 None → 프론트가 recommended를 따른다.
            "selected_index": (job.get("edit_plan") or {}).get("candidate_index"),
            # ★이 job이 어떤 대본으로 매칭됐는지의 지문(2026-08-17). 3단계가 들어올 때마다
            #   화면 대본과 대조해 **바뀌었으면 자동으로 다시 붙이려고** 쓴다(사장님 결정 A).
            #   원문을 실으면 응답만 무거워진다 — 같은지 다른지만 알면 되므로 해시로 보낸다.
            "script_hash": _script_hash(job.get("given_script") or ""),
            "candidates": candidates}


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
                      "cap_segments": video_assemble._caption_segments(
                          b.get("narration", ""), preset=b.get("caption_lines"))})
    # 옛 job(recipe_secret 등)도 새 key로 정규화해 라벨·드롭다운이 어긋나지 않게(fail-open).
    detected = _edit_plan._normalize_video_type(plan.get("detected_type"))
    return {
        "ok": True, "structure": plan["structure"], "beats": beats,
        # ★P1/P2(2026-07-24): 어느 생성기가 만들었나 + 렌더 전 불변식 위반을 화면에 띄우기 위해
        # 내보낸다(조용한 폴백·조용한 위반 금지). 없으면 옛 job → 프런트가 경고 안 그린다.
        "generator": plan.get("generator", ""),
        "generator_note": plan.get("generator_note", ""),
        "gate": plan.get("gate") or None,
        "detected_type": detected,
        "detected_type_label": _edit_plan.VIDEO_TYPES.get(detected, {}).get("label", detected),
        "affiliate_target": plan.get("affiliate_target", ""),
        "video_types": [{"key": k, "label": v["label"]} for k, v in _edit_plan.VIDEO_TYPES.items()],
        # 검수판(Task4) — scene_match.py가 채운 미채택 제안(threshold 미달)을 그대로 넘긴다.
        # {beat_idx, asset_id, score}[]. 자동배치(cutaway)는 이미 beats[].cutaway에 있다.
        "asset_suggestions": plan.get("asset_suggestions") or [],
        # 쿠팡 연결(2026-07-28) — 이미 고른 상품이 있으면 그대로, 없으면 검색 링크만.
        # affiliate_target(팔 제품 이름)이 뜨는 그 자리에서 바로 상품을 확정한다.
        "product": job.get("product"),
        "coupang_search_url": coupang_partners.search_url(plan.get("affiliate_target", "")),
        "partners_link_page": coupang_partners.PARTNERS_LINK_PAGE,
    }


@app.post("/api/mix/product")
def api_mix_product(body: dict):
    """이 영상이 연결할 쿠팡 상품 저장/해제(승인 전 수동 흐름) — 사장님이 쿠팡
    검색결과에서 고른 상품 URL(또는 파트너스에서 만든 추적 링크)을 붙여넣는다."""
    job_id = (body.get("job_id") or "").strip()
    store = Store(DB_PATH)
    job = store.get_mix_job(job_id) if job_id else None
    if not job:
        return JSONResponse(status_code=404, content={"ok": False, "error": "job 없음"})
    if body.get("clear"):
        store.set_mix_product(job_id, None)
        return {"ok": True, "product": None, "final_link": ""}
    try:
        product = coupang_partners.build_product(
            keyword=body.get("keyword", ""), url=body.get("url", ""),
            name=body.get("name", ""), partner_url=body.get("partner_url", ""),
            memo=body.get("memo", ""),
        )
    except ValueError as e:
        return JSONResponse(status_code=422, content={"ok": False, "error": str(e)})
    # 등록완료 체크는 저장할 때마다 초기화하지 않는다 — 링크만 고쳤는데 "인포크에
    # 이미 올렸다"는 사실이 지워지면 사장님이 중복 등록하게 된다.
    prev = job.get("product") or {}
    product["inpock_registered"] = bool(
        body.get("inpock_registered", prev.get("inpock_registered", False)))
    store.set_mix_product(job_id, product)
    return {"ok": True, "product": product,
            "final_link": coupang_partners.final_link(product),
            "description_block": coupang_partners.description_block(product)}


@app.get("/api/coupang/search")
def api_coupang_search(q: str = "", limit: int = 0):
    """키워드 → 쿠팡 상품 후보 카드(승인 전 크롤 경로).

    ★async가 아니라 def다 — 안에서 Playwright **sync** API를 쓰므로 이벤트 루프
    스레드에서 돌면 죽는다(FastAPI가 def 핸들러를 워커 스레드로 돌려준다).
    실패해도 200 + ok:False로 돌려준다 — 화면은 이때 기존 수동 흐름(검색 링크
    새 탭 + URL 붙여넣기)으로 조용히 되돌아간다."""
    from shopping_shorts import coupang_partners, coupang_relay, coupang_search
    if config.COUPANG_SEARCH_MODE != "relay":
        return coupang_search.search(q, limit=limit or None)
    # 릴레이 모드 — 서버는 한국 IP가 없어 직접 못 긁는다(coupang_relay.py 참고).
    kw = (q or "").strip()
    manual = {"ok": False, "items": [], "source": "relay",
              "search_url": coupang_partners.search_url(kw)}
    if not kw:
        return dict(manual, search_url="", notice="검색어가 비어있습니다")
    got = coupang_relay.QUEUE.submit(kw, limit or config.COUPANG_SEARCH_LIMIT,
                                     config.COUPANG_RELAY_WAIT_SEC)
    if got is None:
        return dict(manual, notice="검색 도우미(사장님 PC)가 응답하지 않습니다 — "
                                   "아래에 상품 URL을 직접 붙여넣으세요")
    return got


# job_id → 렌즈가 찾아낸 제품명. SerpApi가 프레임당 1콜이라 같은 영상에서 두 번
# 누르면 과금이 두 번 난다 — 프로세스 메모리 캐시로 막는다(재시작하면 비는 게 맞다).
_COUPANG_LENS_CACHE = {}


@app.post("/api/coupang/lens")
def api_coupang_lens(body: dict):
    """★유료 경로 — 사장님이 '화면으로 정확히 찾기'를 눌렀을 때만 돈다.

    대본 글자만 읽으면 "슬라임 재료" 수준에서 멈춘다. 영상 프레임을 Google Lens로
    역검색하면 브랜드·모델까지 좁혀진다(product_identify, 2026-07-10부터 제품찾기
    화면이 쓰던 그 경로 재사용). SerpApi는 프레임당 1콜이라 **job당 1회만** 돌고
    결과는 mix_jobs에 남긴다 — 같은 영상에서 두 번 누르면 캐시를 준다."""
    job_id = (body.get("job_id") or "").strip()
    store = Store(DB_PATH)
    job = store.get_mix_job(job_id) if job_id else None
    if not job:
        return JSONResponse(status_code=404, content={"ok": False, "error": "job 없음"})
    cached = _COUPANG_LENS_CACHE.get(job_id)
    if cached and not body.get("force"):
        return {"ok": True, "name": cached, "cached": True}

    work = _MIX_WORK_DIR / job_id
    try:
        src = _resolve_sources(job, work)[_source_video_id(0)]
    except Exception:
        return {"ok": False, "name": "", "error": "소스 영상을 찾지 못했습니다"}
    # ★프레임은 _FIND_TMP_DIR 아래로 뽑는다 — /api/find/frame/이 그 폴더만 서빙하고,
    # SerpApi가 우리 서버로 이미지를 받으러 오므로 공개 URL이어야 한다(로그인 예외 경로).
    work_id = f"coupang_{job_id}"
    lens_dir = _FIND_TMP_DIR / work_id
    try:
        frames = frame_extract.extract_frames(src, lens_dir, max_frames=6)
    except Exception as e:  # noqa: BLE001 — 유료 경로 앞단에서 죽어도 화면은 살아야 한다
        return {"ok": False, "name": "", "error": f"프레임 추출 실패: {type(e).__name__}"}
    if not frames:
        return {"ok": False, "name": "", "error": "프레임을 뽑지 못했습니다"}

    urls = [f"{PUBLIC_BASE_URL}/api/find/frame/{work_id}/{p.name}" for p in frames]
    try:
        lines = fetch_lens_lines(urls)
        plan = job.get("edit_plan") or {}
        name = identify_product_from_lines(
            lines, category=plan.get("detected_type", ""),
            caption=(plan.get("affiliate_target") or ""))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "name": "", "error": f"렌즈 실패: {type(e).__name__}"}
    if not name:
        return {"ok": False, "name": "",
                "error": "화면에서 상품을 특정하지 못했습니다 — 검색어를 직접 고쳐보세요"}
    _COUPANG_LENS_CACHE[job_id] = name   # 같은 영상에서 또 누르면 과금 없이 돌려준다
    return {"ok": True, "name": name, "cached": False}


@app.post("/api/coupang/suggest")
def api_coupang_suggest(body: dict):
    """대본 + 연결 대상 → 쿠팡에 칠 만한 상품명 후보.

    편집안의 affiliate_target은 서술형("갈라진 프린팅 수선")일 때가 많아 그대로 검색하면
    엉뚱한 게 나온다(2026-07-29 사장님 캡처: 자수 패치·고양이 패치가 잔뜩). 실패하면
    타깃 그대로 돌려주므로 화면은 어차피 검색을 진행할 수 있다."""
    from shopping_shorts import coupang_query
    qs = coupang_query.suggest((body.get("target") or ""), (body.get("script") or ""))
    return {"ok": True, "queries": qs}


def _analyze_relay_raw(raw, product=None):
    """릴레이가 올린 원본(상세 이미지 base64 + 리뷰) → product_facts 분석 결과.

    ★왜 서버가 분석하나: 분석 키(`SHORTS_GEMINI_KEY`)는 서버에만 있다. PC는 쿠팡이
      막는 부분(긁기)만 맡는다 — 키를 두 곳에 두면 관리가 갈린다(0순위-B).
    ★실패해도 예외를 안 낸다 — 재료가 없다고 대본 생성이 막히면 안 된다.
    """
    raw = raw or {}
    imgs_b64 = raw.get("images_b64") or []
    reviews = raw.get("reviews") or []
    if not imgs_b64 and not reviews:
        return None
    import base64
    import tempfile
    from shopping_shorts import product_facts
    tmpdir = tempfile.mkdtemp(prefix="relay_facts_")
    paths = []
    try:
        for i, b64 in enumerate(imgs_b64):
            try:
                p = os.path.join(tmpdir, "detail_%02d.jpg" % i)
                with open(p, "wb") as f:
                    f.write(base64.b64decode(b64))
                paths.append(p)
            except Exception:      # noqa: BLE001 — 이미지 한 장 깨져도 나머지로 간다
                continue
        return product_facts.analyze(
            {"detail_images": paths, "reviews": reviews,
             "title": raw.get("title") or "", "url": raw.get("url") or ""},
            name=((product or {}).get("name") or raw.get("title") or ""))
    except Exception as e:      # noqa: BLE001
        print("[relay_facts] 분석 실패: %s %s" % (type(e).__name__, str(e)[:120]))
        return None
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@app.get("/api/coupang/relay/next")
def api_coupang_relay_next(token: str = "", wait: int = 25):
    """릴레이(사장님 PC)가 일감을 받아가는 롱폴링 창구. 없으면 job:null."""
    from shopping_shorts import coupang_relay
    if not config.COUPANG_RELAY_TOKEN or token != config.COUPANG_RELAY_TOKEN:
        return JSONResponse(status_code=403, content={"ok": False, "error": "토큰 불일치"})
    job = coupang_relay.QUEUE.take(max(1, min(wait, 55)))
    if job is None:
        return {"ok": True, "job": None}
    # kind·payload를 함께 내려준다(2026-08-17). 옛 릴레이 클라이언트는 이 키를 무시하고
    # 종전대로 q로 검색하므로, 릴레이를 안 올려도 검색은 그대로 돈다(회귀 0).
    return {"ok": True, "job": {"id": job.id, "q": job.q, "limit": job.limit,
                                "kind": getattr(job, "kind", "search"),
                                "payload": getattr(job, "payload", {}) or {}}}


@app.post("/api/coupang/relay/result")
def api_coupang_relay_result(body: dict):
    """릴레이가 로컬에서 긁어온 결과를 되돌려준다 — 기다리던 웹 요청이 이걸 받는다."""
    from shopping_shorts import coupang_relay
    if not config.COUPANG_RELAY_TOKEN or body.get("token") != config.COUPANG_RELAY_TOKEN:
        return JSONResponse(status_code=403, content={"ok": False, "error": "토큰 불일치"})
    payload = {"ok": bool(body.get("ok")), "items": body.get("items") or [],
               "search_url": body.get("search_url") or "", "source": "relay",
               "notice": body.get("notice") or "",
               # 상세·리뷰 수집(kind="detail") 결과.
               # ★PC는 긁기만, 분석은 여기서 한다 — 분석 키(SHORTS_GEMINI_KEY)가 서버에만
               #   있기 때문이다(키를 PC로 복사하면 관리 지점이 둘이 된다, 0순위-B).
               "facts": _analyze_relay_raw(body.get("raw"), body.get("product")),
               "product": body.get("product") or None}
    delivered = coupang_relay.QUEUE.complete((body.get("id") or "").strip(), payload)
    # 이미 타임아웃으로 접힌 요청이면 delivered=False — 릴레이 잘못이 아니니 200으로 알린다.
    return {"ok": True, "delivered": delivered}


@app.get("/api/coupang/relay/status")
def api_coupang_relay_status():
    """화면·운영이 "PC가 붙어 있나"를 볼 수 있게. 토큰은 안 드러낸다."""
    from shopping_shorts import coupang_relay
    st = coupang_relay.QUEUE.status()
    st["mode"] = config.COUPANG_SEARCH_MODE
    st["configured"] = bool(config.COUPANG_RELAY_TOKEN)
    return st


@app.get("/api/mix/product/{job_id}")
def api_mix_product_get(job_id: str):
    """SEO 설명란·최종렌더 단계가 "인포크에 넣을 링크"와 설명 블록을 꺼내 쓴다."""
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"ok": False, "error": "job 없음"})
    product = job.get("product")
    return {"ok": True, "product": product,
            "final_link": coupang_partners.final_link(product),
            "description_block": coupang_partners.description_block(product),
            "partners_link_page": coupang_partners.PARTNERS_LINK_PAGE,
            "inpock_page": coupang_partners.INPOCK_PAGE}


@app.post("/api/mix/retype")
def api_mix_retype(background_tasks: BackgroundTasks, body: dict):
    """사용자가 감지된 영상 유형을 바꾸면 저장된 extract로 EDL+TTS 재생성(재다운로드 없음)."""
    job_id = body.get("job_id"); video_type = body.get("video_type")
    # 옛 key(recipe_secret 등)로 저장된 job·구버전 클라이언트도 받아 새 key로 흡수(fail-open).
    # 진짜 미지값만 거른다(빈 문자열/None은 normalize가 기본형으로 떨어뜨리므로 명시 검사).
    if not video_type or (video_type not in _edit_plan.VIDEO_TYPES
                          and video_type not in _edit_plan._VIDEO_TYPE_ALIASES):
        return JSONResponse(status_code=422, content={"ok": False, "error": "알 수 없는 영상 유형"})
    video_type = _edit_plan._normalize_video_type(video_type)
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job or not job.get("extract"):
        return JSONResponse(status_code=404, content={"ok": False, "error": "재생성할 데이터 없음"})
    Store(DB_PATH).enqueue("retype", {"job_id": job_id, "video_type": video_type})
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
    # 장면실험실 이식(2026-08-15): shot_role·is_key·phash를 **추가**한다(기존 키는 그대로 —
    # 이 응답을 쓰는 기존 피커 화면이 있다. 제거·이름변경 금지). phash는 seg_thumb이
    # 썸네일을 만들 때 함께 계산해 캐시한 것만 싣는다(없으면 "" — 소비자는 접기만 끈다).
    phash = _lab_phash_load(_MIX_WORK_DIR / job_id)
    segs = [{
        "seg_id": sid, "video_id": seg["video_id"],
        "start": seg["start"], "end": seg["end"],
        "dur": round(seg["end"] - seg["start"], 1),
        "scene_desc": seg.get("scene_desc", ""), "text": seg.get("text", ""),
        "thumb_url": f"/api/mix/seg_thumb/{job_id}/{sid}",
        "used": sid in used,
        "shot_role": seg.get("shot_role") or "기타",
        "is_key": bool(seg.get("is_key")),
        "phash": phash.get(sid, ""),
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
    # 장면실험실(2026-08-15): 썸네일이 확보된 김에 phash(8x8 평균해시)도 함께 캐시한다.
    # 응답마다 ffmpeg을 새로 돌리지 않게 캐시 파일(phash.json)에 한 번만. 실패해도 썸네일은 나간다.
    _lab_phash_ensure(work, seg_id, cached)
    return FileResponse(str(cached), media_type="image/jpeg")


# ── 장면실험실(scene_lab) 서버 배선 (2026-08-15) ─────────────────────────────────
# 로컬 실험실(tools/scene_lab)이 SSH로 빼가던 데이터를 제작소 2단계 iframe
# (/scene_lab.html?job=…)이 API로 받는다. 데이터 모양은 fetch.py가 만들던 data.json과
# 1:1 동일 — UI(scene_lab.html)가 모드 분기 없이 같은 코드로 돌기 위해서다(0순위-B).

_LAB_PHASH_LOCK = __import__("threading").Lock()


def _lab_phash_bits(raw):
    """8x8 흑백 rawvideo(64바이트) → 평균해시 64비트 문자열.
    tools/scene_lab/fetch.py가 쓰던 것과 같은 규칙 — 로컬에서 만든 해시와 호환된다."""
    if not raw or len(raw) < 64:
        return ""
    px = list(raw[:64])
    avg = sum(px) / 64.0
    return "".join("1" if v > avg else "0" for v in px)


def _lab_phash_from_jpg(jpg_path):
    """썸네일 jpg → phash. 썸네일은 세그 중간 프레임 그 자체라(추출 시각 동일) 소스를
    다시 시크하는 것보다 훨씬 싸다. 실패하면 ""(소비자는 중복접기만 끈다)."""
    import subprocess
    p = Path(jpg_path)
    if not p.exists():
        return ""
    try:
        # 외부 도구 호출엔 반드시 timeout(memory: ffmpeg 무한대기).
        r = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(p),
             "-vf", "scale=8:8,format=gray", "-frames:v", "1", "-f", "rawvideo", "-"],
            capture_output=True, timeout=20)
        return _lab_phash_bits(r.stdout or b"")
    except Exception:
        return ""


def _lab_phash_load(work):
    """{seg_id: 64비트 문자열} 캐시 읽기(없으면 {})."""
    import json
    f = Path(work) / "seg_thumbs" / "phash.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except Exception:
        return {}


def _lab_phash_ensure(work, seg_id, jpg_path):
    """seg_id의 phash가 캐시에 없으면 jpg에서 계산해 저장(read-modify-write는 락으로 직렬화 —
    피커·실험실이 썸네일 수십 장을 병렬로 당기므로 안 잠그면 서로 덮어쓴다)."""
    import json
    try:
        with _LAB_PHASH_LOCK:
            cache = _lab_phash_load(work)
            if cache.get(seg_id):
                return cache[seg_id]
            bits = _lab_phash_from_jpg(jpg_path)
            if not bits:
                return ""
            cache[seg_id] = bits
            f = Path(work) / "seg_thumbs" / "phash.json"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(cache), encoding="utf-8")
            return bits
    except Exception:
        return ""


def _lab_captions(plan):
    """비트별 자막 구절 [{text,start,end}] + tts 실길이 — fetch.py [3/5]와 같은 계산.
    ★라이브 렌더와 같은 함수(_caption_segments/_caption_durations/_adjust_caps_for_trim)를
    호출해 결과만 싣는다. JS로 다시 나누면 두 벌이 되어 반드시 어긋난다(0순위-B)."""
    caps, tts_dur = {}, {}
    for b in plan.get("beats") or []:
        i = b["beat_idx"]
        segs = video_assemble._caption_segments(b.get("narration") or "",
                                                b.get("caption_lines"))
        dur = 0.0
        tp = b.get("tts_path")
        if tp and Path(tp).exists():
            dur = video_assemble._probe_duration(tp) or 0.0
        tts_dur[str(i)] = round(dur, 3) if dur else None
        lead, rd = video_assemble._adjust_caps_for_trim(b)
        durs = video_assemble._caption_durations(
            segs, dur or (b.get("target_seconds") or 3.0), real_durs=rd)
        t = float(lead or 0.0)
        rows = []
        for seg, dd in zip(segs, durs):
            rows.append({"text": seg, "start": round(t, 3), "end": round(t + dd, 3)})
            t += dd
        caps[str(i)] = rows
    return caps, tts_dur


@app.get("/api/mix/scene_lab/{job_id}")
def api_mix_scene_lab_data(job_id: str):
    """실험실 페이지용 데이터 한 방 — fetch.py가 SSH로 만들던 data.json과 같은 모양."""
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job or not job.get("extract"):
        return JSONResponse(status_code=404, content={"ok": False, "error": "데이터 없음"})
    plan = job.get("edit_plan")
    if not plan:
        return JSONResponse(status_code=404,
                            content={"ok": False, "error": "편집안이 아직 없어요 — 매칭을 먼저 완료하세요"})
    seg_map, _ = _edit_plan._build_inventory(list(job["extract"].values()))
    work = _MIX_WORK_DIR / job_id
    # 소스 실길이 — 범위초과 세그(실체 없는 화면) 표시용. 소스가 없으면 {}로 폴백(표시만 꺼진다).
    src_duration = {}
    try:
        for vid, p in _resolve_sources(job, work).items():
            d = video_assemble._probe_duration(p)
            if d:
                src_duration[vid] = round(d, 2)
    except Exception:
        pass
    # 소스별 갈래(2026-08-17) — 팔레트를 '결'이 아니라 **어느 영상에서 왔나**로 묶을 때
    # 머리글에 제품명을 찍으려고 싣는다. 옛 추출본엔 source_brief가 없어 {}가 되고,
    # 그러면 화면은 '소스 N'만 찍는다(fail-open, 회귀 없음).
    src_brief = {}
    for _s in (job.get("extract") or {}).values():
        _v = (_s or {}).get("video_id") or ""
        _b = (_s or {}).get("source_brief") or {}
        if _v and _b:
            src_brief[_v] = _b
    caps, tts_dur = _lab_captions(plan)
    # ★소재 종류(2026-08-17 사장님 "레시피 틀로 고정돼서 재료·반죽 준비 이런 게 들어왔다").
    #   실험실 팔레트 머리글이 요리 전용으로 하드코딩돼 있어, 젤펜 영상인데도
    #   '🥣 재료·반죽 준비 · 섞기·짜기'가 떴다(실측 job 202377f690d9: 소스 4개 전부 cat=기타).
    #   판정을 새로 만들지 않는다 — 추출이 이미 붙여둔 카테고리를 그대로 넘겨
    #   화면이 그에 맞는 머리글을 고르게 한다(scene_lab.html GROUPS_BY_CAT).
    _cats = []
    for _u in (job.get("urls") or []):
        try:
            _row = Store(DB_PATH).wiki_category_for_url(_u)
        except Exception:      # noqa: BLE001 — 라벨 하나 때문에 실험실이 안 열리면 안 된다
            _row = None
        if _row:
            _cats.append(_row)
    # 다수결(소스가 섞이면 제일 많은 쪽). 하나도 못 찾으면 ""(화면이 중립 라벨로 간다).
    category = max(set(_cats), key=_cats.count) if _cats else ""
    return {"ok": True, "data": {
        "job_id": job_id,
        "category": category,
        "beats": plan.get("beats") or [],
        "urls": job.get("urls") or [],
        "src_brief": src_brief,
        "syll_per_sec": _edit_plan._SYLLABLES_PER_SEC,
        "segments": {sid: {
            "video_id": v["video_id"], "start": v["start"], "end": v["end"],
            "scene_desc": v.get("scene_desc", ""), "text": v.get("text", ""),
            # 짧은 이름(2026-08-16) — 카드 밑 긴 묘사는 2줄에서 잘려 안 읽힌다.
            # 옛 추출본엔 없어 ""(화면이 알아서 이 줄을 안 그린다).
            "label": (v.get("label") or ""),
            "shot_role": v.get("shot_role") or "기타", "is_key": bool(v.get("is_key")),
            "action": v.get("action") or "", "change": v.get("change") or "",
            "benefits": v.get("product_benefits") or [],
        } for sid, v in seg_map.items()},
        "phash": _lab_phash_load(work),      # 썸네일 캐시가 채워지는 대로 /phash로 늦채움
        "src_duration": src_duration,
        "captions": caps,
        "tts_dur": tts_dur,
    }}


@app.get("/api/mix/scene_lab/{job_id}/phash")
def api_mix_scene_lab_phash(job_id: str):
    """phash 늦채움 폴링 — 썸네일(seg_thumb)이 만들어질 때마다 캐시가 늘어난다."""
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"ok": False, "error": "job 없음"})
    return {"ok": True, "phash": _lab_phash_load(_MIX_WORK_DIR / job_id)}


def _range_mp4_response(path, request):
    """mp4를 Range(부분 요청)까지 지원해 내보낸다 — 브라우저가 구간 시크를 하려면 필수.

    ★2026-08-15 실사고: 예전엔 FileResponse만 돌려주고 주석에 "FileResponse가 Range를
      처리해 구간 시크가 된다"고 적어뒀는데 **사실이 아니었다**. 서버 starlette 0.36.3의
      FileResponse에는 range 처리 코드가 아예 없다(실측: 소스에 'range' 문자열 0건.
      Range 지원은 starlette 0.37+). 그래서 서버는 늘 200에 파일 전체를 주고
      Accept-Ranges도 안 보냈다 → 브라우저가 시크를 못 해 **어떤 장면을 골라도 0초부터
      재생**됐다(실측 job 8a5a4732d77b: 담은 구간 4.7~8.8초인데 0~3.0초가 재생,
      s0의 3.0초 프레임과 화면이 픽셀 단위로 일치).
      starlette 업그레이드는 앱 전체에 영향이 가므로 여기서만 Range를 직접 처리한다.
    """
    p = Path(path)
    size = p.stat().st_size
    raw = (request.headers.get("range") or "").strip() if request is not None else ""
    base = {"accept-ranges": "bytes", "content-type": "video/mp4"}
    if not raw.startswith("bytes="):
        return FileResponse(str(p), media_type="video/mp4", headers={"accept-ranges": "bytes"})
    # "bytes=시작-끝" 한 구간만 다룬다(브라우저 영상 재생은 이 형태만 쓴다).
    try:
        s_txt, _, e_txt = raw[6:].split(",")[0].partition("-")
        if s_txt:
            start = int(s_txt)
            end = int(e_txt) if e_txt else size - 1
        else:                       # "bytes=-500" = 뒤에서 500바이트
            start = max(0, size - int(e_txt))
            end = size - 1
    except Exception:
        return FileResponse(str(p), media_type="video/mp4", headers={"accept-ranges": "bytes"})
    if start >= size:
        return Response(status_code=416, headers={"content-range": f"bytes */{size}"})
    end = min(end, size - 1)
    length = end - start + 1

    def _chunks():
        with open(p, "rb") as f:
            f.seek(start)
            left = length
            while left > 0:
                buf = f.read(min(262144, left))
                if not buf:
                    break
                left -= len(buf)
                yield buf

    headers = dict(base)
    headers["content-range"] = f"bytes {start}-{end}/{size}"
    headers["content-length"] = str(length)
    return StreamingResponse(_chunks(), status_code=206, headers=headers)


@app.get("/api/mix/src/{job_id}/{video_id}")
def api_mix_src(job_id: str, video_id: str, request: Request):
    """실험실 미리보기용 소스 원본 mp4(구간 시크 지원 — _range_mp4_response 주석 참고).
    video_id는 _resolve_sources 맵에 있는 것만(경로 방어 — 임의 파일명 불가)."""
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"ok": False, "error": "job 없음"})
    try:
        src = _resolve_sources(job, _MIX_WORK_DIR / job_id).get(video_id)
    except Exception:
        src = None
    if not src or not Path(src).exists():
        return JSONResponse(status_code=404, content={"ok": False, "error": "소스 없음"})
    return _range_mp4_response(src, request)


@app.post("/api/mix/scene_lab/{job_id}/fill")
def api_mix_scene_lab_fill(job_id: str, body: dict):
    """칸 하나를 **대사에 맞는 화면들로** 채운다(2026-08-16 사장님 "당연히 대본이랑
    태깅까지 보면서 매칭을 해야지").

    body = {"beat_idx": 0, "need": 3.8, "taken": ["s1-1", ...]}
      need  = 그 칸의 나레이션 길이(초). 없으면 서버가 편집안에서 읽는다.
      taken = 이미 어느 칸에든 담긴 장면들 — 후보에서 뺀다(같은 화면 되풀이 방지).
    돌려주는 것 = {"picks": [{"seg_id", "fit", "why"}]} · 순서대로.

    ★고르는 판단은 edit_plan.fill_beat_scenes 한 곳에만 있다. 화면(scene_lab.html)은
    이 결과를 그대로 담기만 하고, 실패하면 제 규칙 기반 채우기로 내려간다(fail-open).
    """
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job or not job.get("edit_plan"):
        return JSONResponse(status_code=404, content={"ok": False, "error": "편집안 없음"})
    try:
        bi = int(body.get("beat_idx"))
    except (TypeError, ValueError):
        return JSONResponse(status_code=422, content={"ok": False, "error": "beat_idx 필요"})
    beats = job["edit_plan"].get("beats") or []
    if not (0 <= bi < len(beats)):
        return JSONResponse(status_code=422, content={"ok": False, "error": "없는 칸"})
    narration = (beats[bi].get("narration") or "").strip()
    if not narration:
        return JSONResponse(status_code=422, content={"ok": False, "error": "이 칸엔 멘트가 없어요"})
    seg_map, _ = _edit_plan._build_inventory(list((job.get("extract") or {}).values()))
    taken = {str(s) for s in (body.get("taken") or [])}
    pool = [sid for sid in seg_map if sid not in taken]
    if not pool:
        return {"ok": True, "picks": [], "reason": "남은 장면이 없어요"}
    need = body.get("need")
    if need is None:
        # 화면이 안 보내면 편집안의 그 비트 길이로 대신한다(기준을 두 벌로 두지 않는다).
        # 음성이 아직 없으면 tts 실길이가 None이다 — 그때는 계획 길이로 대신한다.
        _caps, _tts = _lab_captions(job["edit_plan"])
        need = (_tts or {}).get(str(bi)) or beats[bi].get("target_seconds")
    # ★칸의 역할(훅·CTA·결과…)을 함께 넘긴다(2026-08-17 사장님 "훅부터 기준이 뭘로 한 건지").
    #   대사만으로는 감정·상황을 말하는 훅에 아무 화면이나 붙는다 — 역할을 알아야
    #   "훅엔 시선 끄는 완성품"처럼 고를 수 있다(edit_plan._ROLE_WANT_SHOTS).
    picks = _edit_plan.fill_beat_scenes(narration, need, seg_map, pool,
                                        taken_ids=sorted(taken),
                                        role=beats[bi].get("role") or "")
    return {"ok": True, "picks": picks}


@app.post("/api/mix/scene_lab/{job_id}/apply")
def api_mix_scene_lab_apply(job_id: str, body: dict):
    """실험실 편성을 edit_plan에 얹는다/걷는다(edit_plan.apply_scene_lab/revert_scene_lab).
    body = {"payload": {"beats": [...], "trims": {...}}} 또는 {"revert": true}.
    원본 primary/alternates는 안 건드리므로 언제든 100% 복구된다."""
    store = Store(DB_PATH)
    job = store.get_mix_job(job_id)
    if not job or not job.get("edit_plan"):
        return JSONResponse(status_code=404, content={"ok": False, "error": "편집안 없음"})
    # 렌더·생성 중엔 편집안을 바꾸지 않는다(tts_regen과 같은 가드 — 진행 중 잡의 발밑을 빼면 안 된다).
    if job.get("status") in _MIX_ACTIVE_STAGES + ("rendering", "removing_subtitles"):
        return JSONResponse(status_code=409,
                            content={"ok": False, "error": "생성·렌더 중에는 반영할 수 없어요"})
    plan = job["edit_plan"]
    if body.get("revert"):
        _edit_plan.revert_scene_lab(plan)
        store.update_mix_job(job_id, edit_plan=plan)
        return {"ok": True, "reverted": True}
    payload = body.get("payload") or {}
    if not payload.get("beats"):
        return JSONResponse(status_code=422, content={"ok": False, "error": "payload.beats 필요"})
    seg_map, _ = _edit_plan._build_inventory(list((job.get("extract") or {}).values()))
    _edit_plan.apply_scene_lab(plan, seg_map, payload)
    store.update_mix_job(job_id, edit_plan=plan)
    return {"ok": True, "applied": (plan.get("scene_lab") or {}).get("applied", 0)}


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
    Store(DB_PATH).enqueue("render", {"job_id": job_id})
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
    Store(DB_PATH).enqueue("preview", {"job_id": job_id})
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
    Store(DB_PATH).enqueue("clean", {"job_id": job_id})
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
    # 렌더 단계뿐 아니라 '이 음성으로 전체 생성'(active stage "tts") 등 활성 단계 전부에서 막는다.
    # 안 막으면 전체생성 백그라운드가 이 비트 새 톤 mp3를 job 기본 보이스로 덮어써 톤 변경이 사라진다
    # (2026-07-23 진단 — 스크린샷 "전체 음성 생성 중…" 상태에서 톤 바꿔도 적용 안 됨).
    if job.get("status") in _MIX_ACTIVE_STAGES + ("rendering", "removing_subtitles"):
        return JSONResponse(status_code=409, content={"ok": False, "error": "생성·렌더 중에는 재생성할 수 없어요"})
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


@app.post("/api/mix/scene_lab/{job_id}/narration/{beat_idx}")
def api_mix_scene_lab_narration(job_id: str, beat_idx: int, body: dict,
                                background_tasks: BackgroundTasks):
    """3단계(장면 편집)에서 **대본을 그 자리에서 고친다** — 2026-08-17 사장님
    "3단계에서 대본 몇 글자 수정하려고 2단계로 갔다 오는 방법밖에 없나".

    없어서 못 하던 게 아니라 **저장할 곳이 없었다**: 화면(scene_lab.html)엔 편집 장치가
    다 있었는데(NARR/editNarr/retts) 라이브에선 `SL.server`로 잠겨 있었고, 안내는
    "① 새 대본 고르기에서"를 가리키는데 그 UI는 9단계 개편에서 display:none 이 됐다
    (produce.html `#mixScriptPick`). 즉 앱 어디에서도 대본을 못 고치는 상태였다.

    ★새로 만든 건 이 저장구멍 하나뿐이다. 음성·자막 재생성은 **이미 있는**
    `resynth_one_beat`을 그대로 쓴다(그 함수가 beat["narration"]을 읽어 TTS를 다시 만들고
    cap_durs·cap_lead·tts_ver까지 갱신한다). 자막 분할을 여기서 다시 계산하지 않는다 —
    두 벌이 되면 렌더와 반드시 어긋난다(0순위-B).

    body = {"text": "고친 대본", "regen": true}
      regen=false면 문장만 저장한다(음성은 옛것 → 자막·소리가 어긋난 채로 남으므로
      화면이 경고를 띄운다). 기본은 True — 고쳤으면 다시 뽑는 게 정상 흐름이다.
    """
    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse(status_code=422, content={"ok": False, "error": "대본이 비었어요"})
    store = Store(DB_PATH)
    job = store.get_mix_job(job_id)
    if not job or not job.get("edit_plan"):
        return JSONResponse(status_code=404, content={"ok": False, "error": "작업 없음"})
    # /apply·tts_regen과 **같은 가드**. 진행 중 잡의 대본을 바꾸면 만들던 음성과 어긋난다.
    if job.get("status") in _MIX_ACTIVE_STAGES + ("rendering", "removing_subtitles"):
        return JSONResponse(status_code=409,
                            content={"ok": False, "error": "생성·렌더 중에는 대본을 고칠 수 없어요"})
    plan = job["edit_plan"]
    beat = next((b for b in plan["beats"] if b["beat_idx"] == beat_idx), None)
    if beat is None:
        return JSONResponse(status_code=404, content={"ok": False, "error": "비트 없음"})
    if text == (beat.get("narration") or "").strip():
        return {"ok": True, "unchanged": True}
    beat["narration"] = text
    # ★대본이 바뀌면 옛 문장 기준으로 계산된 자막 타이밍은 **전부 무효**다. 지워야
    #   _lab_captions·렌더가 새 문장으로 다시 계산한다(안 지우면 옛 구절 수에 맞춰
    #   zip이 잘려 자막이 중간에서 끊긴다).
    beat["cap_durs"] = None
    beat["cap_lead"] = 0.0
    # AI가 미리 끊어준 호흡 줄도 옛 문장 것이라 버린다 — 안 버리면 _caption_segments가
    # preset을 대조(공백 무시 일치)에서 떨어뜨려 조용히 규칙 폴백으로 내려간다.
    beat["caption_lines"] = None
    store.update_mix_job(job_id, edit_plan=plan)
    if body.get("regen") is False:
        return {"ok": True, "saved": True, "regen": False}
    # 음성·자막 다시 뽑기 = 이미 있는 경로. voice는 job 스냅샷을 그대로 물려준다
    # (통째로 새 dict를 만들면 이 비트만 소리가 달라진다 — tts_regen 주석과 같은 이유).
    background_tasks.add_task(resynth_one_beat, job_id, beat_idx,
                              dict(job.get("voice") or {}), DB_PATH, _MIX_WORK_DIR)
    return {"ok": True, "saved": True, "regen": True,
            "tts_ver": beat.get("tts_ver") or 0}


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
def api_voice_tune_corpus(request: Request):
    """튜닝 작업대 회귀 코퍼스(고정 10줄) — role별 카드로 렌더링."""
    denied = _require_admin(request)
    if denied:
        return denied
    import json as _json
    lines = _json.loads(_TUNE_CORPUS.read_text(encoding="utf-8")) if _TUNE_CORPUS.exists() else []
    return {"lines": lines}


@app.post("/api/voice-tune/preview")
async def api_voice_tune_preview(req: Request):
    """합성 없이 naturalize만 실행해 변환텍스트를 실시간 미리보기."""
    denied = _require_admin(req)
    if denied:
        return denied
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
    denied = _require_admin(req)
    if denied:
        return denied
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
def api_voice_tune_audio(request: Request, fname: str):
    # 작업대는 전부 관리자 전용 — 캐시 오디오도 같은 게이트로 일관성 유지(Task5 리뷰 Minor).
    denied = _require_admin(request)
    if denied:
        return denied
    f = _TUNE_CACHE / fname
    if not f.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(str(f), media_type="audio/mpeg")


@app.get("/api/voice-tune/profile/{preset_id}")
def api_voice_tune_profile_get(preset_id: str, request: Request):
    denied = _require_admin(request)
    if denied:
        return denied
    p = Store(DB_PATH).get_voice_preset(preset_id)
    return {"profile": (p or {}).get("naturalize_profile") if p else None}


@app.post("/api/voice-tune/profile/{preset_id}")
async def api_voice_tune_profile_save(preset_id: str, req: Request):
    """튜닝 작업대에서 완성한 프로파일을 프리셋에 동결 저장. 없는 preset_id면 작업대 임시 프리셋 생성."""
    denied = _require_admin(req)
    if denied:
        return denied
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


@app.get("/api/pron/global")
def api_pron_global_list(request: Request):
    denied = _require_admin(request)
    if denied:
        return denied
    d = pron_corrections.load(Store(DB_PATH))
    return {"entries": [{"phrase": k, "respelling": v} for k, v in d.items()]}


@app.post("/api/pron/global")
async def api_pron_global_save(request: Request):
    denied = _require_admin(request)
    if denied:
        return denied
    body = await request.json()
    phrase = (body.get("phrase") or "").strip()
    respelling = (body.get("respelling") or "").strip()
    if not phrase or not respelling or phrase == respelling:
        return JSONResponse({"error": "구절/재표기가 비었거나 동일합니다"}, status_code=400)
    store = Store(DB_PATH)
    d = pron_corrections.load(store)
    d[phrase] = respelling
    pron_corrections.save(store, d)
    return {"ok": True}


@app.delete("/api/pron/global/{phrase}")
def api_pron_global_delete(request: Request, phrase: str):
    denied = _require_admin(request)
    if denied:
        return denied
    store = Store(DB_PATH)
    d = pron_corrections.load(store)
    d.pop(phrase, None)
    pron_corrections.save(store, d)
    return {"ok": True}


@app.post("/api/pron/report")
async def api_pron_report(request: Request):
    denied = _require_admin(request)
    if denied:
        return denied
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "문장이 비었습니다"}, status_code=400)
    comment = (body.get("comment") or "").strip()
    created_at = datetime.now(timezone.utc).isoformat()
    rid = Store(DB_PATH).add_pron_report(text, comment, created_at)
    return {"ok": True, "id": rid}


@app.get("/api/pron/reports")
def api_pron_reports_list(request: Request):
    denied = _require_admin(request)
    if denied:
        return denied
    return {"reports": Store(DB_PATH).list_pron_reports()}


@app.post("/api/pron/reports/{report_id}/resolve")
def api_pron_report_resolve(request: Request, report_id: int):
    denied = _require_admin(request)
    if denied:
        return denied
    Store(DB_PATH).resolve_pron_report(report_id)
    return {"ok": True}


_PRON_SUGGEST_SCHEMA = {
    "type": "object",
    "properties": {"suggestions": {"type": "array", "items": {
        "type": "object",
        "properties": {"phrase": {"type": "string"}, "respelling": {"type": "string"},
                       "reason": {"type": "string"}},
        "required": ["phrase", "respelling"]}}},
    "required": ["suggestions"],
}


@app.post("/api/pron/suggest")
async def api_pron_suggest(request: Request):
    denied = _require_admin(request)
    if denied:
        return denied
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        return {"suggestions": []}
    prompt = (
        "다음 한국어 나레이션에서 TTS가 이어발음(연음)·발음을 어색하게 읽을 만한 구절을 찾아라. "
        "각 구절마다 성우가 자연스럽게 읽도록 소리 나는 대로 다시 쓴 '재표기'를 제시하라. "
        "예: '좋은데요'→'조은데요', '같이'→'가치'. 원문에 실제로 있는 구절만. 없으면 빈 배열.\n"
        f"나레이션: {text}\n출력은 스키마 JSON만."
    )
    result = edit_plan._vault_call(prompt, _PRON_SUGGEST_SCHEMA)
    if not result or not isinstance(result.get("suggestions"), list):
        return {"suggestions": []}
    # 원문에 실제로 있는 구절만 통과(환각 제거) + no-op 제거.
    out = [s for s in result["suggestions"]
           if s.get("phrase") and s.get("respelling")
           and s["phrase"] in text and s["phrase"] != s["respelling"]]
    return {"suggestions": out}


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
        "pace_mode": body.get("pace_mode", True),
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
def api_mix_video(job_id: str, dl: int = 0):
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job or not job.get("video_path") or not Path(job["video_path"]).exists():
        return JSONResponse(status_code=404, content={"ok": False})
    if dl:   # ?dl=1 → 첨부 다운로드(Content-Disposition attachment). 없으면 인라인 재생(기존).
        return FileResponse(job["video_path"], media_type="video/mp4",
                            filename=export_bundle.safe_name(job_id) + ".mp4")
    return FileResponse(job["video_path"])


# ── QR '폰으로 보내기' (2026-07-23) ──
# 흐름: 제작소(로그인됨)에서 /api/share/link/{job} 호출 → 단축링크+QR(SVG) 발급 → 화면에 QR 표시.
#       폰이 스캔 → /s/{sid}(로그인 불필요, 미들웨어 allowlist) → 영상+카톡공유 버튼.
@app.get("/api/share/link/{job_id}")
def api_share_link(job_id: str, request: Request):
    """완성 영상의 QR용 단축 공유링크+QR SVG 발급(로그인 필요 — 미들웨어 게이트 통과분만 도달)."""
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job or not job.get("video_path") or not Path(job["video_path"]).exists():
        return JSONResponse(status_code=404, content={"ok": False, "error": "완성 영상이 없어요"})
    sid = _share_put(job_id)
    if PUBLIC_BASE_URL:
        base = PUBLIC_BASE_URL.rstrip("/")
    else:
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        host = request.headers.get("host") or request.url.netloc
        base = f"{proto}://{host}"
    url = f"{base}/s/{sid}"
    try:
        qr = qr_svg.qr_svg(url)
    except Exception:
        qr = ""   # QR 실패해도 링크 텍스트로 폴백(프런트가 복사 UI 제공)
    return {"ok": True, "url": url, "qr_svg": qr}


@app.get("/api/share/v/{sid}")
def api_share_v(sid: str, dl: int = 0):
    """단축 id로 영상 스트리밍(로그인 불필요·저장소 조회). allowlist 경로."""
    job_id = _share_get(sid)
    if not job_id:
        return JSONResponse(status_code=403, content={"ok": False, "error": "링크가 만료됐어요"})
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job or not job.get("video_path") or not Path(job["video_path"]).exists():
        return JSONResponse(status_code=404, content={"ok": False})
    if dl:
        return FileResponse(job["video_path"], media_type="video/mp4",
                            filename=export_bundle.safe_name(job_id) + ".mp4")
    return FileResponse(job["video_path"], media_type="video/mp4")


def _selected_thumb_path(job):
    """6단계에서 고른 최종 썸네일(thumbnail_json.selected)의 실제 파일 경로. 없으면 None.

    ⚠️ selected는 사용자 입력이 아니라 서버가 지은 이름(api_thumb_save)이지만, DB를 통과한
    문자열이라 그대로 경로에 붙이지 않는다 — _thumb_dir과 같은 basename 봉인을 한 번 더 건다.
    """
    if not job:
        return None
    thumb = job.get("thumbnail") or {}
    name = thumb.get("selected")
    if not name or name != os.path.basename(name) or name in (".", ".."):
        return None
    d = _thumb_dir(job.get("job_id") or "")
    if d is None:                      # bad job_id — 경로순회 봉인(_thumb_dir이 None을 준다)
        return None
    p = d / name
    return p if p.exists() else None


@app.get("/api/share/t/{sid}")
def api_share_t(sid: str, dl: int = 0):
    """단축 id로 '선택 썸네일' PNG 서빙(로그인 불필요). 영상(/api/share/v)과 짝 — allowlist 경로.

    썸네일을 아직 안 골랐으면 404. 공유 페이지는 404를 받으면 썸네일 UI를 통째로 숨긴다
    (영상만 보내는 기존 동작으로 자연 폴백 — 여기서 500이 나면 공유 자체가 막힌다)."""
    job_id = _share_get(sid)
    if not job_id:
        return JSONResponse(status_code=403, content={"ok": False, "error": "링크가 만료됐어요"})
    p = _selected_thumb_path(Store(DB_PATH).get_mix_job(job_id))
    if not p:
        return JSONResponse(status_code=404, content={"ok": False, "error": "선택된 썸네일이 없어요"})
    fname = export_bundle.safe_name(job_id) + "_thumb.png"
    if dl:
        return FileResponse(str(p), media_type="image/png", filename=fname)
    return FileResponse(str(p), media_type="image/png")


@app.get("/s/{sid}", response_class=HTMLResponse)
def share_page(sid: str):
    """폰이 QR로 여는 모바일 공유 페이지(로그인 불필요). 폰 카톡 네이티브 공유로 전송.

    2026-08-04: 영상만 보내던 것을 **영상+선택 썸네일 한 번에**로. 썸네일이 없으면 __THUMB__을
    빈 문자열로 넘겨(페이지가 그걸로 판단) 예전과 똑같이 영상만 보낸다."""
    job_id = _share_get(sid)
    if not job_id:
        return HTMLResponse(_SHARE_EXPIRED_HTML, status_code=403)
    has_thumb = _selected_thumb_path(Store(DB_PATH).get_mix_job(job_id)) is not None
    return HTMLResponse(_SHARE_PAGE_HTML
                        .replace("__VID__", f"/api/share/v/{sid}")
                        .replace("__THUMB__", f"/api/share/t/{sid}" if has_thumb else ""))


@app.get("/api/mix/export/{job_id}")
def api_mix_export(job_id: str, part: str = ""):
    """캡컷 편집용 내보내기 ZIP(설계 2026-07-20 §2, T1). part=sources|srt|script면 그것만(개별
    다운로드), 없으면 전체(final·sources·tts·srt·script·seo·README). 유료게이트 deny-by-default가
    이 경로를 자동 차단하므로(FREE 목록에 없음) full 등급만 받는다. 없는 재료는 건너뛴다(500 금지)."""
    safe = os.path.basename(job_id)
    if not safe or safe != job_id:
        return JSONResponse(status_code=400, content={"ok": False})
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job or not job.get("edit_plan"):
        return JSONResponse(status_code=404, content={"ok": False, "error": "편집안이 아직 없습니다"})
    plan = job["edit_plan"]
    work = _MIX_WORK_DIR / job_id
    work.mkdir(parents=True, exist_ok=True)
    tts_paths = {b["beat_idx"]: b["tts_path"] for b in plan.get("beats", []) if b.get("tts_path")}
    try:
        source_video_paths = _resolve_sources(job, work)
    except Exception:
        source_video_paths = {}   # 소스 전멸이어도 srt/script/seo는 준다(설계 §6, 500 금지)
    timeline = _beat_timeline(plan, tts_paths)
    parts = {"sources": ["sources"], "srt": ["srt"], "script": ["script"]}.get(
        part, export_bundle.ALL_PARTS)
    final = job.get("video_path") if (job.get("video_path")
                                      and Path(job["video_path"]).exists()) else None
    out = work / f"export_{part or 'all'}.zip"
    export_bundle.build_export_zip(
        out, plan=plan, timeline=timeline, source_video_paths=source_video_paths,
        tts_paths=tts_paths, final_video=final, seo=job.get("seo"), parts=parts)
    fname = export_bundle.safe_name(job_id) + (f"_{part}" if part else "_capcut") + ".zip"
    return FileResponse(str(out), media_type="application/zip", filename=fname)


def _capcut_project_name(job_id, job, plan):
    """캡컷 프로젝트명 — 목록에서 알아보게 헤드카피(없으면 첫 대사)를 **앞**에 둔다.
    캡컷은 이름을 가운데 잘라 보여줘서(예: '쇼핑쇼츠_...169a1') job-id 해시만으론
    어느 게 방금 보낸 건지 구분이 안 됐다(2026-07-21 사장님 제보). 의미있는 제목을
    앞에 두고 짧은 id를 접미로 붙여 유일성만 남긴다. 최종 정제는 safe_project_name."""
    head = ((job.get("headcopy") or {}).get("text") or "").strip()
    if not head:
        beats = (plan or {}).get("beats") or []
        head = ((beats[0].get("narration") if beats else "") or "").strip()
    head = " ".join(head.split())[:24]
    return f"{head} {job_id[:4]}" if head else f"쇼핑쇼츠_{job_id[:8]}"


@app.get("/api/mix/capcut/{job_id}")
def api_mix_capcut(job_id: str, base: str = ""):
    """CapCut draft 매니페스트(설계 부록A, T2). base=캡컷이 draft를 볼 절대경로(프론트가 지정한
    캡컷 Drafts 폴더). 서버가 work/<job>/capcut/<project>/에 draft+에셋을 조립하고, draft_content.json·
    meta는 텍스트로 인라인, mp4/mp3는 asset URL로 돌려준다. 프론트가 File System Access API로
    사용자 캡컷 폴더에 <project>/를 만들고 이 파일들을 쓴다. deny-by-default 자동보호."""
    safe = os.path.basename(job_id)
    if not safe or safe != job_id:
        return JSONResponse(status_code=400, content={"ok": False})
    if not base.strip():
        return JSONResponse(status_code=400, content={"ok": False, "error": "캡컷 폴더 경로가 필요합니다"})
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job or not job.get("edit_plan"):
        return JSONResponse(status_code=404, content={"ok": False, "error": "편집안이 아직 없습니다"})
    plan = job["edit_plan"]
    work = _MIX_WORK_DIR / job_id
    tts_paths = {b["beat_idx"]: b["tts_path"] for b in plan.get("beats", []) if b.get("tts_path")}
    try:
        source_video_paths = _resolve_sources(job, work)
    except Exception:
        source_video_paths = {}
    # ★자막제거(2단계)를 했으면 캡컷도 '자막 없는' 청소본을 써야 한다 — 안 그러면 원본 자막이
    # 그대로 살아난다(2026-07-21 사장님 제보). clean_sources={video_id: 청소본}을 원본 위에 덮는다.
    for _vid, _cp in (job.get("clean_sources") or {}).items():
        if _cp and Path(_cp).exists():
            source_video_paths[_vid] = _cp
    timeline = _beat_timeline(plan, tts_paths)
    out_root = work / "capcut"
    out_root.mkdir(parents=True, exist_ok=True)
    proj, project, files = capcut_draft.assemble_draft_folder(
        out_root, base, plan=plan, timeline=timeline, source_video_paths=source_video_paths,
        tts_paths=tts_paths, project_name=_capcut_project_name(job_id, job, plan))
    texts, assets = {}, []
    for name in files:
        if name.endswith(".json"):
            texts[name] = (proj / name).read_text(encoding="utf-8")
        else:
            assets.append({"name": name, "url": f"/api/mix/capcut_asset/{job_id}/{name}"})
    return {"ok": True, "project": project, "texts": texts, "assets": assets}


@app.get("/api/mix/capcut_asset/{job_id}/{name}")
def api_mix_capcut_asset(job_id: str, name: str):
    """capcut 조립 폴더의 에셋(mp4/mp3) 서빙. 경로순회 차단 후 work/<job>/capcut/*/<name>."""
    safe_j, safe_n = os.path.basename(job_id), os.path.basename(name)
    if safe_j != job_id or safe_n != name:
        return JSONResponse(status_code=400, content={"ok": False})
    capdir = _MIX_WORK_DIR / job_id / "capcut"
    hits = list(capdir.glob(f"*/{safe_n}")) if capdir.exists() else []
    if not hits:
        return JSONResponse(status_code=404, content={"ok": False})
    return FileResponse(str(hits[0]))


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
    # 얹으니 배경 자막은 방해). clean_video_path(2단계 자막제거 완료 시 mix_pipeline.
    # run_clean_sources가 채운다, 2026-07-20)를 먼저 쓰고, preview_path(1단계 무료 미리보기)는
    # 그 다음, 최종 렌더(video_path)는 최후 폴백이다.
    # ⚠️preview_path는 자막이 없는 게 아니다 — run_preview가 clean_fn=None으로 늘 원본
    # 자막째 렌더한다(무료 미리보기니까). 2단계를 아직 안 밟았으면(clean_video_path 없음) 이
    # preview_path가 걸려 자막 있는 배경이 나온다 — 그건 "2단계 전"이라 맞는 동작이고, 2단계를
    # 밟았는데도 이게 걸리면 버그다(2026-07-20 사장님 제보가 정확히 이 케이스: clean_video_path가
    # 그때까지 아무도 안 채워서 늘 여기로 떨어졌었다).
    # 최종 렌더(video_path)는 우리 나레이션 자막이 박혀 있어(사장님 제보 2026-07-19) 배경 부적합.
    # 셋 다 검사하므로 렌더 전(video_path 없음)에도 preview로 프레임을 뽑을 수 있다
    # (매칭 끝낸 작업이라도 최종 영상이 없어 "믹스 영상 없음"으로 막히던 것도 그대로 해소).
    # ★자가치유: 2단계 자막제거는 했는데(clean_status=ready) 조립본(clean_video_path)이 없으면
    # 여기서 즉석 조립한다 — 이전 조립이 재렌더/재매칭 레이스로 유실됐을 수 있다(2026-07-21 사장님
    # 재제보: clean_status=ready·edit_plan 있음인데 clean_video_path=None으로 자막 preview가 걸렸음).
    # VMake는 이미 탔으니 추가과금 0. 실패하면 아래 폴백 그대로.
    _cvp = job.get("clean_video_path")
    if job.get("clean_status") == "ready" and not (_cvp and Path(_cvp).exists()):
        # 자가치유 조립은 ffmpeg를 태운다 — 실패(RuntimeError)나 배포 재시작으로 ffmpeg가
        # 죽으면(exit 255) 여기서 예외가 그대로 올라가 500이 났다(2026-07-22 실측). 그러면
        # 아래 preview/최종 폴백을 못 타고 프레임이 아예 안 나온다. 삼키고 폴백으로 넘긴다.
        try:
            if mix_pipeline.assemble_clean_video(job_id, DB_PATH, _MIX_WORK_DIR):
                job = Store(DB_PATH).get_mix_job(job_id)   # 새 clean_video_path 반영
        except Exception:
            pass   # 자막 없는 배경을 못 만들면 자막 있는 preview/최종으로라도 프레임을 낸다
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

    # ★이전 배경으로 만든 결과 표시(2026-08-03): 자막제거 전(preview 배경)에 생성한 썸네일이
    # 자막제거 후에도 갤러리에 남는다 — 데이터는 사장님 소유라 안 지우고, 어떤 결과가 지금
    # 배경과 다른 영상에서 나왔는지 이름 목록으로 알려 화면이 ⚠️ 표시를 붙이게 한다.
    # result_sigs가 없는 옛 결과는 확인 불가라 전부 '이전 영상'으로 본다(정확히 이번 사고 케이스).
    def _stale_results():
        rs = thumb.get("result_sigs") or {}
        return [n for n in (thumb.get("results") or []) if rs.get(n) != video_sig]

    existing = sorted(out_dir.glob("grid_*.jpg")) if out_dir.exists() else []
    if existing and thumb.get("video_sig") == video_sig:
        meta = thumb.get("frames") or []
        if len(meta) == len(existing):
            return {"ok": True, "frames": meta, "stale_results": _stale_results()}

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

    # ★캐시버스터 ?v=(2026-07-30) — grid_{i:02d}.jpg는 n=10 고정의 **결정적 파일명**이라
    # 재추출이 같은 파일을 덮어쓴다. api_thumb_file(FileResponse)은 Cache-Control을 안 붙이므로
    # (실측: last-modified·etag만) 브라우저가 재검증 없이 옛 이미지를 그대로 보여줄 수 있다 →
    # "자막제거 했는데 자막 있는 프레임이 뜬다"(사장님 제보 2026-07-30). 배경 영상이 바뀌면
    # video_sig가 바뀌므로 URL도 바뀌어 브라우저가 새로 받는다. 같은 화면의 자막제거
    # BEFORE/AFTER 썸네일은 이미 ?t=Date.now()로 캐시를 깨고 있었는데 여기만 빠져 있었다.
    _bust = video_sig.replace(":", "-")
    frames = [{"url": f"/api/produce/thumb/file/{job_id}/{p.name}?v={_bust}", "ts": round(ts, 2)}
              for p, ts in pairs]
    thumb["frames"] = frames
    thumb["video_sig"] = video_sig
    Store(DB_PATH).update_mix_job(job_id, thumbnail=thumb)
    return {"ok": True, "frames": frames, "stale_results": _stale_results()}


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
    # no-cache = "쓰기 전에 반드시 재검증"(no-store 아님 — etag가 같으면 304로 싸게 끝난다).
    # 파일명이 결정적(grid_00.jpg)이라 재추출이 같은 이름을 덮어쓰는데, Cache-Control이 없으면
    # 브라우저가 휴리스틱 캐시로 옛 이미지를 재검증 없이 내보낸다(2026-07-30 자막제거 제보).
    # 위 ?v= 캐시버스터와 이중 방어 — 버스터가 안 붙은 옛 URL(DB에 저장된 frames)도 살린다.
    return FileResponse(str(path), headers={"Cache-Control": "no-cache"})


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
    # ★결과별 배경 서명(2026-08-03 사장님 제보): 자막제거 전 preview 배경으로 만든 썸네일이
    # 자막제거 후에도 갤러리에 그대로 남아 "자막지우기 했는데 자막이 남아있다"가 됐다.
    # 생성 시점의 배경 서명(video_sig — frames 추출이 최신으로 유지)을 결과마다 기록해,
    # 배경이 바뀌면(api_thumb_frames가 대조) 옛 결과에 표시할 수 있게 한다.
    if thumb.get("video_sig"):
        thumb.setdefault("result_sigs", {})[name] = thumb["video_sig"]
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


@app.get("/api/produce/thumb/selected/{job_id}")
def api_thumb_selected(job_id: str):
    """8단계(최종렌더)가 '지금 고른 썸네일'을 물어보는 곳(2026-08-04).

    THUMB_STATE는 페이지 메모리라 새로고침·작업복원 후엔 비어 있다. 8단계는 DB를 진실로 삼는다.
    안 골랐으면 200 + {ok:true, name:null} — 404를 쓰면 프런트가 오류로 오인해 카드가 깨진다."""
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"ok": False, "error": "job 없음"})
    p = _selected_thumb_path(job)
    if not p:
        return {"ok": True, "name": None, "url": None}
    name = (job.get("thumbnail") or {}).get("selected")
    return {"ok": True, "name": name,
            "url": f"/api/produce/thumb/file/{job_id}/{name}"}


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
                        "xhscdn.com",
                        # 도우인 커버 CDN(pN-sign.douyinpic.com) — 해외HOT 도우인 카드 썸네일.
                        # 없으면 도우인 카드가 검게 깨짐(실측 2026-07-26).
                        "douyinpic.com",
                        # ★구글 렌즈 결과 썸네일(encrypted-tbnN.gstatic.com) — 숏템파워검색.
                        # 렌즈(SerpApi visual_matches)의 thumbnail은 플랫폼 CDN이 아니라
                        # **구글이 재호스팅한 gstatic 주소**다. 화이트리스트에 없어서 /api/thumb가
                        # 400을 뱉었고, 카드가 통째로 검게 떴다(실측 2026-08-09 서버로그:
                        # "GET /api/thumb?url=...encrypted-tbn0.gstatic.com... 400 Bad Request" 40건).
                        # 유튜브·인스타 결과만 검게 보인 이유도 이것 — 틱톡 결과는 렌즈가
                        # 원본 tiktokcdn 주소를 주는 경우가 있어 우연히 통과했다.
                        "gstatic.com")
_ALLOWED_VIDEO_HOSTS = ("cdninstagram.com", "fbcdn.net")


@app.get("/api/thumb64")
def api_thumb64(url: str):
    """썸네일을 data: URL(JSON)로 — 인스타 담기 스크립트의 렌즈 오버레이용(2026-08-03).
    인스타 페이지 CSP img-src가 외부 이미지를 전부 막아 <img src=외부CDN>이 깨진다.
    data:는 허용되므로 서버가 받아 base64로 감싸 주고, 스크립트는 GM 브리지로 이
    JSON을 받아 src에 넣는다. 렌즈 결과엔 구글 캐시(gstatic) 썸네일이 많아 허용호스트에
    gstatic·googleusercontent를 추가로 얹는다(프록시 남용 방지 화이트리스트는 유지)."""
    import base64
    import requests
    allowed = _ALLOWED_THUMB_HOSTS + ("gstatic.com", "googleusercontent.com")
    if _reject_cdn_proxy(url, allowed):
        return JSONResponse(status_code=400, content={"ok": False, "error": "invalid host"})
    ref = "https://www.instagram.com/"
    if "xhscdn.com" in url:
        ref = "https://www.xiaohongshu.com/"
    elif "tiktokcdn" in url:
        ref = "https://www.tiktok.com/"
    elif "douyinpic.com" in url:
        ref = "https://www.douyin.com/"
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0", "Referer": ref})
        r.raise_for_status()
        ctype = (r.headers.get("Content-Type") or "image/jpeg").split(";")[0]
        if not ctype.startswith("image/"):
            ctype = "image/jpeg"
        return {"ok": True, "data": "data:" + ctype + ";base64," +
                base64.b64encode(r.content).decode()}
    except Exception:
        return JSONResponse(status_code=502, content={"ok": False, "error": "fetch 실패"})


# 썸네일 디스크 캐시(2026-08-09). CDN 서명토큰(oe)이 ~4일에 만료돼 오래된
# 아카이브 썸네일이 전부 403 → 역대 히트작 카드가 까맣게 죽었다(실측).
# 키 = URL path의 파일명 — 토큰이 갱신돼도 파일명은 같아서 재수집 없이도 맞는다.
_THUMB_CACHE_DIR = Path(__file__).parent / "data" / "thumb_cache"


def _thumb_cache_path(url: str):
    try:
        name = (urllib.parse.urlparse(url).path or "").rsplit("/", 1)[-1]
    except ValueError:
        return None
    if not name or len(name) > 200:
        return None
    import hashlib
    return _THUMB_CACHE_DIR / (hashlib.sha1(name.encode()).hexdigest() + ".jpg")


# 인스타 웹이 자기 자신도 쓰는 공개 앱ID(비밀 아님) — oembed 호출에 필요.
# instagram_playwright._IG_APP_ID와 같은 값이지만, app.py가 그 모듈(=playwright 의존)을
# 끌어오지 않게 여기 따로 둔다.
_IG_OEMBED_APP_ID = "936619743392459"


def _thumb_via_oembed(url: str, shortcode: str | None):
    """만료된 썸네일 URL → 공개 oembed로 새 주소를 받아 내려받고 디스크 캐시에 저장.

    성공하면 이미지 bytes, 실패하면 None. **로그인이 필요 없다**는 게 핵심 —
    계정이 전부 429(한도소진)여도 동작한다(실측 2026-08-09).
    shortcode가 없으면 복구 불가(어느 게시물인지 알 수 없다) → None.
    """
    if not shortcode:
        return None
    import requests
    try:
        j = requests.get("https://www.instagram.com/api/v1/oembed/",
                         params={"url": f"https://www.instagram.com/p/{shortcode}/"},
                         headers={"User-Agent": "Mozilla/5.0",
                                  "x-ig-app-id": _IG_OEMBED_APP_ID},
                         timeout=6).json()
        fresh = j.get("thumbnail_url")
        if not fresh:
            return None
        r = requests.get(fresh, timeout=6, headers={
            "User-Agent": "Mozilla/5.0", "Referer": "https://www.instagram.com/"})
        r.raise_for_status()
        if not r.content[:2] == b"\xff\xd8":     # JPEG가 아니면 버린다(에러 HTML 방지)
            return None
        # 캐시 키는 **원래 URL**의 파일명 — 화면이 그 키로 찾으므로 여기 맞춰 저장해야 한다.
        cache = _thumb_cache_path(url)
        if cache is not None:
            try:
                _THUMB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                tmp = cache.with_suffix(".tmp")
                tmp.write_bytes(r.content)
                tmp.replace(cache)
            except OSError:
                pass
        return r.content
    except Exception:   # noqa: BLE001 — 복구는 best-effort, 실패하면 그냥 404로 떨어진다
        return None


@app.get("/api/thumb")
def api_thumb(url: str, v: str | None = None, shortcode: str | None = None):
    """인스타 CDN 썸네일 프록시 (핫링크 차단 우회). url=원본 이미지 주소.

    v = 캐시버스터(프론트 THUMB_V). 서버 동작엔 안 쓰지만 **받아는 줘야 한다** —
    선언이 없으면 FastAPI가 무시할 뿐이라 무해하지만, 명시해 두면 의도가 드러나고
    나중에 누가 `extra="forbid"`류를 걸어도 안 깨진다. 값은 URL을 다르게 만들어
    브라우저가 옛 404를 재사용하지 못하게 하는 게 전부다."""
    import requests
    from fastapi.responses import Response
    if _reject_cdn_proxy(url, _ALLOWED_THUMB_HOSTS):
        return Response(status_code=400, content=b"invalid host")
    cache = _thumb_cache_path(url)
    if cache is not None and cache.exists():
        return Response(content=cache.read_bytes(), media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})
    # 호스트에 맞는 Referer로 핫링크 차단을 우회한다. xhscdn은 인스타 referer로도 200이
    # 오지만(실측), 만료토큰형 URL 대비 정확한 출처를 보낸다. tiktok도 자기 도메인으로.
    ref = "https://www.instagram.com/"
    if "xhscdn.com" in url:
        ref = "https://www.xiaohongshu.com/"
    elif "tiktokcdn" in url:
        ref = "https://www.tiktok.com/"
    elif "douyinpic.com" in url:
        ref = "https://www.douyin.com/"
    try:
        # timeout 15 → 6 (2026-08-04). 이 라우트는 sync def라 uvicorn 스레드풀에서 돈다.
        # 역대 히트작이 한 화면에 200장을 요청하면 느린 CDN 응답 하나가 스레드를 15초씩
        # 붙잡아 풀이 마르고, 그 사이 들어온 다른 요청까지 밀려 systemd가 timeout으로
        # 서비스를 죽였다(실측 02:15 'Failed with result timeout' → 재시작 → 썸네일 전멸).
        # 썸네일 한 장에 6초를 넘길 이유가 없다 — 넘으면 그 장만 포기하는 게 낫다.
        r = requests.get(url, timeout=6, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": ref,
        })
        r.raise_for_status()
        ctype = r.headers.get("Content-Type", "image/jpeg")
        if cache is not None and ctype.startswith("image/"):
            try:
                _THUMB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                tmp = cache.with_suffix(".tmp")
                tmp.write_bytes(r.content)
                tmp.replace(cache)
            except OSError:
                pass    # 캐시 실패는 서빙에 영향 없음
        return Response(content=r.content, media_type=ctype,
                        headers={"Cache-Control": "public, max-age=86400"})
    except Exception:
        # ★만료 자가복구(2026-08-09): CDN 서명(oe=)은 ~4일이면 만료돼 저장된 URL이 전부
        # 403이 된다. 그런데 **게시물 자체는 살아 있으므로** 공개 oembed에 물어보면 인스타가
        # 서명이 새로 붙은 주소를 알려준다 — 로그인 불필요라 계정이 429여도 된다(실측
        # 2026-08-09: 계정 4개가 전부 429인 상태에서 75건 중 66건 복구).
        # 파일명은 그대로라 디스크 캐시 키(_thumb_cache_path)가 바뀌지 않는다 = 다음부터는
        # 위쪽 캐시히트로 즉시 나간다.
        got = _thumb_via_oembed(url, shortcode)
        if got:
            return Response(content=got, media_type="image/jpeg",
                            headers={"Cache-Control": "public, max-age=86400"})
        # ★실패는 절대 캐시하지 않는다(2026-08-09). 헤더가 없으면 브라우저가 휴리스틱
        # 캐싱으로 이 404를 몇 시간 기억한다. 그 뒤 우리가 이미지를 복구해 디스크 캐시에
        # 넣어도 **브라우저가 재요청을 안 해** 카드가 계속 까맣게 남는다(실측: 서버는
        # 200/71KB를 주는데 화면만 검은 상태). URL이 글자까지 같아 캐시버스팅도 안 먹는다.
        return Response(status_code=404, content=b"",
                        headers={"Cache-Control": "no-store"})


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
    _over = _lens_quota_guard(store, month)
    if _over:
        return _over
    # 유료게이트: 전역 상한(다계정이 SerpApi를 태우는 것 실차단) → 계정별 일일 상한.
    cid = getattr(request.state, "customer_id", 0)
    if _global_over_cap("lens"):
        return JSONResponse(status_code=429, content={
            "ok": False, "error_code": "global_limit",
            "error": "지금 이용이 많아 렌즈 검색이 잠시 막혔어요. 잠시 후 다시 시도해 주세요."})
    if not check_and_count(cid, "lens"):
        return JSONResponse(status_code=429, content={
            "ok": False, "error_code": "daily_limit",
            "error": "오늘 렌즈 검색 횟수를 다 썼어요. 결제하면 더 쓸 수 있어요."})
    _denied = _charge_or_402(cid, pricing.OP_LENS, keyroute.SVC_SERPAPI)
    if _denied:
        return _denied
    global_incr_and_alert("lens")
    try:
        raw = await frame.read()
        # Google Lens는 갓 호스팅된 우리서버 이미지를 인덱싱 전이라 못 읽어 0개를 준다(실측).
        # imgbb·imgur은 Google이 상시 크롤링하는 도메인이라 즉시 매칭 → imgbb(전용키) 1순위,
        # imgur(공유 공개ID) 2순위로 업로드, 실패 시에만 우리서버 URL 폴백(2026-07-14).
        # ★ to_thread — imgbb/imgur 업로드는 블로킹 requests다. 루프에서 그냥 부르면
        #   프론트가 동시에 던진 비전 요청(/api/lens/yt·/cn/keywords)이 뒤에서 굶는다.
        image_url = await asyncio.to_thread(upload_frame, raw)
        if not image_url:
            work_dir = _FIND_TMP_DIR / "lens"
            work_dir.mkdir(parents=True, exist_ok=True)
            name = uuid.uuid4().hex + ".jpg"
            (work_dir / name).write_bytes(raw)
            image_url = f"{PUBLIC_BASE_URL}/api/find/frame/lens/{name}"
        diag = {}
        # SerpApi 호출도 블로킹(+빈결과 재시도 2.5초×3) — 스레드로 뺀다. _lens_finalize는
        # DB 조회뿐(같은 스레드 sqlite 제약)이라 루프에 남긴다.
        rows = await asyncio.to_thread(
            functools.partial(search_similar_videos, image_url,
                              api_key=_lens_api_keys(cid),
                              source_caption=source_caption, stats=diag))
        items = _lens_finalize(rows, store)
        store.bump_lens(month)
        # diag: 인스타 결과가 0/왕창으로 튀는 이유를 화면에서 갈라 보기 위한 계측(2026-08-14).
        return {"ok": True, "items": items, "count": len(items), "diag": diag}
    except Exception:
        refund_credit(cid, "lens")   # 업로드·검색 실패 → 예약한 크레딧 되돌림(성공한 검색만 과금)
        _refund_points(cid, pricing.OP_LENS, keyroute.SVC_SERPAPI)
        raise


# 유튜브는 서버(데이터센터 IP)에서 yt-dlp가 봇차단(쿠키 요구)이라 영상 다운로드가 막힌다
# (2026-07-19 실측). 렌즈는 이미지 1장이면 되므로 공개 썸네일(i.ytimg.com — 구글 CDN이라
# 렌즈가 즉시 읽음)을 다운로드 없이 쓴다.
_YT_ID_RE = re.compile(r"(?:youtube\.com/(?:shorts/|watch\?v=|live/|embed/)|youtu\.be/)([A-Za-z0-9_-]{6,})")

# 렌즈 결과 후처리(2026-08-10 사장님) — 렌즈 검색·유사영상찾기 두 엔드포인트가 공유하는
# 단일 지점(0순위-B). ①인스타 항목을 우리 랭킹 DB(channel_archive·reel_history·
# reel_durations)로 보강해 조회수·좋아요·댓글·게시일·길이·채널을 채우고 ②인스타를
# 맨 위로 정렬한다(같은 플랫폼끼리는 렌즈 유사도 순서 유지 = 안정 정렬).
_IG_SC_RE = re.compile(r"instagram\.com/(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)")
_LENS_DURFILL_LAST = 0.0   # 렌즈발 길이 백필 예약 게이트(10분) — _DURFILL_LAST와 같은 결


def _lens_finalize(items, store):
    try:
        sc_of = {}
        for it in items:
            if it.get("platform") == "instagram":
                m = _IG_SC_RE.search(it.get("url") or "")
                if m:
                    sc_of[id(it)] = m.group(1)
        codes = list(set(sc_of.values()))
        meta = store.lens_insta_meta(codes) if codes else {}
        durs = store.duration_map(codes) if codes else {}
        for it in items:
            sc = sc_of.get(id(it))
            if not sc:
                continue
            m = meta.get(sc) or {}
            for k in ("views", "likes", "comments", "channel", "posted_at"):
                if it.get(k) in (None, "") and m.get(k) not in (None, ""):
                    it[k] = m[k]
            if it.get("duration") in (None, "") and durs.get(sc):
                it["duration"] = durs[sc]
        # ★못 채운 길이는 백필을 예약한다(2026-08-11 사장님 제보 "렌즈 ⏱ 안 나옴").
        #   렌즈 결과는 랭킹 피드·아카이브 밖 영상이 대부분이라 durfill의 _targets 스캔으론
        #   영원히 대상이 안 됐다 — 캐시에 있던 것만 우연히 떴다. 여기서 명시 코드로 예약해
        #   다음 검색부터 뜨게 한다(이번 응답엔 못 싣는다 — 크롤은 비동기).
        #   10분 게이트 + 20건 상한: 조회 경로가 크롤을 몰아치지 않게(_attach_durations와 같은 결).
        missing = [sc for sc in codes if sc not in durs]
        global _LENS_DURFILL_LAST
        if missing and time.time() - _LENS_DURFILL_LAST > 600:
            _LENS_DURFILL_LAST = time.time()
            store.enqueue("durfill", {"codes": missing[:20]})
    except Exception:                       # noqa: BLE001 — 보강 실패로 검색을 죽이지 않는다
        import sys as _sys
        import traceback as _tb
        _tb.print_exc(file=_sys.stderr)
    items.sort(key=lambda i: 0 if i.get("platform") == "instagram" else 1)
    return items


def _lens_image_for_url(url, work_dir, hint_t=None):
    """URL → (구글렌즈에 넣을 공개 이미지 URL, 캡션). 실패 시 (None, '').
    유튜브=썸네일 직행(봇차단 회피). 비유튜브=download_any 프레임(hint_t초, 없으면 중간),
    실패 시 oEmbed 썸네일 폴백. hint_t는 시크바가 가리키던 '보고 있던 장면'(2026-08-03)."""
    m = _YT_ID_RE.search(url)
    if m:
        vid = m.group(1)
        # maxres(풀 9:16 프레임)가 있으면 그걸 쓴다 — hqdefault는 480x360에 검은 레터박스가
        # 껴서 구글렌즈 매칭이 자주 0건이다(2026-07-19 실측). maxres 없으면 hqdefault 폴백.
        for q in ("maxresdefault", "hqdefault"):
            u = f"https://i.ytimg.com/vi/{vid}/{q}.jpg"
            try:
                if requests.head(u, timeout=6).status_code == 200:
                    return u, ""
            except Exception:  # noqa: BLE001
                pass
        return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg", ""
    try:
        video_path, caption = download_any(url, str(work_dir))
        dur = frame_extract._probe_duration(video_path) or 2.0
        name = uuid.uuid4().hex + ".jpg"
        ts = dur / 2
        if hint_t is not None and hint_t >= 0:
            ts = min(max(hint_t, 0.0), max(dur - 0.5, 0.0))   # 영상 끝 넘어가면 클램프
        frame = extract_frame_at(video_path, work_dir, ts, filename=name)
        if frame:
            raw = Path(frame).read_bytes()
            image_url = upload_frame(raw)   # imgbb/imgur 우선(구글 상시 크롤)
            if not image_url:
                lens_dir = _FIND_TMP_DIR / "lens"
                lens_dir.mkdir(parents=True, exist_ok=True)
                (lens_dir / name).write_bytes(raw)
                image_url = f"{PUBLIC_BASE_URL}/api/find/frame/lens/{name}"
            return image_url, caption
    except Exception as e:  # noqa: BLE001 — 다운로드 실패(봇차단·만료) → 썸네일 폴백
        print(f"lens trace_url download 실패, 썸네일 폴백: {e!r}")
    try:
        meta = probe_grab_meta(url) or {}
        if meta.get("thumbnail"):
            return meta["thumbnail"], meta.get("title") or ""
    except Exception:  # noqa: BLE001
        pass
    return None, ""


@app.post("/api/lens/trace_url")
def api_lens_trace_url(request: Request, body: dict):
    """영상 URL 붙여넣기 → 대표(중간) 프레임 → 구글렌즈 → 원본/유사 레퍼런스 영상.
    /api/lens/search와 같은 월 호출가드·같은 결과형태(ok/items/count)를 쓴다 — 입력만
    '프레임 업로드'가 아니라 'URL'이다. download_any가 유튜브·틱톡·인스타·샤오홍슈를
    받으므로 해외 재해설 쇼츠의 원본을 역추적하는 용도. SerpApi 100회/월 절약을 위해
    URL당 프레임 1장(중간지점)·1검색만 쓴다."""
    url = (body.get("url") or "").strip()
    if not url:
        return JSONResponse(status_code=422, content={"ok": False, "error": "url 필요"})
    blocked = _ssrf_guard(url)   # download_any가 이 URL을 그대로 받는다
    if blocked:
        return blocked
    store = Store(DB_PATH)
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    _over = _lens_quota_guard(store, month)
    if _over:
        return _over
    # 유료게이트: trace_url도 /api/lens/search와 같은 SerpApi 비용 → 같은 lens 크레딧을 건다
    # (전역 실차단 → 계정 일일). 여기가 비어 있으면 lens 일일상한을 우회하는 구멍이 된다.
    cid = getattr(request.state, "customer_id", 0)
    if _global_over_cap("lens"):
        return JSONResponse(status_code=429, content={
            "ok": False, "error_code": "global_limit",
            "error": "지금 이용이 많아 렌즈 검색이 잠시 막혔어요. 잠시 후 다시 시도해 주세요."})
    if not check_and_count(cid, "lens"):
        return JSONResponse(status_code=429, content={
            "ok": False, "error_code": "daily_limit",
            "error": "오늘 렌즈 검색 횟수를 다 썼어요. 결제하면 더 쓸 수 있어요."})
    _denied = _charge_or_402(cid, pricing.OP_LENS, keyroute.SVC_SERPAPI)
    if _denied:
        return _denied
    global_incr_and_alert("lens")
    ok = False
    try:
        work_dir = _FIND_TMP_DIR / "lens_trace"
        work_dir.mkdir(parents=True, exist_ok=True)
        # t(초): 인스타 담기 스크립트의 시크바가 '지금 보고 있는 장면'을 실어 보낸다
        # (2026-08-03). 없으면 종전대로 중간 프레임.
        try:
            hint_t = float(body.get("t")) if body.get("t") is not None else None
        except (TypeError, ValueError):
            hint_t = None
        image_url, caption = _lens_image_for_url(url, work_dir, hint_t=hint_t)
        if not image_url:
            return JSONResponse(status_code=502, content={
                "ok": False, "error": "영상/썸네일을 가져오지 못했습니다(봇차단·만료·미지원 URL)"})
        items = _lens_finalize(
            search_similar_videos(image_url, api_key=_lens_api_keys(cid),
                                  source_caption=caption), store)
        # 📕🎬 중국앱 키워드 후보(비전). 렌즈 유사영상은 프론트가 프레임으로 뽑지만 trace는
        # 프레임이 서버에만 있다(유튜브는 아예 썸네일 URL·caption 없음) → 서버가 image_url에서
        # 바이트를 받아 직접 만든다. cn_search_candidates는 image_bytes가 없으면 빈 리스트라
        # caption만으론 안 됨(2026-07-21 사장님 제보로 확인). Gemini 무료쿼터, 실패해도 무시.
        cn_cands = []
        try:
            img_bytes = requests.get(image_url, timeout=15).content
            cn_cands = (cn_search_candidates(img_bytes, caption) or {}).get("candidates", [])
        except Exception:
            pass
        store.bump_lens(month)
        ok = True
        return {"ok": True, "items": items, "count": len(items), "source_url": url,
                "caption": caption, "cn_candidates": cn_cands}
    finally:
        if not ok:
            refund_credit(cid, "lens")
            _refund_points(cid, pricing.OP_LENS, keyroute.SVC_SERPAPI)


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
                                source_caption: str = Form(""), exclude: str = Form("")):
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
    # exclude: 프론트 '🔄 다른 검색어'가 이미 보여준 후보를 개행으로 붙여 보낸다.
    seen = [s.strip() for s in (exclude or "").split("\n") if s.strip()][:20]
    try:
        # ★ to_thread 필수 — cn_search_candidates는 Gemini SDK를 **블로킹**으로 부른다.
        #   async def 안에서 그냥 부르면 이벤트루프가 그 5~10초 동안 통째로 멈춰,
        #   프론트가 동시에 던진 /api/lens/yt가 뒤에서 줄을 서 20초가 됐다(2026-08-16 실측).
        v = await asyncio.to_thread(cn_search_candidates, raw, source_caption, exclude=seen)
    except Exception:
        v = {}
    return {"ok": True, "product": v.get("product", ""),
            "candidates": v.get("candidates", [])}


@app.post("/api/lens/kw/expand")
async def api_lens_kw_expand(request: Request, keyword: str = Form(""),
                              exclude: str = Form(""), n: int = Form(6)):
    """한국어 소재어 → 검색어 조합 [{ko, zh}]. 프레임 불필요(2026-08-14 사장님).

    렌즈 후보는 화면 기반이라 '시금치 치아바타'처럼 사장님이 떠올린 소재는 새로고침해도
    안 나온다. 여기에 직접 넣으면 조합을 펼쳐 4개 플랫폼(인스타·틱톡·샤오홍슈·도우인)
    버튼으로 그린다. 한국어만 넣어도 중국어가 같이 나온다.
    Gemini 텍스트 모델 1회만 — Apify·SerpApi 비용 0."""
    kw = (keyword or "").strip()
    if not kw:
        return {"ok": True, "keyword": "", "candidates": []}
    seen = [s.strip() for s in (exclude or "").split("\n") if s.strip()][:20]
    try:
        cands = await asyncio.to_thread(expand_search_keywords, kw, n=n, exclude=seen)   # 블로킹 Gemini
    except Exception:                       # noqa: BLE001 — 실패해도 렌즈는 정상
        cands = []
    return {"ok": True, "keyword": kw, "candidates": cands}


@app.post("/api/lens/cn/search")
async def api_lens_cn_search(request: Request, keyword: str = Form(""),
                              max_results: int = Form(8)):
    """중국어 검색어 1개 → 샤오홍슈+도우인. **백엔드는 cn_search가 정한다**
    (Playwright 무료 우선 → 0건이면 Apify 폴백). 2026-08-17 통합.

    프론트는 어느 백엔드가 돌았는지 몰라도 되고, meta로 비용만 표시한다."""
    kw = (keyword or "").strip()
    if not kw:
        return {"ok": True, "items": [], "count": 0, "keyword": "", "meta": {}}
    n = max(1, min(int(max_results or 8), 60))
    # ★to_thread 필수 — 백엔드가 Playwright·Apify를 **블로킹**으로 부른다.
    #   안 하면 이벤트루프가 막혀 다른 렌즈 요청이 전부 굶는다(/api/lens/yt와 같은 이유).
    res = await asyncio.to_thread(cn_search.search, kw, n)
    for r in res["items"]:
        r["match"] = None          # 렌즈 카드 계약(제목 매칭은 프론트가 안 씀)
    return {"ok": True, **res}


@app.post("/api/lens/kw/search")
async def api_lens_kw_search(request: Request, keyword: str = Form(""),
                              max_results: int = Form(8)):
    """한국어 검색어 1개 → 인스타+틱톡+유튜브. **백엔드는 kw_search가 정한다.**
    2026-08-17 — 샤오홍슈·도우인(/api/lens/cn/search)을 마무리한 것과 같은 모양이다.

    유료게이트를 CN과 **같은 기준**으로 건다(틱톡이 Apify 유료라 공짜가 아니다).
    프론트는 어느 백엔드가 돌았는지 몰라도 되고, meta로 비용만 표시한다."""
    kw = (keyword or "").strip()
    if not kw:
        return {"ok": True, "items": [], "count": 0, "keyword": "", "meta": {}}
    n = max(1, min(int(max_results or 8), 60))
    # ★to_thread 필수 — 백엔드가 Playwright·Apify·HTTP를 **블로킹**으로 부른다.
    #   안 하면 이벤트루프가 막혀 다른 렌즈 요청이 전부 굶는다(cn/search와 같은 이유).
    res = await asyncio.to_thread(kw_search.search, kw, n)
    for r in res["items"]:
        r["match"] = None          # 렌즈 카드 계약(제목 매칭은 프론트가 안 씀)
    return {"ok": True, **res}


def _yt_keywords(subject_result, cn_result, caption):
    """유튜브 검색어 목록(최대 2개: 기본검색어 + 보조검색어)을 만든다.

    ★실측 A/B(사장님 라이브 썸네일 4건) — cn_search_keyword_vision의 product는
    샤오홍슈/도우인용 프롬프트라 '제품 특정(색·형태·브랜드)'을 요구해 유튜브에서
    과도하게 구체적인 복합어가 되어 결과가 없거나(강아지목욕: same0,no5) 엉뚱한
    영상을 잡았다. subject_tags_vision의 subject는 애초에 "검색어로 이 영상이
    잡히게" 만드는 게 목표라 전부 개선(수납침대 2→5건, 제모기 no3→no0).

    우선순위: subject → (실패시) product → (실패시) 캡션 앞토큰(_cn_keyword)
    ★기존 동작(product→캡션 폴백)은 그대로 보존 — subject 쪽이 실패해도 오늘보다
    나빠지지 않는다.
    """
    primary = (subject_result or {}).get("subject", "") or ""
    primary = primary.strip()
    if not primary:
        primary = ((cn_result or {}).get("product") or "").strip()
    if not primary:
        primary = _cn_keyword(caption)
    if not primary:
        return []
    keywords = [primary]
    for kw in (subject_result or {}).get("keywords") or []:
        kw = (kw or "").strip()
        if kw and kw != primary:
            keywords.append(kw)
            break
    return keywords


@app.post("/api/lens/yt")
async def api_lens_yt(request: Request, frame: UploadFile = File(None),
                       source_caption: str = Form(""), max_results: int = Form(12)):
    """프레임+캡션으로 유튜브를 키워드 검색해 렌즈 결과에 합류할 항목. YouTube Data API라
    무료(쿼터 내) → 월 호출가드 없음. 검색어는 subject_tags_vision의 subject(★2026-08-17
    변경 — "검색어로 이 영상이 잡히게"가 목표인 프롬프트라 유튜브에 맞다) → 실패 시
    cn_search_keyword_vision의 product(기존 동작 그대로 보존) → 캡션 앞토큰(_cn_keyword) 폴백.
    subject_tags_vision의 keywords 중 subject와 다른 첫 항목으로 보조 검색까지 돌려 커버리지를 넓힌다."""
    subject_result, cn_result = {}, {}
    if frame is not None:
        try:
            raw = await frame.read()
            # ★ to_thread — 아래 youtube_search와 함께 블로킹 호출이라 루프를 막는다
            #   (/api/lens/cn/keywords와 동시에 돌아야 렌즈가 빨리 뜬다, 2026-08-16)
            subject_result = await asyncio.to_thread(subject_tags_vision, raw, source_caption)
            if not (subject_result or {}).get("subject"):
                # 폴백도 비전 1회로 해결 — 프레임을 다시 읽을 필요 없이 같은 raw 재사용
                cn_result = await asyncio.to_thread(cn_search_keyword_vision, raw, source_caption)
        except Exception:
            subject_result, cn_result = {}, {}
    keywords = _yt_keywords(subject_result, cn_result, source_caption)
    if not keywords:
        return {"ok": True, "items": [], "count": 0, "note": "검색어를 만들지 못했습니다"}
    keyword = keywords[0]
    # ★상한 12 — 40개는 유튜브만 화면을 도배했다(실측 2026-08-16: 유튜브 43개인데
    #   틱톡 5·인스타 1·샤오홍슈 0·도우인 1). 아래 채점이 관련도순으로 정렬하므로
    #   위쪽 12개면 충분하다. 캐시된 옛 화면이 40을 보내도 여기서 잘린다.
    n = max(1, min(int(max_results or 12), 12))
    rows = []
    seen_urls = set()
    for kw in keywords:
        if len(rows) >= n:
            break
        try:
            # ★videoDuration=short(4분 미만) + relevanceLanguage=ko (2026-08-16 사장님 제보)
            #   예전엔 필터가 하나도 없어 일반 롱폼·외국어 영상까지 그대로 딸려왔다
            #   (실측: 유튜브 43개 vs 틱톡 5·인스타 1·샤오홍슈 0·도우인 1).
            #   둘 다 API가 공짜로 주는 파라미터라 쿼터·비용은 그대로다.
            part = await asyncio.to_thread(youtube_search.search, kw, max_results=n,
                                           duration="short", language="ko")
        except Exception:
            part = []
        for r in part:
            url = r.get("url")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            rows.append(r)
            if len(rows) >= n:
                break
    for r in rows:
        r["platform"] = "youtube"
        r["match"] = None

    # ★유사도 채점 — 샤오홍슈·도우인(/api/lens/cn/search)엔 원래 있는데 유튜브에만
    #   빠져 있었다. match가 전부 None이라 프론트의 '⚠️ 다른주제 숨기기'가 유튜브를
    #   **한 개도 못 걸렀다**(index.html은 match!==false만 거른다). 같은 함수를 그대로 쓴다.
    #   텍스트 전용 + 가벼운 모델(_TRANSLATE_MODEL) 1회라 비용은 0.5원 안쪽.
    #   (기본검색어=keyword 기준으로 채점 — 보조검색어로 찾은 결과도 같은 기준으로 잰다)
    if keyword and rows:
        try:
            verdicts = await asyncio.to_thread(
                judge_same_product, keyword, [r.get("title", "") for r in rows])
        except Exception:
            verdicts = []
        if len(verdicts) == len(rows):
            for r, vd in zip(rows, verdicts):
                r["sim"] = vd
                r["match"] = True if vd == "same" else (False if vd == "no" else None)
            rank = {"same": 0, "similar": 1, "no": 2}
            rows.sort(key=lambda r: rank.get(r.get("sim"), 1))   # 관련있는 것부터
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
# 인증은 비번(DASH_PASS) 또는 구글 OAuth 둘 중 하나라도 설정되면 ON(게이트 작동).
_AUTH_ON = bool(DASH_PASS) or bool(GOOGLE_CLIENT_ID)
if not _AUTH_ON:
    # ★fail-open 경고: DASH_PASS가 비면 인증·유료게이트가 통째로 꺼져 전원이 admin(full)로 열린다.
    #   로컬 개발은 의도지만, 운영 배포에서 env가 빠지면 유료기능·관리기능이 공개된다.
    import sys as _sys
    print("⚠️ [보안] DASH_PASS 미설정 → 인증·유료게이트 OFF(전원 full/admin). "
          "운영이면 DASH_PASS를 반드시 설정하세요.", file=_sys.stderr)
_AUTH_ALLOW = ("/login", "/api/login", "/signup", "/api/signup", "/favicon.ico", "/healthz",
               "/pay",   # 계좌입금 안내 페이지(공개 — 대기중·비로그인도 결제 안내 봄)
               "/terms", "/privacy", "/refund",   # 법적 고지(공개 — 비로그인·대기중도 열람)
               # PWA: 매니페스트는 브라우저가 쿠키 없이(credentials omit) fetch한다 → 공개 필수.
               "/manifest.webmanifest", "/apple-touch-icon.png",
               "/brand-logo.png",   # 로고(로그인·대문 락업) — 비로그인 화면에도 떠야 한다
               "/icon-192.png", "/icon-512.png", "/icon-maskable-512.png",
               "/insta_fill_comment.user.js",
               # 유저스크립트(insta_fill_comment)가 인스타 탭에서 전송 감지 시 GM_xmlhttpRequest로
               # 완료기록을 POST한다. 인증쿠키 없이 오므로 허용. 마킹은 저위험(되돌리기 가능).
               "/api/comment/done",
               # 원클릭 담기: /grab(북마클릿 설치안내)는 공개, /api/grab(팝업)은 자체적으로
               # 세션쿠키를 검증해 고객을 식별한다(_cid 폴백이 legacy라 여기선 직접 검증). 미들웨어
               # 401을 피해 친절한 팝업 응답을 주려고 allowlist에 둔다.
               # /grab_extension.zip(2026-08-04)도 공개 — 설치 안내가 로그인 전에 열리므로
               # 다운로드가 인증에 막히면 설치 자체를 시작할 수 없다.
               "/grab", "/api/grab", "/grab.user.js", "/grab_logic.js", "/grab_extension.zip",
               # 공용 좌측 네비 JS(2026-07-26): 모든 페이지가 <script src="/sidebar.js">로 사이드바를
               # 주입한다. 루트('/')에서 서빙돼 _FREE_PREFIX('/static/')에 안 걸려서, 무료(ranking_only)
               # 등급은 402·비로그인은 307로 막혀 사이드바(카테고리 메뉴)가 통째로 안 떴다(라이브 실증:
               # 무료 계정 홈PC에서 랭킹은 뜨는데 좌측 네비가 없음). 네비 링크만 그리는 무해한 JS이고
               # 잠긴 메뉴 클릭은 그 목적지 게이트가 여전히 막으므로 공개 허용.
               "/sidebar.js",
               # 구글 OAuth: 로그인 전(세션 없음)에 접근해야 하는 공개 경로.
               "/auth/google/login", "/auth/google/callback")
_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30일

# ── 유료게이트 deny-by-default (2026-07-19) ──
# ranking_only(무료/체험만료) 등급도 접근 가능한 경로 = 레퍼런스 랭킹 '조회' + 계정/정적.
# 나머지는 전부 402. 새 유료 엔드포인트를 추가해도 자동 차단(allowlist 방식이라 깜빡해도 안전).
# ⚠️ /api/reference는 '조회(GET)'만 무료 — /api/reference/register(등록·데이터변경)는 exact 매칭이라 제외.
#    /api/collect(수집=크롤 비용)도 제외 → 무료 등급은 마지막 수집 랭킹만 본다.
# 메서드 무관 무료(로그인 폼 POST 등) — 전부 정확 경로.
_FREE_EXACT_ANY = {"/login", "/signup", "/api/login", "/api/signup", "/logout"}
# GET만 무료(레퍼런스 랭킹 '조회') — POST/PUT 등 데이터변경은 같은 경로여도 차단.
_FREE_EXACT_GET = {"/", "/pricing", "/account", "/api/me", "/api/reference", "/api/thumb", "/api/video",
                   "/api/channel/history",   # 채널 히스토리='지난 한 달' 조회 = 랭킹 열람의 연장(무료 허용)
                   # ★2026-08-17 마이페이지(/settings)로 /account를 합치면서 함께 연다.
                   #   안 열면 무료 등급이 자기 계정·포인트를 못 본다 —
                   #   충전하려면 들어올 수 있어야 하는데 충전 화면이 유료 뒤에 있는 꼴이 된다.
                   #   ⚠️ GET만이다. 키 등록(POST /api/settings/keys)은 그대로 막힌다.
                   "/settings", "/api/settings/points", "/api/settings/keys"}
# 경계있는 prefix만(과다매칭 방지 — 트레일링 슬래시).
_FREE_PREFIX = ("/static/", "/auth/google/")


def _ranking_only_blocked(path: str, method: str = "GET") -> bool:
    """ranking_only 등급에게 이 경로를 막아야 하나. FREE 목록 외 전부 True(차단).
    GET 무료 경로는 POST 등으로 오면 막는다(method-aware)."""
    if path in _FREE_EXACT_ANY:
        return False
    if method == "GET" and path in _FREE_EXACT_GET:
        return False
    if any(path.startswith(p) for p in _FREE_PREFIX):
        return False
    if path in _AUTH_ALLOW or path.startswith("/api/find/frame/"):
        return False   # 유저스크립트 담기·favicon 등 기존 공개 경로(단 /api/grab은 핸들러서 등급확인)
    return True


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


# ── QR '폰으로 보내기' 단축 공유 (2026-07-23) ──
# PC 웹은 카톡 대화방에 mp4를 직접 못 넣는다(카톡 PC가 파일 붙여넣기 미지원). 그래서 완성 영상의
# '로그인 없이 열리는' 단기 링크를 QR로 띄운다 → 폰으로 스캔해 폰 카톡 네이티브 공유로 전송.
# ★URL을 짧게(/s/{8자}) 유지해야 QR이 v3(검증범위) 안에 든다 → 긴 서명토큰 대신 메모리 저장소에
#   짧은 id→(job,만료)를 담는다. 재기동 시 사라짐 = 24h 만료와 같은 성질(재발급하면 됨). 무상태 필요 없음.
_SHARE_TTL = 60 * 60 * 24  # 24시간
_SHARE_STORE: dict = {}    # sid -> (job_id, expiry_ts)


def _share_put(job_id: str) -> str:
    now = int(datetime.now(timezone.utc).timestamp())
    for k in [k for k, (_, e) in _SHARE_STORE.items() if e < now]:   # 만료 청소(누수 방지)
        _SHARE_STORE.pop(k, None)
    sid = secrets.token_urlsafe(6)   # ~8자
    _SHARE_STORE[sid] = (job_id, now + _SHARE_TTL)
    return sid


def _share_get(sid: str):
    v = _SHARE_STORE.get(sid)
    if not v:
        return None
    job_id, exp = v
    if int(datetime.now(timezone.utc).timestamp()) > exp:
        _SHARE_STORE.pop(sid, None)
        return None
    return job_id


_SHARE_PAGE_HTML = """<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>완성 영상 · 숏템메이커</title>
<style>
 *{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
 body{background:#0d0f12;color:#eef2f6;font-family:-apple-system,"Malgun Gothic",sans-serif;
      min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:20px 16px 40px}
 h1{font-size:19px;font-weight:800;margin:8px 0 4px;letter-spacing:1px}
 .sub{color:#8b93a7;font-size:13px;margin-bottom:16px}
 video{width:100%;max-width:420px;border-radius:16px;background:#000;box-shadow:0 12px 40px rgba(0,0,0,.5)}
 .media{width:100%;max-width:420px;display:flex;gap:10px;align-items:flex-start}
 .media video{flex:1 1 auto;min-width:0}
 .thumbwrap{flex:0 0 34%;display:none}
 .thumbwrap img{width:100%;display:block;border-radius:12px;background:#000;
      box-shadow:0 8px 24px rgba(0,0,0,.45)}
 .thumbcap{color:#8b93a7;font-size:11px;text-align:center;margin-top:5px;font-weight:700}
 .btns{width:100%;max-width:420px;margin-top:18px;display:flex;flex-direction:column;gap:12px}
 button,a.dl{font-size:19px;font-weight:800;border:0;border-radius:14px;padding:18px;text-align:center;
      text-decoration:none;cursor:pointer}
 #shareBtn{background:#fee500;color:#191600}
 a.dl{background:#1c2740;color:#dfe7f5}
 a.dl.sm{font-size:15px;padding:13px}
 .tip{color:#6b7488;font-size:12px;margin-top:14px;text-align:center;line-height:1.6;max-width:420px}
</style></head><body>
 <h1>완성 영상 📱</h1>
 <div class="sub" id="sub">아래 버튼으로 카톡·인스타에 바로 보내세요</div>
 <div class="media">
   <video src="__VID__" controls playsinline preload="metadata"></video>
   <div class="thumbwrap" id="thumbWrap">
     <img id="thumbImg" alt="썸네일">
     <div class="thumbcap">🖼 썸네일</div>
   </div>
 </div>
 <div class="btns">
   <button id="shareBtn">카톡·인스타로 보내기</button>
   <a class="dl" href="__VID__?dl=1" download>영상 저장(다운로드)</a>
   <a class="dl sm" id="thumbDl" href="#" download style="display:none">🖼 썸네일 저장(PNG)</a>
 </div>
 <div class="tip" id="tip">버튼을 누르면 공유창이 떠요. 카톡을 고르고 대화방을 선택하면 전송됩니다.<br>안 뜨면 '영상 저장' 후 갤러리에서 공유하세요.</div>
<script>
 const V="__VID__", T="__THUMB__";
 // 썸네일은 '있으면 얹는다'. 없거나(선택 안 함) 404면 예전 그대로 영상만 보낸다 —
 // 썸네일 때문에 공유 자체가 막히는 일은 없어야 한다.
 let THUMB_OK=false;
 if(T){
   const im=document.getElementById('thumbImg');
   im.addEventListener('load', ()=>{
     THUMB_OK=true;
     document.getElementById('thumbWrap').style.display='block';
     const dl=document.getElementById('thumbDl');
     dl.href=T+'?dl=1'; dl.style.display='block';
     document.getElementById('sub').textContent='영상 + 썸네일을 한 번에 보냅니다';
     document.getElementById('tip').innerHTML="버튼을 누르면 공유창이 떠요. 카톡을 고르고 대화방을 선택하면 <b>영상과 썸네일이 함께</b> 전송됩니다.<br>둘이 같이 안 가면 아래 저장 버튼으로 각각 받으세요.";
   });
   im.src=T;   // 404면 load가 안 뜨고 THUMB_OK=false로 남는다
 }
 document.getElementById('shareBtn').addEventListener('click', async ()=>{
   try{
     const r=await fetch(V); const b=await r.blob();
     const f=new File([b],'shopping_short.mp4',{type:'video/mp4'});
     // ① 영상+썸네일 동시 — 폰 카톡은 파일 여러 개 공유를 받는다. canShare로 먼저 물어보고,
     //    이 기기가 다중 파일을 거절하면 ②로 내려간다(무조건 시도하면 통째로 실패한다).
     if(THUMB_OK){
       try{
         const tr=await fetch(T);
         if(tr.ok){
           const tf=new File([await tr.blob()],'shopping_short_thumb.png',{type:'image/png'});
           if(navigator.canShare && navigator.canShare({files:[f,tf]})){
             await navigator.share({files:[f,tf], title:'완성 영상 + 썸네일'}); return;
           }
         }
       }catch(e){ if(e && e.name==='AbortError') return; }   // 취소는 폴백 금지(공유창 두 번 뜬다)
     }
     if(navigator.canShare && navigator.canShare({files:[f]})){   // ② 영상만(기존 동작)
       await navigator.share({files:[f], title:'완성 영상'}); return;
     }
     if(navigator.share){ await navigator.share({title:'완성 영상', url:location.href}); return; }
     location.href=V+'?dl=1';
   }catch(e){ if(e && e.name==='AbortError') return; location.href=V+'?dl=1'; }
 });
</script></body></html>"""

_SHARE_EXPIRED_HTML = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>링크 만료</title><style>body{background:#0d0f12;color:#eef2f6;font-family:-apple-system,"Malgun Gothic",sans-serif;
min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:24px}
h1{font-size:22px;margin-bottom:10px}p{color:#8b93a7;line-height:1.6}</style></head>
<body><h1>⏱ 링크가 만료됐어요</h1><p>공유 링크는 24시간만 유효해요.<br>제작소에서 QR을 다시 띄워 주세요.</p></body></html>"""


# ── 브랜드 토큰 (한 곳에 몰아둔다 — 이름 확정 시 여기 1곳만 교체) ──
# 이름 5안(ShortsFactory/Reelery/ShopReel/ShortsForge/Vidory) 중 사용자 확정 대기.
# 지금은 추천안 Reelery 플레이스홀더. 팔레트(민트×블랙)는 sidebar.js 계승·고정.
_BRAND = {
    "name": "숏템메이커",          # 확정(2026-07-20). 한글 주 + 영문 보조 락업.
    "name_en": "SHOTEMMAKER",     # 영문 CI(보조). 로고에 한글 밑 소문자 스페이싱으로.
    "glyph": "📦",
    "tagline": "쇼핑쇼츠, 이제 10분만에",   # 한줄문구(사장님 2026-07-25 확정)
    # 공개 페이지의 '카톡 문의' 링크(오픈채팅/채널 URL). 비면 /login으로 폴백 — 값만 넣으면 연결.
    "kakao": "",
}
# 구글 로고 SVG(로그인 버튼용) — 브랜드색과 무관한 구글 공식 4색.
_GOOGLE_SVG = ('<svg viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.6l6.8-6.8'
               'C35.6 2.4 30.2 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.1C12.4 13.3 17.7 9.5 24 9.5z"/>'
               '<path fill="#4285F4" d="M46.1 24.6c0-1.6-.1-3.1-.4-4.6H24v9.1h12.4c-.5 2.9-2.1 5.4-4.6 7'
               'l7.1 5.5c4.2-3.9 6.6-9.6 6.6-16z"/><path fill="#FBBC05" d="M10.5 28.3c-.5-1.4-.8-2.9-.8-4.3'
               's.3-2.9.8-4.3l-7.9-6.1C1 16.6 0 20.2 0 24s1 7.4 2.6 10.4l7.9-6.1z"/>'
               '<path fill="#34A853" d="M24 48c6.2 0 11.4-2 15.2-5.5l-7.1-5.5c-2 1.3-4.6 2.1-8.1 2.1'
               '-6.3 0-11.6-3.8-13.5-9.1l-7.9 6.1C6.5 42.6 14.6 48 24 48z"/></svg>')


# 시그니처 심볼 v4(2026-07-25) — ★사장님 선택: AI(nano-banana-pro) 생성 원본 그림을 그대로 쓴다.
# 모티프 = 쇼핑 바구니 안에 카메라 셔터+재생 원반이 담긴 형태(=담아서 영상으로 만든다).
# 앞서 내가 손으로 SVG를 짜서 밀어붙였는데 임팩트가 없었다. 사장님이 AI 원본을 골랐고,
# 내가 벡터로 재작도한 버전도 "원본이 좋다"고 해서 원본 픽셀을 유지한다.
#   전처리(scratchpad/make_icons.py): 네 모서리 flood fill로 '바깥 배경만' 투명화.
#   ★전역 색상매칭으로 지우면 바구니 몸통(#0d1424)이 배경과 거의 같아 구멍이 뚫린다 → 연결영역만.
#   그 뒤 그림 bbox로 크롭 + 여백 12% 정사각 패딩 → 1024 마스터에서 각 크기 LANCZOS 리샘플.
# 파일: static/brand-logo.png(96) · favicon.ico(16/32/48) · apple-touch-icon(180) · icon-192/512 ·
#       icon-maskable-512(안전영역 65% + 다크 배경 채움)
# ⚠️ /brand-logo.png 는 로그인 화면에서도 보여야 하므로 _AUTH_ALLOW에 넣어뒀다.
_LOGO_SVG = ('<img class="sym" src="/brand-logo.png" alt="숏템메이커" '
             'width="128" height="128" decoding="async">')


# 공개 페이지 하단 법적 고지 링크(약관·개인정보·환불). 모든 대문/로그인 푸터에 __LEGAL__로 주입.
_LEGAL_LINKS = ('<div style="margin-top:8px;font-size:12px">'
                '<a href="/terms" style="color:#7a9090;text-decoration:none">이용약관</a>'
                ' · <a href="/privacy" style="color:#7a9090;text-decoration:none">개인정보처리방침</a>'
                ' · <a href="/refund" style="color:#7a9090;text-decoration:none">환불정책</a></div>')


def _fill_brand(s: str) -> str:
    """대문·로그인 템플릿의 브랜드 플레이스홀더를 _BRAND로 채운다(모듈 로드 시 1회)."""
    return (s.replace("__LEGAL__", _LEGAL_LINKS)
             .replace("__NAME__", _BRAND["name"])
             .replace("__NAME_EN__", _BRAND["name_en"])
             .replace("__GLYPH__", _BRAND["glyph"])
             .replace("__TAGLINE__", _BRAND["tagline"])
             .replace("__KAKAO__", _BRAND.get("kakao") or "/login")
             .replace("__LOGO_SVG__", _LOGO_SVG)
             .replace("__GOOGLE_SVG__", _GOOGLE_SVG))


def _with_pay(html: str) -> str:
    """결제 CTA(__PAY_HREF__/__PAY_LABEL__)를 요청 시점에 채운다 — 설정 pay_url(외부 결제링크)이
    있으면 '결제하기', 없으면 카톡 문의로 폴백. 설정 변경이 재시작 없이 바로 반영되게 요청마다 읽는다."""
    st = Store(DB_PATH)
    pay = (st.get_setting("pay_url", "") or "").strip()
    bank = (st.get_setting("bank_account", "") or "").strip()
    kakao = (st.get_setting("contact_kakao", "") or _BRAND.get("kakao") or "/login").strip()
    # 우선순위: 외부 결제링크(pay_url) > 계좌입금 안내페이지(/pay, 계좌 설정 시) > 카톡 문의
    if pay:
        href, label = pay, "💳 결제하기 →"
    elif bank:
        href, label = "/pay", "💳 결제 안내"
    else:
        href, label = kakao, "카톡으로 문의"
    return html.replace("__PAY_HREF__", href).replace("__PAY_LABEL__", label)


# ── 공개 대문(랜딩) — 비로그인 방문자용. 민트×블랙, 한 페이지(B). ──
_LANDING_TMPL = """<!doctype html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<link rel=manifest href="/manifest.webmanifest"><meta name=theme-color content="#0c1411"><link rel=icon href="/favicon.ico"><link rel=apple-touch-icon href="/apple-touch-icon.png">
<title>__NAME__ — 쇼핑쇼츠, 이제 10분만에</title>
<link rel=preconnect href="https://fonts.googleapis.com">
<link rel=preconnect href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Black+Han+Sans&family=Noto+Sans+KR:wght@400;500;700;900&display=swap" rel=stylesheet>
<style>*{box-sizing:border-box;margin:0;padding:0}
:root{--mint:#6ff0d6;--grad:linear-gradient(135deg,#6ff0d6,#1f9e7a);--gold:#ffcf6f;--gold-grad:linear-gradient(135deg,#ffe1a1,#f0a93a);
--ink:#0b0f14;--panel:#111722;--line:#1e2735;--txt:#e8f0ee;--muted:#8aa0a0;--faint:#5f7373}
body{background:radial-gradient(1100px 600px at 82% -12%,rgba(111,240,214,.10),transparent 60%),radial-gradient(900px 500px at 0% 112%,rgba(255,207,111,.06),transparent 55%),var(--ink);
color:var(--txt);font-family:'Noto Sans KR',system-ui,sans-serif;line-height:1.6;-webkit-font-smoothing:antialiased;word-break:keep-all}
a{text-decoration:none;color:inherit}
.display{font-family:'Black Han Sans',sans-serif;font-weight:400;letter-spacing:.01em}
.wrap{max-width:1080px;margin:0 auto;padding:0 24px}
.nav{display:flex;align-items:center;justify-content:space-between;padding:22px 0}
.brand{display:flex;align-items:center;gap:10px}
/* 심볼은 글자보다 크면 무거워 보인다(사장님 2026-07-25) — 워드마크 22px 대비 27px로 낮췄다 */
.brand .sym{width:44px;height:44px;flex:none;animation:floaty 4s ease-in-out infinite}
.brand .wm{display:flex;flex-direction:column;line-height:1}
/* 워드마크 v3(2026-07-25): 민트→오로라 그라데이션 + 끝에 골드 마침점(브랜드 포인트).
   ::after 는 background-clip:text를 상속해 투명해지니 text-fill-color를 되돌려 금색을 살린다. */
.brand .nm{font-family:'Black Han Sans',sans-serif;font-size:22px;letter-spacing:-.4px;
  background:linear-gradient(135deg,#3ee0bf 0%,#7fe9d8 42%,#8c6ef0 100%);
  -webkit-background-clip:text;background-clip:text;color:transparent;
  -webkit-text-fill-color:transparent;filter:drop-shadow(0 0 10px rgba(62,224,191,.32))}
.brand .nm::after{content:'.';background:none;-webkit-text-fill-color:#facc6b;color:#facc6b;
  filter:none;margin-left:1px}
.brand .en{font-family:ui-monospace,monospace;font-size:9px;letter-spacing:2.8px;color:#4c8f85;margin-top:3px}
.nav .login{color:var(--txt);font-size:15.5px;font-weight:700;padding:7px 12px;border-radius:9px}
.nav .login:hover{color:var(--mint);background:rgba(111,240,214,.08)}
.nav .login.go{color:#062018;background:var(--grad)}
.nav .login.go:hover{filter:brightness(1.06);color:#062018;background:var(--grad)}
/* HERO — 가운데 정렬 */
.hero{text-align:center;max-width:760px;margin:0 auto;padding:60px 0 40px}
.badge{display:inline-block;font-size:12.5px;color:var(--mint);border:1px solid rgba(111,240,214,.3);border-radius:999px;padding:6px 15px;margin-bottom:22px;background:rgba(111,240,214,.06)}
.hero h1{font-size:clamp(34px,5.2vw,54px);line-height:1.14;letter-spacing:.01em}
.hero h1 .hl{background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.hero .sub{color:var(--muted);font-size:17px;margin:20px auto 30px;max-width:46ch}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:center;justify-content:center}
.cta{display:inline-flex;align-items:center;gap:8px;background:var(--grad);color:#062018;font-weight:700;font-size:16px;padding:15px 30px;border-radius:12px;border:0;cursor:pointer;box-shadow:0 8px 30px rgba(111,240,214,.18)}
.cta:hover{filter:brightness(1.06)}
.cta:not(.ghost){animation:ctaPulse 2.6s ease-in-out infinite}
.cta.ghost{background:transparent;color:var(--txt);border:1px solid var(--line);box-shadow:none;font-weight:600;animation:none}
.trust{color:var(--faint);font-size:12.5px;margin-top:16px}
.stats{display:flex;gap:12px;flex-wrap:wrap;justify-content:center;margin-top:30px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:15px 22px;min-width:120px}
.stat .num{font-family:'Black Han Sans',sans-serif;font-size:25px;background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.stat .lbl{color:var(--muted);font-size:12px;margin-top:2px}
.sec{padding:50px 0}
.sec h2{text-align:center;font-size:clamp(24px,3.4vw,30px);font-weight:900;margin-bottom:8px}
.sec .lead{text-align:center;color:var(--muted);margin-bottom:36px}
/* PAIN — 기존 3~5시간 vs 숏템메이커 10분 */
.vs{display:grid;grid-template-columns:1fr auto 1fr;gap:18px;align-items:stretch;max-width:860px;margin:0 auto}
.vs .col{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:26px 24px}
.vs .col.new{border-color:rgba(111,240,214,.35);box-shadow:0 0 0 1px rgba(111,240,214,.12) inset}
.vs .tag{font-size:12px;font-weight:700;letter-spacing:.04em;margin-bottom:16px}
.vs .old .tag{color:var(--muted)}.vs .new .tag{color:var(--mint)}
.vs ul{list-style:none;display:flex;flex-direction:column;gap:10px;margin-bottom:18px}
.vs li{font-size:14px;display:flex;gap:9px;align-items:flex-start}
.vs .old li{color:var(--muted)}.vs .old li .m{color:#e0623d;flex:none}
.vs .new li{color:var(--txt)}.vs .new li .m{color:var(--mint);flex:none}
.vs .time{font-family:'Black Han Sans',sans-serif;font-size:32px;line-height:1}
.vs .old .time{color:#d68b6f}.vs .new .time{background:var(--grad);-webkit-background-clip:text;color:transparent}
.vs .tl{font-size:12px;color:var(--faint);margin-top:5px}
.vs .arrow{display:flex;align-items:center;justify-content:center;color:var(--faint);font-size:26px}
/* MONEY — 수치화 */
.money{text-align:center;background:linear-gradient(180deg,rgba(255,207,111,.06),transparent);border:1px solid var(--line);border-radius:24px;padding:50px 24px}
.money .k{font-size:13px;letter-spacing:.04em;color:var(--gold);font-weight:700;margin-bottom:8px}
.money h2{font-size:clamp(23px,3.2vw,29px);font-weight:900;margin-bottom:30px}
.money .big{display:flex;gap:26px;justify-content:center;flex-wrap:wrap}
.money .m{min-width:150px}
.money .m .n{font-family:'Black Han Sans',sans-serif;font-size:52px;line-height:1;background:var(--gold-grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.money .m .n .u{font-size:24px}
.money .m .l{color:var(--muted);font-size:13.5px;margin-top:8px}
.money .note{color:var(--faint);font-size:13px;margin-top:26px;max-width:44ch;margin-left:auto;margin-right:auto}
.money .note b{color:var(--txt)}
.steps{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
.step{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:26px}
.step .n{width:34px;height:34px;border-radius:10px;background:rgba(111,240,214,.1);color:var(--mint);font-family:'Black Han Sans',sans-serif;font-size:17px;display:flex;align-items:center;justify-content:center;margin-bottom:14px}
.step h3{font-size:16px;font-weight:700;margin-bottom:6px}.step p{color:var(--muted);font-size:14px}
.feat{display:grid;grid-template-columns:repeat(2,1fr);gap:18px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:24px;display:flex;gap:16px}
.card .ic{font-size:24px;flex:none;line-height:1.2}
.card h3{font-size:16px;font-weight:700;margin-bottom:5px}.card p{color:var(--muted);font-size:14px}
.band{text-align:center;background:linear-gradient(180deg,rgba(111,240,214,.05),transparent);border:1px solid var(--line);border-radius:24px;padding:54px 24px;margin:44px 0 58px}
.band h2{font-size:clamp(24px,3.4vw,30px);font-weight:900;margin-bottom:10px}.band p{color:var(--muted);margin-bottom:26px}
.foot{text-align:center;color:var(--faint);font-size:12.5px;padding:0 0 42px}
/* 애니메이션 */
.reveal{opacity:0;transform:translateY(18px);transition:opacity .7s cubic-bezier(.2,.7,.2,1),transform .7s cubic-bezier(.2,.7,.2,1)}
.reveal.in{opacity:1;transform:none}
.d1{transition-delay:.06s}.d2{transition-delay:.14s}.d3{transition-delay:.22s}.d4{transition-delay:.3s}
/* 히어로(위쪽) 온로드 등장 — JS 없이 확실히 순차 재생 */
.rise{opacity:0;animation:riseIn .82s cubic-bezier(.2,.75,.2,1) both}
@keyframes riseIn{from{opacity:0;transform:translateY(26px)}to{opacity:1;transform:none}}
.r1{animation-delay:.08s}.r2{animation-delay:.2s}.r3{animation-delay:.34s}.r4{animation-delay:.48s}.r5{animation-delay:.6s}
.hero h1 .hl{background-size:220% auto;animation:sheen 3.2s linear infinite}
@keyframes sheen{to{background-position:220% center}}
@keyframes floaty{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}
@keyframes ctaPulse{0%,100%{box-shadow:0 8px 30px rgba(111,240,214,.18)}50%{box-shadow:0 10px 44px rgba(111,240,214,.44)}}
@media(prefers-reduced-motion:reduce){.reveal{opacity:1;transform:none;transition:none}.rise{opacity:1;animation:none}.brand .sym,.cta,.hero h1 .hl{animation:none}}
@media(max-width:760px){.vs{grid-template-columns:1fr}.vs .arrow{transform:rotate(90deg);padding:2px 0}.steps,.feat{grid-template-columns:1fr}.money .big{gap:18px}}
</style></head><body><div class=wrap>
<div class=nav>
<a class=brand href="/">__LOGO_SVG__<span class=wm><span class=nm>__NAME__</span><span class=en>__NAME_EN__</span></span></a>
<span style="display:flex;gap:10px;align-items:center"><a class=login href="/pricing">요금</a><a class="login go" href="/login">로그인</a></span></div>
<div class=hero>
<span class="badge rise r1">생각 0 · 편집 0 · 딱 10분</span>
<h1 class="display rise r2">머리 쓸 필요 없어요.<br>시키는 대로 <span class=hl>딸깍</span>, 10분이면 끝.</h1>
<p class="sub rise r3">쇼츠 하나 만들려고 3~5시간씩 붙잡고 계셨죠? 이제 뭘 팔지 고민할 것도 없어요. 지금 제일 잘 팔리는 걸 짚어주면 딸깍 — 대본·영상·목소리·자막까지 AI가 알아서. 60대도, 컴맹도 그대로 됩니다.</p>
<div class="row rise r4">
<a class=cta href="/login">무료로 시작하기 →</a>
<a class="cta ghost" href="/login">로그인</a></div>
<div class="trust rise r4">구글 계정으로 3초 시작 · 카드 없이 무료 체험</div>
<div class="stats rise r5">
<div class=stat><div class=num><span data-to=5>0</span>분</div><div class=lbl>하나 만드는 시간</div></div>
<div class=stat><div class=num>폰 하나</div><div class=lbl>필요한 장비 전부</div></div>
<div class=stat><div class=num>0</div><div class=lbl>배워야 할 편집기술</div></div></div></div>
<div class=sec>
<h2 class=reveal>쇼츠 하나에, 아직도 이 고생 하시나요?</h2>
<div class="lead reveal">남들이 반나절 붙잡고 있을 때, 사장님은 딸깍 한 번이면 됩니다</div>
<div class=vs>
<div class="col old reveal"><div class=tag>기존 방식</div>
<ul>
<li><span class=m>✕</span> 뭘 만들지 기획부터 고민</li>
<li><span class=m>✕</span> 잘 팔리는 소스 영상 찾아 헤매기</li>
<li><span class=m>✕</span> AI 툴 이것저것 켜서 대본·이미지</li>
<li><span class=m>✕</span> 캡컷으로 자르고 붙이고 자막 달기</li>
<li><span class=m>✕</span> 겨우 하나 올리면 진이 빠짐</li></ul>
<div class=time>3~5시간</div><div class=tl>영상 하나에 반나절, 머리는 지끈</div></div>
<div class=arrow>→</div>
<div class="col new reveal d1"><div class=tag>숏템메이커</div>
<ul>
<li><span class=m>✓</span> 지금 제일 잘 팔리는 걸 짚어줌 (고민 0)</li>
<li><span class=m>✓</span> 딸깍 — 대본·장면·목소리·자막 자동</li>
<li><span class=m>✓</span> 마음에 안 들면 다시 딸깍</li>
<li><span class=m>✓</span> 바로 올릴 세로 쇼츠 완성</li>
<li><span class=m>✓</span> 생각도, 손도 안 씀</li></ul>
<div class=time>10분</div><div class=tl>고르고 딸깍, 그게 전부</div></div></div></div>
<div class=sec><div class="money reveal">
<div class=k>이 시간이면, 몇 개나?</div>
<h2>같은 반나절에 60개.<br>나 대신 팔러 나갑니다.</h2>
<div class=big>
<div class=m><div class=n><span data-to=24>0</span><span class=u>배</span></div><div class=lbl>기존보다 빠르게<br>(3~5시간 → 10분)</div></div>
<div class=m><div class=n><span data-to=10>0</span><span class=u>개</span></div><div class=lbl>하루 30분이면<br>손 안 대고</div></div>
<div class=m><div class=n><span data-to=300>0</span><span class=u>개</span></div><div class=lbl>한 달이면<br>자동으로 쌓임</div></div></div>
<div class=note>영상 하나에 <b>내 판매·제휴 링크</b>가 붙습니다. 자는 동안에도 쇼츠가 대신 팔아주는 구조 — 많이 찍어낼수록 유리합니다.</div></div></div>
<div class=sec>
<h2 class=reveal>딱 세 번이면 끝나요</h2>
<div class="lead reveal">기획도 편집도 없이, 완성까지 10분</div>
<div class=steps>
<div class="step reveal"><div class=n>1</div><h3>고민은 안 해요</h3><p>지금 실시간 제일 잘 팔리는 걸 짚어줍니다. 검증된 1등을 그대로 벤치마킹 — 뭘 팔지 정할 필요도 없어요.</p></div>
<div class="step reveal d1"><div class=n>2</div><h3>딸깍 한 번</h3><p>대본·장면·목소리·자막을 AI가 알아서 붙입니다. 손댈 게 없어요.</p></div>
<div class="step reveal d2"><div class=n>3</div><h3>10분 뒤 완성</h3><p>바로 올릴 수 있는 세로 쇼츠가 나옵니다. 마음에 안 들면 다시 딸깍.</p></div></div></div>
<div class=sec>
<h2 class=reveal>왜 __NAME__인가</h2>
<div class="lead reveal">파는 사람이 진짜 필요한 것만</div>
<div class=feat>
<div class="card reveal"><span class=ic>⏱️</span><div><h3>10분이면 완성</h3><p>기획·촬영·편집으로 반나절 쓰던 걸, 고르고 딸깍하면 10분 만에 끝냅니다.</p></div></div>
<div class="card reveal d1"><span class=ic>📱</span><div><h3>폰으로도 된다</h3><p>PC도 프로그램 설치도 필요 없어요. 손 안의 폰에서 손가락 몇 번이면 됩니다.</p></div></div>
<div class="card reveal"><span class=ic>👆</span><div><h3>딸깍 하나면 자동</h3><p>대본·장면·목소리·자막을 전부 AI가. 컴맹이어도, 60대여도 첫날부터 바로 완성합니다.</p></div></div>
<div class="card reveal d1"><span class=ic>🔥</span><div><h3>지금 뜨는 걸 짚어줌</h3><p>뭘 만들지 고민할 필요 없어요. 실시간 제일 잘 팔리는 걸 골라줘서 검증된 1등만 벤치마킹합니다.</p></div></div></div></div>
<div class=sec>
<h2 class=reveal>요금은 간단해요</h2>
<div class="lead reveal">무료로 써보고, 필요하면 이용권으로</div>
<div class=reveal style="display:grid;grid-template-columns:1fr 1fr;gap:16px;max-width:640px;margin:0 auto">
<div style="background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:24px;text-align:center">
<div style="color:var(--muted);font-weight:700;font-size:14px">무료 체험</div>
<div class=display style="font-size:34px;margin:6px 0">0<span style="font-size:15px;font-family:'Noto Sans KR';color:var(--muted)">원</span></div>
<div style="color:var(--faint);font-size:13px;margin-bottom:16px">가입하면 바로 · 카드 없이</div>
<a class=cta href="/login" style="width:100%;justify-content:center;font-size:14px;padding:12px">무료로 시작</a></div>
<div style="background:var(--panel);border:1px solid rgba(255,207,111,.4);box-shadow:0 0 0 1px rgba(255,207,111,.14) inset;border-radius:18px;padding:24px;text-align:center;position:relative">
<div style="position:absolute;top:-11px;left:50%;transform:translateX(-50%);background:var(--gold-grad);color:#3a2600;font-family:'Black Han Sans',sans-serif;font-size:12px;padding:4px 12px;border-radius:999px">추천</div>
<div style="color:var(--gold);font-weight:700;font-size:14px">Pro 이용권</div>
<div class=display style="font-size:34px;margin:6px 0;background:var(--gold-grad);-webkit-background-clip:text;background-clip:text;color:transparent">가격 문의</div>
<div style="color:var(--faint);font-size:13px;margin-bottom:16px">전 기능 무제한 · 무제한 제작</div>
<a href="__PAY_HREF__" target=_blank rel=noopener style="display:inline-flex;width:100%;justify-content:center;background:var(--gold-grad);color:#3a2600;font-weight:700;font-size:14px;padding:12px;border-radius:12px;text-decoration:none">__PAY_LABEL__</a></div></div>
<div class=reveal style="text-align:center;margin-top:20px"><a href="/pricing" style="color:var(--mint);font-weight:700;font-size:14px">요금 자세히 보기 →</a></div></div>
<div class="band reveal">
<h2>손자한테 안 물어봐도 됩니다</h2>
<p>지금 10분, 무료로 하나 만들어보세요. 구글 계정이면 3초 · 카드 없이 시작.</p>
<a class=cta href="/login">무료로 시작하기 →</a></div>
<div class=foot>© __NAME__ · 쇼핑쇼츠, 이제 10분만에__LEGAL__</div>
</div>
<script>(function(){var rm=matchMedia('(prefers-reduced-motion:reduce)').matches;
var rev=document.querySelectorAll('.reveal');
if(rm){rev.forEach(function(e){e.classList.add('in')});document.querySelectorAll('[data-to]').forEach(function(e){e.textContent=e.dataset.to});return;}
var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target);}});},{threshold:.14});
rev.forEach(function(e){io.observe(e);});
function cu(el){var t=+el.dataset.to,s=null,d=1100;function f(ts){if(!s)s=ts;var p=Math.min((ts-s)/d,1);el.textContent=Math.round(t*(1-Math.pow(1-p,3)));if(p<1)requestAnimationFrame(f);}requestAnimationFrame(f);}
var m=document.querySelector('.money');
if(m){var mo=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.querySelectorAll('[data-to]').forEach(cu);mo.unobserve(e.target);}});},{threshold:.35});mo.observe(m);}
setTimeout(function(){document.querySelectorAll('.hero [data-to]').forEach(cu);},520);
})();</script>
<script>(function(){
// 런처 v3(2026-07-23): 로그인 링크 → 작은 런처 팝업으로("있어보이게"). 팝업 차단·모바일은 일반 이동 폴백.
document.addEventListener('click',function(e){
  var a=e.target.closest?e.target.closest('a[href="/login"]'):null; if(!a) return;
  if(window.innerWidth<600) return;                 // 모바일·좁은 화면은 팝업 어색 → 그냥 이동
  var w=window.open('/login','stb_login','width=440,height=800,menubar=no,toolbar=no,location=no,status=no,resizable=yes');
  if(w){ e.preventDefault(); try{w.focus();}catch(_){}}   // w=null(차단) → preventDefault 안 함 = 기본 이동
},true);
})();</script>
</body></html>"""


# ── 로그인 페이지 — "프로그램 런처" 연출 v3(2026-07-23 사장님): 엔진 부팅 로그(모듈 로드
#    타임라인+%카운터+링 스피너) 후 아이디·비번 폼이 메인, 구글은 보조 버튼.
#    /api/login이 관리자(env)+고객(DB) 둘 다 검증하므로 폼 하나로 충분.
#    JS 꺼짐/reduced-motion이면 부팅 생략·전부 즉시 표시.
_LOGIN_TMPL = """<!doctype html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<link rel=manifest href="/manifest.webmanifest"><meta name=theme-color content="#0c1411"><link rel=icon href="/favicon.ico"><link rel=apple-touch-icon href="/apple-touch-icon.png"><title>__NAME__ 로그인</title>
<link rel=preconnect href="https://fonts.googleapis.com">
<link rel=preconnect href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Black+Han+Sans&family=Noto+Sans+KR:wght@400;500;700&display=swap" rel=stylesheet>
<style>*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;word-break:keep-all;
background:radial-gradient(1000px 560px at 50% -18%,rgba(111,240,214,.11),transparent 62%),
radial-gradient(700px 420px at 88% 108%,rgba(255,207,111,.05),transparent 55%),#090d10;
font-family:'Noto Sans KR',system-ui,sans-serif;color:#e8f0ee}
.box{width:400px;max-width:calc(100vw - 24px);padding:38px 32px 26px;text-align:center;
background:linear-gradient(180deg,#101a1c,#0c1214);border:1px solid #1e2b2c;border-radius:24px;
box-shadow:0 34px 90px rgba(0,0,0,.6),0 0 0 1px rgba(111,240,214,.05) inset;
animation:cardin .5s ease}
@keyframes cardin{from{opacity:0;transform:scale(.96) translateY(8px)}}
.emwrap{position:relative;width:94px;height:94px;margin:0 auto}
.emwrap .sym{position:absolute;inset:8px;width:88px;height:88px;filter:drop-shadow(0 0 16px rgba(62,224,191,.30))}
@media (prefers-reduced-motion:no-preference){.emwrap .sym{animation:lpulse 3.2s ease-in-out infinite}}
@keyframes lpulse{50%{filter:drop-shadow(0 0 30px rgba(111,240,214,.55))}}
.ring{position:absolute;inset:0;border-radius:50%;border:2px solid transparent;
border-top-color:#6ff0d6;border-right-color:rgba(111,240,214,.35);opacity:0;transition:opacity .3s}
body.booting .ring{opacity:1;animation:spin .9s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.wm{display:flex;flex-direction:column;line-height:1;align-items:center;margin-top:13px}
/* 로그인 락업 — 브랜드가 가장 크게 보이는 자리. 워드마크 v3 동일 규칙(민트→오로라+골드 마침점) */
.nm{font-family:'Black Han Sans',sans-serif;font-size:31px;letter-spacing:-.6px;
  background:linear-gradient(135deg,#3ee0bf 0%,#7fe9d8 42%,#8c6ef0 100%);
  -webkit-background-clip:text;background-clip:text;color:transparent;
  -webkit-text-fill-color:transparent;filter:drop-shadow(0 0 14px rgba(62,224,191,.34))}
.nm::after{content:'.';background:none;-webkit-text-fill-color:#facc6b;color:#facc6b;filter:none;margin-left:2px}
.en{font-family:ui-monospace,monospace;font-size:10px;letter-spacing:3.8px;color:#4c8f85;margin-top:6px}
.ver{font-family:ui-monospace,monospace;font-size:10px;letter-spacing:2px;color:#3f5a54;margin-top:9px}
.boot{max-height:120px;margin:18px 0 2px;transition:opacity .4s ease,max-height .45s ease .2s,margin .45s ease .2s;overflow:hidden;text-align:left}
.boot.done{opacity:0;max-height:0;margin:0}
.bhead{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:7px}
.blabel{font-family:ui-monospace,monospace;font-size:10px;letter-spacing:1.6px;color:#47605a}
.bpct{font-family:ui-monospace,monospace;font-size:12px;color:#6ff0d6}
.bar{height:5px;background:#0a1210;border:1px solid #1c2a28;border-radius:99px;overflow:hidden}
.bar i{display:block;height:100%;width:0;border-radius:99px;transition:width .3s ease;
background:linear-gradient(90deg,#1f9e7a,#6ff0d6,#1f9e7a);background-size:200% 100%;animation:flow 1.1s linear infinite}
@keyframes flow{to{background-position:-200% 0}}
.blog{font-family:ui-monospace,monospace;font-size:11px;line-height:1.75;color:#527068;margin-top:8px;height:58px;overflow:hidden;display:flex;flex-direction:column;justify-content:flex-end}
.blog .ok{color:#49c9a9}.blog .cur{color:#9fe8d6}
.blog .cur:after{content:'▌';margin-left:2px;animation:blink .7s step-end infinite}
@keyframes blink{50%{opacity:0}}
.auth{transition:opacity .5s ease,transform .5s ease}
body.booting .auth{opacity:0;transform:translateY(12px);pointer-events:none}
h1{font-size:18px;margin:16px 0 14px;font-weight:700}
.lform input{width:100%;margin:5px 0;padding:13px 14px;background:#0a1113;border:1px solid #1e2b2c;
border-radius:11px;color:#e8f0ee;font-size:14px;outline:none;transition:border-color .15s,box-shadow .15s}
.lform input:focus{border-color:#2f6a5c;box-shadow:0 0 0 3px rgba(111,240,214,.08)}
.lbtn{width:100%;margin-top:10px;padding:13px;border:0;border-radius:11px;cursor:pointer;
font-family:'Noto Sans KR',sans-serif;font-weight:700;font-size:15px;color:#08110e;
background:linear-gradient(135deg,#6ff0d6,#1f9e7a);box-shadow:0 6px 22px rgba(31,158,122,.35);
transition:transform .12s,box-shadow .12s}
.lbtn:hover{transform:translateY(-1px);box-shadow:0 9px 28px rgba(31,158,122,.45)}
.or{display:flex;align-items:center;gap:12px;margin:16px 0 10px;color:#3f5050;font-size:11px}
.or:before,.or:after{content:'';flex:1;height:1px;background:#1a2626}
.gbtn{display:flex;align-items:center;justify-content:center;gap:9px;width:100%;padding:11px;
background:#101820;border:1px solid #1e2735;border-radius:11px;color:#b7c6c2;font-size:13px;
font-weight:700;cursor:pointer;text-decoration:none;transition:background .15s,border-color .15s}
.gbtn:hover{background:#16202e;border-color:#2a3647}
.gbtn svg{width:16px;height:16px}
.err{color:#e0623d;font-size:12px;margin-top:13px;min-height:14px;line-height:1.6}
.home{display:block;color:#5f7373;font-size:12px;margin-top:16px;text-decoration:none}
.home:hover{color:#6ff0d6}</style></head>
<body><div class=box>
<div class=emwrap><div class=ring></div>__LOGO_SVG__</div>
<div class=wm><span class=nm>__NAME__</span><span class=en>__NAME_EN__</span></div>
<div class=ver>__NAME_EN__ STUDIO</div>
<div class=boot id=boot>
<div class=bhead><span class=blabel>SYSTEM BOOT</span><span class=bpct id=bpct>0%</span></div>
<div class=bar><i id=bbar></i></div>
<div class=blog id=blog></div>
</div>
<div class=auth>
<h1>로그인</h1>
<form class=lform method=post action=/api/login>
<input name=user placeholder="아이디 (이메일)" autocomplete=username>
<input name=pass type=password placeholder=비밀번호 autocomplete=current-password>
<button class=lbtn>로그인 →</button></form>
<div class=or>또는</div>
<a class=gbtn href="/auth/google/login">
__GOOGLE_SVG__
Google 계정으로 계속하기</a>
<div class=err>__ERR__</div>
<a class=home href="/">← 홈으로 돌아가기</a>
<div style="text-align:center;color:#5f7373">__LEGAL__</div>
</div>
</div>
<script>(function(){
if(matchMedia('(prefers-reduced-motion:reduce)').matches){document.getElementById('boot').classList.add('done');return;}
var b=document.body;b.classList.add('booting');
var bar=document.getElementById('bbar'),pct=document.getElementById('bpct'),lg=document.getElementById('blog');
var steps=[[9,'코어 부팅'],[24,'AI 엔진 초기화'],[42,'트렌드 데이터 동기화'],[61,'대본 생성 모듈 로드'],[78,'렌더 파이프라인 웜업'],[92,'보안 채널 연결'],[100,'준비 완료']];
var i=0,shown=0,tk=null;
function tick(){shown=Math.min(shown+3,steps[Math.min(i,steps.length-1)][0]);pct.textContent=shown+'%';}
tk=setInterval(tick,40);
function nx(){
var cur=lg.querySelector('.cur');if(cur){cur.className='ok';cur.textContent='  ✓ '+cur.dataset.t;}
if(i>=steps.length){clearInterval(tk);pct.textContent='100%';
setTimeout(function(){b.classList.remove('booting');document.getElementById('boot').classList.add('done');},260);return;}
bar.style.width=steps[i][0]+'%';
var d=document.createElement('div');d.className='cur';d.dataset.t=steps[i][1];d.textContent='  › '+steps[i][1];
lg.appendChild(d);while(lg.children.length>3)lg.removeChild(lg.firstChild);
i++;setTimeout(nx,i===steps.length?460:300);}
setTimeout(nx,160);
})();</script>
</body></html>"""

# ── 요금·이용권(상품 상세) — 공개 페이지. 구성·가격은 플레이스홀더(확정 시 값만 교체). ──
_PRICING_TMPL = """<!doctype html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<link rel=manifest href="/manifest.webmanifest"><meta name=theme-color content="#0c1411"><link rel=icon href="/favicon.ico"><link rel=apple-touch-icon href="/apple-touch-icon.png">
<title>__NAME__ — 요금 · 이용권</title>
<link rel=preconnect href="https://fonts.googleapis.com">
<link rel=preconnect href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Black+Han+Sans&family=Noto+Sans+KR:wght@400;500;700;900&display=swap" rel=stylesheet>
<style>*{box-sizing:border-box;margin:0;padding:0}
:root{--mint:#6ff0d6;--grad:linear-gradient(135deg,#6ff0d6,#1f9e7a);--gold:#ffcf6f;--gold-grad:linear-gradient(135deg,#ffe1a1,#f0a93a);
--ink:#0b0f14;--panel:#111722;--line:#1e2735;--txt:#e8f0ee;--muted:#8aa0a0;--faint:#5f7373}
body{background:radial-gradient(1100px 600px at 82% -12%,rgba(111,240,214,.10),transparent 60%),radial-gradient(900px 500px at 0% 112%,rgba(255,207,111,.06),transparent 55%),var(--ink);
color:var(--txt);font-family:'Noto Sans KR',system-ui,sans-serif;line-height:1.6;-webkit-font-smoothing:antialiased;word-break:keep-all}
a{text-decoration:none;color:inherit}
.display{font-family:'Black Han Sans',sans-serif;font-weight:400}
.wrap{max-width:1000px;margin:0 auto;padding:0 24px}
.nav{display:flex;align-items:center;justify-content:space-between;padding:22px 0}
.brand{display:flex;align-items:center;gap:10px}
.brand .sym{width:44px;height:44px;flex:none}
.brand .wm{display:flex;flex-direction:column;line-height:1}
/* 워드마크 v3(2026-07-25): 민트→오로라 그라데이션 + 끝에 골드 마침점(브랜드 포인트).
   ::after 는 background-clip:text를 상속해 투명해지니 text-fill-color를 되돌려 금색을 살린다. */
.brand .nm{font-family:'Black Han Sans',sans-serif;font-size:22px;letter-spacing:-.4px;
  background:linear-gradient(135deg,#3ee0bf 0%,#7fe9d8 42%,#8c6ef0 100%);
  -webkit-background-clip:text;background-clip:text;color:transparent;
  -webkit-text-fill-color:transparent;filter:drop-shadow(0 0 10px rgba(62,224,191,.32))}
.brand .nm::after{content:'.';background:none;-webkit-text-fill-color:#facc6b;color:#facc6b;
  filter:none;margin-left:1px}
.brand .en{font-family:ui-monospace,monospace;font-size:9px;letter-spacing:2.8px;color:#4c8f85;margin-top:3px}
.nav a.top{color:var(--muted);font-size:14px;font-weight:600}.nav a.top:hover{color:var(--mint)}
.hero{text-align:center;max-width:700px;margin:0 auto;padding:52px 0 36px}
.eyebrow{font-size:12px;letter-spacing:.2em;color:var(--mint);font-weight:700;margin-bottom:14px}
.hero h1{font-size:clamp(30px,4.4vw,46px);line-height:1.18}
.hero p{color:var(--muted);font-size:16px;margin:16px auto 26px;max-width:44ch}
.row{display:flex;gap:12px;justify-content:center;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;gap:8px;font-weight:700;font-size:15px;padding:14px 26px;border-radius:12px;cursor:pointer;border:0}
.btn.pri{background:var(--grad);color:#062018;box-shadow:0 8px 30px rgba(111,240,214,.18)}
.btn.pri:hover{filter:brightness(1.06)}
.btn.kko{background:var(--gold-grad);color:#3a2600}
.btn.kko:hover{filter:brightness(1.05)}
.btn.ghost{background:transparent;color:var(--txt);border:1px solid var(--line);font-weight:600}
.plans{display:grid;grid-template-columns:1fr 1fr;gap:18px;max-width:760px;margin:20px auto 0}
.plan{background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:30px 26px;position:relative}
.plan.pro{border-color:rgba(255,207,111,.4);box-shadow:0 0 0 1px rgba(255,207,111,.14) inset}
.plan .rec{position:absolute;top:-11px;left:50%;transform:translateX(-50%);background:var(--gold-grad);color:#3a2600;font-family:'Black Han Sans',sans-serif;font-size:12px;padding:4px 12px;border-radius:999px}
.plan .pt{font-size:15px;font-weight:700;color:var(--muted)}
.plan .pro-t{color:var(--gold)}
.plan .price{font-family:'Black Han Sans',sans-serif;font-size:38px;margin:10px 0 4px}
.plan.pro .price{background:var(--gold-grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.plan .price small{font-size:15px;color:var(--muted);font-family:'Noto Sans KR'}
.plan .pd{color:var(--faint);font-size:13px;margin-bottom:18px}
.plan ul{list-style:none;display:flex;flex-direction:column;gap:9px;margin-bottom:22px}
.plan li{font-size:14px;color:var(--txt);display:flex;gap:9px}.plan li .c{color:var(--mint);flex:none}
.plan .btn{width:100%;justify-content:center}
.sec{padding:48px 0}
.sec h2{text-align:center;font-size:clamp(22px,3vw,28px);font-weight:900;margin-bottom:8px}
.sec .lead{text-align:center;color:var(--muted);margin-bottom:32px}
.incl{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;max-width:820px;margin:0 auto}
.incl .i{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px;font-size:14px}
.incl .i b{display:block;margin-bottom:3px}.incl .i span{color:var(--muted);font-size:13px}
.revs{display:grid;grid-template-columns:1fr 1fr;gap:16px;max-width:820px;margin:0 auto}
.rev{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:22px}
.rev p{font-size:14px;margin-bottom:10px}.rev .who{color:var(--faint);font-size:12.5px}
.faq{max-width:720px;margin:0 auto}
.qa{border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin-bottom:12px;background:var(--panel)}
.qa .q{font-weight:700;font-size:15px;margin-bottom:6px}.qa .a{color:var(--muted);font-size:14px}
.band{text-align:center;background:linear-gradient(180deg,rgba(255,207,111,.05),transparent);border:1px solid var(--line);border-radius:24px;padding:50px 24px;margin:40px 0 58px}
.band h2{font-size:clamp(23px,3.2vw,29px);font-weight:900;margin-bottom:10px}.band p{color:var(--muted);margin-bottom:24px}
.tbd{color:var(--faint);font-size:12px;margin-top:14px}
.foot{text-align:center;color:var(--faint);font-size:12.5px;padding:0 0 42px}
@media(max-width:760px){.plans,.incl,.revs{grid-template-columns:1fr}}
</style></head><body><div class=wrap>
<div class=nav>
<a class=brand href="/">__LOGO_SVG__<span class=wm><span class=nm>__NAME__</span><span class=en>__NAME_EN__</span></span></a>
<a class="top" href="/login">로그인</a></div>
<div class=hero>
<div class=eyebrow>요금 · 이용권</div>
<h1 class=display>필요한 만큼만,<br>부담 없이 시작하세요</h1>
<p>먼저 무료로 만들어보고, 마음에 들면 이용권으로 계속. 결제·문의는 카톡으로 간편하게 안내해 드립니다.</p>
<div class=row>
<a class="btn pri" href="/login">무료로 시작하기 →</a>
<a class="btn kko" href="__PAY_HREF__" target="_blank" rel="noopener">__PAY_LABEL__</a></div></div>
<div class=plans>
<div class=plan>
<div class=pt>무료 체험</div>
<div class=price>0<small>원</small></div>
<div class=pd>가입하면 바로 시작 · 카드 없이</div>
<ul>
<li><span class=c>✓</span> 가입 후 일정 기간 전 기능 체험</li>
<li><span class=c>✓</span> 레퍼런스 랭킹 열람</li>
<li><span class=c>✓</span> 쇼츠 제작 체험</li></ul>
<a class="btn pri" href="/login">무료로 시작</a></div>
<div class="plan pro">
<div class=rec>추천</div>
<div class="pt pro-t">Pro 이용권</div>
<div class=price>가격 문의<small></small></div>
<div class=pd>기간·구성은 카톡으로 안내 (준비 중)</div>
<ul>
<li><span class=c>✓</span> 전 기능 무제한</li>
<li><span class=c>✓</span> 쇼츠 무제한 제작</li>
<li><span class=c>✓</span> 렌즈·대본·보이스 전부</li>
<li><span class=c>✓</span> 우선 문의·운영 노하우</li></ul>
<a class="btn kko" href="__PAY_HREF__" target="_blank" rel="noopener">__PAY_LABEL__</a></div></div>
<div class=tbd style="text-align:center">※ 가격·이용권 기간은 확정 후 표기됩니다(현재 플레이스홀더).</div>
<div class=sec>
<h2>이용권에 들어있는 것</h2>
<div class=lead>파는 사람이 처음부터 끝까지 쓰는 도구</div>
<div class=incl>
<div class=i><b>🔥 레퍼런스 랭킹</b><span>지금 제일 잘 팔리는 걸 짚어줌</span></div>
<div class=i><b>🔎 렌즈 · 유사영상</b><span>짜맞출 소스 자동 수집</span></div>
<div class=i><b>✍️ 대본 추출·리메이크</b><span>내 상품 이야기로 다시 씀</span></div>
<div class=i><b>🎬 제작소</b><span>장면·자막 원클릭 조립</span></div>
<div class=i><b>🎙️ AI 보이스</b><span>자연스러운 나레이션 자동</span></div>
<div class=i><b>♾️ 무제한 제작</b><span>많이 찍어낼수록 유리</span></div></div></div>
<div class=sec>
<h2>먼저 써본 분들</h2>
<div class=lead>(후기 자리 — 실제 후기로 교체 예정)</div>
<div class=revs>
<div class=rev><p>"편집 하나도 몰랐는데 하루에 몇 개씩 만들어요. 이게 10분이면 된다는 게 신기합니다."</p><div class=who>— 준비 중</div></div>
<div class=rev><p>"뭘 만들지 고민이 제일 힘들었는데, 잘 팔리는 걸 짚어주니 그냥 딸깍만 하면 돼요."</p><div class=who>— 준비 중</div></div></div></div>
<div class=sec>
<h2>자주 묻는 질문</h2>
<div class=faq>
<div class=qa><div class=q>결제는 어떻게 하나요?</div><div class=a>카톡으로 문의하시면 안내해 드립니다. 확인 후 바로 이용권이 열립니다.</div></div>
<div class=qa><div class=q>무료 체험만 써도 되나요?</div><div class=a>네. 체험 기간엔 전 기능을 그대로 쓰실 수 있고, 이후엔 레퍼런스 랭킹은 계속 보실 수 있어요.</div></div>
<div class=qa><div class=q>환불되나요?</div><div class=a>환불 정책은 확정 후 안내드립니다(준비 중).</div></div></div></div>
<div class=band>
<h2>일단 무료로 하나 만들어보세요</h2>
<p>구글 계정이면 3초 · 카드 없이 시작. 궁금한 건 카톡으로.</p>
<div class=row>
<a class="btn pri" href="/login">무료로 시작하기 →</a>
<a class="btn kko" href="__PAY_HREF__" target="_blank" rel="noopener">__PAY_LABEL__</a></div></div>
<div class=foot>© __NAME__ · 요금·이용권 안내__LEGAL__</div>
</div></body></html>"""

# ── 내 계정(유저 자기 설정) — 로그인 전용. /api/me로 플랜·한도·연락처를 채운다. ──
_ACCOUNT_TMPL = """<!doctype html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<link rel=manifest href="/manifest.webmanifest"><meta name=theme-color content="#0c1411"><link rel=icon href="/favicon.ico"><link rel=apple-touch-icon href="/apple-touch-icon.png">
<title>__NAME__ — 내 계정</title>
<link rel=preconnect href="https://fonts.googleapis.com">
<link rel=preconnect href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Black+Han+Sans&family=Noto+Sans+KR:wght@400;500;700;900&display=swap" rel=stylesheet>
<style>*{box-sizing:border-box;margin:0;padding:0}
:root{--mint:#6ff0d6;--grad:linear-gradient(135deg,#6ff0d6,#1f9e7a);--gold:#ffcf6f;--gold-grad:linear-gradient(135deg,#ffe1a1,#f0a93a);
--ink:#0b0f14;--panel:#111722;--line:#1e2735;--txt:#e8f0ee;--muted:#8aa0a0;--faint:#5f7373}
body{background:radial-gradient(1000px 560px at 82% -12%,rgba(111,240,214,.09),transparent 60%),var(--ink);
color:var(--txt);font-family:'Noto Sans KR',system-ui,sans-serif;line-height:1.6;-webkit-font-smoothing:antialiased;word-break:keep-all;min-height:100vh}
a{text-decoration:none;color:inherit}
.wrap{max-width:520px;margin:0 auto;padding:0 22px}
.nav{display:flex;align-items:center;justify-content:space-between;padding:22px 0}
.brand{display:flex;align-items:center;gap:10px}
.brand .sym{width:38px;height:38px;flex:none}
.brand .nm{font-family:'Black Han Sans',sans-serif;font-size:20px;letter-spacing:-.4px;
  background:linear-gradient(135deg,#3ee0bf 0%,#7fe9d8 42%,#8c6ef0 100%);
  -webkit-background-clip:text;background-clip:text;color:transparent;-webkit-text-fill-color:transparent}
.brand .nm::after{content:'.';background:none;-webkit-text-fill-color:#facc6b;color:#facc6b;margin-left:1px}
.nav .back{color:var(--muted);font-size:14px;font-weight:600}.nav .back:hover{color:var(--mint)}
h1{font-family:'Black Han Sans',sans-serif;font-size:30px;margin:16px 0 22px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:22px;margin-bottom:16px}
.card h3{font-size:13px;letter-spacing:.03em;color:var(--faint);font-weight:700;margin-bottom:12px}
.plan{display:flex;align-items:center;gap:12px}
.plan .badge{font-family:'Black Han Sans',sans-serif;font-size:15px;padding:6px 14px;border-radius:999px}
.badge.trial{background:rgba(111,240,214,.14);color:var(--mint)}
.badge.free{background:#1a2028;color:var(--muted)}
.badge.pro{background:var(--gold-grad);color:#3a2600}
.plan .sub{color:var(--muted);font-size:14px}
.lims{display:flex;gap:10px;flex-wrap:wrap}
.lim{flex:1;min-width:90px;background:#0d131c;border:1px solid var(--line);border-radius:12px;padding:14px;text-align:center}
.lim .n{font-family:'Black Han Sans',sans-serif;font-size:24px;color:var(--mint)}
.lim .l{color:var(--muted);font-size:12px;margin-top:2px}
.btn{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;padding:14px;border-radius:12px;font-weight:700;font-size:15px;cursor:pointer;border:0}
.btn.kko{background:var(--gold-grad);color:#3a2600}
.btn.ghost{background:transparent;color:var(--muted);border:1px solid var(--line);font-weight:600}
.up p{color:var(--muted);font-size:13.5px;margin-bottom:14px}
.foot{text-align:center;color:var(--faint);font-size:12px;padding:16px 0 40px}
.hide{display:none!important}
</style></head><body><div class=wrap>
<div class=nav>
<a class=brand href="/">__LOGO_SVG__<span class=nm>__NAME__</span></a>
<a class=back href="/">← 앱으로</a></div>
<h1>내 계정</h1>
<div class=card>
<h3>현재 플랜</h3>
<div class=plan><span id=planBadge class="badge free">…</span><span id=planSub class=sub></span></div></div>
<div class=card>
<h3>하루 이용 한도</h3>
<div class=lims>
<div class=lim><div class=n id=limRender>–</div><div class=l>제작</div></div>
<div class=lim><div class=n id=limLens>–</div><div class=l>렌즈</div></div>
<div class=lim><div class=n id=limScript>–</div><div class=l>대본</div></div></div></div>
<div class="card up" id=upCard>
<h3>이용권</h3>
<p id=upText>더 쓰고 싶으면 이용권으로 계속 쓸 수 있어요. 결제·문의는 카톡으로 안내해 드립니다.</p>
<a class="btn kko" id=kkoBtn href="/pricing">__PAY_LABEL__</a></div>
<form method=post action="/logout"><button type=submit class="btn ghost" style="width:100%">로그아웃</button></form>
<div class=foot>© __NAME____LEGAL__</div>
</div>
<script>(function(){
function t(id,v){var e=document.getElementById(id);if(e)e.textContent=v;}
fetch("/api/me").then(function(r){return r.ok?r.json():null;}).then(function(d){
if(!d)return;
var L=d.limits||{};t("limRender",L.render);t("limLens",L.lens);t("limScript",L.script);
var b=document.getElementById("planBadge");
if(d.plan==="pro"){b.className="badge pro";t("planBadge","Pro 이용권");t("planSub","전 기능 무제한");document.getElementById("upCard").classList.add("hide");}
else if(typeof d.days_left==="number"&&d.days_left>0){b.className="badge trial";t("planBadge","무료 체험");t("planSub","D-"+d.days_left+" 남음");}
else{b.className="badge free";t("planBadge","무료");t("planSub","레퍼런스 랭킹 열람");}
var c=d.contact||{};var pay=(c.pay||"").trim(),kko=(c.kakao||"").trim();
var btn=document.getElementById("kkoBtn");
if(pay){btn.href=pay;btn.target="_blank";btn.rel="noopener";btn.textContent="💳 결제하기 →";}
else if(/^https?:\\/\\//.test(kko)){btn.href=kko;btn.target="_blank";btn.rel="noopener";btn.textContent="카톡으로 문의";}
else{btn.href="/pricing";btn.textContent="카톡으로 문의";}
}).catch(function(){});
})();</script>
</body></html>"""

_LANDING_HTML = _fill_brand(_LANDING_TMPL)

_PENDING_HTML = _fill_brand("""<!doctype html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<link rel=manifest href="/manifest.webmanifest"><meta name=theme-color content="#0c1411"><link rel=icon href="/favicon.ico"><link rel=apple-touch-icon href="/apple-touch-icon.png">
<title>승인 대기중 · __NAME__</title>
<style>body{font-family:-apple-system,'Malgun Gothic',sans-serif;background:#0f1115;color:#e8eaed;
margin:0;display:flex;min-height:100vh;align-items:center;justify-content:center;text-align:center}
.box{max-width:420px;padding:40px 28px}.emoji{font-size:56px}h1{font-size:22px;margin:18px 0 10px}
p{color:#9aa0a6;line-height:1.6;font-size:15px}a{display:inline-block;margin-top:24px;color:#8ab4f8;
text-decoration:none;font-size:14px}</style></head>
<body><div class=box><div class=emoji>🙏</div>
<h1>가입 신청이 접수됐어요</h1>
<p>운영자 승인 후 이용할 수 있어요.<br>결제하고 알려주시면 바로 열어드려요.</p>
<a href="__PAY_HREF__" target=_blank rel=noopener style="display:inline-block;margin-top:22px;background:linear-gradient(135deg,#6ff0d6,#1f9e7a);color:#08110e;font-weight:700;padding:12px 24px;border-radius:11px;text-decoration:none;font-size:15px">__PAY_LABEL__</a>
<form method=post action="/logout" style="margin-top:16px"><button type=submit style="background:none;border:0;color:#8ab4f8;font-size:14px;cursor:pointer;text-decoration:none">로그아웃</button></form>
<div style="margin-top:20px;color:#5f6773;font-size:12px">__LEGAL__</div></div></body></html>""")

# 로그아웃 확인 화면 — GET /logout이 세션을 안 지우는 대신 이 화면을 준다(CSRF 방어).
# 실제 로그아웃은 이 폼의 POST만.
_LOGOUT_CONFIRM_HTML = _fill_brand("""<!doctype html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<link rel=manifest href="/manifest.webmanifest"><meta name=theme-color content="#0c1411"><link rel=icon href="/favicon.ico"><link rel=apple-touch-icon href="/apple-touch-icon.png">
<title>로그아웃 · __NAME__</title>
<style>body{font-family:-apple-system,'Malgun Gothic',sans-serif;background:#0f1115;color:#e8eaed;
margin:0;display:flex;min-height:100vh;align-items:center;justify-content:center;text-align:center}
.box{max-width:380px;padding:40px 28px}h1{font-size:20px;margin:0 0 18px}
button{background:#8ab4f8;color:#111;border:0;border-radius:8px;padding:11px 22px;font-size:15px;
font-weight:700;cursor:pointer}a{display:block;margin-top:18px;color:#9aa0a6;font-size:13px;text-decoration:none}
</style></head>
<body><div class=box><h1>로그아웃 하시겠어요?</h1>
<form method=post action="/logout"><button type=submit>로그아웃</button></form>
<a href="/">돌아가기</a></div></body></html>""")

_LOGIN_HTML = _fill_brand(_LOGIN_TMPL)
_PRICING_HTML = _fill_brand(_PRICING_TMPL)
_ACCOUNT_HTML = _fill_brand(_ACCOUNT_TMPL)

_SIGNUP_HTML = """<!doctype html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<link rel=manifest href="/manifest.webmanifest"><meta name=theme-color content="#0c1411"><link rel=icon href="/favicon.ico"><link rel=apple-touch-icon href="/apple-touch-icon.png"><title>숏템메이커 가입</title>
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
<h1>🛍️ 숏템메이커 가입</h1>
<input name=user placeholder=아이디(영문/숫자) autocomplete=username autofocus>
<input name=name placeholder=이름 autocomplete=name>
<input name=phone placeholder="전화번호(010-0000-0000)" autocomplete=tel>
<input name=pass type=password placeholder=비밀번호 autocomplete=new-password>
<button>가입하기</button>
<div class=err>__ERR__</div>
<div class=foot><a href=/login>이미 계정이 있으신가요? 로그인</a></div>
</form></body></html>"""


@app.get("/login", response_class=HTMLResponse)
def _login_page(request: Request, e: str = ""):
    # 이미 로그인된 세션이면 홈으로 — 앱 런처(작은 창)가 /login을 직접 열어도 재로그인 강요 안 함.
    if _AUTH_ON and _verify_session(request.cookies.get("dash_auth", "")) is not None:
        return RedirectResponse("/", status_code=303)
    if e == "1":
        msg = "아이디 또는 비밀번호가 틀렸습니다"
    elif e:   # 구글 콜백 등에서 온 안내 — XSS 방지 이스케이프
        msg = e.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    else:
        msg = ""
    return _LOGIN_HTML.replace("__ERR__", msg)


@app.get("/logout", response_class=HTMLResponse)
def _logout_confirm():
    # CSRF 방어: GET은 세션을 지우지 않는다 — <img src="/logout">·링크 프리페치로 강제
    # 로그아웃당하는 걸 막는다. 실제 로그아웃은 POST(_logout_do)만. 여기선 확인 버튼만 보여준다.
    return _LOGOUT_CONFIRM_HTML


@app.post("/logout")
def _logout_do():
    # 세션 쿠키 제거 후 로그인 화면으로. pending 게이트에서도 통과시켜야 하는 유일한 탈출구
    # (2026-07-21, Task6) — 없으면 승인대기 유저가 로그아웃도 못 하는 함정에 갇힌다.
    r = RedirectResponse("/login", status_code=303)
    r.delete_cookie("dash_auth")
    return r


# ── 계좌입금 안내 페이지(2026-07-23) — 사장님이 admin에 은행·계좌·예금주 넣으면 자동 표시. ──
_DEPOSIT_TMPL = _fill_brand("""<!doctype html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<link rel=manifest href="/manifest.webmanifest"><meta name=theme-color content="#0c1411"><link rel=icon href="/favicon.ico"><link rel=apple-touch-icon href="/apple-touch-icon.png">
<title>결제 안내 · __NAME__</title>
<style>*{box-sizing:border-box}body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:radial-gradient(900px 500px at 50% -15%,rgba(111,240,214,.10),transparent 60%),#090d10;
font-family:'Noto Sans KR',system-ui,sans-serif;color:#e8f0ee;word-break:keep-all;padding:20px}
.box{width:440px;max-width:100%;background:linear-gradient(180deg,#101a1c,#0c1214);border:1px solid #1e2b2c;border-radius:22px;padding:34px 28px 26px;box-shadow:0 30px 80px rgba(0,0,0,.55)}
h1{font-size:20px;margin:0 0 4px;text-align:center}.sub{color:#8aa0a0;font-size:13px;text-align:center;margin-bottom:22px}
.row{background:#0a1113;border:1px solid #1e2b2c;border-radius:12px;padding:14px 16px;margin:9px 0;display:flex;justify-content:space-between;align-items:center;gap:10px}
.k{color:#7a9090;font-size:13px;flex:none}.v{font-weight:700;font-size:16px;text-align:right;word-break:break-all}
.acc .v{font-size:20px;color:#6ff0d6;letter-spacing:.3px}
.copy{margin-left:10px;background:#16202a;border:1px solid #2a3647;color:#b7c6c2;border-radius:8px;padding:6px 10px;font-size:12px;font-weight:700;cursor:pointer;flex:none}
.copy:hover{border-color:#37e0bd;color:#6ff0d6}
.note{background:#101c18;border:1px solid #1d3a30;border-radius:12px;padding:14px 16px;margin:16px 0 6px;font-size:13px;line-height:1.7;color:#b9d3c9}
.note b{color:#6ff0d6}
.contact{display:flex;gap:10px;margin-top:16px}
.contact a{flex:1;text-align:center;padding:12px;border-radius:11px;text-decoration:none;font-weight:700;font-size:14px}
.kko{background:linear-gradient(135deg,#6ff0d6,#1f9e7a);color:#08110e}
.tel{background:#101820;border:1px solid #1e2735;color:#b7c6c2}
.home{display:block;text-align:center;color:#5f7373;font-size:12px;margin-top:16px;text-decoration:none}
.empty{color:#c9a24b;text-align:center;font-size:13px;line-height:1.7;padding:8px 0}</style></head>
<body><div class=box>
<h1>💳 결제 안내</h1><div class=sub>__NAME__ 이용권 · 계좌입금</div>
__BODY__
<a class=home href="/">← 돌아가기</a>
</div>
<script>function cp(t){navigator.clipboard&&navigator.clipboard.writeText(t);var e=event.target;var o=e.textContent;e.textContent='복사됨';setTimeout(function(){e.textContent=o;},1200);}</script>
</body></html>""")


def _deposit_body():
    """계좌 설정이 있으면 계좌 카드, 없으면 안내문구. 요청 시점에 admin 설정을 읽는다."""
    st = Store(DB_PATH)
    bank = (st.get_setting("bank_name", "") or "").strip()
    acc = (st.get_setting("bank_account", "") or "").strip()
    holder = (st.get_setting("bank_holder", "") or "").strip()
    note = (st.get_setting("deposit_note", "") or "").strip()
    kakao = (st.get_setting("contact_kakao", "") or "").strip()
    phone = (st.get_setting("contact_phone", "") or "").strip()
    import html as _h
    if not acc:
        return ('<div class=empty>결제 안내가 아직 준비 중이에요.<br>아래로 문의해 주세요.</div>'
                + _deposit_contact(kakao, phone))
    rows = ""
    if bank:
        rows += f'<div class=row><span class=k>은행</span><span class=v>{_h.escape(bank)}</span></div>'
    rows += (f'<div class="row acc"><span class=k>계좌번호</span>'
             f'<span class=v id=acc>{_h.escape(acc)}</span>'
             f'<button class=copy onclick="cp(document.getElementById(\'acc\').textContent)">복사</button></div>')
    if holder:
        rows += f'<div class=row><span class=k>예금주</span><span class=v>{_h.escape(holder)}</span></div>'
    note_html = (f'<div class=note>{_h.escape(note)}</div>' if note else
                 '<div class=note>입금 금액·이용권은 아래로 <b>문의</b>해 주세요.<br>'
                 '입금 후 <b>입금자명</b>을 알려주시면 <b>바로 이용권을 열어드려요.</b></div>')
    return rows + note_html + _deposit_contact(kakao, phone)


def _deposit_contact(kakao, phone):
    import html as _h
    if not kakao and not phone:
        return ""
    out = '<div class=contact>'
    if kakao:
        href = kakao if kakao.startswith("http") else ("https://" + kakao)
        out += f'<a class=kko href="{_h.escape(href)}" target=_blank rel=noopener>💬 카톡 문의</a>'
    if phone:
        out += f'<a class=tel href="tel:{_h.escape(phone)}">📞 {_h.escape(phone)}</a>'
    return out + '</div>'


@app.get("/pay", response_class=HTMLResponse)
def _deposit_page():
    """계좌입금 안내(공개). 사장님이 admin에 은행·계좌·예금주 넣으면 표시."""
    return _DEPOSIT_TMPL.replace("__BODY__", _deposit_body())


# ── 법적 고지 문서(공개): 이용약관 · 개인정보처리방침 · 환불정책 ──
# 서비스명은 브랜드 토큰, 사업자정보는 admin 설정(biz_*)에서 요청 시점에 읽어 채운다.
# 값이 비면 "(준비 중)"으로 표시 → 사장님이 실제 값을 나중에 admin에서 채워 넣으면 즉시 반영.
_LEGAL_TMPL = _fill_brand("""<!doctype html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<link rel=manifest href="/manifest.webmanifest"><meta name=theme-color content="#0c1411"><link rel=icon href="/favicon.ico"><link rel=apple-touch-icon href="/apple-touch-icon.png">
<title>__DOCTITLE__ · __NAME__</title>
<style>*{box-sizing:border-box}body{margin:0;min-height:100vh;
background:radial-gradient(900px 500px at 50% -15%,rgba(111,240,214,.08),transparent 60%),#090d10;
font-family:'Noto Sans KR',system-ui,sans-serif;color:#dbe6e3;word-break:keep-all;padding:32px 18px 64px;line-height:1.75}
.wrap{max-width:760px;margin:0 auto}
.brand{display:inline-flex;align-items:center;gap:8px;color:#8aa0a0;font-size:14px;margin-bottom:18px;text-decoration:none}
.brand svg{width:26px;height:26px;flex:none}.brand b{color:#e8f0ee}
h1{font-size:24px;margin:0 0 4px}.upd{color:#7a9090;font-size:12.5px;margin-bottom:26px}
h2{font-size:16px;color:#6ff0d6;margin:30px 0 8px;padding-top:6px}
p,li{font-size:14px;color:#c5d3cf}
ul{padding-left:20px;margin:8px 0}li{margin:4px 0}
.biz{margin-top:38px;padding:16px 18px;background:#0c1416;border:1px solid #1c2a2b;border-radius:14px;font-size:13px;color:#9fb2ad;line-height:1.9}
.biz b{color:#c5d3cf;font-weight:600}
.nav{display:flex;gap:8px;flex-wrap:wrap;margin-top:30px}
.nav a{flex:1;min-width:120px;text-align:center;padding:11px;border-radius:11px;text-decoration:none;font-size:13px;font-weight:700;
background:#101a1c;border:1px solid #1e2b2c;color:#b7c6c2}
.nav a.on{background:linear-gradient(135deg,#6ff0d6,#1f9e7a);color:#08110e;border-color:transparent}
.home{display:inline-block;margin-top:20px;color:#5f7373;font-size:13px;text-decoration:none}</style></head>
<body><div class=wrap>
<a class=brand href="/">__LOGO_SVG__ <b>__NAME__</b></a>
<h1>__DOCTITLE__</h1><div class=upd>__UPDATED__</div>
__BODY__
__BIZ__
<div class=nav>__NAV__</div>
<a class=home href="/">← __NAME__ 홈으로</a>
</div></body></html>""")

_LEGAL_UPDATED = "시행일 2026-07-23"

def _biz_block():
    """사업자정보 표시(전자상거래법). admin 설정(biz_*)이 비면 '(준비 중)'."""
    import html as _h
    st = Store(DB_PATH)
    def g(k, d="(준비 중)"):
        v = (st.get_setting(k, "") or "").strip()
        return _h.escape(v) if v else d
    return (
        '<div class=biz>'
        f'<b>상호</b> {g("biz_name", _BRAND["name"])} &nbsp;·&nbsp; '
        f'<b>대표자</b> {g("biz_owner")}<br>'
        f'<b>사업자등록번호</b> {g("biz_regno")}<br>'
        f'<b>통신판매업신고</b> {g("biz_sales_no")}<br>'
        f'<b>주소</b> {g("biz_addr")}<br>'
        f'<b>문의</b> {g("biz_email")}'
        '</div>')

def _legal_nav(active: str):
    items = [("/terms", "이용약관"), ("/privacy", "개인정보처리방침"), ("/refund", "환불정책")]
    return "".join(
        f'<a href="{href}"{" class=on" if href == active else ""}>{label}</a>'
        for href, label in items)

def _legal_page(path: str, title: str, body: str) -> str:
    return (_LEGAL_TMPL
            .replace("__DOCTITLE__", title)
            .replace("__UPDATED__", _LEGAL_UPDATED)
            .replace("__BODY__", body)
            .replace("__BIZ__", _biz_block())
            .replace("__NAV__", _legal_nav(path)))

_TERMS_BODY = f"""
<p>본 약관은 {_BRAND['name']}(이하 "회사")가 제공하는 AI 쇼츠 제작 서비스(이하 "서비스")의 이용조건과 절차, 회사와 이용자의 권리·의무를 규정합니다.</p>
<h2>제1조 (서비스 내용)</h2>
<p>회사는 이용자가 업로드·선택한 소재를 바탕으로 AI가 대본·음성·영상을 생성·편집하는 온라인 이용권 서비스를 제공합니다. 서비스는 이용권(크레딧)에 따라 렌즈·제작(렌더) 등 기능 이용량이 정해집니다.</p>
<h2>제2조 (이용계약의 성립)</h2>
<p>이용계약은 이용자가 구글 계정 등으로 가입하고 회사가 이를 승인함으로써 성립합니다. 회사는 운영상·기술상 필요에 따라 가입 승인을 보류하거나 이용을 제한할 수 있습니다.</p>
<h2>제3조 (이용권과 결제)</h2>
<ul>
<li>이용권은 계좌입금 등 회사가 안내하는 방법으로 결제하며, 입금 확인 후 활성화됩니다.</li>
<li>이용권별 제공 기능·기간·제작 횟수는 서비스 내 안내에 따릅니다.</li>
<li>환불에 관한 사항은 별도의 <a href="/refund" style="color:#6ff0d6">환불정책</a>을 따릅니다.</li>
</ul>
<h2>제4조 (이용자의 의무)</h2>
<ul>
<li>이용자는 타인의 저작권·초상권 등 권리를 침해하는 소재를 업로드해서는 안 됩니다. 업로드 소재에 대한 책임은 이용자에게 있습니다.</li>
<li>불법·음란·타인 비방 등 위법하거나 제3자의 권리를 침해하는 콘텐츠 제작에 서비스를 이용할 수 없습니다.</li>
<li>계정을 타인과 공유하거나 자동화 수단으로 부정 이용해서는 안 됩니다.</li>
</ul>
<h2>제5조 (콘텐츠의 권리)</h2>
<p>이용자가 서비스로 생성한 결과물의 이용권한은 이용자에게 있습니다. 다만 이용자가 업로드한 소재에 제3자의 권리가 포함된 경우, 그 이용에 대한 책임은 이용자가 부담합니다.</p>
<h2>제6조 (서비스의 중단·변경)</h2>
<p>회사는 시스템 점검·교체, 통신 두절, 천재지변 등 부득이한 사유가 있을 때 서비스 제공을 일시 중단할 수 있으며, 이 경우 가능한 범위에서 사전 고지합니다.</p>
<h2>제7조 (책임의 제한)</h2>
<p>서비스는 AI 자동 생성 결과물을 제공하며, 결과물의 상업적 성과·정확성·완전성을 보증하지 않습니다. 회사는 이용자가 업로드한 소재로 인한 분쟁, 이용자의 서비스 이용 결과에 대해 법령이 허용하는 범위에서 책임을 지지 않습니다.</p>
<h2>제8조 (약관의 개정)</h2>
<p>회사는 관련 법령을 위반하지 않는 범위에서 약관을 개정할 수 있으며, 개정 시 시행일과 개정 내용을 서비스 내에 공지합니다.</p>
"""

_PRIVACY_BODY = f"""
<p>{_BRAND['name']}(이하 "회사")는 「개인정보 보호법」 등 관련 법령을 준수하며, 이용자의 개인정보를 다음과 같이 처리합니다.</p>
<h2>1. 수집하는 개인정보 항목</h2>
<ul>
<li>구글 계정 로그인 시: 이메일 주소, 이름(프로필), 계정 식별자</li>
<li>이용·결제 과정에서: 연락처(전화번호), 입금자명 등 결제 확인에 필요한 정보</li>
<li>서비스 이용 과정에서 자동 생성: 접속 기록, 이용 내역, 기기·브라우저 정보</li>
</ul>
<h2>2. 개인정보의 이용 목적</h2>
<ul>
<li>회원 식별 및 로그인 유지, 이용권·결제 관리</li>
<li>서비스 제공, 이용 문의·고객 응대</li>
<li>부정 이용 방지 및 서비스 운영·개선</li>
</ul>
<h2>3. 보유 및 이용 기간</h2>
<p>회원 탈퇴 시 또는 수집·이용 목적 달성 시 지체 없이 파기합니다. 다만 관련 법령에 따라 보존이 필요한 경우 해당 기간 동안 보관합니다(예: 전자상거래법상 계약·결제 기록).</p>
<h2>4. 제3자 제공 및 처리위탁</h2>
<p>회사는 이용자의 개인정보를 동의 없이 외부에 제공하지 않습니다. 다만 서비스 제공을 위해 아래와 같이 일부 처리를 위탁할 수 있습니다.</p>
<ul>
<li>구글(Google): 계정 로그인 인증</li>
<li>AI·클라우드 인프라 제공사: 대본·음성·영상 생성 처리</li>
</ul>
<h2>5. 브라우저 확장프로그램 (로또 · 원클릭 담기)</h2>
<p>회사가 배포하는 크롬 확장프로그램 ‘원클릭 담기’는 아래 범위에서만 동작합니다.
크롬 웹스토어 심사 기준에 따라 처리 내용을 명시합니다.</p>
<ul>
<li><b>동작 범위</b>: 유튜브·틱톡·인스타그램·샤오홍슈·도우인의 영상 페이지에서만 ‘담기’ 버튼을 표시합니다. 그 외 사이트에서는 어떤 동작도 하지 않습니다.</li>
<li><b>수집·전송 항목</b>: 이용자가 ‘담기’ 버튼을 <b>직접 누른 경우에만</b> 해당 영상의 주소(URL)·제목·썸네일 이미지 주소를 회사 서버로 전송해 이용자 본인의 모음집에 저장합니다.</li>
<li><b>수집하지 않는 것</b>: 페이지의 다른 내용, 입력값, 비밀번호, 방문 기록을 수집하지 않습니다. 버튼을 누르지 않으면 어떤 정보도 전송되지 않습니다.</li>
<li><b>통신 대상</b>: 회사 서비스 서버(shoppingshorts.duckdns.org) 외 어떤 외부 도메인과도 통신하지 않습니다.</li>
<li><b>원격 코드</b>: 확장은 모든 코드를 설치 패키지에 포함하며, 외부에서 코드를 내려받아 실행하지 않습니다.</li>
<li><b>제3자 판매·양도</b>: 확장을 통해 수집한 정보를 제3자에게 판매하거나 양도하지 않으며, 신용도 평가·대출 목적으로 사용하지 않습니다.</li>
</ul>
<h2>6. 이용자의 권리</h2>
<p>이용자는 언제든지 본인의 개인정보를 조회·수정·삭제하거나 처리 정지를 요청할 수 있으며, 회원 탈퇴로 개인정보 삭제를 요청할 수 있습니다.
확장프로그램은 크롬 설정에서 언제든 삭제할 수 있으며, 삭제 시 이후 어떤 정보도 전송되지 않습니다.</p>
<h2>7. 개인정보 보호책임자</h2>
<p>개인정보 관련 문의는 아래 사업자정보의 문의처로 접수해 주시면 지체 없이 답변·처리합니다.</p>
"""

_REFUND_BODY = f"""
<p>{_BRAND['name']}(이하 "회사")의 이용권 결제에 대한 환불 기준은 다음과 같습니다. 본 서비스는 결제 즉시 이용 가능한 <b>디지털 콘텐츠(이용권)</b>입니다.</p>
<h2>1. 전액 환불 (미사용)</h2>
<p>결제 후 서비스 기능(렌즈·제작 등)을 <b>한 번도 사용하지 않은 경우</b>, 결제일로부터 <b>7일 이내</b> 요청 시 전액 환불해 드립니다.</p>
<h2>2. 환불 불가 (사용 개시 후)</h2>
<p>이용권으로 <b>제작(렌더)·렌즈 등 기능을 1회라도 사용한 경우</b>, 해당 이용권은 디지털 콘텐츠의 특성상 환불이 불가합니다. 이는 「전자상거래법」 제17조제2항에 따라 <b>사용에 의해 재화등의 가치가 현저히 감소한 경우</b>에 해당합니다.</p>
<h2>3. 회사 귀책 사유</h2>
<p>서비스 장애 등 회사의 책임 있는 사유로 이용권을 정상적으로 사용하지 못한 경우, 사용하지 못한 분에 대해 환불하거나 이용권을 복구해 드립니다. (제작 실패 시 소진된 이용 횟수는 자동 복구됩니다.)</p>
<h2>4. 환불 절차</h2>
<ul>
<li>환불은 아래 사업자정보의 문의처로 요청해 주세요.</li>
<li>계좌입금 결제분은 입금하신 계좌로, 요청 확인 후 영업일 기준 3일 이내 환불합니다.</li>
</ul>
<p style="color:#8aa0a0;font-size:12.5px;margin-top:14px">※ 본 정책은 관련 법령의 소비자 보호 규정에 우선하지 않으며, 법령과 상충하는 부분은 법령이 정하는 바에 따릅니다.</p>
"""


@app.get("/terms", response_class=HTMLResponse)
def _terms_page():
    return _legal_page("/terms", "이용약관", _TERMS_BODY)

@app.get("/privacy", response_class=HTMLResponse)
def _privacy_page():
    return _legal_page("/privacy", "개인정보처리방침", _PRIVACY_BODY)

@app.get("/refund", response_class=HTMLResponse)
def _refund_page():
    return _legal_page("/refund", "환불정책", _REFUND_BODY)


@app.get("/pricing", response_class=HTMLResponse)
def _pricing_page():
    return _with_pay(_PRICING_HTML)   # 공개 요금·이용권 페이지(비로그인 방문자 포함) + 결제링크 주입


@app.get("/account")
def _account_page():
    """★2026-08-17: 계정 화면을 마이페이지(/settings)의 '내 계정' 탭으로 합쳤다.

    사장님 제보 — "내 계정"과 "내 설정"이 따로 있어 키 등록표를 못 찾으셨다.
    같은 데이터(/api/me)를 두 화면이 각자 그리면 언젠가 어긋나기도 한다(0순위-B).
    옛 주소로 들어온 사람(북마크·외부 링크)이 끊기지 않게 넘겨준다.
    _ACCOUNT_HTML(=_ACCOUNT_TMPL)은 일부러 남겨뒀다 — 되돌릴 때 이 함수만 되돌리면 된다."""
    return RedirectResponse("/settings", status_code=307)


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
    # ★DASH_PASS가 비었으면 이 분기를 절대 타면 안 된다: 안 그러면 구글만 켠 배포(DASH_PASS 빈값)에서
    #   user=admin·pass=빈값이 admin/빈값과 compare_digest True가 돼 누구나 사장님 세션을 얻는다(백도어).
    if DASH_PASS and hmac.compare_digest(u, DASH_USER) and hmac.compare_digest(p, DASH_PASS):
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


def _notify_new_signup(*, name=None, username=None, phone=None, email=None):
    """새 회원 가입 → 사장님 텔레그램 알림(승인 재촉). 부가채널이라 절대 요청을 막지 않는다:
    notify.send_telegram이 무키/네트워크예외를 이미 삼키므로 여기선 얇게 감싸기만."""
    try:
        who = (name or "").strip() or (username or "").strip() or "새 회원"
        parts = [p for p in [phone, email] if p]           # 있는 것만 덧붙임
        tail = (" · " + " · ".join(parts)) if parts else ""
        from shopping_shorts import notify
        notify.send_telegram(f"🆕 새 가입 신청: {who}{tail}\n→ /admin 에서 승인해주세요 (승인 대기중)")
    except Exception:
        pass                                                # 알림 실패가 가입을 막으면 안 된다


@app.post("/api/signup")
async def _api_signup(req: Request):
    body = (await req.body()).decode("utf-8", "ignore")
    form = urllib.parse.parse_qs(body)
    u = (form.get("user") or [""])[0].strip()
    p = (form.get("pass") or [""])[0]
    name = (form.get("name") or [""])[0].strip()
    phone = (form.get("phone") or [""])[0].strip()
    if len(u) < 3 or len(p) < 4:
        return RedirectResponse("/signup?e=" + urllib.parse.quote("아이디 3자·비밀번호 4자 이상"), status_code=303)
    try:
        customer_id = Store(DB_PATH).create_customer(u, p, approved=False,
                                                     name=name or None, phone=phone or None)
    except ValueError:
        return RedirectResponse("/signup?e=" + urllib.parse.quote("이미 존재하는 아이디입니다"), status_code=303)
    _notify_new_signup(name=name, username=u, phone=phone)   # 사장님 텔레 알림(무키면 no-op)
    r = RedirectResponse("/", status_code=303)
    _set_session_cookie(r, customer_id)
    return r


# ── 구글 OAuth (유료게이트 고객 로그인, 2026-07-19) ──
# 라이브러리 없이: authorize 리다이렉트 → code → token 교환 → userinfo(sub,email).
# id_token JWT 서명검증 대신 Google token 엔드포인트(TLS)로 받은 access_token으로 userinfo를
# 직접 조회한다(서명검증 불필요·동등 안전). state 쿠키로 CSRF 방어.
_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def _google_configured():
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


def _google_authorize_url(state):
    q = urllib.parse.urlencode({
        "client_id": GOOGLE_CLIENT_ID, "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code", "scope": "openid email profile",
        "state": state, "access_type": "online", "prompt": "select_account"})
    return _GOOGLE_AUTH_URL + "?" + q


def _google_fetch_identity(code, _requests=None):
    """code → {sub, email} 또는 None. 네트워크는 _requests 주입으로 테스트 가능."""
    rq = _requests or requests
    tok = rq.post(_GOOGLE_TOKEN_URL, data={
        "code": code, "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI, "grant_type": "authorization_code"}, timeout=10)
    if tok.status_code != 200:
        return None
    access = tok.json().get("access_token")
    if not access:
        return None
    ui = rq.get(_GOOGLE_USERINFO_URL, headers={"Authorization": "Bearer " + access}, timeout=10)
    if ui.status_code != 200:
        return None
    d = ui.json()
    if not d.get("sub"):
        return None
    # 미인증 이메일은 신뢰하지 않는다(매칭은 sub로 하므로 로그인엔 지장 없음, 저장만 안 함).
    email = d.get("email") if d.get("email_verified") is True else None
    return {"sub": d["sub"], "email": email}


@app.get("/auth/google/login")
def _google_login(request: Request):
    if not _google_configured():
        return HTMLResponse("<h3 style='font-family:sans-serif'>구글 로그인이 아직 설정되지 않았어요.</h3>",
                            status_code=503)
    state = secrets.token_urlsafe(24)
    r = RedirectResponse(_google_authorize_url(state), status_code=303)
    r.set_cookie("g_state", state, max_age=600, httponly=True, samesite="lax")
    return r


@app.get("/auth/google/callback")
def _google_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    if error or not code:
        return RedirectResponse("/login?e=" + urllib.parse.quote("구글 로그인이 취소됐어요"), status_code=303)
    cookie_state = request.cookies.get("g_state")
    try:
        state_ok = bool(cookie_state) and hmac.compare_digest(cookie_state, state)
    except (TypeError, ValueError):
        state_ok = False       # 비-ASCII state 주입 등 → fail-closed
    if not state_ok:
        return RedirectResponse("/login?e=" + urllib.parse.quote("보안 검증 실패 — 다시 시도해주세요"), status_code=303)
    ident = _google_fetch_identity(code)
    if not ident:
        return RedirectResponse("/login?e=" + urllib.parse.quote("구글 인증에 실패했어요"), status_code=303)
    cid, created = Store(DB_PATH).get_or_create_by_google(
        ident["sub"], ident.get("email"), return_created=True)
    if cid is None:
        return RedirectResponse("/login?e=" + urllib.parse.quote("계정 생성 실패"), status_code=303)
    if created:                                              # 신규 구글 가입만 알림(재로그인은 조용히)
        _notify_new_signup(username="구글", email=ident.get("email"))
    r = RedirectResponse("/", status_code=303)
    _set_session_cookie(r, cid)
    r.delete_cookie("g_state")
    return r


def _client_ip(request):
    """nginx 뒤라 실제 IP는 X-Forwarded-For 첫 항목. 없으면 X-Real-IP, 그다음 소켓 주소."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "")


_ACCESS_SEEN = set()   # (cid, day, ip, ua) 이 프로세스에서 이미 기록한 조합 → DB 중복호출 방지


def _record_access(customer_id, request):
    """돌려쓰기 소프트감지: 로그인 사용자의 접속 IP·기기를 하루 단위로 기록(차단 안 함).
    best-effort — 절대 요청을 막지 않는다. 사장님(0)은 여러 기기가 정상이라 제외."""
    if not customer_id:
        return
    try:
        ip = _client_ip(request)
        ua = request.headers.get("user-agent", "")[:200]
        day = _today_utc()
        key = (customer_id, day, ip, ua)
        if key in _ACCESS_SEEN:
            return
        Store(DB_PATH).record_access(customer_id, ip, ua, day)
        # ★쓰기 성공 후에만 seen 표시 — 실패(DB락 등)면 다음 요청에서 재시도 가능(기록 유실 방지)
        if len(_ACCESS_SEEN) > 50000:      # 무한증식 방지 — 넘치면 비운다(날짜 바뀌면 어차피 새 키)
            _ACCESS_SEEN.clear()
        _ACCESS_SEEN.add(key)
    except Exception:
        pass


# 활동 트레일(2026-07-22): 경로→친절한 액션명. 이 목록에 걸리는 요청만 '몇 번 전 뭘 했다'로 남는다.
# 나머지(단순 조회·정적)는 last_seen(접속중)만 갱신하고 로그엔 안 남긴다.
_ACTIVITY_MAP = (
    ("/api/mix/start", "영상 제작 시작"),
    ("/api/produce/mix/render", "영상 렌더"),
    ("/api/produce/mix/settings", "제작 설정"),
    ("/api/grab", "재료 담기"),
    ("/api/find/analyze", "렌즈 분석"),
    ("/api/find/candidates", "유사영상 검색"),
    ("/api/find/translate_keyword", "키워드 번역"),
    ("/api/produce/extract_from_url", "대본 추출"),
    ("/api/produce/category", "카테고리 분류"),
    ("/api/produce/save_to_wiki", "대본 저장"),
    ("/api/collect", "소스 수집"),
)
_LASTSEEN_SEEN = {}   # cid → 마지막 last_seen 기록 epoch(60s 스로틀)
_ACTIVITY_SEEN = {}   # (cid, action) → 마지막 로그 epoch(60s 중복제거)


def _track_activity(customer_id, path):
    """접속중(last_seen) 갱신 + 의미있는 액션이면 활동 로그. best-effort, 요청 절대 안 막는다.
    사장님(0)은 항상 온라인이라 굳이 기록 안 함(노이즈)."""
    if not customer_id:
        return
    try:
        now = int(datetime.now(timezone.utc).timestamp())
        st = Store(DB_PATH)
        if now - _LASTSEEN_SEEN.get(customer_id, 0) >= 60:          # last_seen 60s 스로틀
            st.touch_customer(customer_id, now)
            if len(_LASTSEEN_SEEN) > 50000:
                _LASTSEEN_SEEN.clear()
            _LASTSEEN_SEEN[customer_id] = now
        for pref, label in _ACTIVITY_MAP:
            if path.startswith(pref):
                k = (customer_id, label)
                if now - _ACTIVITY_SEEN.get(k, 0) >= 60:            # 같은 액션 60s 내 1건만
                    st.record_activity(customer_id, label, now)
                    if len(_ACTIVITY_SEEN) > 50000:
                        _ACTIVITY_SEEN.clear()
                    _ACTIVITY_SEEN[k] = now
                break
    except Exception:
        pass


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
    # /s/{sid}·/api/share/v/{sid}·/api/share/t/{sid} = QR '폰으로 보내기' 공개경로(단축id 저장소
    #   조회, 로그인 불필요). 폰이 쿠키 없이 연다. /t는 선택 썸네일 PNG(2026-08-04, 영상과 한 번에 전송).
    #   ★/api/share/link(발급)은 여기 없음 → 로그인 게이트 유지(로그인해야 QR 발급).
    # /api/yt_relay/*는 사장님 PC 릴레이 에이전트가 로그인 쿠키 없이 호출한다(2026-07-24).
    #   자체 키 인증(_relay_auth_ok: YT_RELAY_KEY)이 있어 로그인 가드는 건너뛴다 — 안 그러면 유튜브 다운로드가 죽는다.
    # /api/coupang/relay/*도 같은 이유다(2026-07-29) — 쿠팡은 한국 IP가 아니면 막아서
    #   사장님 PC의 도우미가 로그인 쿠키 없이 폴링한다. 엔드포인트가 자체 토큰
    #   (COUPANG_RELAY_TOKEN)을 검사하고, 토큰이 비어 있으면 스스로 403으로 닫는다.
    if (path in _AUTH_ALLOW or path.startswith("/static") or path.startswith("/api/find/frame/")
            or path.startswith("/s/") or path.startswith("/api/share/v/")
            or path.startswith("/api/share/t/")
            or path.startswith("/api/yt_relay/") or path.startswith("/api/coupang/relay/")):
        return await call_next(request)
    customer_id = _verify_session(request.cookies.get("dash_auth"))
    if customer_id is not None:
        request.state.customer_id = customer_id
        _record_access(customer_id, request)   # 돌려쓰기 소프트감지(best-effort, 차단 안 함)
        _track_activity(customer_id, path)     # 접속중·활동기록(best-effort)
        lvl = access_level(customer_id)
        if lvl == "pending":
            # 승인 전 전면 차단. /logout만 통과(로그아웃 가능), /static은 위에서 이미 허용.
            if path == "/logout":
                return await call_next(request)
            if path.startswith("/api/"):
                return JSONResponse({"error": "승인 대기중이에요", "level": "pending"}, status_code=403)
            return HTMLResponse(_with_pay(_PENDING_HTML))
        # 유료게이트: 로그인은 됐으나 등급이 ranking_only(무료/체험만료)면 유료 경로 차단.
        # 사장님(0)·pro·체험중은 access_level=full이라 안 걸린다. deny-by-default.
        if lvl == "ranking_only" and _ranking_only_blocked(path, request.method):
            return JSONResponse(
                {"error": "유료 기능이에요. 결제하면 열려요.", "level": "ranking_only"},
                status_code=402)
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if path in ("/", "/index.html"):
        return HTMLResponse(_with_pay(_LANDING_HTML))   # 비로그인 방문자 → 공개 대문(랜딩) + 결제링크 주입
    if request.method == "GET" and path == "/pricing":
        return await call_next(request)      # 요금·이용권은 비로그인도 열람
    return RedirectResponse("/login")


# ── 유료게이트 접근권한 판정 (단일 진실원. API게이트·화면·크레딧 모두 이 함수만 본다) ──
def access_level(customer_id, now=None):
    """customer_id → "full"(전기능) | "ranking_only"(랭킹만) | "pending"(승인대기, 전면차단).
    규칙: 사장님(0)=full / 계정없음=ranking_only / 미승인(approved_at NULL)=pending /
    plan=pro=full / 체험중(now<full_access_until)=full / 그 외 ranking_only."""
    if _as_cid(customer_id) == 0:           # "0"(문자열)로 와도 사장님 (2026-07-30)
        return "full"                       # 사장님 = 영구 pro+admin
    cust = Store(DB_PATH).get_customer(customer_id)
    if not cust:
        return "ranking_only"
    if cust.get("approved_at") is None:
        # 🎁 무료체험 이벤트: 미승인이라도 가입 후 체험창(trial_ends_at) 안이면 full로 맛보기.
        #    창 밖이면 대기실 전면차단(pending). NULL(기존고객)은 0 취급 → 즉시 pending.
        if now is None:
            now = int(datetime.now(timezone.utc).timestamp())
        if now < (cust.get("trial_ends_at") or 0):
            return "full"
        return "pending"
    if cust.get("plan") == "pro":
        return "full"
    if now is None:
        now = int(datetime.now(timezone.utc).timestamp())
    if now < (cust.get("full_access_until") or 0):
        return "full"                       # 무료 체험 창
    return "ranking_only"


def _is_trial(customer_id, now=None):
    """무료체험 이벤트 중인가 = 미승인(approved_at None) AND 체험창(trial_ends_at) 안. 사장님(0) 제외."""
    if _as_cid(customer_id) == 0:
        return False
    cust = Store(DB_PATH).get_customer(customer_id)
    if not cust or cust.get("approved_at") is not None:
        return False
    if now is None:
        now = int(datetime.now(timezone.utc).timestamp())
    return now < (cust.get("trial_ends_at") or 0)


# ── 유료게이트 비용 방어: 계정별 일일 크레딧 + 전역 상한 ──
# 사장님 지시(2026-08-17): 본인 키가 있어도 영상제작·렌즈검색은 하루 10회.
# 서버 보호 목적이라 포인트와 별개로 유지한다. admin 설정으로 조정 가능.
_CREDIT_DEFAULTS = {"lens": 10, "render": 10, "script": 10}
_CREDIT_PRO_DEFAULTS = {"lens": 10, "render": 10, "script": 200}  # 하루 영상 최대 10개(돌려쓰기 상한, 2026-07-22)
_GLOBAL_CAP_DEFAULTS = {"lens": 200, "render": 100, "script": 400}


def _today_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _valid_backbone_main(raw, n_urls):
    """UI가 보낸 backbone_main(메인 소스 인덱스)을 검증. 정수·[0,n) 범위면 그대로,
    아니면 None(자동 선정). 잘못된 값에 믹스 job을 죽이지 않는다."""
    if raw is None:
        return None
    try:
        idx = int(raw)
    except (TypeError, ValueError):
        return None
    return idx if 0 <= idx < n_urls else None


def _as_cid(customer_id):
    """customer_id를 정수로 정규화. 숫자로 못 바꾸면 원값 그대로(비교만 실패하게).

    호출 경로가 섞여 있다 — 쿠키·큐 args는 문자열("0"), 내부 호출은 int(0). 등급 판정을
    `== 0`으로 하던 곳이 문자열을 무료 등급으로 떨궈 사고가 났다(2026-07-30)."""
    try:
        return int(customer_id)
    except (TypeError, ValueError):
        return customer_id


def check_and_count(customer_id, op):
    """유료 op(lens/render/script) 실행 전 호출. 일일 상한 초과면 False(막기),
    아니면 카운트+1 후 True. 관리자=무제한 / pro=limit_{op}_pro / 무료=limit_{op}."""
    # 관리자(사장님·지정 관리자)는 영상 만들기(render) 무제한 — pro 하루 상한(10)에 안 걸린다.
    # 렌즈(SerpApi)·대본(Gemini)은 실외부비용이라 관리자도 계량 유지(높은 pro 상한).
    if op == "render" and _is_admin(customer_id):
        return True
    st = Store(DB_PATH)
    # 🎁 무료체험 이벤트: 체험 유저의 render는 '오늘' 대신 영구 "trial" 버킷으로 딱 1회.
    #    렌즈·대본은 아래 일반 일일 한도 그대로(사장님이 담기·렌즈 열기를 택함).
    if op == "render" and _is_trial(customer_id):
        if st.usage_get(customer_id, "render", "trial") >= 1:
            return False
        st.usage_incr(customer_id, "render", "trial")
        return True
    # ★customer_id는 호출 경로에 따라 int 0 또는 문자열 "0"으로 온다(2026-07-30 실사고).
    #   `customer_id == 0`만 보면 문자열 "0"이 False가 돼 **사장님 계정이 무료 등급으로 계산**됐다
    #   → limit_script 10건. 예열(prewarm)은 customer_id를 문자열로 넘기므로, 하루 10건을 넘는
    #   순간 담긴 영상의 대본 예열이 전부 skipped_limit로 조용히 스킵됐다(실측: 3개 담았는데
    #   유튜브 2개만 대본이 생기고 인스타·샤오홍슈는 0.03초 만에 done 처리).
    is_paid = (_as_cid(customer_id) == 0) or (st.get_customer(customer_id) or {}).get("plan") == "pro"
    if is_paid:
        key, dflt = f"limit_{op}_pro", _CREDIT_PRO_DEFAULTS.get(op, 100)
    else:
        key, dflt = f"limit_{op}", _CREDIT_DEFAULTS.get(op, 5)
    try:
        limit = int(st.get_setting(key, dflt))
    except (TypeError, ValueError):
        limit = dflt
    day = _today_utc()
    if st.usage_get(customer_id, op, day) >= limit:
        return False
    st.usage_incr(customer_id, op, day)
    return True


def _charge_or_402(customer_id, op, service):
    """포인트를 깎는다. 부족하면 402 응답을 반환(호출부가 그대로 return).
    깎을 필요가 없으면(사용자가 자기 키 등록) None.

    ★차감 여부는 keyroute가 정한다 — 여기서 따로 판단하면 어긋난다(0순위-B).
    ★일일 상한(check_and_count)과 별개다. 상한은 서버 보호, 이건 비용 회수.
      그래서 상한을 통과한 뒤에도 이걸 또 부른다 — 둘 다 통과해야 실행된다.

    cid 0(사장님 본인)은 keyroute가 개인키 조회를 건너뛰고 사장님 키를 주므로
    should_charge가 True를 준다. 하지만 자기 키로 자기한테 청구하는 꼴이라
    과금 대상이 아니다 — mix_pipeline._charge_clean과 같은 판단을 쓴다."""
    if not keyroute.as_cid(customer_id):
        return None
    store = Store(DB_PATH)
    if not keyroute.should_charge(store, customer_id, service):
        return None
    need = pricing.cost(store, op)
    if points.deduct(store, customer_id, need, op):
        return None
    return JSONResponse(status_code=402, content={
        "ok": False,
        "error": f"포인트가 부족합니다 (필요 {pricing.to_display(need)}P, "
                 f"보유 {pricing.to_display(points.balance(store, customer_id))}P)"})


def _refund_points(customer_id, op, service):
    """_charge_or_402가 깎은 포인트를 실패 시 되돌린다 — refund_credit(일일 크레딧)과 대칭.

    ★"성공한 작업만 과금한다"는 기존 규칙을 포인트에도 그대로 적용한다. 크레딧만
      돌려주고 포인트는 안 돌려주면, 실패한 요청마다 잔액이 조용히 갉힌다.
    ★깎는 조건과 **같은 조건**으로만 돌려준다(cid 0·사용자 키는 애초에 안 깎았으니
      환불도 없다). 여기서 따로 판단하면 안 깎은 사람에게 돈이 생긴다(0순위-B).
    ★핸들러의 finally에서 불리므로 자체 예외를 삼킨다 — 환불 중 DB 락이 나도
      원래 응답/예외를 가리면 안 된다(refund_credit과 같은 이유)."""
    try:
        if not keyroute.as_cid(customer_id):
            return
        store = Store(DB_PATH)
        if not keyroute.should_charge(store, customer_id, service):
            return
        points.refund(store, customer_id, pricing.cost(store, op), op)
    except Exception:
        import sys as _s
        import traceback
        traceback.print_exc(file=_s.stderr)


def global_incr_and_alert(op):
    """전역 일일 사용량(customer_id=-1) 증가. 90% 도달 시 텔레그램 1회 알림(best-effort)."""
    st = Store(DB_PATH)
    n = st.usage_incr(-1, op, _today_utc())
    try:
        cap = int(st.get_setting(f"global_cap_{op}", _GLOBAL_CAP_DEFAULTS.get(op, 200)))
    except (TypeError, ValueError):
        cap = _GLOBAL_CAP_DEFAULTS.get(op, 200)
    if cap > 0 and n == max(1, int(cap * 0.9)):   # 90% 첫 도달 1회만
        try:
            from shopping_shorts import notify
            notify.send_telegram(f"⚠️ [유료게이트] {op} 전역 일일 사용 {n}/{cap} (90% 도달)")
        except Exception:
            pass
    return n


def _lens_api_keys(customer_id):
    """렌즈 검색에 쓸 SerpApi 키 목록. **여기 한 곳에서만 정한다**(0순위-B).

    사용자가 마이페이지에 SerpApi 키를 등록했으면 그 키만, 아니면 사장님 env 키.
    폴백 없음은 keyroute가 지킨다 — 여기서 섞지 마라.

    ★과금 판단(OP_LENS를 깎을지)도 같은 SVC_SERPAPI를 봐야 한다. 키를 고르는 쪽과
      과금하는 쪽이 다른 서비스를 보면 "키 등록했는데 포인트도 깎임"이 난다."""
    keys, _ = keyroute.keys_for(Store(DB_PATH), customer_id, keyroute.SVC_SERPAPI)
    return keys


def _global_over_cap(op):
    """전역 일일 사용량이 상한 이상이면 True(차단). cap<=0이면 무제한(False).
    ⚠️ global_incr_and_alert는 알림만 하고 안 막았다 — 다계정이 SerpApi·렌더를 태워도
    사장님이 텔레 핑만 받을 뿐 비용은 계속 나갔다. 설계 §1(비용 게이트 최우선)이 의지한
    '전역 상한'이 실제로 막도록, 유료 op 실행 전에 이걸로 선체크한다."""
    st = Store(DB_PATH)
    try:
        cap = int(st.get_setting(f"global_cap_{op}", _GLOBAL_CAP_DEFAULTS.get(op, 200)))
    except (TypeError, ValueError):
        cap = _GLOBAL_CAP_DEFAULTS.get(op, 200)
    if cap <= 0:
        return False
    return st.usage_get(-1, op, _today_utc()) >= cap


def refund_credit(customer_id, op):
    """예약(check_and_count + global_incr_and_alert)했던 크레딧을 실패 시 되돌린다 —
    계정·전역 둘 다. points.refund와 대칭. 실 로직은 Store.refund_daily_credit.
    ★핸들러의 finally에서 불리므로 자체 예외를 삼킨다 — 환불 중 DB 락 등이 나도 원래
    응답/예외(502·500)를 가리면 안 된다(리뷰 G2)."""
    try:
        Store(DB_PATH).refund_daily_credit(customer_id, op)
    except Exception:
        import sys as _s
        import traceback
        traceback.print_exc(file=_s.stderr)


@app.get("/api/me")
def _api_me(request: Request):
    """프론트가 부팅 시 호출 — 등급·체험 남은날·크레딧 상한."""
    cid = getattr(request.state, "customer_id", 0)
    st = Store(DB_PATH)
    cust = st.get_customer(cid) if cid else None
    now = int(datetime.now(timezone.utc).timestamp())
    plan = "pro" if cid == 0 else (cust or {}).get("plan", "free")
    fau = (cust or {}).get("full_access_until", 0) if cust else 0
    if plan == "pro" or cid == 0:
        days_left = None
    else:
        days_left = max(0, (fau - now + 86399) // 86400) if fau else 0
    def _lim(k, d):
        try:
            return int(st.get_setting(k, d))
        except (TypeError, ValueError):
            return d
    # 계정 패널(2026-07-22): 구글 이메일·이름·가입 며칠째·오늘 사용량.
    is_admin = _is_admin(cid)   # 사장님(0) + 이메일 화이트리스트(parklotto12) 모두 관리자

    email = "관리자" if is_admin else ((cust or {}).get("email") or (cust or {}).get("username") or "")
    name = (cust or {}).get("name") or "" if cust else ""
    # 등급별 실제 크레딧 상한(check_and_count와 동일 규칙) — 패널에 'x/상한' 표시용.
    if is_admin:
        usage = None                       # 관리자=무제한, 사용량 표시 안 함
        limits = {"lens": None, "render": None, "script": None}
    else:
        day = _today_utc()
        usage = {op: st.usage_get(cid, op, day) for op in ("lens", "render", "script")}
        if plan == "pro":
            limits = {op: _lim(f"limit_{op}_pro", _CREDIT_PRO_DEFAULTS.get(op, 100))
                      for op in ("lens", "render", "script")}
        else:
            limits = {op: _lim(f"limit_{op}", _CREDIT_DEFAULTS.get(op, 5))
                      for op in ("lens", "render", "script")}
    # 가입 며칠째 — created_at은 UTC 문자열(datetime('now') 또는 ISO). 파싱 실패 시 None.
    member_days = None
    ca = (cust or {}).get("created_at") if cust else None
    if ca:
        try:
            dt = datetime.fromisoformat(str(ca).replace("Z", "+00:00").split(".")[0])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            member_days = max(0, (datetime.now(timezone.utc) - dt).days) + 1
        except (ValueError, TypeError):
            member_days = None
    return {"customer_id": cid, "level": access_level(cid, now), "plan": plan,
            "days_left": days_left, "is_admin": is_admin,
            "email": email, "name": name, "member_days": member_days,
            "usage": usage, "usage_limits": limits,
            "limits": {"lens": _lim("limit_lens", 5), "render": _lim("limit_render", 2),
                       "script": _lim("limit_script", 10)},
            "contact": {"kakao": st.get_setting("contact_kakao", ""),
                        "phone": st.get_setting("contact_phone", ""),
                        "pay": st.get_setting("pay_url", "")}}


# ── 유료게이트 관리자(사장님 cid0 전용) — 결제 승격·설정 조정 ──
# 사장님(cid0) 외 추가 관리자 = 이 구글 계정들. 코드로만 바꾼다(admin UI로 못 늘려 공격면 없음).
_ADMIN_EMAILS = {"parklotto12@gmail.com"}


def _code_admin(customer_id):
    """코드로 고정된 관리자 = 사장님(0) 또는 이메일 화이트리스트. UI로 회수 불가(락아웃 방지 바닥)."""
    if _as_cid(customer_id) == 0:
        return True
    if not customer_id:
        return False
    email = (Store(DB_PATH).get_customer(customer_id) or {}).get("email") or ""
    return email.lower() in _ADMIN_EMAILS


def _is_admin(customer_id):
    """관리자 = 사장님(0) 또는 이메일 화이트리스트(코드) 또는 사장님이 UI로 지정(customers.admin=1).
    지정 관리자는 권한이 코드 관리자와 완전히 동일하다."""
    if _as_cid(customer_id) == 0:
        return True
    if not customer_id:
        return False
    cust = Store(DB_PATH).get_customer(customer_id)
    if not cust:
        return False
    return ((cust.get("email") or "").lower() in _ADMIN_EMAILS) or bool(cust.get("admin"))


def _require_admin(request):
    if not _is_admin(getattr(request.state, "customer_id", None)):
        return JSONResponse({"error": "관리자 전용"}, status_code=403)
    return None


_ADMIN_SETTING_KEYS = {"trial_days", "trial_event_hours", "limit_lens", "limit_render", "limit_script",
                       "limit_lens_pro", "limit_render_pro", "limit_script_pro",
                       "global_cap_lens", "global_cap_render", "global_cap_script",
                       "contact_kakao", "contact_phone", "pay_url",
                       "bank_name", "bank_account", "bank_holder", "deposit_note",
                       "biz_name", "biz_owner", "biz_regno", "biz_addr", "biz_sales_no", "biz_email"}


@app.get("/api/admin/customers")
def _admin_customers(request: Request):
    denied = _require_admin(request)
    if denied:
        return denied
    st = Store(DB_PATH)
    day = _today_utc()
    since7 = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")  # 돌려쓰기 감지 창(7일)
    out = []
    for cu in st.list_customers():
        cu["level"] = access_level(cu["id"])
        cu["usage"] = {op: st.usage_get(cu["id"], op, day) for op in ("lens", "render", "script")}
        cu["access_7d"] = st.access_summary(cu["id"], since7)   # {ips, devices} 최근 7일 고유 수
        cu["is_admin"] = _is_admin(cu["id"])                    # 관리자 배지용
        cu["code_admin"] = _code_admin(cu["id"])                # 코드 고정 관리자(UI 토글 불가)
        # last_seen은 store.list_customers가 이미 넣어줌 → 프론트가 '접속중/N분전' 계산
        out.append(cu)
    return {"ok": True, "customers": out, "settings": st.all_settings()}


@app.get("/api/admin/pending")
def _admin_pending(request: Request):
    """승인 대기 회원 요약 — 프론트(sidebar.js)가 폴링해 '띠링' 팝업을 띄운다.
    관리자만 200. 비관리자는 _require_admin이 막아 폴러가 조용히 꺼진다(부하 없음)."""
    denied = _require_admin(request)
    if denied:
        return denied
    pend = Store(DB_PATH).pending_customers()
    newest = pend[0] if pend else None                      # id DESC 정렬이라 [0]이 최신
    # 운영 사고 쪽지(2026-08-04). 이 폴러는 이미 관리자 화면이 돌리고 있으므로 여기 얹으면
    # 새 폴러·새 배선 없이 '띠링'이 그대로 재사용된다. 비관리자는 위 _require_admin이 막는다.
    try:
        from shopping_shorts import ops_alert
        alerts = ops_alert.list_alerts()
    except Exception:                                       # noqa: BLE001 — 알림이 승인화면을 막지 않는다
        alerts = []
    return {"ok": True, "count": len(pend),
            "newest_id": (newest["id"] if newest else 0),
            "newest": newest, "pending": pend[:20],          # 팝업 목록은 최근 20건까지
            "alerts": alerts,
            "alert_unread": sum(1 for a in alerts if not a.get("read"))}


@app.post("/api/admin/alerts/read")
def _admin_alerts_read(request: Request):
    """운영 사고 쪽지 전부 읽음 처리(배지 끄기). 관리자만."""
    denied = _require_admin(request)
    if denied:
        return denied
    from shopping_shorts import ops_alert
    return {"ok": True, "marked": ops_alert.mark_read()}


@app.post("/api/admin/customer/update")
async def _admin_customer_update(request: Request):
    """관리자 정보수정 — 고객 이름·전화. body: {customer_id, name?, phone?}."""
    denied = _require_admin(request)
    if denied:
        return denied
    body = await request.json()
    try:
        cid = int(body.get("customer_id"))
    except (TypeError, ValueError):
        return JSONResponse({"error": "customer_id 필요"}, status_code=400)
    Store(DB_PATH).update_customer_info(cid, body.get("name"), body.get("phone"))
    return {"ok": True}


@app.post("/api/admin/customer/delete")
async def _admin_customer_delete(request: Request):
    """관리자 완전 삭제 — 고객+결제이력+접속기록. 사장님(0)·다른 관리자는 못 지운다(락아웃 방지)."""
    denied = _require_admin(request)
    if denied:
        return denied
    body = await request.json()
    try:
        cid = int(body.get("customer_id"))
    except (TypeError, ValueError):
        return JSONResponse({"error": "customer_id 필요"}, status_code=400)
    if _is_admin(cid):
        return JSONResponse({"error": "관리자 계정은 삭제할 수 없어요"}, status_code=400)
    Store(DB_PATH).delete_customer(cid)
    return {"ok": True}


@app.post("/api/admin/customer/set_admin")
async def _admin_customer_set_admin(request: Request):
    """관리자 지정/회수 — 사장님이 다른 계정에 관리자 권한(관리자와 동일)을 준다.
    body: {customer_id, admin: bool}. 코드 고정 관리자(사장님·화이트리스트)는 UI로 못 바꾼다."""
    denied = _require_admin(request)
    if denied:
        return denied
    body = await request.json()
    try:
        cid = int(body.get("customer_id"))
    except (TypeError, ValueError):
        return JSONResponse({"error": "customer_id 필요"}, status_code=400)
    if _code_admin(cid):
        return JSONResponse({"error": "고정 관리자는 변경할 수 없어요"}, status_code=400)
    Store(DB_PATH).set_customer_admin(cid, bool(body.get("admin")))
    return {"ok": True}


@app.get("/api/admin/customer/activity")
def _admin_customer_activity(request: Request, customer_id: int):
    """이 고객의 최근 활동(몇 번 전 뭘 했다). admin 전용."""
    denied = _require_admin(request)
    if denied:
        return denied
    return {"ok": True, "activity": Store(DB_PATH).recent_activity(customer_id, 12)}


@app.post("/api/admin/set_plan")
async def _admin_set_plan(request: Request):
    denied = _require_admin(request)
    if denied:
        return denied
    body = await request.json()
    try:
        cid = int(body.get("customer_id"))
    except (TypeError, ValueError):
        return JSONResponse({"error": "customer_id 필요"}, status_code=422)
    plan = body.get("plan")
    if plan not in ("free", "pro"):
        return JSONResponse({"error": "plan=free|pro"}, status_code=422)
    days = body.get("days")
    st = Store(DB_PATH)
    if plan == "pro":
        st.set_plan(cid, "pro")                         # 결제 승격 = 전기능 무기한
    elif days:
        until = int(datetime.now(timezone.utc).timestamp()) + int(days) * 86400
        st.set_plan(cid, "free", full_access_until=until)   # 체험 창 재부여
    else:
        st.set_plan(cid, "free", full_access_until=0)   # 즉시 무료(랭킹만)로 내림
    import sys as _s
    print(f"[admin] set_plan cid={cid} plan={plan} days={days}", file=_s.stderr)  # 변경 로그
    return {"ok": True}


@app.post("/api/admin/approve")
async def _admin_approve(request: Request):
    denied = _require_admin(request)
    if denied:
        return denied
    body = await request.json()
    try:
        cid = int(body.get("customer_id"))
        period_days = int(body.get("period_days"))
        amount = int(body.get("amount"))
    except (TypeError, ValueError):
        return JSONResponse({"error": "customer_id·period_days·amount 필요"}, status_code=422)
    if period_days < 0 or amount < 0:
        return JSONResponse({"error": "음수 불가"}, status_code=422)
    method = (body.get("method") or "").strip()
    note = body.get("note")
    st = Store(DB_PATH)
    cust = st.approve_customer(cid, period_days, amount, method, note=note)
    if cust is None:
        return JSONResponse({"error": "없는 고객"}, status_code=404)
    import sys as _s
    print(f"[admin] approve cid={cid} +{period_days}d {amount}원", file=_s.stderr)
    return {"ok": True, "customer": cust}


@app.post("/api/admin/payment")
async def _admin_payment(request: Request):
    """이미 승인된 고객에 결제 추가+기간 연장(approve_customer 재호출과 동일 경로)."""
    denied = _require_admin(request)
    if denied:
        return denied
    body = await request.json()
    try:
        cid = int(body.get("customer_id"))
        period_days = int(body.get("period_days"))
        amount = int(body.get("amount"))
    except (TypeError, ValueError):
        return JSONResponse({"error": "customer_id·period_days·amount 필요"}, status_code=422)
    if period_days < 0 or amount < 0:
        return JSONResponse({"error": "음수 불가"}, status_code=422)
    method = (body.get("method") or "").strip()
    note = body.get("note")
    st = Store(DB_PATH)
    cust = st.approve_customer(cid, period_days, amount, method, note=note)
    if cust is None:
        return JSONResponse({"error": "없는 고객"}, status_code=404)
    return {"ok": True, "customer": cust}


@app.get("/api/admin/payments")
def _admin_payments(request: Request, customer_id: int = 0):
    denied = _require_admin(request)
    if denied:
        return denied
    return {"payments": Store(DB_PATH).list_payments(customer_id)}


@app.post("/api/admin/settings")
async def _admin_settings(request: Request):
    denied = _require_admin(request)
    if denied:
        return denied
    body = await request.json()
    st = Store(DB_PATH)
    for k, v in (body or {}).items():
        if k in _ADMIN_SETTING_KEYS:
            st.set_setting(k, v)
    return {"ok": True, "settings": st.all_settings()}


@app.get("/admin", response_class=HTMLResponse)
def _admin_page(request: Request):
    if not _is_admin(getattr(request.state, "customer_id", None)):
        return HTMLResponse("<h2 style='font-family:sans-serif'>관리자 전용입니다</h2>", status_code=403)
    return FileResponse(Path(__file__).parent / "static" / "admin.html",
                        media_type="text/html; charset=utf-8")


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
    # ★CORS 허용(2026-08-04, 확장프로그램 도입): 확장은 이 로직을 페이지 월드에서
    # <script src>로 불러온다. 같은 파일을 유저스크립트(GM_xmlhttpRequest)와 공유하므로
    # 한 곳만 고치면 양쪽 모두 자동 반영된다. 공개 정적 JS라 노출 위험은 없다.
    return FileResponse(p, media_type="text/javascript; charset=utf-8",
                        headers={"Cache-Control": "public, max-age=60",
                                 "Access-Control-Allow-Origin": "*"})


@app.get("/grab_extension.zip", include_in_schema=False)
def _serve_grab_extension():
    """원클릭 담기 **확장프로그램**(.zip) — 텀퍼몽키 없이 이것만 설치하면 된다.

    왜 만들었나(2026-08-04 사장님): 유저스크립트 방식은 사용자가 4단계를 밟아야 하고
    그중 크롬 토글 2개("개발자 모드", "사용자 스크립트 허용")는 **파일로 못 켠다**(크롬 정책).
    실제로 2026-07-21에 고객이 그 토글을 몰라 📥가 안 뜨는 사고가 났다.
    확장프로그램은 "사용자 스크립트 허용" 토글 자체가 필요 없어 단계가 절반으로 준다.

    zip은 요청 때 메모리에서 만든다 — 빌드 산출물을 repo에 커밋하지 않기 위해서다
    (소스가 바뀌면 zip도 자동으로 최신이 된다. mtime 기준 캐시로 매번 다시 만들지 않는다)."""
    import io
    import zipfile
    edir = Path(__file__).parent / "extension"
    if not edir.is_dir():
        return JSONResponse({"error": "확장 소스 없음"}, status_code=404)
    # ★로직은 userscript/grab_logic.js가 **원본**이다. zip을 만들 때마다 그걸 담는다 —
    # extension/ 안의 사본은 개발용 편의일 뿐이고, 배포물엔 항상 원본이 들어가야 한다.
    # (두 벌을 손으로 관리하면 반드시 어긋나고, 그럼 확장 사용자만 옛 로직을 쓰게 된다.)
    logic_src = Path(__file__).parent / "userscript" / "grab_logic.js"
    # ★도우인 메인월드 스크립트(2026-08-17) — manifest가 world:"MAIN"으로 크롬에게 직접
    # 주입시키는 파일. 격리월드에서 <script>를 만드는 종전 방식은 **확장 자신의 CSP**
    # ('unsafe-inline' 없음)에 차단됐다(사장님 콘솔 실측: grab_logic.js:716 blocked).
    # 도우인 CSP가 아니라 확장 CSP였다 — 그래서 world:"MAIN"이면 그 검사를 아예 안 탄다.
    #
    # 이 파일을 손으로 관리하지 않는다: grab_logic.js의 _douyinMainWorld 본문을 **그때그때
    # 잘라내 만든다**. 두 벌을 손으로 두면 반드시 어긋나고, 그러면 도우인만 옛 로직을 쓴다
    # (0순위-B: 같은 판단을 두 군데 적지 마라).
    def _douyin_main_js(logic_text: str) -> str:
        """grab_logic.js에서 _douyinMainWorld 함수를 떼어내 즉시실행 스크립트로 만든다."""
        head = "  function _douyinMainWorld() {"
        i = logic_text.find(head)
        if i < 0:
            return ""                      # 함수가 사라졌으면 빈 문자열 → zip에 넣지 않는다
        # 함수 끝 = 같은 들여쓰기(2칸)의 닫는 중괄호 첫 줄
        rest = logic_text[i + len(head):]
        end = rest.find("\n  }")
        if end < 0:
            return ""
        body = rest[:end]
        return ("// ⚠️자동 생성 파일 — 손으로 고치지 마라.\n"
                "// 원본: userscript/grab_logic.js 의 _douyinMainWorld()\n"
                "// /grab_extension.zip 이 요청마다 원본에서 다시 잘라 만든다.\n"
                "// world:\"MAIN\" 으로 크롬이 직접 주입 → 확장 CSP의 인라인 검사를 타지 않는다.\n"
                "(function () {" + body + "\n})();\n")
    # store/ 는 **웹스토어 제출용 자료**(스크린샷·제출가이드)라 배포물에 넣지 않는다.
    # 넣으면 사용자 zip에 내부 문서와 이미지 수백 KB가 딸려 나간다(2026-08-04 실측으로 발견).
    # douyin_main.js도 자동 생성물이라 extension/ 안의 사본은 담지 않는다(grab_logic.js와 같은 이유).
    files = sorted(p for p in edir.rglob("*")
                   if p.is_file() and p.name not in ("grab_logic.js", "douyin_main.js")
                   and "store" not in p.relative_to(edir).parts)
    stamp = str(max([p.stat().st_mtime_ns for p in files]
                    + [logic_src.stat().st_mtime_ns if logic_src.exists() else 0], default=0))
    cached = getattr(_serve_grab_extension, "_cache", None)
    if not (cached and cached[0] == stamp):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for p in files:
                z.write(p, p.relative_to(edir).as_posix())
            if logic_src.exists():
                _logic_text = logic_src.read_text(encoding="utf-8")
                z.writestr("grab_logic.js", _logic_text)
                _dy = _douyin_main_js(_logic_text)
                if _dy:
                    z.writestr("douyin_main.js", _dy)
        cached = (stamp, buf.getvalue())
        _serve_grab_extension._cache = cached
    return Response(
        content=cached[1], media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="lotto-grab-extension.zip"',
                 "Cache-Control": "no-cache"})


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
             url: str = "", thumbnail: str = "", title: str = "", video_url: str = ""):
    """북마클릿/유저스크립트가 여는 팝업 대상. 세션쿠키로 고객을 직접 식별(_AUTH_ALLOW라
    미들웨어가 customer_id를 안 채우므로 여기서 검증). 영상 즐겨찾기(mix_basket)에 멱등 추가하고
    백그라운드로 메타(썸네일·조회수 등)를 보강한다(팝업은 즉시 반환)."""
    cid = _verify_session(request.cookies.get("dash_auth")) if _AUTH_ON else 0
    if cid is None:
        return _grab_popup_html(False, "로그인이 필요해요",
                                "shoppingshorts.duckdns.org에 먼저 로그인하세요")
    # 유료게이트: /api/grab은 _AUTH_ALLOW라 미들웨어 게이트를 우회한다 → 여기서 직접 등급 확인.
    # 담기(+백그라운드 메타 크롤 비용)는 full 전용. pending(승인대기)·ranking_only 모두 차단.
    lvl = access_level(cid)
    if lvl != "full":
        title = "승인 대기중이에요" if lvl == "pending" else "유료 기능이에요"
        msg = ("운영자 승인 후 담기를 쓸 수 있어요" if lvl == "pending"
               else "무료 체험이 끝났어요. 결제하면 담기를 계속 쓸 수 있어요")
        return _grab_popup_html(False, title, msg)
    platform = _grab_platform(url)
    if not platform:
        return _grab_popup_html(False, "담을 수 없는 링크예요", "유튜브·틱톡·샤오홍슈·도우인 영상 페이지에서 눌러주세요")
    sc = "grab_" + platform + "_" + hashlib.sha1(url.encode("utf-8", "ignore")).hexdigest()[:12]
    # ★영상 파일 직접 주소(2026-08-17) — 담기 스크립트가 보내면 함께 보관한다.
    #   도우인은 yt-dlp가 쿠키를 요구해 페이지 URL로는 못 받는다(서버·PC 양쪽 재현).
    #   브라우저에는 CDN 주소가 그대로 있으므로 담는 순간 받아 두는 것이 유일하게 확실한 길.
    #   아무나 임의 주소를 넣지 못하게 **알려진 영상 CDN만** 받아들인다.
    vurl = (video_url or "").strip()
    if vurl and not _is_grabbable_media(vurl):
        vurl = ""
    store = Store(DB_PATH)
    added = store.mix_basket_add(
        sc, url=url, thumbnail=thumbnail or "", name=(title or "")[:120],
        caption=(title or "")[:200], customer_id=cid, video_url=vurl)
    # ★다시 담으면 실패 기록을 지워 한 번 더 해본다(2026-08-16).
    #   실패 횟수가 차면 영영 안 뽑는 장치가 있는데, 받는 방법이 바뀌어도 그 옛 판정이
    #   남아 시도조차 막았다(도우인 실사고: 새 경로 배포 후에도 로그 0건, 화면엔 오전에
    #   찍힌 실패가 계속 떠 있었다). 사장님이 다시 담는 건 '다시 해보라'는 뜻이다.
    store.autoload_reset(sc)
    background_tasks.add_task(_enrich_grab, url, sc, cid)   # 썸네일·조회수 등 보강
    _enqueue_prewarm(Store(DB_PATH), sc, url, caption=(title or "")[:200], customer_id=cid)
    return _grab_popup_html(True, "영상 즐겨찾기에 담겼어요!" if added else "이미 담겨 있어요",
                            f"{platform} · 왼쪽 ⭐영상 즐겨찾기에서 확인")


# 북마클릿 본문(플랫폼 페이지에서 실행) — 따옴표 충돌을 피해 base64로 실어 페이지에서 atob.
# ★설치페이지(우리 도메인)에서 '클릭'하면 자기 URL을 담으려다 실패해 헷갈린다 → 우리 도메인
# 에서 실행되면 담지 말고 '드래그하세요' 안내만 띄운다(사장님 첫 사용 혼동, 2026-07-18).
_GRAB_BOOKMARKLET = r'''javascript:(function(){var h=location.host||"";if(/shoppingshorts|localhost|127\.0\.0\.1/.test(h)){alert("❗ 이 버튼은 '눌러서' 쓰는 게 아니라, 마우스로 북마크바에 끌어다(드래그) 저장하는 거예요.\n\n저장한 뒤, 유튜브·틱톡·샤오홍슈·도우인에서 영상을 열고 그 북마크를 누르세요.");return;}var q=function(s){var e=document.querySelector(s);return e?e.content:"";};var th=q('meta[property="og:image"]');var ti=q('meta[property="og:title"]')||document.title||"";window.open("__BASE__/api/grab?url="+encodeURIComponent(location.href)+"&thumbnail="+encodeURIComponent(th)+"&title="+encodeURIComponent(ti.slice(0,120)),"ss_grab","width=380,height=220");})();'''


# 설치 안내 '신호등' 페이지(자가감지). __TM_URL__=텀퍼몽키 스토어 딥링크, __BM64__=북마클릿.
# 설치가 끝나면 유저스크립트가 이 페이지에서 실행돼 data-ss-grab-installed 표식을 남기고
# (grab_logic.js 비컨), 아래 스크립트가 폴링·포커스새로고침으로 감지해 자동으로 '완료'로 바꾼다.
_GRAB_SETUP_HTML = """<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>\U0001F4E5 담기 켜기</title>
<style>
  :root{color-scheme:light}
  *{box-sizing:border-box}
  body{margin:0;background:#f3f5f8;color:#1a1f2b;font-family:system-ui,-apple-system,"Malgun Gothic",sans-serif}
  .wrap{max-width:560px;margin:0 auto;padding:28px 18px 60px}
  h1{font-size:26px;margin:.2em 0 .3em}
  .lead{font-size:17.5px;line-height:1.7;color:#232a36;margin:0 0 20px}
  .warn{background:#fff3f2;border:2px solid #e0245e;border-radius:12px;padding:14px 16px;font-size:15px;line-height:1.6;margin:0 0 18px;color:#a01040}
  .step{display:flex;gap:14px;align-items:flex-start;background:#fff;border:2px solid #e3e7ee;border-radius:16px;padding:18px 16px;margin:0 0 14px;transition:.25s}
  .step.ok{border-color:#1f9d55;background:#f0fbf4}
  .num{flex:0 0 40px;height:40px;border-radius:50%;background:#1f6feb;color:#fff;font-weight:800;font-size:19px;display:flex;align-items:center;justify-content:center}
  .step.ok .num{background:#1f9d55}
  #s3 .num{background:#c3c9d4}
  #s3.ok .num{background:#1f9d55}
  .cbody{flex:1;min-width:0}
  .t{font-size:18px;font-weight:800;margin-bottom:4px}
  .d{font-size:15px;line-height:1.6;color:#3c4759;margin-bottom:12px}
  .check{flex:0 0 auto;font-size:22px;color:#c3c9d4;font-weight:800}
  .step.ok .check{color:#1f9d55}
  .btn{display:inline-block;background:#1f6feb;color:#fff;text-decoration:none;font-weight:800;font-size:17px;padding:14px 20px;border-radius:12px;border:none;cursor:pointer;box-shadow:0 3px 10px rgba(31,111,235,.28)}
  .btn:active{transform:translateY(1px)}
  .btn.ghost{background:#fff;color:#1f6feb;border:2px solid #1f6feb;box-shadow:none}
  .donebox{background:#eafaf0;border:2px solid #1f9d55;border-radius:16px;padding:20px 18px;font-size:17px;line-height:1.6;color:#186c3c;margin:4px 0 8px}
  .recheck{display:block;width:100%;margin:8px 0 0;background:#fff;border:2px solid #cbd2dd;border-radius:12px;padding:13px;font-size:15px;font-weight:700;color:#3a4252;cursor:pointer}
  .alt{margin:22px 0 0}
  .alt>summary{cursor:pointer;color:#6b7488;font-weight:700;font-size:14px;padding:8px 0}
  .altbox{background:#fff7e6;border:1px solid #f0c36d;border-radius:12px;padding:16px;margin:8px 0;font-size:14px;line-height:1.6;color:#7a6528}
  .altbox .hi{font-weight:800;color:#a86;margin-bottom:6px}
  .foot{color:#8a92a4;font-size:13px;line-height:1.6;margin-top:18px}
  a{color:#1f6feb}
  .guide{margin:4px 0 22px;background:#fff;border:2px solid #e3e7ee;border-radius:16px;padding:18px 16px}
  .ghead{font-size:20px;font-weight:800;margin:0 0 6px;color:#0f2748}
  .gsub{font-size:15px;color:#42506a;margin:0 0 12px;line-height:1.5}
  .gstep{display:flex;gap:11px;align-items:flex-start;margin:20px 0 10px}
  .gnum{flex:0 0 34px;height:34px;border-radius:50%;background:#1f6feb;color:#fff;font-weight:800;font-size:17px;display:flex;align-items:center;justify-content:center}
  .gstep.warn .gnum{background:#e0245e}
  .gtitle{font-size:17px;line-height:1.55;padding-top:4px;color:#141a24;font-weight:500}
  .gstep.warn .gtitle{color:#96003f;font-weight:700}
  .gbtn{display:inline-block;background:#1f6feb;color:#fff;text-decoration:none;font-weight:800;font-size:16px;padding:12px 18px;border-radius:10px;margin:2px 0 10px;box-shadow:0 3px 10px rgba(31,111,235,.28)}
  .gcopy{display:inline-block;background:#fff;color:#1f6feb;border:2px solid #1f6feb;font-weight:800;font-size:15px;padding:11px 16px;border-radius:10px;margin:2px 0 10px;cursor:pointer;text-align:left;line-height:1.4}
  .gimg{display:block;width:100%;max-width:100%;height:auto;border:2px solid #e3e7ee;border-radius:10px;margin:0}
  .gwarnbox{background:#fff3f2;border:1.5px solid #e0245e;border-radius:10px;padding:11px 13px;font-size:13.5px;line-height:1.55;color:#a01040;margin:16px 0 0}
  .gdone{background:#eafaf0;border:1.5px solid #1f9d55;border-radius:10px;padding:12px 14px;font-size:15px;color:#186c3c;margin:12px 0 0;font-weight:600}
  code{background:#eef1f6;padding:2px 6px;border-radius:5px;font-size:13px;font-weight:700}
</style></head>
<body><div class="wrap">
  <h1>\U0001F4E5 담기 기능 켜기</h1>
  <p class="lead">유튜브·틱톡·인스타·샤오홍슈·도우인에서 <b>마음에 든 영상을 클릭 한 번</b>으로 모음집에 담는 기능이에요. <b>아래 2단계</b>면 끝납니다.</p>

  <div id="browserWarn" class="warn" style="display:none">
    ⚠️ 이 기능은 <b>PC의 크롬(Chrome) 또는 엣지(Edge)</b>에서만 켤 수 있어요.<br>이 페이지 주소를 복사해 PC 크롬에서 열어주세요.
  </div>

  <!-- ★확장프로그램(권장, 2026-08-04) — 텀퍼몽키 방식은 아래 접이식으로 내렸다.
       이유: 텀퍼몽키는 크롬 토글 2개를 사람이 직접 켜야 하는데(파일로 못 켠다) 실제로
       고객이 거기서 막혔다(2026-07-21). 확장은 '사용자 스크립트 허용' 토글이 불필요하다. -->
  <div class="guide">
    <div class="ghead">\U0001F4E6 딱 2단계면 끝나요</div>
    <div class="gsub">설치 파일 하나만 받으면 됩니다. 텀퍼몽키 같은 다른 프로그램은 <b>필요 없어요</b>.</div>

    <div class="gstep"><div class="gnum">1</div><div class="gtitle">아래 버튼으로 파일을 받고 → <b>압축을 풀어주세요</b><br><span style="font-size:14.5px;color:#42506a">(받은 파일에 <b>마우스 오른쪽</b> → “압축 풀기” / “Extract All”. 풀면 폴더가 하나 생겨요)</span></div></div>
    <a class="gbtn" href="/grab_extension.zip" onclick="ssMark(1)">① 설치 파일 내려받기 ⬇</a>

    <div class="gstep"><div class="gnum">2</div><div class="gtitle">아래 <b>“주소 복사”</b> → 크롬 주소창에 <b>붙여넣기(Ctrl+V) + Enter</b> → 오른쪽 위 <b>“개발자 모드”</b> 켜기 → <b>압축 푼 폴더를 그 화면에 끌어다 놓기</b></div></div>
    <button class="gcopy" onclick="ssCopy('chrome://extensions', this)">\U0001F4CB chrome://extensions 주소 복사</button>
    <img class="gimg" src="__IMG3__" alt="개발자 모드 켜기">

    <div class="gwarnbox">\U0001F4A1 폴더를 <b>끌어다 놓는</b> 거예요. 파일(zip)이 아니라 <b>압축을 푼 폴더</b>를 놓아야 합니다.</div>
    <div class="gdone">✅ 다 되면 유튜브·인스타·틱톡 영상에서 <b>\U0001F4E5 담기</b> 버튼이 자동으로 떠요.</div>
  </div>

  <div id="steps">
    <div class="step" id="s3">
      <div class="num">✓</div>
      <div class="cbody">
        <div class="t">설치 확인</div>
        <div class="d">위 <b>사진 4단계</b>를 다 마치면 <b>여기가 저절로 초록불</b>로 바뀌어요. 아무것도 안 눌러도 돼요.</div>
      </div>
      <div class="check">○</div>
    </div>
  </div>

  <div id="doneBox" class="donebox" style="display:none">
    \U0001F389 <b>설치 완료!</b> 이제 유튜브·틱톡·샤오홍슈·도우인에서 영상을 열면 오른쪽 아래에 <b>\U0001F4E5 담기</b> 버튼이 자동으로 떠요. 그 버튼만 누르면 담깁니다.
    <div style="margin-top:12px"><a class="btn ghost" href="/collection">\U0001F3AC 담은 영상 보러가기</a></div>
  </div>

  <button id="recheck" class="recheck" style="display:none" onclick="location.reload()">설치했는데 안 바뀌나요? → 확인하기</button>

  <details class="alt">
    <summary>확장프로그램이 안 되나요? — 텀퍼몽키로 설치하기(예전 방식)</summary>
    __GUIDE_SECTION__
  </details>

  <details class="alt">
    <summary>설치가 어렵나요? — 설치 없이 쓰는 방법(북마클릿)</summary>
    <div class="altbox">
      <div class="hi">① 아래 파란 버튼을 <span style="color:#c0392b">누르지 말고</span> 마우스로 <u>북마크바로 드래그</u>해서 놓으세요</div>
      <div style="color:#a99;margin-bottom:10px">북마크바가 안 보이면 <b>Ctrl+Shift+B</b>. 드래그 = 버튼을 꾹 눌러 위쪽 북마크바까지 끌고 가 놓기.</div>
      <a id="bm" draggable="true" href="#" class="btn" style="cursor:grab">\U0001F4E5 담기</a>
      <div style="margin-top:12px;font-weight:700;color:#7a6528">② 영상을 <u>열고</u>(그리드 말고 영상 클릭해 들어간 뒤) 방금 만든 북마크를 누르면 끝.</div>
    </div>
  </details>

  <p class="foot">담긴 영상은 <a href="/collection">\U0001F3AC 모음집</a>에서 확인 · 실제 다운로드는 제작소에서 자동(무료). shoppingshorts에 <b>로그인된 상태</b>여야 담깁니다.</p>
</div>
<script>
(function(){
  var UA=navigator.userAgent||"";
  var inApp=/KAKAOTALK|Instagram|FBAN|FBAV|Line|NAVER|DaumApps/i.test(UA);
  var mobile=/Android|iPhone|iPad|iPod/i.test(UA);
  if(inApp||mobile){ var w=document.getElementById("browserWarn"); if(w) w.style.display=""; }
  function detected(){
    return document.documentElement.getAttribute("data-ss-grab-installed")==="1"
        || (function(){try{return localStorage.getItem("ss_grab_ok")==="1";}catch(e){return false;}})();
  }
  function markDone(){
    try{localStorage.setItem("ss_grab_ok","1");}catch(e){}
    ["s1","s2","s3"].forEach(function(id){var e=document.getElementById(id);if(!e)return;e.classList.add("ok");var c=e.querySelector(".check");if(c)c.textContent="✓";});
    var db=document.getElementById("doneBox"); if(db) db.style.display="";
    var st=document.getElementById("steps"); if(st) st.style.opacity=".6";
    var rc=document.getElementById("recheck"); if(rc) rc.style.display="none";
  }
  window.ssMark=function(n){ try{sessionStorage.setItem("ss_did"+n,"1"); if(n===2) sessionStorage.removeItem("ss_reloaded");}catch(e){} };
  // chrome:// 주소는 웹페이지 링크로 못 연다(크롬 정책) → '주소 복사'로 대신한다.
  window.ssCopy=function(t,btn){
    try{ navigator.clipboard.writeText(t); }catch(e){ try{var i=document.createElement("input");i.value=t;document.body.appendChild(i);i.select();document.execCommand("copy");i.remove();}catch(e2){} }
    if(btn){ var o=btn.getAttribute("data-label")||btn.textContent; btn.setAttribute("data-label",o); btn.textContent="✅ 복사됐어요! 주소창에 붙여넣기(Ctrl+V) 후 Enter"; setTimeout(function(){btn.textContent=o;},2800); }
  };
  window.addEventListener("message",function(ev){ if(ev&&ev.data&&ev.data.__ssGrabInstalled) markDone(); });
  // ★유저스크립트가 표식을 '언제' 남기든(느린 네트워크로 늦게 실행돼도) 즉시 감지 —
  //   유한 폴링만 쓰면 그 시간 지나 표식이 생길 때 영영 못 잡는다(2026-07-21 고객 실사고).
  try{
    new MutationObserver(function(){ if(detected()) markDone(); })
      .observe(document.documentElement,{attributes:true,attributeFilter:["data-ss-grab-installed"]});
  }catch(e){}
  var polls=0;
  var iv=setInterval(function(){
    if(detected()){ markDone(); clearInterval(iv); return; }
    polls++;
    // 12틱(약6초) 뒤 '확인하기'를 노출하되, 폴링은 멈추지 않는다(늦은 설치도 계속 감지).
    if(polls===12){ try{ if(sessionStorage.getItem("ss_did2")==="1"){ var rc=document.getElementById("recheck"); if(rc) rc.style.display=""; } }catch(e){} }
    if(polls>=300){ clearInterval(iv); }   // 약150초 상한(무한 타이머 방지)
  },500);
  if(detected()) markDone();
  document.addEventListener("visibilitychange",function(){
    try{
      if(document.visibilityState==="visible" && !detected()
         && sessionStorage.getItem("ss_did2")==="1"
         && sessionStorage.getItem("ss_reloaded")!=="1"){
        sessionStorage.setItem("ss_reloaded","1");
        location.reload();
      }
    }catch(e){}
  });
  try{ var bm=document.getElementById("bm"); if(bm) bm.setAttribute("href", atob("__BM64__")); }catch(e){}
})();
</script>
</body></html>"""


# 사진 설치 매뉴얼(실제 크롬 스크린샷 4장, 화살표는 캡처에 이미 포함). 이미지는 base64로
# 페이지에 직접 박는다 — /grab은 로그인 전에 열리므로 별도 이미지 URL은 인증에 막힐 수 있다.
# ★3·4단계(개발자 모드·사용자 스크립트 허용)를 크게 강조: 이걸 안 켜면 설치해도 안 돈다
# (2026-07-21 고객 실사고 — 텀퍼몽키·스크립트는 깔았는데 이 토글을 몰라서 📥가 안 떴음).
_GRAB_GUIDE_TEMPLATE = """<div class="guide">
    <div class="ghead">📸 사진 보고 그대로 따라 하기 — 이 4단계면 끝</div>
    <div class="gsub">아래 4장은 실제 크롬 화면이에요. 사진 속 빨간 화살표가 가리키는 곳을 누르면 됩니다.</div>

    <div class="gstep"><div class="gnum">1</div><div class="gtitle">‘텀퍼몽키’ 설치 — 아래 파란 버튼을 누르면 새 탭이 열려요 → 파란 <b>“Chrome에 추가”</b></div></div>
    <a class="gbtn" href="__TM_URL__" target="_blank" rel="noopener" onclick="ssMark(1)">① 텀퍼몽키 설치 페이지 열기 ↗</a>
    <img class="gimg" src="__IMG1__" alt="1단계 텀퍼몽키 추가">

    <div class="gstep"><div class="gnum">2</div><div class="gtitle">담기 스크립트 설치 — 아래 버튼을 누르면 설치창이 떠요 → <b>“설치”</b></div></div>
    <a class="gbtn" href="/grab.user.js" target="_blank" rel="noopener" onclick="ssMark(2)">② 담기 스크립트 설치 열기 ↗</a>
    <img class="gimg" src="__IMG2__" alt="2단계 스크립트 설치">

    <div class="gstep warn"><div class="gnum">3</div><div class="gtitle">⚠️ 아래 <b>“주소 복사”</b> 누르고 → 크롬 주소창에 <b>붙여넣기(Ctrl+V) + Enter</b> → 오른쪽 위 <b>“개발자 모드”</b> 스위치 켜기</div></div>
    <button class="gcopy" onclick="ssCopy('chrome://extensions', this)">📋 chrome://extensions 주소 복사</button>
    <img class="gimg" src="__IMG3__" alt="3단계 개발자 모드 켜기">

    <div class="gstep warn"><div class="gnum">4</div><div class="gtitle">⚠️ <b>가장 중요!</b> 아래 <b>“주소 복사”</b> 누르고 → 주소창에 <b>붙여넣기 + Enter</b> → 텀퍼몽키 설정에서 <b>“사용자 스크립트 허용”</b> 켜기 → 크롬을 껐다 켜기</div></div>
    <button class="gcopy" onclick="ssCopy('chrome://extensions/?id=dhdgffkkebhmkfjojejmpbldmpobfkfo', this)">📋 텀퍼몽키 설정 주소 복사</button>
    <img class="gimg" src="__IMG4__" alt="4단계 사용자 스크립트 허용">

    <div class="gwarnbox">❗ <b>3·4번을 안 켜면</b> 텀퍼몽키와 스크립트를 다 깔아도 <b>아무것도 안 됩니다.</b> 여기가 제일 많이 놓치는 부분이에요.</div>
    <div class="gdone">✅ 4단계를 마치면 유튜브·샤오홍슈 영상에 <b>📥 담기</b> 버튼이 자동으로 떠요.</div>
  </div>"""

_grab_guide_cache = None


def _grab_guide_html():
    """설치 매뉴얼 사진 4장을 base64 data URI로 박은 가이드 HTML(1회 계산 후 캐시)."""
    global _grab_guide_cache
    if _grab_guide_cache is not None:
        return _grab_guide_cache
    gdir = Path(__file__).parent / "static" / "guide"

    def _uri(name):
        try:
            return "data:image/png;base64," + base64.b64encode((gdir / name).read_bytes()).decode()
        except Exception:
            return ""

    _grab_guide_cache = (_GRAB_GUIDE_TEMPLATE
                         .replace("__IMG1__", _uri("step1_tampermonkey.png"))
                         .replace("__IMG2__", _uri("step2_script.png"))
                         .replace("__IMG3__", _uri("step3_devmode.png"))
                         .replace("__IMG4__", _uri("step4_userscripts.png")))
    return _grab_guide_cache


@app.get("/grab", include_in_schema=False)
def grab_setup(request: Request):
    """원클릭 담기 설치 안내(공개). 사진 4단계 매뉴얼 + 자가감지 '신호등'(설치 끝나면 유저스크립트
    비컨을 감지해 자동으로 '완료'로 바꾼다). 유저스크립트가 안 맞는 환경엔 북마클릿 폴백을 제공."""
    base = (PUBLIC_BASE_URL or "").rstrip("/")
    bm64 = base64.b64encode(_GRAB_BOOKMARKLET.replace("__BASE__", base).encode()).decode()
    # Tampermonkey 크롬 웹스토어 상세(딥링크=검색 안 시킴). 엣지도 크롬스토어에서 설치 가능.
    tm_url = "https://chromewebstore.google.com/detail/tampermonkey/dhdgffkkebhmkfjojejmpbldmpobfkfo"
    # ★__GUIDE_SECTION__을 먼저 끼운 뒤 __IMG3__를 치환한다 — 확장프로그램 안내(본문)와
    # 텀퍼몽키 안내(접이식) 둘 다 같은 '개발자 모드' 사진을 쓰기 때문이다. 순서를 바꾸면
    # 본문 쪽 __IMG3__가 그대로 남아 깨진 이미지가 뜬다.
    gdir = Path(__file__).parent / "static" / "guide"
    try:
        img3 = "data:image/png;base64," + base64.b64encode(
            (gdir / "step3_devmode.png").read_bytes()).decode()
    except Exception:
        img3 = ""
    html = (_GRAB_SETUP_HTML
            .replace("__GUIDE_SECTION__", _grab_guide_html())
            .replace("__IMG3__", img3)
            .replace("__TM_URL__", tm_url).replace("__BM64__", bm64))
    return HTMLResponse(html)


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
    # ★스타일 강제 경로(2026-08-15) — body.style_ids가 오면 스타일마다 1안씩 만들고
    #   script_gate로 구조를 대조한다. 안 오면 기존 경로 그대로(회귀 0).
    #   기본 off인 이유: 검증 안 된 플래그를 라이브에 켜서 사고 난 적이 있다
    #   (memory feedback_no_unverified_flag_in_live).
    style_ids = [int(x) for x in (body.get("style_ids") or []) if str(x).isdigit()]
    if style_ids:
        _st = Store(DB_PATH)
        _by_id = {s["id"]: s for s in _st.list_style_spines()}
        picked = [_by_id[i] for i in style_ids if i in _by_id]
        if not picked:
            return JSONResponse(status_code=422,
                                content={"ok": False, "error": "고른 스타일을 찾을 수 없음(승인·구조 필요)"})
        styled = script_generate.generate_by_styles(
            sources, picked, target_seconds=body.get("target_seconds") or 20)
        if not styled:
            return JSONResponse(status_code=502,
                                content={"ok": False, "error": "생성 실패(키 소진 또는 응답 오류)"})
        cid = _cid(request)
        for dr in styled:
            did = uuid.uuid4().hex[:12]
            _st.save_draft(did, cid, None, None, dr.get("hook", ""), dr.get("script", ""),
                           None, "style")
            dr["draft_id"] = did
            _st.record_script_usage(hook=dr.get("hook", ""), spine_id=dr.get("style_id"))
        return {"ok": True, "drafts": styled, "mode": "style"}
    drafts = script_generate.generate_mix(
        sources, target_seconds=body.get("target_seconds") or 20, n=body.get("n") or 3)
    if not drafts:
        return JSONResponse(status_code=502,
                            content={"ok": False, "error": "생성 실패(키 소진 또는 응답 오류)"})
    store = Store(DB_PATH)
    cid = _cid(request)
    for dr in drafts:
        did = uuid.uuid4().hex[:12]
        store.save_draft(did, cid, None, None, dr.get("hook", ""), dr.get("script", ""), None, "mix")
        dr["draft_id"] = did
    return {"ok": True, "drafts": drafts}


@app.post("/api/produce/picks/toggle")
def api_produce_picks_toggle(request: Request, body: dict):
    """도서관 대본을 영상제작 목록에 담기/빼기 토글. body: {shortcode}."""
    sc = (body.get("shortcode") or "").strip()
    if not sc:
        return JSONResponse(status_code=422, content={"ok": False, "error": "shortcode 필요"})
    picked = Store(DB_PATH).produce_pick_toggle(sc, customer_id=_cid(request))
    return {"ok": True, "picked": picked}


@app.post("/api/produce/picks/remove")
def api_produce_picks_remove(request: Request, body: dict):
    """영상제작 목록에서 빼기(멱등). body: {shortcode}.
    ★왜 toggle로 안 하나: 이미 빠져 있는 걸 toggle하면 오히려 **다시 담긴다**.
      1단계 ✕(dropFootage)는 '무조건 빼기'라 멱등이어야 한다 — 자동적재(2026-07-26)
      이후로는 담김이 서버에도 쌓이므로, 클라에서만 빼면 AI PICK이 뺀 영상을 계속 쓴다."""
    sc = (body.get("shortcode") or "").strip()
    if not sc:
        return JSONResponse(status_code=422, content={"ok": False, "error": "shortcode 필요"})
    Store(DB_PATH).produce_pick_remove(sc, customer_id=_cid(request))
    return {"ok": True}


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


@app.post("/api/produce/works/{work_id}/rename")
def api_produce_works_rename(request: Request, work_id: str, body: dict):
    # 작업 이름 바꾸기(2026-08-17) — 목록이 '(제목 없음)' 투성이라 구분이 안 됐다.
    # ★제목 계산은 store._work_title 한 곳에만 있다(0순위-B). 여기선 이름을 넘길 뿐이다.
    #   빈 문자열이면 직접 지은 이름을 지워 자동 제목(대본 앞 20자)으로 되돌린다 —
    #   그래서 name이 없다고 422로 막지 않는다(그게 '해제' 경로다).
    name = body.get("name")
    if name is not None and not isinstance(name, str):
        # ★타입을 확인하고 부른다 — dict가 와서 .strip()이 500을 내던 사고가 이 앱에서
        #   이미 세 번 났다(handoff/장면라벨.md). 모르는 모양이면 받지 않는다.
        return JSONResponse(status_code=422, content={"ok": False, "error": "name은 문자열"})
    title = Store(DB_PATH).rename_produce_work(work_id, name or "", customer_id=_cid(request))
    if title is None:
        return JSONResponse(status_code=404, content={"ok": False, "error": "작업 없음"})
    return {"ok": True, "title": title}


@app.post("/api/produce/works/{work_id}/delete")
def api_produce_works_delete(request: Request, work_id: str):
    if not Store(DB_PATH).delete_produce_work(work_id, customer_id=_cid(request)):
        return JSONResponse(status_code=404, content={"ok": False, "error": "작업 없음"})
    return {"ok": True}


# ── AI PICK 사전분석(2026-07-23, 숏템메이커 리뉴얼 Task3) ──────────────
# 지금 구조에서 "영상제작에 담긴 소스"는 work 단위가 아니라 **고객 단위 버킷**
# (produce_script_picks, /api/produce/picks와 같은 출처)이다. work_id는 이 시점엔
# 아직 없을 수도 있고(1단계 첫 진입, WORK_ID=null), 있어도 그 work의 상태에 저장된
# ⭐메인 지정(있다면)을 읽는 용도로만 쓴다 — 소스 목록 자체는 항상 picks 버킷.
def _extract_as_source_item(store, shortcode):
    """도서관(script_wiki)에 없는 '넘어온 영상'을 AI PICK 후보로 쓰기 위한 얇은 item.
    script_extracts(전역 추출 캐시)에 대본이 있으면 그걸 본문으로, 이름·썸네일·댓글수는
    reel_history 최신 메타에서 채운다. 추출조차 없으면 None(=진짜 후보 불가). _wiki_row와
    같은 키 형태를 돌려줘 _load_work_sources의 소스 빌더가 그대로 처리한다(2026-07-27)."""
    ex = store.get_extract(shortcode)
    if not ex:
        return None
    reel = store.get_reel_meta(shortcode) or {}
    return {
        "shortcode": shortcode,
        "name": reel.get("name") or "",
        "category": ex.get("category") or reel.get("category") or "",
        "source_url": reel.get("url") or "",
        "full_text": ex.get("full_text", ""),
        "segments": ex.get("segments") or [],
        "structure": ex.get("structure") or {},
        "followers": None,
        "comments": reel.get("comments"),
        "density": None,
        "saved_at": None,
        "thumbnail": reel.get("thumb") or "",
    }


def _load_work_sources(work_id, cid):
    """AI PICK용 소스 목록. '영상제작에 담긴(handoff)' 영상 전부 — 도서관에 있으면 그 행을,
    backbone/aipick이 기대하는 얇은 필드로 변환한다.
    ⚠️ views(조회수)는 이 시스템 어디에도 저장되지 않는다(script_wiki 스키마 확인,
    2026-07-23) — 거짓 수치 대신 항상 None(aipick.build_aipick이 우아하게 폴백).
    seconds는 whisper 세그먼트(start/end)에서 실측(마지막 세그먼트 end) — 저장 안 됐으면 None.
    structure는 도서관 저장 시(api_produce_save_to_wiki) 이미 1회 analyze_structure가
    돌아 캐시돼 있으므로 그대로 실어 aipick.py가 재분석(Gemini 재호출) 없이 재사용하게 한다."""
    store = Store(DB_PATH)
    # ★후보는 '이 작업(work)에 담긴 영상'으로 한정한다(2026-07-26 사고). 예전엔 계정 전체
    #   produce_pick_shortcodes(cid)를 후보로 써서, 이 work과 무관한 옛 도서관픽(참여율 높은
    #   다른 영상)이 AI PICK 1위로 떴다("담은 2개와 무관한 홈테리어픽"). work.state['handoff']가
    #   이 작업의 재료 목록이므로 그 shortcode로 좁힌다. work_id 없거나 handoff가 비면(옛 경로)
    #   계정 전체 픽으로 폴백(회귀0).
    codes = None
    entry_by_code = {}       # shortcode → handoff 항목(추출 전에도 이름·썸네일·URL을 아는 유일한 출처)
    if work_id:
        work = store.get_produce_work(work_id, customer_id=cid)
        if work and isinstance(work.get("state"), dict):
            handoff = work["state"].get("handoff") or []
            # 순서 보존(핸드오프 순서 = 재료 바구니 순서 → pick 카드의 이름·썸네일 정합).
            codes = [e.get("shortcode") for e in handoff
                     if isinstance(e, dict) and e.get("shortcode")]
            entry_by_code = {e["shortcode"]: e for e in handoff
                             if isinstance(e, dict) and e.get("shortcode")}
    if not codes:
        codes = list(store.produce_pick_shortcodes(customer_id=cid))
    # ★후보 = '넘어온 영상(handoff)' 전부. 예전엔 wiki_list(도서관) ∩ codes로 좁혀,
    #   도서관에 저장 안 된 영상은 후보에서 통째로 탈락했다(2026-07-27 실측 사고:
    #   넘어온 3개 중 도서관에 없던 '홈스텐다드'가 빠지고, 도서관 즐겨찾기인 금손여신·
    #   살림홈만 남아 "도서관 것만 AI PICK"). 이제 도서관에 없으면 script_extracts(전역
    #   추출 캐시)+reel_history에서 끌어와, 저장 여부와 무관하게 넘어온 영상이 곧 후보다.
    #   ★2026-08-14(사장님 "왜 메인이 중국어냐"): 추출이 **아직 안 끝난** 영상을 조용히 빼던
    #   것을 멈춘다. 실측(work 73fc36693ed5): 인스타 Db9O4pqza74의 추출은 04:05:00에 끝났는데
    #   사장님이 화면을 본 건 04:02 — 그 3분 동안 한국어 소스가 목록에서 통째로 사라져,
    #   남은 샤오홍슈 2개로 메인이 정해졌다(영구 결손이 아니라 경합). 이제 pending으로 남겨
    #   "분석 중"임을 화면이 말하게 하고, 하류(build_aipick)가 메인 확정을 보류한다.
    items = []
    pending_codes = []
    seen = set()
    for sc in codes:
        if sc in seen:
            continue
        seen.add(sc)
        w = store.get_wiki_item(sc, customer_id=cid) or _extract_as_source_item(store, sc)
        if w:
            items.append(w)
        else:
            pending_codes.append(sc)
    # 댓글수는 '지금' 값(reel_history 최신 크롤)을 우선 쓴다 — 도서관 스냅샷(script_wiki.comments)은
    # 저장 순간에 박제돼, 저장 후 댓글이 늘면 AI PICK만 옛 숫자를 보여준다(재료카드와 불일치,
    # 참여밀도도 옛 기준). 최신값이 없으면(30일 지나 정리 등) 도서관 스냅샷으로 폴백(2026-07-26).
    fresh = store.latest_comments([w["shortcode"] for w in items])
    sources = []
    for w in items:
        segs = w.get("segments") or []
        seconds = round(max((s.get("end", 0) for s in segs), default=0), 1) if segs else None
        sources.append({
            "video_id": w["shortcode"],
            "text": w.get("full_text", ""),
            "followers": w.get("followers") or None,
            "comments": fresh.get(w["shortcode"], w.get("comments")) or None,
            "seconds": seconds,
            "views": None,
            "structure": w.get("structure") or None,
            "source_url": w.get("source_url", ""),
            # ★이름·썸네일·카테고리를 서버가 직접 실어 보낸다(2026-07-26 사고). 안 실으면 pick_meta가
            #   비어, 프론트가 HANDOFF[pick_index]로 이름·썸네일을 추측한다 — 바구니 순서가 서버
            #   sources 순서와 어긋나면 '살림홈 숫자에 엉뚱한 영상 썸네일'처럼 카드가 자기모순이 된다.
            #   pick의 숫자와 썸네일이 항상 같은 영상에서 나오게 하려면 여기서 실어야 한다.
            #   ★handoff 항목으로 폴백(2026-08-14). 샤오홍슈 담기(grab_*)는 reel_history에
            #   행이 없어(실측) 이름·썸네일이 빈 채로 내려갔고, 그래서 프론트가 HANDOFF
            #   인덱스로 '추측'하는 길이 열려 있었다. 담을 때 이미 아는 값이니 여기서 채운다.
            "name": w.get("name") or (entry_by_code.get(w["shortcode"]) or {}).get("name") or "",
            "thumbnail": (w.get("thumbnail")
                          or (entry_by_code.get(w["shortcode"]) or {}).get("thumbnail") or ""),
            "category": w.get("category") or "",
        })
    # 추출 대기 중인 영상 — 목록에서 빼지 않고 pending으로 실어 보낸다(화면이 "분석 중"을 말하게).
    for sc in pending_codes:
        e = entry_by_code.get(sc) or {}
        sources.append({
            "video_id": sc, "text": "", "segments": [], "followers": None, "comments": None,
            "seconds": None, "views": None, "structure": None,
            "source_url": e.get("url") or "", "name": e.get("name") or "",
            "thumbnail": e.get("thumbnail") or "", "category": "",
            "pending": True,
        })
    return sources


def _build_source_meta(sources):
    """backbone.score_backbones/pick_backbone이 기대하는 meta = {video_id: {platform,
    comments, avg_comments}}. avg_comments(바구니 평균)는 폐기된 comments_x_avg 타일의
    기준값이었다(2026-07-26 진짜값 전환으로 타일 제거) — score_backbones는 comments만 읽으므로
    지금은 참고용으로만 남겨둔다(제거해도 무방)."""
    counted = [s["comments"] for s in sources if s.get("comments") is not None]
    avg = round(sum(counted) / len(counted), 1) if counted else None
    meta = {}
    for s in sources:
        meta[s["video_id"]] = {
            "platform": backbone.platform_of(s.get("source_url", "")),
            "comments": s.get("comments"),
            "avg_comments": avg,
        }
    return meta


def _forced_backbone(work_id, cid):
    """work.state에 사장님이 UI에서 지정한 ⭐메인(있다면)을 읽는다. work_id 없음/남의
    work/필드 없음이면 None(=자동 선정 폴백, pick_backbone의 기본 동작).
    프론트(Task4~)가 아직 이 필드를 안 쓰므로 이름은 mix_pipeline의 backbone_main
    관례를 따르되 shortcode 문자열을 직접 담게 열어둔다(인덱스는 여기선 의미 없음
    — picks 소스는 url 인덱스가 아니라 shortcode로 식별된다)."""
    if not work_id:
        return None
    w = Store(DB_PATH).get_produce_work(work_id, customer_id=cid)
    if not w:
        return None
    state = w.get("state")
    if not isinstance(state, dict):
        return None
    return state.get("backbone_main") or None


@app.get("/api/produce/source_brief")
def api_produce_source_brief(request: Request, shortcode: str):
    """1단계 소스 분석 카드용 — **저장된 추출 결과만** 읽어 준다(2026-08-16).

    ★비용 0원을 구조로 보장한다: 여기서는 Gemini를 절대 부르지 않는다. 없으면 없다고
    답할 뿐(`ok:false, pending:true`)이고, 실제 추출은 기존 자동적재 경로(api_produce_autoload)가
    맡는다. 1단계 화면을 열기만 해도 크레딧이 타는 일을 원천 차단하려는 것 —
    /api/extract_script는 캐시미스에 과금하므로 그걸 그대로 쓰면 안 된다.

    반환: {ok, brief:{product,role,core,summary}, segments:[{start,end,label,scene_desc,is_key}]}
    옛 추출본엔 source_brief·label이 없다 → brief={} / label="" 로 나가고 화면이 알아서 견딘다.
    """
    store = Store(DB_PATH)
    data = None
    for code in (shortcode, _media_code(shortcode)):
        if not code:
            continue
        data = store.get_script(code)
        if data:
            break
    if not data:
        # ★왜 아직 없는지까지 알려준다(2026-08-17 사장님 "영상분석은?").
        #   추출이 없는 데는 두 가지가 있는데 화면은 둘을 구별할 수 없었다:
        #     · 아직 도는 중        → 기다리면 된다
        #     · 받기부터 실패해 포기 → 기다려도 영원히 안 온다
        #   구별을 못 하니 실패한 영상도 계속 "분석 대기"로 보였다(실측: 도우인 4건이
        #   'Fresh cookies needed'로 3회 실패·래치됐는데 화면은 아무 말도 안 했다).
        st = Store(DB_PATH).autoload_status([shortcode, _media_code(shortcode)])
        info = st.get(shortcode) or st.get(_media_code(shortcode)) or {}
        err = info.get("last_error") or ""
        # ★재시도해도 소용없는 실패는 **1회만에** 알린다(2026-08-17 사장님 "대본 만들기를
        #   눌러야 분석이 된다고?"). 3회를 채워야 알리게 해뒀더니, 이미 로그인벽에 막힌
        #   영상이 1~2회 동안 '분석 대기'로 보여 사장님이 오지 않을 결과를 기다렸다.
        #   로그인·비공개처럼 원인이 분명한 것은 몇 번을 더 해도 결과가 같다.
        att = info.get("attempts", 0)
        # ★시도를 다 썼는데 **결과도 오류도 없으면 도중에 끊긴 것**이다(2026-08-16 실측).
        #   긴 영상이 다운로드 도중 시간 초과로 죽으면 여기 걸린다 — 그때 화면이 계속
        #   "분석 중"이라고 하면 사장님은 오지 않을 결과를 기다린다(실제로 그랬다).
        stalled = (not err) and att >= _AUTOLOAD_MAX_ATTEMPTS
        return {"ok": False, "pending": True,
                "attempts": att,
                "gave_up": stalled or (bool(err) and (att >= _AUTOLOAD_MAX_ATTEMPTS
                                                      or _is_hopeless_error(err))),
                "reason": (_autoload_reason_ko(err) if err else
                           ("분석이 도중에 끊겼어요 — 긴 영상은 더 오래 걸립니다"
                            if stalled else ""))}
    segs = []
    for s in (data.get("segments") or []):
        if not isinstance(s, dict):   # 깨진 세그로 카드 전체가 500 나지 않게
            continue
        segs.append({
            "start": s.get("start"), "end": s.get("end"),
            "label": (s.get("label") or ""),
            "scene_desc": s.get("scene_desc") or "",
            "is_key": bool(s.get("is_key")),
            # 카드가 "이 영상이 어떤 재료인지"를 스스로 세어 보여주려고 싣는다(2026-08-17).
            # shot_role = 화면 구성(완성품·과정·전후), text 길이 = 말이 있는 영상인지.
            # 무자막·외국어 소스도 화면만 보고 태깅되므로 '말 없음'은 결함이 아니라 성질이다.
            "shot_role": s.get("shot_role") or "기타",
            "chars": len((s.get("text") or "").strip()),
        })
    return {"ok": True, "brief": data.get("source_brief") or {}, "segments": segs}


@app.get("/api/produce/aipick")
def api_produce_aipick(request: Request, work_id: str = "", forced: str = ""):
    """1단계 "AI가 미리 픽 추천" 조회 — 지금 담긴 소스를 pick_backbone/score_backbones/
    analyze_structure로 사전분석해 프론트 계약 하나로 묶어 반환(build_aipick)."""
    cid = _cid(request)
    sources = _load_work_sources(work_id, cid)
    meta = _build_source_meta(sources)
    return build_aipick(sources, meta, forced=(forced or _forced_backbone(work_id, cid)) or None)


# ── 담긴 영상 자동 대본적재(2026-07-26) ─────────────────────────────────
# 왜 필요한가: AI PICK 소스는 script_wiki(도서관) ∩ produce_script_picks(담김)이고
# 둘 다 customer_id로 스코핑된다(_load_work_sources). 관리자는 도서관이 차 있어 카드가
# 뜨지만 신규 고객은 도서관이 0건 → 교집합 공집합 → pick_id=None → 폴백 화면.
# 도서관/즐겨찾기는 계정별 독립이 정책이므로(공유 안 함) **그 고객 도서관에 자동으로
# 적재**해서 관리자와 같은 화면을 만든다.
#
# ★사고 재발 방지 4종(2026-07-26 무한루프·크레딧 소모 사고, revert cb8c0fa1d):
#   ① 래치는 DB에(produce_autoload) — 클라 메모리·HANDOFF 객체에 두면 배열 재대입으로 증발
#   ② 추출 전에 선(先)래치 — 타임아웃·재시작에도 시도 흔적이 남는다
#   ③ full_text가 비면 저장하지 않고 실패로 확정 — segments만 있는 저장은 "대본 없음"이
#      영구 캐시돼 클라가 계속 미추출로 오인한다(인스타 릴스 실패의 정체)
#   ④ 호출당 건수 상한 + 시도 횟수 상한 — 최악의 경우에도 소모가 유한하다
_AUTOLOAD_MAX_PER_CALL = 4      # 한 번 호출로 새로 태울 수 있는 영상 수
# 1 → 3 (2026-08-04): prewarm과 같은 완화 — 인스타 일시 실패 1번으로 영구 스킵되면
# 재담기가 조용히 죽는다. 3회면 폭주 차단은 유지하면서 일시 실패를 흡수한다.
def _is_grabbable_media(u):
    """담기가 보낸 '영상 파일 직접 주소'로 받아들일지. https + 알려진 영상 CDN만.

    ★왜 좁게 받나: 이 값은 그대로 서버가 내려받는 주소가 된다. 임의 주소를 허용하면
    내부망을 찌르는 통로가 된다(_ssrf_guard와 같은 취지). blob:은 브라우저 안에서만
    유효하므로 애초에 걸러야 한다 — 서버가 받을 수 없다."""
    u = (u or "").strip()
    if not u.lower().startswith("https://"):
        return False
    # ★확장자(.mp4)로 판단하지 않는다 — 그러면 아무 도메인이나 통과한다(evil.example.com/a.mp4).
    #   담기가 보낼 수 있는 것은 우리가 아는 소스 CDN뿐이다. 호스트로 좁힌다.
    try:
        host = urllib.parse.urlparse(u).hostname or ""
    except ValueError:
        return False
    host = host.lower()
    return any(host == h or host.endswith("." + h) for h in _GRAB_MEDIA_HOSTS)


# 담기가 보낸 영상 주소로 받아들일 CDN(도우인=zjcdn/douyinvod, 샤오홍슈=xhscdn).
# ★여기 없는 호스트는 조용히 버린다 — 그러면 종전대로 페이지 URL로 간다(회귀 없음).
_GRAB_MEDIA_HOSTS = ("zjcdn.com", "douyinvod.com", "xhscdn.com", "douyinpic.com")


_AUTOLOAD_MAX_ATTEMPTS = 3      # shortcode당 자동추출 총 시도 횟수(넘으면 영구 스킵)


def _is_hopeless_error(err):
    """더 시도해도 결과가 같은 실패인가(로그인벽·비공개·삭제).
    네트워크 흔들림 같은 일시적 실패와 갈라, 이런 것만 즉시 사장님께 알린다."""
    low = (err or "").lower()
    return any(k in low for k in ("cookie", "login", "sign in", "private",
                                  "unavailable", "removed", "deleted"))


def _autoload_reason_ko(err):
    """자동적재 실패 원문 → 사장님이 읽을 한 줄. 실패가 아니면 "".

    ★원문을 그대로 화면에 던지지 않는다 — 'Fresh cookies (not necessarily logged in)
    are needed'를 보고 무엇을 해야 할지 알 수 있는 사람은 없다. 대신 **무엇이
    막혔는지**를 말한다. 모르는 오류는 숨기지 말고 앞부분을 그대로 보여준다
    (조용히 삼키면 또 '왜 안 되지'가 된다)."""
    e = (err or "").strip()
    if not e:
        return ""
    low = e.lower()
    if "cookie" in low or "login" in low or "sign in" in low:
        return "이 사이트가 로그인을 요구해 영상을 받지 못했습니다"
    if "private" in low or "unavailable" in low or "removed" in low:
        return "원본이 비공개이거나 삭제돼 받지 못했습니다"
    if "yt-dlp" in low or "download" in low or "다운로드" in e:
        return "영상을 내려받지 못했습니다"
    if "timeout" in low or "timed out" in low:
        return "시간이 초과돼 받지 못했습니다"
    return "영상 분석에 실패했습니다 — " + (e[:60] + ("…" if len(e) > 60 else ""))
# 동시에 추출할 영상 수(2026-07-30). 대기의 정체가 제미니 응답이라 동시에 올리면 총 시간이
# '가장 느린 1개'로 수렴한다. 다만 무제한으로 올리면 제미니 429가 몰려 오히려 느려지고 키가
# 소진되므로 3으로 묶는다(_AUTOLOAD_MAX_PER_CALL=4와는 다른 축 — 그건 '총 몇 개').
_AUTOLOAD_MAX_WORKERS = 3


@app.post("/api/produce/autoload")
def api_produce_autoload(request: Request, body: dict):
    """담긴 영상 중 이 고객 도서관에 없는 것을 자동으로 대본추출→도서관 적재→담기까지 한다.
    body: {items:[{url, shortcode?, video_url?, name?, thumbnail?, caption?, category?,
                   followers?, comments?}]}
    반환: {ok, results:[{shortcode, status}], added} — status: already|added|skipped_latched|
          failed_download|failed_empty|failed_limit|failed_points(포인트 부족).
    ⚠️ 이 엔드포인트는 **자기 자신이나 프론트 재귀를 유발하지 않는다**. 프론트는 페이지
       로드당 1회만 부르고, 응답 뒤 aipick을 딱 한 번 다시 조회한다."""
    cid = _cid(request)
    items = [i for i in (body.get("items") or []) if (i or {}).get("url")]
    if not items:
        return {"ok": True, "results": [], "added": 0}
    store = Store(DB_PATH)
    have = {w["shortcode"] for w in store.wiki_list(customer_id=cid)}
    results, added, burned = [], 0, 0

    codes = [(i.get("shortcode") or "").strip()
             or hashlib.sha1((i.get("url") or "").strip().encode()).hexdigest()[:12] for i in items]
    tried = store.autoload_attempts(codes)

    # ★3단계 구조(2026-07-30 동시화). 예전엔 영상들을 순차로 돌려 제미니 대기가 그대로
    #   더해졌다(3개면 3배). 대기의 정체는 우리 CPU가 아니라 **제미니 업로드·처리 응답**
    #   (script_extract가 영상을 통째로 올리고 _wait_until_active로 폴링)이라, 동시에 올리면
    #   대기가 겹쳐 총 시간이 '가장 느린 1개'로 수렴한다. 2단계 믹스는 이미 이렇게 병렬이다
    #   (mix_pipeline의 ThreadPoolExecutor) — 1단계만 순차로 남아 있었다.
    #   A) 게이트·크레딧(순차) → B) 다운로드·추출·구조분석(병렬) → C) DB 쓰기(순차)
    #   왜 이렇게 가르나: 게이트(래치·호출당 상한·크레딧)는 순서가 있어야 상한이 정확하고,
    #   SQLite 쓰기를 여러 스레드에서 하면 락 경합이 난다. 오래 걸리는 네트워크 대기만 겹친다.
    slots = [None] * len(items)      # 결과를 원래 순서대로 채운다(프론트가 순서를 신뢰한다)
    todo = []                        # 병렬로 돌릴 항목만

    # ── A) 게이트 (순차) ─────────────────────────────────────────
    for i, (item, code) in enumerate(zip(items, codes)):
        url = (item.get("url") or "").strip()
        # ① 이미 도서관에 있으면 추출 없이 '담기'만 보장한다(교집합 통과에 둘 다 필요).
        if code in have:
            store.produce_pick_add(code, customer_id=cid)
            slots[i] = {"shortcode": code, "status": "already"}
            continue
        if _ssrf_guard(*[u for u in (url, item.get("video_url")) if u]):
            slots[i] = {"shortcode": code, "status": "failed_download"}
            continue

        # ②-a 캐시를 **래치보다 먼저** 본다(2026-08-04 실사고 DQohOUqgdRt): 수동 대본뽑기로
        # 추출이 이미 있는데도 래치가 앞에 있어 skipped_latched → 도서관 적재가 영영 안 돼
        # AI PICK(대본 3안 버튼)이 안 떴다. 캐시 히트는 제미니 비용 0이라 래치(비용 폭주
        # 차단 장치)가 막을 이유가 없다.
        # ★캐시 유효 판정은 has_usable_result 한 곳으로(0순위-B). full_text만 보면
        #   무자막 영상은 저장돼 있어도 캐시미스가 돼 매번 제미니를 다시 태우고, 시도
        #   횟수만 쌓여 결국 영구 래치된다(2026-08-16 저장 기준을 '말 또는 화면'으로
        #   바꾼 것과 짝인데, 읽는 쪽 두 곳이 옛 기준으로 남아 있었다).
        cached = store.get_extract(code)
        cache_ok = has_usable_result(cached)
        if not cache_ok:
            # ②-b DB 래치 — 상한까지 실패한 영상은 다시 태우지 않는다(무한루프 차단의 핵심)
            if tried.get(code, 0) >= _AUTOLOAD_MAX_ATTEMPTS:
                slots[i] = {"shortcode": code, "status": "skipped_latched"}
                continue
        if cache_ok:
            # 캐시 히트 — 제미니 비용도 상한도 안 쓴다(담기 예열이 채워둔 경우가 이것).
            todo.append({"i": i, "item": item, "code": code, "url": url, "charged": False,
                         "script": {"full_text": cached.get("full_text", ""),
                                    "segments": cached.get("segments") or []},
                         "category": item.get("category") or cached.get("category") or None,
                         "structure": cached.get("structure")})
            continue
        # ③ 호출당 상한 — 캐시미스(=실제 제미니 비용)에만 센다. 남은 건 다음 진입에서.
        if burned >= _AUTOLOAD_MAX_PER_CALL:
            slots[i] = {"shortcode": code, "status": "skipped_cap"}
            continue
        # 캐시미스 → 실제 Gemini 비용. 크레딧 확인 후 태운다(실패 시 C단계에서 환불).
        if _global_over_cap("script") or not check_and_count(cid, "script"):
            slots[i] = {"shortcode": code, "status": "failed_limit"}
            continue
        # ★여기는 라우트가 아니라 **항목 루프 안**이다 — 402를 그대로 return하면 남은
        #   영상까지 통째로 죽는다. 포인트가 모자란 항목만 접고 나머지는 계속 돌린다
        #   (위 failed_limit·skipped_cap과 같은 모양).
        if _charge_or_402(cid, pricing.OP_SCRIPT, keyroute.SVC_GEMINI):
            slots[i] = {"shortcode": code, "status": "failed_points"}
            continue
        global_incr_and_alert("script")
        burned += 1
        store.autoload_mark_attempt(code)     # ★추출 전에 래치
        todo.append({"i": i, "item": item, "code": code, "url": url, "charged": True,
                     "script": None, "category": None, "structure": None})

    # ── B) 네트워크 대기 구간 (병렬) ──────────────────────────────
    # ⚠️ 이 함수 안에서 DB에 쓰지 않는다 — 결과만 dict에 담아 C단계가 쓴다.
    def _fetch(e):
        item, code = e["item"], e["code"]
        work_dir = _FIND_TMP_DIR / hashlib.sha1(code.encode()).hexdigest()[:16]
        e["video_path"] = None
        if e["script"] is None:                      # 캐시미스 → 다운로드+추출
            try:
                e["video_path"], dl_caption = download_any(
                    item.get("video_url") or e["url"], str(work_dir))
            except DouyinBusy as ex:
                # ★자리가 없을 뿐 실패가 아니다(2026-08-16 사장님 "잠시후 다시 시도해달라고
                #   표시하고 그 영상 다시 받게"). 실패로 적으면 시도 횟수를 까먹고 결국
                #   영영 못 받는다 — 래치를 되돌려 다음에 온전히 다시 시도하게 한다.
                e["status"], e["error"] = "busy", str(ex)
                e["rollback_latch"] = True
                return e
            except Exception as ex:  # noqa: BLE001 — 만료·비공개·차단
                e["status"], e["error"] = "failed_download", str(ex)
                return e
            try:
                result = extract_auto(e["video_path"], code,
                                      caption=(item.get("caption") or dl_caption or ""))
            except KeyPoolExhausted as ex:
                # 키 풀 잠김 = 서버 사정. 영상 탓이 아니므로 래치를 되돌려야 한다
                # (2026-08-07). 여기선 DB에 못 쓰므로(병렬 구간) 표시만 남기고
                # C단계에서 rollback 한다.
                e["status"], e["error"] = "deferred_nokey", str(ex)
                e["rollback_latch"] = True
                return e
            except Exception as ex:  # noqa: BLE001
                e["status"], e["error"] = "failed_download", str(ex)
                return e
            # ★재료가 하나도 안 나왔을 때만 버린다(2026-08-16 기준 교체).
            #   예전엔 full_text(말)만 봐서 **무음 영상이 통째로 버려졌다** — 도우인
            #   제품 영상이 여기 걸렸다. 화면 태깅만 나와도 쓸 수 있는 재료다.
            #   빈 대본이 캐시로 굳는 것은 has_usable_result가 그대로 막는다.
            if not has_usable_result(result):
                e["status"] = "failed_empty"
                e["error"] = "쓸 만한 재료가 안 나왔어요(화면·말 모두 비어 있음)"
                # ★분석 결과는 남긴다(2026-08-17, 쿠팡선수집 세션) — 저장(캐시)은 안 한다.
                #   쿠팡 선수집이 product·product_benefits를 쓴다.
                #   ⚠️여기까지 오는 경우가 줄었다(2026-08-16, 장면라벨 세션): 판정이
                #   full_text(말)에서 has_usable_result(말 **또는** 화면)로 바뀌어,
                #   화면 태깅이 나온 무자막 영상은 이제 위에서 정상 저장된다.
                #   이 분기는 말도 화면도 못 건진 진짜 빈 결과일 때만 탄다.
                e["result"] = result
                # 카테고리도 채워 둔다 — 선수집이 홈템·기타만 거르는 데 쓴다.
                e["category"] = item.get("category") or categorize(
                    item.get("name") or "", item.get("caption") or "") or None
                return e
            e["category"] = item.get("category") or categorize(
                item.get("name") or "", item.get("caption") or "") or None
            e["script"] = storable(result)   # tag_qa 보존(손으로 추리면 샌다, 2026-08-01)
            e["save_script"] = True                  # C단계가 캐시에 저장
        if not e["structure"]:
            try:
                e["structure"] = analyze_structure(e["script"].get("full_text", "")) or None
            except Exception:  # noqa: BLE001 — 구조분석 실패해도 적재는 성공시킨다
                e["structure"] = None
        # 원본 영상 영구보관(도서관 인라인 재생용) — /api/wiki/save와 동일 로직. 캐시 히트로
        # video_path가 비어 있으면(대본만 캐시되고 영상은 없던 경우) 여기서 재다운로드한다.
        # 실패해도 대본·구조는 저장(2026-07-26: 이 블록 누락으로 "원본 영상 없음"이었다).
        media_target = _WIKI_MEDIA_DIR / f"{hashlib.sha1(code.encode()).hexdigest()[:16]}.mp4"
        if not media_target.exists():
            src = e["video_path"]
            if src is None:
                try:
                    src, _dl_caption = download_any(item.get("video_url") or e["url"],
                                                    str(work_dir))
                except Exception:
                    src = None
            if src and Path(src).exists():
                try:
                    _WIKI_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
                    shutil.copy(str(src), str(media_target))
                except Exception:
                    pass
        e["status"] = "added"
        return e

    if todo:
        # 동시 3개 상한: 제미니 429(쿼터)가 한꺼번에 몰리면 오히려 느려지고 키가 소진된다.
        # 호출당 상한(_AUTOLOAD_MAX_PER_CALL=4)과 별개로 '동시에 몇 개'를 제한한다.
        with ThreadPoolExecutor(max_workers=min(_AUTOLOAD_MAX_WORKERS, len(todo))) as ex:
            done = list(ex.map(_fetch, todo))
    else:
        done = []

    # ── C) DB 쓰기 (순차) ────────────────────────────────────────
    for e in done:
        code, item = e["code"], e["item"]
        if e["status"] != "added":
            if e.get("rollback_latch"):
                # 키 풀 잠김 — 시도 횟수를 돌려준다(영상 탓이 아니다, 2026-08-07)
                store.autoload_rollback_attempt(code, e.get("error") or "")
            elif e.get("error"):
                store.autoload_mark_error(code, e["error"])
            if e["charged"]:
                refund_credit(cid, "script")         # 실패는 환불
                _refund_points(cid, pricing.OP_SCRIPT, keyroute.SVC_GEMINI)
            slots[e["i"]] = {"shortcode": code, "status": e["status"]}
            continue
        if e.get("save_script"):
            store.save_script(code, e["script"], category=e["category"])
        store.save_to_wiki({
            "shortcode": code,
            "name": item.get("name"),
            "category": e["category"],
            "url": e["url"],
            "followers": item.get("followers") or 0,
            "comments": item.get("comments") or 0,
            "density": item.get("density") or 0.0,
            "thumbnail": item.get("thumbnail") or "",
        }, e["script"], e["structure"], customer_id=cid)
        if e["structure"]:
            store.save_extract_structure(code, e["structure"])
        store.produce_pick_add(code, customer_id=cid)   # ★도서관+담기 둘 다 있어야 AI PICK이 뜬다
        added += 1
        slots[e["i"]] = {"shortcode": code, "status": "added"}

    results = [s for s in slots if s]
    # ★쿠팡 선수집(2026-08-17 사장님 지시 "1단계에서 뒤에서 상세·리뷰까지 뽑자").
    #   분석이 끝난 이 자리에 걸어두면, 사장님이 2단계로 넘어올 때쯤 재료가 준비돼 있다.
    #   대본 만들 때 긁으면 2~3분을 그 자리에서 기다리게 된다.
    try:
        _queue_product_prefetch(store, done, cid)
    except Exception as e:      # noqa: BLE001 — 선수집 실패가 영상 적재를 망치면 안 된다
        print("[product_prefetch] 큐잉 실패: %s %s" % (type(e).__name__, str(e)[:120]))
    return {"ok": True, "results": results, "added": added}


# 상품 재료를 미리 긁을 카테고리 — 사장님 지시로 **상품 관련만**(레시피·뷰티 제외).
# ⚠️ 라이브에 실재하는 라벨만 쓴다(홈템/레시피/뷰티/기타). 없는 라벨을 적으면 조용히 0건이 된다.
_PREFETCH_CATEGORIES = ("홈템", "기타")


def _lens_product_name(shortcode, hint="", src_path=None):
    """영상 화면을 Google Lens로 역검색해 **브랜드·모델까지** 잡는다(2026-08-17).

    ★왜 필요한가(사장님 지적): 무자막 해외 영상은 태깅이 뽑는 이름이 "실리콘 접이식 도마"
      수준에서 멈춘다. 그걸로 쿠팡을 치면 엉뚱한 게 잡힌다. 렌즈는 화면을 실제로
      역검색하므로 자막이 없어도 상품을 특정한다.
    ⚠️ **유료(SerpApi 프레임당 1콜)**라 아무 때나 부르지 않는다 — 태깅 이름으로 친
      쿠팡 검색이 빈손일 때만 승격한다(`_queue_product_prefetch`의 lens 폴백).
    ⚠️ `/api/coupang/lens`와 같은 원리지만 job이 필요 없다 — 1단계엔 job이 아직 없고,
      도서관 적재본이 서버에 있으므로 그 파일로 프레임을 뽑는다(판정 로직은 공용 함수 재사용).
    """
    code = (shortcode or "").strip()
    if not code:
        return ""
    # ★영상 경로를 두 곳에서 찾는다: 도서관 영구보관본 → 없으면 방금 받은 임시본.
    #   무자막 영상은 전사가 비어 `failed_empty`로 끝나 **영구보관까지 못 간다**(그 앞에서
    #   return한다). 그런데 화면은 방금 받아 놨다 — 그 파일이 살아 있는 동안에 뽑아야 한다.
    src = _WIKI_MEDIA_DIR / f"{hashlib.sha1(code.encode()).hexdigest()[:16]}.mp4"
    if not src.exists():
        src = Path(src_path) if src_path else None
        if not src or not src.exists():
            return ""
    work_id = f"prefetch_{code}"
    lens_dir = _FIND_TMP_DIR / work_id
    try:
        frames = frame_extract.extract_frames(str(src), lens_dir, max_frames=6)
        if not frames:
            return ""
        urls = [f"{PUBLIC_BASE_URL}/api/find/frame/{work_id}/{p.name}" for p in frames]
        return identify_product_from_lines(fetch_lens_lines(urls), caption=hint or "") or ""
    except Exception as e:      # noqa: BLE001 — 유료 경로가 죽어도 선수집은 계속 간다
        print("[product_prefetch] 렌즈 실패: %s %s" % (type(e).__name__, str(e)[:100]))
        return ""


def _queue_product_prefetch(store, done, cid):
    """1단계 분석 결과 → 쿠팡 상세·리뷰 선수집을 릴레이 큐에 걸어둔다.

    ## 왜 1단계인가 (사장님 설계)
    상품 재료 수집은 2~3분이 걸린다. 대본 만들 때 돌리면 그 시간을 사장님이 그대로
    기다린다. 영상 분석이 이미 도는 이 자리에 얹으면 **대기가 겹쳐 사라진다.**

    ## 검색어를 어디서 얻나 — 3단계를 기다릴 필요가 없다
    지금까지 상품은 3단계 편집안의 `affiliate_target`에서 왔다. 그런데 1단계 태깅이
    이미 **`product`(이 영상이 파는 제품 이름)**를 뽑고 있다(`script_extract.py:92`).
    그걸 검색어로 쓰면 1단계에서 바로 시작할 수 있다.

    ## 왜 서버가 직접 안 긁나
    쿠팡은 서버를 막는다 — AWS 서울(**한국 IP**)에서도 403(2026-08-17 실측).
    IP가 아니라 브라우저 지문을 본다. 그래서 사장님 PC 릴레이가 대신 돈다.
    릴레이가 꺼져 있으면 큐에 남아 있다가 켜질 때 처리된다(아무것도 안 깨진다).
    """
    from shopping_shorts import coupang_relay
    for e in done or []:
        # ★`added`만 보지 않는다(2026-08-17 사장님 지적 "무자막 외국 영상도 되나").
        #   무자막 영상은 전사가 비어 적재가 `failed_empty`로 끝나지만(app.py의 빈 대본
        #   캐시 방지 — 그 판정은 옳고 안 건드린다), **제품은 화면으로 이미 잡혀 있다**
        #   (`script_extract`가 자막 없어도 product·product_benefits를 뽑는다).
        #   재료가 제일 아쉬운 게 바로 그런 영상이라 여기서 빼면 안 된다.
        if e.get("status") in ("skipped_latched", "failed_limit", "failed_download"):
            continue                     # 영상을 못 받았으면 화면도 없다
        cat = (e.get("category") or "").strip()
        if cat not in _PREFETCH_CATEGORIES:
            continue                     # 레시피·뷰티는 팔 물건이 아니라 건너뛴다
        brief = ((e.get("script") or e.get("result") or {}).get("source_brief") or {})
        product = (brief.get("product") or "").strip() if isinstance(brief, dict) else ""
        code = e.get("code") or ""
        if not product:
            # 태깅이 이름을 못 잡았으면 화면 역검색으로 승격한다(유료라 이때만).
            product = _lens_product_name(code, hint=cat, src_path=e.get("video_path"))
        if not product:
            continue                     # 그래도 모르면 검색할 말이 없다
        if store.get_setting("product_prefetch_%s" % code, ""):
            continue                     # 같은 영상으로 두 번 긁지 않는다(쿠팡 두들김 방지)
        store.set_setting("product_prefetch_%s" % code, "queued")

        _enqueue_prefetch(code, product, cat)


def _enqueue_prefetch(code, product, cat, lens_tried=False):
    """상품 재료 수집 일감 하나를 큐에 건다(결과 저장 콜백 포함).

    ★렌즈 승격(2026-08-17): 태깅 이름으로 친 검색이 **빈손**이면 화면 역검색으로 이름을
      다시 잡아 한 번 더 시도한다. 무자막 해외 영상은 태깅 이름이 뭉뚱그려져("실리콘 도마")
      엉뚱한 게 잡히거나 아예 안 잡히는데, 렌즈는 화면을 보므로 브랜드·모델까지 간다.
    ★유료라 **한 번만** 승격한다(`lens_tried`) — 무한 재시도가 곧 요금이다.
    """
    from shopping_shorts import coupang_relay

    def _save(payload, meta, _code=code, _cat=cat, _tried=lens_tried):
        """릴레이가 보낸 결과를 도서관 캐시에 심는다 — job이 아직 없어도 남는다."""
        st = Store(DB_PATH)
        facts = (payload or {}).get("facts") or {}
        picked = (payload or {}).get("product") or {}
        if facts:
            st.set_setting("product_prefetch_%s" % _code, "done")
            st.set_setting("product_facts_%s" % _code,
                           json.dumps({"facts": facts, "product": picked}, ensure_ascii=False))
            return
        # 빈손 — 상품 자체를 못 찾은 경우에만 렌즈로 한 번 더 간다.
        # (상품은 찾았는데 분석이 빈 경우는 이름 문제가 아니므로 다시 긁지 않는다)
        if not _tried and not picked:
            lens_name = _lens_product_name(_code, hint=_cat)
            if lens_name:
                st.set_setting("product_prefetch_%s" % _code, "lens")
                print("[product_prefetch] 렌즈 승격: %s (%s)" % (lens_name, _code))
                _enqueue_prefetch(_code, lens_name, _cat, lens_tried=True)
                return
        st.set_setting("product_prefetch_%s" % _code, "empty")

    coupang_relay.QUEUE.submit_async(
        "detail", {"product": product, "shortcode": code, "category": cat},
        q=product, on_done=_save)
    print("[product_prefetch] 큐잉: %s (%s / %s%s)"
          % (product, cat, code, " · 렌즈" if lens_tried else ""))


@app.post("/api/produce/mix/start")
def api_produce_mix_start(request: Request, background_tasks: BackgroundTasks, body: dict):
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
    # 유료게이트(2026-07-20 E): 제작소 2단계도 결국 run_mix_job→렌더로 돈이 나간다. /api/mix/start와
    # 동일하게 render 과금+글로벌캡을 건다 — 안 걸면 제작소 흐름으로 하루 상한·전역 상한을 통째로
    # 우회할 수 있다(1단계 script 과금은 별개 자원이라 render 과금을 대체하지 못한다). 검증(위 ssrf·
    # 파싱)을 먼저 통과시킨 뒤 과금(리뷰 G1). render_charge_day를 채워 run_mix_job 실패 시 자동 환불된다.
    cid = getattr(request.state, "customer_id", 0)
    if _global_over_cap("render"):
        return JSONResponse(status_code=429, content={
            "ok": False, "error_code": "global_limit",
            "error": "지금 영상 만들기 이용이 많아요. 잠시 후 다시 시도해 주세요."})
    if not check_and_count(cid, "render"):
        return JSONResponse(status_code=429, content={
            "ok": False, "error_code": "daily_limit",
            "error": "오늘 영상 만들기 횟수를 다 썼어요. 결제하면 더 만들 수 있어요."})
    _denied = _charge_or_402(cid, pricing.OP_MIX, keyroute.SVC_GEMINI)
    if _denied:
        return _denied
    global_incr_and_alert("render")
    # 장면 우선 대본 모드(2026-07-20, Task7): produce.html "우리 시스템으로 믹스"는 항상 이 값을
    # true로 보낸다. mix_pipeline._plan_and_tts가 build_scene_first_plan으로 후보 n개를 만들고
    # 추천 후보를 자동 세팅한다(candidates=[]이면 기존 build_edit_plan으로 조용히 폴백).
    scene_first = bool(body.get("scene_first", False))
    # 백본(메인) 지정(2026-07-22): 사장님이 재료카드에서 '⭐메인'으로 고른 소스의 urls 인덱스.
    # 범위 밖·형변환 실패는 None으로 흘려 자동 선정에 맡긴다(잘못된 값에 job을 죽이지 않는다).
    backbone_main = _valid_backbone_main(body.get("backbone_main"), len(urls))
    job_id = uuid.uuid4().hex[:12]
    Store(DB_PATH).create_mix_job(job_id, urls, target, "free",
                                  subtitle_removal=subtitle_removal, given_script=script,
                                  script_structure=script_structure, scene_first=scene_first,
                                  customer_id=cid,
                                  render_charge_day=("trial" if _is_trial(cid) else _today_utc()),
                                  backbone_main=backbone_main)
    Store(DB_PATH).enqueue("mix", {"job_id": job_id})
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


@app.post("/api/produce/mix/{job_id}/trim")
def api_produce_mix_trim(job_id: str, body: dict):
    """비트의 앞/뒤 조용한 부분을 자른다(비파괴 — head_trim/tail_trim만 저장).
    mode=auto: silencedetect로 그 엣지 무음 길이 산출. nudge: step 누적. reset: 0.
    렌더 중이면 409(regen 규율). 하한 가드: 트림 합이 (probe−_TRIM_FLOOR)를 못 넘는다."""
    store = Store(DB_PATH)
    job = store.get_mix_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"ok": False, "error": "작업 없음"})
    if job.get("status") in ("rendering", "removing_subtitles"):
        return JSONResponse(status_code=409, content={"ok": False, "error": "렌더 중에는 자를 수 없어요"})
    plan = job.get("edit_plan") or {}
    beats = plan.get("beats") or []
    try:
        bi = int(body.get("beat_idx"))
    except (TypeError, ValueError):
        return JSONResponse(status_code=422, content={"ok": False, "error": "beat_idx 필요"})
    edge = body.get("edge")
    if edge not in ("tail", "head"):
        return JSONResponse(status_code=422, content={"ok": False, "error": "edge는 tail/head"})
    hit = next((b for b in beats if b.get("beat_idx") == bi), None)
    if hit is None:
        return JSONResponse(status_code=422, content={"ok": False, "error": "beat_idx 범위 밖"})
    key = "tail_trim" if edge == "tail" else "head_trim"
    mode = body.get("mode", "nudge")
    tts = hit.get("tts_path")
    if mode == "reset":
        hit[key] = 0.0
    elif mode == "auto":
        hit[key] = float(detect_edge_silence(tts, edge)) if tts else 0.0
    else:  # nudge
        step = float(body.get("step", 0.3))
        hit[key] = round(float(hit.get(key, 0.0)) + step, 3)
    # 하한 가드: head+tail이 probe−floor를 넘으면 이번 엣지를 되돌려 막는다.
    probe = _probe_duration(tts) if tts else 0.0
    if probe > 0:
        head, tail = hit.get("head_trim", 0.0), hit.get("tail_trim", 0.0)
        if _effective_dur(probe, head, tail) <= _TRIM_FLOOR and (head + tail) > (probe - _TRIM_FLOOR):
            hit[key] = max(0.0, round(probe - _TRIM_FLOOR - (head + tail - hit.get(key, 0.0)), 3))
    store.update_mix_job(job_id, edit_plan=plan)
    return {"ok": True, "head_trim": hit.get("head_trim", 0.0),
            "tail_trim": hit.get("tail_trim", 0.0), "trimmed": hit.get(key, 0.0)}


@app.post("/api/produce/mix/{job_id}/shorten")
def api_produce_mix_shorten(job_id: str, body: dict):
    """'⏱ 대사가 영상보다 김' 비트의 대사를 화면 예산에 맞게 줄이고 그 비트만 재TTS
    (2026-07-22 사장님 요청 — 경고만 뜨고 손볼 버튼이 없었다). 뜻·역할·말투 유지 축약
    (conform_narration: Gemini 실패 시 결정적 폴백). 성공 시 narration·tts·sync_gap 갱신."""
    store = Store(DB_PATH)
    job = store.get_mix_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"ok": False, "error": "작업 없음"})
    if job.get("status") in ("rendering", "removing_subtitles"):
        return JSONResponse(status_code=409, content={"ok": False, "error": "렌더 중에는 줄일 수 없어요"})
    plan = job.get("edit_plan") or {}
    beats = plan.get("beats") or []
    try:
        bi = int(body.get("beat_idx"))
    except (TypeError, ValueError):
        return JSONResponse(status_code=422, content={"ok": False, "error": "beat_idx 필요"})
    hit = next((b for b in beats if b.get("beat_idx") == bi), None)
    if hit is None:
        return JSONResponse(status_code=422, content={"ok": False, "error": "beat_idx 범위 밖"})
    # 화면 예산 = 공용 헬퍼(0순위-B: _conform_beats와 같은 한 곳) — 실험실 편성·트림 반영.
    budget = mix_pipeline.beat_screen_budget(hit)
    if budget <= 0:
        return JSONResponse(status_code=422, content={"ok": False, "error": "화면 길이를 알 수 없어요"})
    new_n = _edit_plan.conform_narration(hit.get("narration", ""), budget)
    if not new_n or new_n == hit.get("narration"):
        return {"ok": True, "changed": False, "narration": hit.get("narration", ""),
                "note": "더 줄일 여지가 없어요(뜻 훼손 없이)"}
    # 그 비트만 재TTS(렌더와 동일 공유 경로) → 실제 발화초로 sync_gap 재계산.
    idx = beats.index(hit)
    out = _MIX_WORK_DIR / job_id / "tts" / f"beat_{hit['beat_idx']}.mp3"
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        mix_pipeline.synthesize_line(
            new_n, out, voice=job.get("voice"), beat_role=hit.get("role"),
            beat_index=idx, beat_total=len(beats),
            previous_text=beats[idx - 1]["narration"] if idx > 0 else None,
            next_text=beats[idx + 1]["narration"] if idx < len(beats) - 1 else None)
        dur = mix_pipeline._probe_duration(str(out))
    except Exception as e:  # noqa: BLE001 — 실패해도 원문 유지(불일치 안 만든다)
        return JSONResponse(status_code=500, content={"ok": False, "error": f"재합성 실패: {e}"})
    hit["narration"] = new_n
    # 대사 바뀜 → 자막 메타(caption_lines·cap_durs·cap_lead) 통째 무효(2026-08-15).
    # 종전엔 caption_lines만 지워 cap_durs·cap_lead가 옛 대본 기준으로 남았다 → 자막 드리프트.
    mix_pipeline.invalidate_caption_meta(hit)
    hit["tts_path"] = str(out)
    if dur and dur > 0:
        hit["target_seconds"] = round(dur, 1)
        hit["sync_gap"] = round(max(0.0, dur - budget), 2)
    store.update_mix_job(job_id, edit_plan=plan)
    return {"ok": True, "changed": True, "narration": new_n, "sync_gap": hit.get("sync_gap", 0.0)}


@app.post("/api/produce/mix/{job_id}/sfx")
def api_produce_mix_sfx(job_id: str, request: Request, body: dict):
    """검수판에서 비트의 효과음(beat["sfx"])을 제거한다(스펙 §6 — "이 효과음 빼기").
    역할 매칭은 점수·제안 큐가 없어(자동배치 아니면 빈 채) v1은 제거만 지원 —
    되살리려면 다시 매칭한다. 컷어웨이 토글과 같은 구조(대상 키만 sfx)."""
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
    hit.pop("sfx", None)
    store.update_mix_job(job_id, edit_plan=plan)
    return {"ok": True}


@app.get("/api/produce/mix/{job_id}/bank_injected")
def api_produce_mix_bank_injected(job_id: str):
    """주입 미리보기(2026-07-23) — 이 대본 생성에 실제로 들어간 은행 블록(스파인·말투·전개)을
    그대로 돌려준다. '은행이 이번 대본에 뭘 댔나'를 눈으로 검증. 스마트믹스 off거나 은행이
    비었으면 injected=''(주입 없음)."""
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"ok": False, "error": "작업 없음"})
    plan = job.get("edit_plan") or {}
    return {"ok": True, "injected": plan.get("bank_injected", "")}


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


def _extract_beat_frame(work, beat, out_path, clean_sources=None):
    """beat.primary 클립의 start 시각 프레임 1장을 9:16(1080x1920)로 out_path에 저장.
    소스 영상이 없으면 False(파일 안 만듦). 프로덕션 poster 로직을 비트 단위로 일반화.

    clean_sources={video_id: 청소본경로}가 있으면 그 vid는 **원본 대신 청소본**에서
    프레임을 뜬다 — 2단계 자막제거를 켰는데도 꾸미기 미리보기에 원본 자막이 그대로
    살아있던 버그 수정(2026-07-21 사장님 제보). 최종렌더·캡컷·썸네일은 이미 청소본을
    쓰는데(app.py:2145·2214) 이 미리보기 프레임만 원본 glob을 써서 자막이 남았었다."""
    import subprocess
    pr = beat.get("primary") or {}
    vid = pr.get("video_id")
    ss = float(pr.get("start") or 0)
    src = None
    if vid and clean_sources:
        _cp = clean_sources.get(vid)
        if _cp and Path(_cp).exists():
            src = Path(_cp)
    if src is None and vid:
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
            "segs": video_assemble._caption_segments(narr, preset=b.get("caption_lines")),  # 렌더와 같은 분할
            "durs": b.get("cap_durs"),                              # 구절별 실제 표시시간(없으면 None)
            "lead": b.get("cap_lead", 0.0),                         # 말 시작 전 무음(초) — 렌더와 같은 기준점
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
    # 2단계 자막제거를 밟았으면(clean_sources 존재) 청소본에서 프레임을 뜬다. 캐시 파일명도
    # 분리(_clean)해, 자막제거 전에 캐시된 원본 프레임이 남아 미리보기에 지운 자막이 살아
    # 있는 것처럼 보이는 캐시 오염을 막는다(2026-07-21 제보).
    clean_map = job.get("clean_sources") or {}
    out = work / "beatframes" / f"{i}{'_clean' if clean_map else ''}.jpg"
    if not out.exists():
        _extract_beat_frame(work, beats[i], out, clean_sources=clean_map)
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


def _validate_role(asset_type, role):
    """sfx/overlay의 role 통제어휘 검증(scene_assets._ROLES) — upload·commit 공용 헬퍼.
    clip은 Gemini 자동태깅이 이미 이 어휘로 강제하지만 sfx/overlay는 role이 자유텍스트라
    오타·이형태가 매칭 키를 흩뜨린다(스펙 §5). 빈 role은 허용 — 매칭 후보에서 빠질 뿐이라
    저장 자체는 막지 않는다. 문제 없으면 None, 있으면 에러메시지."""
    if asset_type not in ("sfx", "overlay"):
        return None
    r = (role or "").strip()
    if r and r not in scene_assets._ROLES:
        return f"role은 {'/'.join(scene_assets._ROLES)} 중 하나여야 합니다(비우면 매칭 안 함)"
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

    # sfx/overlay role 통제어휘 검증(스펙 §5) — 자유텍스트 role이 매칭 키를 흩뜨리지 않게.
    role_err = _validate_role(asset_type, body.get("role"))
    if role_err:
        return JSONResponse(status_code=422, content={"ok": False, "error": role_err})

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
    # role 통제어휘 검증(스펙 §5) — sfx/overlay 업로드 폼은 드롭다운으로 막지만 서버도 방어.
    role_err = _validate_role(asset_type, role)
    if role_err:
        return JSONResponse(status_code=422, content={"ok": False, "error": role_err})
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
    seo/generate·fx/suggest와 같은 규약). 사장님이 후보를 눌러 레이어에 얹고 다듬는다.

    ★영상 대본(edit_plan) 우선(2026-07-26 사고): 제목은 '영상이 실제로 말하는 것'과 맞아야 한다.
    장면 우선 대본 모드(2026-07-20~)에선 후보를 고르면 그 후보의 나레이션이 edit_plan에 박히고
    영상은 그걸로 만들어진다. 반면 job.given_script/화면 대본(STATE.script)은 1단계 원본으로
    남고, 후보가 소스영상에서 생성되므로 영상과 무관해진다(세탁 영상에 '다이소 큐티클' 네일
    제목이 나온 실사고). 그래서 edit_plan의 나레이션(=고른 후보=영상이 말하는 대본)을 최우선으로
    쓴다. edit_plan이 없으면(구 흐름) 예전대로 화면 대본→원본 대본으로 폴백한다.

    2026-07-24 선행 사고(바나나 팬케이크에 '밥솥 식빵' 제목)도 이 규칙이 포섭한다: 제목이 늘
    '지금 영상(edit_plan)'을 따라가므로 옛 원본이 새지 않는다. 화면 대본이 영상 대본과 다르면
    script_mismatch=true로 알려 프런트가 '1단계 내용을 반영하려면 영상 매칭을 다시'라고 안내한다."""
    job_id = (body.get("job_id") or "").strip()
    job = Store(DB_PATH).get_mix_job(job_id) if job_id else None
    if not job:
        return JSONResponse(status_code=404, content={"ok": False, "error": "job 없음"})
    screen_script = (body.get("script") or "").strip()
    job_script = (job.get("given_script") or "").strip()
    # 영상이 실제로 말하는 대본 = 고른 후보(edit_plan)의 beat 나레이션을 이어붙인 것.
    plan_script = " ".join(
        (b.get("narration") or "").strip()
        for b in ((job.get("edit_plan") or {}).get("beats") or [])
    ).strip()
    used_script = plan_script or screen_script or job_script
    if not used_script:
        return JSONResponse(status_code=422, content={
            "ok": False, "error": "대본이 비어 있어요 — 1단계에서 대본을 확정하세요"})
    # 제목은 영상 대본(edit_plan)으로 짓되, headcopy/구조는 job 것을 그대로 참고로 둔다(대본이 진실의 축).
    job_for_titles = dict(job)
    job_for_titles["given_script"] = used_script
    # 경고는 '1단계 대본을 매칭 후 고쳤는가'를 본다 = 화면 대본 vs 원본(job) 대본(2026-07-24 규약).
    # edit_plan 나레이션은 원본의 리라이트라 화면 대본과 늘 달라서, 그걸로 비교하면 매번 오탐이 뜬다.
    # 제목은 이미 edit_plan(영상)으로 지어 영상과 일치하므로, 이 경고는 순수히 '네 1단계 수정은
    # 영상에 아직 안 들어갔다'는 안내다(같으면=안 고쳤으면 안 뜬다 → 정상 흐름은 조용하다).
    mismatch = bool(screen_script and job_script and screen_script != job_script)
    titles = thumb_title.generate(job_for_titles)
    if titles is None:
        return JSONResponse(status_code=502,
                            content={"ok": False, "error": "제목 생성 실패 — 잠시 후 다시 눌러보세요"})
    return {"ok": True, "titles": titles, "script_mismatch": mismatch}


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


# ── 부품은행(Pattern Bank) 큐레이션 API — Phase 0 (2026-07-21) ──────────────
# 대본을 8버킷 부품으로 분해·큐레이션한다. 백엔드 로직은 store.py·pattern_bank.py에
# 완성돼 있고 여기선 얇은 HTTP 래퍼만 얹는다(기존 흐름 무편집).

@app.post("/api/pattern/ingest")
def api_pattern_ingest(body: dict):
    """대본 1건을 분해해 부품은행에 담는다. body: {full_text, product_category?}.
    실 호출은 키풀(Gemini)을 쓴다 — 키가 없거나 추출 실패면 added=0으로도 200을 준다."""
    full_text = (body.get("full_text") or "").strip()
    if not full_text:
        return JSONResponse(status_code=422, content={"ok": False, "error": "full_text 필요"})
    product_category = (body.get("product_category") or "").strip() or None
    res = pattern_bank.ingest_script(
        Store(DB_PATH), full_text, product_category=product_category)
    return {"ok": True, **res}


@app.get("/api/pattern/items")
def api_pattern_items(bucket: str = None, status: str = None,
                      order: str = "perf", is_negative: int = None):
    """부품 목록. bucket/status로 필터, order=perf|freq|recent, is_negative(0/1)."""
    items = Store(DB_PATH).list_pattern_items(
        bucket=bucket or None, status=status or None,
        is_negative=is_negative, order_by=order or "perf")
    return {"ok": True, "items": items}


@app.post("/api/pattern/item/status")
def api_pattern_item_status(body: dict):
    """부품 상태 변경(approve/reject/pending). body: {id, status}."""
    item_id = body.get("id")
    status = (body.get("status") or "").strip()
    if item_id is None or not status:
        return JSONResponse(status_code=422, content={"ok": False, "error": "id·status 필요"})
    Store(DB_PATH).set_pattern_item_status(item_id, status)
    return {"ok": True}


@app.post("/api/pattern/item/edit")
def api_pattern_item_edit(body: dict):
    """부품 문구·태그·메모 교정. body: {id, text?, tags?, note?}. None인 필드는 유지."""
    item_id = body.get("id")
    if item_id is None:
        return JSONResponse(status_code=422, content={"ok": False, "error": "id 필요"})
    Store(DB_PATH).edit_pattern_item(
        item_id, text=body.get("text"), tags=body.get("tags"), note=body.get("note"))
    return {"ok": True}


@app.get("/api/pattern/buckets")
def api_pattern_buckets():
    """{bucket: {pending, approved, rejected}} 카운트(is_negative=0만)."""
    return {"ok": True, "counts": Store(DB_PATH).pattern_bucket_counts()}


@app.get("/api/pattern/spines")
def api_pattern_spines(status: str = None):
    """매크로 스파인 목록. status로 필터."""
    return {"ok": True, "spines": Store(DB_PATH).list_spines(status=status or None)}


@app.get("/api/script/styles")
def api_script_styles(category: str = None):
    """대본 생성에서 고를 수 있는 **스타일** 목록(2026-08-15).

    조건: 승인됨 + beat_roles가 붙어 있음(=기계가 검사 가능).

    ★카테고리로 **숨기지 않는다**(2026-08-15 사장님 지적으로 방침 변경). 처음엔 안 맞으면
      목록에서 뺐는데, 그러면 홈템 말고는(레시피·가전·뷰티) 칸이 통째로 사라져 사용자는
      기능이 있는지도 모른다. 실제로 다른 소재에 씌워도 잘 나온 실험이 있다(채이홈 스타일을
      DIY 피규어 소재에 적용 성공). 그래서 **경고만 달고 판단은 사람에게 맡긴다**:
        fit="검증"  = 이 소재에서 실제로 통한 스타일
        fit="타소재" = 다른 소재에서 검증됨(써도 되지만 어울림은 확인 필요)
      정렬은 검증 먼저, 그다음 실적순 — 첫 번째가 곧 추천이다."""
    styles = Store(DB_PATH).list_style_spines(category=None)     # 잠그지 않고 전부
    cat = (category or "").strip()
    out = []
    for s in styles:
        fits = s.get("fit_categories") or []
        verified = bool(cat) and (not fits or cat in fits)
        out.append({
            "id": s["id"], "name": s["name"], "situation_type": s["situation_type"],
            "beat_roles": s["beat_roles"], "chars_per_30s": s["chars_per_30s"],
            "fit_categories": fits, "source_count": s["source_count"],
            "perf_score": s["perf_score"],
            "fit": "검증" if verified else "타소재",
            # 사용자가 이름만 보고는 못 고른다 — 어디서 나왔고 얼마나 통했는지를 함께 준다.
            "evidence": s.get("situation_type") or "",
        })
    out.sort(key=lambda x: (x["fit"] != "검증", -(x["perf_score"] or 0), -(x["source_count"] or 0)))
    return {"ok": True, "styles": out}


def _facts_block_for_job(job_id, store=None):
    """job에 미리 긁어둔 제품 재료 → 프롬프트 블록. 없으면 ''(호출부는 기존 경로 그대로).

    ★여기서 크롤을 돌리지 않는다. 수집은 2~3분이 걸리므로 대본 생성 경로에 끼우면
      사장님이 그만큼 기다리게 된다 — 수집은 /api/product/facts/collect가 미리 해둔다."""
    job_id = job_id.strip() if isinstance(job_id, str) else ""   # 타입을 믿지 않는다
    if not job_id:
        return ""
    try:
        from shopping_shorts import product_facts
        st = store or Store(DB_PATH)
        job = st.get_mix_job(job_id)
        facts = ((job or {}).get("product") or {}).get("facts") or {}
        # ★1단계 선수집분 폴백(2026-08-17) — 3단계에서 상품을 고르기 전에도 재료가 있다.
        #   1단계가 담긴 영상별로 긁어 캐시에 심어두므로, job에 상품이 아직 없으면 거기서 꺼낸다.
        #   담긴 영상 여러 개 중 **재료가 있는 첫 번째**를 쓴다(주제는 [대본 1]이므로 그 순서).
        if not facts:
            facts = _prefetched_facts_for_job(job, st)
        return product_facts.prompt_block(facts)
    except Exception:      # noqa: BLE001 — 재료 조회 실패가 대본 생성을 막으면 안 된다
        return ""


def _prefetched_facts_for_job(job, store):
    """1단계가 미리 긁어둔 상품 재료 — 이 작업에 담긴 영상들의 캐시에서 찾는다.

    없으면 {}. 캐시 키는 `product_facts_<shortcode>`(1단계 `_queue_product_prefetch`가 심는다).
    ⚠️ 여기서 새로 긁지 않는다 — 이 함수는 대본 생성 경로라 기다림이 그대로 사장님 몫이 된다.
    """
    from shopping_shorts import mix_pipeline
    for url in ((job or {}).get("urls") or []):
        for key in mix_pipeline._cache_keys_for_url(url):
            raw = store.get_setting("product_facts_%s" % key, "")
            if not raw:
                continue
            try:
                d = json.loads(raw)
            except Exception:      # noqa: BLE001 — 깨진 캐시로 대본을 막지 않는다
                continue
            facts = (d or {}).get("facts") or {}
            if facts:
                return facts
    return {}


def _sources_for_generate(item, job, limit=3):
    """대본 생성에 넣을 **재료 대본 목록**. 담긴 영상 전부(최대 limit편) + 씨앗 항목.

    ★왜 여러 편인가(2026-08-17 사장님 지시): 한 편만 넣으면 그 한 편의 인물·상황에
      끌려가 편협해지고, **어느 편을 고르느냐가 결과를 좌우**한다(사용자는 뭐가 좋은
      대본인지 모른다). 담긴 것을 다 넣으면 고를 일이 없어진다 = 복불복이 사라진다.
    ★`_mix_source_block`이 원래 `sources[:3]`으로 3편까지 받게 돼 있다 — 그릇에 맞춰 채운다.
    ★job이 없으면(위키 직행 등) 종전대로 항목 하나. 회귀 0.
    """
    out, seen = [], set()

    def _add(name, full_text, structure):
        txt = (full_text or "").strip()
        if not txt or txt in seen:
            return
        seen.add(txt)
        out.append({"name": name or "", "full_text": txt, "structure": structure or {}})

    _add(item.get("category") or "", item.get("full_text"), item.get("structure"))
    for _vid, ex in sorted(((job or {}).get("extract") or {}).items()):
        if len(out) >= limit:
            break
        if not isinstance(ex, dict):
            continue
        txt = (ex.get("full_text") or "").strip()
        if not txt:
            txt = " ".join((s.get("text") or "").strip()
                           for s in (ex.get("segments") or [])
                           if isinstance(s, dict)).strip()
        _add(item.get("category") or "", txt, ex.get("structure"))
    return out[:limit]


def _materials_for_generate(item, body, store, cid):
    """대본 생성에 넣을 **재료 한 벌** → (sources, facts_block, job, job_id, scene_block)

    ★왜 함수로 뽑았나(2026-08-17): 원래 이 조립이 `/api/wiki/generate` 안에 통째로
      적혀 있었는데, [바꾸기] 부분 재생성(`/api/script/beat/regen`)도 **똑같은 재료**가
      필요해졌다. 두 곳에 각각 적으면 언젠가 반드시 어긋나고(0순위-B), 어긋나면
      "왜 전체 생성과 [바꾸기] 결과의 결이 다르냐"로 나타난다 — 조용해서 더 나쁘다.
      한 군데서만 정하게 만든다.

    담기는 것: 담긴 영상 전부(최대 3편) + 쿠팡 상세·리뷰 + 1단계 장면 태깅.
    ★타입을 믿지 마라(work_id 사고와 같은 유형): job_id·work_id는 클라이언트 값이라
      문자열이 아닐 수 있다 — dict가 오면 .strip()에서 500이 나고 대본이 통째로 안 나온다.
    """
    _jid = body.get("job_id")
    _jid = _jid.strip() if isinstance(_jid, str) else ""
    _job = store.get_mix_job(_jid) if _jid else None
    # 옛 작업이라 스냅샷에 장면 태깅이 없으면 캐시에서 보충한다 —
    # 이게 없으면 사장님이 1단계부터 다시 담아야 새 재료가 붙는다.
    _job = _enrich_job_extract(_job, store)
    # ★3단계를 아직 안 돌렸으면 job이 없다 — 그때는 **담긴 영상 전부**를 직접 모은다
    #   (2026-08-16). 안 그러면 재료가 씨앗 1편으로 줄어 모델이 나머지를 지어낸다.
    _wid = body.get("work_id")
    _wid = _wid.strip() if isinstance(_wid, str) else ""
    if not (_job or {}).get("extract") and _wid:
        try:
            _wex = _extract_from_work(_wid, cid, store)
        except Exception:  # noqa: BLE001 — 재료 보강 실패가 생성을 막지 않는다
            _wex = None
        if _wex:
            _job = dict(_job or {}, extract=_wex)
    _src = _sources_for_generate(item, _job)
    # ★제품 재료 주입(2026-08-16) — 이 작업에 연결된 쿠팡 상품에서 미리 긁어둔
    #   스펙·리뷰가 있으면 프롬프트에 얹는다. 없으면 ''이라 기존 경로 그대로(회귀 0).
    #   여기서 긁지 않는다 — 수집은 /api/product/facts/collect가 미리 해둔다(2~3분).
    _facts_block = _facts_block_for_job(_jid, store)
    # ★1단계 장면 태깅을 대본에도 준다(2026-08-17). label=이 장면이 무엇인가,
    #   use_point=이 장면을 어디에 어떻게 써먹나. 지금까지는 화면 붙일 때(edit_plan)만
    #   쓰고 대본 생성엔 안 실렸다 — 재료를 반만 쓰고 있었다.
    _scene_block = _scene_points_block(_job)
    if _scene_block:
        _facts_block = (_facts_block + "\n\n" + _scene_block) if _facts_block else _scene_block
    # ★`_scene_block`도 돌려준다 — 호출부가 응답의 `materials.scene_points`(화면에 "장면 N개"로
    #   표시)를 만들 때 쓴다. 여기서 안 주면 호출부가 `_scene_points_block`을 **한 번 더**
    #   부르게 되고, 그러면 같은 판단이 두 곳이 된다(0순위-B).
    return _src, _facts_block, _job, _jid, _scene_block


def _extract_from_work(work_id, cid, store):
    """3단계(매칭)를 아직 안 돌린 작업의 **담긴 영상 전부**를 job.extract 모양으로 만든다.

    ★왜 필요한가(2026-08-16 사장님 제보 "대본에 엉뚱한 얘기가 나온다"):
      대본 재료는 job(3단계 매칭 결과)에서 나온다. 그런데 1단계에서 담고 **바로 2단계로
      가면 job이 아직 없어서** 재료가 씨앗 1편으로 줄어든다 — 실측 work `ba20ea764254`는
      담긴 3편 중 216자짜리가 있었는데도 대표로 뽑힌 20자짜리 하나만 실렸고,
      모자란 만큼 모델이 지어내 카메라 영상에서 발뒤꿈치 각질 대본이 나왔다.
      화면은 "담긴 영상 N편을 전부 씁니다"라고 적혀 있었으니 화면도 거짓이었다.
    담긴 영상의 추출본은 캐시에 이미 있다 — job이 없을 때 그걸 대신 쓴다.
    """
    out = {}
    try:
        work = store.get_produce_work(work_id, customer_id=cid)
        state = (work or {}).get("state") or {}
        for e in (state.get("handoff") or []):
            if not isinstance(e, dict) or not e.get("useFootage"):
                continue
            sc = (e.get("shortcode") or "").strip()
            if not sc:
                continue
            ex = store.get_script(sc)
            if isinstance(ex, dict) and (ex.get("segments") or ex.get("full_text")):
                out[sc] = ex
    except Exception:  # noqa: BLE001 — 재료 보강 실패가 생성을 막지 않는다
        return {}
    return out


def _enrich_job_extract(job, store=None):
    """job 스냅샷에 장면 태깅이 없으면 **캐시(script_extracts)에서 보충**한다(2026-08-17).

    ★왜 필요한가(실측): job의 `extract`는 **그때 찍힌 스냅샷**이라, 나중에 재태깅으로
      `use_point`·`source_brief`가 쌓여도 옛 작업에는 소급되지 않는다.
      실측 job `8873eeb48a08` — 스냅샷은 장면 37개에 use_point **0건**인데,
      같은 영상이 캐시엔 `lens_tiktok_…` 키로 use_point 10건씩 갖춘 채 있었다.
      이걸 안 보충하면 **사장님이 1단계부터 다시 담아야** 새 재료를 쓴다.

    ⚠️ 원본을 안 건드린다(얕은 복사). DB에 쓰지도 않는다 — 읽기 전용 보충이다.
    ⚠️ 캐시 키 후보는 `mix_pipeline._cache_keys_for_url`이 정한다(같은 판단 1벌, 0순위-B).
    """
    ex = dict((job or {}).get("extract") or {})
    if not ex:
        return job
    # 이미 태깅이 있으면 손대지 않는다(스냅샷이 최신인 경우 = 대부분).
    def _tagged(e):
        return bool(isinstance(e, dict) and (e.get("source_brief") or any(
            (s.get("use_point") or "").strip() for s in (e.get("segments") or [])
            if isinstance(s, dict))))
    if any(_tagged(v) for v in ex.values()):
        return job
    try:
        from shopping_shorts import mix_pipeline
        st = store or Store(DB_PATH)
        urls = list((job or {}).get("urls") or [])
        keys = [k for u in urls for k in mix_pipeline._cache_keys_for_url(u)]
        cached = [c for c in (st.get_extract(k) for k in keys) if c and _tagged(c)]
        if not cached:
            return job
        # 소스 순서(s0·s1…)와 캐시 순서를 맞춰 얹는다. 개수가 다르면 있는 만큼만.
        for (vid, old), new in zip(sorted(ex.items()), cached):
            merged = dict(old if isinstance(old, dict) else {})
            merged["segments"] = new.get("segments") or merged.get("segments") or []
            if new.get("source_brief"):
                merged["source_brief"] = new["source_brief"]
            if not (merged.get("full_text") or "").strip() and new.get("full_text"):
                merged["full_text"] = new["full_text"]
            ex[vid] = merged
        out = dict(job)
        out["extract"] = ex
        return out
    except Exception:      # noqa: BLE001 — 보충 실패가 대본 생성을 막으면 안 된다
        return job


def _brief_line(brief):
    """영상 요약(dict 또는 문자열) → 프롬프트에 넣을 한 줄. 없으면 "".

    형식이 둘인 이유: 추출기는 {product, role, core, summary} dict로 주는데,
    옛 데이터·다른 경로에서는 문자열이 오기도 한다. 읽는 쪽이 둘 다 견뎌야 한다.
    """
    if isinstance(brief, str):
        return brief.strip()
    if not isinstance(brief, dict):
        return ""
    parts = [str(brief.get(k) or "").strip()
             for k in ("product", "role", "core")]
    return " · ".join(p for p in parts if p)


def _scene_points_block(job, limit=14):
    """1단계 장면 태깅 → 대본 프롬프트 재료 블록. 없으면 ''(기존 경로 그대로 = 회귀 0).

    label     = 이 장면이 **무엇인가**(정체)
    use_point = 이 장면을 새 영상에서 **어디에 어떻게 써먹나**(쓸모)

    지금까지 이 둘은 화면 붙이기(`edit_plan`)에서만 쓰이고 대본 생성엔 안 실렸다.
    대본이 장면을 모른 채 쓰이면 "말과 화면이 따로 노는" 결과가 된다 — 같은 재료를
    양쪽이 보게 한다.

    ⚠️ 장면을 **그대로 나열하라는 지시가 아니다.** 사실 재료로만 준다(표현은 스타일 몫).
    """
    lines = []
    for _vid, ex in sorted(((job or {}).get("extract") or {}).items()):
        if not isinstance(ex, dict):
            continue
        # ★source_brief는 **dict**다(product/role/core/summary) — 문자열이 아니다.
        #   여기서 .strip()을 바로 불러 500이 났다(2026-08-16 실사고: 대본이 통째로
        #   안 나오고 화면엔 '네트워크 오류'만). 옛 작업엔 이 값이 없어 안 터지다가,
        #   캐시에서 최신 추출본을 끌어오면서 진짜 값이 들어오자 드러났다.
        #   문자열로 와도(옛 형식) 그대로 받아들인다.
        brief = _brief_line(ex.get("source_brief"))
        if brief:
            lines.append("· [영상 요약] " + brief)
        for seg in (ex.get("segments") or []):
            if not isinstance(seg, dict):   # 세그가 문자열 등으로 깨져 있어도 500 내지 않는다
                continue
            if len(lines) >= limit:
                break
            up = (seg.get("use_point") or "").strip()
            lb = (seg.get("label") or "").strip()
            if up:
                lines.append("· %s%s" % (up, (" (%s)" % lb) if lb else ""))
            elif lb:
                lines.append("· " + lb)
        if len(lines) >= limit:
            break
    if not lines:
        return ""
    return ("[이 영상들에 실제로 있는 장면]\n" + "\n".join(lines[:limit])
            + "\n※ 여기 있는 장면으로 말이 되게 써라. 없는 장면을 지어내지 마라. "
              "장면 이름을 그대로 나열하지 말고 **말로 풀어라**.")


@app.post("/api/coupang/relay/prefetch_retry")
def api_product_prefetch_retry(body: dict):
    """상품 재료 선수집을 **다시** 건다(2026-08-17). body: {shortcode, product?, category?}.

    ## 왜 필요한가
    선수집은 1단계 담기 때 자동으로 한 번만 걸린다(같은 영상을 두 번 긁으면 쿠팡이
    소프트 차단한다). 그래서 **릴레이가 꺼져 있었거나 중간에 실패한 영상**은 되살릴
    길이 없었다 — 실제로 릴레이가 옛 코드로 돌아 재료 0건으로 끝난 건이 있었다.

    product를 안 주면 그 영상 태깅에서 다시 찾고, 그래도 없으면 화면 역검색(유료 1회).
    """
    # ★경로를 /api/coupang/relay/ 아래에 둔 이유: 이건 화면 버튼이 아니라 **운영 도구**라
    #   로그인 세션이 없다. 그 접두사는 미들웨어 예외이고 대신 **엔드포인트가 토큰을 검사**한다
    #   (릴레이 next/result와 같은 규칙 — 인증 방식을 새로 만들지 않는다).
    if not config.COUPANG_RELAY_TOKEN or body.get("token") != config.COUPANG_RELAY_TOKEN:
        return JSONResponse(status_code=403, content={"ok": False, "error": "토큰 불일치"})
    code = (body.get("shortcode") or "").strip()
    if not code:
        return JSONResponse(status_code=422, content={"ok": False, "error": "shortcode 필요"})
    store = Store(DB_PATH)
    cat = (body.get("category") or "").strip()
    product = (body.get("product") or "").strip()
    if not product:
        ex = store.get_extract(code) or {}
        product = ((ex.get("source_brief") or {}) or {}).get("product") or ""
        cat = cat or (ex.get("category") or "")
        product = product.strip()
    if not product:
        product = _lens_product_name(code, hint=cat)
    if not product:
        return {"ok": False, "error": "제품 이름을 잡지 못했습니다(태깅·렌즈 모두 실패)"}
    # 재시도니까 중복 가드를 푼다 — 사람이 명시적으로 요청한 것이다.
    store.set_setting("product_prefetch_%s" % code, "")
    _enqueue_prefetch(code, product, cat or "기타")
    return {"ok": True, "queued": product}


@app.post("/api/product/facts/collect")
def api_product_facts_collect(body: dict):
    """쿠팡 상품 → **대본 재료**(스펙·리뷰) 수집·분석해 product_json에 심는다(2026-08-16).

    body: {job_id, force?}  — 이미 facts가 있으면 그대로 준다(force=true면 다시 긁는다).

    ## 왜 이 자리인가
    사장님이 8단계에서 쿠팡 상품을 고르는 흐름이 이미 있다(`/api/coupang/product`).
    **그 상품을 대상으로 한 번만** 긁어두면 대본을 몇 번 만들든 재사용한다.
    대본 만들 때 실시간으로 돌리면 2~3분을 기다리게 되므로 그렇게 하지 않는다.

    ## ⚠️ 사장님 PC에서만 수집된다
    쿠팡은 **한국 IP만** 받는다(coupang_relay.py 실측: 서버 직결·독일 주거용 프록시 모두 403).
    서버에서 부르면 크롤이 빈 결과가 되고 facts도 빈 채로 저장된다 — 그래도 **예외는 안 낸다**
    (재료가 없다고 대본 생성이 막히면 안 된다. `prompt_block`이 ''를 주면 기존 경로 그대로).

    소요(실측 2026-08-16, 필통): 상세 60~90초 + 리뷰 23초 + 제미니 30~50초 = **약 2~3분**.
    화면은 이 호출을 **백그라운드로** 띄우고 기다리지 마라.
    """
    from shopping_shorts import product_facts

    job_id = (body.get("job_id") or "").strip()
    store = Store(DB_PATH)
    job = store.get_mix_job(job_id) if job_id else None
    if not job:
        return JSONResponse(status_code=404, content={"ok": False, "error": "job 없음"})
    product = job.get("product") or {}
    url = product.get("url") or ""
    if not url:
        return JSONResponse(status_code=422,
                            content={"ok": False, "error": "이 작업에 연결된 쿠팡 상품이 없습니다"})
    if product.get("facts") and not body.get("force"):
        return {"ok": True, "facts": product["facts"], "cached": True}

    work = _MIX_WORK_DIR / job_id / "product_facts"
    facts = product_facts.collect_and_analyze(url, str(work), name=product.get("name") or "")
    product["facts"] = facts
    store.set_mix_product(job_id, product)
    return {"ok": True, "facts": facts, "cached": False,
            "empty": not any(facts.get(k) for k in ("specs", "pain", "voice", "satisfy"))}


@app.get("/api/script/style/templates")
def api_script_style_templates(spine_id: int, role: str = None):
    """[바꾸기] 후보 — **그 스타일이 가진 문장틀**을 준다(2026-08-16 사장님 지시).

    ## 왜 은행 완성문장이 아니라 '틀'인가 (실측 근거)

    처음엔 은행(`pattern_item`)의 완성문장을 후보로 띄우려 했는데, 사장님이 목업을 보고
    바로 짚으셨다 — *"쌀밥 대본인데 훅 샘플에 안 맞는 것들이 많다"*.
    실측해보니 그 지적이 맞았다:

      · 은행 훅 534건 중 **소재 태그(`tags_json`)가 있는 건 0건** → 소재로 거를 방법이 없다
      · 문장틀로만 걸러도 74건이 남는데 거기에 "냉동 삼겹살은 절대 해동하지 마세요",
        "여러분 다이소 가면 이거 무조건 사오세요"가 섞인다
        → **쌀밥 대본에 삼겹살 훅을 후보로 띄우게 된다**

    틀을 주면 이 문제가 통째로 사라진다. 빈칸(`{가족}`·`{제품}`)은 **AI가 이 대본 소재에
    맞게 채우므로** 소재 태그가 아예 필요 없고, 남의 문장을 복사하는 게 아니라 **구조만
    빌려 창작**하게 된다. 틀은 이미 `spine.templates_json`에 있고, 생성 프롬프트도 이미
    같은 틀을 "빈칸만 채워라"로 쓰고 있다(`bank_assemble.style_block`) — 화면과 프롬프트가
    **같은 원천**을 보게 되므로 어긋날 수가 없다(0순위-B).

    role을 주면 그 칸만, 안 주면 칸 전체를 준다.
    ★틀이 없는 칸은 **빈 배열**로 준다(그 칸은 문장을 강제하지 않는다는 뜻이지 고장이 아니다).
    """
    sp = None
    for s in Store(DB_PATH).list_spines():
        if s["id"] == spine_id:
            sp = s
            break
    if not sp:
        return JSONResponse(status_code=404, content={"ok": False, "error": "없는 스타일"})
    templates = sp.get("templates") or {}
    roles = sp.get("beat_roles") or []
    # 칸 설명은 beat_chain(사람이 읽는 자연어)에서 순서대로 빌린다 — style_block과 같은 규칙.
    descs = dict(zip(roles, sp.get("beat_chain") or []))
    want = [role] if role else roles
    out = []
    for r in want:
        if r not in roles:
            continue
        out.append({
            "role": r,
            "desc": descs.get(r, ""),
            # 빈칸이 보이게 그대로 준다 — 화면에서 "{가족}" 같은 자리를 표시해야
            # 사용자가 "여긴 우리 소재로 채워진다"를 안다.
            "templates": list(templates.get(r) or []),
        })
    return {"ok": True, "spine_id": spine_id, "name": sp.get("name") or "",
            "chars_per_30s": sp.get("chars_per_30s"), "roles": roles, "slots": out}


@app.post("/api/script/beat/regen")
def api_script_beat_regen(request: Request, body: dict):
    """[바꾸기] — 대본의 **한 칸만** 다시 쓴다(2026-08-17 사장님 B안).

    body: {shortcode, style_id, role, beats:[{role,text}], template?,
           job_id?, work_id?, target_seconds?, structure?, base_script?, category?}

    ## 왜 이게 필요했나

    지금까지 [바꾸기]는 문장틀을 **원문 그대로** 칸에 꽂았다. 그래서 화면에
    `이것 때문에 {가족}한테 욕 바가지로 먹을 뻔했어요`처럼 중괄호가 박혔다.
    설계는 원래 "빈칸은 AI가 이 대본 소재로 채운다"였는데(위 `templates` 주석)
    **그 채우는 단계가 미구현**이었다(handoff/대본UI2단계.md ⏭ 4번).

    사장님이 B안을 고르셨다 — 빈칸만 치환하는 게 아니라 **틀의 구조만 빌려 그 칸을
    새로 쓴다**. 빈칸 치환은 한 단어만 바뀌어 "바꿔도 바뀐 느낌이 안 나고"(실측: 미끼
    틀 4개 중 2개가 슬롯만 다른 같은 문장), 재생성은 같은 틀이라도 매번 다른 문장이
    나온다. 이게 곧 `[훅만 다시]` 부분 재생성이라 두 기능이 한 벌이 된다.

    ★재료는 `_materials_for_generate`로 **전체 생성과 같은 한 벌**을 쓴다(0순위-B).
    ★실패를 조용히 넘기지 않는다 — 못 만들면 502로 알려 화면이 "다시 시도"를 띄운다.
      (반쪽짜리 문장이나 중괄호가 남은 문장을 성공인 척 돌려주면 이 기능의 존재 이유가 없다)
    """
    store = Store(DB_PATH)
    cid = _cid(request)
    role = (body.get("role") or "").strip()
    if not role:
        return JSONResponse(status_code=422, content={"ok": False, "error": "role 필요"})
    try:
        style_id = int(body.get("style_id"))
    except (TypeError, ValueError):
        return JSONResponse(status_code=422, content={"ok": False, "error": "style_id 필요"})
    beats = [b for b in (body.get("beats") or []) if isinstance(b, dict)]
    if not beats:
        return JSONResponse(status_code=422, content={"ok": False, "error": "beats 필요"})

    style = next((s for s in store.list_style_spines(category=None) if s["id"] == style_id), None)
    if not style:
        return JSONResponse(status_code=404, content={"ok": False, "error": "없는 스타일"})

    # 재료 — 전체 생성과 같은 경로로 씨앗 항목을 찾는다(위키에 없으면 body 폴백도 동일).
    shortcode = (body.get("shortcode") or "").strip()
    it = store.get_wiki_item(shortcode, customer_id=cid) if shortcode else None
    if not it:
        _structure = body.get("structure")
        it = {"structure": _structure if isinstance(_structure, dict) else {},
              "full_text": body.get("base_script") or "",
              "category": body.get("category") or ""}
    _src, _facts_block, _job, _jid, _scene_block = _materials_for_generate(it, body, store, cid)

    _bank_ctx = ""
    if store.get_setting("ping_pong_enabled", "") == "1":
        _bank_ctx = bank_assemble.assemble_bank_context(store, it.get("category") or "") or ""

    try:
        out = script_generate.regen_one_beat(
            _src, style, role, beats,
            template=body.get("template") or "",
            target_seconds=body.get("target_seconds") or 30,
            bank_context=_bank_ctx, facts_block=_facts_block)
    except Exception as e:  # noqa: BLE001 — 실패해도 화면이 살아야 한다(원본 문장 유지)
        print(f"beat regen 실패(style={style_id}, role={role}): {e}")
        out = None
    if not out:
        return JSONResponse(status_code=502, content={
            "ok": False, "error": "문장을 다시 만들지 못했어요 — 잠시 후 다시 시도해 주세요"})
    return {"ok": True, **out}


@app.post("/api/pattern/spine/status")
def api_pattern_spine_status(body: dict):
    """스파인 승인/기각. body: {id, status}. 승격게이트(source_count>=3 AND approved)의
    '사람 승인' 절반 — 야간배치는 pending만 만들고 여기서만 approved가 된다."""
    spine_id = body.get("id")
    status = (body.get("status") or "").strip()
    if spine_id is None or not status:
        return JSONResponse(status_code=422, content={"ok": False, "error": "id·status 필요"})
    Store(DB_PATH).set_spine_status(spine_id, status)
    return {"ok": True}


@app.post("/api/pattern/spine")
def api_pattern_spine_add(body: dict):
    """매크로 스파인 수동 시드. body: {name, situation_type?, character_roles?,
    beat_chain?, emotion_arc?, appeal?, fit_categories?, status?}."""
    name = (body.get("name") or "").strip()
    if not name:
        return JSONResponse(status_code=422, content={"ok": False, "error": "name 필요"})
    sid = Store(DB_PATH).add_spine(
        name,
        situation_type=body.get("situation_type"),
        character_roles=body.get("character_roles"),
        beat_chain=body.get("beat_chain"),
        emotion_arc=body.get("emotion_arc"),
        appeal=body.get("appeal"),
        fit_categories=body.get("fit_categories"),
        status=(body.get("status") or "pending"))
    return {"ok": True, "id": sid}


# 정적 프론트 (마운트는 맨 마지막)
_STATIC = Path(__file__).parent / "static"


# PWA 매니페스트 — StaticFiles의 mimetypes 추측(.webmanifest 미등록 환경=octet-stream)에
# 맡기지 않고 표준 타입을 명시한다. 마운트보다 먼저 등록돼 우선 매칭.
@app.get("/manifest.webmanifest", include_in_schema=False)
def _pwa_manifest():
    return FileResponse(_STATIC / "manifest.webmanifest",
                        media_type="application/manifest+json")

# 롱폼→쇼츠 API(2026-08-15). 라우트 정의는 longform_api.py에 모아두고 여기서 붙이기만 한다
# — app.py가 이미 9천 줄이라 새 기능을 여기에 또 쌓으면 찾기 어려워진다.
# 게이트는 미들웨어(_verify_session)가 이미 /api/* 전체를 막으므로 여기선 통과 함수만 넘긴다.
try:
    from shopping_shorts import longform_api as _lf_api
    _lf_api.register(app, lambda _req: None)
except Exception:                                  # noqa: BLE001 — 이 기능이 앱 기동을 막지 않는다
    traceback.print_exc()


# 클린 URL — /library, /mix 등 확장자(.html) 없이 접근. (index는 루트 '/'로 자동)
# 기존 /xxx.html 경로도 아래 StaticFiles 마운트로 계속 동작(백워드 호환).
# no-cache: UI 배포 후 브라우저가 옛 HTML을 캐시로 재사용해 "고쳤는데 안 바뀜"이
# 반복됨(2026-07-14 역할배정·사이드바 등 실사고) → 매 요청 서버 재검증 강제.
_NOCACHE = {"Cache-Control": "no-cache, must-revalidate"}
for _pg in ("discover", "find", "library", "mix", "outreach", "produce", "collection",
            "scene_library", "pattern_bank", "longform", "settings"):
    app.add_api_route(
        f"/{_pg}",
        (lambda n=_pg: FileResponse(_STATIC / f"{n}.html", media_type="text/html",
                                    headers=_NOCACHE)),
        include_in_schema=False,
    )

# 작업대(발음교정 튜닝 워크벤치)는 관리자(customer_id==0) 전용 — 위 클린 URL 루프와
# 달리 명시 게이트가 필요해 별도 처리한다. "/voice_tune"과 "/voice_tune.html" 둘 다
# 명시 라우트로 등록해 아래 StaticFiles 마운트(확장자 그대로 서빙)보다 먼저 매칭시킨다
# — 안 그러면 /voice_tune.html 직접 접근이 게이트 없이 뚫린다(2026-07-22).
def _voice_tune_page(request: Request):
    denied = _require_admin(request)
    if denied:
        return denied
    return FileResponse(_STATIC / "voice_tune.html", media_type="text/html", headers=_NOCACHE)


app.add_api_route("/voice_tune", _voice_tune_page, include_in_schema=False)
app.add_api_route("/voice_tune.html", _voice_tune_page, include_in_schema=False)


# 레퍼런스 채널 통합 관리페이지(2026-07-24) — 관리자(customer_id==0) 전용.
# 인스타·유튜브·틱톡 레퍼런스 계정을 "엑셀처럼" 여러 줄 붙여넣기로 일괄 등록/관리한다.
# 등록·목록·삭제는 전부 기존 API 재사용(신규 등록 로직 없음): 인스타=/api/reference/register
# +/api/discover/added+/api/prune/remove, 틱톡·유튜브=/api/seeds(kind=account). 그래서
# 이 페이지는 게이트 있는 정적 라우트 하나면 된다(voice_tune과 동일 이유로 mount보다 먼저).
def _refs_page(request: Request):
    denied = _require_admin(request)
    if denied:
        return denied
    return FileResponse(_STATIC / "refs.html", media_type="text/html", headers=_NOCACHE)


app.add_api_route("/refs", _refs_page, include_in_schema=False)
app.add_api_route("/refs.html", _refs_page, include_in_schema=False)


# ── 역대 히트작(채널 아카이브, 2026-08-03) — 관리자 전용 ─────────────────────
# channel_archive(백그라운드 크롤러가 채우는 채널 전체 릴스)를 조회수순으로 본다.
# 매일 수집 랭킹(48h 창)이 못 보는 옛 히트작 발굴용. 담기는 기존 mix_basket 재사용.
def _archive_page(request: Request):
    denied = _require_admin(request)
    if denied:
        return denied
    return FileResponse(_STATIC / "archive.html", media_type="text/html", headers=_NOCACHE)


app.add_api_route("/archive", _archive_page, include_in_schema=False)


def _archive_channel_cat_fn(store):
    """채널→카테고리 판정 함수(2026-08-03) — 랭킹과 같은 우선순위:
    reel_history 최빈 > 발굴등록 카테고리 > 채널명 키워드 분류. 채널 목록과
    '태그 없는 릴스' 폴백이 공유한다."""
    from shopping_shorts.categorize import categorize as _cat
    human = store.channel_categories()
    disc_cat, names = {}, {}
    for d in store.discovered_channels():
        u = (d.get("username") or "").strip().lstrip("@")
        if u:
            disc_cat[u] = (d.get("category") or "").strip()
            names[u] = d.get("name") or u
    try:
        for ch in load_channels():
            u = (ch.get("username") or "").strip().lstrip("@")
            if u and u not in names:
                names[u] = ch.get("name") or u
    except Exception:   # noqa: BLE001 — 엑셀 없음(로컬 등)이어도 목록은 나가야 한다
        pass
    def _chcat(u):
        return (human.get((u or "").lower()) or disc_cat.get(u)
                or _cat(names.get(u, u), "") or "기타")
    return _chcat


@app.get("/api/archive/channels")
def api_archive_channels(request: Request):
    """아카이브된 채널 목록 [{username, reels, top_views}] — 진행률 표시 겸용."""
    denied = _require_admin(request)
    if denied:
        return denied
    store = Store(DB_PATH)
    blocked = store.removed_usernames()   # 영구차단 채널은 아카이브에서도 안 보이게(2026-08-03)
    _chcat = _archive_channel_cat_fn(store)
    with store._conn() as c:
        rows = c.execute(
            "SELECT username, COUNT(*), MAX(views) FROM channel_archive "
            "GROUP BY username ORDER BY MAX(views) DESC").fetchall()
    names = store.channel_name_map()   # 한글 표시명(2026-08-06) — 드롭다운도 카드와 같은 이름으로
    return {"ok": True, "channels": [
        {"username": r[0], "name": names.get((r[0] or "").strip().lstrip("@"), ""),
         "reels": r[1], "top_views": r[2] or 0,
         "category": _chcat(r[0])} for r in rows
        if (r[0] or "").strip().lstrip("@").lower() not in blocked]}


@app.get("/api/archive/items")
def api_archive_items(request: Request, username: str = "", sort: str = "views",
                      q: str = "", cat: str = "", limit: int = 120, offset: int = 0):
    """아카이브 릴스 조회. username 지정 시 그 채널만, q는 채널명 부분일치.
    sort: views | recent | comments. cat: 카테고리 필터 — **영상 단위**(2026-08-03).

    채널 단위 카테고리는 혼합 채널(맛집|살림템|레시피)에서 레시피 영상이 홈템에
    묻히는 문제(사장님 제보)가 있어, 랭킹과 같은 방식으로 릴스별 비전태그를
    캡션 자리에 넣어 categorize로 영상마다 판정한다. 태그 없는 릴스는 채널명만으로
    판정(종전과 동일 수준)."""
    denied = _require_admin(request)
    if denied:
        return denied
    from shopping_shorts.categorize import categorize as _cat_fn
    from shopping_shorts.vision_tagging import vision_text
    store = Store(DB_PATH)
    _chcat = _archive_channel_cat_fn(store)
    order = {"recent": "posted_at DESC", "comments": "comments DESC"}.get(sort, "views DESC")
    where, args = [], []
    if username:
        where.append("a.username=?"); args.append(username.strip().lstrip("@"))
    if q:
        where.append("a.username LIKE ?"); args.append(f"%{q.strip().lstrip('@')}%")
    sql = ("SELECT a.username, a.shortcode, a.url, a.thumbnail, a.views, a.likes, "
           " a.comments, a.posted_at, v.subject, v.keywords_json "
           "FROM channel_archive a LEFT JOIN vision_tags v ON v.shortcode=a.shortcode "
           + ("WHERE " + " AND ".join(where) + " " if where else "")
           + f"ORDER BY {order} LIMIT ? OFFSET ?")
    # 카테고리 필터는 파이썬에서 거르므로 넉넉히 읽고 자른다.
    lim = max(1, min(int(limit or 120), 500))
    # 페이지네이션(2026-08-09): cat 필터는 파이썬에서 거르므로 offset도 파이썬에서 센다.
    off = max(0, int(offset or 0))
    args.extend([lim, off] if not cat else [5000, 0])
    blocked = store.removed_usernames()   # 영구차단 채널 릴스 숨김(2026-08-03)
    # 한글 표시명(2026-08-06 사장님: "채널명은 한글로 레퍼런스 랭킹처럼"). 아카이브엔
    # username뿐이라 수집 이력에서 이름을 끌어온다. 없으면 화면이 @아이디로 폴백한다.
    names = store.channel_name_map()
    import json as _json
    with store._conn() as c:
        rows = c.execute(sql, args).fetchall()
    out = []
    for r in rows:
        u = (r[0] or "").strip().lstrip("@")
        if u.lower() in blocked:
            continue
        try:
            kws = _json.loads(r[9] or "[]")
        except ValueError:
            kws = []
        vtext = vision_text({"subject": r[8] or "", "keywords": kws})
        # 태그 있으면 영상 단위 판정(랭킹과 동일), 없으면 채널 단위 폴백(종전 수준 유지).
        item_cat = _cat_fn(u, vtext) if vtext else _chcat(u)
        if cat and item_cat != cat:
            continue
        if cat and off > 0:
            off -= 1
            continue
        out.append({"username": r[0], "name": names.get(u, ""),
                    "shortcode": r[1], "url": r[2], "thumbnail": r[3],
                    "views": r[4], "likes": r[5], "comments": r[6], "posted_at": r[7],
                    "category": item_cat})
        if len(out) >= lim:
            break
    # ⏱ 영상 길이(2026-08-06 사장님 요청). 랭킹과 **같은 헬퍼**를 쓴다 — 캐시 결합 + 빈 곳이
    # 있으면 백필 예약(1시간 1회)까지 한 곳에서 처리된다. 아직 대부분 비어 있어(78,265건 중
    # 극소수) 화면은 아는 것에만 ⏱을 띄운다 — 백필이 조회수 상위부터 채우면 점점 늘어난다.
    _attach_durations(out, store)
    return {"ok": True, "items": out}


@app.get("/api/archive/similar")
def api_archive_similar(request: Request, shortcode: str, limit: int = 40,
                        verify: bool = True, verify_n: int = 60):
    """랭킹 릴스 1개 → 내 아카이브에서 '같은 제품'의 옛 영상 찾기(2026-08-03, 08-04 개편).

    사장님 궁극 목표: 오늘 터진 영상을 눌러, 우리가 크롤해 둔 채널 아카이브에서
    **같은 제품**을 다룬 예전 영상을 모아 담기→믹스. 렌즈로 하던 걸 내부에서 하는 것.

    2단이다:
      1단 태그 겹침 — 전체를 훑어 후보를 만든다(무료·즉시).
      2단 제품명 검증 — 상위 verify_n개만 AI로 실제 제품명을 읽어 같은 제품을 올린다.
    2단이 왜 필요한가: 태그만으로는 분위기어('살림꿀팁' 15%)가 지배해 같은 제품이
    안 올라온다(실측). verify=false면 1단만 — 빠르지만 예전 품질이다."""
    denied = _require_admin(request)
    if denied:
        return denied
    import json as _json
    store = Store(DB_PATH)
    src = store.vision_tags_map([shortcode]).get(shortcode)
    def _tokens(subject, kws):
        toks = set()
        for w in ([subject or ""] + list(kws or [])):
            for t in str(w).replace(",", " ").split():
                if len(t) >= 2:
                    toks.add(t.lower())
        return toks
    # ★태그가 없어도 끝내지 않는다(2026-08-04 2차). 종전엔 여기서 no_tags 조기반환해
    # 미태깅 영상은 내부검색 버튼이 무용지물이었다(사장님 실화면 제보). 지금은 제품명
    # 직접검색이 있어 썸네일 제품명만 읽으면 태그 없이도 같은 제품을 찾는다.
    src_t = _tokens(src.get("subject"), src.get("keywords")) if src else set()
    with store._conn() as c:
        rows = c.execute(
            "SELECT a.username, a.shortcode, a.url, a.thumbnail, a.views, a.likes, "
            " a.comments, a.posted_at, v.subject, v.keywords_json, v.product "
            "FROM channel_archive a JOIN vision_tags v ON v.shortcode=a.shortcode "
            "LIMIT 50000").fetchall()

    # 질의의 제품명이 이미 판독돼 있으면 먼저 꺼낸다 — 후보 선정에 쓴다(아래).
    known_q = store.products_map([shortcode]).get(shortcode) or ""

    scored = []
    for r in rows:
        if r[1] == shortcode:
            continue
        try:
            kws = _json.loads(r[9] or "[]")
        except ValueError:
            kws = []
        ov = len(src_t & _tokens(r[8], kws))
        # ★겹침0이어도 '이미 판독된 제품명이 같으면' 후보에 넣는다(2026-08-04).
        # 안 그러면 제품명이 같은데도 후보에 못 들어 영영 안 보인다 — 실측:
        # [극세사 걸레] → [극세사 유리 닦이]가 겹침0으로 탈락(제품명엔 '극세사'가 같은데).
        # 태그는 분위기어라 같은 제품이라고 겹친다는 보장이 없다.
        if ov or (known_q and r[10] and _product_same(known_q, r[10])):
            scored.append((ov, r))
    scored.sort(key=lambda x: (-x[0], -(x[1][6] or 0)))   # 겹침↓ → 댓글수↓(사장님 기준)

    # 판독 대상(head)을 고를 때, 이미 '같은 제품'으로 아는 것을 앞으로 당긴다.
    # 실측: [김밥] 질의에서 제품명이 그대로 '김밥'인 영상이 겹침1로 50등이라 상위30 밖이었다.
    if known_q:
        scored.sort(key=lambda x: (0 if (x[1][10] and _product_same(known_q, x[1][10])) else 1,
                                   -x[0], -(x[1][6] or 0)))

    # ── 제품명 검증(2026-08-04, 사장님 지시: "미리 돌리지 말고 검색 누를 때") ──
    # 태그 겹침만으로는 **같은 제품**이 안 나온다(실측: 제품명 완전일치 0건, '다이소 걸레'
    # → 냉장고정리용품, '천사점토' → 비즈스트랩. 분위기어 '살림꿀팁'이 15%를 차지해서다).
    # 그래서 겹침 상위 후보에만 AI를 태워 실제 제품명을 읽고, 같은 제품을 맨 위로 올린다.
    # 미리 14,000건을 돌지 않는 이유가 이것 — 볼 것만, 그때 판독하고 캐시한다.
    src_product = ""
    verified = set()
    if verify:
        try:
            from shopping_shorts import product_name as _pn
            # 30 → 60 (2026-08-04 사장님 승인). 30이면 실측에서 놓치는 게 나왔다:
            # [김밥] 질의에 제품명이 그대로 '김밥'인 53만회 영상이 50등이라 판독 대상 밖.
            # 검색이 15초 → 25초로 느려지지만 "빠른데 못 찾는" 것보다 낫다는 판단.
            # 캐시가 쌓이면 다시 빨라진다(판독된 건 재호출 없음).
            head = scored[:max(0, min(int(verify_n or 60), 120))]
            src_thumb = ""
            with store._conn() as c:
                row = c.execute("SELECT thumbnail FROM channel_archive WHERE shortcode=?",
                                (shortcode,)).fetchone()
                if row:
                    src_thumb = row[0] or ""
            if not src_thumb:      # 랭킹 영상은 아카이브에 없을 수 있다 → 최근 수집분에서
                src_thumb = _last_run_thumb(store, shortcode)
            targets = ([{"shortcode": shortcode, "thumbnail": src_thumb}]
                       + [{"shortcode": r[1], "thumbnail": r[3]} for _ov, r in head])
            pmap = _pn.identify_many(targets, DB_PATH)
            src_product = pmap.get(shortcode) or ""
            if src_product:
                # ★제품명 직접검색(2026-08-04 2차): 같은 제품 판정을 '태그 겹침 후보'
                # 안에서만 하지 않고 **아카이브 전체의 판독된 제품명**과 대조한다.
                # 종전 구조는 순환 구멍이었다 — 태그가 어긋나면(분위기어라 흔하다)
                # 후보에 못 들고 → 판독 대상도 아니고 → 제품명이 이미 캐시돼 있어도
                # 영영 안 나왔다. 사장님 제보 "있는 것 중에서 못 잡는다"의 뿌리.
                in_scored = {r[1] for _ov, r in scored}
                for r in rows:
                    if r[1] == shortcode or r[1] in in_scored:
                        continue
                    if r[10] and _pn.same_product(src_product, r[10]):
                        scored.append((0, r))   # 겹침0이지만 같은 제품 — 아래 정렬이 최상단으로
                # head 밖이라도 DB에 이미 제품명이 있으면 같은 제품인지 판정한다
                # (이번 회차에 판독한 것 + 예전에 판독해둔 것 = 전부 활용).
                verified = {r[1] for _ov, r in scored
                            if _pn.same_product(src_product,
                                                pmap.get(r[1]) or r[10] or "")}
                # 같은 제품이면 겹침과 무관하게 최상단(사장님 목적이 '같은 제품 모으기').
                scored.sort(key=lambda x: (0 if x[1][1] in verified else 1,
                                           -x[0], -(x[1][6] or 0)))
        except Exception:   # noqa: BLE001 — 판독 실패해도 기존 겹침 결과는 나가야 한다
            pass

    items = [
        {"username": r[0], "shortcode": r[1], "url": r[2], "thumbnail": r[3],
         "views": r[4], "likes": r[5], "comments": r[6], "posted_at": r[7],
         "overlap": ov, "same_product": r[1] in verified}
        for ov, r in scored[:max(1, min(limit, 100))]]
    # no_tags는 '태그도 없고 제품명도 못 읽음'일 때만. 제품명을 읽었는데 결과가 0이면
    # no_tags가 아니다 — 프론트가 '같은 제품이 아직 없다'는 정직한 안내를 하게 한다
    # (실사고: 냉장고 영상이 '스테인리스 냉장고'로 판독됐는데도 '판독 없음'으로 안내됨).
    return {"ok": True,
            "no_tags": (not src_t) and not src_product and not known_q and not items,
            "src_tags": sorted(src_t),
            "src_product": src_product, "verified_count": len(verified), "items": items}


def _product_same(a, b):
    """제품명 동일 판정 래퍼 — product_name 미로딩 상황에서도 라우트가 죽지 않게."""
    try:
        from shopping_shorts import product_name as _pn
        return _pn.same_product(a, b)
    except Exception:   # noqa: BLE001
        return False


def _last_run_thumb(store, shortcode):
    """최근 수집분(last_run)에서 썸네일 찾기 — 랭킹 영상은 아카이브에 없기 때문."""
    import json as _j
    try:
        with store._conn() as c:
            row = c.execute("SELECT items_json FROM last_run ORDER BY rowid DESC LIMIT 1").fetchone()
        for it in _j.loads(row[0]) if row else []:
            if it.get("shortcode") == shortcode:
                return it.get("thumbnail") or it.get("displayUrl") or ""
    except Exception:   # noqa: BLE001
        pass
    return ""

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
