"""관제 151 — 인스타 메인월드 스크립트(ig_main.js)가 확장 zip에 자동 생성돼 들어가고, manifest가 그걸 MAIN으로 주입한다."""
import io
import json
import zipfile

from fastapi.testclient import TestClient

from shopping_shorts import app as app_mod


def test_zip_has_generated_ig_main(monkeypatch, tmp_path):
    monkeypatch.setattr(app_mod, "DB_PATH", tmp_path / "t.db")
    app_mod._serve_grab_extension.__dict__.pop("_cache", None)
    r = TestClient(app_mod.app).get("/grab_extension.zip")
    assert r.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(z.namelist())
    assert {"ig_main.js", "douyin_main.js", "grab_logic.js", "manifest.json"} <= names
    ig = z.read("ig_main.js").decode("utf-8")
    assert "_igMainWorld()" in ig and "__ssIgMedia" in ig and "__ssIgMediaReq" in ig
    assert ig.rstrip().endswith("})();")
    m = json.loads(z.read("manifest.json"))
    entry = [c for c in m["content_scripts"] if "ig_main.js" in c.get("js", [])]
    assert entry and entry[0]["world"] == "MAIN" and entry[0]["run_at"] == "document_start"
    assert any("instagram.com" in u for u in entry[0]["matches"])
