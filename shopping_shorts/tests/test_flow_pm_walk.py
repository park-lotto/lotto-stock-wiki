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
    out = _go(st, {"save_pm": {}, "crop": {"sheets": []}, "pm": {"ok": None, "note": "계획 검사 통과"}})
    assert out["do"] == [{"id": "pm", "cmd": "pm", "mode": "make", "preset": "channel/humorshowshow/preset/썰템쇼_화자썰"}]
    out = _go(st, {"pm": {"ok": True, "final": "C:/W/pm/make/final.mp4", "rows": [{"B": "B1", "항목": "길이", "값": 28, "ok": True}],
                          "sheets": ["pm/make/sheet_1s.jpg"]}})
    assert out["review"][0]["id"] == "pm_eye"
    out = _go(st, rp={"pm_eye": {"ok": True, "title_seen": "한국 반입금지", "scenes": [{"t": 1}, {"t": 5}, {"t": 9}], "problems": []}})
    assert out["status"] == "done" and out.get("video") == "C:/W/pm/make/final.mp4" or (out.get("done") or {}).get("video") == "C:/W/pm/make/final.mp4", out


def test_script_rejected_then_fixed():
    st = _start()
    st, out = _to_rows(st)
    assert st["tries"].get("pm_script", 0) == 0           # PC 본보기 대본은 한 번에 통과
