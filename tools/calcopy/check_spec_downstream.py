"""칼카피 틀 설명서 모드가 편집 화면 · 렌더 레이어 · 썸네일 · 최종 합성에서 **같은 그림**을 내나 (0순위-A1a).

check_plain_downstream.py 와 같은 방식(같은 스냅샷 → 네 길 → 잉크 상자 대조)이다.
  ⓪ 서버 검사: to_snapshot 결과가 validate_snapshot 통과 / 편집 화면이 다시 저장한 스냅샷도 통과하고 같은 틀 번호
  ① 편집 화면(장면꾸미기 UI 그대로)의 미리보기 칸 — tools/calcopy/spec_editor_shot.js
  ② 렌더·캡컷용 레이어(render_layers) — 장면 2개(자막이 장면마다 바뀌는지)
  ③ 썸네일 한 장(render_layer_one)
  ④ 최종 합성 mp4(compose) 0.5초 프레임
기준 = ② 첫 장면. 층마다 잉크 상자(x0,y0,x1,y1) 차이를 재고, ②③④는 2px, ①(화면 배율이 달라 다시 키움)은 화면 높이의 0.6% 안이면 통과.
쓰는 법: py tools/calcopy/check_spec_downstream.py <출력폴더> [frame.json]
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools" / "calcopy"))
from PIL import Image  # noqa: E402

from shopping_shorts import scene_style, video_assemble as va  # noqa: E402
from shopping_shorts.calcopy_frame import schema, to_snapshot  # noqa: E402
from frame_compare import measure  # noqa: E402

out = pathlib.Path(sys.argv[1]).resolve(); shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
frame_path = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "shopping_shorts/calcopy_frame/examples/frame_A_ZdeZRtCeAC4.json"
frame = json.loads(frame_path.read_text(encoding="utf-8"))
spec = schema.validate(frame)
fails = []


def need(ok, msg):
    print(("  통과  " if ok else "★ 실패  ") + msg)
    if not ok:
        fails.append(msg)


CAPS = ["아니 이거 해외 릴스에서 맨날 보이길래", "두 번째 장면 자막"]
timeline = [{"beat_idx": i, "t0": i, "dur": 1, "narration": c, "caption_lines": [c], "role": "hook" if i == 0 else "body",
             "primary": {"video_id": "s0", "start": i, "end": i + 1}} for i, c in enumerate(CAPS)]
HEAD = {"text": "닿으면 스피커\n소름 돋는 음질 수준"}

# ⓪ 서버 검사
snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(frame))
need(snap.get("customFrame", {}).get("id") == snap["presetId"], f"⓪ validate_snapshot 통과 · 틀 번호 {snap['presetId']}")


def flat(png, bg=(255, 255, 255)):
    im = Image.open(png).convert("RGBA")
    if im.size != (1080, 1920):
        im = im.resize((1080, 1920), Image.LANCZOS)
    base = Image.new("RGBA", im.size, bg + (255,)); base.alpha_composite(im)
    return base.convert("RGB")


# ① 편집 화면
context = scene_style.context_for(timeline, HEAD, snap)
req = out / "editor-request.json"
req.write_text(json.dumps({"snapshot": snap, "context": context, "output": str(out), "index": 0}, ensure_ascii=False), encoding="utf-8")
env = os.environ.copy()
if sys.platform.startswith("linux"):
    env.setdefault("SCENE_STYLE_NO_SANDBOX", "1")
run = subprocess.run(["node", str(ROOT / "tools/calcopy/spec_editor_shot.js"), str(req)], capture_output=True, text=True,
                     encoding="utf-8", errors="replace", timeout=180, env=env)
need(run.returncode == 0, "① 편집 화면 열기·찍기" + ("" if run.returncode == 0 else ": " + run.stderr[-800:]))
if run.returncode == 0:
    resaved = json.loads((out / "editor-snapshot.json").read_text(encoding="utf-8"))
    try:
        again = scene_style.validate_snapshot(resaved)
        need(again["presetId"] == snap["presetId"] and again["customFrame"]["id"] == snap["presetId"],
             f"① 편집 화면이 다시 저장한 스냅샷도 같은 틀({again['presetId']})로 서버 검사 통과")
    except Exception as exc:
        need(False, f"① 편집 화면 저장본이 서버 검사에서 막힘: {exc}")

# ② 렌더 레이어
layers = scene_style.render_layers(timeline, snap, out / "layers", HEAD, "spec")
pngs = [out / "layers" / l["file"] for l in layers]
need(len(pngs) >= 2, f"② 렌더·캡컷용 레이어 {len(pngs)}장")
# ③ 썸네일 한 장
one = pathlib.Path(scene_style.render_layer_one(timeline, snap, out / "thumb", 0, HEAD, "spec"))
# ④ 최종 합성
src = out / "src.mp4"
va._run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=1080x1920:d=2", "-r", "30", "-pix_fmt", "yuv420p", str(src)])
final = out / "final.mp4"
scene_style.compose(str(src), timeline, snap, str(final), out / "cw", HEAD)
fpng = out / "final_0.5s.png"
va._run_ffmpeg(["ffmpeg", "-y", "-ss", "0.5", "-i", str(final), "-frames:v", "1", str(fpng)])

# 영상 창은 투명이어야 한다(렌더 합성이 그 자리에 영상을 둔다) · 바탕은 불투명
video = next((l for l in spec["layers"] if l["kind"] == "video"), None)
al = Image.open(pngs[0]).convert("RGBA").split()[3]
if video:
    cx, cy = video["x"] + video["w"] // 2, video["y"] + video["h"] // 2
    need(al.getpixel((cx, cy)) == 0 and al.getpixel((cx, video["y"] - 5)) == 255 and al.getpixel((cx, video["y"] + video["h"] + 5)) == 255,
         f"② 영상 창 가운데 투명(알파 {al.getpixel((cx, cy))}) · 창 바로 위/아래 바탕 불투명({al.getpixel((cx, video['y'] - 5))}/{al.getpixel((cx, video['y'] + video['h'] + 5))})")
    fr = Image.open(fpng).convert("RGB")
    need(fr.getpixel((cx, cy))[2] > 150 and fr.getpixel((cx, cy))[0] < 80, f"④ 완성 영상의 영상 창에 소스 영상(파랑)이 보인다 {fr.getpixel((cx, cy))}")

paths = {"①편집화면": out / "editor.png", "②렌더레이어": pngs[0], "③썸네일": one, "④합성": fpng}
ref = dict(measure(flat(pngs[0]), spec))
need(all(ref.values()), f"② 기준 그림에 모든 글자 층이 찍힌다 {list(ref)}")
table = {}
for name, png in paths.items():
    if not pathlib.Path(png).exists():
        continue
    got = dict(measure(flat(png), spec))
    table[name] = got
    tol = 12 if name.startswith("①") else 2
    for layer, box in got.items():
        rb = ref.get(layer)
        d = max(abs(a - b) for a, b in zip(box, rb)) if box and rb else None
        need(d is not None and d <= tol, f"{name} {layer:8s} {box} (기준 {rb}, 최대 차이 {d}px, 허용 {tol})")
# 장면마다 자막이 바뀌나 — 둘째 장면 자막 상자가 첫 장면과 달라야 한다(같은 글이 박혀 있으면 실패)
cap0, cap1 = dict(measure(flat(pngs[0]), spec)).get("caption"), dict(measure(flat(pngs[1]), spec)).get("caption")
need(cap0 and cap1 and cap0 != cap1, f"② 장면 2의 자막이 장면 1과 다르게 찍힌다 ({cap0} → {cap1})")
(out / "result.json").write_text(json.dumps({"fails": fails, "table": table, "ref": ref}, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n결과:", "전부 통과" if not fails else f"실패 {len(fails)}건")
sys.exit(1 if fails else 0)
