from copy import deepcopy
from datetime import datetime, timezone
import wave

from fastapi.testclient import TestClient

from shopping_shorts import app as appmod
from shopping_shorts.store import Store


def _cookie(customer_id):
    expires = int(datetime.now(timezone.utc).timestamp()) + 3600
    return appmod._sign_session(customer_id, expires)


def _setup(tmp_path, monkeypatch):
    db_path = tmp_path / "lab.db"
    work_root = tmp_path / "mix_jobs"
    monkeypatch.setattr(appmod, "DB_PATH", str(db_path))
    monkeypatch.setattr(appmod, "_MIX_WORK_DIR", work_root)
    monkeypatch.setattr(appmod, "_AUTH_ON", True)
    monkeypatch.setattr(appmod, "DASH_SECRET", "scene-style-lab-test-secret")
    store = Store(str(db_path))
    store.ensure_paywall_schema()
    return store, work_root


def _create_ready_job(store, work_root, job_id="j1", customer_id=0):
    store.create_mix_job(job_id, ["https://example.com/source"], 20, "free", customer_id=customer_id)
    tts = work_root / job_id / "tts" / "beat_00.mp3"
    clean = work_root / job_id / "s0" / "clean.mp4"
    tts.parent.mkdir(parents=True, exist_ok=True)
    clean.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(tts), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8_000)
        audio.writeframes(b"\0\0" * 8_000)
    clean.write_bytes(b"clean")
    plan = {
        "beats": [
            {
                "beat_idx": 0,
                "narration": "훅 대사",
                "tts_path": str(tts),
                "target_seconds": 1.8,
                "primary": {"video_id": "s0", "start": 0, "end": 1.8},
            }
        ]
    }
    store.update_mix_job(
        job_id,
        edit_plan=plan,
        clean_sources={"s0": str(clean)},
        headcopy={"text": "훅 제목"},
    )
    return store.get_mix_job(job_id)


def test_lab_page_is_hidden_from_non_admin_and_open_to_admin(tmp_path, monkeypatch):
    store, _work = _setup(tmp_path, monkeypatch)
    customer_id = store.create_customer("lab-user", "pw12")
    other = TestClient(appmod.app, cookies={"dash_auth": _cookie(customer_id)})
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})

    assert other.get("/scene_style_lab.html").status_code == 404
    page = owner.get("/scene_style_lab.html")
    assert page.status_code == 200
    assert "장면꾸미기 실데이터 시험" in page.text


def test_admin_lists_only_owned_recent_jobs(tmp_path, monkeypatch):
    store, work_root = _setup(tmp_path, monkeypatch)
    other_id = store.create_customer("other-owner", "pw12")
    _create_ready_job(store, work_root, "mine", customer_id=0)
    _create_ready_job(store, work_root, "other", customer_id=other_id)
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})

    response = owner.get("/api/admin/scene-style-lab/jobs")

    assert response.status_code == 200
    assert [row["job_id"] for row in response.json()["jobs"]] == ["mine"]


def test_create_and_save_lab_copy_never_updates_source_job(tmp_path, monkeypatch):
    store, work_root = _setup(tmp_path, monkeypatch)
    source = _create_ready_job(store, work_root)
    before = deepcopy(source)
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})

    created = owner.post("/api/admin/scene-style-lab", json={"job_id": "j1"})

    assert created.status_code == 200
    manifest = created.json()["manifest"]
    lab_id = manifest["lab_id"]
    packet = owner.get(f"/api/admin/scene-style-lab/{lab_id}")
    assert packet.status_code == 200
    assert packet.json()["context"]["scenes"][0]["caption_visible"] is False

    snapshot = dict(packet.json()["snapshot"], hookMotion="pop")
    saved = owner.put(
        f"/api/admin/scene-style-lab/{lab_id}/snapshot",
        json={"snapshot": snapshot},
    )
    assert saved.status_code == 200
    assert saved.json()["snapshot"]["hookMotion"] == "pop"
    assert Store(str(tmp_path / "lab.db")).get_mix_job("j1") == before


def test_non_admin_cannot_probe_lab_api(tmp_path, monkeypatch):
    store, _work = _setup(tmp_path, monkeypatch)
    customer_id = store.create_customer("blocked-user", "pw12")
    other = TestClient(appmod.app, cookies={"dash_auth": _cookie(customer_id)})

    assert other.get("/api/admin/scene-style-lab/jobs").status_code == 404
    assert other.post("/api/admin/scene-style-lab", json={"job_id": "missing"}).status_code == 404
    assert other.get("/api/admin/scene-style-lab/lab_000000000000").status_code == 404


def test_admin_can_queue_isolated_render(tmp_path, monkeypatch):
    from shopping_shorts import scene_style_lab

    store, work_root = _setup(tmp_path, monkeypatch)
    _create_ready_job(store, work_root)
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    created = owner.post("/api/admin/scene-style-lab", json={"job_id": "j1"}).json()
    lab_id = created["manifest"]["lab_id"]
    calls = []

    monkeypatch.setattr(
        scene_style_lab,
        "render_copy",
        lambda manifest, source_job, root: calls.append((manifest["lab_id"], source_job["job_id"], root)) or (root / "done.mp4"),
    )

    response = owner.post(f"/api/admin/scene-style-lab/{lab_id}/render")

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert calls == [(lab_id, "j1", work_root)]


def test_lab_frame_is_admin_only_and_marks_clean_signature(tmp_path, monkeypatch):
    from shopping_shorts import scene_style_lab

    store, work_root = _setup(tmp_path, monkeypatch)
    _create_ready_job(store, work_root)
    other_id = store.create_customer("frame-blocked", "pw12")
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    other = TestClient(appmod.app, cookies={"dash_auth": _cookie(other_id)})
    manifest = owner.post("/api/admin/scene-style-lab", json={"job_id": "j1"}).json()["manifest"]
    lab_id = manifest["lab_id"]
    frame = tmp_path / "frame.jpg"
    frame.write_bytes(b"jpg")
    monkeypatch.setattr(scene_style_lab, "frame_for_scene", lambda *_args: frame)

    blocked = other.get(f"/api/admin/scene-style-lab/{lab_id}/frame/0")
    response = owner.get(f"/api/admin/scene-style-lab/{lab_id}/frame/0")

    assert blocked.status_code == 404
    assert response.status_code == 200
    assert response.headers["x-clean-signature"] == manifest["clean"]["signature"]
