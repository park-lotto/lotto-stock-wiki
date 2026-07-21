from shopping_shorts.edit_plan import _reconcile_weak_beats


def _beat(idx, narr, fit, scene, respined=False):
    return {"beat_idx": idx, "narration": narr, "fit": fit, "respined": respined,
            "primary": {"scene_desc": scene}}


def test_only_weak_anchor_beats_reworded():
    beats = [_beat(0, "결대로 찢어진다", 2, "도우를 치댄다"),      # 약함+앵커 → 대상
             _beat(1, "완성입니다", 5, "완성품 클로즈업"),          # fit 높음 → 제외
             _beat(2, "촉촉해요", 1, "도우 반죽", respined=True)]   # respined → 제외
    def fake_call(prompt, schema, **kw):
        return {"rewrites": [{"beat_idx": 0, "narration": "반죽을 정성껏 치대요"}]}
    out = _reconcile_weak_beats(beats, call=fake_call)
    assert out[0]["narration"] == "반죽을 정성껏 치대요"
    assert out[1]["narration"] == "완성입니다" and out[2]["narration"] == "촉촉해요"


def test_reconcile_fail_open_keeps_original():
    beats = [_beat(0, "결대로 찢어진다", 2, "도우를 치댄다")]
    out = _reconcile_weak_beats(beats, call=lambda *a, **k: None)  # Gemini 실패
    assert out[0]["narration"] == "결대로 찢어진다"


def test_no_weak_beats_noop():
    beats = [_beat(0, "완성", 5, "완성품")]
    calls = []
    _reconcile_weak_beats(beats, call=lambda *a, **k: calls.append(1))
    assert calls == []   # 대상 0개면 Gemini 호출 자체를 안 함
