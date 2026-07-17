"""썸네일 PNG 저장·선택. 파일명은 **서버가 부여**한다 — 클라이언트 이름을 믿지 않는다."""
import base64
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts.store import Store

# 유효한 최소 PNG(1x1)
_PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(app_module, "_THUMB_DIR", tmp_path / "thumbs")
    s = Store(tmp_path / "t.db")
    s.create_mix_job("j1", ["https://x/1"], 30, "template")
    return TestClient(app_module.app)


_META = json.dumps({"frame_ts": 4.7, "layers": [{"text": "강남언니", "x": 0.5, "y": 0.18}]})


def test_save_writes_png_and_records(client, tmp_path):
    r = client.post("/api/produce/thumb/save",
                    data={"job_id": "j1", "meta": _META},
                    files={"file": ("x.png", _PNG_1PX, "image/png")})
    assert r.status_code == 200
    name = r.json()["name"]
    assert (tmp_path / "thumbs" / "j1" / name).read_bytes() == _PNG_1PX
    thumb = Store(tmp_path / "t.db").get_mix_job("j1")["thumbnail"]
    assert thumb["results"] == [name]
    assert thumb["layers"][0]["text"] == "강남언니"   # meta가 함께 보존된다
    assert thumb["frame_ts"] == 4.7


def test_save_accumulates_gallery(client, tmp_path):
    for _ in range(3):
        client.post("/api/produce/thumb/save", data={"job_id": "j1", "meta": _META},
                    files={"file": ("x.png", _PNG_1PX, "image/png")})
    thumb = Store(tmp_path / "t.db").get_mix_job("j1")["thumbnail"]
    assert len(thumb["results"]) == 3
    assert len(set(thumb["results"])) == 3        # 서로 안 덮어쓴다


def test_save_ignores_client_filename(client, tmp_path):
    """'../../evil.png'을 보내도 서버 이름(thumb_N.png)으로만 떨어진다."""
    r = client.post("/api/produce/thumb/save",
                    data={"job_id": "j1", "meta": _META},
                    files={"file": ("../../evil.png", _PNG_1PX, "image/png")})
    assert r.status_code == 200
    assert r.json()["name"].startswith("thumb_")
    assert not (tmp_path / "evil.png").exists()
    assert not (tmp_path / "thumbs" / "evil.png").exists()


def test_save_rejects_non_png(client):
    r = client.post("/api/produce/thumb/save",
                    data={"job_id": "j1", "meta": _META},
                    files={"file": ("x.png", b"not a png at all", "image/png")})
    assert r.status_code == 400


def test_save_404_unknown_job(client):
    r = client.post("/api/produce/thumb/save",
                    data={"job_id": "nope", "meta": _META},
                    files={"file": ("x.png", _PNG_1PX, "image/png")})
    assert r.status_code == 404


def test_select_sets_selected(client, tmp_path):
    name = client.post("/api/produce/thumb/save", data={"job_id": "j1", "meta": _META},
                       files={"file": ("x.png", _PNG_1PX, "image/png")}).json()["name"]
    r = client.post("/api/produce/thumb/select", json={"job_id": "j1", "name": name})
    assert r.status_code == 200
    assert Store(tmp_path / "t.db").get_mix_job("j1")["thumbnail"]["selected"] == name


def test_select_rejects_unknown_name(client):
    """results에 없는 이름은 못 고른다 — 임의 문자열이 selected에 박히면 안 된다."""
    r = client.post("/api/produce/thumb/select", json={"job_id": "j1", "name": "../../etc/passwd"})
    assert r.status_code == 400


def test_save_meta_cannot_clobber_server_fields(client, tmp_path):
    """★frames·results·selected는 서버 소유다. 클라이언트 meta가 못 덮는다.

    meta를 통째로 thumb.update()하면 여기서 뚫린다 — 후보 프레임 목록이 날아가고
    고르지도 않은 썸네일이 selected로 박힌다.
    """
    s = Store(tmp_path / "t.db")
    s.update_mix_job("j1", thumbnail={"frames": [{"url": "/real/0.jpg", "ts": 1.0}],
                                      "results": [], "selected": None})
    evil = json.dumps({"frame_ts": 1.0, "layers": [],
                       "frames": [], "results": ["hacked.png"], "selected": "hacked.png"})
    client.post("/api/produce/thumb/save", data={"job_id": "j1", "meta": evil},
                files={"file": ("x.png", _PNG_1PX, "image/png")})
    thumb = Store(tmp_path / "t.db").get_mix_job("j1")["thumbnail"]
    assert thumb["frames"] == [{"url": "/real/0.jpg", "ts": 1.0}]   # 후보목록 보존
    assert thumb["results"] == ["thumb_1.png"]                      # 서버가 매긴 것만
    assert thumb["selected"] is None                                # 고른 적 없다
