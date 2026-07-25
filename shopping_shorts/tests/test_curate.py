from shopping_shorts import curate


def test_judge_parts_keeps_and_rejects():
    captured = {}

    def fake_call(prompt, schema):
        captured["prompt"] = prompt
        # 모델이 훅 품질 판정: 1=스토리/강한주장 keep, 2=밋밋한 설명 reject
        return {"verdicts": [{"id": 1, "keep": True}, {"id": 2, "keep": False}]}

    items = [{"id": 1, "text": "주말에 시부모님 오신다고 해서 급하게 만든 건데"},
             {"id": 2, "text": "여러분 감자는 이렇게 드세요"}]
    out = curate.judge_parts(items, "hook", call=fake_call)
    assert out == {1: True, 2: False}
    assert "시부모님" in captured["prompt"] and "감자는 이렇게" in captured["prompt"]


def test_judge_parts_empty_or_nocall():
    assert curate.judge_parts([], "hook", call=lambda *a, **k: {}) == {}
    assert curate.judge_parts([{"id": 1, "text": "x"}], "hook", call=lambda *a, **k: None) == {}


def test_judge_parts_missing_verdict_defaults_keep():
    # 판정 누락된 부품은 기각하지 않음(보수적 — 억울한 삭제 방지)
    fake = lambda p, s: {"verdicts": [{"id": 1, "keep": False}]}
    items = [{"id": 1, "text": "밋밋"}, {"id": 2, "text": "판정없음"}]
    out = curate.judge_parts(items, "hook", call=fake)
    assert out == {1: False}   # 2는 결과에 없음 → 호출부가 유지
