# -*- coding: utf-8 -*-
"""각 단계 전문가 지침서(2026-10-02 사장님 "영상추출분석 전문가 / 영상대본작가 / 장면매칭 전문가 — 지침서가 확실하게").
지침서 문구가 실제 프롬프트에 붙는지 본다(상수만 있고 안 붙으면 아무것도 안 바뀐다)."""
import inspect

from shopping_shorts import script_extract as se, backbone_assemble as ba, ai_match as am


def test_stage1_analyst_brief():
    g = se._SEG_FIELD_GUIDE
    assert "영상 추출·분석 전문가" in g and "밑작업" in g and "꼭 필요한가" in g


def test_stage2_writer_brief_on_all_three_prompts():
    assert "영상 대본 작가" in ba.WRITER_BRIEF and "장면 매칭 전문가" in ba.WRITER_BRIEF
    for fn in (ba._spine_prompt, ba.write_lines, ba.write_lines_from_origin):
        assert "WRITER_BRIEF" in inspect.getsource(fn), fn.__name__


def test_stage3_matcher_brief():
    assert "대본과 장면을 딱 맞게 배치하는 최고 전문가" in am.BRIEF


def test_stage2_writer_brief_on_customer_path_with_one_style():
    """고객 경로(이야기작가 write)도 같은 대본 작가 지침서 + 스타일 하나. 지위 문구('너는')는 지침서에만 — 두 번 말하지 않는다."""
    from shopping_shorts import story_writer as sw
    seen = {}
    def fake(prompt, schema, **k):
        seen.setdefault("p", []).append(prompt)
        return {}
    sw._sg._call_json, _orig = fake, sw._sg._call_json
    try:
        for plat in ("yt", "ig"):
            try:
                sw.write("거치대", "씨앗", [{"name": "a", "claim": "고리 쓱", "from_cuts": ["s1-0"]}], platform=plat)
            except Exception:
                pass
    finally:
        sw._sg._call_json = _orig
    ps = seen.get("p") or []
    assert len(ps) >= 2
    for p in ps:
        assert p.startswith(ba.WRITER_BRIEF) and p.count("너는") == 1
    assert "유튜브 썰쇼핑" in ps[0] and "인스타 릴스 체험담" not in ps[0]
    assert "인스타 릴스 체험담" in ps[-1] and "유튜브 썰쇼핑" not in ps[-1]


def test_seedless_makes_drafts_instead_of_refusing(monkeypatch):
    """씨앗 없음(외국 영상만) — 막지 않고 재료만으로 쓴다(2026-10-02 사장님). 씨앗 안내문이 대본에 새지 않는다."""
    from shopping_shorts import story_writer as sw
    assert len(sw.SEEDLESS_NOTE) >= 60
    seen = {}
    def fake_feats(vis, product, note=None, seed_text=""):
        seen["vis"] = [s.get("video_id") for s in vis]; seen["seed"] = seed_text
        return [{"name": "고정", "claim": "손가락 꾹 당겨 고정", "from_cuts": ["s0-1"], "pain": "", "kind": "기능", "seed_quote": "", "seed_point": 0}]
    monkeypatch.setattr(sw, "extract_feats", fake_feats)
    monkeypatch.setattr(sw, "write", lambda *a, **k: [{"role": "훅", "text": "꿀잠 각", "group": 0}, {"role": "마무리", "text": "끝", "group": -1}])
    job = {"extract": {"s0": {"full_text": "hi", "source_brief": {"product": "목베개"},
                              "segments": [{"seg_id": "s0-1", "start": 0, "end": 3, "scene_desc": "고정"}]}}}
    drafts, why = sw.make_drafts([], job, 25, job_id="t", seed_text="")
    assert "너무 짧음" not in (why or "")
    assert seen.get("vis") == ["s0"] and seen.get("seed") == sw.SEEDLESS_NOTE


def test_writer_brief_allows_hype_bans_fake_numbers():
    assert "마음껏 써도 된다" in ba.WRITER_BRIEF and "판매량" in ba.WRITER_BRIEF
