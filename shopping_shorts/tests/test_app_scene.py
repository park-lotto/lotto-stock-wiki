import re
import subprocess
from pathlib import Path
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
    # example.com은 실제 DNS 해석이 되지만 테스트 환경 네트워크에 의존하지 않도록 고정 IP로 스텁
    monkeypatch.setattr(app_mod.socket, "gethostbyname", lambda h: "93.184.216.34")
    monkeypatch.setattr(app_mod.frame_extract, "download_video",
                        lambda url, dest: tmp_path / "src.mp4")
    (tmp_path / "src.mp4").write_bytes(b"src")
    # Task6 — prepare가 소스 fps를 재려고 실제 ffprobe를 태우는데 위 파일은 가짜
    # 바이트라 ffprobe가 실패한다. fps 자체는 이 테스트의 관심사가 아니므로 스텁한다.
    monkeypatch.setattr(app_mod.scene_cut, "video_fps", lambda p: 30.0)
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
    # 토큰은 정상이지만 media_path를 끼워넣으면 무시돼야 한다.
    # C-1 수정으로 commit이 토큰파일을 소비용으로 rename하므로 최종 media_path는 더 이상
    # 원본 토큰 이름으로 끝나지 않는다 — 여전히 scene_assets 디렉터리 안의 .mp4이고
    # 주입한 /etc/passwd가 전혀 안 쓰였는지만 확인한다(이 테스트의 원래 취지).
    d = tmp_path / "scene_assets"
    d.mkdir(parents=True, exist_ok=True)
    token = "a" * 32
    (d / f"{token}.mp4").write_bytes(b"clip")

    r = client.post("/api/scene/save/commit", json={
        "token": token, "asset_type": "clip", "title": "t", "render_mode": "cutaway",
        "source_origin": "짜집기", "media_path": "/etc/passwd"})

    assert r.status_code == 200
    got = Store(app_mod.DB_PATH).get_scene_asset(r.json()["id"])
    assert got["media_path"].endswith(".mp4")
    assert str(d) in got["media_path"]
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
        "source_kind": "reference", "source_ref": "ABC", "source_origin": "짜집기"})

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
        "token": token, "asset_type": "sfx", "title": "띠용", "render_mode": "cutaway",
        "source_origin": "짜집기"})

    assert r.status_code == 200
    # C-1 수정으로 commit이 원본 토큰파일을 먼저 소비용 이름으로 rename하므로 extract_audio에
    # 넘어가는 경로는 더 이상 원본 토큰 이름이 아니다 — 같은 구간컷(.mp4) 1개만 재사용됐는지
    # (재추출 없음, 이 테스트의 원래 취지)만 확인한다.
    assert seen["clip"].suffix == ".mp4"
    assert seen["clip"].name != f"{token}.mp4"       # 토큰은 이미 소비돼 원본 이름이 아니다
    got = Store(app_mod.DB_PATH).get_scene_asset(r.json()["id"])
    assert got["media_path"].endswith(".mp3")
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
    media = Path(Store(app_mod.DB_PATH).get_scene_asset(aid)["media_path"])
    assert media.exists()

    assert client.post(f"/api/scene/{aid}/delete").json()["ok"] is True
    assert Store(app_mod.DB_PATH).get_scene_asset(aid) is None
    assert not media.exists()          # 물리 파일도 같이 지워져야 한다(디스크 누수 버그 회귀)


def test_delete_removes_poster_too(client, tmp_path):
    d = tmp_path / "scene_assets"
    d.mkdir(parents=True, exist_ok=True)
    media = d / "poster1.mp4"
    poster = d / "poster1.jpg"
    media.write_bytes(b"video")
    poster.write_bytes(b"jpg")
    aid = Store(app_mod.DB_PATH).add_scene_asset({
        "asset_type": "overlay", "media_path": str(media), "poster_path": str(poster),
        "title": "포스터있음"})

    assert client.post(f"/api/scene/{aid}/delete").json()["ok"] is True
    assert not media.exists()
    assert not poster.exists()


def test_delete_of_other_customers_asset_leaves_files(client, tmp_path):
    # 남의 자산(customer_id 다름)은 404여야 하고, 그 파일은 절대 지워지면 안 된다.
    d = tmp_path / "scene_assets"
    d.mkdir(parents=True, exist_ok=True)
    media = d / "other.mp4"
    media.write_bytes(b"video")
    aid = Store(app_mod.DB_PATH).add_scene_asset(
        {"asset_type": "clip", "media_path": str(media), "title": "남의것"},
        customer_id=999)

    r = client.post(f"/api/scene/{aid}/delete")

    assert r.status_code == 404
    assert media.exists()                          # 파일이 그대로 남아있어야 한다
    assert Store(app_mod.DB_PATH).get_scene_asset(aid, customer_id=999) is not None


def test_delete_ok_when_file_already_missing(client, tmp_path):
    # 파일이 디스크에서 이미 사라져도(수동 정리 등) 삭제 요청 자체는 500 없이 성공해야 한다.
    aid = _mk_asset(client, tmp_path)
    media = Path(Store(app_mod.DB_PATH).get_scene_asset(aid)["media_path"])
    media.unlink()

    r = client.post(f"/api/scene/{aid}/delete")

    assert r.status_code == 200
    assert r.json()["ok"] is True


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


# ── 리뷰 Important 4건 회귀 테스트 (2026-07-15) ──

def test_upload_rejects_clip_type(client):
    # I-2 — clip 업로드는 make_clip 규격정규화를 안 거쳐 페이즈2 렌더가 깨진다.
    # _SCENE_EXT에서 clip을 뺐으니 asset_type=clip은 422로 막혀야 한다.
    r = client.post("/api/scene/upload",
                    data={"asset_type": "clip", "title": "몰래업로드"},
                    files={"file": ("evil.mp4", b"\x00" * 100, "video/mp4")})

    assert r.status_code == 422
    assert r.json()["ok"] is False


def test_upload_rejects_oversized_file(client, monkeypatch):
    # I-1 — 무제한 RAM 적재로 인한 OOM 방지. 상한을 낮춰 실제로 넘겨서 413을 확인한다.
    monkeypatch.setattr(app_mod, "_SCENE_UPLOAD_MAX", 10)
    r = client.post("/api/scene/upload",
                    data={"asset_type": "sfx", "title": "너무큼"},
                    files={"file": ("big.mp3", b"x" * 1000, "audio/mpeg")})

    assert r.status_code == 413
    assert r.json()["ok"] is False


def test_commit_rejects_bogus_keep_original_audio(client, tmp_path):
    # I-3 — int("yes")가 ValueError로 500 나던 것(리뷰 실증). 422로 막혀야 한다.
    d = tmp_path / "scene_assets"
    d.mkdir(parents=True, exist_ok=True)
    token = "f" * 32
    (d / f"{token}.mp4").write_bytes(b"clip")

    r = client.post("/api/scene/save/commit", json={
        "token": token, "asset_type": "clip", "title": "t", "render_mode": "cutaway",
        "source_origin": "짜집기", "keep_original_audio": "yes"})

    assert r.status_code == 422
    assert r.json()["ok"] is False


def test_commit_rejects_bogus_render_mode(client, tmp_path):
    # asset_type=clip일 때 render_mode는 replace/cutaway 둘뿐이어야 한다.
    d = tmp_path / "scene_assets"
    d.mkdir(parents=True, exist_ok=True)
    token = "1" * 32
    (d / f"{token}.mp4").write_bytes(b"clip")

    r = client.post("/api/scene/save/commit", json={
        "token": token, "asset_type": "clip", "title": "t",
        "source_origin": "짜집기", "render_mode": "DROP TABLE"})

    assert r.status_code == 422
    assert r.json()["ok"] is False


def test_commit_rejects_bogus_asset_type(client, tmp_path):
    # asset_type을 검증 없이 받으면 임의 문자열이 저장되고, 그게 프론트 onclick='...'
    # 속성 컨텍스트로 흘러 XSS 체인이 닫힌다(리뷰 실증). clip/sfx/overlay만 허용해야 한다.
    d = tmp_path / "scene_assets"
    d.mkdir(parents=True, exist_ok=True)
    for bad, token in (("x'),alert(1),('", "2" * 32), ("banana", "3" * 32)):
        (d / f"{token}.mp4").write_bytes(b"clip")
        r = client.post("/api/scene/save/commit", json={
            "token": token, "asset_type": bad, "title": "t", "source_origin": "짜집기"})
        assert r.status_code == 422, f"asset_type={bad!r}가 통과됨"
        assert r.json()["ok"] is False


def test_commit_accepts_valid_asset_types(client, tmp_path, monkeypatch):
    # sfx는 commit 안에서 실제 ffmpeg로 오디오를 추출한다 — 여기선 화이트리스트 통과 여부만
    # 보는 테스트라 extract_audio를 스텁해 ffmpeg 의존을 없앤다(다른 sfx 동작은 이미
    # test_commit_as_sfx_extracts_audio_from_clip에서 검증됨).
    monkeypatch.setattr(app_mod.scene_assets, "extract_audio",
                        lambda clip, out: (out.write_bytes(b"mp3"), out)[-1])
    d = tmp_path / "scene_assets"
    d.mkdir(parents=True, exist_ok=True)
    for i, at in enumerate(("clip", "sfx", "overlay")):
        token = f"{i}" * 32
        (d / f"{token}.mp4").write_bytes(b"clip")
        r = client.post("/api/scene/save/commit", json={
            "token": token, "asset_type": at, "title": f"t-{at}",
            "source_origin": "짜집기", "render_mode": "cutaway"})
        assert r.status_code == 200, f"asset_type={at}가 막힘: {r.text}"
        assert r.json()["ok"] is True


def test_update_rejects_dict_value(client, tmp_path):
    # I-3 — dict 값이 sqlite에 그대로 넘어가면 InterfaceError로 500 나던 것(리뷰 실증).
    aid = _mk_asset(client, tmp_path)

    r = client.post(f"/api/scene/{aid}/update",
                    json={"title": {"nested": "dict"}})

    assert r.status_code == 422
    assert r.json()["ok"] is False
    # 실제로 반영 안 됐는지도 확인
    got = Store(app_mod.DB_PATH).get_scene_asset(aid)
    assert got["title"] != {"nested": "dict"}


def test_update_still_allows_keywords_list(client, tmp_path):
    # keywords는 list가 정상 — dict/list 거부 로직이 keywords까지 막으면 안 된다.
    aid = _mk_asset(client, tmp_path)

    r = client.post(f"/api/scene/{aid}/update", json={"keywords": ["설탕", "소금"]})

    assert r.status_code == 200 and r.json()["ok"] is True
    got = Store(app_mod.DB_PATH).get_scene_asset(aid)
    assert got["keywords"] == ["설탕", "소금"]


def test_prepare_rejects_cloud_metadata_ip(client):
    # I-4 — AWS 메타데이터 엔드포인트로 SSRF 시도. 422로 막혀야 한다.
    r = client.post("/api/scene/save/prepare", json={
        "src_url": "http://169.254.169.254/latest/meta-data/",
        "start": 0, "end": 1})

    assert r.status_code == 422
    assert r.json()["ok"] is False


def test_prepare_rejects_file_scheme(client):
    # I-4 — file:// 스킴으로 로컬 파일 접근 시도. 422로 막혀야 한다.
    r = client.post("/api/scene/save/prepare", json={
        "src_url": "file:///etc/passwd", "start": 0, "end": 1})

    assert r.status_code == 422
    assert r.json()["ok"] is False


def test_prepare_rejects_localhost(client):
    # I-4 — 루프백으로 서버 자기 자신을 호출하는 SSRF 시도. 422로 막혀야 한다.
    r = client.post("/api/scene/save/prepare", json={
        "src_url": "http://127.0.0.1:8849/admin", "start": 0, "end": 1})

    assert r.status_code == 422
    assert r.json()["ok"] is False


def test_prepare_allows_public_host(client, tmp_path, monkeypatch):
    # 정상 공개 URL은 여전히 통과해야 한다(회귀 방지) — DNS는 고정 IP로 스텁.
    monkeypatch.setattr(app_mod.socket, "gethostbyname", lambda h: "93.184.216.34")
    monkeypatch.setattr(app_mod.frame_extract, "download_video",
                        lambda url, dest: tmp_path / "src2.mp4")
    (tmp_path / "src2.mp4").write_bytes(b"src")
    # Task6 — 위와 동일한 이유(가짜 바이트라 실제 ffprobe fps 측정이 실패한다).
    monkeypatch.setattr(app_mod.scene_cut, "video_fps", lambda p: 30.0)
    monkeypatch.setattr(app_mod.scene_assets, "make_clip",
                        lambda src, s, e, out: (out.parent.mkdir(parents=True, exist_ok=True),
                                                out.write_bytes(b"clip"), out)[-1])
    monkeypatch.setattr(app_mod.scene_assets, "make_poster", lambda m, o: o)
    monkeypatch.setattr(app_mod.scene_assets, "probe_duration", lambda p: 1.0)
    monkeypatch.setattr(app_mod.scene_assets, "autotag", lambda frames, ctx: {})

    r = client.post("/api/scene/save/prepare", json={
        "src_url": "https://cdn.example.com/v.mp4", "start": 0, "end": 2})

    assert r.status_code == 200
    assert r.json()["ok"] is True


# ── 최종 whole-branch 리뷰 회귀 테스트 (2026-07-15, scene-p1-final-review.md) ──

def test_commit_token_reuse_is_blocked_c1(client, tmp_path):
    """C-1 재현 시나리오 재실행 — 이전엔 같은 토큰으로 commit을 두 번 하면 둘 다 200이었고
    두 자산이 같은 media_path를 공유했다. 이제 두 번째는 404여야 한다."""
    d = tmp_path / "scene_assets"
    d.mkdir(parents=True, exist_ok=True)
    token = "9" * 32
    (d / f"{token}.mp4").write_bytes(b"clip-bytes")

    r1 = client.post("/api/scene/save/commit", json={
        "token": token, "asset_type": "clip", "title": "첫번째",
        "render_mode": "cutaway", "source_origin": "짜집기"})
    assert r1.status_code == 200 and r1.json()["ok"] is True

    r2 = client.post("/api/scene/save/commit", json={
        "token": token, "asset_type": "clip", "title": "두번째(재사용 시도)",
        "render_mode": "cutaway", "source_origin": "짜집기"})
    assert r2.status_code == 404

    # 중복 카드가 생기지 않는다 — 자산은 정확히 1개.
    items = client.get("/api/scene/list").json()["items"]
    assert len(items) == 1


def test_commit_distinct_assets_never_share_media_path_c1(client, tmp_path):
    """C-1 — 서로 다른 prepare 토큰으로 만든 두 자산의 media_path는 절대 같아선 안 된다.
    같으면(=고쳐지기 전 버그) 한쪽 삭제가 다른 쪽 파일을 파괴한다."""
    d = tmp_path / "scene_assets"
    d.mkdir(parents=True, exist_ok=True)
    tok_a, tok_b = "7" * 32, "8" * 32
    (d / f"{tok_a}.mp4").write_bytes(b"clip-a")
    (d / f"{tok_b}.mp4").write_bytes(b"clip-b")

    id_a = client.post("/api/scene/save/commit", json={
        "token": tok_a, "asset_type": "clip", "title": "A",
        "render_mode": "cutaway", "source_origin": "짜집기"}).json()["id"]
    id_b = client.post("/api/scene/save/commit", json={
        "token": tok_b, "asset_type": "clip", "title": "B",
        "render_mode": "cutaway", "source_origin": "짜집기"}).json()["id"]

    media_a = Store(app_mod.DB_PATH).get_scene_asset(id_a)["media_path"]
    media_b = Store(app_mod.DB_PATH).get_scene_asset(id_b)["media_path"]
    assert media_a != media_b


def test_commit_token_reuse_delete_one_survive_other_c1(client, tmp_path):
    """C-1 — 리뷰 재현의 핵심 인수 시나리오: 두 자산이 있을 때 하나를 지워도 다른 하나의
    media는 계속 200으로 서빙돼야 한다(파일 공유가 없으므로 파괴가 전파되지 않음)."""
    d = tmp_path / "scene_assets"
    d.mkdir(parents=True, exist_ok=True)
    tok_a, tok_b = "5" * 32, "6" * 32
    (d / f"{tok_a}.mp4").write_bytes(b"clip-a")
    (d / f"{tok_b}.mp4").write_bytes(b"clip-b")

    id_a = client.post("/api/scene/save/commit", json={
        "token": tok_a, "asset_type": "clip", "title": "A",
        "render_mode": "cutaway", "source_origin": "짜집기"}).json()["id"]
    id_b = client.post("/api/scene/save/commit", json={
        "token": tok_b, "asset_type": "clip", "title": "B",
        "render_mode": "cutaway", "source_origin": "짜집기"}).json()["id"]

    assert client.post(f"/api/scene/{id_a}/delete").json()["ok"] is True
    r = client.get(f"/api/scene/{id_b}/media")
    assert r.status_code == 200
    assert r.content == b"clip-b"


# ── I-1: render_mode/keep_original_audio 불변식이 update에도 지켜지는지 ──

def test_update_rejects_bogus_render_mode_on_sfx_i1(client, tmp_path):
    aid = _mk_asset(client, tmp_path, asset_type="sfx", render_mode=None)

    r = client.post(f"/api/scene/{aid}/update", json={"render_mode": "banana"})

    assert r.status_code == 422
    assert r.json()["ok"] is False
    got = Store(app_mod.DB_PATH).get_scene_asset(aid)
    assert got["render_mode"] is None                # 오염 안 됨


def test_update_rejects_bogus_render_mode_on_clip_i1(client, tmp_path):
    aid = _mk_asset(client, tmp_path, asset_type="clip", render_mode="cutaway")

    r = client.post(f"/api/scene/{aid}/update", json={"render_mode": "banana"})

    assert r.status_code == 422
    got = Store(app_mod.DB_PATH).get_scene_asset(aid)
    assert got["render_mode"] == "cutaway"            # 원래 값 그대로


def test_update_rejects_bogus_keep_original_audio_i1(client, tmp_path):
    aid = _mk_asset(client, tmp_path)

    r = client.post(f"/api/scene/{aid}/update", json={"keep_original_audio": "yes"})

    assert r.status_code == 422
    assert r.json()["ok"] is False
    got = Store(app_mod.DB_PATH).get_scene_asset(aid)
    assert got["keep_original_audio"] != "yes"        # 문자열로 새어들어가지 않음


def test_update_accepts_valid_render_mode_and_koa_i1(client, tmp_path):
    aid = _mk_asset(client, tmp_path, asset_type="clip", render_mode="cutaway")

    r = client.post(f"/api/scene/{aid}/update", json={
        "render_mode": "replace", "keep_original_audio": True})

    assert r.status_code == 200 and r.json()["ok"] is True
    got = Store(app_mod.DB_PATH).get_scene_asset(aid)
    assert got["render_mode"] == "replace"
    assert got["keep_original_audio"] == 1


# ── I-2: 업로드 자산도 category를 저장하고 페이즈2 1차필터로 찾을 수 있어야 한다 ──

def test_upload_saves_category_and_is_findable_by_filter_i2(client):
    r = client.post("/api/scene/upload",
                    data={"asset_type": "sfx", "title": "띠용", "category": "레시피"},
                    files={"file": ("a.mp3", b"mp3bytes", "audio/mpeg")})

    assert r.status_code == 200 and r.json()["ok"] is True
    got = client.get("/api/scene/list?category=레시피").json()["items"]
    assert [i["title"] for i in got] == ["띠용"]


# ── I-3: overlay poster 경로가 media 경로와 절대 겹치면 안 된다(.jpg 업로드 함정) ──

def test_upload_overlay_poster_path_never_equals_media_path_i3(client, monkeypatch):
    seen = {}

    def fake_make_poster(media_path, out_path):
        seen["media"] = media_path
        seen["poster"] = out_path
        out_path.write_bytes(b"jpg")
        return out_path
    monkeypatch.setattr(app_mod.scene_assets, "make_poster", fake_make_poster)

    r = client.post("/api/scene/upload",
                    data={"asset_type": "overlay", "title": "화살표"},
                    files={"file": ("arrow.jpg", b"orig-jpg-bytes", "image/jpeg")})

    assert r.status_code == 200 and r.json()["ok"] is True
    assert seen["media"] != seen["poster"]
    assert seen["media"].suffix == ".jpg"
    assert seen["poster"].name != seen["media"].name


# ── Task5: /api/scene/split — 자동 컷 분할(DB 미기록, 사장님이 고르는 A안) ──

def test_split_returns_frame_pairs_and_posters(client, monkeypatch, tmp_path):
    src = tmp_path / "s.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "testsrc=size=320x568:rate=30:duration=3",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src)],
                   check=True, capture_output=True, stdin=subprocess.DEVNULL)
    # cdn.example.com의 실 DNS 해석에 테스트를 의존시키지 않는다(다른 prepare 테스트와 동일한 이유).
    monkeypatch.setattr(app_mod.socket, "gethostbyname", lambda h: "93.184.216.34")
    monkeypatch.setattr(app_mod.frame_extract, "download_video",
                        lambda url, td: str(src))

    r = client.post("/api/scene/split", json={"src_url": "https://cdn.example.com/a.mp4"})

    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["fps"] == 30.0
    assert d["total_frames"] == 90
    assert len(d["cuts"]) >= 1
    c0 = d["cuts"][0]
    assert isinstance(c0["start_frame"], int) and isinstance(c0["end_frame"], int)
    assert c0["poster_url"].startswith("/api/scene/split/")

    # 포스터가 실제로 서빙되는지도 확인(라우트만 200이고 파일이 없으면 리그레션을 놓친다)
    poster_r = client.get(c0["poster_url"])
    assert poster_r.status_code == 200
    assert poster_r.headers["content-type"] == "image/jpeg"


def test_split_rejects_internal_url(client):
    r = client.post("/api/scene/split", json={"src_url": "http://169.254.169.254/latest/meta-data/"})
    assert r.status_code == 422


def test_split_requires_src_url(client):
    assert client.post("/api/scene/split", json={}).status_code == 422


# ── Task6: commit이 source_origin·render_mode를 강제 ──

def test_commit_rejects_unknown_origin(client, tmp_path):
    """★'모름'이면 막는다(설계 §7.2). 손해가 비대칭이다 — 짤 하나 잃는 것보다
    남의 촬영분이 라이브에 들어가는 게 훨씬 나쁘다."""
    d = tmp_path / "scene_assets"
    d.mkdir(parents=True, exist_ok=True)
    token = "a1" * 16
    (d / f"{token}.mp4").write_bytes(b"clip")

    r = client.post("/api/scene/save/commit", json={
        "token": token, "title": "t", "asset_type": "clip",
        "render_mode": "cutaway", "source_origin": "모름"})

    assert r.status_code == 422
    assert "출처" in r.json()["error"] or "origin" in r.json()["error"]


def test_commit_rejects_missing_origin(client, tmp_path):
    d = tmp_path / "scene_assets"
    d.mkdir(parents=True, exist_ok=True)
    token = "a2" * 16
    (d / f"{token}.mp4").write_bytes(b"clip")

    r = client.post("/api/scene/save/commit", json={
        "token": token, "title": "t", "asset_type": "clip",
        "render_mode": "cutaway"})

    assert r.status_code == 422


def test_commit_rejects_clip_without_render_mode(client, tmp_path):
    """페이즈1 리뷰 잔여: render_mode 없이 저장되면 배지가 NULL을 '컷어웨이'로
    거짓 표기한다(설계 §8)."""
    d = tmp_path / "scene_assets"
    d.mkdir(parents=True, exist_ok=True)
    token = "a3" * 16
    (d / f"{token}.mp4").write_bytes(b"clip")

    r = client.post("/api/scene/save/commit", json={
        "token": token, "title": "t", "asset_type": "clip",
        "source_origin": "짜집기"})

    assert r.status_code == 422


def test_commit_stores_origin_and_start_frame(client, tmp_path):
    d = tmp_path / "scene_assets"
    d.mkdir(parents=True, exist_ok=True)
    token = "a4" * 16
    (d / f"{token}.mp4").write_bytes(b"clip")

    r = client.post("/api/scene/save/commit", json={
        "token": token, "title": "t", "asset_type": "clip",
        "render_mode": "cutaway", "source_origin": "짜집기",
        "source_start_frame": 124})

    assert r.status_code == 200
    got = Store(app_mod.DB_PATH).list_scene_assets()[-1]
    assert got["source_origin"] == "짜집기"
    assert got["source_start_frame"] == 124


def test_prepare_returns_source_start_frame(client, monkeypatch, tmp_path):
    """★소스 fps 기준이어야 한다. 클립은 30fps로 통일되므로 클립 fps로 재면
    원본이 24fps일 때 틀린 번호가 저장된다."""
    src = tmp_path / "s24.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "testsrc=size=320x568:rate=24:duration=4",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src)],
                   check=True, capture_output=True, stdin=subprocess.DEVNULL)
    monkeypatch.setattr(app_mod.socket, "gethostbyname", lambda h: "93.184.216.34")
    monkeypatch.setattr(app_mod.frame_extract, "download_video",
                        lambda url, td: str(src))
    # make_poster → frame_extract.extract_frame_at는 이 관문의 관심사가 아니고(포스터
    # 생성은 fps/start_frame 계산과 무관), 그 안의 subprocess.run에 stdin=DEVNULL이
    # 빠져 있어 pytest 기본 캡처 아래서 별개의 OSError[WinError 50]로 죽는 게 실측됨
    # (다른 prepare 테스트들도 전부 make_poster를 스텁한다 — 같은 이유로 따라간다).
    monkeypatch.setattr(app_mod.scene_assets, "make_poster", lambda m, o: o)

    r = client.post("/api/scene/save/prepare", json={
        "src_url": "https://cdn.example.com/a.mp4", "start": 1.0, "end": 2.0})

    assert r.status_code == 200
    assert r.json()["start_frame"] == 24        # 30이 나오면 클립 fps로 잰 것


def test_split_never_writes_to_db(client, monkeypatch, tmp_path):
    """리뷰 Important — split의 계약은 '컷 목록 + 포스터만 반환, DB는 안 건드림'이다
    (app.py의 함수 docstring). 이 테스트가 없으면 누가 라우트 안에
    Store(...).add_scene_asset(...)을 심어도 기존 42건이 전부 통과했다."""
    src = tmp_path / "s2.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "testsrc=size=320x568:rate=30:duration=3",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src)],
                   check=True, capture_output=True, stdin=subprocess.DEVNULL)
    monkeypatch.setattr(app_mod.socket, "gethostbyname", lambda h: "93.184.216.34")
    monkeypatch.setattr(app_mod.frame_extract, "download_video",
                        lambda url, td: str(src))

    r = client.post("/api/scene/split", json={"src_url": "https://cdn.example.com/b.mp4"})

    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert Store(app_mod.DB_PATH).list_scene_assets() == []


# ── 장면라이브러리 저장 라우트 리뷰 회귀 테스트 — I-1/I-2 (2026-07-16) ──

def test_commit_normalizes_oversized_source_start_frame_i1(client, tmp_path):
    """source_start_frame에 SQLite INTEGER 상한(부호있는 64비트)을 넘는 정수를 넣으면
    str().isdigit()도 int()도 통과해 store.py의 INSERT에서 OverflowError→500이 났다
    (실증). source_start_frame은 편집 편의용 부가 메타라 -5·12.5·"abc" 같은 쓰레기 값은
    거부 대신 조용히 None으로 흘리는 게 설계 의도 — 10**19도 그 대접을 받아야 한다
    (거부 422가 아니라 저장 성공 200 + None)."""
    d = tmp_path / "scene_assets"
    d.mkdir(parents=True, exist_ok=True)
    token = "b1" * 16
    (d / f"{token}.mp4").write_bytes(b"clip")

    # 실제 서버(uvicorn)처럼 예외를 500 응답으로 관찰하려면 raise_server_exceptions=False가
    # 필요하다 — 기본 TestClient(다른 테스트들이 쓰는 `client` 픽스처)는 처리 안 된 서버
    # 예외를 파이썬 레벨로 재발생시켜서, 고쳐지기 전 코드로 돌리면 500 응답이 아니라
    # pytest 에러(OverflowError)로 나타난다.
    raw_client = TestClient(app_mod.app, raise_server_exceptions=False)
    r = raw_client.post("/api/scene/save/commit", json={
        "token": token, "asset_type": "clip", "title": "t", "render_mode": "cutaway",
        "source_origin": "짜집기", "source_start_frame": 10 ** 19})

    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    got = Store(app_mod.DB_PATH).get_scene_asset(r.json()["id"])
    assert got["source_start_frame"] is None   # 상한 밖 값은 다른 쓰레기 값과 같이 None으로


def test_commit_keeps_source_start_frame_at_sqlite_int_boundary(client, tmp_path):
    """경계값 확인 — SQLite INTEGER 상한 그 자체는 여전히 정상 저장돼야 한다(과잉 조임 방지)."""
    d = tmp_path / "scene_assets"
    d.mkdir(parents=True, exist_ok=True)
    token = "b2" * 16
    (d / f"{token}.mp4").write_bytes(b"clip")

    r = client.post("/api/scene/save/commit", json={
        "token": token, "asset_type": "clip", "title": "t", "render_mode": "cutaway",
        "source_origin": "짜집기", "source_start_frame": app_mod._SQLITE_INT_MAX})

    assert r.status_code == 200, r.text
    got = Store(app_mod.DB_PATH).get_scene_asset(r.json()["id"])
    assert got["source_start_frame"] == app_mod._SQLITE_INT_MAX


def test_update_rejects_render_mode_none_on_clip_i2(client, tmp_path):
    """commit이 clip에 render_mode를 필수로 강제하는데(설계 §8), update가
    render_mode=None을 그대로 허용해 그 불변식을 되돌릴 수 있었다(실증: 200, 저장값
    None). NULL이면 배지가 그걸 '컷어웨이'로 거짓 표기한다."""
    aid = _mk_asset(client, tmp_path, asset_type="clip", render_mode="cutaway")

    r = client.post(f"/api/scene/{aid}/update", json={"render_mode": None})

    assert r.status_code == 422
    got = Store(app_mod.DB_PATH).get_scene_asset(aid)
    assert got["render_mode"] == "cutaway"            # 원래 값 그대로, None으로 안 풀림


def test_update_still_allows_render_mode_none_on_sfx_i2(client, tmp_path):
    """sfx/overlay는 render_mode가 없는 게 정상(스펙 §4) — I-2 방어는 clip에만 적용돼야
    하고, 멀쩡한 sfx 편집(다른 필드와 같이 render_mode=None을 보내는 흔한 프론트 패턴)까지
    막으면 안 된다."""
    aid = _mk_asset(client, tmp_path, asset_type="sfx", render_mode=None)

    r = client.post(f"/api/scene/{aid}/update", json={"render_mode": None, "title": "새 이름"})

    assert r.status_code == 200 and r.json()["ok"] is True
    got = Store(app_mod.DB_PATH).get_scene_asset(aid)
    assert got["render_mode"] is None
    assert got["title"] == "새 이름"
