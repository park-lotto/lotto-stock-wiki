"""어두운 바탕 · 밝은 글자 틀(틀 B mY · 핫템 OE11)이 to_frame → 라이브 렌더러(장면 레이어)에서 극성 그대로 나오나 — 렌더 프레임 실측.

원본 프레임(fixtures/calcopy_to_frame/<편>_t1.png)과 그 편 뜯기.json 으로 to_frame.build → frame.json → to_snapshot → render_scene_style.js
(render_layer_one 과 같은 요청, 느린 PC 를 위해 시간 한도만 길게) → 레이어 PNG 를 영상 창 자리에 회색(128) 영상을 깔고 합성한 뒤
원본·렌더 둘 다 같은 자로 잰다:
  - 바탕(창 위 글자 없는 점) 밝기          : 둘 다 어둡다(≤ 30)
  - 제목 줄마다 채움색 점 수·행 범위         : 원본 줄 색(line_rgb) ±50 안 점, 렌더도 같은 색으로 찍힌다(잉크 비 0.6~1.6)
  - 자막: 흰 채움 점 + 그 둘레 검정 외곽선   : 렌더 자막 칸에 흰 점이 있고, 흰 점 3px 바깥 고리의 검정 비율 ≥ 0.6
쓰는 법: py tools/calcopy/check_polarity_render.py <출력폴더>
"""
import json
import pathlib
import subprocess
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
import cv2  # noqa: E402
from PIL import Image  # noqa: E402

from shopping_shorts import scene_style  # noqa: E402
from shopping_shorts.calcopy_frame import schema, to_snapshot  # noqa: E402
from tools.calcopy.engine import to_frame  # noqa: E402

FIX = ROOT / "shopping_shorts/tests/fixtures/calcopy_to_frame"
CASES = {
    "mY": ("channel/sseolpulda/뜯기/mYxuF1A74j4/뜯기.json", "mY_t1.png", {"title": ["퍽? 이게 뭐라고", "눈물 줄줄 ㅠㅠ"]}, "선수가 퍽을"),
    "OE11": ("channel/hottemreport/뜯기/OE-11wb7vdY/뜯기.json", "OE11_t1.png",
             {"title": ["AI 주작 논란 터진", "아이언맨 헬멧"], "brand": "핫템리포트"}, "요즘 미국에서 난리난"),
}
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
fails = []


def need(ok, msg):
    print(("  통과  " if ok else "★ 실패  ") + msg)
    if not ok:
        fails.append(msg)


def render(frame: dict, cap: str, tag: str) -> np.ndarray:
    snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(frame))
    t = next(l for l in schema.validate(frame)["layers"] if l.get("role") == "title")["text"]
    tl = [{"beat_idx": 0, "t0": 0, "dur": 2, "narration": cap, "caption_lines": [cap], "role": "hook",
           "primary": {"video_id": "s", "start": 0, "end": 2}}]
    ctx = scene_style.context_for(tl, {"text": t}, snap, "spec")
    o = out / tag; o.mkdir(parents=True, exist_ok=True)
    rq = o / "scene-style-request.json"
    rq.write_text(json.dumps({"snapshot": snap, "context": ctx, "output": str(o), "only": [0], "still": True}, ensure_ascii=False), encoding="utf-8")
    for _ in range(4):   # 부하가 큰 PC 에서 크롬 띄우기가 가끔 실패한다 — 다시 시도
        r = subprocess.run(["node", str(ROOT / "tools/render_scene_style.js"), str(rq)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=900)
        if r.returncode == 0:
            break
    assert r.returncode == 0, r.stderr[-400:]
    lay = Image.open(o / json.loads((o / "scene-style-layers.json").read_text(encoding="utf-8"))[0]["file"]).convert("RGBA")
    base = Image.new("RGBA", lay.size, (128, 128, 128, 255)); base.alpha_composite(lay)
    a = np.asarray(base.convert("RGB"))
    Image.fromarray(a).save(o / "composite.png")
    return a


def color_rows(a, rgb, y0, y1):
    m = np.zeros(a.shape[:2], bool)
    m[y0:y1] = np.abs(a[y0:y1].astype(int) - rgb).max(axis=2) < 50
    rows = np.where(m.sum(axis=1) > 10)[0]
    return int(m.sum()), ([int(rows.min()), int(rows.max())] if len(rows) else None)


def white_with_black_ring(a, y0, y1):
    reg = a[y0:y1].astype(int)
    white = (reg.min(axis=2) > 225).astype(np.uint8)
    white = cv2.morphologyEx(white, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    ring = cv2.dilate(white, np.ones((7, 7), np.uint8)).astype(bool) & ~white.astype(bool)
    return int(white.sum()), (float((reg[ring].max(axis=1) < 70).mean()) if ring.sum() else 0.0)


for name, (tj, png, ocr, cap) in CASES.items():
    print(f"== {name}")
    J = json.loads((ROOT / tj).read_text(encoding="utf-8"))
    orig = np.asarray(Image.open(FIX / png).convert("RGB"))
    F = to_frame.build(J, orig, ocr)
    F.pop("made_from", None)
    (out / f"frame_{name}.json").write_text(json.dumps(F, ensure_ascii=False, indent=1), encoding="utf-8")
    ren = render(F, cap, name)
    L = J["layout"]; win = L["window"]
    t = next(l for l in F["layers"] if l.get("role") == "title")
    c = next(l for l in F["layers"] if l.get("role") == "caption")
    need(max(t["rgb"]) > 200 and (c["rgb"][0] > 200), f"설명서 극성: 제목 {t['rgb']} · 줄색 {t.get('line_rgb')} · 자막 {c['rgb']} 외곽선 {c.get('outline')}")
    bgp = [(20, 30), (1060, 30), (20, win[1] - 10), (1060, win[1] - 10)]
    need(all(max(ren[y, x]) <= 30 for x, y in bgp), f"렌더 바탕 어둡다 {[ren[y, x].tolist() for x, y in bgp]} (원본 {[orig[y, x].tolist() for x, y in bgp]})")
    bands = [b for b in L["above_bands"] if b[0] > 100][-len(t.get("line_rgb") or [t["rgb"]]):]
    for i, (rgb, b) in enumerate(zip(t.get("line_rgb") or [t["rgb"]], bands)):
        y0, y1 = b[0] - 20, b[1] + 40
        no, ro = color_rows(orig, rgb, y0, y1)
        nr, rr = color_rows(ren, rgb, y0, y1)
        need(no > 0 and 0.6 <= nr / no <= 1.6, f"제목 {i + 1}줄 색 {rgb}: 원본 점 {no} 행 {ro} · 렌더 점 {nr} 행 {rr} (비 {nr / max(1, no):.2f})")
    cy0, cy1 = int(c["y"] - 40), int(c["y"] + c["line_h"] + 40)
    wo, bo = white_with_black_ring(orig, cy0, cy1)
    wr, br = white_with_black_ring(ren, cy0, cy1)
    need(wr > 500 and br >= 0.6, f"자막 흰 채움 점 {wr}(원본 {wo}) · 둘레 검정 비율 {br:.2f}(원본 {bo:.2f})")

print("\n결과:", "전부 통과" if not fails else f"실패 {len(fails)}건")
sys.exit(1 if fails else 0)
