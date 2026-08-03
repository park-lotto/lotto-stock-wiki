"""쿠팡 검색어 다듬기 — 파싱·폴백 계약(Gemini 호출 없이 돈다)."""
from shopping_shorts import coupang_query as cq


def test_parse_queries_plain_json():
    raw = '{"queries": ["옷 프린팅 복원제", "열전사 필름", "의류 리페어 접착제"]}'
    assert cq.parse_queries(raw) == ["옷 프린팅 복원제", "열전사 필름", "의류 리페어 접착제"]


def test_parse_queries_tolerates_code_fence():
    """모델이 ```json 을 붙여도 살려낸다 — 여기서 죽으면 매번 폴백만 나간다."""
    raw = "```json\n{\"queries\": [\"주방 가림막\"]}\n```"
    assert cq.parse_queries(raw) == ["주방 가림막"]


def test_parse_queries_dedupes_and_drops_junk():
    raw = '{"queries": ["집게", "집게", "", "  ", "가"]}'
    assert cq.parse_queries(raw) == ["집게"]      # 빈값·1글자는 버린다


def test_parse_queries_bad_input_is_empty():
    assert cq.parse_queries("모르겠습니다") == []
    assert cq.parse_queries("") == []


def test_parse_queries_respects_limit():
    raw = '{"queries": ["가나", "다라", "마바", "사아"]}'
    assert len(cq.parse_queries(raw, limit=2)) == 2


def test_suggest_falls_back_to_target_without_keys(monkeypatch):
    """★키가 소진돼도 기능이 멈추면 안 된다 — 원래 타깃으로 검색은 되어야 한다."""
    from shopping_shorts import comment_gen
    monkeypatch.setattr(comment_gen, "_next_live_key_and_idx", lambda: (None, None))
    assert cq.suggest("실리콘 집게", "대본") == ["실리콘 집게"]


def test_suggest_keeps_target_as_last_resort(monkeypatch):
    """AI가 헛다리를 짚었을 때 되돌아갈 자리로 타깃을 뒤에 남긴다."""
    from shopping_shorts import comment_gen

    class _Resp:
        text = '{"queries": ["옷 프린팅 복원제"]}'

    class _Models:
        def generate_content(self, **kw):
            return _Resp()

    class _Client:
        models = _Models()

    monkeypatch.setattr(comment_gen, "_next_live_key_and_idx", lambda: ("k", 0))
    monkeypatch.setattr(comment_gen, "_client_for_key", lambda k: _Client())
    assert cq.suggest("갈라진 프린팅 수선", "대본") == ["옷 프린팅 복원제", "갈라진 프린팅 수선"]
