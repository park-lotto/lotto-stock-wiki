# -*- coding: utf-8 -*-
"""#1631 김유선(채널명 크기) · #1949·#1950 이성택(자막 크게·채널명 크기/색) — 회원이 styles.py 를 직접 고쳐 우회했다.
한 칸 설계: 팩 text.caption_scale · brand.name_scale · brand.name_color — 저장 관문 preview_request.check, 판에 얹기 styles.member_frame 한 곳
(채널명 세 자리 = styles.name_look). 안 정하면 지금과 같은 그림."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy import preview_request as PR  # noqa: E402
from tools.calcopy.hybrid import render_bench as RB  # noqa: E402
from tools.calcopy.hybrid import styles as ST  # noqa: E402


def _cat():
    return {"fonts": [], "templates": [], "bgm": [], "caption_mode": [], "caption_enter": [], "emphasis": [], "voices": []}


def test_check_accepts_and_bounds():
    ok = {"brand": {"name_scale": 2.0, "name_color": "#ff0000"}, "text": {"caption_scale": 1.4}}
    assert not [e for e in PR.check(ok, _cat()) if "크기" in e or "색" in e or "모르는 칸" in e]
    bad = {"brand": {"name_scale": 9, "name_color": "red"}, "text": {"caption_scale": 0.1}}
    err = " ".join(PR.check(bad, _cat()))
    assert "채널명 크기" in err and "채널명 색" in err and "자막 크기" in err


def test_name_look_three_places():
    logo = {"px": 40, "rgba": [1, 2, 3, 200]}
    wm = {"px": 40, "alpha": 170}
    bar = {"kind": "text", "px": 30, "max_w": 300}
    ST.name_look([logo, wm, bar, None], 2.0, "#102030")
    assert logo == {"px": 80, "rgba": [16, 32, 48, 200]}
    assert wm == {"px": 80, "alpha": 170, "color": "#102030"}
    assert bar["px"] == 60 and bar["max_w"] == 600 and bar["color"] == "#102030"
    keep = {"px": 40}
    ST.name_look([keep], None, None)
    assert keep == {"px": 40}


def test_member_frame_applies(tmp_path, monkeypatch):
    f = tmp_path / "pack.json"
    f.write_text(json.dumps({"member": {"brand": {"channel_name": "우리채널", "name_scale": 2.0, "name_color": "#00ff00"},
                                        "text": {"caption_scale": 1.5}}}), encoding="utf-8")
    monkeypatch.setenv("SHORTEM_MEMBER_PACK", str(f))
    st = ST.load("썰템쇼판")
    assert st["member_caption"]["scale"] == 1.5
    assert RB.snapshot(st)["captionOverride"]["scale"] == 1.5          # 자막팩 렌더러까지 간다
    F = st["frame"]
    bar = lambda F: [i for i in ((F.get("post") or {}).get("head_bar") or {}).get("icons") or [] if i.get("kind") == "text"]
    marks = [x for x in (F.get("logo"), F.get("watermark")) if x] + bar(F)     # 썰템쇼 = 머리띠 글자 칸이 채널명 자리(11-03 — 상단 워터마크를 더 넣지 않는다)
    assert marks and all(x.get("color") == "#00ff00" or (x.get("rgba") or [None])[:3] == [0, 255, 0] for x in marks)
    monkeypatch.setenv("SHORTEM_MEMBER_PACK", str(tmp_path / "none.json"))
    (tmp_path / "none.json").write_text(json.dumps({"member": {"brand": {"channel_name": "우리채널"}}}), encoding="utf-8")
    st0 = ST.load("썰템쇼판")
    m0 = [x for x in (st0["frame"].get("logo"), st0["frame"].get("watermark")) if x] + bar(st0["frame"])
    assert [round(x.get("px") * 2) for x in m0] == [round(x.get("px")) for x in marks]   # 안 정하면 그대로, 정하면 정확히 2배
