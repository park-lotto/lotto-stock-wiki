"""등장 효과팩 20종 만들기(관제 144) — 계약 파일 shopping_shorts/static/caption-motions.js 의 CAPTION_MOTION_PACKS 를 쓴다.

  py tools/caption_pack/make_motion_packs.py          # 만들고 계약 파일에 쓴다(같은 씨앗 = 늘 같은 20종)
  py tools/caption_pack/make_motion_packs.py --check  # 쓰지 않고 지금 계약 파일만 잰다

효과음팩(sfx_pack, 20종·두 팩 사이 7칸 중 최소 4칸 다름)과 같은 방식. 효과팩은 **움직임만** — 글꼴·색·상자·강조는 자막 스타일·고객 설정 그대로.
칸: first 첫 장면 · body 일반 줄(3개를 번갈아) · price 가격·숫자 · problem 문제 제기 · reveal 제품 공개 · end 마지막 장면 · emph 영상 위 강조.
칸마다 어울리는 후보만 쓴다(가격 줄에 '서서히 나타나기' 같은 약한 효과를 넣지 않는다).
★장면 효과(fx, 2026-10-06 사장님 "장면효과팩 여기서 통합") — 장면 성격(moment)별 줌·어둡게·흑백. 효과팩 번호 하나에 자막 움직임과 같이 묶인다.
  값은 켤 효과 목록(확대 in·pull·inout 중 하나 + dim 어둡게+큰 글자 + shock 흑백 충격). 편집기 자동 배치(api.autoPlace)가 이 표를 쓴다.
  자막 움직임 20벌은 바꾸지 않으려고 장면 효과는 따로 씨앗으로 만들어 붙인다(두 팩 최소 FX_MIN_DIFF 칸 다름).
"""
import json, random, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "shopping_shorts/static/caption-motions.js"
N, MIN_DIFF, SEED = 20, 4, 20261006
POOL = {
    "first":   ["slam", "riseClip", "trackIn", "popBounce", "wide", "drop"],
    "body":    ["rise", "blurUp", "popBounce", "riseClip", "slide", "pop", "fade", "typing", "jelly", "grow"],
    "price":   ["slam", "jelly", "popBounce", "pop", "drop"],
    "problem": ["drop", "typing", "fade", "slide", "wide"],
    "reveal":  ["popBounce", "pop", "slam", "riseClip", "grow", "wide"],
    "end":     ["slam", "riseClip", "trackIn", "blurUp", "popBounce", "rise"],
    "emph":    ["slam", "trackIn", "popBounce", "riseClip", "grow", "blurUp"],
}
SLOTS = list(POOL)
FX_POOL = {
    "hook":    [["in"], ["pull"], ["inout"]],
    "problem": [["shock"], ["inout"], ["in", "shock"]],
    "reveal":  [["pull"], ["in"], ["inout"]],
    "peak":    [["dim"], ["dim", "in"], ["dim", "pull"], ["shock", "pull"]],
    "cta":     [["inout"], ["in"], ["pull"]],
}
FX_MIN_DIFF, FX_SEED = 2, 20261007


def diff(a, b):
    """두 팩이 다른 칸 수(일반 줄은 3개 묶음을 순서 없이 비교)."""
    return sum((set(a[s]) != set(b[s])) if s == "body" else (a[s] != b[s]) for s in SLOTS)


def make():
    rnd = random.Random(SEED); packs = []
    while len(packs) < N:
        p = {s: (rnd.sample(POOL[s], 3) if s == "body" else rnd.choice(POOL[s])) for s in SLOTS}
        if all(diff(p, q) >= MIN_DIFF for q in packs):
            packs.append(p)
    return packs


def fx_diff(a, b):
    return sum(sorted(a[m]) != sorted(b[m]) for m in FX_POOL)


def make_fx(n):
    rnd = random.Random(FX_SEED); out = []
    while len(out) < n:
        f = {m: rnd.choice(FX_POOL[m]) for m in FX_POOL}
        if all(fx_diff(f, g) >= FX_MIN_DIFF for g in out):
            out.append(f)
    return out


def read():
    return json.loads(CONTRACT.read_text(encoding="utf-8").split("/*MPACKS*/")[1])


def measure(packs):
    motions = json.loads(CONTRACT.read_text(encoding="utf-8").split("/*JSON*/")[1])
    vals = [p[s] for p in packs for s in SLOTS]
    bad = [v for vv in vals for v in (vv if isinstance(vv, list) else [vv]) if v not in motions]
    pair = min(diff(a, b) for i, a in enumerate(packs) for b in packs[i + 1:])
    same_body = [i + 1 for i, p in enumerate(packs) if len(set(p["body"])) < 3]
    fxs = [p.get("fx") for p in packs]
    fx_pair = min(fx_diff(a, b) for i, a in enumerate(fxs) for b in fxs[i + 1:]) if all(fxs) else 0
    fx_kinds = {k for f in fxs if f for v in f.values() for k in v}
    return {"팩": len(packs), "모르는 효과": bad, "두 팩 최소 다른 칸": pair, "일반 줄 3개가 겹치는 팩": same_body,
            "장면 효과 두 팩 최소 다른 칸": fx_pair, "장면 효과 종류": sorted(fx_kinds), "서로 다른 장면 효과 조합": len({json.dumps(f, sort_keys=True) for f in fxs})}


if __name__ == "__main__":
    if "--check" not in sys.argv:
        packs = make()
        for p_, f in zip(packs, make_fx(len(packs))):
            p_["fx"] = f
        text = CONTRACT.read_text(encoding="utf-8")
        body = json.dumps(packs, ensure_ascii=False)
        if "/*MPACKS*/" in text:
            a, _, b = text.split("/*MPACKS*/", 2); text = a + "/*MPACKS*/" + body + "/*MPACKS*/" + b
        else:
            text = text.replace("\n})(window);", """
  // 등장 효과팩 20종(관제 144) — 움직임만. 칸별 효과(일반 줄 body 는 3개를 번갈아). 번호 = 배열 순서 + 1.
  //   만든 곳: tools/caption_pack/make_motion_packs.py(씨앗 고정 · 두 팩 최소 4칸 다름) — 손으로 고치지 말고 그 도구로.
  //   배정: 회원마다 자동(scene_style.caption_motion_pack_for, 효과음팩과 같은 crc32) · 영상마다 자동/끔/번호(snapshot.motionPack).
  //   ★서버는 MPACKS 표식 두 개 사이를 json 으로 읽는다 — 그 안에는 JSON 만.
  root.CAPTION_MOTION_PACKS = /*MPACKS*/""" + body + """/*MPACKS*/;
})(window);""")
        CONTRACT.write_text(text, encoding="utf-8", newline="\n")
    m = measure(read())
    print(json.dumps(m, ensure_ascii=False))
    sys.exit(0 if not m["모르는 효과"] and m["두 팩 최소 다른 칸"] >= MIN_DIFF and not m["일반 줄 3개가 겹치는 팩"] and m["팩"] == N
             and m["장면 효과 두 팩 최소 다른 칸"] >= FX_MIN_DIFF and m["서로 다른 장면 효과 조합"] == N else 1)
