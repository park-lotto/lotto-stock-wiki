"""장면꾸미기 로고(관제 065) — 저장값 effects[].masks[] 의 {kind:'image', src} 한 항목이 주인.
서버 검증은 계정 폴더의 실재 PNG만 통과시키고, 업로드 API는 그림만 받아 PNG로 저장한다."""
import io, json, pathlib, re
from PIL import Image
from shopping_shorts import scene_style
from shopping_shorts.scene_style import ROOT

LOGO_DIR = ROOT / "out" / "장면꾸미기_로고"


def _png_bytes(w=64, h=32):
    im = Image.new("RGBA", (w, h), (255, 0, 0, 255)); b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()


def _snap(mask):
    return {"mode": "story", "presetId": "s0101", "effects": {"0": {"masks": [mask]}}}


def test_validate_keeps_image_mask_only_when_file_exists(tmp_path):
    d = LOGO_DIR / "999999"; d.mkdir(parents=True, exist_ok=True)
    f = d / ("a" * 16 + ".png"); f.write_bytes(_png_bytes())
    try:
        ok = scene_style.validate_snapshot(_snap({"kind": "image", "src": "장면꾸미기_로고/999999/" + "a" * 16 + ".png", "l": 70, "t": 4, "w": 24, "h": 12}))
        m = ok["effects"]["0"]["masks"]
        assert len(m) == 1 and m[0]["kind"] == "image" and m[0]["src"].endswith("a" * 16 + ".png")
        missing = scene_style.validate_snapshot(_snap({"kind": "image", "src": "장면꾸미기_로고/999999/" + "b" * 16 + ".png", "l": 1, "t": 1, "w": 10, "h": 10}))
        assert missing["effects"]["0"]["masks"] == []                       # 없는 파일은 버린다
        bad = scene_style.validate_snapshot(_snap({"kind": "image", "src": "../../etc/passwd", "l": 1, "t": 1, "w": 10, "h": 10}))
        assert bad["effects"]["0"]["masks"] == []                           # 경로 장난은 버린다
    finally:
        f.unlink(missing_ok=True)


def test_upload_api_saves_png_and_rejects_non_image(monkeypatch):
    from fastapi.testclient import TestClient
    from shopping_shorts import app as A
    monkeypatch.setattr(A, "_cid", lambda request: 999998)
    c = TestClient(A.app)
    r = c.post("/api/produce/scene-style/logo", files={"file": ("logo.png", _png_bytes(2000, 1000), "image/png")})
    assert r.status_code == 200 and r.json()["ok"], r.text
    src = r.json()["src"]
    assert re.fullmatch(r"장면꾸미기_로고/999998/[0-9a-f]{16}\.png", src)
    p = ROOT / "out" / src
    assert p.is_file() and Image.open(p).size[0] <= 1024            # 큰 그림은 1024로 줄인다
    bad = c.post("/api/produce/scene-style/logo", files={"file": ("x.png", b"not an image", "image/png")})
    assert bad.status_code == 422
    lst = c.get("/api/produce/scene-style/logo").json()
    assert any(it["src"] == src for it in lst["items"])
    p.unlink(missing_ok=True)
