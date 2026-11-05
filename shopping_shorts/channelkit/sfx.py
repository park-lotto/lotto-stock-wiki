# -*- coding: utf-8 -*-
"""효과음 배정 — 컷마다 1발, 순서는 서버 고정(5편 접미사까지 동일), RED 컷만 게인 1.25.

"12개 반복"이 아니다(아스트라 지적, 검증됨). 관측된 32개를 그대로 쓰고 그 뒤는 4칸×계열주기 공식으로 늘린다.
"""
import re

from . import spec


def _extend(n):
    seq = list(spec.SFX_SEQ32)
    if n <= len(seq):
        return seq[:n]
    for i in range(len(seq), n):
        fam = spec.SFX_FAMILY[i % 4]
        base = fam[(i // 4) % len(fam)]
        # 접미사(변주 번호)는 관측된 마지막 같은 계열 것을 따른다
        last = next((s for s in reversed(seq) if re.sub(r"_\d+$", "", s) == base), base + "_0")
        seq.append(last)
    return seq


def plan(groups, sfx_dir="sfx_norm"):
    """groups: timing/대본 컷 리스트(color 필수) → [{cut, file, gain}] (cut은 0부터)"""
    names = _extend(len(groups))
    out = []
    for i, (g, name) in enumerate(zip(groups, names)):
        gain = spec.SFX_GAIN_RED if g["color"] == "RED" else spec.SFX_GAIN_DEFAULT
        out.append({"cut": i, "file": f"{sfx_dir}/{name}.mp3", "gain": gain})
    return out
