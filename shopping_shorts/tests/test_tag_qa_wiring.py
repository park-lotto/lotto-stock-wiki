"""태깅 QA 배선 — extract_script가 QA 점수를 보고 한 번 고쳐 부르는지 검증.

Gemini를 부르지 않는다: 재시도 판단 로직을 순수 함수(`_qa_retry_decision`)로 분리하고
그것만 테스트한다. 실제 API 경로는 기존 재시도 루프를 그대로 쓴다.
"""
from shopping_shorts import script_extract, tag_qa


def _good(n=3, dur=15.0):
    step = dur / n
    segs = [{"seg_id": f"v-{i}", "start": round(i * step, 1), "end": round((i + 1) * step, 1),
             "text": f"{i}번째 나레이션입니다요", "scene_desc": f"{i}번째 서로 다른 화면 묘사",
             "shot_role": "사용중", "change": "재료가 노릇해진다", "is_key": True}
            for i in range(n)]
    return {"segments": segs, "full_text": " ".join(s["text"] for s in segs),
            "product_benefits": ["기름이 안 튄다"]}


def _bad():
    """훅 누락 + 시간역전 + shot_role 붕괴 — 점수가 확실히 문턱 밑으로 떨어지는 결과."""
    r = _good()
    r["segments"][0]["start"] = 5.0
    r["segments"][1]["end"] = r["segments"][1]["start"] - 1.0
    for s in r["segments"]:
        s["shot_role"] = "기타"
        s["scene_desc"] = "요리"
        s["change"] = ""
    return r


def test_good_result_does_not_trigger_retry():
    should_retry, hint = script_extract._qa_retry_decision(_good(), 15.0, already_retried=False)
    assert should_retry is False
    assert hint == ""


def test_bad_result_triggers_retry_with_flags_in_hint():
    """재시도 프롬프트에 '무엇이 틀렸는지'가 실제로 실려야 모델이 고칠 수 있다."""
    should_retry, hint = script_extract._qa_retry_decision(_bad(), 15.0, already_retried=False)
    assert should_retry is True
    assert "지난 시도의 문제" in hint
    assert "훅" in hint, f"훅 누락이 힌트에 없다: {hint}"


def test_never_retries_twice():
    """딱 1회 — 이미 QA 재시도를 했으면 아무리 점수가 낮아도 그대로 간다(비용·루프 방지)."""
    should_retry, hint = script_extract._qa_retry_decision(_bad(), 15.0, already_retried=True)
    assert should_retry is False


def test_attach_qa_records_score_and_flags_without_dropping_result():
    """fail-open 핵심: 점수가 낮아도 segments를 절대 버리지 않는다."""
    bad = _bad()
    out = script_extract._attach_qa(bad, 15.0, retried=True)
    assert out["segments"] == bad["segments"], "결과를 버리거나 바꾸면 안 된다"
    assert out["tag_qa"]["score"] < 0.6
    assert out["tag_qa"]["flags"], "왜 낮은지 이유가 남아야 한다"
    assert out["tag_qa"]["retried"] is True


def test_attach_qa_on_good_result_records_high_score():
    out = script_extract._attach_qa(_good(), 15.0, retried=False)
    assert out["tag_qa"]["score"] >= 0.9
    assert out["tag_qa"]["flags"] == []
    assert out["tag_qa"]["retried"] is False


def test_pick_better_keeps_higher_scoring_attempt():
    """재시도 결과가 더 나쁘면 첫 시도를 쓴다 — 재시도가 품질을 깎지 않게."""
    first, second = _good(), _bad()
    assert script_extract._pick_better_extract(first, second, 15.0) is first
    assert script_extract._pick_better_extract(second, first, 15.0) is first


def test_pick_better_falls_back_when_retry_is_empty():
    """재시도가 빈 결과(API 실패)면 첫 시도를 그대로 쓴다."""
    first = _good()
    assert script_extract._pick_better_extract(first, {"segments": []}, 15.0) is first


def test_video_duration_returns_none_on_ffprobe_failure(monkeypatch):
    """ffprobe가 죽어도 QA가 멈추면 안 된다 — None이면 길이 검사만 건너뛴다."""
    monkeypatch.setattr(script_extract.scene_cut, "video_fps",
                        lambda p: (_ for _ in ()).throw(RuntimeError("no ffprobe")))
    assert script_extract._video_duration("nonexistent.mp4") is None


def test_qa_decision_survives_unknown_duration():
    """duration을 몰라도(None) 판단이 크래시 없이 나와야 한다."""
    should_retry, hint = script_extract._qa_retry_decision(_bad(), None, already_retried=False)
    assert isinstance(should_retry, bool)
