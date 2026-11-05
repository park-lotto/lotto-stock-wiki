# -*- coding: utf-8 -*-
"""11-05 숏템리폿 회원 편이 벤치(핫템리포트) 1차 판 겉모습(노랑/빨강 제목·외곽선 큰 자막)으로 나와 PC 납품(분홍 제목·검정 둥근 상자 자막·원음 하늘색)과 달랐다.
숏템리폿판_v2 = 1차 판 상속 + PC 납품 겉모습(make_frame/make_render_숏템리폿.py 값). 회원 프리셋은 v2 를 쓴다."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import render_bench as RB  # noqa: E402
from tools.calcopy.hybrid import styles as S  # noqa: E402


def test_v2_inherits_base_and_has_pc_look():
    st, base = S.load("숏템리폿판_v2"), S.load("숏템리폿판")
    assert st["renderer"] == base["renderer"] and st["length"] == base["length"]          # 뼈대는 1차 그대로
    assert st["frame"]["window"] == [0, 560, 1080, 1360]
    assert [t["color"] for t in st["frame"]["title"]] == ["#FFFFFF", "#FF82C3"]
    assert st["caption"]["pack"] == "hottemreport_v2"


def test_pack_box_fits_text_and_orig_is_sky_blue():
    pk = RB.caption_packs()["hottemreport_v2"]
    assert pk["box"]["fit"] is True and pk["box"]["radius"] == 22 and pk["box"]["color"] == "#0A0A0E"
    assert pk["speakers"]["orig"]["text"]["color"] == "#68C8E8"
    assert "hottemreport" in RB.caption_packs()                                                   # 1차 팩은 그대로


def test_member_preset_uses_v2():
    line = json.loads((ROOT / "channel/hottemreport/preset/검정띠/line.json").read_text(encoding="utf-8"))
    # 사장님 11-05 "다음 주에 한다" — 그때까지 회원 프리셋은 1차 판. 다음 주에 v2 로 바꾸면 이 줄도 v2 로
    assert line["version"] == "숏템리폿판"
