"""2단계 백본 연결(_backbone_drafts) — 씨앗 선택·실패 이유·초안 모양."""
from shopping_shorts import app as A
from shopping_shorts import backbone_assemble as ba


def _job(bm=None):
    seg = lambda v, i: {"seg_id": f"{v}-{i}", "start": i, "end": i + 2, "scene_desc": "펜"}
    return {"backbone_main": bm, "extract": {
        "s0": {"video_id": "AAA", "full_text": "짧은 한국어 원문", "segments": [seg("AAA", 0)]},
        "s1": {"video_id": "BBB", "full_text": "훨씬 더 긴 한국어 원문 문장입니다 여기", "segments": [seg("BBB", 0)]},
    }}


def test_seed_is_backbone_main_else_longest_korean(monkeypatch):
    seen = []

    def fake(srcs, bb, store, spine_id=None, target_seconds=25, seed=None, note=None):
        seen.append(bb)
        return "훅.\n특징.\n끝.", [{"role": "hook", "seg": "BBB-0", "segs": ["BBB-0"]}] * 3, {
            "spine": {"id": spine_id, "name": "S"}, "note": {}}
    monkeypatch.setattr(ba, "assemble", fake)
    d, why = A._backbone_drafts([{"id": 5, "name": "S"}], _job(0), None)
    assert seen[-1] == "AAA" and why == ""
    assert d[0]["made_by"] == "백본" and d[0]["beats"][0]["src_segs"] == ["BBB-0"]
    A._backbone_drafts([{"id": 5, "name": "S"}], _job(None), None)
    assert seen[-1] == "BBB"


def test_failure_reason_is_reported(monkeypatch):
    def fail(*a, note=None, **k):
        note["reason"] = "groups_empty"
        return None, None, {"note": note}
    monkeypatch.setattr(ba, "assemble", fail)
    d, why = A._backbone_drafts([{"id": 5, "name": "S"}], _job(), None)
    assert d == [] and "groups_empty" in why
    assert A._backbone_drafts([{"id": 5}], {"extract": {}}, None)[1]
