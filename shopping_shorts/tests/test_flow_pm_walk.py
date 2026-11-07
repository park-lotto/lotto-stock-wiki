# -*- coding: utf-8 -*-
"""PC제작형(썰템쇼 = PC 제작 라인) 지시서를 처음부터 끝까지 흘려 본다 — 실행기 결과·회원 Claude 답은 가짜, 대본은 PC 납품 본보기.
단계 = PC 작품 폴더 순서(소재 → 근거.md → 원본 → 대본.json → 짤 → 재료.json → preset_make 계획 → 완성 → 눈 확인).
쿠팡 단계 없음 · 계획 관문에 걸리면 재료만 다시 · 통과하면 렌더(c_pm make) 한 번."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import flow as F  # noqa: E402

EX = ROOT / "channel" / "humorshowshow" / "작품3_태양의맛썬"


def _go(st, m=None, rp=None):
    return F.step(st, m or {}, rp or {}, {})


def _start():
    st = F.start("https://www.youtube.com/shorts/bfKkNmVTGPs", "썰템쇼판", "pmwalk00001")
    st["fmt"] = "PC제작형"          # 전환 전 — 프리셋 장부는 아직 쇼핑형
    return st


def _to_rows(st):
    out = _go(st)
    assert out["do"][0]["cmd"] == "env"
    out = _go(st, {"env": {"missing": []}})
    assert out["do"][0]["cmd"] == "bench"
    out = _go(st, {"bench": {"id": "bfKkNmVTGPs", "title": "미국 선물 1위가 한국 반입금지", "lines": [{"text": "베이글 시즈닝"}]}})
    assert out["review"][0]["id"] == "pm_topic"
    out = _go(st, rp={"pm_topic": {"topic": "반입금지 시즈닝", "product": "에브리띵 베이글 시즈닝", "queries": ["everything bagel seasoning"], "research_words": ["양귀비씨"]}})
    assert out["review"][0]["id"] == "pm_research" and "근거.md" in out["review"][0]["ask"]
    md = "출처: https://a.com/1 https://b.com/2 https://c.com/3"
    out = _go(st, rp={"pm_research": {"근거_md": md, "facts": ["양귀비씨는 마약류"], "queries": ["everything bagel seasoning review"]}})
    assert out["do"][0]["cmd"] == "write_doc" and out["do"][0]["files"] == {"pm/근거.md": md}
    out = _go(st, {"save_research": {"ok": True}})
    assert out["do"][0]["cmd"] == "screen"
    out = _go(st, {"screen": {"rows": [{"id": "abc", "title": "bagel"}, {"id": "def", "title": "seasoning"}], "sheets": []}})
    assert out["review"][0]["id"] == "screen_pick" and "2~9" in out["review"][0]["ask"]          # PC 원본 개수
    out = _go(st, rp={"screen_pick": {"chosen": [{"id": "abc"}, {"id": "def"}]}})
    assert out["do"][0]["cmd"] == "download" and not any(d["cmd"] == "coupang" for d in out["do"])
    out = _go(st, {"dl": {"files": [{"name": "src_abc.mp4"}, {"name": "src_def.mp4"}]}})
    assert out["do"][0]["cmd"] == "mat_sheets"
    out = _go(st, {"mats": {"sheets": ["_sheet_abc.jpg"]}})
    assert out["review"][0]["id"] == "pm_script" and "frame_vars" in out["review"][0]["ask"]
    S = json.loads((EX / "대본.json").read_text(encoding="utf-8"))
    bare = json.loads(json.dumps(S))
    out = _go(st, rp={"pm_script": {"대본": bare}})          # 줄마다 장면 증거가 없으면 그 자리에서 다시
    assert out["review"][0]["id"] == "pm_script" and "장면 증거 없음" in out["review"][0]["ask"]
    for l in S["lines"]:
        l["scene"] = "src_abc.mp4@1.0 — 손에 든 병"
    out = _go(st, rp={"pm_script": {"대본": S}})
    assert out["review"][0]["id"] == "pm_memes" and "fm_travolta" in out["review"][0]["ask"] or out["review"][0]["id"] == "pm_memes"
    out = _go(st, rp={"pm_memes": {"stems": ["fm_travolta", "gfr_Xh3A"]}})
    assert out["do"][0] == {"id": "memes", "cmd": "memes", "stems": ["fm_travolta", "gfr_Xh3A"]}
    out = _go(st, {"memes": {"got": ["fm_travolta"], "sheet": "doc/pm/plan/짤후보.jpg"}})
    assert out["review"][0]["id"] == "pm_rows" and "src_crop" in out["review"][0]["ask"] and "흐림 없음" in out["review"][0]["ask"]
    return st, out


def test_walk_to_done():
    st, out = _to_rows(_start())
    R = {"shots": [{"src": "src_abc.mp4", "ss": 1.0}]}
    out = _go(st, rp={"pm_rows": {"재료": R}})
    cmds = [d["cmd"] for d in out["do"]]
    assert cmds == ["write_doc", "pm_sheet", "pm"] and out["do"][2]["mode"] == "plan"
    assert out["do"][0]["files"]["pm/재료.json"] == R and out["do"][0]["cand_dir"] is True
    # 계획 관문에 걸림 → 재료만 다시(대본·원본 단계로 안 돌아간다)
    out = _go(st, {"save_pm": {}, "crop": {"sheets": ["doc/pm/plan/자를칸/자를칸_1.jpg"]}, "pm": {"ok": False, "problems": ["④ 컷 3 남의 글자"]}})
    assert out["review"][0]["id"] == "pm_rows" and "④ 컷 3 남의 글자" in out["review"][0]["ask"]
    out = _go(st, rp={"pm_rows": {"재료": R}})
    out = _go(st, {"save_pm": {}, "crop": {"sheets": []}, "pm": {"ok": None, "note": "계획 검사 통과", "sheets": ["doc/pm/plan/계획_시트_자동.jpg", "doc/pm/plan/계획_접촉시트.jpg"]}})
    # 렌더 전 눈 확인(계획 접촉 시트) — 걸리면 재료만 다시, 렌더는 안 한다
    assert out["review"][0]["id"] == "pm_plan_eye" and "A-B-A" in out["review"][0]["ask"]
    out = _go(st, rp={"pm_plan_eye": {"ok": False, "cuts": [{"no": 1}], "problems": ["#11 ① 진열대→손 장면 바뀜"]}})
    assert out["review"][0]["id"] == "pm_rows" and "#11 ① 진열대→손 장면 바뀜" in out["review"][0]["ask"]
    out = _go(st, rp={"pm_rows": {"재료": R}})
    out = _go(st, {"save_pm": {}, "crop": {"sheets": []}, "pm": {"ok": None, "sheets": ["doc/pm/plan/계획_접촉시트.jpg"]}})
    assert out["review"][0]["id"] == "pm_plan_eye"
    out = _go(st, rp={"pm_plan_eye": {"ok": True, "cuts": [{"no": 0}, {"no": 1}, {"no": 2}], "problems": []}})
    assert out["do"] == [{"id": "pm", "cmd": "pm", "mode": "make", "preset": "channel/humorshowshow/preset/썰템쇼_화자썰"}]
    out = _go(st, {"pm": {"ok": True, "final": "C:/W/pm/make/final.mp4", "rows": [{"B": "B1", "항목": "길이", "값": 28, "ok": True}],
                          "sheets": ["pm/make/sheet_1s.jpg"]}})
    assert out["review"][0]["id"] == "pm_eye"
    out = _go(st, rp={"pm_eye": {"ok": True, "title_seen": "한국 반입금지", "scenes": [{"t": 1}, {"t": 5}, {"t": 9}], "problems": []}})
    assert out["status"] == "done" and out.get("video") == "C:/W/pm/make/final.mp4" or (out.get("done") or {}).get("video") == "C:/W/pm/make/final.mp4", out


def test_script_rejected_then_fixed():
    st = _start()
    st, out = _to_rows(st)
    assert st["tries"].get("pm_script", 0) == 1           # 장면 증거 없는 첫 답만 다시(PC 본보기 대본 규칙은 통과)


def test_scene_from_unknown_source_is_rejected():
    from tools.calcopy.hybrid import flow_pm as PMF
    st = {"material": {"files": [{"name": "src_abc.mp4"}]}}
    bad = PMF.scene_problems(st, {"lines": [{"scene": "src_zzz.mp4@3 — 병"}, {"scene": "src_abc.mp4@2.5 — 병"}]})
    assert len(bad) == 1 and "src_zzz.mp4" in bad[0]


def test_topic_start_without_video_goes_to_research():
    """#3207 — 쿠팡 제품 + 주제(영상 주소 없음)로 시작하면 받기 없이 소재 판독 → 근거 조사(옛 remake 길로 안 간다)."""
    assert F.takes_topic("썰템쇼판") and not F.takes_topic("잇썸홈판")
    st = F.start("", "썰템쇼판", "pmtopic0001", "https://www.coupang.com/vp/products/1", topic="미국 베이글 시즈닝 반입금지")
    assert st["given_topic"] and st["fmt"] == "PC제작형"
    out = _go(st)
    assert out["do"][0]["cmd"] == "env"
    out = _go(st, {"env": {"missing": []}})
    assert out["review"][0]["id"] == "pm_topic" and "반입금지" in out["review"][0]["ask"] and "coupang" in out["review"][0]["ask"]
    assert not any(d.get("cmd") == "bench" for d in out.get("do") or [])
    out = _go(st, rp={"pm_topic": {"topic": "t", "product": "에브리띵 베이글 시즈닝", "queries": ["q"], "research_words": ["w"]}})
    assert out["review"][0]["id"] == "pm_research"


def test_topic_start_refused_for_other_formats():
    import pytest
    with pytest.raises(F.FormatError):
        F.start("", "잇썸홈판", "pmtopic0002", topic="x")


def _to_make_task():
    """만들기가 계속 실패해 제작자 과제(task_*, 단계 render)가 나온 PC 편."""
    st, out = _to_rows(_start())
    R = {"shots": [{"src": "src_abc.mp4", "ss": 1.0}]}
    for _ in range(5):
        if out["review"][0]["id"].startswith("task"):
            return st, out
        out = _go(st, rp={"pm_rows": {"재료": R}})
        out = _go(st, {"save_pm": {}, "crop": {"sheets": []}, "pm": {"ok": None, "sheets": ["doc/pm/plan/계획_접촉시트.jpg"]}})
        out = _go(st, rp={"pm_plan_eye": {"ok": True, "cuts": [{"no": 0}, {"no": 1}, {"no": 2}], "problems": []}})
        out = _go(st, {"pm": {"ok": False, "error": "ImportError preset_save"}})
    raise AssertionError(out)


def test_make_task_answers_stay_on_pc_line():
    """11-04 회원 시험: 렌더 실패 → 제작자 과제에 waive → 보통 라인 render 처리기(_fix_review, st['script'] 전제) → KeyError 'script' → http_500 영영.
    PC제작형 과제 답은 PC 처리기로 가야 한다(waive·back render = 만들기 한 번 더, back plan = 재료만 다시, submit = 멈춤 안내)."""
    import copy
    st0, out = _to_make_task()
    tid = out["review"][0]["id"]
    assert st0["_task"]["stage"] == "render"
    for act, to, want in (("waive", "", "pm"), ("back", "render", "pm"), ("back", "plan", "pm_rows")):
        st = copy.deepcopy(st0)
        out = _go(st, rp={tid: {"action": act, "to": to, "note": "t"}})
        got = (out.get("do") or [{}])[0].get("cmd") if out.get("do") else (out.get("review") or [{}])[0].get("id")
        assert got == want, (act, to, out)
        assert "script" not in st
        if want == "pm":                       # 만들기 성공 → 완성본 눈 확인(PC 길 그대로)
            out = _go(st, {"pm": {"ok": True, "final": "C:/W/pm/make/final.mp4", "rows": [], "sheets": ["pm/make/sheet_1s.jpg"]}})
            assert out["review"][0]["id"] == "pm_eye"
    st = copy.deepcopy(st0)
    out = _go(st, rp={tid: {"action": "submit", "note": "t"}})          # PC 라인은 직접 만든 결과를 판정할 길이 없다 → 멈춤 안내(500 아님)
    assert out["status"] == "stop" and "script" not in st, out
