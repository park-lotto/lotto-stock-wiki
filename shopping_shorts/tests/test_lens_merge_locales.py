"""렌즈 회수율 개편 회귀 테스트 (2026-08-16).

사장님: "다른 프로그램은 자막없는 동일영상을 가져오는데 우린 한국어만 나온다",
        "틱톡·유튜브가 렌즈로 너무 안 나온다 — 구멍이 있는 건지 봐라"

구멍 2개를 실측으로 찾았다:
 ① 응답 리스트 3개 중 **visual_matches 하나만** 읽고 있었다.
    실측(라이브 1장): visual_matches 60(인7 틱6 유6) / organic_results 8(인3 틱2)
    / short_videos 10(인2 틱3 유4) → 19건 버리고 33건 중 19건만 쓰던 셈.
    short_videos는 이름 그대로 숏폼 전용인데 통째로 버려졌다. **추가 비용 0원**.
 ② 로케일 ko/kr 고정 → 한국어 자막판만 올라왔다. en/us는 거의 겹치지 않는
    해외 원본을 준다. 실측 A/B(같은 이미지): 9건 → 27건(3배), 늘어난 18건은
    전부 비한글 제목 = 자막 없는 원본.

★네트워크를 타지 않는다 — SerpApi 응답을 가짜로 만들어 검증한다.
"""
import pytest

from shopping_shorts import lens_discover as LD


def _match(link, title="t", thumb="th"):
    return {"link": link, "title": title, "thumbnail": thumb}


class _FakeResp:
    status_code = 200

    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


@pytest.fixture
def spy(monkeypatch):
    """SerpApi 호출을 가로채 (hl, country)를 기록하고 로케일별 다른 결과를 준다."""
    seen = []

    def fake_get(url, params=None, timeout=None):
        hl = (params or {}).get("hl")
        seen.append((hl, (params or {}).get("country")))
        if hl == "ko":
            return _FakeResp({
                "visual_matches": [_match("https://www.instagram.com/reel/KO1/")],
                "organic_results": [_match("https://www.tiktok.com/@a/video/111")],
                "short_videos": [_match("https://www.youtube.com/watch?v=KOV")],
            })
        if hl == "en":
            return _FakeResp({   # en — 겹치지 않는 다른 영상들
                "visual_matches": [_match("https://www.instagram.com/reel/EN1/")],
                "organic_results": [_match("https://www.tiktok.com/@b/video/222")],
                "short_videos": [_match("https://www.youtube.com/watch?v=ENV")],
            })
        return _FakeResp({   # zh — 또 다른 영상들
            "visual_matches": [_match("https://www.instagram.com/reel/ZH1/")],
            "organic_results": [_match("https://www.tiktok.com/@c/video/333")],
            "short_videos": [_match("https://www.youtube.com/watch?v=ZHV")],
        })

    monkeypatch.setattr(LD.requests, "get", fake_get)
    monkeypatch.setattr(LD, "SERPAPI_KEYS", ["K1"], raising=False)
    monkeypatch.setattr(LD.serpapi_client, "is_exhausted", lambda *a, **k: False)
    monkeypatch.setattr(LD, "verify_matches", lambda out, keywords=None: out)
    return seen


# ── ① 응답 필드 3개를 모두 읽는다 ────────────────────────────────────────
def test_세_필드를_모두_읽는다():
    """visual_matches만 읽으면 organic_results·short_videos를 통째로 버린다."""
    assert LD._RESULT_FIELDS == ("visual_matches", "organic_results", "short_videos")


def test_short_videos와_organic_results도_결과에_들어온다(spy, monkeypatch):
    monkeypatch.setattr(LD, "_LENS_LOCALES", (("ko", "kr"),))
    rows = LD.search_similar_videos("http://img", stats={})
    urls = {r["url"] for r in rows}
    assert any("/video/111" in u for u in urls), "organic_results가 버려졌다"
    assert any("KOV" in u for u in urls), "short_videos가 버려졌다(숏폼 전용인데!)"
    plats = {r["platform"] for r in rows}
    assert plats == {"instagram", "tiktok", "youtube"}


# ── ② 로케일 2벌을 돈다 ──────────────────────────────────────────────────
def test_기본은_ko와_en_두_로케일이다():
    assert ("ko", "kr") in LD._LENS_LOCALES
    assert ("en", "us") in LD._LENS_LOCALES, "en이 빠지면 한국어 자막판만 나온다"


def test_로케일마다_한번씩_호출한다(spy, monkeypatch):
    monkeypatch.setattr(LD, "_LENS_LOCALES", (("ko", "kr"), ("en", "us")))
    LD.search_similar_videos("http://img", stats={})
    assert spy == [("ko", "kr"), ("en", "us")]


def test_두_로케일_결과가_합쳐진다(spy, monkeypatch):
    """ko만 3건 → ko+en 6건. 이게 안 되면 회수율 개편이 죽은 것."""
    monkeypatch.setattr(LD, "_LENS_LOCALES", (("ko", "kr"),))
    only_ko = LD.search_similar_videos("http://img", stats={})
    spy.clear()
    monkeypatch.setattr(LD, "_LENS_LOCALES", (("ko", "kr"), ("en", "us")))
    both = LD.search_similar_videos("http://img", stats={})
    assert len(only_ko) == 3
    assert len(both) == 6, "en 결과가 합쳐지지 않았다"


def test_stats에_로케일별_수집량이_남는다(spy, monkeypatch):
    monkeypatch.setattr(LD, "_LENS_LOCALES", (("ko", "kr"), ("en", "us")))
    st = {}
    LD.search_similar_videos("http://img", stats=st)
    assert st["raw_ko"] == 3 and st["raw_en"] == 3


# ── ③ 중복 제거 — 합치면 같은 영상이 두 번 온다 ──────────────────────────
def test_같은_영상은_한_번만_나온다(monkeypatch):
    """ko와 en이 같은 영상을 주면 카드가 두 번 뜬다 → URL 기준으로 하나만."""
    def fake_get(url, params=None, timeout=None):
        return _FakeResp({"visual_matches": [
            _match("https://www.instagram.com/reel/SAME/"),
            _match("https://www.instagram.com/reel/SAME/?utm_source=x"),  # 쿼리만 다름
            _match("https://www.instagram.com/reel/SAME"),                # 슬래시만 다름
        ]})
    monkeypatch.setattr(LD.requests, "get", fake_get)
    monkeypatch.setattr(LD, "SERPAPI_KEYS", ["K1"], raising=False)
    monkeypatch.setattr(LD.serpapi_client, "is_exhausted", lambda *a, **k: False)
    monkeypatch.setattr(LD, "verify_matches", lambda out, keywords=None: out)
    monkeypatch.setattr(LD, "_LENS_LOCALES", (("ko", "kr"), ("en", "us")))
    rows = LD.search_similar_videos("http://img", stats={})
    assert len(rows) == 1, f"중복이 안 걸러졌다: {[r['url'] for r in rows]}"


def test_유튜브는_쿼리의_영상ID까지_봐야_한다():
    """★유튜브는 영상 ID가 경로가 아니라 쿼리(?v=)에 있다.

    ?앞만 잘라 키를 만들면 서로 다른 영상이 전부 'youtube.com/watch'가 돼
    **유튜브가 1개로 뭉개진다**(2026-08-16 이 테스트가 실제로 잡아낸 버그)."""
    a = LD._dedup_key("https://www.youtube.com/watch?v=AAA")
    b = LD._dedup_key("https://www.youtube.com/watch?v=BBB")
    assert a != b, "서로 다른 유튜브 영상이 같은 키가 됐다"
    # 같은 영상인데 부가 파라미터만 다른 것은 같은 키여야 한다
    assert a == LD._dedup_key("https://www.youtube.com/watch?v=AAA&t=30s")


def test_같은_영상의_사소한_차이는_무시한다():
    k = LD._dedup_key("https://www.instagram.com/reel/ABC/")
    assert k == LD._dedup_key("https://www.instagram.com/reel/ABC")
    assert k == LD._dedup_key("https://www.instagram.com/reel/ABC/?utm_source=x")


# ── ⑤ 호출 상한 — 한 번 클릭에 SerpApi 3회까지 ───────────────────────────
def test_로케일은_ko_en_zh_세벌이다():
    """★중국어는 country=**tw**다. 본토(cn)는 구글이 서비스하지 않아 90초를 끌다
    503을 뱉는다 — 실측 2026-08-16: zh-cn/cn 90.3초 503·0건 / zh-cn/tw 4.0초 60건."""
    assert LD._LENS_LOCALES == (("ko", "kr"), ("en", "us"), ("zh-cn", "tw"))


def test_한번_검색에_최대_3회만_호출한다(monkeypatch):
    """★로케일 3벌 × 재시도 3회 = 최대 9회까지 불어날 수 있다.

    빈 결과가 계속 오는 최악의 경우에도 상한을 넘으면 안 된다
    (2026-08-16 사장님 "무조건 한번클릭에 3회로 상한")."""
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append((params or {}).get("hl"))
        return _FakeResp({"visual_matches": []})      # 항상 빈 결과 → 재시도 유발

    monkeypatch.setattr(LD.requests, "get", fake_get)
    monkeypatch.setattr(LD, "SERPAPI_KEYS", ["K1"], raising=False)
    monkeypatch.setattr(LD.serpapi_client, "is_exhausted", lambda *a, **k: False)
    monkeypatch.setattr(LD, "verify_matches", lambda out, keywords=None: out)
    monkeypatch.setattr(LD.time, "sleep", lambda s: None)

    st = {}
    LD.search_similar_videos("http://img", stats=st)
    assert len(calls) <= LD._MAX_CALLS_PER_SEARCH, f"상한 초과: {len(calls)}회 {calls}"
    assert st["serpapi_calls"] == len(calls)


def test_소진된_키는_예산을_먹지_않는다(monkeypatch):
    """★소진 키(429)는 검색을 안 해주므로 예산에서 빼면 안 된다.

    라이브에서 실제로 터진 버그(2026-08-16): 키1이 소진 상태였는데 로케일마다
    그 키를 찔러 예산을 깎아, ko 한 벌만 돌고 **en·zh가 통째로 굶었다**
    (ko 69건 / en 0건 / zh 미실행). 죽은 키는 예산을 돌려주고 다음부터 건너뛴다."""
    hit = []

    def fake_get(url, params=None, timeout=None):
        key, hl = params["api_key"], params["hl"]
        hit.append((hl, key))
        if key == "DEAD":
            return _FakeResp({"error": "Your account has run out of searches."})
        return _FakeResp({"visual_matches": [
            _match(f"https://www.instagram.com/reel/{hl.upper()}/")]})

    monkeypatch.setattr(LD.requests, "get", fake_get)
    monkeypatch.setattr(LD, "SERPAPI_KEYS", ["DEAD", "LIVE"], raising=False)
    monkeypatch.setattr(LD.serpapi_client, "is_exhausted",
                        lambda status, data: "run out" in str(data.get("error", "")))
    monkeypatch.setattr(LD, "verify_matches", lambda out, keywords=None: out)
    monkeypatch.setattr(LD, "_LENS_LOCALES", (("ko", "kr"), ("en", "us"), ("zh-cn", "cn")))

    st = {}
    rows = LD.search_similar_videos("http://img", stats=st)
    # 죽은 키는 **한 번만** 찔린다(첫 로케일). 이후 로케일은 바로 LIVE로 간다.
    assert [k for _, k in hit].count("DEAD") == 1, f"죽은 키를 여러 번 찔렀다: {hit}"
    # 로케일 3벌이 모두 실제 결과를 받았다 = 굶은 로케일 없음
    assert st["raw_ko"] and st["raw_en"] and st["raw_zh-cn"], st
    assert len(rows) == 3


def test_앞_로케일_재시도가_뒤_로케일을_굶기지_않는다(monkeypatch):
    """★중국어(zh)가 아예 안 도는 문제(2026-08-16 사장님 "중국어가 얼마나 나올지 보고싶다").

    ko가 빈 결과로 재시도를 돌면 예산 3회를 혼자 다 먹어 en·zh 차례가 안 왔다.
    로케일마다 최소 1회는 보장해야 한다."""
    hit = []

    def fake_get(url, params=None, timeout=None):
        hl = params["hl"]
        hit.append(hl)
        if hl == "ko":
            return _FakeResp({"visual_matches": []})       # 빈 결과 → 재시도 유발
        return _FakeResp({"visual_matches": [
            _match(f"https://www.instagram.com/reel/{hl.upper()}/")]})

    monkeypatch.setattr(LD.requests, "get", fake_get)
    monkeypatch.setattr(LD, "SERPAPI_KEYS", ["K1"], raising=False)
    monkeypatch.setattr(LD.serpapi_client, "is_exhausted", lambda *a, **k: False)
    monkeypatch.setattr(LD, "verify_matches", lambda out, keywords=None: out)
    monkeypatch.setattr(LD.time, "sleep", lambda s: None)
    monkeypatch.setattr(LD, "_LENS_LOCALES", (("ko", "kr"), ("en", "us"), ("zh-cn", "cn")))

    st = {}
    rows = LD.search_similar_videos("http://img", stats=st)
    assert "zh-cn" in hit, f"중국어가 한 번도 안 돌았다: {hit}"
    assert "en" in hit, f"영어가 안 돌았다: {hit}"
    assert st["serpapi_calls"] <= LD._MAX_CALLS_PER_SEARCH   # 상한은 그대로 지킨다
    assert len(rows) == 2          # en + zh (ko는 빈 결과)


def test_결과가_바로_나오면_로케일마다_한번씩만(monkeypatch, spy):
    """정상 상황(첫 호출에 결과 있음)에선 로케일당 1회 = 정확히 3회."""
    monkeypatch.setattr(LD.time, "sleep", lambda s: None)
    st = {}
    LD.search_similar_videos("http://img", stats=st)
    assert st["serpapi_calls"] == 3


# ── ⑥ 사진·롱폼은 서버가 잘라낸다 ────────────────────────────────────────
def _one_locale(monkeypatch, payload):
    monkeypatch.setattr(LD.requests, "get",
                        lambda url, params=None, timeout=None: _FakeResp(payload))
    monkeypatch.setattr(LD, "SERPAPI_KEYS", ["K1"], raising=False)
    monkeypatch.setattr(LD.serpapi_client, "is_exhausted", lambda *a, **k: False)
    monkeypatch.setattr(LD, "verify_matches", lambda out, keywords=None: out)
    monkeypatch.setattr(LD, "_LENS_LOCALES", (("ko", "kr"),))


def test_인스타_카드뉴스는_결과에서_빠진다(monkeypatch):
    """예전엔 프론트에서 '가리기'만 해 개수엔 잡혔다 — 이제 서버가 잘라낸다."""
    _one_locale(monkeypatch, {"visual_matches": [
        _match("https://www.instagram.com/p/PHOTO1/"),      # 카드뉴스 → 컷
        _match("https://www.instagram.com/reel/REEL1/"),    # 영상 → 통과
    ]})
    st = {}
    rows = LD.search_similar_videos("http://img", stats=st)
    assert [r["url"] for r in rows] == ["https://www.instagram.com/reel/REEL1/"]
    assert st["cut_photo"] == 1


def test_롱폼은_결과에서_빠진다(monkeypatch):
    """short_videos의 duration으로 판정한다("0:13"·"1:02:33" 형태)."""
    _one_locale(monkeypatch, {"short_videos": [
        {**_match("https://www.youtube.com/watch?v=SHORT"), "duration": "0:45"},
        {**_match("https://www.youtube.com/watch?v=LONG"), "duration": "12:30"},
        {**_match("https://www.youtube.com/watch?v=VLONG"), "duration": "1:02:33"},
    ]})
    st = {}
    rows = LD.search_similar_videos("http://img", stats=st)
    assert [r["url"] for r in rows] == ["https://www.youtube.com/watch?v=SHORT"]
    assert st["cut_longform"] == 2


def test_길이를_모르면_자르지_않는다(monkeypatch):
    """visual_matches엔 duration이 없다 — 모른다고 자르면 멀쩡한 릴스가 사라진다."""
    _one_locale(monkeypatch, {"visual_matches": [
        _match("https://www.instagram.com/reel/NODUR/"),
    ]})
    st = {}
    rows = LD.search_similar_videos("http://img", stats=st)
    assert len(rows) == 1 and st["cut_longform"] == 0
    assert rows[0]["is_short"] is True          # 모르면 숏폼 취급(토글이 안 가리게)


@pytest.mark.parametrize("raw,secs", [
    ("0:13", 13), ("1:02:33", 3753), ("45", 45), (45, 45),
    (None, None), ("", None), ("N/A", None),
])
def test_길이_문자열_파싱(raw, secs):
    assert LD._duration_secs(raw) == secs


# ── ④ 기존 안전장치가 살아있다 ───────────────────────────────────────────
def test_모음페이지는_여전히_걸러진다(monkeypatch):
    """프로필·해시태그 페이지는 재생이 안 된다 — 새 필드로 들어와도 막아야 한다."""
    def fake_get(url, params=None, timeout=None):
        return _FakeResp({"short_videos": [
            _match("https://www.tiktok.com/discover/다이소-욕조"),   # 모음
            _match("https://www.instagram.com/some_account/"),      # 프로필
            _match("https://www.tiktok.com/@u/video/999"),          # 개별 ✅
        ]})
    monkeypatch.setattr(LD.requests, "get", fake_get)
    monkeypatch.setattr(LD, "SERPAPI_KEYS", ["K1"], raising=False)
    monkeypatch.setattr(LD.serpapi_client, "is_exhausted", lambda *a, **k: False)
    monkeypatch.setattr(LD, "verify_matches", lambda out, keywords=None: out)
    monkeypatch.setattr(LD, "_LENS_LOCALES", (("ko", "kr"),))
    rows = LD.search_similar_videos("http://img", stats={})
    assert len(rows) == 1 and "/video/999" in rows[0]["url"]


def test_thumbnail_없는_항목도_죽지_않는다(monkeypatch):
    """organic_results엔 thumbnail이 없다(실측) — KeyError로 죽으면 안 된다."""
    def fake_get(url, params=None, timeout=None):
        return _FakeResp({"organic_results": [
            {"link": "https://www.instagram.com/reel/NOTHUMB/", "title": "t"},
        ]})
    monkeypatch.setattr(LD.requests, "get", fake_get)
    monkeypatch.setattr(LD, "SERPAPI_KEYS", ["K1"], raising=False)
    monkeypatch.setattr(LD.serpapi_client, "is_exhausted", lambda *a, **k: False)
    monkeypatch.setattr(LD, "verify_matches", lambda out, keywords=None: out)
    monkeypatch.setattr(LD, "_LENS_LOCALES", (("ko", "kr"),))
    rows = LD.search_similar_videos("http://img", stats={})
    assert len(rows) == 1 and rows[0]["thumbnail"] == ""
