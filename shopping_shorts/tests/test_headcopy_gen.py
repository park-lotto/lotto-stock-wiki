"""고정카피 생성 — AI가 죽어도 화면이 죽지 않는가(fail-open)를 함께 잠근다."""
from shopping_shorts import headcopy_gen


def test_returns_four_copies(monkeypatch):
    monkeypatch.setattr(headcopy_gen, "_call_json", lambda p, s: {"copies": [
        {"label": "짧은 훅형", "text": "이거 모르면 손해"},
        {"label": "숫자형", "text": "3초면 끝납니다"},
        {"label": "반전형", "text": "비싼 줄 알았는데"},
        {"label": "질문형", "text": "아직도 손으로 하세요?"},
    ]})
    out = headcopy_gen.suggest("대본 텍스트입니다")
    assert len(out) == 4
    assert out[0]["text"] == "이거 모르면 손해"
    assert out[0]["label"] == "짧은 훅형"


def test_empty_script_skips_ai_entirely(monkeypatch):
    """대본이 없으면 AI를 부르지 않는다 — 부르면 빈 재료로 지어내고 돈만 쓴다."""
    called = []
    monkeypatch.setattr(headcopy_gen, "_call_json", lambda p, s: called.append(1) or {})
    assert headcopy_gen.suggest("   ") == []
    assert called == [], "빈 대본인데 AI를 불렀다"


def test_ai_failure_returns_empty_not_crash(monkeypatch):
    """_call_json은 실패 시 {}를 준다(fail-open). 그걸 그대로 흘리면 화면이 깨진다."""
    monkeypatch.setattr(headcopy_gen, "_call_json", lambda p, s: {})
    assert headcopy_gen.suggest("대본") == []


def test_drops_blank_and_overlong(monkeypatch):
    """빈 문구·너무 긴 문구는 버린다 — 헤드카피는 화면에 크게 박히는 한 줄이다."""
    monkeypatch.setattr(headcopy_gen, "_call_json", lambda p, s: {"copies": [
        {"label": "a", "text": "  "},
        {"label": "b", "text": "정상 문구"},
        {"label": "c", "text": "가" * 200},
    ]})
    out = headcopy_gen.suggest("대본")
    assert [c["text"] for c in out] == ["정상 문구"]


def test_dedupes_identical_text(monkeypatch):
    monkeypatch.setattr(headcopy_gen, "_call_json", lambda p, s: {"copies": [
        {"label": "a", "text": "같은 문구"},
        {"label": "b", "text": "같은 문구"},
        {"label": "c", "text": "다른 문구"},
    ]})
    assert [c["text"] for c in headcopy_gen.suggest("대본")] == ["같은 문구", "다른 문구"]


def test_copies_not_a_list_returns_empty(monkeypatch):
    """copies가 배열이 아니라 문자열이면(스키마 위반) 문자 단위로 순회되며 .get()이 터진다 — 실제로 잡았던 크래시."""
    monkeypatch.setattr(headcopy_gen, "_call_json", lambda p, s: {"copies": "not a list"})
    assert headcopy_gen.suggest("대본") == []


def test_copy_item_empty_dict_returns_empty(monkeypatch):
    """항목이 label/text 없는 빈 dict여도 죽지 않고 그냥 걸러진다."""
    monkeypatch.setattr(headcopy_gen, "_call_json", lambda p, s: {"copies": [{}]})
    assert headcopy_gen.suggest("대본") == []


def test_copies_none_returns_empty(monkeypatch):
    """copies 키 값 자체가 None이면(스키마상 있어야 할 배열이 null) 빈 리스트로 취급한다."""
    monkeypatch.setattr(headcopy_gen, "_call_json", lambda p, s: {"copies": None})
    assert headcopy_gen.suggest("대본") == []


def test_call_json_returns_non_dict_returns_empty(monkeypatch):
    """_call_json 자체가 dict가 아닌 값(None·문자열)을 주면 fail-open 계약이 깨진 것 — 그래도 죽지 않아야 한다."""
    monkeypatch.setattr(headcopy_gen, "_call_json", lambda p, s: None)
    assert headcopy_gen.suggest("대본") == []
    monkeypatch.setattr(headcopy_gen, "_call_json", lambda p, s: "junk")
    assert headcopy_gen.suggest("대본") == []


def test_skips_bad_item_keeps_valid_one(monkeypatch):
    """섞여 들어온 이상한 항목 하나 때문에 나머지 정상 항목까지 통째로 버려지면 안 된다."""
    monkeypatch.setattr(headcopy_gen, "_call_json", lambda p, s: {"copies": [
        "junk", {"label": "a", "text": "정상 문구"},
    ]})
    assert [c["text"] for c in headcopy_gen.suggest("대본")] == ["정상 문구"]


def test_int_label_and_text_returns_empty(monkeypatch):
    """스키마는 string을 요구해도 Gemini가 int를 줄 수 있다 — truthy라 `or ""`를 안 타고 .strip()에서 죽는다."""
    monkeypatch.setattr(headcopy_gen, "_call_json", lambda p, s: {"copies": [
        {"label": 5, "text": 7},
    ]})
    assert headcopy_gen.suggest("대본") == []


def test_list_text_returns_empty(monkeypatch):
    """text가 리스트처럼 문자열이 아닌 truthy 값이어도 .strip()에서 죽지 않고 걸러져야 한다."""
    monkeypatch.setattr(headcopy_gen, "_call_json", lambda p, s: {"copies": [
        {"label": "정상", "text": ["리스트"]},
    ]})
    assert headcopy_gen.suggest("대본") == []


def test_bad_label_falls_back_but_keeps_good_text(monkeypatch):
    """label만 이상해도(text는 멀쩡) 그 카피 전체를 버리면 안 된다 — label은 '제안'으로 대체."""
    monkeypatch.setattr(headcopy_gen, "_call_json", lambda p, s: {"copies": [
        {"label": {"d": 1}, "text": "정상 문구"},
    ]})
    out = headcopy_gen.suggest("대본")
    assert out == [{"label": "제안", "text": "정상 문구"}]


def test_mixed_batch_int_text_and_valid_item(monkeypatch):
    """배치 하나에 int text 불량 항목과 정상 항목이 섞이면, 정상 항목만 살아남는다."""
    monkeypatch.setattr(headcopy_gen, "_call_json", lambda p, s: {"copies": [
        {"label": "a", "text": 999},
        {"label": "b", "text": "정상 문구"},
    ]})
    assert [c["text"] for c in headcopy_gen.suggest("대본")] == ["정상 문구"]
