"""렌즈 유튜브 검색어를 '제품명'에서 '주제(subject)'로 (2026-08-17).

실측 A/B (사장님 라이브 썸네일 4건, cn_search_keyword_vision의 product vs
subject_tags_vision의 subject):

    수납침대   : '수납 침대'(2건,same1)        → '수납침대'(5건,same5)
    제모기     : '크리스탈 제모기'(same5,no3)   → '제모기'(same8,no0)
    차량방향제 : '차량용 방향제'(same8)         → 동일(same8)
    강아지목욕 : '강아지 목욕용 캠핑 침대'(same0,no5, 신혼여행 발리 영상 오검색)
                                              → '강아지 목욕'(same7~8)

cn_search_keyword_vision은 '제품 특정(색·형태·브랜드)'을 요구하는 샤오홍슈/도우인용
프롬프트라 유튜브에선 과도하게 구체적인 복합어가 되어 0건이 나온다.
subject_tags_vision은 애초에 "검색어로 이 영상이 잡히게" 만드는 게 목표라 유튜브에 맞다.

★네트워크·Gemini 전부 가짜로 대체 — API 키 없이 로컬에서 돈다.
"""
from shopping_shorts import app as APP


# ── ① 순수 헬퍼 _yt_keywords 단위 테스트 ──────────────────────────────
def test_subject가_있으면_product보다_우선한다():
    kws = APP._yt_keywords(
        subject_result={"subject": "수납침대", "keywords": ["침대", "수납가구"]},
        cn_result={"product": "수납 침대"},
        caption="수납 침대 후기",
    )
    assert kws[0] == "수납침대"


def test_subject가_비어있으면_product로_폴백한다():
    """기존 동작 보존 — subject_tags_vision이 {}거나 subject가 빈 문자열."""
    kws = APP._yt_keywords(
        subject_result={},
        cn_result={"product": "크리스탈 제모기"},
        caption="제모기 리뷰",
    )
    assert kws[0] == "크리스탈 제모기"


def test_둘_다_실패하면_캡션_토큰으로_폴백한다():
    kws = APP._yt_keywords(
        subject_result={},
        cn_result={},
        caption="강아지 목욕 캠핑 침대 후기",
    )
    assert kws[0] == APP._cn_keyword("강아지 목욕 캠핑 침대 후기")
    assert kws[0] != ""


def test_keywords의_첫번째_다른_항목을_보조검색어로_쓴다():
    kws = APP._yt_keywords(
        subject_result={"subject": "제모기", "keywords": ["제모기", "브라운 실크에피", "미용가전"]},
        cn_result={},
        caption="",
    )
    # subject와 같은 첫 keywords 항목은 건너뛰고 다음 걸 쓴다
    assert kws == ["제모기", "브라운 실크에피"]


def test_보조검색어가_없으면_기본검색어_하나만():
    kws = APP._yt_keywords(
        subject_result={"subject": "제모기", "keywords": []},
        cn_result={},
        caption="",
    )
    assert kws == ["제모기"]


def test_보조검색어가_기본검색어와_전부_같으면_추가하지_않는다():
    kws = APP._yt_keywords(
        subject_result={"subject": "제모기", "keywords": ["제모기", "제모기"]},
        cn_result={},
        caption="",
    )
    assert kws == ["제모기"]


# ── ② 엔드포인트 통합 — FastAPI TestClient ──────────────────────────────
def _fake_search_factory(store):
    def fake_search(keyword, max_results=10, duration=None, language=None):
        store.setdefault("calls", []).append(keyword)
        # ★두 키워드 검색 모두 같은 영상(shared-u0)을 하나씩 물어와 dedupe를 검증
        return [{"url": "shared-u0", "title": f"{keyword} 제목0", "thumbnail": ""},
                {"url": f"{keyword}-u1", "title": f"{keyword} 제목1", "thumbnail": ""}]
    return fake_search


def test_두_검색어_결과가_합쳐지고_url로_중복제거된다(monkeypatch):
    from fastapi.testclient import TestClient

    store = {}
    monkeypatch.setattr(APP, "subject_tags_vision",
                        lambda raw, cap: {"subject": "제모기", "keywords": ["제모기", "미용가전"]})
    monkeypatch.setattr(APP, "cn_search_keyword_vision", lambda raw, cap: {"product": "크리스탈 제모기"})
    monkeypatch.setattr(APP.youtube_search, "search", _fake_search_factory(store))
    monkeypatch.setattr(APP, "judge_same_product", lambda p, t: ["same"] * len(t))

    client = TestClient(APP.app)
    r = client.post("/api/lens/yt", data={"source_caption": "제모기 후기"},
                    files={"frame": ("f.jpg", b"fakebytes", "image/jpeg")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["keyword"] == "제모기"
    # 검색은 주검색어+보조검색어 2번, 각 2건이지만 u0가 겹쳐 dedupe되어 3건
    assert store["calls"] == ["제모기", "미용가전"]
    urls = [it["url"] for it in body["items"]]
    assert len(urls) == len(set(urls)), "URL 중복이 남아있다"
    assert len(body["items"]) == 3


def test_subject_tags_vision이_실패하면_기존동작_product로_폴백한다(monkeypatch):
    from fastapi.testclient import TestClient

    store = {}
    monkeypatch.setattr(APP, "subject_tags_vision", lambda raw, cap: {})
    monkeypatch.setattr(APP, "cn_search_keyword_vision", lambda raw, cap: {"product": "크리스탈 제모기"})
    monkeypatch.setattr(APP.youtube_search, "search", _fake_search_factory(store))
    monkeypatch.setattr(APP, "judge_same_product", lambda p, t: ["same"] * len(t))

    client = TestClient(APP.app)
    r = client.post("/api/lens/yt", data={"source_caption": "제모기 후기"},
                    files={"frame": ("f.jpg", b"fakebytes", "image/jpeg")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["keyword"] == "크리스탈 제모기"
    assert store["calls"] == ["크리스탈 제모기"]


def test_둘_다_실패하면_캡션_폴백으로_기존동작_유지(monkeypatch):
    from fastapi.testclient import TestClient

    store = {}
    monkeypatch.setattr(APP, "subject_tags_vision", lambda raw, cap: {})
    monkeypatch.setattr(APP, "cn_search_keyword_vision", lambda raw, cap: {})
    monkeypatch.setattr(APP.youtube_search, "search", _fake_search_factory(store))
    monkeypatch.setattr(APP, "judge_same_product", lambda p, t: ["same"] * len(t))

    client = TestClient(APP.app)
    r = client.post("/api/lens/yt", data={"source_caption": "강아지 목욕 캠핑 침대"},
                    files={"frame": ("f.jpg", b"fakebytes", "image/jpeg")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["keyword"] == APP._cn_keyword("강아지 목욕 캠핑 침대")


def test_결과_총합은_12개를_넘지_않는다(monkeypatch):
    from fastapi.testclient import TestClient

    def fake_search(keyword, max_results=10, duration=None, language=None):
        return [{"url": f"{keyword}-u{i}", "title": f"t{i}", "thumbnail": ""}
                for i in range(max_results)]

    monkeypatch.setattr(APP, "subject_tags_vision",
                        lambda raw, cap: {"subject": "제모기", "keywords": ["제모기", "미용가전"]})
    monkeypatch.setattr(APP, "cn_search_keyword_vision", lambda raw, cap: {})
    monkeypatch.setattr(APP.youtube_search, "search", fake_search)
    monkeypatch.setattr(APP, "judge_same_product", lambda p, t: ["same"] * len(t))

    client = TestClient(APP.app)
    r = client.post("/api/lens/yt", data={"source_caption": "제모기", "max_results": "12"},
                    files={"frame": ("f.jpg", b"fakebytes", "image/jpeg")})
    assert r.status_code == 200, r.text
    assert r.json()["count"] <= 12


def test_frame_없으면_캡션_폴백으로_기존동작(monkeypatch):
    """frame이 None이면 비전 호출 자체가 없다 — 기존과 동일하게 캡션 토큰으로."""
    from fastapi.testclient import TestClient

    store = {}
    monkeypatch.setattr(APP.youtube_search, "search", _fake_search_factory(store))
    monkeypatch.setattr(APP, "judge_same_product", lambda p, t: ["same"] * len(t))

    client = TestClient(APP.app)
    r = client.post("/api/lens/yt", data={"source_caption": "차량용 방향제 추천"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["keyword"] == APP._cn_keyword("차량용 방향제 추천")
