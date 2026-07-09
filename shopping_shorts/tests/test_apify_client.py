"""apify_client 계정 로테이션 로직 테스트.

배경: (1) Apify run-sync-get-dataset-items의 서버측 ~5분 타임아웃(대량배치에서
408) 사고, (2) 실행 도중 계정 소진으로 전체 배치가 중단된 사고 — 두 프로덕션
장애를 고치며 만든 로테이션 로직(_start_run 거부 시 + 실행 도중 실패 시 모두
다음 토큰으로 "처음부터" 재시도)을 고정한다.
"""
import requests
import pytest

from shopping_shorts import apify_client


class FakeResponse:
    """requests.Response 흉내: status_code / json() / raise_for_status()."""

    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = {} if json_data is None else json_data

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


def _token_from_headers(headers):
    return headers["Authorization"].removeprefix("Bearer ")


def _is_run_status_url(url):
    return "actor-runs" in url


def _is_dataset_url(url):
    return "datasets" in url


@pytest.fixture(autouse=True)
def isolate_key_state(monkeypatch, tmp_path):
    """모든 테스트에서 실제 data/apify_key_index.json을 절대 건드리지 않는다."""
    monkeypatch.setattr(apify_client, "_KEY_STATE_PATH", tmp_path / "apify_key_index.json")


def test_fetch_reels_happy_path_single_token(monkeypatch):
    monkeypatch.setattr(apify_client, "APIFY_TOKENS", ["tok1"])

    def fake_post(url, headers=None, json=None, timeout=None):
        assert _token_from_headers(headers) == "tok1"
        return FakeResponse(200, {"data": {"id": "run1", "status": "SUCCEEDED",
                                            "defaultDatasetId": "ds1"}})

    def fake_get(url, headers=None, timeout=None):
        assert _is_dataset_url(url)
        return FakeResponse(200, [{"id": "reel1"}, {"id": "reel2"}])

    monkeypatch.setattr(apify_client.requests, "post", fake_post)
    monkeypatch.setattr(apify_client.requests, "get", fake_get)

    items = apify_client.fetch_reels(["user1"], poll_interval=0.01, timeout=5)

    assert items == [{"id": "reel1"}, {"id": "reel2"}]
    # 로테이션이 일어나지 않았으므로(시작 인덱스=성공 인덱스) 인덱스 파일은 갱신되지 않는다.
    assert apify_client._load_key_index() == 0


def test_fetch_reels_rotates_on_start_rejection(monkeypatch):
    monkeypatch.setattr(apify_client, "APIFY_TOKENS", ["tok1", "tok2"])
    post_calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        token = _token_from_headers(headers)
        post_calls.append(token)
        if token == "tok1":
            return FakeResponse(402, {"error": "usage exhausted"})
        return FakeResponse(200, {"data": {"id": "run2", "status": "SUCCEEDED",
                                            "defaultDatasetId": "ds2"}})

    def fake_get(url, headers=None, timeout=None):
        assert _is_dataset_url(url)
        return FakeResponse(200, [{"id": "reel-from-tok2"}])

    monkeypatch.setattr(apify_client.requests, "post", fake_post)
    monkeypatch.setattr(apify_client.requests, "get", fake_get)

    items = apify_client.fetch_reels(["user1"], poll_interval=0.01, timeout=5)

    assert items == [{"id": "reel-from-tok2"}]
    assert post_calls == ["tok1", "tok2"]
    # 성공한 토큰(tok2, index 1)이 영구 저장되어 다음 호출은 여기서 시작한다.
    assert apify_client._load_key_index() == 1


def test_fetch_reels_rotates_on_mid_run_failure(monkeypatch):
    """token0은 시작에 성공하지만 run이 도중에 FAILED로 끝난다 → token1로
    "전체를 처음부터" 재시도해야 한다(단순히 예외를 삼키는 게 아니라 새 run 시작)."""
    monkeypatch.setattr(apify_client, "APIFY_TOKENS", ["tok1", "tok2"])
    post_calls = []
    poll_calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        token = _token_from_headers(headers)
        post_calls.append(token)
        if token == "tok1":
            # 시작은 성공(200)하지만 아직 RUNNING → 폴링이 필요하다.
            return FakeResponse(200, {"data": {"id": "run1", "status": "RUNNING"}})
        # tok2는 처음부터 다시 시작한 완전히 새로운 run → 바로 SUCCEEDED.
        return FakeResponse(200, {"data": {"id": "run2", "status": "SUCCEEDED",
                                            "defaultDatasetId": "ds2"}})

    def fake_get(url, headers=None, timeout=None):
        if _is_run_status_url(url):
            poll_calls.append(url)
            # tok1의 run은 폴링 결과 FAILED로 끝난다.
            return FakeResponse(200, {"data": {"id": "run1", "status": "FAILED",
                                                "defaultDatasetId": None}})
        assert _is_dataset_url(url)
        return FakeResponse(200, [{"id": "reel-from-tok2-retry"}])

    monkeypatch.setattr(apify_client.requests, "post", fake_post)
    monkeypatch.setattr(apify_client.requests, "get", fake_get)

    items = apify_client.fetch_reels(["user1"], poll_interval=0.01, timeout=5)

    assert items == [{"id": "reel-from-tok2-retry"}]
    # tok1, tok2 각각에 대해 _start_run이 새로 호출됨(처음부터 재시도 증거).
    assert post_calls == ["tok1", "tok2"]
    assert len(poll_calls) == 1
    assert apify_client._load_key_index() == 1


def test_fetch_reels_all_tokens_exhausted_raises(monkeypatch):
    monkeypatch.setattr(apify_client, "APIFY_TOKENS", ["tok1", "tok2", "tok3"])

    def fake_post(url, headers=None, json=None, timeout=None):
        return FakeResponse(402, {"error": "usage exhausted"})

    monkeypatch.setattr(apify_client.requests, "post", fake_post)
    # get은 호출되지 않아야 한다(모든 토큰이 시작 단계에서 거부됨).
    monkeypatch.setattr(apify_client.requests, "get",
                         lambda *a, **kw: pytest.fail("get should not be called"))

    with pytest.raises(RuntimeError, match="3"):
        apify_client.fetch_reels(["user1"], poll_interval=0.01, timeout=5)

    # 전부 실패했으므로 인덱스 파일도 갱신되지 않는다.
    assert apify_client._load_key_index() == 0


def test_fetch_reels_splits_large_batch_into_chunks(monkeypatch):
    """443채널을 한 run에 몰아넣으면 액터가 ~124번째에서 조용히 나머지를
    누락시키는 실제 사고(2026-07-09, 443개 중 26개만 처리됨)가 있었다 —
    chunk_size 단위로 나눠 여러 run을 순차로 돌려야 한다."""
    monkeypatch.setattr(apify_client, "APIFY_TOKENS", ["tok1"])
    payload_usernames_per_call = []

    def fake_post(url, headers=None, json=None, timeout=None):
        payload_usernames_per_call.append(list(json["username"]))
        run_id = f"run{len(payload_usernames_per_call)}"
        return FakeResponse(200, {"data": {"id": run_id, "status": "SUCCEEDED",
                                            "defaultDatasetId": f"ds-{run_id}"}})

    def fake_get(url, headers=None, timeout=None):
        assert _is_dataset_url(url)
        return FakeResponse(200, [{"batch": len(payload_usernames_per_call)}])

    monkeypatch.setattr(apify_client.requests, "post", fake_post)
    monkeypatch.setattr(apify_client.requests, "get", fake_get)

    usernames = [f"user{i}" for i in range(95)]
    items = apify_client.fetch_reels(usernames, poll_interval=0.01, timeout=5, chunk_size=40)

    # 95개를 40 단위로 나누면 40+40+15 = 3번의 별도 run이 있어야 한다.
    assert len(payload_usernames_per_call) == 3
    assert [len(c) for c in payload_usernames_per_call] == [40, 40, 15]
    # 청크가 원래 순서를 그대로, 겹치거나 빠짐없이 나눴는지 확인.
    assert payload_usernames_per_call[0] + payload_usernames_per_call[1] + payload_usernames_per_call[2] == usernames
    # 청크마다 결과가 합쳐져서 반환된다.
    assert len(items) == 3


def test_fetch_reels_explicit_token_bypasses_rotation(monkeypatch):
    # APIFY_TOKENS를 일부러 빈 리스트로 둔다 — 만약 코드가 이걸 참조하면
    # "tokens가 비어있음" RuntimeError로 즉시 실패해야 하므로, 성공한다는 것
    # 자체가 rotation pool을 건드리지 않았다는 증거다.
    monkeypatch.setattr(apify_client, "APIFY_TOKENS", [])
    post_calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        token = _token_from_headers(headers)
        post_calls.append(token)
        assert token == "explicit-token"
        return FakeResponse(200, {"data": {"id": "run-explicit", "status": "SUCCEEDED",
                                            "defaultDatasetId": "ds-explicit"}})

    def fake_get(url, headers=None, timeout=None):
        assert _is_dataset_url(url)
        return FakeResponse(200, [{"id": "reel-explicit"}])

    monkeypatch.setattr(apify_client.requests, "post", fake_post)
    monkeypatch.setattr(apify_client.requests, "get", fake_get)

    items = apify_client.fetch_reels(["user1"], token="explicit-token",
                                      poll_interval=0.01, timeout=5)

    assert items == [{"id": "reel-explicit"}]
    assert post_calls == ["explicit-token"]
    # 명시적 토큰 경로는 persisted index를 절대 읽거나 쓰지 않는다.
    assert not apify_client._KEY_STATE_PATH.exists()


def test_fetch_single_reel_uses_direct_urls_payload(monkeypatch):
    monkeypatch.setattr(apify_client, "APIFY_TOKENS", ["tok1"])
    posted_payloads = []

    def fake_post(url, headers=None, json=None, timeout=None):
        posted_payloads.append(json)
        return FakeResponse(200, {"data": {"id": "run1", "status": "SUCCEEDED",
                                            "defaultDatasetId": "ds1"}})

    def fake_get(url, headers=None, timeout=None):
        assert _is_dataset_url(url)
        return FakeResponse(200, [{"shortcode": "abc123", "videoUrl": "https://cdn/v.mp4"}])

    monkeypatch.setattr(apify_client.requests, "post", fake_post)
    monkeypatch.setattr(apify_client.requests, "get", fake_get)

    result = apify_client.fetch_single_reel(
        "https://www.instagram.com/reel/abc123/", poll_interval=0.01, timeout=5
    )

    assert result == {"shortcode": "abc123", "videoUrl": "https://cdn/v.mp4"}
    assert posted_payloads == [{
        "directUrls": ["https://www.instagram.com/reel/abc123/"],
        "resultsLimit": 1,
        "skipPinnedPosts": True,
    }]


def test_fetch_single_reel_no_result_returns_none(monkeypatch):
    monkeypatch.setattr(apify_client, "APIFY_TOKENS", ["tok1"])

    def fake_post(url, headers=None, json=None, timeout=None):
        return FakeResponse(200, {"data": {"id": "run1", "status": "SUCCEEDED",
                                            "defaultDatasetId": "ds1"}})

    def fake_get(url, headers=None, timeout=None):
        return FakeResponse(200, [])  # 비공개 계정·삭제된 게시물 등

    monkeypatch.setattr(apify_client.requests, "post", fake_post)
    monkeypatch.setattr(apify_client.requests, "get", fake_get)

    result = apify_client.fetch_single_reel(
        "https://www.instagram.com/reel/gone/", poll_interval=0.01, timeout=5
    )

    assert result is None


def test_fetch_single_reel_rotates_on_start_rejection(monkeypatch):
    monkeypatch.setattr(apify_client, "APIFY_TOKENS", ["tok1", "tok2"])
    post_calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        token = _token_from_headers(headers)
        post_calls.append(token)
        if token == "tok1":
            return FakeResponse(402, {"error": "usage exhausted"})
        return FakeResponse(200, {"data": {"id": "run2", "status": "SUCCEEDED",
                                            "defaultDatasetId": "ds2"}})

    def fake_get(url, headers=None, timeout=None):
        return FakeResponse(200, [{"shortcode": "xyz"}])

    monkeypatch.setattr(apify_client.requests, "post", fake_post)
    monkeypatch.setattr(apify_client.requests, "get", fake_get)

    result = apify_client.fetch_single_reel(
        "https://www.instagram.com/reel/xyz/", poll_interval=0.01, timeout=5
    )

    assert result == {"shortcode": "xyz"}
    assert post_calls == ["tok1", "tok2"]
