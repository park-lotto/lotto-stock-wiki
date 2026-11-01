"""10-31 썰템홈샷 납품 공정(동일화명세 §2): 남의 영상 포인트 · 줄별 대조표 · 훅 장면 · 고르기 개수. 칸 없는 판은 질문 불변."""
import pytest

from tools.calcopy.hybrid import flow as F, runner_ops as RO

V = "썰템홈샷판"
OTHER = "키치잇판"


def _st(v=V, **kw):
    return {"version": v, "log": [], "tries": {}, "product": {"name": "요플레", "product_id": "1"},
            "bench": {"id": "b1", "title": "요플레 뚜껑", "channel": "방구석"}, "read": {"celeb": ""}, "bench_lines": [], "reviews": [],
            "script": {"S": {"lines": [{"id": "A1", "kind": "tts"}, {"id": "A2", "kind": "tts"}]}, "M": {}}, **kw}


def test_shop_research_gathers_peers_first_then_asks_table():
    st = _st()
    r = F.s_research(st, {}, {}, {})
    d = r["do"][0]
    assert d["cmd"] == "peer_points" and d["n"] == 4 and d["skip_channel"] == "방구석" and d["skip_ids"] == ["b1"] and r["then"] == "s_peers_got"
    r2 = F.s_peers_got(st, {"peers": {"videos": [{"id": "p", "title": "t", "text": "뚜껑 놀라운 사실"}]}}, {}, {})
    assert "뚜껑 놀라운 사실" in r2["review"][0]["ask"] and "남의 영상 포인트" in r2["review"][0]["ask"]


def test_research_rejected_without_point_table_only_when_subs_came():
    rp = {"research": {"조사_md": "결론 출처 사실 금지 확인 못", "keywords": [], "queries": []}}
    r = F.s_research_check(_st(peer_videos=[{"id": "p", "text": "x"}]), {}, rp, {})
    assert r["reject"] and "남의 영상 포인트" in r["reject"]["why"]
    assert F.s_research_check(_st(peer_videos=[]), {}, rp, {})["then"] == "material"


def test_old_runner_without_command_still_reaches_research():
    st = _st()
    r = F.s_peers_got(st, {"peers": {"error": "허용되지 않은 명령"}}, {}, {})
    assert "review" in r and st["log"]


def test_other_preset_no_extra_step_and_no_table():
    st = _st(OTHER)
    assert "review" in F.s_research(st, {}, {}, {})
    assert F._process(st) == {} and F.line_table_problems(st, {}) == []
    assert F._lessons("plan", OTHER) == F._lessons("plan")


def test_table_required_once_then_passes_and_is_saved(monkeypatch):
    monkeypatch.setattr(F, "_fix_review", lambda st, why, *a, **k: {"why": why})
    monkeypatch.setattr(F, "_redo_done", lambda st: None)
    st = _st()
    r = F.ph_plan_look(st, {}, {f"plan_{V}": {"ok": True}}, {})
    assert "A1" in r["review"][0]["why"] and r["then"] == "plan_look"
    rows = [{"줄": i, "화면": "빵", "이유": "맞음"} for i in ("A1", "A2")]
    r = F.ph_plan_look(st, {}, {f"plan_{V}": {"ok": True, "대조표": rows}}, {})
    assert r["do"][0]["files"] == {f"{V}/대조표.json": rows} and r["then"] == "thumb"


def test_table_missing_twice_does_not_stop_the_episode(monkeypatch):
    monkeypatch.setattr(F, "_redo_done", lambda st: None)
    st = _st(tries={"line_table": 1})
    assert F.ph_plan_look(st, {}, {f"plan_{V}": {"ok": True}}, {}) == {"goto": "thumb"}
    assert any("대조표" in x for x in st["log"])


def test_plan_question_asks_table_only_for_this_preset():
    assert F.LINE_TABLE_ASK in _ask(V) and F.LINE_TABLE_ASK not in _ask(OTHER)


def _ask(v):
    st = _st(v)
    st["script"]["M"] = {"cuts": {}}
    return F._fix_review(st, "", None, f"plan_{v}")["ask"]


def test_hook_rule_in_brief_and_style_lessons():
    from tools.calcopy.hybrid import styles as STY
    assert "훅 장면" in STY.brief(V) and "훅 장면" not in STY.brief(OTHER)
    assert "누구나 아는 장면" in F._lessons("plan", V) and "누구나 아는 장면" not in F._lessons("plan", OTHER)


@pytest.mark.parametrize("v,want", [(V, "8~12개"), (OTHER, "2~4개")])
def test_more_material_question_carries_preset_count(v, want):
    st = _st(v, _more_q=["q"])
    r = F.ph_more_got(st, {"screen": {"rows": [{"id": "n"}], "sheets": []}}, {}, {})
    assert want in r["review"][0]["ask"]


def test_alt_question_carries_preset_count(monkeypatch):
    monkeypatch.setattr(F, "_alt_material_needed", lambda st: True)
    st = _st(_alt_screen={"rows": [{"id": "a"}], "sheets": []})
    assert "8~12개" in F.f_alt_ask(st, {}, {}, {})["review"][0]["ask"]


def test_all_chosen_material_gets_a_sheet():
    files = [{"name": f"m{i}.mp4"} for i in range(12)]
    assert len(F.ph_script(_st(material={"files": files}), {}, {}, {})["do"][0]["files"]) == 12
    assert len(F.ph_script(_st(OTHER, material={"files": files}), {}, {}, {})["do"][0]["files"]) == 5


def test_runner_skips_bench_channel_and_stops_on_block(tmp_path, monkeypatch):
    monkeypatch.setattr(RO, "_search", lambda *a: [{"id": "b1", "channel": "x"}, {"id": "v0", "channel": "방구석"}, {"id": "v1", "title": "t", "channel": "남"}, {"id": "v2", "channel": "남"}])
    calls = []

    def words(W, vid):
        calls.append(vid)
        return ([[0, "말"]], "자동자막") if vid == "v1" else ([], "blocked")

    monkeypatch.setattr(RO, "_origin_words", words)
    got = RO.c_peer_points(tmp_path, {"queries": ["q"], "n": 4, "skip_ids": ["b1"], "skip_channel": "방구석"})
    assert calls == ["v1", "v2"] and [x["id"] for x in got["videos"]] == ["v1"] and got["videos"][0]["text"] == "말"
