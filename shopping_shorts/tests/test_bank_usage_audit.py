from shopping_shorts.bank_usage_audit import structural_conformance


def _plan(beats, plag=None):
    return {"beats": beats, "plagiarism_flags": plag or []}


def test_conformant_when_opener_cta_beats_ok():
    beats = [{"narration": "이거 진짜 대박인데요?"}, {"narration": "b"},
             {"narration": "c"}, {"narration": "d"}, {"narration": "e"}]
    snap = {"spine_beats": 3}
    story = {"cta_line": "프로필 링크 확인하세요"}
    conf = structural_conformance(_plan(beats), snap, story)
    assert conf["beat_ok"] is True
    assert conf["opener_ok"] is True
    assert conf["cta_ok"] is True
    assert conf["plagiarism_hits"] == 0
    assert conf["conformant"] is True


def test_not_conformant_weak_opener_no_cta_short():
    beats = [{"narration": "매번 이렇게 하던 참이었거든요"}, {"narration": "b"}]
    snap = {"spine_beats": 5}
    story = {"cta_line": ""}
    conf = structural_conformance(_plan(beats), snap, story)
    assert conf["beat_ok"] is False       # 2 < max(5,5)
    assert conf["opener_ok"] is False
    assert conf["cta_ok"] is False
    assert conf["conformant"] is False


def test_plagiarism_breaks_conformance():
    beats = [{"narration": "이거 몰라서 손해 봤잖아요"}] + [{"narration": str(i)} for i in range(5)]
    story = {"cta_line": "댓글 남겨주세요"}
    conf = structural_conformance(_plan(beats, plag=[{"beat": 0}]), {"spine_beats": 3}, story)
    assert conf["plagiarism_hits"] == 1
    assert conf["conformant"] is False
