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
                      "performance_grade": "Normal", "channel_title": "c", "thumbnail": "",
                      "relevance_score": 80}]
    with patch("server.find_hot_clips", return_value=fake_results):
        resp = client.post("/yt/hot_clips", json={"q": "반도체 조정"})

    assert resp.status_code == 200
    assert resp.json()["results"] == fake_results


def test_hot_clips_endpoint_drops_candidates_without_relevance(client):
    fake_results = [
        {"video_id": "good", "relevance_score": 73},
        {"video_id": "junk", "relevance_score": 0},
    ]
    with patch("server.find_hot_clips", return_value=fake_results):
        resp = client.post("/yt/hot_clips", json={
            "q": "쇼핑쇼츠", "published_days": 30,
            "video_format": "shorts", "sort_by": "meaningful",
        })

    assert resp.status_code == 200
    assert resp.json()["results"] == [fake_results[0]]


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
    assert project["topic_discovery"]["mode"] == "topic"
    assert project["video_analyses"] == []

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
    assert "주제 찾기·레퍼런스 분석" in html
    assert "URL 직접 분석" in html
    assert "아스트라 주제 확정 카드" in html
    assert "장면으로 자동 나누기" in html
    assert "장면·촬영파일" in html
    assert "에보링크 AI 장면" in html
    assert "AI 영상 만들기(유료)" in html
    assert "아직 실행 버튼은 만들지 않았습니다" in html


def test_evolink_status_does_not_expose_key(monkeypatch, client):
    monkeypatch.setattr(server_module, "_yt_evolink_key", lambda: "top-secret-key")
    response = client.get("/yt/evolink/status")
    assert response.status_code == 200
    assert response.json()["configured"] is True
    assert "top-secret-key" not in response.text


def test_scene_ai_video_submit_poll_and_local_save(monkeypatch, tmp_path):
    monkeypatch.setattr(server_module, "YT_PROJECTS_DIR", str(tmp_path / "projects"))
    monkeypatch.setattr(server_module, "_yt_evolink_key", lambda: "secret")
    monkeypatch.setattr(server_module._evolink, "create_video", lambda **kwargs: {
        "id": "task-unified-123", "status": "pending", "progress": 0,
        "model": kwargs["model"], "task_info": {"estimated_time": 60},
    })
    monkeypatch.setattr(server_module._evolink, "get_task", lambda **kwargs: {
        "id": kwargs["task_id"], "status": "completed", "progress": 100,
        "results": ["https://cdn.example.com/generated.mp4"],
    })

    def fake_download(url, destination):
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        Path(destination).write_bytes(b"real-video-file")
        return 15

    monkeypatch.setattr(server_module._evolink, "download_result", fake_download)
    c = TestClient(server_module.app)
    project = c.post("/yt/projects", json={"title": "AI 장면 시험", "format": "shorts"}).json()
    project["scenes"] = [{
        "id": "scene-01", "title": "훅", "script": "첫 장면",
        "status": "waiting", "assets": [], "production_type": "ai_generated",
    }]
    c.patch(f"/yt/projects/{project['id']}", json=project)

    submitted = c.post(
        f"/yt/projects/{project['id']}/scenes/scene-01/ai-video",
        json={"prompt": "카메라가 제품으로 다가간다", "duration": 5, "quality": "720p"},
    )
    assert submitted.status_code == 202
    assert submitted.json()["task"]["task_id"] == "task-unified-123"
    assert submitted.json()["task"]["aspect_ratio"] == "9:16"

    completed = c.get(f"/yt/projects/{project['id']}/scenes/scene-01/ai-video")
    assert completed.status_code == 200
    scene = completed.json()["project"]["scenes"][0]
    assert scene["ai_video"]["asset_id"]
    assert scene["assets"][0]["source"] == "evolink"
    asset = scene["assets"][0]
    saved = c.get(f"/yt/projects/{project['id']}/assets/scene-01/{asset['id']}")
    assert saved.content == b"real-video-file"


def test_scene_ai_video_requires_server_side_key(monkeypatch, tmp_path):
    monkeypatch.setattr(server_module, "YT_PROJECTS_DIR", str(tmp_path))
    monkeypatch.setattr(server_module, "_yt_evolink_key", lambda: "")
    c = TestClient(server_module.app)
    project = c.post("/yt/projects", json={"title": "키 없음"}).json()
    response = c.post(
        f"/yt/projects/{project['id']}/scenes/scene-01/ai-video",
        json={"prompt": "장면"},
    )
    assert response.status_code == 503
    assert "EVOLINK_API_KEY" in response.json()["error"]


def test_topic_analysis_stream_saves_cards_and_decision(monkeypatch, tmp_path):
    monkeypatch.setattr(server_module, "YT_PROJECTS_DIR", str(tmp_path / "projects"))
    monkeypatch.setattr(server_module, "YT_ANALYSIS_CACHE_DIR", str(tmp_path / "cache"))

    class FakeTeardown:
        @staticmethod
        def parse_video_id(value):
            return "abc123DEF45" if "abc123DEF45" in value else ""

        @staticmethod
        def teardown(video_id, title, channel, stats, context):
            return {
                "video_id": video_id, "url": "https://youtu.be/abc123DEF45",
                "title": title or "성과 영상", "channel": channel or "채널",
                "thumbnail": "https://example.com/t.jpg", "metrics": stats,
                "click_device": {"title_formula": "대상+문제"},
                "hook": {"type": "공감", "evidence": [{"at": "00:00:03", "quote": "근거"}]},
                "story_beats": [], "viewer_needs": [], "visual_grammar": {},
                "strengths": [], "risks": [],
            }

        @staticmethod
        def synthesize(cards, context):
            return {
                "topic": "확정 주제", "audience": context["audience"],
                "promise": "변화", "why_now": "지금", "differentiation": "차별점",
                "score": {"total": 82}, "decisions": [], "titles": [],
                "thumbnails": [], "hooks": [], "outline": [],
                "research_tasks": ["숫자 확인"], "needed_assets": [], "guardrails": [],
            }

    monkeypatch.setattr(server_module, "_teardown", FakeTeardown)
    c = TestClient(server_module.app)
    project = c.post("/yt/projects", json={"title": "주제 분석 시험"}).json()
    response = c.post(
        f"/yt/projects/{project['id']}/topic/analyze",
        json={
            "mode": "urls", "seed_topic": "AI 직원", "audience": "1인 사업자",
            "videos": ["https://youtu.be/abc123DEF45"],
        },
    )
    assert response.status_code == 200
    assert '"type": "video_done"' in response.text
    assert '"type": "done"' in response.text

    saved = c.get(f"/yt/projects/{project['id']}").json()
    assert saved["video_analyses"][0]["video_id"] == "abc123DEF45"
    assert saved["topic_discovery"]["astra_decision"]["topic"] == "확정 주제"
    assert saved["idea"] == "확정 주제"


def test_topic_analysis_rejects_non_youtube_input(monkeypatch, tmp_path):
    monkeypatch.setattr(server_module, "YT_PROJECTS_DIR", str(tmp_path))
    c = TestClient(server_module.app)
    project = c.post("/yt/projects", json={"title": "잘못된 주소"}).json()
    response = c.post(
        f"/yt/projects/{project['id']}/topic/analyze",
        json={"videos": ["https://example.com/not-youtube"]},
    )
    assert response.status_code == 400
