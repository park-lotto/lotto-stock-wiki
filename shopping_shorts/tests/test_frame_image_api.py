"""이미지 틀 업로드 API — 캔바 그림을 그대로 등록하는 경로(2026-08-31).

★계약:
  1. 알파(투명)가 살아야 한다 — JPEG로 굳히면 가운데가 검게 막혀 영상을 가린다
  2. id는 **저장한 그림의 내용해시** — 같은 그림은 한 번만 쌓이고, 바뀌면 id가 갈린다
  3. 삭제는 목록에서만 뺀다 — 파일을 지우면 같은 그림을 쓰는 남의 작업이 깨진다
  4. 그림이 아닌 파일·너무 큰 파일은 422/413으로 돌려준다(500 금지)
"""
import io

import pytest
from PIL import Image

from shopping_shorts import deco_frame as df


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from shopping_shorts import app as app_mod
    monkeypatch.setattr(df, "_BG_DIR", tmp_path)
    return TestClient(app_mod.app)


def _png(size=(1080, 1920), alpha_hole=True):
    im = Image.new("RGBA", size, (10, 20, 30, 255))
    if alpha_hole:
        im.paste((0, 0, 0, 0), (0, 400, size[0], size[1]))   # 아래쪽 투명(영상 자리)
    b = io.BytesIO()
    im.save(b, format="PNG")
    return b.getvalue()


def test_upload_keeps_transparency_and_returns_id(client, tmp_path):
    r = client.post("/api/produce/frame/image",
                    files={"file": ("canva.png", _png(), "image/png")})
    assert r.status_code == 200, r.text
    iid = r.json()["id"]
    assert df.bg_image_path(iid), "저장된 파일을 못 찾는다"
    with Image.open(df.bg_image_path(iid)) as im:
        assert im.mode == "RGBA"
        assert im.size == (df.W, df.H), "출력 규격으로 맞춰 저장해야 한다"
        assert im.getpixel((540, 1500))[3] == 0, "투명이 굳으면 영상이 가려진다"


def test_same_image_twice_is_one_entry(client):
    raw = _png()
    a = client.post("/api/produce/frame/image", files={"file": ("a.png", raw, "image/png")}).json()
    b = client.post("/api/produce/frame/image", files={"file": ("b.png", raw, "image/png")}).json()
    assert a["id"] == b["id"], "같은 그림인데 id가 다르다"
    ids = [x["id"] for x in client.get("/api/produce/frame/images").json()["images"]]
    assert ids.count(a["id"]) == 1, "같은 그림이 목록에 두 번 쌓였다"


def test_delete_removes_from_list_but_keeps_file(client):
    iid = client.post("/api/produce/frame/image",
                      files={"file": ("a.png", _png(), "image/png")}).json()["id"]
    assert client.delete(f"/api/produce/frame/image/{iid}").status_code == 200
    assert client.get("/api/produce/frame/images").json()["images"] == []
    assert df.bg_image_path(iid), "★파일까지 지우면 같은 그림을 쓰는 남의 작업이 깨진다"


def test_bad_files_are_refused_not_crashed(client):
    r = client.post("/api/produce/frame/image",
                    files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 422 and r.json()["ok"] is False
    r = client.post("/api/produce/frame/image",
                    files={"file": ("x.png", b"not a png", "image/png")})
    assert r.status_code == 422 and r.json()["ok"] is False


def test_serving_rejects_bogus_id(client):
    assert client.get("/api/produce/frame/image/../../app.py").status_code == 404
    assert client.get("/api/produce/frame/image/zzzz").status_code == 404


# ── 쿼리 참/거짓 (2026-08-31 실사고) ─────────────────────────────────────────
def test_every_boolean_field_survives_the_query_string(client):
    """★"0"은 파이썬에서 **참**이다. 참/거짓 칸 이름을 손으로 나열하면 값이 늘 때
    반드시 하나가 빠지고, 그 칸은 조용히 늘 켜진 상태가 된다(head_block이 그랬다).
    그래서 DEFAULTS의 타입에서 뽑는지를 **전 필드로** 확인한다."""
    from shopping_shorts import app as app_mod
    bools = [k for k, v in df.DEFAULTS.items() if isinstance(v, bool)]
    assert bools, "참/거짓 칸이 하나도 없다 — 검사가 헛돈다"
    for k in bools:
        spec = {kk: q for kk, q in (("preset", "plain_black"),)}
        spec[k] = "0"
        assert app_mod  # 라우트를 태워 실제 파싱 경로를 지난다
        r = client.get("/api/produce/frame.png", params=spec)
        assert r.status_code == 200, f"{k}: {r.status_code}"
        # 파싱 결과를 직접 본다 — 그림 픽셀로 재면 칸마다 판정이 달라진다
        parsed = df.normalize({k: False})
        assert parsed[k] is False, f"{k}: normalize가 참/거짓으로 안 자른다"


def test_head_block_off_actually_stops_drawing_the_band(client):
    """★그림으로 확인한다 — 파싱만 맞고 안 그려지면 소용없다."""
    import io as _io

    from PIL import Image as _Image
    q = {"preset": "plain_black", "bar_h": 0, "title": "제목", "title_y": 40,
         "title_size": 70, "title_color": "#FFFFFF", "icons": "0"}
    def covered(hb):
        raw = client.get("/api/produce/frame.png", params={**q, "head_block": hb}).content
        im = _Image.open(_io.BytesIO(raw)).convert("RGBA")
        return sum(im.getpixel((x, int(df.H * 0.42)))[3] > 0 for x in range(0, df.W, 20))
    assert covered("0") < covered("1"), "바탕을 껐는데 여전히 덮는다"
