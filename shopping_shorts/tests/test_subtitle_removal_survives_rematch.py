"""재매칭해도 자막제거 설정이 새 job에 따라가는가 (2026-07-30 사장님 제보).

제보: "3단계 자막제거를 하고 최종 렌더를 했는데 자막이 그대로다. 백본 바꾸고 대본 바꿔서
1단계부터 다시 한 거라 그런지 확인해달라."

서버 실측(라이브 DB):
    125c74e5abff | 07-30 03:34 | done | subtitle_removal=0 | clean_status=None  ← 그 영상
    9d03ee741492 | 07-30 02:34 | done | subtitle_removal=1 | clean_status=ready ← 그 전(정상)
자막제거를 아예 안 돌린 job이었다.

뿌리: 재매칭 = **새 job**인데 startProduceMix의 payload에 subtitle_removal이 없어 서버
기본값 False로 생성된다. 반면 브라우저 STATE.subtitleRemoval은 true로 남고 refreshSub()가
체크박스를 켜진 채 그린다 → 사장님은 이미 켜져 있으니 안 건드림 → onchange가 안 떠서
/api/produce/mix/settings가 한 번도 안 불림 → 화면은 "켜짐", job은 0.
렌더(mix_pipeline)는 job을 읽으므로 원본 자막이 그대로 남는다.

여기서 못 박는 것:
1. 서버가 subtitle_removal을 받아 job에 저장한다(켜짐/꺼짐 둘 다).
2. 프론트가 매칭 시작 payload에 그 값을 싣는다.
3. 3단계 화면(refreshSub)이 화면값을 job에 한 번 더 맞춘다(경로가 늘어나도 안 어긋나게).
"""
import pathlib
import re

from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts.store import Store

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
_U0 = "https://www.instagram.com/reel/AAA111/"
_U1 = "https://www.instagram.com/reel/BBB222/"


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    monkeypatch.setattr(app_module, "run_mix_job", lambda *a, **k: None)
    return TestClient(app_module.app), Store(db)


def _start(client, **extra):
    body = {"script": "확정 대본", "urls": [_U0, _U1], "target_seconds": 30,
            "scene_first": True, **extra}
    return client.post("/api/produce/mix/start", json=body)


def test_rematch_carries_subtitle_removal_on(monkeypatch, tmp_path):
    """★핵심: 자막제거 켠 채 1단계부터 다시 하면 새 job도 켜져 있어야 한다."""
    client, store = _client(monkeypatch, tmp_path)
    r = _start(client, subtitle_removal=True)
    assert r.status_code == 200
    assert store.get_mix_job(r.json()["job_id"])["subtitle_removal"] == 1


def test_rematch_carries_subtitle_removal_off(monkeypatch, tmp_path):
    """꺼둔 사람에게 몰래 유료 자막제거가 켜지면 안 된다(반대 방향 사고 방지)."""
    client, store = _client(monkeypatch, tmp_path)
    r = _start(client, subtitle_removal=False)
    assert store.get_mix_job(r.json()["job_id"])["subtitle_removal"] == 0


def test_absent_defaults_to_off(monkeypatch, tmp_path):
    """값을 안 보내는 옛 클라이언트는 종전대로 꺼짐(과금 없는 쪽이 안전 기본값)."""
    client, store = _client(monkeypatch, tmp_path)
    r = _start(client)
    assert store.get_mix_job(r.json()["job_id"])["subtitle_removal"] == 0


def test_settings_route_still_toggles(monkeypatch, tmp_path):
    """3단계 토글 경로(/api/produce/mix/settings)도 그대로 작동한다."""
    client, store = _client(monkeypatch, tmp_path)
    jid = _start(client, subtitle_removal=False).json()["job_id"]
    client.post("/api/produce/mix/settings", json={"job_id": jid, "subtitle_removal": True})
    assert store.get_mix_job(jid)["subtitle_removal"] == 1


def test_frontend_sends_subtitle_removal_on_match_start():
    """★뿌리 회귀 가드: 매칭 시작 payload에 subtitle_removal이 실려야 한다."""
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    start = src.index("async function startProduceMix(){")
    body = src[start:src.index("/api/produce/mix/start", start)]
    assert "subtitle_removal" in body, (
        "재매칭 payload에 subtitle_removal이 없다 — 새 job이 꺼진 채 생성돼 "
        "화면은 '켜짐'인데 렌더에 원본 자막이 남는다")


def test_refresh_sub_syncs_state_to_job():
    """3단계 화면이 화면값을 job에 맞춘다 — job 생성 경로가 늘어나도 안 어긋나게."""
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    start = src.index("function refreshSub(){")
    body = src[start:src.index("async function onSubToggle(){", start)]
    assert "/api/produce/mix/settings" in body
    assert "subtitle_removal" in body
