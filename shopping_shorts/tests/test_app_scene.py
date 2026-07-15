import re
import pytest
from fastapi.testclient import TestClient
from shopping_shorts import app as app_mod
from shopping_shorts.store import Store


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    Store(db)  # 스키마 생성
    monkeypatch.setattr(app_mod, "DB_PATH", db)
    monkeypatch.setattr(app_mod, "_SCENE_ASSETS_DIR", tmp_path / "scene_assets")
    return TestClient(app_mod.app)


def _mk_asset(client, tmp_path, **over):
    d = tmp_path / "scene_assets"
    d.mkdir(parents=True, exist_ok=True)
    media = d / "deadbeefdeadbeefdeadbeefdeadbeef.mp4"
    media.write_bytes(b"video")
    a = {"asset_type": "clip", "render_mode": "cutaway", "media_path": str(media),
         "title": "가루 한스푼", "category": "레시피", "role": "비법공개",
         "keywords": ["가루"], "source_kind": "reference", "source_ref": "ABC"}
    a.update(over)
    return Store(app_mod.DB_PATH).add_scene_asset(a)


def test_prepare_cuts_clip_and_returns_draft(client, tmp_path, monkeypatch):
    monkeypatch.setattr(app_mod.frame_extract, "download_video",
                        lambda url, dest: tmp_path / "src.mp4")
    (tmp_path / "src.mp4").write_bytes(b"src")
    monkeypatch.setattr(app_mod.scene_assets, "make_clip",
                        lambda src, s, e, out: (out.parent.mkdir(parents=True, exist_ok=True),
                                                out.write_bytes(b"clip"), out)[-1])
    monkeypatch.setattr(app_mod.scene_assets, "make_poster", lambda m, o: o)
    monkeypatch.setattr(app_mod.scene_assets, "probe_duration", lambda p: 2.5)
    monkeypatch.setattr(app_mod.scene_assets, "autotag",
                        lambda frames, ctx: {"scene_desc": "가루를 뜬다", "role": "비법공개",
                                             "subject": "가루", "tone": "궁금",
                                             "keywords": ["숟가락"]})

    r = client.post("/api/scene/save/prepare", json={
        "source_kind": "reference", "source_ref": "ABC",
        "src_url": "https://example.com/v.mp4", "start": 3.0, "end": 5.5,
        "category": "레시피", "caption": "한 스푼이면 끝"})

    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert re.fullmatch(r"[0-9a-f]{32}", d["token"])     # 서버가 발급한 토큰
    assert d["duration"] == 2.5
    assert d["draft"]["role"] == "비법공개"


def test_commit_rejects_bogus_token(client):
    for bad in ("../../etc/passwd", "abc", "", "x" * 32, "/tmp/evil"):
        r = client.post("/api/scene/save/commit", json={"token": bad, "title": "t",
                                                        "asset_type": "clip"})
        assert r.status_code == 422, f"token={bad!r}가 통과됨 — 경로조작 위험"
        assert r.json()["ok"] is False


def test_commit_rejects_client_supplied_media_path(client, tmp_path):
    # 토큰은 정상이지만 media_path를 끼워넣으면 무시돼야 한다
    d = tmp_path / "scene_assets"
    d.mkdir(parents=True, exist_ok=True)
    token = "a" * 32
    (d / f"{token}.mp4").write_bytes(b"clip")

    r = client.post("/api/scene/save/commit", json={
        "token": token, "asset_type": "clip", "title": "t",
        "media_path": "/etc/passwd"})

    assert r.status_code == 200
    got = Store(app_mod.DB_PATH).get_scene_asset(r.json()["id"])
    assert got["media_path"].endswith(f"{token}.mp4")
    assert "/etc/passwd" not in got["media_path"]


def test_commit_404_when_token_file_missing(client):
    r = client.post("/api/scene/save/commit", json={"token": "b" * 32, "asset_type": "clip",
                                                    "title": "t"})
    assert r.status_code == 404
    assert r.json()["ok"] is False


def test_commit_saves_and_list_returns_it(client, tmp_path):
    d = tmp_path / "scene_assets"
    d.mkdir(parents=True, exist_ok=True)
    token = "c" * 32
    (d / f"{token}.mp4").write_bytes(b"clip")

    r = client.post("/api/scene/save/commit", json={
        "token": token, "asset_type": "clip", "render_mode": "cutaway",
        "keep_original_audio": 1, "title": "가루 한스푼", "scene_desc": "가루를 뜬다",
        "role": "비법공개", "category": "레시피", "subject": "가루(밀가루·설탕류)",
        "tone": "궁금", "keywords": ["숟가락", "가루"],
        "source_kind": "reference", "source_ref": "ABC"})

    assert r.status_code == 200 and r.json()["ok"] is True
    items = client.get("/api/scene/list").json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "가루 한스푼"
    assert items[0]["keywords"] == ["숟가락", "가루"]


def test_commit_as_sfx_extracts_audio_from_clip(client, tmp_path, monkeypatch):
    """스펙 §5.3 — 효과음은 업로드뿐 아니라 잘라둔 화면짤에서 오디오만 뽑아도 만든다."""
    d = tmp_path / "scene_assets"
    d.mkdir(parents=True, exist_ok=True)
    token = "e" * 32
    (d / f"{token}.mp4").write_bytes(b"clip")
    seen = {}

    def fake_extract(clip, out):
        seen["clip"] = clip
        out.write_bytes(b"mp3")
        return out
    monkeypatch.setattr(app_mod.scene_assets, "extract_audio", fake_extract)

    r = client.post("/api/scene/save/commit", json={
        "token": token, "asset_type": "sfx", "title": "띠용", "render_mode": "cutaway"})

    assert r.status_code == 200
    assert seen["clip"].name == f"{token}.mp4"       # 같은 구간컷 재사용 — 재추출 없음
    got = Store(app_mod.DB_PATH).get_scene_asset(r.json()["id"])
    assert got["media_path"].endswith(f"{token}.mp3")
    assert got["render_mode"] is None                # sfx는 render_mode 없음(스펙 §4)
    assert got["poster_path"] is None


def test_commit_requires_title(client, tmp_path):
    d = tmp_path / "scene_assets"
    d.mkdir(parents=True, exist_ok=True)
    token = "d" * 32
    (d / f"{token}.mp4").write_bytes(b"clip")

    r = client.post("/api/scene/save/commit", json={"token": token, "asset_type": "clip",
                                                    "title": "  "})
    assert r.status_code == 422


def test_list_filters(client, tmp_path):
    _mk_asset(client, tmp_path, title="A", asset_type="clip", category="레시피")
    _mk_asset(client, tmp_path, title="B", asset_type="sfx", category="가전")

    assert len(client.get("/api/scene/list").json()["items"]) == 2
    got = client.get("/api/scene/list?type=sfx").json()["items"]
    assert [i["title"] for i in got] == ["B"]
    got = client.get("/api/scene/list?category=레시피").json()["items"]
    assert [i["title"] for i in got] == ["A"]


def test_update_edits_tags(client, tmp_path):
    aid = _mk_asset(client, tmp_path)

    r = client.post(f"/api/scene/{aid}/update", json={"title": "설탕 한스푼",
                                                      "keywords": ["설탕"]})

    assert r.status_code == 200 and r.json()["ok"] is True
    got = Store(app_mod.DB_PATH).get_scene_asset(aid)
    assert got["title"] == "설탕 한스푼"
    assert got["keywords"] == ["설탕"]


def test_delete_removes(client, tmp_path):
    aid = _mk_asset(client, tmp_path)

    assert client.post(f"/api/scene/{aid}/delete").json()["ok"] is True
    assert Store(app_mod.DB_PATH).get_scene_asset(aid) is None


def test_media_serves_file(client, tmp_path):
    aid = _mk_asset(client, tmp_path)

    r = client.get(f"/api/scene/{aid}/media")

    assert r.status_code == 200
    assert r.headers["content-type"] == "video/mp4"
    assert r.content == b"video"


def test_media_404_for_unknown_id(client):
    assert client.get("/api/scene/99999/media").status_code == 404


def test_upload_saves_sfx(client, tmp_path):
    r = client.post("/api/scene/upload",
                    data={"asset_type": "sfx", "title": "띠용"},
                    files={"file": ("a.mp3", b"mp3bytes", "audio/mpeg")})

    assert r.status_code == 200 and r.json()["ok"] is True
    got = Store(app_mod.DB_PATH).get_scene_asset(r.json()["id"])
    assert got["asset_type"] == "sfx"
    assert got["title"] == "띠용"
    assert got["media_path"].endswith(".mp3")


def test_upload_rejects_bad_extension(client):
    r = client.post("/api/scene/upload",
                    data={"asset_type": "sfx", "title": "나쁜것"},
                    files={"file": ("evil.exe", b"MZ", "application/octet-stream")})

    assert r.status_code == 422
    assert r.json()["ok"] is False


def test_scene_api_is_not_in_auth_allowlist():
    # /api/scene/*가 allowlist에 들어가면 남의 자산을 인증 없이 만질 수 있다
    for p in app_mod._AUTH_ALLOW:
        assert not p.startswith("/api/scene"), f"{p}가 allowlist에 있음"
