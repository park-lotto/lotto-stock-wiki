from shopping_shorts.bank_usage_audit import structural_conformance, judge_snapshot, usage_health, compute_usage_audit


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


def test_judge_snapshot_picks_recommended_and_gap():
    cands = [{"score": 0.4, "recommended": False},
             {"score": 0.8, "recommended": True,
              "judge": {"script_quality": 4, "scene_sync": 3, "storyline": 5, "total": 0.8}}]
    js = judge_snapshot(cands)
    assert js["judged"] is True
    assert js["total"] == 0.8
    assert js["axes"]["storyline"] == 5
    assert abs(js["best_gap"] - 0.4) < 1e-9


def test_judge_snapshot_none_when_no_judge():
    js = judge_snapshot([{"score": 0.5, "recommended": True}])
    assert js["judged"] is False
    assert js["total"] is None
    assert js["best_gap"] is None   # 후보 1개


def test_usage_health_red_when_bank_unused():
    h = usage_health({"bank_used_rate": 0.49, "conformance_pass_rate": 0.9,
                      "plagiarism_rate": 0.0, "compliance": None})
    assert h["level"] == "🔴"
    assert any("무용" in r for r in h["reasons"])


def test_usage_health_yellow_on_low_conformance():
    h = usage_health({"bank_used_rate": 0.9, "conformance_pass_rate": 0.69,
                      "plagiarism_rate": 0.0, "compliance": None})
    assert h["level"] == "🟡"


def test_usage_health_green_all_pass():
    h = usage_health({"bank_used_rate": 0.9, "conformance_pass_rate": 0.8,
                      "plagiarism_rate": 0.05, "compliance": {"arc_avg": 3.5}})
    assert h["level"] == "🟢"


def test_compute_usage_audit_aggregates():
    recent = [
        {"snapshot": {"empty": False, "spine_present": True, "parts_total": 10},
         "conformance": {"conformant": True, "plagiarism_hits": 0},
         "judge": {"judged": True, "total": 0.8}, "compliance": None},
        {"snapshot": {"empty": True, "spine_present": False, "parts_total": 0},
         "conformance": {"conformant": False, "plagiarism_hits": 1},
         "judge": {"judged": False, "total": None},
         "compliance": {"arc_follow": 4, "flavor_follow": 3, "verbatim_copy": False}},
    ]
    agg = compute_usage_audit(recent)
    assert agg["n"] == 2
    assert agg["bank_used_rate"] == 0.5
    assert agg["plagiarism_rate"] == 0.5
    assert agg["judge_avg"] == 0.8            # judged 레코드만
    assert agg["compliance"]["arc_avg"] == 4.0
    assert agg["compliance"]["n"] == 1
    assert "level" in agg["health"]


def test_compute_usage_audit_empty_is_none_safe():
    agg = compute_usage_audit([])
    assert agg["n"] == 0
    assert agg["judge_avg"] is None
    assert agg["compliance"] is None
    assert agg["health"]["level"] == "🟢"
