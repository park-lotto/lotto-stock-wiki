"""FastAPI: 수집 API + 정적 프론트 서빙."""
import hmac
import hashlib
import os
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from shopping_shorts.service import collect, generate_missing_drafts, next_draft_targets
from shopping_shorts.outreach import build_queue
from shopping_shorts.store import Store
from shopping_shorts.config import DB_PATH, DRAFT_BATCH_SIZE, PUBLIC_BASE_URL
from shopping_shorts.frame_extract import download_video, extract_frames
from shopping_shorts.video_analysis import analyze_video
from shopping_shorts.search_links import build_search_links, lens_search_url
from shopping_shorts.youtube_search import search as youtube_search_fn
from shopping_shorts.similarity import score_candidate

app = FastAPI(title="쇼핑쇼츠 레퍼런스 랭킹")


@app.post("/api/collect")
def api_collect(background_tasks: BackgroundTasks, limit: int | None = None):
    """지금 수집 버튼. limit=채널 수 상한(테스트용).

    댓글 draft 생성(항목당 Gemini 호출, 쿼터 걸리면 62초 대기)은 응답 후
    백그라운드로 넘긴다 — 랭킹 결과는 Apify 수집 즉시 반환, 소통 큐 draft는
    뒤이어 채워짐(2026-07-09, 443채널 전체수집이 draft생성 때문에 응답을
    막아버리던 문제 수정).

    Gemini 쿼터 절약을 위해 draft는 랭킹 상위 40개만 자동 생성한다(2026-07-09).
    나머지(또는 실패해서 draft 없는 상위권 항목)는 /api/generate_drafts 버튼으로
    필요할 때만 이어서 생성."""
    try:
        items = collect(limit_channels=limit)
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
def api_reference():
    """마지막 수집 결과 반환 (프론트 초기 로드용)."""
    items, collected_at = Store(DB_PATH).load_last_run()
    return {"ok": True, "items": items, "collected_at": collected_at}


@app.get("/api/outreach")
def api_outreach(sort: str = "latest", hide_done: bool = True, rank_limit: int = DRAFT_BATCH_SIZE):
    """소통 큐 반환 — 마지막 수집 릴스 + draft 결합, 정렬·완료필터.

    rank_limit: 레퍼런스랭킹(score) 상위 N개만 큐 후보로 노출(2026-07-09).
    기본 40 — 프론트가 "댓글 더 생성" 클릭 시 40씩 늘려서 재요청한다."""
    store = Store(DB_PATH)
    items, _ = store.load_last_run()
    drafts = store.drafts_map([i["shortcode"] for i in items])
    commented = store.commented_set()
    queue = build_queue(items, drafts_map=drafts, commented=commented,
                        sort=sort, hide_done=hide_done, rank_limit=rank_limit)
    return {"ok": True, "count": len(queue), "items": queue}


@app.post("/api/comment/done")
def api_comment_done(shortcode: str):
    """소통 완료 기록."""
    store = Store(DB_PATH)
    store.mark_commented(shortcode)
    return {"ok": True, "shortcode": shortcode}


@app.post("/api/save")
def api_save(shortcode: str):
    """제품찾기 소스로 담기 (기능 ③에서 재사용)."""
    store = Store(DB_PATH)
    store.mark_saved(shortcode)
    return {"ok": True, "shortcode": shortcode}


@app.get("/api/saved")
def api_saved():
    """담긴 shortcode 목록."""
    store = Store(DB_PATH)
    return {"ok": True, "saved": sorted(store.saved_set())}


_FIND_TMP_DIR = Path(__file__).parent / "data" / "find_frames"


@app.post("/api/find/analyze")
def api_find_analyze(shortcode: str):
    """영상 다운로드 → 프레임 추출 → Gemini 분석 → 검색링크 생성, 결과 저장 후 반환."""
    store = Store(DB_PATH)
    items, _ = store.load_last_run()
    item = next((i for i in items if i["shortcode"] == shortcode), None)
    if not item:
        return JSONResponse(status_code=404, content={"ok": False, "error": "해당 항목 없음"})

    work_dir = _FIND_TMP_DIR / hashlib.sha1(shortcode.encode()).hexdigest()[:16]
    video_path = download_video(item["video_url"], work_dir)
    frame_paths = extract_frames(video_path, work_dir, max_frames=6)
    analysis = analyze_video(video_path, item.get("caption", ""))

    frame_urls = [f"/api/find/frame/{work_dir.name}/{p.name}" for p in frame_paths]
    frame_abs_urls = [f"{PUBLIC_BASE_URL}{u}" for u in frame_urls]
    store.save_source_analysis(
        shortcode, keywords=analysis["keywords"],
        frame_paths=[str(p) for p in frame_paths],
        analyzed_at=datetime.now(timezone.utc).isoformat(),
    )
    return {
        "ok": True,
        "keywords": analysis["keywords"],
        "category": analysis["category"],
        "frame_urls": frame_urls,
        "search_links": build_search_links(analysis["keywords"]),
        "lens_links": [lens_search_url(u) for u in frame_abs_urls],
    }


@app.post("/api/find/collect")
def api_find_collect(shortcode: str, platform: str):
    """분석된 소스의 키워드로 다른 플랫폼을 실검색 → 후보 저장 → Gemini 유사도 채점."""
    store = Store(DB_PATH)
    analysis = store.get_source_analysis(shortcode)
    if not analysis:
        return JSONResponse(status_code=404, content={"ok": False, "error": "먼저 분석이 필요합니다"})
    if platform != "youtube":
        return JSONResponse(status_code=400, content={"ok": False, "error": f"'{platform}' 실수집은 아직 미지원"})

    keyword = (analysis["keywords"]["en"] or analysis["keywords"]["ko"] or [""])[0]
    if not keyword:
        return {"ok": True, "count": 0}
    raw = youtube_search_fn(keyword, max_results=10)
    ids = store.save_candidates(shortcode, "youtube", raw)

    frame_paths = analysis["frame_paths"]
    for cand_id, cand in zip(ids, raw):
        score = score_candidate(frame_paths, cand["thumbnail"])
        if score is not None:
            store.update_candidate_score(cand_id, score)
    return {"ok": True, "count": len(ids)}


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


@app.get("/api/thumb")
def api_thumb(url: str):
    """인스타 CDN 썸네일 프록시 (핫링크 차단 우회). url=원본 이미지 주소."""
    import requests
    from fastapi.responses import Response
    # 인스타 CDN 도메인만 허용 (SSRF 방지 — 임의 URL 프록시 금지)
    if not any(h in url for h in ("cdninstagram.com", "fbcdn.net")):
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


@app.get("/healthz")
def api_healthz():
    return {"ok": True}


# ── 로그인 게이트 (공유 계정, dashboard/server.py 패턴 포팅) ──
DASH_USER = os.environ.get("DASH_USER", "admin")
DASH_PASS = os.environ.get("DASH_PASS", "")  # 비어있으면 인증 OFF(로컬 개발)
DASH_SECRET = os.environ.get("DASH_SECRET", "shopping-shorts-local-secret")
_AUTH_ON = bool(DASH_PASS)
_AUTH_ALLOW = ("/login", "/api/login", "/favicon.ico", "/healthz")


def _auth_token() -> str:
    return hmac.new(DASH_SECRET.encode(), f"{DASH_USER}:{DASH_PASS}".encode(),
                     hashlib.sha256).hexdigest()


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
.err{color:#e74c3c;font-size:12px;text-align:center;margin-top:10px;min-height:14px}</style></head>
<body><form class=box method=post action=/api/login>
<h1>🛍️ 쇼핑쇼츠</h1>
<input name=user placeholder=아이디 autocomplete=username autofocus>
<input name=pass type=password placeholder=비밀번호 autocomplete=current-password>
<button>로그인</button>
<div class=err>__ERR__</div></form></body></html>"""


@app.get("/login", response_class=HTMLResponse)
def _login_page(e: str = ""):
    return _LOGIN_HTML.replace("__ERR__", "아이디 또는 비밀번호가 틀렸습니다" if e else "")


@app.post("/api/login")
async def _api_login(req: Request):
    body = (await req.body()).decode("utf-8", "ignore")
    form = urllib.parse.parse_qs(body)
    u = (form.get("user") or [""])[0]
    p = (form.get("pass") or [""])[0]
    if _AUTH_ON and hmac.compare_digest(u, DASH_USER) and hmac.compare_digest(p, DASH_PASS):
        r = RedirectResponse("/", status_code=303)
        r.set_cookie("dash_auth", _auth_token(), max_age=60 * 60 * 24 * 30,
                     httponly=True, samesite="lax")
        return r
    return RedirectResponse("/login?e=1", status_code=303)


@app.middleware("http")
async def _auth_guard(request: Request, call_next):
    if not _AUTH_ON:
        return await call_next(request)
    path = request.url.path
    if path in _AUTH_ALLOW or path.startswith("/static"):
        return await call_next(request)
    cookie = request.cookies.get("dash_auth")
    if cookie and hmac.compare_digest(cookie, _auth_token()):
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return RedirectResponse("/login")


# 정적 프론트 (마운트는 맨 마지막)
_STATIC = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(_STATIC), html=True), name="static")
