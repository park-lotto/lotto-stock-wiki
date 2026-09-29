import pytest

from shopping_shorts import higgsfield_api as hf


class FakeResponse:
    def __init__(self, data, status_code=200, chunks=None):
        self._data = data
        self.status_code = status_code
        self._chunks = chunks or []

    def json(self):
        return self._data

    def iter_content(self, chunk_size):
        yield from self._chunks

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _keys(monkeypatch):
    monkeypatch.setenv("HIGGSFIELD_API_KEY_ID", "key-id")
    monkeypatch.setenv("HIGGSFIELD_API_KEY_SECRET", "key-secret")


def test_submit_uses_server_credentials_and_fixed_safe_shape(monkeypatch):
    _keys(monkeypatch)
    seen = {}

    def post(url, **kwargs):
        seen.update(url=url, **kwargs)
        return FakeResponse({"request_id": "req-1", "status_url":
                             "https://api.higgsfield.ai/requests/req-1/status"})

    result = hf.submit_image_to_video("https://example.com/product.jpg", "slow orbit", post=post)

    assert seen["url"] == hf.MODEL_URL
    assert seen["headers"]["Authorization"] == "Key key-id:key-secret"
    assert seen["json"] == {
        "image_url": "https://example.com/product.jpg",
        "prompt": "slow orbit",
        "duration": 5,
        "resolution": "720p",
        "generate_audio": False,
    }
    assert result["request_id"] == "req-1"
    assert result["state"] == "running"


def test_wait_for_result_polls_then_reads_video(monkeypatch):
    _keys(monkeypatch)
    replies = iter([
        FakeResponse({"request_id": "req-1", "status": "running"}),
        FakeResponse({"request_id": "req-1", "status": "completed",
                      "video": {"url": "https://cdn.example.com/out.mp4"}}),
    ])

    result = hf.wait_for_result({
        "request_id": "req-1",
        "status_url": "https://api.higgsfield.ai/requests/req-1/status",
        "state": "running",
    }, get=lambda *_a, **_k: next(replies), sleep=lambda _n: None, poll_seconds=0)

    assert result["state"] == "done"
    assert result["video_url"] == "https://cdn.example.com/out.mp4"


@pytest.mark.parametrize("url", [
    "http://example.com/a.jpg",
    "https://localhost/a.jpg",
    "https://127.0.0.1/a.jpg",
    "https://169.254.169.254/latest/meta-data",
])
def test_input_url_rejects_insecure_or_private_addresses(url):
    with pytest.raises(hf.HiggsfieldError):
        hf.validate_public_https_url(url)


def test_status_url_cannot_send_credentials_to_another_host(monkeypatch):
    _keys(monkeypatch)
    with pytest.raises(hf.HiggsfieldError):
        hf.wait_for_result({
            "request_id": "req-1", "state": "running",
            "status_url": "https://evil.example/steal",
        }, get=lambda *_a, **_k: None)


def test_download_is_atomic(monkeypatch, tmp_path):
    monkeypatch.setattr(hf.socket, "getaddrinfo", lambda *_a, **_k: [
        (hf.socket.AF_INET, hf.socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
    ])
    out = tmp_path / "out.mp4"
    hf.download_video("https://cdn.example.com/out.mp4", out,
                      get=lambda *_a, **_k: FakeResponse({}, chunks=[b"abc", b"def"]))
    assert out.read_bytes() == b"abcdef"
    assert not (tmp_path / "out.mp4.part").exists()
