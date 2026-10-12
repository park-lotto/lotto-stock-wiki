"""🖼 내 이미지를 썸네일 후보로 직접 올린다(2026-09-16 회원 제보).

제보: 7단계 썸네일에서 **영상에서 추출만** 가능해, 미리 만들어 둔 이미지를 쓰거나
그 이미지를 영상 맨 앞에 넣을 방법이 없었다.

★올린 그림은 핀과 **같은 목록**(thumbnail.pins)에 들어간다 — 고르기·글자 얹기·
  [영상 맨 앞에 넣기]가 종전 경로 그대로 돈다(0순위-B).
"""
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from shopping_shorts import app as appmod
    monkeypatch.setattr(appmod, "_thumb_dir", lambda jid: (tmp_path / jid) if jid else None)
    return TestClient(appmod.app)


def _png_bytes(size=(400, 700), color=(10, 120, 200)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def _fake_job(monkeypatch, tmp_path, job_id="J1"):
    """Store를 건드리지 않고 job 하나가 있는 것처럼 만든다."""
    from shopping_shorts import app as appmod
    state = {"thumbnail": {}}

    class _S:
        def __init__(self, *a, **k):
            pass

        def get_mix_job(self, jid):
            return {"job_id": jid, "thumbnail": state["thumbnail"]} if jid == job_id else None

    monkeypatch.setattr(appmod, "Store", _S)
    monkeypatch.setattr(appmod, "_save_render_inputs",
                        lambda store, jid, **kw: state.update(kw))
    return state


def test_올린_이미지가_후보목록에_들어간다(client, tmp_path, monkeypatch):
    state = _fake_job(monkeypatch, tmp_path)
    r = client.post("/api/produce/thumb/upload",
                    data={"job_id": "J1"},
                    files={"file": ("내사진.png", _png_bytes(), "image/png")})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] is True
    assert d["name"].startswith("up_") and d["name"].endswith(".jpg")
    assert d["label"] == "🖼 내사진"
    # 핀 목록 맨 앞에 들어간다 = 방금 올린 것이 바로 눈에 보인다
    assert state["thumbnail"]["pins"][0]["name"] == d["name"]
    assert state["thumbnail"]["pins"][0]["uploaded"] is True
    # 실제 파일이 저장됐고, 열리는 JPEG이다
    saved = tmp_path / "J1" / d["name"]
    assert saved.is_file()
    assert Image.open(saved).format == "JPEG"


def test_같은_그림을_두번_올려도_후보가_안_쌓인다(client, tmp_path, monkeypatch):
    state = _fake_job(monkeypatch, tmp_path)
    data = _png_bytes()
    n1 = client.post("/api/produce/thumb/upload", data={"job_id": "J1"},
                     files={"file": ("a.png", data, "image/png")}).json()["name"]
    n2 = client.post("/api/produce/thumb/upload", data={"job_id": "J1"},
                     files={"file": ("a.png", data, "image/png")}).json()["name"]
    assert n1 == n2                                  # 이름 = 내용 해시
    assert len(state["thumbnail"]["pins"]) == 1


def test_이미지가_아니면_막는다(client, tmp_path, monkeypatch):
    _fake_job(monkeypatch, tmp_path)
    r = client.post("/api/produce/thumb/upload", data={"job_id": "J1"},
                    files={"file": ("나쁜파일.png", b"#!/bin/sh\necho hi\n", "image/png")})
    assert r.status_code == 400
    assert "이미지" in r.json()["error"]


def test_빈파일은_막는다(client, tmp_path, monkeypatch):
    _fake_job(monkeypatch, tmp_path)
    r = client.post("/api/produce/thumb/upload", data={"job_id": "J1"},
                    files={"file": ("x.png", b"", "image/png")})
    assert r.status_code == 400


def test_없는_job은_404(client, tmp_path, monkeypatch):
    _fake_job(monkeypatch, tmp_path)
    r = client.post("/api/produce/thumb/upload", data={"job_id": "NOPE"},
                    files={"file": ("x.png", _png_bytes(), "image/png")})
    assert r.status_code == 404
