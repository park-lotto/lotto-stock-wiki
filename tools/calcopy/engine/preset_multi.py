# -*- coding: utf-8 -*-
"""틀 여러 장(훅 카드 + 본문) 프리셋 만들기 — 편마다 훅·본문 설명서 두 장을 frames 하나로 묶어 preset_save.save 에 넣는다.

    PYTHONUTF8=1 py tools/calcopy/engine/preset_multi.py --slug yummyknow --style 게시글형 --roles-of yummyknow --source-kind 제품비하인드 \
        --src rGFXQlS9Cp4=channel/yummyknow/칼카피_rGFX:frame_rGFX_hook.json:frame_rGFX_body.json:C:/숏템_칼카피/yummyknow/칼카피_rGFX/뜯기2/뜯기.json \
        --src shinramyun_gumi=channel/yummyknow/새소재_shinramyun_gumi:frame_hook.json:frame_body.json:-

훅 길이 = 그 편 폴더 timeline.json 의 hook_end(편마다 변수 — preset_save.always_per_video). 뜯기가 없는 편(새소재 제작)은 '-'.
프리셋 폴더는 지우고 새로 만든다(manifest 의 META_KEYS 칸은 이어 붙인다).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shopping_shorts.calcopy_frame import schema  # noqa: E402
from tools.calcopy.engine import preset_save as P  # noqa: E402


def multi(folder: str, hook: str, body: str, src: str) -> dict:
    d = ROOT / folder
    T = json.loads((d / "timeline.json").read_text(encoding="utf-8"))
    H = json.loads((d / hook).read_text(encoding="utf-8"))
    B = json.loads((d / body).read_text(encoding="utf-8"))
    he = round(float(T["hook_end"]), 3)
    F = {"canvas": H["canvas"], "frames": [{"id": "hook", "span": [0, he], "layers": H["layers"]},
                                         {"id": "body", "span": [he, None], "layers": B["layers"]}],
         "template_off": None, "made_by": schema.MADE_BY, "source": src,
         "made_from": {"tool": f"preset_multi: {folder}/{hook} + {body} (훅 길이 = timeline.hook_end {he}초)",
                       "notes": [x for x in (H.get("_note"), B.get("_note")) if x]}}
    schema.validate(F)
    return F


def build(slug: str, style: str, srcs: list[tuple], roles=None, source_kind=None) -> dict:
    d = ROOT / "channel" / slug / "preset" / style
    meta = {}
    if (d / "manifest.json").exists():
        old = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        meta = {k: old[k] for k in P.META_KEYS if k in old}
    shutil.rmtree(d, ignore_errors=True)
    M = None
    for sid, folder, hook, body, tg in srcs:
        J = json.loads(Path(tg if Path(tg).is_absolute() else ROOT / tg).read_text(encoding="utf-8")) if tg != "-" else \
            {"engine": "손질본(새소재 제작 — 뜯기 없음)", "measured_at": None, "unknown": ["원본 뜯기 없음"]}
        M = P.save(J, multi(folder, hook, body, sid), d, sid, tg, caption_style=style, caption_note="손질본(틀 여러 장)")
    if meta:
        M.update(meta)
        (d / "manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    if roles or source_kind:
        M = P.set_meta(d, roles=roles, source_kind=source_kind)
    return M


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True); ap.add_argument("--style", required=True)
    ap.add_argument("--src", action="append", required=True, help="id=폴더:훅.json:본문.json:뜯기.json(없으면 -)")
    ap.add_argument("--roles-of", help="script_engine.ROLES 의 채널 이름(그 역할 칸을 manifest.roles 로)")
    ap.add_argument("--source-kind")
    a = ap.parse_args(argv)
    srcs = []
    for s in a.src:
        sid, rest = s.split("=", 1)
        folder, hook, body, tg = rest.split(":", 3)
        srcs.append((sid, folder, hook, body, tg))
    roles = None
    if a.roles_of:
        from tools.calcopy.engine.script_engine import ROLES
        roles = ROLES[a.roles_of]
    M = build(a.slug, a.style, srcs, roles, a.source_kind)
    print("출처", [s["id"] for s in M["sources"]], "변수", M["variables"])


if __name__ == "__main__":
    main()
