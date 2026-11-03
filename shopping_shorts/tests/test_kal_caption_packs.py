"""칼카피 새 판 자막팩(관제 263 · 팩요청.md <판>#1) — 고객이 쓰던 자막팩은 한 글자도 안 바뀐다 + 새 팩이 판·글꼴과 이어져 있다.

caption-motions.js 는 고객 라이브 파일이다. 새 팩은 **키를 더하기만** 한다 — 기존 12 키 값이 바뀌면 고객 화면 자막이 바뀐다.
렌더 결과 대조(벤치 프레임 ↔ 우리 렌더)는 tools/caption_pack/check_kal_new_packs.py (결과물 검사).
"""
import hashlib
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "shopping_shorts/static/caption-motions.js"
SHOWCASE = ROOT / "out/scene-style-ui-showcase.html"
STYLES = ROOT / "tools/calcopy/hybrid/styles"

# 2026-10-25 이 트랙 HEAD(4a2082a0b 계열)의 기존 팩 값 sha256(정렬 JSON) 앞 16자 — 이 값이 바뀌면 고객 자막이 바뀐 것이다.
LEGACY = {
    "tension": "afe68b85011327e3",
    "clean": "c337c474d9cb3744",
    "premium": "074629957380ab3b",
    "story": "744ddbec8dc763a2",
    "deal": "60f23cc0bbecef36",
    "soft": "9ef9fe5d01aaa9b9",
    "kitchit": "8034f20a40ddc6e2",
    "kkultemnote": "d55b10cbe032c37f",
    "starpick": "11fe592f6bde737f",
    "recipe": "6bb615d9b9856296",
    "goodletter": "c9979c0afaf633e9",
    "ititemlog": "c58368e280e56eca",
}
# 판 → 새 자막팩(팩요청.md <판>#1 이 요청한 그 채널 한 벌)
BOARD = {"썰템홈샷판": "banggu", "맛템썰템판": "yummyknow", "썰템쇼판": "humorshowshow", "숏템리폿판": "hottemreport", "신박판": "sinbak",
         "트롯파파판": "uljimatrot", "만템판": "mantem", "아이템홈판": "itemhome", "안나픽판": "annapick", "도파민썰템A판": "sseolpulda_a",
         "도파민썰템B판": "sseolpulda_b", "뜨거운사람들판": "hotpeople"}
NEW = set(BOARD.values()) | {"ititemlog_v2"}


def _packs(text=None):
    return json.loads((text if text is not None else CONTRACT.read_text(encoding="utf-8")).split("/*PACKS*/")[1])


def _sha(v):
    return hashlib.sha256(json.dumps(v, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def legacy_changes(text=None):
    """기존 키 중 값·순서가 달라진 것 목록(빈 목록 = 고객 자막팩 diff 0)."""
    P = _packs(text)
    bad = [k for k, h in LEGACY.items() if k not in P or _sha(P[k]) != h]
    if list(P)[:len(LEGACY)] != list(LEGACY):
        bad.append("순서")
    return bad


def test_기존_자막팩_diff_0():
    assert legacy_changes() == []


def test_사보타주_기존키_한글자_바꾸면_잡는다():
    text = CONTRACT.read_text(encoding="utf-8")
    a = text.index("/*PACKS*/") + 9
    i = text.index('"label": "', text.index('"clean"', a)) + len('"label": "')
    broken = text[:i] + "X" + text[i:]                       # clean 팩 label 앞에 한 글자
    assert legacy_changes(broken) == ["clean"]
    j = text.index('"size": 78', text.index('"kitchit"', a))
    assert legacy_changes(text[:j] + '"size": 79' + text[j + len('"size": 78'):]) == ["kitchit"]


def test_새_팩은_더하기만():
    P = _packs()
    assert NEW <= set(P)      # 다른 세션이 더한 키는 막지 않는다(기존 키만 잠근다 — test_기존_자막팩_diff_0)


def _faces():
    return set(re.findall(r'font-family:"([^"]+)";src:url', SHOWCASE.read_text(encoding="utf-8")))


@pytest.mark.parametrize("key", sorted(NEW))
def test_새_팩_글꼴은_렌더가_받는_글꼴(key):
    # 렌더(tools/render_scene_style.js)는 out/scene-style-ui-showcase.html 의 @font-face 이름만 받는다 — 없는 이름이면 조용히 대체 글꼴
    P = _packs()[key]
    fams = {P["font"], (P.get("emph") or {}).get("font")} | {s.get("font") for s in (P.get("speakers") or {}).values()}
    assert {f for f in fams if f} <= _faces(), key


@pytest.mark.parametrize("board,key", sorted(BOARD.items()))
def test_판이_새_팩을_쓴다(board, key):
    import sys
    sys.path.insert(0, str(ROOT))
    from tools.calcopy.hybrid import pack_map, styles
    raw = json.loads((STYLES / f"{board}.json").read_text(encoding="utf-8"))
    assert raw["packs"]["caption"]["pack"] == key and raw["caption"]["pack"] == key
    st = styles.load(board)
    assert pack_map.check(st["packs"]) == [] and pack_map.snapshot_fields(st)["captionPack"] == key


def test_잇템로그_업그레이드_팩_강조색_후보():
    import sys
    sys.path.insert(0, str(ROOT))
    from tools.calcopy.hybrid import placement
    P = _packs()
    up, base = P["ititemlog_v2"], P["ititemlog"]
    assert {k: v for k, v in up.items() if k not in ("label", "desc", "mark", "bench")} == \
           {k: v for k, v in base.items() if k not in ("label", "desc", "mark", "bench")}   # 모양은 1차 팩 그대로, 색 후보만 더함
    cands = up["mark"]["colors"]
    assert {"#FFFFFF", "#F7EB0E"} <= set(cands) and cands[0] == base["mark"]["colors"][0]
    for line in ("#F7EB0E", "#FDFCFD", "#E30004"):            # 나레 노랑 · 원음 흰 · 훅 빨강 — 어느 줄이든 강조색이 남는다(㉒ 문턱 30 업그레이드)
        c, _ = placement.pick_emph_color(line, cands, 30.0, "#000000")
        assert c, line
