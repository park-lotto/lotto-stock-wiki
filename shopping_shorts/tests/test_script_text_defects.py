# -*- coding: utf-8 -*-
"""관문 G-1 — 대본 단계(TTS 전) 글 결함: 판단 주인 tools/calcopy/hybrid/script_audit.text_defects.

표본 = tools/calcopy/gate_fixtures/g1_script.json (10-25 전 편 음성 감사에서 소리 결함을 낸 대본 줄 ↔ 정상 줄, git 기록 글 그대로).
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.engine import narr_align as NA  # noqa: E402
from tools.calcopy.engine import narr_verify as NV  # noqa: E402
from tools.calcopy.hybrid import rules as RU  # noqa: E402
from tools.calcopy.hybrid import script_audit as SA  # noqa: E402

FIX = json.loads((ROOT / "tools/calcopy/gate_fixtures/g1_script.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", FIX, ids=[c["name"] for c in FIX])
def test_fixture(case):
    got = sorted([x["rule"], x["line"]] for x in SA.text_defects({"lines": case["lines"]}, joined=case["joined"]))
    assert got == sorted(case["expect"]), case["why"]


def test_fixture_has_both_sides():
    assert sum(bool(c["expect"]) for c in FIX) >= 8 and sum(not c["expect"] for c in FIX) >= 6


def test_end_mark_owner_same_as_split():
    assert NA.ends_with_mark("붓고,") and NA.ends_with_mark("됐어요. ") and NA.ends_with_mark("있다는데요?")
    assert not NA.ends_with_mark("따르자") and not NA.ends_with_mark("그렇다…") and not NA.ends_with_mark("")


def test_end_mark_last_tts_and_shark_exempt():
    L = [{"id": "N1", "kind": "tts", "tts": "앞 줄은 부호 없이"}, {"id": "O1", "kind": "orig", "text": "원음"},
         {"id": "N2", "kind": "tts", "tts": "끝 줄도 부호 없이"}]
    assert [(x["rule"], x["line"]) for x in SA.text_defects({"lines": L})] == [("end_mark", "N1")]
    assert SA.text_defects({"lines": L}, joined=False) == []          # 샥탬 final.lines(줄마다 합성)


def test_latin_reads_text_when_no_tts_and_skips_orig():
    L = [{"id": "a", "text": "AI 신발이요."}, {"id": "b", "kind": "tts", "text": "LED 눈", "tts": "엘이디 눈."},
         {"id": "c", "kind": "orig", "text": "OK"}]
    assert SA.latin_in({"lines": L}) == [("a", ["AI"])]


def test_narr_verify_latin_lines_is_a_door():
    S = {"lines": [{"id": "B4", "kind": "tts", "tts": "눈에 LED까지 들어와서,"}, {"id": "B5", "kind": "tts", "tts": "난리예요."}]}
    assert NV.latin_lines(S) == SA.latin_in(S) == [("B4", ["LED"])]


def test_caps_trim_allowed_but_unsaid_caption_word_caught():
    ok = [("한국인들이/졸라서 살린 과자?", "한국인들이 끝까지 졸라서 살려낸 과자?"),       # 자막이 줄인 것(98 #19)
          ("그대로 판매가/뚝 끊겨버린 것", "그대로 판매가 뚝 끊겨 버린 거."),
          ("국물 맛이 걍 미쳤음 ㄷㄷ", "국물 맛이 그냥 미쳤음."),
          ("유명한 서인영이 집에서", "유명한 방송인 서인영 씨가 집에서"),                  # 이름 발음 고침(name_dict)
          ("한 시간에 유리병 1만 2천 개씩", "한 시간에 유리병 만 이천 개씩."),             # 숫자 읽기
          ("배터리도 4000mAh라 밖에서", "배터리도 사천 밀리암페어시라 밖에서")]
    for shown, say in ok:
        assert SA.shown_not_said(shown, say) == [], (shown, say)
    assert SA.shown_not_said("따라 사 봤는데요", "하나 사서 따라 해 봤는데요,") == ["사"]
    assert SA.shown_not_said("메디큐브 PDRN 핑크 콜라겐 캡슐", "메디큐브 콜라겐 캡슐") == ["핑크"]


def test_caps_text_reading_in_text_field_not_flagged():
    l = {"id": "B3", "kind": "tts", "text": "굽도 이 점 오 센티 납작한 플랫이라,", "tts": "굽도 이 점 오 센티 납작한 플랫이라,",
         "caps": ["굽도 2.5cm", "납작한 플랫이라"]}
    assert SA.text_defects({"lines": [l]}) == []


def test_rules_caps_vs_tts_is_a_door():
    S = {"lines": [{"id": "n3", "kind": "tts", "text": "따라 사 봤는데요", "tts": "하나 사서 따라 해 봤는데요,", "caps": ["따라 사 봤는데요"]}]}
    out = RU.caps_vs_tts(S)
    assert len(out) == 1 and out[0].startswith("n3:")


def test_audit_carries_g1_rules(tmp_path):
    case = next(c for c in FIX if c["name"] == "ep09_N3_밀림")
    p = tmp_path / "대본.json"
    p.write_text(json.dumps({"lines": case["lines"]}, ensure_ascii=False), encoding="utf-8")
    r = SA.audit(p, "잇썸홈판")
    bad = [x for x in r["rules"] if x["kind"].startswith("text:")]
    assert [x["kind"] for x in bad] == ["text:end_mark"] and bad[0]["why"].startswith("N3 ") and r["ok"] is False
