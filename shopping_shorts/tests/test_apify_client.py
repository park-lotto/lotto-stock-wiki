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
            # 실제 requests처럼 예외에 응답을 붙인다 — _run_with_rotation이
            # e.response.status_code로 로테이션 여부를 가르므로 이게 없으면
            # 프로덕션(403 재발생)을 재현하지 못한다(2026-07-25).
            err = requests.HTTPError(f"{self.status_code} error")
            err.response = self
            raise err


def _token_from_headers(headers):
    return headers["Authorization"].removeprefix("Bearer ")


def _raw(code):
    """apidojo 액터가 실제로 주는 모양의 원본 아이템 (2026-08-10).

    fetch_reels는 2026-07-13(커밋 2b859d1dd)에 apidojo~instagram-scraper-api로
    갈아타면서 `_normalize_apidojo_item`으로 **10키 스키마로 정규화해서** 돌려준다.
    그런데 이 파일의 테스트들은 그 전 동작(원본 그대로 통과)을 기대한 채 남아 있어
    6건이 계속 실패했다 — 코드가 바뀌었는데 테스트가 안 따라온 것이다.

    여기 테스트들의 진짜 관심사는 **토큰 로테이션**이지 payload 모양이 아니므로,
    아이템은 실제 필드명(code)으로 만들고 검증은 정규화 결과의 shortcode로 한다.
    """
    return {"code": code}


def _codes(items):
    """정규화된 결과에서 식별자만 뽑는다(원본 code → shortcode로 매핑됨)."""
    return [i["shortcode"] for i in items]


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
        return FakeResponse(200, [_raw("reel1"), _raw("reel2")])

    monkeypatch.setattr(apify_client.requests, "post", fake_post)
    monkeypatch.setattr(apify_client.requests, "get", fake_get)

    items = apify_client.fetch_reels(["user1"], poll_interval=0.01, timeout=5)

    assert _codes(items) == ["reel1", "reel2"]
    # 정규화가 실제로 걸렸는지도 같이 고정한다(ownerUsername은 요청한 계정으로 채워진다).
    assert all(i["ownerUsername"] == "user1" for i in items)
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
        return FakeResponse(200, [_raw("reel-from-tok2")])

    monkeypatch.setattr(apify_client.requests, "post", fake_post)
    monkeypatch.setattr(apify_client.requests, "get", fake_get)

    items = apify_client.fetch_reels(["user1"], poll_interval=0.01, timeout=5)

    assert _codes(items) == ["reel-from-tok2"]
    assert post_calls == ["tok1", "tok2"]
    # 성공한 토큰(tok2, index 1)이 영구 저장되어 다음 호출은 여기서 시작한다.
    assert apify_client._load_key_index() == 1


def test_fetch_reels_rotates_on_403_monthly_limit(monkeypatch):
    """FREE 계정이 월 $5 한도를 넘기면 유료 렌탈 액터(apidojo)가 403
    'Monthly usage hard limit exceeded'를 뱉는다(2026-07-25 실측 실사고). 403은
    시작 거부(런 미생성=무과금)이므로 401/402/429와 똑같이 다음 토큰으로
    로테이션해야 한다 — 안 그러면 아직 예산이 남은 STARTER 토큰을 써보지도 못하고
    인스타 '지금 수집'이 통째로 403으로 즉사한다."""
    monkeypatch.setattr(apify_client, "APIFY_TOKENS", ["free-maxed", "starter-ok"])
    post_calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        token = _token_from_headers(headers)
        post_calls.append(token)
        if token == "free-maxed":
            return FakeResponse(403, {"error": {"type": "platform-feature-disabled",
                                                "message": "Monthly usage hard limit exceeded"}})
        return FakeResponse(200, {"data": {"id": "run-starter", "status": "SUCCEEDED",
                                            "defaultDatasetId": "ds-starter"}})

    def fake_get(url, headers=None, timeout=None):
        assert _is_dataset_url(url)
        return FakeResponse(200, [_raw("reel-from-starter")])

    monkeypatch.setattr(apify_client.requests, "post", fake_post)
    monkeypatch.setattr(apify_client.requests, "get", fake_get)

    items = apify_client.fetch_reels(["user1"], poll_interval=0.01, timeout=5)

    assert len(items) == 1 and items[0]["ownerUsername"] == "user1"  # starter가 준 릴 1개
    assert post_calls == ["free-maxed", "starter-ok"]   # 403에서 멈추지 않고 넘어감
    assert apify_client._load_key_index() == 1           # 성공 토큰 저장


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
        return FakeResponse(200, [_raw("reel-from-tok2-retry")])

    monkeypatch.setattr(apify_client.requests, "post", fake_post)
    monkeypatch.setattr(apify_client.requests, "get", fake_get)

    items = apify_client.fetch_reels(["user1"], poll_interval=0.01, timeout=5)

    assert _codes(items) == ["reel-from-tok2-retry"]
    # tok1, tok2 각각에 대해 _start_run이 새로 호출됨(처음부터 재시도 증거).
    assert post_calls == ["tok1", "tok2"]
    assert len(poll_calls) == 1
    assert apify_client._load_key_index() == 1


def test_fetch_reels_all_tokens_exhausted_returns_empty(monkeypatch):
    """토큰이 전부 소진되면 그 채널은 **빈 리스트**로 끝난다(예외를 올리지 않는다).

    2026-07-13 apidojo 전환에서 fetch_reels가 **채널당 run 1개를 병렬로** 돌리게
    바뀌면서 `except RuntimeError: return []`가 들어갔다(apify_client.py:231).
    의도는 명확하다 — 채널 하나가 실패했다고 배치 전체(수백 채널)를 죽이지 않는다.
    옛 테스트는 전환 전 동작(RuntimeError 전파)을 기대해 계속 실패했다.

    ★단, '조용히 빈 값'이 되는 자리이므로 **모든 토큰을 실제로 시도했는지**를
    같이 고정한다. 안 그러면 첫 토큰에서 포기해도 이 테스트는 통과해버린다.
    """
    monkeypatch.setattr(apify_client, "APIFY_TOKENS", ["tok1", "tok2", "tok3"])
    tried = []

    def fake_post(url, headers=None, json=None, timeout=None):
        tried.append(_token_from_headers(headers))
        return FakeResponse(402, {"error": "usage exhausted"})

    monkeypatch.setattr(apify_client.requests, "post", fake_post)
    # get은 호출되지 않아야 한다(모든 토큰이 시작 단계에서 거부됨).
    monkeypatch.setattr(apify_client.requests, "get",
                         lambda *a, **kw: pytest.fail("get should not be called"))

    items = apify_client.fetch_reels(["user1"], poll_interval=0.01, timeout=5)

    assert items == []
    assert tried == ["tok1", "tok2", "tok3"]   # 3개 전부 시도했다(조용히 1개만 쓰지 않았다)
    # 전부 실패했으므로 인덱스 파일도 갱신되지 않는다.
    assert apify_client._load_key_index() == 0


def test_fetch_reels_runs_one_job_per_channel_and_loses_none(monkeypatch):
    """채널을 한 run에 몰아넣지 않는다 — **채널당 run 1개**로 쪼개 돌린다.

    지키려는 사고는 그대로다: 443채널을 한 run에 몰아넣었더니 액터가 ~124번째에서
    조용히 나머지를 누락시켰다(2026-07-09, 443개 중 26개만 처리). 옛 구현은 이걸
    chunk_size 단위 순차 run으로 막았고, 2026-07-13 apidojo 전환에서는 아예
    **채널당 startUrls run 1개 + 스레드풀 병렬**로 바뀌었다(chunk_size는 미사용 인자로만 남음).
    옛 테스트는 없어진 `json["username"]` 청크를 들여다봐 KeyError로 실패했다.

    그래서 검사 대상을 '청크 모양'이 아니라 **누락이 없는가**로 바꾼다 — 이게 원래 목적이다.
    """
    monkeypatch.setattr(apify_client, "APIFY_TOKENS", ["tok1"])
    started_urls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        # 전환 후 payload는 채널 URL 하나짜리 startUrls다.
        started_urls.append(json["startUrls"][0]["url"])
        run_id = f"run{len(started_urls)}"
        return FakeResponse(200, {"data": {"id": run_id, "status": "SUCCEEDED",
                                            "defaultDatasetId": f"ds-{run_id}"}})

    def fake_get(url, headers=None, timeout=None):
        assert _is_dataset_url(url)
        # 어느 채널의 데이터셋인지는 중요치 않다 — 채널마다 1건씩 준다고 본다.
        return FakeResponse(200, [_raw("reel")])

    monkeypatch.setattr(apify_client.requests, "post", fake_post)
    monkeypatch.setattr(apify_client.requests, "get", fake_get)

    usernames = [f"user{i}" for i in range(95)]
    items = apify_client.fetch_reels(usernames, poll_interval=0.01, timeout=5)

    # 95채널 → run 95개. 한 run에 몰아넣어 뒤쪽이 잘리는 일이 없다.
    assert len(started_urls) == 95
    # 요청한 채널이 하나도 빠지지 않았다(순서는 스레드풀이라 보장하지 않으므로 집합으로).
    assert {u.rstrip("/").split("/")[-2] for u in started_urls} == set(usernames)
    # 채널당 1건씩 전부 합쳐져 돌아온다 — 조용한 누락이 없다는 뜻.
    assert len(items) == 95


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
        return FakeResponse(200, [_raw("reel-explicit")])

    monkeypatch.setattr(apify_client.requests, "post", fake_post)
    monkeypatch.setattr(apify_client.requests, "get", fake_get)

    items = apify_client.fetch_reels(["user1"], token="explicit-token",
                                      poll_interval=0.01, timeout=5)

    assert _codes(items) == ["reel-explicit"]
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
        "username": ["https://www.instagram.com/reel/abc123/"],
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
