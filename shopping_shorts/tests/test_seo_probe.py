import pytest

from shopping_shorts import seo_probe
from shopping_shorts.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "p.db"))


class _FakeResp:
    def __init__(self, payload, status=200):
        self._p, self.status_code = payload, status

    def json(self):
        return self._p


def _search_payload(titles):
    return {"items": [
        {"id": {"videoId": f"v{i}"},
         "snippet": {"channelId": f"c{i}", "channelTitle": f"ch{i}", "title": t,
                     "description": "", "thumbnails": {}, "publishedAt": "2026-07-01T00:00:00Z"}}
        for i, t in enumerate(titles)]}


def _videos_payload(n, views):
    return {"items": [{"id": f"v{i}", "statistics": {"viewCount": str(views)}} for i in range(n)]}


def _channels_payload(n, subs):
    return {"items": [{"id": f"c{i}", "statistics": {"subscriberCount": str(subs)}} for i in range(n)]}


def _fake_get(search, videos, channels, calls=None):
    """URL로 어느 API인지 갈라 가짜 응답을 준다."""
    def _get(url, params=None, timeout=None):
        if calls is not None:
            calls.append(url)
        if "search" in url:
            return _FakeResp(search)
        if "videos" in url:
            return _FakeResp(videos)
        return _FakeResp(channels)
    return _get


def test_probe_keywords_measures(monkeypatch, store):
    monkeypatch.setattr(seo_probe, "YOUTUBE_API_KEYS", ["k1"])
    titles = ["한글제목1", "한글제목2", "한글제목3", "한글제목4"]
    monkeypatch.setattr(seo_probe.requests, "get", _fake_get(
        _search_payload(titles), _videos_payload(4, 500_000), _channels_payload(4, 500)))
    got = seo_probe.probe_keywords(["빨대텀블러"], store)
    assert len(got) == 1
    assert got[0]["keyword"] == "빨대텀블러"
    assert got[0]["views_median"] == 500_000
    assert got[0]["small_ratio"] == 1.0
    assert got[0]["verdict"] == "blue"


def test_probe_keywords_caps_at_max_probe(monkeypatch, store):
    """쿼터 상한 — 6개를 넘겨도 6개만 잰다."""
    monkeypatch.setattr(seo_probe, "YOUTUBE_API_KEYS", ["k1"])
    calls = []
    monkeypatch.setattr(seo_probe.requests, "get", _fake_get(
        _search_payload(["한글1", "한글2", "한글3"]),
        _videos_payload(3, 500_000), _channels_payload(3, 500), calls))
    got = seo_probe.probe_keywords([f"키워드{i}" for i in range(20)], store)
    assert len(got) == seo_probe._MAX_PROBE
    assert sum(1 for u in calls if "search" in u) == seo_probe._MAX_PROBE


def test_probe_keywords_uses_cache(monkeypatch, store):
    """캐시가 있으면 API를 아예 안 부른다 — 100유닛짜리다."""
    store.put_keyword_stats({"keyword": "캐시된", "region": "KR", "views_median": 7,
                             "small_ratio": 0.5, "sample_n": 20,
                             "top_titles": ["x"], "verdict": "blue"})

    def _boom(*a, **k):
        raise AssertionError("캐시 적중인데 API를 불렀다")

    monkeypatch.setattr(seo_probe, "YOUTUBE_API_KEYS", ["k1"])
    monkeypatch.setattr(seo_probe.requests, "get", _boom)
    got = seo_probe.probe_keywords(["캐시된"], store)
    assert got[0]["views_median"] == 7


def test_probe_keywords_writes_cache(monkeypatch, store):
    monkeypatch.setattr(seo_probe, "YOUTUBE_API_KEYS", ["k1"])
    monkeypatch.setattr(seo_probe.requests, "get", _fake_get(
        _search_payload(["한글1", "한글2", "한글3"]),
        _videos_payload(3, 500_000), _channels_payload(3, 500)))
    seo_probe.probe_keywords(["새키워드"], store)
    assert store.get_keyword_stats("새키워드") is not None


def test_probe_keywords_no_keys_is_unknown(monkeypatch, store):
    """키가 없어도 예외를 던지지 않는다 — SEO 문구 생성이 측정보다 우선이다."""
    monkeypatch.setattr(seo_probe, "YOUTUBE_API_KEYS", [])
    got = seo_probe.probe_keywords(["아무거나"], store)
    assert got[0]["verdict"] == "unknown"


def test_probe_keywords_403_rotates_then_unknown(monkeypatch, store):
    """모든 키가 403이면 unknown — 우아하게 꺼진다."""
    monkeypatch.setattr(seo_probe, "YOUTUBE_API_KEYS", ["k1", "k2"])
    calls = []

    def _get(url, params=None, timeout=None):
        calls.append(params.get("key"))
        return _FakeResp({}, status=403)

    monkeypatch.setattr(seo_probe.requests, "get", _get)
    got = seo_probe.probe_keywords(["소진"], store)
    assert got[0]["verdict"] == "unknown"
    assert "k1" in calls and "k2" in calls      # 로테이션은 했다


def test_probe_keywords_403_not_cached(monkeypatch, store):
    """실패를 캐시하면 7일간 unknown에 갇힌다."""
    monkeypatch.setattr(seo_probe, "YOUTUBE_API_KEYS", ["k1"])
    monkeypatch.setattr(seo_probe.requests, "get",
                        lambda url, params=None, timeout=None: _FakeResp({}, status=403))
    seo_probe.probe_keywords(["소진"], store)
    assert store.get_keyword_stats("소진") is None


def test_probe_keywords_filters_foreign_titles(monkeypatch, store):
    """한국어 필터 — 외국 영상이 섞이면 측정이 틀어진다."""
    monkeypatch.setattr(seo_probe, "YOUTUBE_API_KEYS", ["k1"])
    monkeypatch.setattr(seo_probe.requests, "get", _fake_get(
        _search_payload(["한글제목", "English Only Title", "another english"]),
        _videos_payload(3, 500_000), _channels_payload(3, 500)))
    got = seo_probe.probe_keywords(["섞임"], store)
    assert got[0]["sample_n"] == 1          # 한글 1건만 남는다
    assert got[0]["verdict"] == "unknown"   # 표본 부족


def _items(n, views, subs):
    return [{"title": f"t{i}", "views": views, "subs": subs} for i in range(n)]


def test_judge_blue():
    """수요 있고(조회수 높음) 작은 채널도 상위권 → 뚫린다."""
    assert seo_probe.judge(320_000, 0.4, 20) == "blue"


def test_judge_red():
    """수요는 있으나 대형 채널이 독식 → 레드오션."""
    assert seo_probe.judge(1_800_000, 0.05, 20) == "red"


def test_judge_dead():
    """조회수가 낮으면 소형채널 비율과 무관하게 수요 없음."""
    assert seo_probe.judge(3_000, 0.9, 20) == "dead"


def test_judge_unknown_small_sample():
    """샘플이 모자라면 판정하지 않는다 — 거짓 근거를 만들지 않는다."""
    assert seo_probe.judge(320_000, 0.4, 2) == "unknown"


def test_judge_boundary_views_floor():
    """문턱 정확히 = 통과(>=). off-by-one 방지."""
    assert seo_probe.judge(100_000, 0.4, 20) == "blue"
    assert seo_probe.judge(99_999, 0.4, 20) == "dead"


def test_judge_boundary_small_ratio():
    assert seo_probe.judge(320_000, 0.3, 20) == "blue"
    assert seo_probe.judge(320_000, 0.29, 20) == "red"


def test_summarize_median_and_ratio():
    items = [{"title": "a", "views": 100, "subs": 500},
             {"title": "b", "views": 300, "subs": 50_000},
             {"title": "c", "views": 200, "subs": 900}]
    got = seo_probe.summarize(items)
    assert got["views_median"] == 200          # 중앙값(평균 아님 — 이상치에 안 흔들리게)
    assert got["small_ratio"] == 2 / 3         # subs < 10,000 인 게 2개
    assert got["sample_n"] == 3


def test_summarize_top_titles_by_views():
    """top_titles는 조회수 상위 3개 — 사장님이 눈으로 검증할 실물."""
    items = [{"title": "low", "views": 1, "subs": 1},
             {"title": "high", "views": 999, "subs": 1},
             {"title": "mid", "views": 50, "subs": 1},
             {"title": "x", "views": 2, "subs": 1}]
    got = seo_probe.summarize(items)
    assert got["top_titles"] == ["high", "mid", "x"]


def test_summarize_empty_is_unknown():
    got = seo_probe.summarize([])
    assert got["verdict"] == "unknown"
    assert got["sample_n"] == 0


def test_summarize_missing_subs_counts_as_large():
    """구독자를 못 받아온 채널을 '작다'고 치면 블루오션이 과대평가된다 → 크다고 친다."""
    items = _items(5, 500_000, 0)
    for it in items:
        it.pop("subs")
    got = seo_probe.summarize(items)
    assert got["small_ratio"] == 0.0
    assert got["verdict"] == "red"


def test_summarize_median_even_sample():
    """짝수 샘플 → 가운데 두 값의 평균(정수 나눗셈). 이 분기는 T3에서 미검증이었다."""
    items = [{"title": "a", "views": 100, "subs": 1},
             {"title": "b", "views": 200, "subs": 1},
             {"title": "c", "views": 300, "subs": 1},
             {"title": "d", "views": 500, "subs": 1}]
    got = seo_probe.summarize(items)
    assert got["views_median"] == 250       # (200+300)//2
