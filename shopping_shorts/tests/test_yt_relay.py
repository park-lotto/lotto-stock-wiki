"""유튜브 로컬 릴레이(2026-07-24) — 서버 데이터센터 IP 봇차단 우회.
큐 store · HTTP 엔드포인트 · 라우팅 스위치를 네트워크 없이 검증한다."""
import io
import tempfile
from pathlib import Path

from shopping_shorts.store import Store


def _store():
    return Store(Path(tempfile.mkdtemp()) / "r.db")


def test_queue_roundtrip():
    s = _store()
    rid = s.enqueue_yt_relay("https://youtu.be/abc")
    assert len(rid) == 16
    assert s.get_yt_relay(rid)["status"] == "pending"
    j = s.next_pending_yt_relay()
    assert j["req_id"] == rid and j["url"].endswith("abc")
    s.finish_yt_relay(rid, out_path="/tmp/x.mp4")
    assert s.get_yt_relay(rid) == {"status": "done", "out_path": "/tmp/x.mp4", "error": None}
    assert s.next_pending_yt_relay() is None       # done은 더 안 뽑힌다


def test_queue_failure():
    s = _store()
    rid = s.enqueue_yt_relay("https://youtu.be/z")
    s.finish_yt_relay(rid, error="blocked")
    assert s.get_yt_relay(rid)["status"] == "failed"
    assert s.get_yt_relay("missing") is None


def test_endpoints_auth_and_deliver():
    from fastapi.testclient import TestClient
    import shopping_shorts.app as A
    from shopping_shorts import config

    tmp = Path(tempfile.mkdtemp())
    A.DB_PATH = tmp / "r.db"
    config.YT_RELAY_KEY = "k"
    config.YT_RELAY_DIR = tmp / "relay"
    Store(A.DB_PATH)
    c = TestClient(A.app)

    assert c.get("/api/yt_relay/next", params={"key": "bad"}).status_code == 403
    assert c.get("/api/yt_relay/next", params={"key": "k"}).json()["job"] is None

    rid = Store(A.DB_PATH).enqueue_yt_relay("https://youtu.be/vid")
    assert c.get("/api/yt_relay/next", params={"key": "k"}).json()["job"]["req_id"] == rid

    r = c.post(f"/api/yt_relay/deliver/{rid}", data={"key": "k"},
               files={"file": ("v.mp4", io.BytesIO(b"MP4"), "video/mp4")})
    assert r.json()["status"] == "done"
    rec = Store(A.DB_PATH).get_yt_relay(rid)
    assert Path(rec["out_path"]).read_bytes() == b"MP4"

    rid2 = Store(A.DB_PATH).enqueue_yt_relay("https://youtu.be/z")
    assert c.post(f"/api/yt_relay/deliver/{rid2}", data={"key": "k", "error": "x"}).json()["status"] == "failed"
    assert c.post(f"/api/yt_relay/deliver/{rid}", data={"key": "y"}).status_code == 403


def test_relay_bypasses_login_guard():
    """로그인 가드(_auth_guard)가 켜져 있어도 /api/yt_relay/*는 자체 키 인증으로 통과.
    통과하면 401(로그인)이 아니라 403(키 불일치)이 나와야 한다 — 안 그러면 에이전트가 막힌다."""
    from fastapi.testclient import TestClient
    import shopping_shorts.app as A
    from shopping_shorts import config

    tmp = Path(tempfile.mkdtemp())
    A.DB_PATH = tmp / "r.db"
    config.YT_RELAY_KEY = "k"
    Store(A.DB_PATH)
    orig = A._AUTH_ON
    A._AUTH_ON = True                       # 유료게이트 ON 상황 재현
    try:
        c = TestClient(A.app)
        # 잘못된 키 → 로그인 가드(401)가 아니라 릴레이 자체 가드(403)
        assert c.get("/api/yt_relay/next", params={"key": "bad"}).status_code == 403
        # 로그인 필요한 다른 api는 여전히 401(가드 정상 동작 확인)
        assert c.get("/api/reference").status_code == 401
    finally:
        A._AUTH_ON = orig


def test_routing_switch():
    from shopping_shorts import config, media_download as m
    calls = []
    orig_relay, orig_ytdlp = m._download_via_relay, m._download_ytdlp
    m._download_via_relay = lambda u, d: (calls.append(("relay", u)), ("r", ""))[1]
    m._download_ytdlp = lambda u, d: (calls.append(("ytdlp", u)), ("y", ""))[1]
    try:
        config.YT_RELAY_ENABLED = True
        m.download_any("https://www.youtube.com/watch?v=x", "/t")   # 릴레이
        m.download_any("https://www.tiktok.com/@a/video/1", "/t")   # 서버서도 되니 직접
        config.YT_RELAY_ENABLED = False
        m.download_any("https://youtu.be/y", "/t")                  # 릴레이 꺼지면 직접
    finally:
        m._download_via_relay, m._download_ytdlp = orig_relay, orig_ytdlp
        config.YT_RELAY_ENABLED = False
    assert calls == [("relay", "https://www.youtube.com/watch?v=x"),
                     ("ytdlp", "https://www.tiktok.com/@a/video/1"),
                     ("ytdlp", "https://youtu.be/y")]
