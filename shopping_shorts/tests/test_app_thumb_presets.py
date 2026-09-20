"""🖼 내 썸네일 프리셋(2026-09-02) — 만든 구성을 담아 다음 영상에 그대로 얹는다.

여기서 지키는 것(전부 실제로 요청을 보내 확인한다 — 문자열 검색은 증거가 아니다):
  · 담기→목록→그림→이름변경→삭제 왕복
  · **배경을 안 담는다** — 프리셋은 다른 영상에 쓰는 것이라 그 영상 배경 위에 얹혀야 한다
  · 남의 계정 프리셋은 보이지도, 고쳐지지도, 지워지지도 않는다(멀티테넌시)
  · 지우면 그림 파일도 같이 치운다 — 안 하면 안 쓰이는 PNG가 영원히 쌓인다
  · 파일명은 **서버가** 부여한다(경로순회 차단) — test_app_thumb_save와 같은 관례
"""
import base64
import json

import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts.store import Store

_PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

_LAYERS = [
    {"kind": "sticker", "emoji": "🔥", "size": 18, "x": 0.5, "y": 0.7},
    {"text": "이것만 있으면 끝", "size": 90, "color": "#ffffff",
     "box": {"color": "#000000", "pad": 16, "opacity": 80}},
]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(app_module, "_THUMB_PRESET_DIR", tmp_path / "tp")
    Store(tmp_path / "t.db")
    return TestClient(app_module.app)


def _add(client, name="내 스타일", layers=None, png=_PNG_1PX):
    files = {"file": ("x.png", png, "image/png")} if png else None
    return client.post("/api/produce/thumb/presets",
                       data={"name": name,
                             "layers": json.dumps(layers if layers is not None else _LAYERS)},
                       files=files)


def test_담기_목록_그림_이름변경_삭제_왕복(client, tmp_path):
    r = _add(client)
    assert r.status_code == 200 and r.json()["ok"], r.text
    p = r.json()["preset"]
    pid, url = p["preset_id"], p["url"]
    assert p["layers"] == _LAYERS          # 구성이 그대로 돌아온다

    lst = client.get("/api/produce/thumb/presets").json()["presets"]
    assert [x["preset_id"] for x in lst] == [pid]
    assert lst[0]["layers"] == _LAYERS

    assert client.get(url).status_code == 200          # 카드 그림이 서빙된다

    assert client.post(f"/api/produce/thumb/presets/{pid}/rename",
                       json={"name": "새이름"}).json() == {"ok": True, "name": "새이름"}
    assert client.get("/api/produce/thumb/presets").json()["presets"][0]["name"] == "새이름"

    assert client.delete(f"/api/produce/thumb/presets/{pid}").json()["ok"] is True
    assert client.get("/api/produce/thumb/presets").json()["presets"] == []
    # ★그림도 같이 치운다 — 안 지우면 안 쓰이는 PNG가 영원히 쌓인다
    assert client.get(url).status_code == 404


def test_파일명은_서버가_부여한다(client):
    """클라이언트가 준 이름을 그대로 쓰면 경로순회 재료가 된다(save 라우트와 같은 규약)."""
    r = client.post("/api/produce/thumb/presets",
                    data={"name": "n", "layers": json.dumps(_LAYERS)},
                    files={"file": ("../../evil.png", _PNG_1PX, "image/png")})
    url = r.json()["preset"]["url"]
    assert "evil" not in url and ".." not in url
    assert url.startswith("/api/produce/thumb/preset-image/tp_")


def test_배경은_담지_않는다(client):
    """★프리셋은 **다른 영상**에 쓴다 — 배경까지 담으면 남의 영상 장면이 딸려온다.

    응답·목록 어디에도 배경 키(frame_ts·frame_url)가 없어야 한다."""
    p = _add(client).json()["preset"]
    got = client.get("/api/produce/thumb/presets").json()["presets"][0]
    for key in ("frame_ts", "frame_url", "img"):
        assert key not in p and key not in got


def test_남의_프리셋은_안_보이고_못_고치고_못_지운다(client, tmp_path):
    """멀티테넌시 — customer_id를 WHERE에 끼우는 규약이 실제로 지켜지는가."""
    Store(tmp_path / "t.db").add_thumb_preset(
        "tp_other", "남의것", [{"text": "x"}], customer_id=999)

    assert client.get("/api/produce/thumb/presets").json()["presets"] == []
    assert client.post("/api/produce/thumb/presets/tp_other/rename",
                       json={"name": "z"}).status_code == 404
    assert client.delete("/api/produce/thumb/presets/tp_other").status_code == 404
    # 남의 것은 멀쩡히 살아 있어야 한다(404를 냈다고 지워버리면 안 된다)
    assert Store(tmp_path / "t.db").get_thumb_preset(
        "tp_other", customer_id=999)["name"] == "남의것"


@pytest.mark.parametrize("layers,why", [
    ("[]", "빈 배열 — 담을 것이 없다"),
    ('{"a":1}', "dict — 불러올 때 프런트가 layers.map에서 죽는다"),
    ("{{{", "깨진 json"),
])
def test_잘못된_layers는_거부(client, layers, why):
    assert client.post("/api/produce/thumb/presets",
                       data={"name": "n", "layers": layers}).status_code == 400, why


def test_빈_이름과_PNG아닌_파일은_거부(client):
    assert _add(client, name="   ").status_code == 400
    assert _add(client, png=b"NOTAPNG").status_code == 400


def test_그림_없이도_담긴다(client):
    """그림은 카드 장식일 뿐 — 없으면 url=None인 카드로 뜬다(담기 자체는 성공)."""
    r = _add(client, png=None)
    assert r.status_code == 200 and r.json()["preset"]["url"] is None


def test_상한을_넘기면_안내와_함께_거부(client, tmp_path):
    s = Store(tmp_path / "t.db")
    for i in range(app_module._THUMB_PRESET_MAX):
        s.add_thumb_preset(f"c{i}", f"n{i}", [{"text": "a"}], customer_id=0)
    r = _add(client)
    assert r.status_code == 400 and str(app_module._THUMB_PRESET_MAX) in r.json()["error"]


def test_없는_그림은_404(client):
    assert client.get("/api/produce/thumb/preset-image/nope.png").status_code == 404
