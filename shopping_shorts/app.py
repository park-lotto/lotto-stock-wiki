"""FastAPI: 수집 API + 정적 프론트 서빙."""
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from shopping_shorts.service import collect
from shopping_shorts.outreach import build_queue
from shopping_shorts.store import Store
from shopping_shorts.config import DB_PATH

app = FastAPI(title="쇼핑쇼츠 레퍼런스 랭킹")

# 마지막 수집 결과 메모리 캐시 (수동 새로고침용)
_LAST = {"items": [], "collected_at": None}


@app.post("/api/collect")
def api_collect(limit: int | None = None):
    """지금 수집 버튼. limit=채널 수 상한(테스트용)."""
    try:
        items = collect(limit_channels=limit)
        from datetime import datetime, timezone
        _LAST["items"] = items
        _LAST["collected_at"] = datetime.now(timezone.utc).isoformat()
        return {"ok": True, "count": len(items), "items": items,
                "collected_at": _LAST["collected_at"]}
    except Exception as e:
        import re
        msg = re.sub(r"(token=|Bearer\s+)[^\s&\"']+", r"\1***", str(e))
        return JSONResponse(status_code=500, content={"ok": False, "error": msg})


@app.get("/api/reference")
def api_reference():
    """마지막 수집 결과 반환 (프론트 초기 로드용)."""
    return {"ok": True, "items": _LAST["items"], "collected_at": _LAST["collected_at"]}


@app.get("/api/outreach")
def api_outreach(sort: str = "latest", hide_done: bool = True):
    """소통 큐 반환 — 마지막 수집 릴스 + draft 결합, 정렬·완료필터."""
    store = Store(DB_PATH)
    items = _LAST["items"]
    drafts = store.drafts_map([i["shortcode"] for i in items])
    commented = store.commented_set()
    queue = build_queue(items, drafts_map=drafts, commented=commented,
                        sort=sort, hide_done=hide_done)
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


# 정적 프론트 (마운트는 맨 마지막)
_STATIC = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(_STATIC), html=True), name="static")
