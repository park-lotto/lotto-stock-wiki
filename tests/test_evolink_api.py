from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from dashboard import evolink_api


def response(status=200, data=None, text=""):
    r = Mock()
    r.status_code = status
    r.ok = status < 400
    r.json.return_value = data or {}
    r.text = text
    return r


def test_create_video_uses_bearer_and_official_async_endpoint():
    accepted = response(data={"id": "task-unified-123", "status": "pending", "model": "wan2.7-text-to-video"})
    with patch("dashboard.evolink_api.requests.request", return_value=accepted) as request:
        task = evolink_api.create_video(api_key="secret", prompt="카메라가 제품으로 다가간다")

    assert task["id"] == "task-unified-123"
    _, url = request.call_args.args
    assert url.endswith("/v1/videos/generations")
    assert request.call_args.kwargs["headers"]["Authorization"] == "Bearer secret"
    assert request.call_args.kwargs["json"]["prompt_extend"] is False


def test_create_video_rejects_invalid_paid_request_before_network():
    with patch("dashboard.evolink_api.requests.request") as request:
        with pytest.raises(evolink_api.EvoLinkError, match="2~15초"):
            evolink_api.create_video(api_key="secret", prompt="장면", duration=60)
    request.assert_not_called()


def test_get_task_hides_auth_detail():
    denied = response(status=401, data={"error": "raw provider secret detail"})
    with patch("dashboard.evolink_api.requests.request", return_value=denied):
        with pytest.raises(evolink_api.EvoLinkError, match="올바르지 않거나 권한"):
            evolink_api.get_task(api_key="bad", task_id="task-unified-123")


def test_download_result_saves_atomically(tmp_path):
    r = Mock()
    r.ok = True
    r.iter_content.return_value = [b"video-", b"bytes"]
    r.__enter__ = Mock(return_value=r)
    r.__exit__ = Mock(return_value=False)
    dest = tmp_path / "clip.mp4"
    with patch("dashboard.evolink_api.requests.get", return_value=r):
        size = evolink_api.download_result("https://cdn.example.com/clip.mp4", dest)
    assert size == 11
    assert dest.read_bytes() == b"video-bytes"
    assert not Path(str(dest) + ".part").exists()
