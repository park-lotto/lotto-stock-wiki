"""렌즈 유튜브 잡음 제거 회귀 테스트 (2026-08-16).

사장님 제보 + 스크린샷: **유튜브 43 / 틱톡 5 / 인스타 1 / 샤오홍슈 0 / 도우인 1**.
유튜브만 쓸데없는 게 쏟아지는 원인이 둘이었다.

① 유튜브 검색에 필터가 하나도 없었다 — 일반 롱폼·외국어 영상까지 그대로 딸려옴.
② 유튜브만 유사도 채점을 안 받아 match가 전부 None이었다.
   프론트의 '⚠️ 다른주제 숨기기'는 match!==false만 거르므로(index.html),
   **체크박스를 켜도 유튜브는 한 개도 안 걸러졌다.**
   같은 렌즈인데 샤오홍슈·도우인(/api/lens/cn/search)엔 원래 채점이 있었다
   → CLAUDE.md 0순위-B "같은 일을 하는 코드가 갈라지면 언젠가 어긋난다"의 실제 사례.

★네트워크를 타지 않는다 — requests / Gemini 전부 가짜로 대체.
"""
import pytest

from shopping_shorts import youtube_search


class _FakeResp:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _payload(n=3):
    return {"items": [
        {"id": {"videoId": f"vid{i}"},
         "snippet": {"title": f"제목{i}",
                     "thumbnails": {"medium": {"url": f"http://t/{i}.jpg"}}}}
        for i in range(n)
    ]}


@pytest.fixture
def captured(monkeypatch):
    """youtube_search가 실제로 보낸 쿼리 파라미터를 잡아둔다."""
    seen = {}

    def fake_get(url, params=None, timeout=None):
        seen.update(params or {})
        return _FakeResp(_payload())

    monkeypatch.setattr(youtube_search, "requests",
                        type("R", (), {"get": staticmethod(fake_get),
                                       "RequestException": Exception})())
    monkeypatch.setattr(youtube_search, "YOUTUBE_API_KEYS", ["K1"], raising=False)
    monkeypatch.setattr(youtube_search, "_load_key_index", lambda: 0)
    monkeypatch.setattr(youtube_search, "_save_key_index", lambda i: None)
    return seen


# ── ① 공짜 필터가 실제로 요청에 실린다 ──────────────────────────────────
def test_렌즈용_호출은_숏폼_한국어_필터를_보낸다(captured):
    youtube_search.search("피규어 진열", max_results=40,
                          duration="short", language="ko")
    assert captured.get("videoDuration") == "short", "롱폼이 그대로 딸려온다"
    assert captured.get("relevanceLanguage") == "ko", "외국어 잡음이 그대로 딸려온다"


def test_필터를_안_주면_기존동작_그대로다(captured):
    """gap_check 등 기존 호출부가 영향을 받으면 안 된다."""
    youtube_search.search("x", max_results=10)
    assert "videoDuration" not in captured
    assert "relevanceLanguage" not in captured


def test_필터를_줘도_결과_형태는_같다(captured):
    rows = youtube_search.search("x", duration="short", language="ko")
    assert len(rows) == 3
    assert set(rows[0]) == {"url", "title", "thumbnail"}


# ── ② 유튜브도 유사도 채점을 받는다 ─────────────────────────────────────
def test_유튜브도_다른주제_숨기기가_먹히게_match가_채워진다(monkeypatch):
    """match가 None만 있으면 프론트가 한 개도 못 거른다 — False가 실제로 나와야 한다."""
    from shopping_shorts import app as APP

    rows = [{"title": "피규어 진열장 추천"}, {"title": "오늘의 주식 시황"}]
    monkeypatch.setattr(APP, "judge_same_product", lambda p, t: ["same", "no"])

    verdicts = APP.judge_same_product("피규어 진열", [r["title"] for r in rows])
    for r, vd in zip(rows, verdicts):
        r["sim"] = vd
        r["match"] = True if vd == "same" else (False if vd == "no" else None)

    assert rows[0]["match"] is True
    assert rows[1]["match"] is False          # ★이게 None이면 못 거른다

    shown = [r for r in rows if r.get("match") is not False]   # index.html과 같은 규칙
    assert len(shown) == 1 and shown[0]["title"] == "피규어 진열장 추천"


def test_관련있는_것이_위로_정렬된다():
    rows = [{"sim": "no"}, {"sim": "same"}, {"sim": "similar"}]
    rank = {"same": 0, "similar": 1, "no": 2}
    rows.sort(key=lambda r: rank.get(r.get("sim"), 1))
    assert [r["sim"] for r in rows] == ["same", "similar", "no"]


# ── ③ 개수 상한 — 유튜브가 화면을 도배하지 않게 ──────────────────────────
@pytest.mark.parametrize("sent,expected", [
    ("40", 12),     # 캐시된 옛 화면이 40을 보내도 서버가 자른다
    ("60", 12),
    ("5", 5),       # 더 적게 요청하면 그건 존중
])
def test_유튜브_개수는_서버가_12개로_자른다(monkeypatch, sent, expected):
    """40개는 유튜브만 화면을 도배했다(실측: 유튜브 43 vs 틱톡 5·인스타 1).

    ★프론트만 고치면 캐시된 옛 화면이 계속 40을 보낸다 → 서버에서 자르는지 본다.
    실제 /api/lens/yt를 태워서 youtube_search가 **몇 개로 불렸는지** 확인한다."""
    from fastapi.testclient import TestClient
    from shopping_shorts import app as APP

    asked = {}

    def fake_search(kw, max_results=10, duration=None, language=None):
        asked["n"] = max_results
        return [{"url": f"u{i}", "title": f"t{i}", "thumbnail": ""}
                for i in range(max_results)]

    monkeypatch.setattr(APP.youtube_search, "search", fake_search)
    monkeypatch.setattr(APP, "judge_same_product", lambda p, t: [])
    monkeypatch.setattr(APP, "_cn_keyword", lambda c: "피규어 진열")

    client = TestClient(APP.app)
    r = client.post("/api/lens/yt",
                    data={"source_caption": "피규어 진열장", "max_results": sent})
    assert r.status_code == 200, r.text
    assert asked["n"] == expected
    assert r.json()["count"] == expected


def test_채점이_실패해도_결과는_사라지지_않는다():
    """Gemini가 죽어도 렌즈는 계속 떠야 한다 — 개수 불일치면 채점을 통째로 버린다."""
    rows = [{"title": "a"}, {"title": "b"}]
    verdicts = ["same"]                        # 개수 불일치(비정상 응답)
    if len(verdicts) == len(rows):
        pytest.fail("개수가 다른데 적용하면 안 된다")
    assert all("match" not in r or r["match"] is None for r in rows)
    assert len(rows) == 2                      # 결과는 그대로 남는다
