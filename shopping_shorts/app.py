"""FastAPI: 수집 API + 정적 프론트 서빙."""
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from shopping_shorts.service import collect

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
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@app.get("/api/reference")
def api_reference():
    """마지막 수집 결과 반환 (프론트 초기 로드용)."""
    return {"ok": True, "items": _LAST["items"], "collected_at": _LAST["collected_at"]}


# 정적 프론트 (마운트는 맨 마지막)
_STATIC = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(_STATIC), html=True), name="static")
