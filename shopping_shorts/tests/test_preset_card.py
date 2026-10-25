# -*- coding: utf-8 -*-
"""숏템프리셋 카드 생성기·합격선 판정기(tools/calcopy/preset_card.py, 관제 263 지시서 01).

픽스처 뿌리(--root 와 같은 set_root)에 주인 장부를 꾸며 판정이 장부를 **따라가는지** 잰다:
 규칙빈도 k 를 바꾸면 카드 rate 가 바뀐다 · 자막팩 키가 없으면 L1 '자막팩' 미달 · 미측정에 measure_task 없으면 build 거절 · 두 번 build 해도 built_at 외 같다.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy import preset_card as pc  # noqa: E402


def _w(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def _line(t0, t1, sp="나레", **kw):
    base = {"t0": t0, "t1": t1, "speaker": sp, "text": "가나다라", "layer": "채널", "enter": "instant", "emph": [], "sticker": [],
            "sfx": None, "scene": 1, "cut_at": [], "role": "본문", "y": 900, "fill_hex": "#FFFFFF", "fit": 8, "transition": "cut", "exit": "cut"}
    base.update(kw)
    return base


@pytest.fixture
def fx(tmp_path):
    R = tmp_path
    _w(R / "channel/프리셋.json", {"presets": {"fx": {
        "format": "해외원본", "subformat": "나레+원음", "bench_option": "픽스처",
        "engine": {"style_file": "tools/calcopy/hybrid/styles/픽스처판.json", "renderer": "bench", "hand_scripts": []},
        "member": {"line_json": None, "preset_name": None, "flow_format": "해외원본형"}}}})
    _w(R / "channel/fx/_kal/규칙빈도.json", {
        "n_docs": 1, "rules": [{"cond": "화자=나레", "effect": "sfx", "k": 2, "n": 10, "rate": 0.2, "base": 0.1, "grade": "약"},
                               {"cond": "자리=훅", "effect": "enter=pop", "k": 3, "n": 5, "rate": 0.6, "grade": "강"}],
        "plain": {"n": 7, "denom": 10}, "by_speaker": {"나레": {"n": 10, "cps": 8.5, "sec_med": 1.0}}, "min_n": 5})
    _w(R / "channel/fx/줄판독/a.json", {"id": "a", "dur": 10, "title_lines": [], "source_label": "", "beats": [], "narr_share": 1, "notes": [],
                                       "frame0": {"kind": "얼굴"},
                                       "lines": [_line(i, i + 0.9, sticker=[{"what": "빨간원"}] if i == 0 else []) for i in range(6)]})
    _w(R / "tools/calcopy/hybrid/styles/_common.json", {"script": {"audit": []}})
    _w(R / "tools/calcopy/hybrid/styles/픽스처판.json", {
        "name": "픽스처판", "renderer": "bench", "thumb_card_face": False, "voice": {"name": "유라", "why": "x"}, "bgm": {"id": "sweets", "db_below_voice": 12, "why": "x"},
        "loudness": {"lufs": -14, "why": "x"}, "length": {"min": 26, "max": 31, "why": "x"}, "cps_target": 8.6,
        "script": {"audit": [{"kind": "count"}]}, "caption": {"pack": "fxpack", "why": "x"},
        "placement": {"rules": {"enter": {"narr.first": "cut"}, "sfx": {"why": "x"}}, "counted": {"made_by": "p", "n_videos": 6}}})
    _w(R / "shopping_shorts/static/caption-motions.js", 'root.CAPTION_PACKS = /*PACKS*/{"fxpack": {"text": {}}}/*PACKS*/;')
    pc.set_root(R)
    yield R
    pc.set_root(None)


def test_rate_follows_rules_freq(fx):
    """사보타주 2a 꼴 — 규칙빈도 rules[0].k 를 바꾸면 카드 레코드 rate 가 따라 바뀐다(카드가 장부를 읽는다는 증거)."""
    def sfx_rate():
        c = pc.build_card("fx")
        return [r for r in c["rules"] if r["element"] == "sfx" and r["cond"] == "화자=나레"][0]
    assert sfx_rate()["k"] == 2
    p = fx / "channel/fx/_kal/규칙빈도.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["rules"][0]["k"] = 9               # k 만 바꾼다 — rate 칸은 그대로 0.2
    p.write_text(json.dumps(d), encoding="utf-8")
    r = sfx_rate()
    assert (r["k"], r["rate"]) == (9, 0.9)


def test_bad_caption_pack_fails_L1(fx):
    """사보타주 2b 꼴 — caption.pack 을 없는 키로 바꾸면 L1 '자막팩' 미달."""
    assert "자막팩" not in pc.build_card("fx")["done"]["missing"]
    p = fx / "tools/calcopy/hybrid/styles/픽스처판.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["caption"]["pack"] = "없는팩"
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    c = pc.build_card("fx")
    assert "자막팩" in c["done"]["missing"]
    assert c["facts"]["caption_pack_ok"] is False


def test_unmeasured_without_task_rejected(fx, monkeypatch):
    """미측정 레코드에 measure_task 가 없으면 build exit 1, 카드 파일을 쓰지 않는다."""
    real = pc.rules_of

    def broken(slug, O=None):
        recs = real(slug, O)
        for r in recs:
            if r["confidence"] == "미측정":
                r["measure_task"] = None
        return recs
    monkeypatch.setattr(pc, "rules_of", broken)
    assert any(r["confidence"] == "미측정" for r in broken("fx"))      # 픽스처에 미측정 칸이 실제로 있다(없으면 이 시험은 아무것도 안 잰다)
    assert pc.build(["fx"], write_html=False) == 1
    assert not pc.card_path("fx").exists()
    monkeypatch.setattr(pc, "rules_of", real)
    assert pc.build(["fx"], write_html=False) == 0
    assert pc.card_path("fx").exists()


def test_every_unmeasured_has_task(fx):
    c = pc.build_card("fx")
    un = [r for r in c["rules"] if r["confidence"] == "미측정"]
    assert un and all(r["measure_task"] == "06-fx" for r in un)
    assert {r["element"] for r in c["rules"]} == set(pc.ELEMENTS)        # 15종 전부 레코드가 있다(측정 또는 미측정)


def test_build_deterministic(fx):
    """같은 입력으로 두 번 build → built_at 외 diff 0, 표식(made_by·inputs sha) 있다."""
    pc.build(["fx"], write_html=False)
    a = json.loads(pc.card_path("fx").read_text(encoding="utf-8"))
    pc.build(["fx"], write_html=False)
    b = json.loads(pc.card_path("fx").read_text(encoding="utf-8"))
    assert a["made_by"] == pc.MADE_BY and a["inputs"] and all(len(v) == 12 for v in a["inputs"].values())
    a.pop("built_at"); b.pop("built_at")
    assert a == b


def test_level_reads_owner_files(fx):
    """L0 미달 사유는 실제 빠진 파일이다 — 줄판독 1편·스타일분석/팔레트/sfx_events 없음."""
    c = pc.build_card("fx")
    assert c["done"]["level"] == "L0 미달"
    for m in ("줄판독≥6", "스타일분석", "팔레트", "sfx_events"):
        assert m in c["done"]["missing"]
    assert "규칙빈도" not in c["done"]["missing"] and "판파일" not in c["done"]["missing"]


def test_pointer_from_line_reads(fx):
    c = pc.build_card("fx")
    p = [r for r in c["rules"] if r["element"] == "pointer"][0]
    assert (p["k"], p["n"]) == (1, 6)


def test_real_repo_all_presets_build():
    """실제 저장소 장부로 23개 카드가 거절 없이 만들어진다(파일은 안 쓴다)."""
    pc.set_root(None)
    slugs = list(pc.presets())
    assert len(slugs) >= 23
    for s in slugs:
        c = pc.build_card(s)
        assert not pc.validate(c), s


def test_edition_folder_by_style(fx):
    """판 편 폴더(우리 채널 폴더 아래, 작업정보.json style=판) 의 품질관문·결과물 장부 doc 을 카드가 읽는다(10-25 박정수 키치잇판 L1 구멍).
    작업정보 style 이 다른 판이면 안 읽는다 — 위치 규칙 주인 work_log.edition_dirs."""
    R = fx
    ed = R / "channel/ours/하이브리드_X/픽스처판"
    _w(ed / "작업정보.json", {"bench_channel": "fx", "style": "픽스처판"})
    _w(ed / "품질관문.json", {"ok": True})
    _w(R / "channel/결과물.json", {"items": [{"channel": "ours", "title": "x", "path": "x", "seconds": 1, "date": "d", "from": "f",
                                            "doc": "channel/ours/하이브리드_X/픽스처판/", "judge": "[사장님승인] 사장님 OK"}]})
    F = pc.build_card("fx")["facts"]
    assert F["quality_gate_ok"] and F["owner_pass"]
    _w(ed / "작업정보.json", {"bench_channel": "fx", "style": "다른판"})
    F = pc.build_card("fx")["facts"]
    assert not F["quality_gate_ok"] and not F["owner_pass"]
