import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard"))

import server as server_module


@pytest.fixture
def client():
    return TestClient(server_module.app)


def test_hot_clips_endpoint_returns_results(client):
    fake_results = [{"video_id": "v1", "title": "테스트", "view_count": 1000,
                      "view_pct_above_avg": 50.0, "contribution_grade": "Normal",
                      "performance_grade": "Normal", "channel_title": "c", "thumbnail": ""}]
    with patch("server.find_hot_clips", return_value=fake_results):
        resp = client.post("/yt/hot_clips", json={"q": "반도체 조정"})

    assert resp.status_code == 200
    assert resp.json()["results"] == fake_results


def test_generate_plan_streams_sse_events(client):
    def fake_events(idea, references, pipeline_id):
        yield {"type": "step", "id": "plan", "status": "running", "attempt": 1}
        yield {"type": "done", "pid": "test789", "plan_text": "# 완성", "qc_score": 8}

    with patch("server.run_plan_stage", side_effect=fake_events):
        resp = client.post("/yt/generate_plan", json={"idea": "반도체 조정", "references": []})

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    body = resp.text
    assert '"type": "step"' in body or '"type":"step"' in body
    assert '"type": "done"' in body or '"type":"done"' in body


def test_video_project_create_update_and_list(monkeypatch, tmp_path):
    monkeypatch.setattr(server_module, "YT_PROJECTS_DIR", str(tmp_path))
    c = TestClient(server_module.app)

    made = c.post("/yt/projects", json={
        "title": "숏템메이커 3편", "format": "vsl", "target_minutes": 10,
    })
    assert made.status_code == 201
    project = made.json()
    assert project["title"] == "숏템메이커 3편"
    assert project["scenes"] == []

    project["script_text"] = "## S1 — 훅\n첫 문장"
    project["scenes"] = [{
        "id": "scene-01", "title": "S1 — 훅", "script": "첫 문장",
        "status": "waiting", "assets": [],
    }]
    saved = c.patch(f"/yt/projects/{project['id']}", json=project)
    assert saved.status_code == 200
    assert saved.json()["scenes"][0]["title"] == "S1 — 훅"

    listed = c.get("/yt/projects").json()["projects"]
    assert listed[0]["id"] == project["id"]
    assert listed[0]["scene_count"] == 1


def test_video_project_asset_upload_and_read(monkeypatch, tmp_path):
    monkeypatch.setattr(server_module, "YT_PROJECTS_DIR", str(tmp_path))
    c = TestClient(server_module.app)
    project = c.post("/yt/projects", json={"title": "업로드 시험"}).json()
    project["scenes"] = [{
        "id": "scene-01", "title": "훅", "script": "대사",
        "status": "waiting", "assets": [],
    }]
    c.patch(f"/yt/projects/{project['id']}", json=project)

    uploaded = c.post(
        f"/yt/projects/{project['id']}/assets",
        data={"scene_id": "scene-01"},
        files={"file": ("voice.mp3", b"fake-mp3", "audio/mpeg")},
    )
    assert uploaded.status_code == 201
    asset = uploaded.json()["asset"]
    assert asset["name"] == "voice.mp3"
    assert asset["size"] == 8

    downloaded = c.get(
        f"/yt/projects/{project['id']}/assets/scene-01/{asset['id']}"
    )
    assert downloaded.status_code == 200
    assert downloaded.content == b"fake-mp3"

    rejected = c.post(
        f"/yt/projects/{project['id']}/assets",
        data={"scene_id": "../../outside"},
        files={"file": ("voice.mp3", b"fake-mp3", "audio/mpeg")},
    )
    assert rejected.status_code == 400


def test_yt_page_is_persistent_project_workflow(client):
    html = client.get("/yt").text
    assert "새 영상 프로젝트" in html
    assert "장면으로 자동 나누기" in html
    assert "장면·촬영파일" in html
    assert "아직 실행 버튼은 만들지 않았습니다" in html
