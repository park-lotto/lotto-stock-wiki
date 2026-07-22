"""제작소 믹스 시작 시 사장님이 고른 ⭐메인(백본) 인덱스가 job에 저장되는지.
잘못된 인덱스는 None으로 흘려 job을 죽이지 않는다(자동 선정)."""
from fastapi.testclient import TestClient
from shopping_shorts import app as app_module
from shopping_shorts.store import Store

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


def test_backbone_main_saved_on_job(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    r = _start(client, backbone_main=1)
    assert r.status_code == 200
    assert store.get_mix_job(r.json()["job_id"])["backbone_main"] == 1


def test_backbone_main_absent_is_none(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    r = _start(client)                       # 지정 없음 → 자동 선정
    assert store.get_mix_job(r.json()["job_id"])["backbone_main"] is None


def test_backbone_main_out_of_range_ignored(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    r = _start(client, backbone_main=9)      # urls 2개인데 9 → 무시(None)
    assert r.status_code == 200
    assert store.get_mix_job(r.json()["job_id"])["backbone_main"] is None
