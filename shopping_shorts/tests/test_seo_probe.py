from datetime import datetime, timedelta, timezone

import pytest
import requests

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
    """수요 있고, 10만+ 낸 영상 중 소형채널이 있다 → 뚫린다.
    두 번째 인자는 '비율'이 아니라 '소형채널이 10만+ 낸 편수'다(사장님 결정 2026-07-17)."""
    assert seo_probe.judge(320_000, 1, 20) == "blue"


def test_judge_red():
    """수요는 있으나 10만+ 낸 소형채널이 하나도 없다 → 대형채널 독식."""
    assert seo_probe.judge(1_800_000, 0, 20) == "red"


def test_judge_dead():
    """조회수가 낮으면 소형채널 비율과 무관하게 수요 없음."""
    assert seo_probe.judge(3_000, 0.9, 20) == "dead"


def test_judge_unknown_small_sample():
    """샘플이 모자라면 판정하지 않는다 — 거짓 근거를 만들지 않는다."""
    assert seo_probe.judge(320_000, 0.4, 2) == "unknown"


def test_judge_boundary_views_floor():
    """문턱 정확히 = 통과(>=). off-by-one 방지."""
    assert seo_probe.judge(100_000, 1, 20) == "blue"
    assert seo_probe.judge(99_999, 1, 20) == "dead"


def test_judge_boundary_small_hits():
    """1편이라도 있으면 blue, 0편이면 red — 사장님이 고른 문턱(_SMALL_HITS_MIN=1)."""
    assert seo_probe.judge(320_000, 1, 20) == "blue"
    assert seo_probe.judge(320_000, 0, 20) == "red"


def test_summarize_median_and_ratio():
    items = [{"title": "a", "views": 100, "subs": 500},
             {"title": "b", "views": 300, "subs": 50_000},
             {"title": "c", "views": 200, "subs": 900}]
    got = seo_probe.summarize(items)
    assert got["views_median"] == 200          # 중앙값(평균 아님 — 이상치에 안 흔들리게)
    # 셋 다 10만 미만이라 '뚫었다'고 셀 영상이 없다 → 소형채널 비율은 0.
    # (구독자만 보면 2/3이 소형이지만, 아무도 조회수를 못 냈으므로 뚫림의 증거가 아니다)
    assert got["small_ratio"] == 0.0
    assert got["small_hits"] == 0
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


def test_probe_keywords_videos_fail_is_unknown_not_cached(monkeypatch, store):
    """search는 성공, videos.list만 500 실패 → dead로 오판돼 캐시되면 안 된다."""
    monkeypatch.setattr(seo_probe, "YOUTUBE_API_KEYS", ["k1"])

    def _get(url, params=None, timeout=None):
        if "search" in url:
            return _FakeResp(_search_payload(["한글1", "한글2", "한글3"]))
        if "videos" in url:
            return _FakeResp({}, status=500)
        return _FakeResp(_channels_payload(3, 500))

    monkeypatch.setattr(seo_probe.requests, "get", _get)
    got = seo_probe.probe_keywords(["통계실패"], store)
    assert got[0]["verdict"] == "unknown"
    assert store.get_keyword_stats("통계실패") is None


def test_probe_keywords_channels_fail_keeps_measurement_as_large(monkeypatch, store):
    """channels.list 실패해도 측정은 살아있고 subs는 '큰 채널'로 처리된다(보수적).

    ★단 캐시는 하지 않는다(2026-07-17 리뷰 지적). 구독자를 못 받으면 전부 0으로 잡혀
    소형채널 0편 = red가 되는데, 이걸 캐시하면 **진짜 blue 키워드가 7일간 red로 굳어**
    그동안 Gemini에 "이걸 메인으로 쓰지 마라"를 계속 먹인다. 재시도로 자가치유되게 둔다
    — views 실패를 캐시 안 하는 것과 같은 이유다. 예전 이 테스트는 캐시하는 쪽을
    '의도'로 못 박고 있었다."""
    monkeypatch.setattr(seo_probe, "YOUTUBE_API_KEYS", ["k1"])

    def _get(url, params=None, timeout=None):
        if "search" in url:
            return _FakeResp(_search_payload(["한글1", "한글2", "한글3"]))
        if "videos" in url:
            return _FakeResp(_videos_payload(3, 500_000))
        return _FakeResp({}, status=500)

    monkeypatch.setattr(seo_probe.requests, "get", _get)
    got = seo_probe.probe_keywords(["구독실패"], store)
    assert got[0]["views_median"] == 500_000
    assert got[0]["small_ratio"] == 0.0
    assert got[0]["verdict"] == "red"
    assert store.get_keyword_stats("구독실패") is None    # 틀렸을지 모르는 red를 굳히지 않는다


def test_probe_keywords_network_exception_does_not_raise(monkeypatch, store):
    """requests.get이 Timeout을 던져도 probe_keywords 밖으로 예외가 나가면 안 된다."""
    monkeypatch.setattr(seo_probe, "YOUTUBE_API_KEYS", ["k1"])

    def _boom(url, params=None, timeout=None):
        raise requests.exceptions.Timeout("network is slow today")

    monkeypatch.setattr(seo_probe.requests, "get", _boom)
    got = seo_probe.probe_keywords(["타임아웃"], store)  # 예외 없이 리턴돼야 한다
    assert got[0]["verdict"] == "unknown"
    assert store.get_keyword_stats("타임아웃") is None


def test_summarize_median_even_sample():
    """짝수 샘플 → 가운데 두 값의 평균(정수 나눗셈). 이 분기는 T3에서 미검증이었다."""
    items = [{"title": "a", "views": 100, "subs": 1},
             {"title": "b", "views": 200, "subs": 1},
             {"title": "c", "views": 300, "subs": 1},
             {"title": "d", "views": 500, "subs": 1}]
    got = seo_probe.summarize(items)
    assert got["views_median"] == 250       # (200+300)//2


# ── T8 실측이 드러낸 것(2026-07-17) ──────────────────────────────
# 유튜브를 처음 진짜로 불러보니 상위 조회수 분포가 극단적 롱테일이었다.
# '빨대텀블러' 90일 실측: 1,525,523 / 950,512 / 150,651 / 92,205 / 24,016 …
# 9위부터 1만 아래. 20편 중앙값=10,230 → 기존 판정은 dead(수요 없음).
# 150만짜리가 두 편 터진 키워드를 '아무도 안 본다'고 말하는 건 틀렸다.
# → 수요는 '상위 5편의 중앙값'으로 재고, 20편 중앙값은 기대치로 남긴다.


def _tail(top, tail_views=5_000, tail_n=15, subs=500):
    """상위 몇 편 + 긴 꼬리 = 실제 유튜브 검색 결과 모양."""
    return ([{"title": f"top{i}", "views": v, "subs": subs} for i, v in enumerate(top)]
            + [{"title": f"tail{i}", "views": tail_views, "subs": subs}
               for i in range(tail_n)])


def test_summarize_demand_is_top_not_tail():
    """빨대텀블러 실측 그대로 — 꼬리가 수요 판정을 죽이면 안 된다."""
    got = seo_probe.summarize(_tail([1_525_523, 950_512, 150_651, 92_205, 24_016]))
    assert got["views_top"] == 150_651        # 상위 5편의 중앙값 = 수요
    assert got["views_median"] < 30_000       # 기대치는 정직하게 낮게 남는다
    assert got["verdict"] == "blue"           # 소형채널이 뚫는 키워드다


def test_summarize_demand_red_when_big_channels_own_it():
    """무선청소기 실측 모양 — 수요는 있는데 대형채널 독식이면 red(dead 아님)."""
    got = seo_probe.summarize(_tail([1_198_270, 500_000, 233_462, 120_000, 90_000],
                                    subs=500_000))
    assert got["views_top"] == 233_462
    assert got["verdict"] == "red"


def test_summarize_views_top_when_fewer_than_five():
    """5편이 안 되면 있는 것 전부의 중앙값 — 표본이 작다고 0으로 죽이지 않는다."""
    got = seo_probe.summarize([{"title": "a", "views": 300, "subs": 1},
                               {"title": "b", "views": 100, "subs": 1},
                               {"title": "c", "views": 200, "subs": 1}])
    assert got["views_top"] == 200


def test_summarize_empty_has_views_top():
    got = seo_probe.summarize([])
    assert got["views_top"] == 0
    assert got["verdict"] == "unknown"


def test_probe_unescapes_html_entities_in_titles(monkeypatch, store):
    """유튜브 API는 제목을 HTML 이스케이프해 준다(실측: "아직도 &#39;맹물 커피&#39;").
    그대로 두면 사장님 화면의 근거 제목에 &#39;가 그대로 보인다."""
    monkeypatch.setattr(seo_probe, "YOUTUBE_API_KEYS", ["k1"])
    monkeypatch.setattr(seo_probe.requests, "get", _fake_get(
        _search_payload(["아직도 &#39;맹물 커피&#39; 드세요?", "한글둘", "한글셋"]),
        _videos_payload(3, 500_000), _channels_payload(3, 500)))
    got = seo_probe.probe_keywords(["이스케이프"], store)
    assert "아직도 '맹물 커피' 드세요?" in got[0]["top_titles"]
    assert "&#39;" not in " ".join(got[0]["top_titles"])


# ── 리뷰가 잡은 Critical + 실측 재보정(2026-07-17) ────────────────
# small_ratio를 20편 전체로 재던 것 → 꼬리는 정의상 영세채널이라 비율이 부풀고
# 상위권을 대형이 독식한 키워드가 blue로 뒤집혔다. 실측 6키워드 중 3건이 뒤집혔다.
# 사장님 결정: 소형=구독 1만 미만 유지 / 10만+ 낸 소형채널이 1편이라도 있으면 blue.


def test_summarize_tail_small_channels_do_not_make_it_blue():
    """★실측 '빨대텀블러': 상위권은 구독 59만·49만·9.5만이 1.5M/950k/151k를 먹고,
    소형채널(구독 80명·1명)은 1.6만·1.3만에 그쳤다. 꼬리가 소형이라고 blue라 하면 안 된다.
    이게 리뷰가 잡은 Critical의 실물이다(현행 코드는 이걸 blue라고 했다)."""
    items = ([{"title": "대형1", "views": 1_525_629, "subs": 594_000},
              {"title": "대형2", "views": 950_553, "subs": 498_000},
              {"title": "대형3", "views": 150_651, "subs": 95_000},
              {"title": "중형", "views": 92_205, "subs": 52_200}]
             + [{"title": f"영세{i}", "views": 16_000 - i * 100, "subs": 80}
                for i in range(16)])          # 꼬리 16편 전부 영세채널
    got = seo_probe.summarize(items)
    assert got["small_hits"] == 0        # 10만+ 낸 소형채널이 하나도 없다
    assert got["verdict"] == "red"       # 꼬리에 속으면 안 된다


def test_summarize_one_small_breakthrough_is_blue():
    """★실측 '캠핑의자': 구독 9,610명 채널이 117,259 조회를 냈다.
    한 편이라도 뚫었으면 blue — 증명된 가능성이다(사장님 결정)."""
    items = ([{"title": "대형1", "views": 966_070, "subs": 49_100},
              {"title": "대형2", "views": 667_716, "subs": 61_200},
              {"title": "대형3", "views": 243_234, "subs": 68_200},
              {"title": "★소형돌파", "views": 117_259, "subs": 9_610},
              {"title": "중형", "views": 102_118, "subs": 10_800}]
             + [{"title": f"꼬리{i}", "views": 30_000, "subs": 9_000} for i in range(15)])
    got = seo_probe.summarize(items)
    assert got["small_hits"] == 1
    assert got["verdict"] == "blue"


def test_summarize_hit_counts_are_reported():
    """화면·프롬프트가 '10만+ N편 중 소형 M편'을 근거로 쓴다 — 둘 다 실려야 한다."""
    items = [{"title": "a", "views": 500_000, "subs": 500},
             {"title": "b", "views": 300_000, "subs": 900_000},
             {"title": "c", "views": 50_000, "subs": 100}]     # 10만 미만 = 안 센다
    got = seo_probe.summarize(items)
    assert got["hit_n"] == 2         # 10만 넘긴 건 2편
    assert got["small_hits"] == 1    # 그중 소형은 1편
    assert got["small_ratio"] == 0.5 # 비율은 '10만+ 중' 비율이다(20편 전체 아님)


def test_search_request_asks_for_the_right_thing(monkeypatch, store):
    """★검색 요청 자체를 잰다(2026-07-17 리뷰 지적).

    이 테스트가 없을 때 뮤테이션이 드러낸 것: q를 상수 "zzz"로 바꿔 **사용자 키워드를
    아예 안 검색해도** 60건이 전부 green이었다. summarize·judge 수학은 자물쇠가 촘촘한데
    그 수학에 들어가는 숫자를 어디서 길어왔는지는 아무도 안 쟀다 — 없는 키워드의
    blue/red를 지어내도 통과한다는 뜻이다. 기존 가짜 응답 헬퍼가 params를 통째로 버린 탓.
    """
    monkeypatch.setattr(seo_probe, "YOUTUBE_API_KEYS", ["k1"])
    seen = {}

    def _get(url, params=None, timeout=None):
        if "search" in url:
            seen.update(params)
            return _FakeResp(_search_payload(["한글1", "한글2", "한글3"]))
        if "videos" in url:
            return _FakeResp(_videos_payload(3, 500_000))
        return _FakeResp(_channels_payload(3, 500))

    monkeypatch.setattr(seo_probe.requests, "get", _get)
    seo_probe.probe_keywords(["빨대텀블러"], store, lang="ko")

    assert seen["q"] == "빨대텀블러"          # ★사용자 키워드를 실제로 검색한다
    assert seen["order"] == "viewCount"       # 상위 조회수 = 수요. relevance면 딴 걸 잰다
    assert seen["videoDuration"] == "short"   # 쇼츠만 — 롱폼 섞이면 조회수 기준이 딴 세상
    assert seen["type"] == "video"
    assert seen["regionCode"] == "KR"         # 한국 시장을 잰다
    assert seen["relevanceLanguage"] == "ko"
    assert seen["maxResults"] == seo_probe._SAMPLE_MAX
    assert "publishedAfter" in seen           # 최근 것만 — 없으면 10년 전 영상이 섞인다


def test_search_window_is_recent(monkeypatch, store):
    """publishedAfter가 _WINDOW_DAYS를 실제로 반영하고, 그 창이 '최근'이다.

    ⚠️상수를 그대로 따라가는 단언(days == _WINDOW_DAYS)만 쓰면 상수를 9999로 바꿔도
    기대값이 같이 움직여 통과한다 — 자기참조라 아무것도 안 재는 테스트가 된다(실측:
    그 뮤턴트가 살아남았다). 그래서 창의 범위 자체도 못 박는다. 수요는 '지금' 수요라
    10년치를 긁으면 옛날 영상이 섞여 판정이 왜곡된다. 튜닝은 이 범위 안에서 해라."""
    monkeypatch.setattr(seo_probe, "YOUTUBE_API_KEYS", ["k1"])
    seen = {}

    def _get(url, params=None, timeout=None):
        if "search" in url:
            seen.update(params)
            return _FakeResp(_search_payload(["한글1", "한글2", "한글3"]))
        if "videos" in url:
            return _FakeResp(_videos_payload(3, 500_000))
        return _FakeResp(_channels_payload(3, 500))

    monkeypatch.setattr(seo_probe.requests, "get", _get)
    seo_probe.probe_keywords(["창"], store)

    assert 7 <= seo_probe._WINDOW_DAYS <= 365      # 창 자체가 '최근'이어야 한다
    since = datetime.fromisoformat(seen["publishedAfter"])
    days = (datetime.now(timezone.utc) - since).days
    assert days == seo_probe._WINDOW_DAYS or days == seo_probe._WINDOW_DAYS - 1


def test_probe_uses_default_ttl_not_forever(monkeypatch, store):
    """★프로덕션이 쓰는 TTL을 잰다(2026-07-17 리뷰 지적).

    기존 TTL 테스트는 ttl_days=7을 **명시로 넘겨서** 인자만 검증했다. 정작
    probe_keywords는 기본값으로 부른다 → 기본값이 10년으로 바뀌어도 전부 green이었다.
    '저장한 값 ≠ 읽는 값' 계통의 이음새다."""
    old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    store.put_keyword_stats({"keyword": "낡은", "region": "KR", "views_top": 500_000,
                             "views_median": 9, "small_ratio": 1.0, "small_hits": 3,
                             "hit_n": 3, "sample_n": 20, "top_titles": ["x"],
                             "verdict": "blue"})
    with store._conn() as c:
        c.execute("UPDATE seo_keyword_stats SET checked_at=?", (old,))

    monkeypatch.setattr(seo_probe, "YOUTUBE_API_KEYS", ["k1"])
    monkeypatch.setattr(seo_probe.requests, "get", _fake_get(
        _search_payload(["한글1", "한글2", "한글3"]),
        _videos_payload(3, 500_000), _channels_payload(3, 500)))
    got = seo_probe.probe_keywords(["낡은"], store)
    assert got[0]["views_median"] == 500_000   # 8일 된 캐시를 안 쓰고 새로 쟀다
