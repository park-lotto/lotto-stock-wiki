"""Claude 영상 Buffer 예약 공개 주소 /api/share/f/{name} (관제 250, 2026-10-21).

못 박는 것:
  1. buffer_drop 의 mp4 를 GET·HEAD 로 내준다 — ★HEAD 404 면 Buffer 가 "Video could not be read" 로 거절한다.
  2. 이름 규칙(긴 무작위 [A-Za-z0-9_-] + .mp4) 밖이면 404 — 경로순회·짧은 추측 이름 봉인.
  3. 없는 파일은 404.
"""
import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as app_module

_NAME = "A" * 20 + "b-c_" * 3 + ".mp4"      # 32자 — tools/buffer_post.py 의 token_urlsafe(24) 와 같은 꼴


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "_BUFFER_DROP_DIR", tmp_path)
    (tmp_path / _NAME).write_bytes(b"\x00\x00\x00\x18ftypmp42fake")
    (tmp_path / "short.mp4").write_bytes(b"x")
    return TestClient(app_module.app)


def test_get_and_head_serve_mp4(client):
    g = client.get(f"/api/share/f/{_NAME}")
    assert g.status_code == 200 and g.headers["content-type"].startswith("video/mp4")
    assert g.content.endswith(b"fake")
    h = client.head(f"/api/share/f/{_NAME}")
    assert h.status_code == 200 and int(h.headers["content-length"]) == len(g.content)


@pytest.mark.parametrize("name", ["short.mp4", "..%2F..%2Fapp.py", "A" * 30 + ".txt",
                                  "B" * 32 + ".mp4"])     # 마지막 = 규칙엔 맞지만 파일 없음
def test_rejects_bad_or_missing(client, name):
    assert client.get(f"/api/share/f/{name}").status_code == 404
