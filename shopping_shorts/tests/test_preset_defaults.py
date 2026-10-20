# -*- coding: utf-8 -*-
"""회원 기본값 = 그 프리셋 원본 영상(사장님 10-20, 모든 프리셋) — preview_request.preset_defaults.
10-20 실측: 프리셋 5개가 팩 하나(잘난고딕·외곽선 0·금지된 필재)로 덮여 4개가 원본과 달랐다."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy import preview_request as P  # noqa: E402

CUSTOMER = ["banggu/preset/게시글형", "foreignshowshow/preset/샤크탱크_검정띠2줄", "hottemreport/preset/검정띠",
            "mantem/preset/얜샷템", "yummyknow/preset/게시글형"]
BANNED = {"tc_68257f68bc6e3c161ab5078d"}   # 필재(사장님 10-20 금지, kal.BANNED_VOICES)


def _frame_text(p):
    f = json.loads((ROOT / "channel" / p / "frame.json").read_text(encoding="utf-8"))
    L = [x for fr in (f.get("frames") or [f]) for x in fr.get("layers", []) if x.get("kind") == "text"]
    return next(x for x in L if x.get("role") == "title"), next(x for x in L if x.get("role") == "caption")


def test_every_customer_preset_follows_its_own_frame_and_voice():
    for p in CUSTOMER:
        d = P.preset_defaults(f"channel/{p}")
        title, cap = _frame_text(p)
        assert d["text"]["title_font"] == title["font"] and d["text"]["caption_font"] == cap["font"], p
        assert d["text"]["caption"]["outline_px"] == ((cap.get("outline") or {}).get("px") or 0), p
        assert d["tts"]["voice_id"] not in BANNED, p
        assert d["tts"]["voice_id"] and d["bgm"]["candidates"] and d["text"]["caption"].get("mode"), p
        assert P.check(d) == [], (p, P.check(d))


def test_yanshottem_is_its_measured_values():
    d = P.preset_defaults("channel/mantem/preset/얜샷템")
    assert (d["text"]["title_font"], d["text"]["caption"]["outline_px"], d["tts"]["name"]) == ("Cafe24Ohsquare", 5, "문정")
