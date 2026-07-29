"""P0 보안·비용 결함 회귀테스트 (2026-07-17 코드점검 지시서).

각 테스트는 "고치기 전이었다면 반드시 실패했을" 시나리오를 고정한다.
  P0-1 DASH_SECRET 하드코딩 → 세션쿠키 위조로 인증 전면 우회
  P0-2 썸네일·영상 프록시 SSRF(부분문자열 매칭) → 메타데이터 크리덴셜 탈취
  P0-5 최종 렌더 중복예약 → VMake 유료 이중과금
  P0-6 Apify run 실패가 전 토큰으로 전파 → 유료 run 반복 청구
"""
import importlib

import pytest
import requests
from fastapi.testclient import TestClient

from shopping_shorts import apify_client
from shopping_shorts import app as app_module
from shopping_shorts.store import Store


# ── P0-1. 세션 시크릿 ──────────────────────────────────────────────

def test_dash_secret_has_no_hardcoded_default(monkeypatch, tmp_path):
    """DASH_SECRET env가 없어도 소스에 박힌 공개 기본값을 쓰면 안 된다.

    예전 기본값("shopping-shorts-local-secret")은 소스에 공개돼 있어, 운영에서
    DASH_PASS만 넣고 DASH_SECRET을 빠뜨리면 누구나 쿠키를 위조해 관리자(cid=0)를
    사칭할 수 있었다.
    """
    monkeypatch.delenv("DASH_SECRET", raising=False)
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "data" / "t.db")
    secret = app_module._load_dash_secret()
    assert secret != "shopping-shorts-local-secret"
    assert len(secret) >= 32


def test_dash_secret_persists_across_restarts(monkeypatch, tmp_path):
    """생성한 시크릿은 영속화돼야 한다 — 아니면 재기동마다 전원 로그아웃된다."""
    monkeypatch.delenv("DASH_SECRET", raising=False)
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "data" / "t.db")
    assert app_module._load_dash_secret() == app_module._load_dash_secret()


def test_dash_secret_env_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("DASH_SECRET", "env-provided-secret")
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "data" / "t.db")
    assert app_module._load_dash_secret() == "env-provided-secret"


# ── P0-2. 프록시 SSRF ──────────────────────────────────────────────

_METADATA_ATTACK = "http://169.254.169.254/latest/meta-data/iam/security-credentials/?x=cdninstagram.com"


@pytest.mark.parametrize("url", [
    _METADATA_ATTACK,                                   # 쿼리스트링에 허용호스트 심기
    "http://127.0.0.1:8849/admin?cdninstagram.com",     # 루프백
    "http://10.0.0.5/x#cdninstagram.com",               # 사설망 + 프래그먼트
    "http://evil.com/cdninstagram.com/a.jpg",           # 경로에 허용호스트 심기
    "http://cdninstagram.com.evil.com/a.jpg",           # 접미사 사칭
    "file:///etc/passwd",                               # 비 http(s)
])
def test_cdn_proxy_rejects_ssrf_and_spoofed_hosts(url):
    """부분문자열 매칭(`h in url`)이었다면 전부 통과했을 URL들."""
    assert app_module._reject_cdn_proxy(url, app_module._ALLOWED_THUMB_HOSTS) is True


@pytest.mark.parametrize("url", [
    "https://scontent.cdninstagram.com/v/t51/a.jpg",    # 서브도메인
    "https://cdninstagram.com/a.jpg",                   # 정확일치
    "https://i.ytimg.com/vi/abc/hq.jpg",
])
def test_cdn_proxy_allows_real_cdn_hosts(monkeypatch, url):
    """정상 CDN은 계속 통과해야 한다(가드가 기능을 깨면 안 됨).
    내부망 판정은 DNS를 타므로 테스트에선 공인 IP로 고정한다."""
    monkeypatch.setattr(app_module.socket, "gethostbyname", lambda h: "93.184.216.34")
    assert app_module._reject_cdn_proxy(url, app_module._ALLOWED_THUMB_HOSTS) is False


def test_thumb_route_rejects_metadata_url(monkeypatch, tmp_path):
    """라우트 레벨 실요청 — 400이어야 하고, 서버가 메타데이터로 GET을 보내면 안 된다."""
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "t.db")

    def _boom(*a, **k):                      # 프록시가 실제로 나가면 테스트 실패
        raise AssertionError("차단됐어야 할 URL로 요청이 나갔다")

    monkeypatch.setattr(app_module.requests, "get", _boom)
    r = TestClient(app_module.app).get("/api/thumb", params={"url": _METADATA_ATTACK})
    assert r.status_code == 400


def test_video_route_rejects_metadata_url(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "t.db")

    def _boom(*a, **k):
        raise AssertionError("차단됐어야 할 URL로 요청이 나갔다")

    monkeypatch.setattr(app_module.requests, "get", _boom)
    r = TestClient(app_module.app).get("/api/video", params={"url": _METADATA_ATTACK})
    assert r.status_code == 400


# ── P0-3. 다운로드 라우트 SSRF 가드 확산 ────────────────────────────

_INTERNAL = "http://169.254.169.254/latest/meta-data/"


@pytest.mark.parametrize("path,payload", [
    ("/api/mix/start",
     {"urls": [_INTERNAL, "http://127.0.0.1/x.mp4"], "target_seconds": 20, "structure": "free"}),
    ("/api/produce/mix/start",
     {"script": "대본", "urls": [_INTERNAL], "target_seconds": 20}),
    ("/api/produce/extract_from_url", {"url": _INTERNAL}),
    ("/api/produce/save_to_wiki", {"url": _INTERNAL}),
])
def test_download_routes_reject_internal_urls(monkeypatch, tmp_path, path, payload):
    """이 라우트들은 받은 URL을 download_any/download_video로 그대로 fetch한다.
    _reject_ssrf가 scene/save/prepare 한 곳에만 걸려 있어 전부 무방비였다(P0-3)."""
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(app_module, "run_mix_job", lambda *a, **k: None)
    r = TestClient(app_module.app).post(path, json=payload)
    assert r.status_code == 422, f"{path} 가 내부망 URL을 통과시켰다"


def test_save_to_wiki_checks_video_url_too(monkeypatch, tmp_path):
    """download_any는 video_url이 오면 그걸 우선 쓴다 — url만 검사하면 우회된다."""
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "t.db")
    r = TestClient(app_module.app).post("/api/produce/save_to_wiki", json={
        "url": "https://www.instagram.com/reel/AAA111/", "video_url": _INTERNAL})
    assert r.status_code == 422


# ── P0-5. 최종 렌더 중복예약 ────────────────────────────────────────

def _mix_client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    store = Store(db)

    # 2026-07-29 독립워커 전환: app.py는 이제 run_render를 직접 예약하지 않고
    # Store(DB_PATH).enqueue("render", {"job_id": job_id})로 큐에 넣는다(실행은
    # 별도 워커 프로세스). '예약됐는가'는 job_queue의 render 항목 수로 센다 —
    # 검증하는 계약(더블클릭해도 한 번만)은 그대로다.
    class _Scheduled:
        def __len__(self):
            with store._conn() as c:
                return c.execute(
                    "SELECT COUNT(*) FROM job_queue WHERE task='render'"
                ).fetchone()[0]

        def __bool__(self):
            return len(self) > 0

        def __eq__(self, other):
            if other == []:
                return len(self) == 0
            return NotImplemented

        def __repr__(self):
            return f"<render queue count={len(self)}>"

    return TestClient(app_module.app), store, _Scheduled()


def _ready_job(store, job_id="jr"):
    store.create_mix_job(job_id, ["u0"], 20, "free")
    store.update_mix_job(job_id, status="ready_for_review", edit_plan={
        "structure": "free",
        "beats": [{"beat_idx": 0, "role": "훅", "narration": "n", "target_seconds": 2,
                   "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0},
                   "alternates": [], "effect": "cut"}],
        "plagiarism_flags": []})
    return job_id


def test_render_double_click_schedules_only_once(monkeypatch, tmp_path):
    """더블클릭 = run_render 2개 → 같은 final.mp4에 ffmpeg 둘이 쓰고 VMake 유료 호출도 2회.
    첫 요청이 동기적으로 status='rendering'을 선기록하므로 두 번째는 예약되면 안 된다."""
    client, store, scheduled = _mix_client(monkeypatch, tmp_path)
    jid = _ready_job(store)

    assert client.post("/api/mix/render", json={"job_id": jid}).status_code == 200
    assert store.get_mix_job(jid)["status"] == "rendering"   # 응답 시점에 이미 기록됨
    client.post("/api/mix/render", json={"job_id": jid})     # 더블클릭

    assert len(scheduled) == 1, "두 번째 렌더가 예약됐다 — 유료 이중과금 위험"


def test_render_blocked_while_removing_subtitles(monkeypatch, tmp_path):
    """removing_subtitles = VMake 유료 단계 진행 중. 여기서 재예약되면 그 돈이 두 번 나간다."""
    client, store, scheduled = _mix_client(monkeypatch, tmp_path)
    jid = _ready_job(store, "jv")
    store.update_mix_job(jid, status="removing_subtitles")

    client.post("/api/mix/render", json={"job_id": jid})
    assert scheduled == []


def test_render_allowed_again_when_stale(monkeypatch, tmp_path):
    """서버 재시작으로 죽은 렌더의 'rendering' 잔해가 job을 영구 잠그면 안 된다."""
    client, store, scheduled = _mix_client(monkeypatch, tmp_path)
    jid = _ready_job(store, "js")
    store.update_mix_job(jid, status="rendering")
    monkeypatch.setattr(app_module, "_render_is_stale", lambda job: True)

    client.post("/api/mix/render", json={"job_id": jid})
    assert len(scheduled) == 1, "stale 잔해인데도 재예약이 막혔다 — job 영구 잠김"


# ── P0-6. Apify 유료 run 반복 ───────────────────────────────────────

class _Resp:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = {} if json_data is None else json_data

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"{self.status_code} error")
            err.response = self
            raise err


def test_run_failure_does_not_burn_every_token(monkeypatch):
    """액터 스키마 변경처럼 토큰 무관한 원인으로 run이 FAILED일 때, 토큰 30개를
    전부 돌면 유료 run이 30번 청구된다. 재시도는 제한돼야 한다."""
    tokens = [f"tok{i}" for i in range(30)]
    started = []

    def fake_post(url, headers=None, json=None, timeout=None):
        if url.endswith("/abort"):
            return _Resp(200, {})
        started.append(headers["Authorization"])
        return _Resp(200, {"data": {"id": "r", "status": "FAILED"}})

    monkeypatch.setattr(apify_client.requests, "post", fake_post)
    monkeypatch.setattr(apify_client, "_save_key_index", lambda i: None)
    monkeypatch.setattr(apify_client, "_load_key_index", lambda: 0)

    with pytest.raises(apify_client.ApifyRunFailed):
        apify_client._run_with_rotation({}, tokens, timeout=5, poll_interval=0.01)

    assert len(started) <= apify_client._MAX_RUN_FAILURE_ROTATIONS + 1, (
        f"유료 run이 {len(started)}번 시작됐다 — 실패 전파로 비용 폭주")


def test_mid_run_exhaustion_still_rotates_once(monkeypatch):
    """단, 2026-07-09 실사고(실행 도중 계정 소진)는 계속 복구돼야 한다 —
    첫 토큰의 run이 죽으면 다음 토큰으로 한 번은 재시도한다."""
    def fake_post(url, headers=None, json=None, timeout=None):
        if url.endswith("/abort"):
            return _Resp(200, {})
        if headers["Authorization"].endswith("tok1"):
            return _Resp(200, {"data": {"id": "r1", "status": "FAILED"}})
        return _Resp(200, {"data": {"id": "r2", "status": "SUCCEEDED",
                                    "defaultDatasetId": "ds2"}})

    monkeypatch.setattr(apify_client.requests, "post", fake_post)
    monkeypatch.setattr(apify_client.requests, "get",
                        lambda url, headers=None, timeout=None: _Resp(200, [{"id": "ok"}]))
    monkeypatch.setattr(apify_client, "_save_key_index", lambda i: None)
    monkeypatch.setattr(apify_client, "_load_key_index", lambda: 0)

    items = apify_client._run_with_rotation({}, ["tok1", "tok2"], timeout=5, poll_interval=0.01)
    assert items == [{"id": "ok"}]


def test_timeout_aborts_run_before_rotating(monkeypatch):
    """타임아웃 시 기존 run을 abort 안 하면, 그 run은 계속 돌며 과금되는데
    그 위에 새 run을 또 띄운다 = 이중 과금."""
    aborted = []

    def fake_post(url, headers=None, json=None, timeout=None):
        if url.endswith("/abort"):
            aborted.append(url)
            return _Resp(200, {})
        return _Resp(200, {"data": {"id": "runX", "status": "RUNNING"}})

    monkeypatch.setattr(apify_client.requests, "post", fake_post)
    monkeypatch.setattr(apify_client.requests, "get",
                        lambda url, headers=None, timeout=None:
                        _Resp(200, {"data": {"id": "runX", "status": "RUNNING"}}))

    with pytest.raises(TimeoutError):
        apify_client._run_to_completion({"Authorization": "Bearer t"},
                                        {"id": "runX", "status": "RUNNING"},
                                        timeout=0, poll_interval=0.01)
    assert aborted, "타임아웃인데 run을 abort하지 않았다 — 이중 과금"
