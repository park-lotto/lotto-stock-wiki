# -*- coding: utf-8 -*-
"""channelkit 쪼개기 동일성 — 골든 픽스처 5편의 (린터 issues, 레이아웃 줄나눔, sub.ass 텍스트)를 해시로 찍는다.

  # 쪼개기 전: 옛 커밋을 스냅샷으로 풀어 --root 로 가리킨다(남의 트랙 폴더에서 돌리지 않는다)
  git archive 21c68343a shopping_shorts | tar -x -C <scratch>/pre
  py tools/channelkit/parity_check.py --root <scratch>/pre --write out/channelkit_parity/baseline.json
  # 쪼갠 뒤(이 트랙):
  py tools/channelkit/parity_check.py --compare out/channelkit_parity/baseline.json

두 실행의 해시가 전부 같아야 "전과 같다". 다르면 어느 편·어느 항목인지 찍는다.
옛 패키지(shopping_shorts.brainbulb)와 새 패키지(shopping_shorts.channelkit) 둘 다에서 돌도록 import를 폴백한다.
--root 를 주면 그 트리를 sys.path 맨 앞에 넣어 그 트리의 모듈을 import한다 — 실제로 어느 파일을 읽었는지 찍는다.

입력은 골든 테스트(test_brainbulb_golden._script)와 같게 만든다: payload의 lines는 버리고(레이아웃이 다시 계산),
meme 경로는 enum 통과용 감정 문자열로, source_text = transcript. 시간은 payload의 실측 wav_secs
('0'=카드, '1'..=컷)를 그대로 쓴다 — pipeline.run_step의 layout·lint·timing·subtitle 단계와 같은 호출.
"""
import argparse
import glob
import hashlib
import importlib
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load(root):
    """root 트리의 엔진 모듈을 import. → (모듈 dict, 패키지 이름)"""
    root = os.path.abspath(root)
    sys.path.insert(0, root)
    names = ["lint", "layout", "ass_gen", "timing", "spec"]
    for pkg in ("shopping_shorts.channelkit", "shopping_shorts.brainbulb"):
        try:
            mods = {n: importlib.import_module(f"{pkg}.{n}") for n in names}
        except ImportError:
            continue
        f = os.path.abspath(mods["lint"].__file__)
        if not f.startswith(root):
            raise SystemExit(f"[중단] --root 밖의 모듈을 읽었다: {f}")
        return mods, pkg
    raise SystemExit(f"[중단] {root} 에서 channelkit·brainbulb 둘 다 import 실패")


def _h(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _script(p):
    """볼케이노 payload → 우리 대본 형식(test_brainbulb_golden._script와 같다)."""
    groups = []
    for g in p["groups"]:
        ng = {"text": g["text"], "color": g["color"], "role": g["role"]}
        if g.get("img") is not None:
            ng["img"] = g["img"]
        if g.get("meme"):
            ng["meme"] = "경악/충격"
        groups.append(ng)
    return {"title": p["title"], "region": p.get("region"), "groups": groups}, (p.get("transcript") or "")


def measure(m, root):
    lint, layout, ass_gen, timing, spec = (m[k] for k in ("lint", "layout", "ass_gen", "timing", "spec"))
    fonts_dir = spec.FONTS_DIR
    fix = os.path.join(root, "shopping_shorts", "tests", "fixtures", "brainbulb")
    out = {}
    for d in sorted(glob.glob(os.path.join(fix, "*"))):
        name = os.path.basename(d)
        pth = os.path.join(d, "payload.json")
        if not os.path.isfile(pth):
            continue
        with open(pth, encoding="utf-8") as fh:
            p = json.load(fh)
        script, src = _script(p)
        # pipeline: layout 단계 → lint 단계(do_layout=False + r_layout) — lint.lint(do_layout=True)와 같은 규칙 집합
        issues, laid = lint.lint(script, source_text=src, do_layout=True, fonts_dir=fonts_dir)
        groups = laid["groups"]
        ws = p.get("wav_secs") or {}
        card_sec = float(ws.get("0", 3.0))
        cut_secs = [float(ws.get(str(i + 1), 2.0)) for i in range(len(groups))]
        tm = timing.build(card_sec, cut_secs, groups)
        ass = ass_gen.build(script["title"], script["title"]["card"], tm, fonts_dir=fonts_dir)
        if os.path.abspath(root) in ass or fonts_dir in ass:
            raise SystemExit(f"[중단] {name}: ASS에 절대경로가 들어 있다 — 해시가 폴더마다 달라진다")
        out[name] = {"issues": _h([i.__dict__ for i in issues]),
                     "lines": _h([g.get("lines") for g in groups]),
                     "ass": _h(ass)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=_REPO, help="엔진 코드를 읽을 트리(기본: 이 저장소)")
    ap.add_argument("--write")
    ap.add_argument("--compare")
    a = ap.parse_args()
    if not (a.write or a.compare):
        ap.error("--write 또는 --compare")
    mods, pkg = _load(a.root)
    print(f"[import] {pkg} ← {mods['lint'].__file__}")
    cur = measure(mods, os.path.abspath(a.root))
    if a.write:
        os.makedirs(os.path.dirname(os.path.abspath(a.write)), exist_ok=True)
        with open(a.write, "w", encoding="utf-8") as fh:
            json.dump(cur, fh, ensure_ascii=False, indent=1)
        print(f"wrote {len(cur)}편 → {a.write}")
        return 0
    with open(a.compare, encoding="utf-8") as fh:
        base = json.load(fh)
    bad = [(n, k) for n in base for k in base[n] if cur.get(n, {}).get(k) != base[n][k]]
    extra = sorted(set(cur) - set(base))
    print(f"편 {len(base)} · 항목 {sum(len(v) for v in base.values())} · 불일치 {len(bad)}")
    for n, k in bad:
        print(f"  ✗ {n}.{k}: {base[n][k]} → {cur.get(n, {}).get(k)}")
    if extra:
        print(f"  (기준선에 없는 편: {extra})")
    return 1 if (bad or not base) else 0


if __name__ == "__main__":
    sys.exit(main())
