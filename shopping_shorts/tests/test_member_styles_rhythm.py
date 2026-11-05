"""10-30 다른 PC 회원 시험(썰템홈샷 sid 1cc9b72791d6): 판 rhythm 칸이 없어 완성본 검사가 늘 × — 재료·대본으로 못 고쳐 10/11 에서 멈춤.
회원 길(channel/프리셋.json member.line_json)에 연결된 판은 리듬 4칸이 다 있어야 한다(완성본 검사 quality_gate '판 리듬' 필수)."""
import json
from pathlib import Path

from tools.calcopy.hybrid import styles as ST

ROOT = Path(__file__).resolve().parents[2]


def test_every_member_style_has_rhythm():
    P = json.loads((ROOT / "channel" / "프리셋.json").read_text(encoding="utf-8"))["presets"]
    bad = {}
    for slug, x in P.items():
        lj = ((x or {}).get("member") or {}).get("line_json")
        if not lj:
            continue
        v = json.loads((ROOT / lj).read_text(encoding="utf-8"))["version"]
        RH = ST.rhythm(ST.load(v)) or {}
        miss = [k for k in ("cut_median", "hook_cuts_3s", "plain_share", "photo_share_max") if not RH.get(k)]
        if miss:
            bad[v] = miss
    assert not bad, f"회원 판 리듬 칸 없음: {bad}"
