from datetime import datetime, timezone

from fastapi.testclient import TestClient

from shopping_shorts import app as appmod
from shopping_shorts import scene_style_lab
from shopping_shorts.store import Store


def _cookie(customer_id):
    expires = int(datetime.now(timezone.utc).timestamp()) + 3600
    return appmod._sign_session(customer_id, expires)


def _lab(tmp_path, monkeypatch):
    db = tmp_path / "lab.db"
    work = tmp_path / "jobs"
    monkeypatch.setattr(appmod, "DB_PATH", str(db))
    monkeypatch.setattr(appmod, "_MIX_WORK_DIR", work)
    monkeypatch.setattr(appmod, "_AUTH_ON", True)
    monkeypatch.setattr(appmod, "DASH_SECRET", "lab-landing-secret")
    store = Store(str(db))
    store.ensure_paywall_schema()
    store.create_mix_job("source", [], 20, "free", customer_id=0)
    manifest = {
        "version": 1,
        "lab_id": "lab_000000000001",
        "source_job_id": "source",
        "outputs": {},
    }
    target = scene_style_lab.lab_dir(work, manifest["lab_id"])
    target.mkdir(parents=True)
    video = target / "lab-final.mp4"
    video.write_bytes(b"exact-lab-video")
    manifest["outputs"]["mp4"] = str(video)
    scene_style_lab.write_manifest(target, manifest)
    return work, manifest, video


def test_lab_landing_is_private_and_streams_exact_lab_output(tmp_path, monkeypatch):
    _work, manifest, video = _lab(tmp_path, monkeypatch)
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    outsider_id = Store(str(tmp_path / "lab.db")).create_customer("outsider", "pw12")
    outsider = TestClient(appmod.app, cookies={"dash_auth": _cookie(outsider_id)})

    assert outsider.get(f"/scene-style-lab/{manifest['lab_id']}").status_code == 404
    assert outsider.get(f"/api/admin/scene-style-lab/{manifest['lab_id']}/video").status_code == 404

    page = owner.get(f"/scene-style-lab/{manifest['lab_id']}")
    response = owner.get(f"/api/admin/scene-style-lab/{manifest['lab_id']}/video")

    assert page.status_code == 200
    assert page.headers["x-robots-tag"] == "noindex, nofollow, noarchive"
    assert "/api/share/" not in page.text
    assert response.status_code == 200
    assert response.content == video.read_bytes()
    assert response.headers["x-scene-style-lab"] == manifest["lab_id"]
    assert response.headers["cache-control"] == "no-store"
    partial = owner.get(
        f"/api/admin/scene-style-lab/{manifest['lab_id']}/video",
        headers={"Range": "bytes=0-4"},
    )
    assert partial.status_code == 206
    assert partial.content == b"exact"


def test_lab_video_rejects_manifest_output_outside_its_lab_folder(tmp_path, monkeypatch):
    work, manifest, _video = _lab(tmp_path, monkeypatch)
    outside = tmp_path / "other.mp4"
    outside.write_bytes(b"must-not-leak")
    manifest["outputs"]["mp4"] = str(outside)
    scene_style_lab.write_manifest(scene_style_lab.lab_dir(work, manifest["lab_id"]), manifest)
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})

    response = owner.get(f"/api/admin/scene-style-lab/{manifest['lab_id']}/video")

    assert response.status_code == 409
    assert response.content != outside.read_bytes()
