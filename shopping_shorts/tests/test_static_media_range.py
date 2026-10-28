"""정적 미디어(/landing/*.mp4 등)도 Range(부분 요청)를 받아야 되감기가 된다 — 2026-09-27 사장님
"영상 플레이하고 뒤로 이동이 안 먹힌다"(/landing/vertex_guide.mp4). 서버 starlette 0.36.3의 FileResponse는
Range를 무시하고 200 전체를 준다 → 정적 마운트도 _range_media_response를 거쳐야 한다(로컬 starlette는 신버전이라
그냥 두면 우연히 통과하므로, 그 함수를 실제로 타는지까지 본다)."""
from fastapi.testclient import TestClient
from shopping_shorts import app as module


def test_static_mp4_goes_through_range_helper(monkeypatch):
    calls = []
    real = module._range_media_response

    def spy(path, request, media_type="video/mp4"):
        calls.append((str(path), media_type))
        return real(path, request, media_type)

    monkeypatch.setattr(module, "_range_media_response", spy)
    c = TestClient(module.app)
    r = c.get("/landing/vertex_guide.mp4", headers={"Range": "bytes=1000-1999"})
    assert calls and calls[0][1] == "video/mp4", calls
    assert r.status_code == 206
    assert r.headers["content-range"].startswith("bytes 1000-1999/")
    assert len(r.content) == 1000


def test_static_html_unchanged():
    c = TestClient(module.app)
    r = c.get("/api_manual.html")
    assert r.status_code == 200
    assert "no-cache" in r.headers.get("cache-control", "")
