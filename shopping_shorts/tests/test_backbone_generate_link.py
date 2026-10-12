"""2단계 백본 연결(_backbone_drafts) — 자동 1안 + 고른 1안, 통과본만, 실패 이유 노출.

★2026-09-20 구조 변경: 씨앗 유형으로 후보를 정하고(자동 안), 사용자가 고른 원문형 스파인으로 한 안 더.
  검사에 걸린 스파인은 안 쓰고 why에 이유를 남긴다(조용한 폴백 금지).
"""
from shopping_shorts import app as A
from shopping_shorts import backbone_assemble as ba


def _job(bm=None):
    def seg(v, i):
        return {"seg_id": f"{v}-{i}", "start": i, "end": i + 2, "scene_desc": "장면"}
    return {"backbone_main": bm, "extract": {
        "s0": {"video_id": "AAA", "full_text": "짧은 한국어 원문", "segments": [seg("AAA", 0)]},
        "s1": {"video_id": "BBB", "full_text": "훨씬 더 긴 한국어 원문 문장입니다 여기", "segments": [seg("BBB", 0)]},
    }}


def _spine(sid, name, typ="지인증언형"):
    return {"id": sid, "name": name, "fit_categories": [typ],
            "templates": {"_origin": {"cells": [{"role": "훅", "text": "훅."}], "hook_tpl": "훅."}}}


def test_auto_and_picked(monkeypatch):
    """자동 안(씨앗 유형)과 고른 안이 각각 한 편씩. 자동 안에는 auto_pick 표시."""
    monkeypatch.setattr(ba, "seed_type", lambda *a, **k: "지인증언형")
    monkeypatch.setattr(ba, "origin_spines", lambda store, typ, limit=6: [_spine(1, "자동틀")])

    def fake_clean(sources, bb, store, spines, **kw):
        if not spines:
            return []
        sp = spines[0]
        return [{"spine": sp, "given": "한 줄.\n두 줄.",
                 "beat_sources": [{"role": "훅", "seg": "BBB-0", "segs": ["BBB-0"]}] * 2,
                 "meta": {"spine": {"id": sp["id"], "name": sp["name"]}, "note": {}}}]
    monkeypatch.setattr(ba, "assemble_clean", fake_clean)

    drafts, why = A._backbone_drafts([_spine(2, "고른틀")], _job(0), None)
    assert [d["style_name"] for d in drafts] == ["자동틀", "고른틀"]
    assert [d["auto_pick"] for d in drafts] == [True, False]
    assert drafts[0]["seed_type"] == "지인증언형"
    assert why == ""


def test_skipped_reason_is_reported(monkeypatch):
    """통과본이 없으면 빈 목록 + 왜 안 썼는지(화면이 옛 경로로 가되 이유를 싣는다)."""
    monkeypatch.setattr(ba, "seed_type", lambda *a, **k: "오용형")
    monkeypatch.setattr(ba, "origin_spines", lambda store, typ, limit=6: [_spine(1, "틀", "오용형")])

    def none_clean(sources, bb, store, spines, **kw):
        note = kw.get("note")
        if note is not None:
            note["skipped"] = [{"spine": "틀", "why": "딴 용도 장면 없음"}]
        return []
    monkeypatch.setattr(ba, "assemble_clean", none_clean)

    drafts, why = A._backbone_drafts([], _job(), None)
    assert drafts == [] and "딴 용도 장면 없음" in why


def test_no_extract_is_reported():
    drafts, why = A._backbone_drafts([], {"extract": {}}, None)
    assert drafts == [] and why
