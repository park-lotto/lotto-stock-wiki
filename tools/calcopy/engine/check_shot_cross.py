# -*- coding: utf-8 -*-
"""완성본 컷이 원본 영상의 샷 경계를 넘어 옆 장면이 섞였나 (관제 097, 2026-10-18).

    PYTHONUTF8=1 py tools/calcopy/engine/check_shot_cross.py <make 폴더> [...]

왜: 썰템쇼 10편을 박창수(느린 말)로 다시 만들자 컷이 길어져, 원본 샷에 딱 맞춰 고른 컷이 다음 샷 0.1~0.4초를 끌고 들어왔다
(작품6 52.06~53.36 ← 샷 52.05~53.19). B13(중복)·B16(되감김·점프줌)은 이걸 못 잡는다 — 워커 넷이 눈으로만 찾았다.
재는 법: make/timeline.json groups(src·ss·dur·src_span) → 그 원본 구간을 장면 경계로 나눈 조각 중 0.4초 미만이 있으면 걸림.
경계·조각 판정 주인 = hybrid/render_bench.shot_starts·inner_bounds·short_pieces(계획 snap_ss·preset_make.fit_shot·관문 ③과 같은 자 — 10-26 98 #111).
옛 판의 자(ffmpeg scene>0.25 + 색분포)는 관문 ③과 달라 진짜 편집점(태양의맛썬 40.50·42.83)을 놓쳤다. 제안 ss = render_bench.snap_ss.
짤(meme:)은 뺀다(짤 자체 편집). 걸린 컷이 있으면 rc 1.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid.render_bench import MIN_PIECE_SEC, inner_bounds, short_pieces, shot_starts, snap_ss, src_start  # noqa: E402

FLASH = MIN_PIECE_SEC        # 이보다 짧게 끼는 옆 샷 = 번쩍(눈에 띈다)


def check(make: Path) -> list[dict]:
    d = json.loads((make / "timeline.json").read_text(encoding="utf-8"))
    out = []
    for g in d["groups"]:
        if str(g["src"]).startswith("meme:"):
            continue
        a, b = float(g["ss"]), float(g["ss"]) + float(g.get("src_span") or g["dur"])   # 늘린 컷은 원본에서 쓴 길이만
        src = make.parent / g["src"]
        if not src.exists():         # 옛 판은 ffmpeg 오류를 '경계 없음'으로 삼켜 통과시켰다 — 못 잰 컷은 못 잰 것으로 적는다
            out.append({"src": g["src"], "ss": round(a, 2), "end": round(b, 2), "t0": g["t0"], "pieces": g["pieces"], "missing": True,
                        "cross": [], "flash": False, "short": [], "head": False, "tail": False, "fix_ss": None})
            continue
        st = shot_starts(src)
        e = src_start(src, a)                      # 실제 첫 화면 초(24fps 원본은 ss 보다 늦다)
        inside = inner_bounds(st, e, e + (b - a))
        short = short_pieces(st, e, e + (b - a))
        head = bool(inside) and inside[0] - e < FLASH
        tail = bool(inside) and e + (b - a) - inside[-1] < FLASH
        fix = None
        if short:
            s2 = snap_ss(src, a, b - a)
            fix = s2 if s2 != a else None
        out.append({"src": g["src"], "ss": round(a, 2), "end": round(b, 2), "t0": g["t0"], "pieces": g["pieces"], "cross": inside,
                    "flash": bool(short), "short": short, "head": head, "tail": tail, "fix_ss": fix})
    return out


if __name__ == "__main__":
    rc = 0
    for m in sys.argv[1:]:
        rows = check(Path(m))
        bad = [r for r in rows if r["flash"]]
        miss = [r for r in rows if r.get("missing")]
        rc |= bool(bad) or bool(miss)
        if miss:
            print(f"== {m} → 원본 없음 {len(miss)}컷 못 잼(통과 아님): {sorted({r['src'] for r in miss})[:5]}")
        print(f"== {m} → {'○' if not bad else f'× 옆 샷 번쩍 컷 {len(bad)}'} (긴 조각끼리 이은 경계만 있는 컷 {sum(1 for r in rows if r['cross'] and not r['flash'])}개는 통과)")
        for r in bad:
            where = ("앞" if r["head"] else "") + ("뒤" if r["tail"] else "") or "가운데"
            print(f"  영상 {r['t0']:6.2f}초 토막 {r['pieces']} {r['src']} {r['ss']}~{r['end']} ← 경계 {r['cross']} 짧은 조각 {r['short']} ({where}) 제안 ss {r['fix_ss']}")
    sys.exit(1 if rc else 0)
