"""확대 이어받기(zoom_runs) 점검 — 서버 규칙(scene_style.zoom_runs)과 편집기 미리보기(scene-style-connect.js zoomRunOf)가
무작위 장면·효과 500벌에서 같은 답을 내는지, 그리고 이어받은 칸의 곡선이 앞 칸 끝 값에서 이어지는지(튐 없음) 잰다.
실행: py tools/scene_font_research/check_zoom_runs.py"""
import json, random, re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shopping_shorts.scene_style import zoom_runs, zoom_curve

src = (ROOT / "out/scene-style-connect.js").read_text(encoding="utf-8")
fn = src[src.index("  const ZOOM_KEYS="):src.index("  function sync(){")]
cases = []
rnd = random.Random(7)
for _ in range(500):
    sc, t, beat = [], 0.0, 0
    for i in range(rnd.randint(1, 8)):
        if rnd.random() < .45: beat += 1
        d = round(rnd.uniform(.3, 1.6), 2); sc.append({"start": t, "end": round(t + d, 2), "beat_idx": beat}); t = round(t + d, 2)
    ef = {}
    for i in range(len(sc)):
        r = rnd.random()
        if r < .3: ef[str(i)] = {"zoom": 1.3, "zoomIn": .5, "zoomMove": rnd.choice(["in", "pull", "inout"]), "panX": .2}
        elif r < .4: ef[str(i)] = {"zoom": 1.35, "fxAuto": "jump"}
        elif r < .5: ef[str(i)] = {"dim": {"level": .5}}
    cases.append({"sc": sc, "ef": ef})
js = fn + "\nconst cases=" + json.dumps(cases) + ";let cur;const api={context:()=>({scenes:cur.sc}),effectAt:k=>cur.ef[String(k)]||{}};\n" \
     "console.log(JSON.stringify(cases.map(c=>{cur=c;return c.sc.map((_,i)=>{const r=zoomRunOf(i);return [r.fx,+r.off.toFixed(4),+r.dur.toFixed(4)]})})))"
out = json.loads(subprocess.run(["node"], input=js, capture_output=True, text=True, encoding="utf-8", check=True).stdout)
bad = 0
for c, got in zip(cases, out):
    want = [[fx, round(o, 4), round(d, 4)] for fx, o, d in zoom_runs(c["sc"], c["ef"])]
    if want != got:
        bad += 1
        if bad <= 3: print("어긋남", c, want, got)
# 튐: 이어받은 칸 시작 배율 == 앞 칸 끝 배율
jumps = 0
for c in cases:
    r = zoom_runs(c["sc"], c["ef"])
    for i in range(1, len(r)):
        fx, off, dur = r[i]
        if off > 0:
            pfx, poff, _ = r[i - 1]
            pend = c["sc"][i - 1]["end"] - c["sc"][i - 1]["start"] + poff
            a = zoom_curve(pend, dur, fx["zoom"], fx.get("zoomMove", "in"), fx["zoomIn"])
            b = zoom_curve(off, dur, fx["zoom"], fx.get("zoomMove", "in"), fx["zoomIn"])
            jumps += abs(a - b) > 1e-6
print(f"서버↔편집기 어긋남 {bad}/500 · 이어받은 칸 경계 튐 {jumps}")
sys.exit(1 if bad or jumps else 0)
