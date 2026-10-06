"""3단계 배경음 목록(관제 146) — 목록·저장·렌더/캡컷 경로·롱폼 차단."""
import os

from shopping_shorts import bgm_lib, mix_pipeline


def test_catalog_files_all_exist_and_capped():
    tracks = bgm_lib.list_tracks()
    assert len(tracks) >= 24
    assert len({t["id"] for t in tracks}) == len(tracks)
    for t in tracks:
        assert os.path.getsize(bgm_lib.path_of(t["id"])) < 1_200_000     # 128k × 60초 ≈ 0.96MB — 60초 상한


def test_path_of_rejects_unknown_and_traversal():
    assert bgm_lib.path_of("nope_x") is None
    assert bgm_lib.path_of("../app") is None
    assert bgm_lib.path_of("") is None


def test_resolve_deco_media_uses_lib_over_upload(tmp_path):
    (tmp_path / "bgm.mp3").write_bytes(b"x")
    d = mix_pipeline.resolve_deco_media({"bgm": {"lib": "blue", "file": "bgm.mp3", "volume": 15}}, tmp_path)
    assert d["bgm"]["_abspath"] == bgm_lib.path_of("blue")
    d = mix_pipeline.resolve_deco_media({"bgm": {"file": "bgm.mp3"}}, tmp_path)
    assert d["bgm"]["_abspath"] == str(tmp_path / "bgm.mp3")              # 업로드 경로 종전 그대로


def _app(tmp_path, monkeypatch, deco=None, cid=0):
    from shopping_shorts import app as A
    from shopping_shorts.store import Store
    db = tmp_path / "t.db"
    st = Store(str(db))
    st.create_mix_job("jb", ["u"], 25, "free", customer_id=cid)
    st.update_mix_job("jb", deco=deco or {"bgm": {"file": "bgm.mp3", "volume": 15}, "sfx_pack": "off"})
    monkeypatch.setattr(A, "DB_PATH", str(db))
    return A, (lambda: Store(str(db)).get_mix_job("jb"))


def test_settings_pick_clear_volume_and_preserve(tmp_path, monkeypatch):
    A, job = _app(tmp_path, monkeypatch)
    assert A.api_produce_mix_settings({"job_id": "jb", "bgm_lib": "blue"})["ok"]
    d = job()["deco"]
    assert d["bgm"] == {"lib": "blue", "volume": 15} and d["sfx_pack"] == "off"   # 업로드 파일은 비우고 다른 꾸미기 보존
    A.api_produce_mix_settings({"job_id": "jb", "bgm_volume": 25})
    assert job()["deco"]["bgm"] == {"lib": "blue", "volume": 25}
    A.api_produce_mix_settings({"job_id": "jb", "deco": {"sfx_pack": "off"}})     # bgm 모르는 통째 저장
    assert job()["deco"]["bgm"]["lib"] == "blue"
    r = A.api_produce_mix_settings({"job_id": "jb", "bgm_lib": "../x"})
    assert r.status_code == 422
    A.api_produce_mix_settings({"job_id": "jb", "bgm_lib": ""})
    assert job()["deco"]["bgm"] == {"volume": 25}


def test_pick_invalidates_preview(tmp_path, monkeypatch):
    A, job = _app(tmp_path, monkeypatch)
    from shopping_shorts.store import Store
    Store(A.DB_PATH).update_mix_job("jb", preview_status="ready")
    A.api_produce_mix_settings({"job_id": "jb", "bgm_lib": "beggin"})
    assert job()["preview_status"] == ""


def test_longform_blocked_for_shorts_only_track(tmp_path, monkeypatch):
    src = tmp_path / "v.mp4"; src.write_bytes(b"x")
    A, job = _app(tmp_path, monkeypatch, deco={"bgm": {"lib": "blue", "volume": 15}})
    from shopping_shorts.store import Store
    Store(A.DB_PATH).update_mix_job("jb", status="done", video_path=str(src))
    monkeypatch.setattr(A, "_video_gone_reason", lambda j: None)
    _, s, resp = A._longform_job("jb")
    assert s is None and resp.status_code == 409
    Store(A.DB_PATH).update_mix_job("jb", deco={"bgm": {"volume": 15}})
    _, s, resp = A._longform_job("jb")
    assert resp is None and s == str(src)


def test_admin_only_by_default(tmp_path, monkeypatch):
    """2026-10-06 사장님 "관리자만 봐야 한다" — 기본은 사장님 계정(0) 작업만. 회원 작업은 목록 0·고르기 403."""
    A, job = _app(tmp_path, monkeypatch, cid=7)
    from shopping_shorts.store import Store
    st = Store(A.DB_PATH)
    assert not bgm_lib.enabled_for(st, job())
    r = A.api_produce_mix_settings({"job_id": "jb", "bgm_lib": "blue"})
    assert r.status_code == 403 and "lib" not in (job()["deco"].get("bgm") or {})
    st.set_setting("bgm_lib_enabled", "1")                 # 회원에게 열면
    assert bgm_lib.enabled_for(st, job())
    assert A.api_produce_mix_settings({"job_id": "jb", "bgm_lib": "blue"})["ok"]
    st.set_setting("bgm_lib_enabled", "off")
    assert not bgm_lib.enabled_for(st, {"customer_id": 0})


def test_speed_owner_render_and_capcut_follow(tmp_path, monkeypatch):
    """속도의 뜻은 bgm_lib.speed_of 한 곳 — 저장·렌더(atempo)·캡컷(배속 칸)이 같은 값을 쓴다."""
    assert bgm_lib.speed_of({}) == 1.0 and bgm_lib.speed_of({"speed": 9}) == 2.0
    assert bgm_lib.speed_of({"speed": "x"}) == 1.0 and bgm_lib.speed_of({"speed": 0.1}) == 0.5
    A, job = _app(tmp_path, monkeypatch)
    A.api_produce_mix_settings({"job_id": "jb", "bgm_lib": "blue", "bgm_speed": 1.25, "bgm_volume": 40})
    assert job()["deco"]["bgm"] == {"lib": "blue", "volume": 40, "speed": 1.25}
    A.api_produce_mix_settings({"job_id": "jb", "bgm_speed": 1})
    assert "speed" not in job()["deco"]["bgm"]                    # 1배속은 키를 지워 종전 그래프 그대로
