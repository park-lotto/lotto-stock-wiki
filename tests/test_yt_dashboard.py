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
