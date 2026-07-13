"""FastAPI: 수집 API + 정적 프론트 서빙."""
import hmac
import hashlib
import os
import re
import shutil
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import requests
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from shopping_shorts.service import collect, generate_missing_drafts, next_draft_targets
from shopping_shorts.outreach import build_queue
from shopping_shorts.store import Store
from shopping_shorts.config import DB_PATH, DRAFT_BATCH_SIZE, PUBLIC_BASE_URL
from shopping_shorts.frame_extract import download_video, extract_frames, extract_frame_at
from shopping_shorts.script_extract import extract_script
from shopping_shorts.structure_analyze import analyze_structure
from shopping_shorts import script_generate
from shopping_shorts.apify_client import fetch_single_reel, fetch_reels, fetch_profiles
from shopping_shorts import discovery, instagram_search
from shopping_shorts.channels import load_channels
from shopping_shorts.video_analysis import analyze_video, translate_keyword
from shopping_shorts.product_identify import fetch_lens_lines, identify_product_from_lines
from shopping_shorts.search_links import build_search_links, lens_search_url
from shopping_shorts.mix_pipeline import run_mix_job, run_render, retype_mix_job, _source_video_id
from shopping_shorts import edit_plan as _edit_plan
import uuid

app = FastAPI(title="쇼핑쇼츠 레퍼런스 랭킹")

_MEDIA_CODE_RE = re.compile(r"/(?:p|reel|reels)/([A-Za-z0-9_-]+)")


def _media_code(url):
    """인스타 URL에서 미디어코드만 추출("/p/"·"/reel/"·"/reels/" 전부 대응, 쿼리
    파라미터 무시) — 사용자가 인스타에서 그대로 복사한 URL(추적파라미터·reel
    형식 포함)이 저장된 shortcode(우리가 만든 url 형식)와 문자열이 달라도
    같은 항목으로 매칭되게 함(2026-07-09, "해당 항목 없음" 오탐 수정)."""
    m = _MEDIA_CODE_RE.search(url or "")
    return m.group(1) if m else (url or "")


@app.post("/api/collect")
def api_collect(background_tasks: BackgroundTasks, limit: int | None = None, platform: str = "instagram"):
    """지금 수집 버튼. limit=채널 수 상한(테스트용). platform=플랫폼(기본 인스타).

    댓글 draft 생성(항목당 Gemini 호출, 쿼터 걸리면 62초 대기)은 응답 후
    백그라운드로 넘긴다 — 랭킹 결과는 Apify 수집 즉시 반환, 소통 큐 draft는
    뒤이어 채워짐(2026-07-09, 443채널 전체수집이 draft생성 때문에 응답을
    막아버리던 문제 수정).

    Gemini 쿼터 절약을 위해 draft는 랭킹 상위 40개만 자동 생성한다(2026-07-09).
    나머지(또는 실패해서 draft 없는 상위권 항목)는 /api/generate_drafts 버튼으로
    필요할 때만 이어서 생성.

    platform != "instagram"인 경우 댓글 draft/save_last_run(인스타 전용
    캐시)은 건너뛴다 — 유튜브 등은 _collect_youtube가 자체적으로 저장한다."""
    try:
        items = collect(platform=platform, limit_channels=limit)
        if platform != "instagram":
            _, collected_at = Store(DB_PATH).load_last_run_platform(platform)
            return {"ok": True, "count": len(items), "items": items,
                    "collected_at": collected_at}
        from datetime import datetime, timezone
        collected_at = datetime.now(timezone.utc).isoformat()
        store = Store(DB_PATH)
        store.save_last_run(items, collected_at)
        background_tasks.add_task(generate_missing_drafts, next_draft_targets(items, store))
        return {"ok": True, "count": len(items), "items": items,
                "collected_at": collected_at}
    except Exception as e:
        import re
        msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
        return JSONResponse(status_code=500, content={"ok": False, "error": msg})


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
    if platform == "instagram":
        items, collected_at = Store(DB_PATH).load_last_run()
    else:
        items, collected_at = Store(DB_PATH).load_last_run_platform(platform)
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
def api_mix_basket_toggle(request: Request, body: dict):
    """영상 믹싱 바구니 담기/담기취소 토글. body: {shortcode, url, thumbnail, name, caption}."""
    sc = (body.get("shortcode") or "").strip()
    if not sc:
        return JSONResponse(status_code=422, content={"ok": False, "error": "shortcode 필요"})
    store = Store(DB_PATH)
    cid = _cid(request)
    in_basket = store.mix_basket_toggle(
        sc,
        url=body.get("url") or "",
        thumbnail=body.get("thumbnail") or "",
        name=body.get("name") or "",
        caption=body.get("caption") or "",
        customer_id=cid,
    )
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

    store.save_script(code, result)
    return {"ok": True, "cached": False, **result}


@app.post("/api/wiki/save")
def api_wiki_save(request: Request, shortcode: str):
    """S급 대본을 위키(도서관)에 저장 — 대본 확보(캐시/즉석추출) → 구조분석 → 저장."""
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
        store.save_script(code, script)

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


@app.get("/api/wiki/list")
def api_wiki_list(request: Request):
    """위키(도서관)에 담은 S급 대본 전체."""
    return {"ok": True, "items": Store(DB_PATH).wiki_list(customer_id=_cid(request))}


@app.post("/api/wiki/remove")
def api_wiki_remove(request: Request, shortcode: str):
    """위키에서 제거."""
    Store(DB_PATH).remove_from_wiki(shortcode, customer_id=_cid(request))
    return {"ok": True, "shortcode": shortcode}


@app.post("/api/wiki/generate")
def api_wiki_generate(request: Request, shortcode: str, mode: str = "A", my_topic: str = "", keep: str = "", n: int = 3):
    """도서관 S급 1개의 구조를 빌려 새 20초 대본 초안 생성(모드 A/B, 유지/변형).

    keep: 유지할 요소 키를 콤마로(예: "characters,twist,development"). 나머지는 변형."""
    it = Store(DB_PATH).get_wiki_item(shortcode, customer_id=_cid(request))
    if not it:
        return JSONResponse(status_code=404, content={"ok": False, "error": "위키에 없는 항목 — 먼저 S급으로 저장하세요"})
    if not (it.get("structure") or it.get("full_text")):
        return JSONResponse(status_code=422, content={"ok": False, "error": "구조분석/대본이 비어 생성 불가 — 재저장 필요"})
    kept = {x for x in (keep or "").split(",") if x}
    keep_flags = {k: (k in kept) for k in script_generate.ELEM_KEYS}
    drafts = script_generate.generate_variations(
        it.get("structure") or {}, it.get("full_text") or "", keep_flags,
        mode=mode, my_topic=my_topic, n=n)
    if not drafts:
        return JSONResponse(status_code=502, content={"ok": False, "error": "생성 실패(Gemini 키 소진 또는 오류) — 잠시 후 재시도"})
    return {"ok": True, "drafts": drafts}


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


@app.get("/api/mix/status/{job_id}")
def api_mix_status(job_id: str):
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"ok": False, "error": "job 없음"})
    return {"ok": True, "status": job["status"], "error": job["error"]}


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
                      "tts_preview_url": f"/api/mix/tts/{job_id}/{b['beat_idx']}"})
    detected = plan.get("detected_type") or _edit_plan._DEFAULT_TYPE
    return {
        "ok": True, "structure": plan["structure"], "beats": beats,
        "detected_type": detected,
        "detected_type_label": _edit_plan.VIDEO_TYPES.get(detected, {}).get("label", detected),
        "affiliate_target": plan.get("affiliate_target", ""),
        "video_types": [{"key": k, "label": v["label"]} for k, v in _edit_plan.VIDEO_TYPES.items()],
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
            matched = True
            break
    if not matched:
        return JSONResponse(status_code=404, content={"ok": False, "error": "beat_idx 없음"})
    store.update_mix_job(job_id, edit_plan=plan)
    return {"ok": True}


@app.post("/api/mix/render")
def api_mix_render(background_tasks: BackgroundTasks, body: dict):
    job_id = body.get("job_id")
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job or not job.get("edit_plan"):
        return JSONResponse(status_code=404, content={"ok": False, "error": "렌더할 job 없음"})
    background_tasks.add_task(run_render, job_id, DB_PATH, _MIX_WORK_DIR)
    return {"ok": True}


@app.get("/api/mix/tts/{job_id}/{beat_idx}")
def api_mix_tts(job_id: str, beat_idx: int):
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job or not job.get("edit_plan"):
        return JSONResponse(status_code=404, content={"ok": False})
    for b in job["edit_plan"]["beats"]:
        if b["beat_idx"] == beat_idx and b.get("tts_path") and Path(b["tts_path"]).exists():
            return FileResponse(b["tts_path"])
    return JSONResponse(status_code=404, content={"ok": False})


@app.get("/api/mix/video/{job_id}")
def api_mix_video(job_id: str):
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job or not job.get("video_path") or not Path(job["video_path"]).exists():
        return JSONResponse(status_code=404, content={"ok": False})
    return FileResponse(job["video_path"])


@app.get("/api/thumb")
def api_thumb(url: str):
    """인스타 CDN 썸네일 프록시 (핫링크 차단 우회). url=원본 이미지 주소."""
    import requests
    from fastapi.responses import Response
    # 허용 CDN 도메인만 프록시 (SSRF 방지 — 임의 URL 프록시 금지).
    # 인스타 + 유튜브(ytimg) + 틱톡(tiktokcdn) 썸네일 호스트.
    _ALLOWED_THUMB_HOSTS = ("cdninstagram.com", "fbcdn.net", "ytimg.com",
                            "ggpht.com", "tiktokcdn.com", "tiktokcdn-us.com")
    if not any(h in url for h in _ALLOWED_THUMB_HOSTS):
        return Response(status_code=400, content=b"invalid host")
    try:
        r = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.instagram.com/",
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
    if not any(h in url for h in ("cdninstagram.com", "fbcdn.net")):
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


@app.get("/healthz")
def api_healthz():
    return {"ok": True}


# ── 로그인 게이트 (멀티테넌시, 2026-07-13 — 고객별 계정) ──
# 기존 단일 관리자 계정(DASH_USER/DASH_PASS)은 그대로 유지하고 LEGACY_CUSTOMER_ID(0)로
# 로그인되게 하위호환(기존 작업물 보존). 신규 고객은 customers 테이블(회원가입) 계정.
DASH_USER = os.environ.get("DASH_USER", "admin")
DASH_PASS = os.environ.get("DASH_PASS", "")  # 비어있으면 인증 OFF(로컬 개발)
DASH_SECRET = os.environ.get("DASH_SECRET", "shopping-shorts-local-secret")
_AUTH_ON = bool(DASH_PASS)
_AUTH_ALLOW = ("/login", "/api/login", "/signup", "/api/signup", "/favicon.ico", "/healthz",
               "/insta_fill_comment.user.js",
               # 유저스크립트(insta_fill_comment)가 인스타 탭에서 전송 감지 시 GM_xmlhttpRequest로
               # 완료기록을 POST한다. 인증쿠키 없이 오므로 허용. 마킹은 저위험(되돌리기 가능).
               "/api/comment/done")
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


# ── 영상제작 위저드(produce) ─────────────────────────────────
@app.post("/api/produce/script/gemini")
def api_produce_script_gemini(body: dict):
    """1단계 대본 · 제미니 자동 — 주제/제품으로 처음부터 대본 초안 N개 생성."""
    topic = (body.get("topic") or "").strip()
    if not topic:
        return JSONResponse(status_code=422, content={"ok": False, "error": "주제/제품을 입력하세요"})
    drafts = script_generate.generate_from_topic(
        topic, target_seconds=body.get("target_seconds") or 20, n=body.get("n") or 3)
    if not drafts:
        return JSONResponse(status_code=502,
                            content={"ok": False, "error": "생성 실패(키 소진 또는 응답 오류)"})
    return {"ok": True, "drafts": drafts}


@app.post("/api/produce/script/mix")
def api_produce_script_mix(request: Request, body: dict):
    """1단계 대본 · 우리믹스(Feature B) — 선택한 도서관 S급 대본들 강점 조합 → 새 대본."""
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


@app.post("/api/produce/mix/start")
def api_produce_mix_start(background_tasks: BackgroundTasks, body: dict):
    """2단계 영상믹스 — 확정 대본(given_script)을 소스영상 장면에 매칭하는 job 시작.
    리뷰·렌더는 기존 /api/mix/{status,result,adjust,render,video}를 그대로 쓴다.
    body: {script, urls, target_seconds, subtitle_removal}."""
    script = (body.get("script") or "").strip()
    urls = [u for u in (body.get("urls") or []) if u]
    if not script:
        return JSONResponse(status_code=422, content={"ok": False, "error": "확정 대본이 비어 있습니다(1단계)"})
    if len(urls) < 2:
        return JSONResponse(status_code=422, content={"ok": False, "error": "소스 영상 URL 2개 이상 필요"})
    target = int(body.get("target_seconds") or 30)
    subtitle_removal = bool(body.get("subtitle_removal", False))
    job_id = uuid.uuid4().hex[:12]
    Store(DB_PATH).create_mix_job(job_id, urls, target, "free",
                                  subtitle_removal=subtitle_removal, given_script=script)
    background_tasks.add_task(run_mix_job, job_id, DB_PATH, _MIX_WORK_DIR)
    return {"ok": True, "job_id": job_id}


# 정적 프론트 (마운트는 맨 마지막)
_STATIC = Path(__file__).parent / "static"

# 클린 URL — /library, /mix 등 확장자(.html) 없이 접근. (index는 루트 '/'로 자동)
# 기존 /xxx.html 경로도 아래 StaticFiles 마운트로 계속 동작(백워드 호환).
for _pg in ("discover", "find", "library", "mix", "outreach", "produce"):
    app.add_api_route(
        f"/{_pg}",
        (lambda n=_pg: FileResponse(_STATIC / f"{n}.html", media_type="text/html")),
        include_in_schema=False,
    )

app.mount("/", StaticFiles(directory=str(_STATIC), html=True), name="static")
