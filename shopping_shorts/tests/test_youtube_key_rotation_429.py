"""유튜브 키 로테이션 — 429(rateLimitExceeded)에서도 다음 키로 넘어가야 한다.

실사고(2026-08-17 라이브 실측):
서버 키 10개 중 1번 키가 429였는데 `search_shorts`가 403에서만 로테이션해서
**모든 검색이 조용히 0건**을 반환했다. 같은 시각 같은 키워드 실측:
    기본 로테이션(키1부터) → 0건
    키2 지정              → 50건
키 6개가 멀쩡한데 1번 키 하나 때문에 검색 경로가 통째로 죽어 있었다.

★조용한 실패라 더 위험하다 — 예외도 안 나고 빈 리스트라, 호출부는 "그런 영상이
없나 보다"로 읽는다. 매일 08:10 자동수집의 키워드 경로도 같은 상태였다.
(계정 시드 경로는 `_first_ok`를 써서 무사했다 — 그래서 수집이 0이 아니라 절반이었다)
"""
from shopping_shorts import youtube_client


def _fake_search(seq, calls):
    """호출될 때마다 seq에서 (status, items)를 하나씩 꺼내는 가짜 _search_page."""
    def fake(kw, after, max_per_kw, tok, region, lang):
        calls.append(tok)
        return seq.pop(0)
    return fake


def test_429_rotates_to_next_key(monkeypatch):
    """429면 다음 키로 넘어가 같은 키워드를 다시 시도해야 한다."""
    calls = []
    seq = [(429, None), (200, [{"video_id": "v1", "title": "살림템 추천"}])]
    monkeypatch.setattr(youtube_client, "_search_page", _fake_search(seq, calls))
    monkeypatch.setattr(youtube_client, "_stats", lambda ids, tok: {})
    monkeypatch.setattr(youtube_client, "_title_lang_ok", lambda t, l: True)
    monkeypatch.setattr(youtube_client, "_tokens_for", lambda cid=0: ["K1", "K2", "K3"])

    out = youtube_client.search_shorts(["살림템"], "2026-08-01T00:00:00Z",
                                       token=None, lang="ko")
    assert [r["video_id"] for r in out] == ["v1"], "429 뒤 다음 키 결과를 못 받았다"
    assert len(calls) == 2, "429인데 다음 키로 재시도하지 않았다"
    assert calls[0] != calls[1], "같은 키로 재시도했다 — 로테이션이 안 됐다"


def test_403_still_rotates(monkeypatch):
    """기존 403 동작은 그대로여야 한다(회귀 방지)."""
    calls = []
    seq = [(403, None), (200, [{"video_id": "v2", "title": "주방템"}])]
    monkeypatch.setattr(youtube_client, "_search_page", _fake_search(seq, calls))
    monkeypatch.setattr(youtube_client, "_stats", lambda ids, tok: {})
    monkeypatch.setattr(youtube_client, "_title_lang_ok", lambda t, l: True)
    monkeypatch.setattr(youtube_client, "_tokens_for", lambda cid=0: ["K1", "K2", "K3"])

    out = youtube_client.search_shorts(["주방템"], "2026-08-01T00:00:00Z",
                                       token=None, lang="ko")
    assert [r["video_id"] for r in out] == ["v2"]
    assert len(calls) == 2


def test_explicit_token_does_not_rotate(monkeypatch):
    """token=을 명시하면 그 키만 쓴다(기존 계약) — 429여도 로테이션 안 함."""
    calls = []
    seq = [(429, None)]
    monkeypatch.setattr(youtube_client, "_search_page", _fake_search(seq, calls))
    monkeypatch.setattr(youtube_client, "_stats", lambda ids, tok: {})
    monkeypatch.setattr(youtube_client, "_title_lang_ok", lambda t, l: True)

    out = youtube_client.search_shorts(["살림템"], "2026-08-01T00:00:00Z",
                                       token="ONLY_THIS", lang="ko")
    assert out == []
    assert calls == ["ONLY_THIS"], "단일 토큰 지정인데 다른 키를 썼다"
