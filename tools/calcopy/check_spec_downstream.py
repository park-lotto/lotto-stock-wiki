"""칼카피 틀 설명서 모드가 편집 화면 · 렌더 레이어 · 썸네일 · 최종 합성에서 **같은 그림**을 내나 (0순위-A1a).

check_plain_downstream.py 와 같은 방식(같은 스냅샷 → 네 길 → 잉크 상자 대조)이다.
장면 2개(8초 + 2초). 틀 A 의 template_off.tail_sec=3.5 → 장면 2(8초 시작)는 **틀이 꺼진다**(원본 끝 3.5초처럼 영상 전체 화면).
  ⓪ 서버 검사: to_snapshot 결과가 validate_snapshot 통과 / 편집 화면이 다시 저장한 스냅샷도 통과하고 같은 틀 번호
  ① 편집 화면(장면꾸미기 UI 그대로)의 미리보기 칸 — tools/calcopy/spec_editor_shot.js (장면 1 그림 · 장면 2 영상칸·그린 요소 수)
  ② 렌더·캡컷용 레이어(render_layers)
  ③ 썸네일 한 장(render_layer_one) — 장면 1 · 장면 2
  ④ 최종 합성 mp4(compose) — 0.5초(장면 1) · 9초(장면 2)
  ⑤ 틀 끄기 대조: template_off 를 뺀 같은 설명서로 그린 장면 1 레이어와 픽셀이 같아야 한다(끄기가 장면 1을 건드리지 않는다)
기준 = ② 장면 1. 층마다 잉크 상자(x0,y0,x1,y1) 차이: ②③④ 2px, ①(화면 배율이 달라 다시 키움) 12px 안이면 통과.
쓰는 법: py tools/calcopy/check_spec_downstream.py <출력폴더> [frame.json]
"""
import copy
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools" / "calcopy"))
from PIL import Image, ImageChops  # noqa: E402

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
DURS = [8, 2]
timeline, t = [], 0
for i, (c, d) in enumerate(zip(CAPS, DURS)):
    timeline.append({"beat_idx": i, "t0": t, "dur": d, "narration": c, "caption_lines": [c], "role": "hook" if i == 0 else "body",
                     "primary": {"video_id": "s0", "start": t, "end": t + d}}); t += d
HEAD = {"text": "닿으면 스피커\n소름 돋는 음질 수준"}
OFF = (spec.get("template_off") or {})
need(OFF.get("tail_sec") and DURS[-1] <= OFF["tail_sec"] < DURS[-1] + DURS[0],
     f"(전제) 설명서 template_off.tail_sec={OFF.get('tail_sec')} — 이 검사의 장면 2({DURS[0]}초 시작)만 꺼지는 값")

# ⓪ 서버 검사
snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(frame))
need(snap.get("customFrame", {}).get("id") == snap["presetId"], f"⓪ validate_snapshot 통과 · 틀 번호 {snap['presetId']}")


def flat(png, bg=(255, 255, 255)):
    im = Image.open(png).convert("RGBA")
    if im.size != (1080, 1920):
        im = im.resize((1080, 1920), Image.LANCZOS)
    base = Image.new("RGBA", im.size, bg + (255,)); base.alpha_composite(im)
    return base.convert("RGB")


def max_alpha(png):
    return Image.open(png).convert("RGBA").split()[3].getextrema()[1]


# ① 편집 화면 — 장면 1(그림) · 장면 2(꺼짐)
context = scene_style.context_for(timeline, HEAD, snap)
need(len(context["scenes"]) == 2, f"(전제) 장면 {len(context['scenes'])}개 — {[(s['start'], s['end']) for s in context['scenes']]}")
env = os.environ.copy()
if sys.platform.startswith("linux"):
    env.setdefault("SCENE_STYLE_NO_SANDBOX", "1")
for idx, tag in ((0, "editor"), (1, "editor-off")):
    req = out / f"{tag}-request.json"
    req.write_text(json.dumps({"snapshot": snap, "context": context, "output": str(out), "index": idx, "tag": tag}, ensure_ascii=False), encoding="utf-8")
    run = subprocess.run(["node", str(ROOT / "tools/calcopy/spec_editor_shot.js"), str(req)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=180, env=env)
    need(run.returncode == 0, f"① 편집 화면 장면 {idx + 1} 열기·찍기" + ("" if run.returncode == 0 else ": " + run.stderr[-800:]))
if (out / "editor-snapshot.json").exists():
    resaved = json.loads((out / "editor-snapshot.json").read_text(encoding="utf-8"))
    try:
        again = scene_style.validate_snapshot(resaved)
        need(again["presetId"] == snap["presetId"] and again["customFrame"]["id"] == snap["presetId"],
             f"① 편집 화면이 다시 저장한 스냅샷도 같은 틀({again['presetId']})로 서버 검사 통과")
    except Exception as exc:
        need(False, f"① 편집 화면 저장본이 서버 검사에서 막힘: {exc}")
if (out / "editor-off-probe.json").exists():
    probe = json.loads((out / "editor-off-probe.json").read_text(encoding="utf-8"))
    on = json.loads((out / "editor-probe.json").read_text(encoding="utf-8"))
    need(probe["geometry"]["media"] == {"top": 0, "height": 100} and probe["drawn"] == 0,
         f"① 편집 화면 장면 2: 영상 칸 {probe['geometry']['media']} · 그린 요소 {probe['drawn']}개 (기대 전체 화면 · 0개)")
    need(on["drawn"] > 0 and on["geometry"]["media"]["top"] > 0, f"① 편집 화면 장면 1은 틀 그대로: 영상 칸 {on['geometry']['media']} · 그린 요소 {on['drawn']}개")

# ② 렌더 레이어
layers = scene_style.render_layers(timeline, snap, out / "layers", HEAD, "spec")
pngs = [out / "layers" / l["file"] for l in layers]
need(len(pngs) == 2, f"② 렌더·캡컷용 레이어 {len(pngs)}장")
need(layers[1]["media"] == {"top": 0, "height": 100} and max_alpha(pngs[1]) == 0,
     f"② 장면 2 레이어: 영상 칸 {layers[1]['media']} · 최대 알파 {max_alpha(pngs[1])} (기대 전체 화면 · 0 = 아무것도 안 그림)")
# ③ 썸네일 한 장 — 장면 1 · 장면 2
one = pathlib.Path(scene_style.render_layer_one(timeline, snap, out / "thumb", 0, HEAD, "spec"))
one_off = pathlib.Path(scene_style.render_layer_one(timeline, snap, out / "thumb_off", 1, HEAD, "spec"))
need(max_alpha(one_off) == 0, f"③ 썸네일 장면 2 최대 알파 {max_alpha(one_off)} (기대 0)")
# ④ 최종 합성
src = out / "src.mp4"
va._run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=blue:s=1080x1920:d={sum(DURS)}", "-r", "30", "-pix_fmt", "yuv420p", str(src)])
final = out / "final.mp4"
scene_style.compose(str(src), timeline, snap, str(final), out / "cw", HEAD)
fpng, fpng_off = out / "final_0.5s.png", out / "final_9s.png"
va._run_ffmpeg(["ffmpeg", "-y", "-ss", "0.5", "-i", str(final), "-frames:v", "1", str(fpng)])
va._run_ffmpeg(["ffmpeg", "-y", "-ss", "9", "-i", str(final), "-frames:v", "1", str(fpng_off)])
blue = lambda p: p[2] > 150 and p[0] < 80 and p[1] < 80  # noqa: E731
f_on, f_off = Image.open(fpng).convert("RGB"), Image.open(fpng_off).convert("RGB")
probe_pts = [(540, 100), (540, 1700), (540, 300), (540, 1500)]   # 바탕·제목·자막 자리
need(all(blue(f_off.getpixel(p)) for p in probe_pts), f"④ 완성 영상 9초(장면 2): 바탕·제목·자막 자리가 전부 영상(파랑) {[f_off.getpixel(p) for p in probe_pts]}")
need(not blue(f_on.getpixel((540, 100))) and not blue(f_on.getpixel((540, 1700))), f"④ 완성 영상 0.5초(장면 1): 바탕이 그대로 {[f_on.getpixel(p) for p in probe_pts[:2]]}")

# 영상 창은 투명이어야 한다(렌더 합성이 그 자리에 영상을 둔다) · 바탕은 불투명
video = next((l for l in spec["layers"] if l["kind"] == "video"), None)
al = Image.open(pngs[0]).convert("RGBA").split()[3]
if video:
    cx, cy = video["x"] + video["w"] // 2, video["y"] + video["h"] // 2
    need(al.getpixel((cx, cy)) == 0 and al.getpixel((cx, video["y"] - 5)) == 255 and al.getpixel((cx, video["y"] + video["h"] + 5)) == 255,
         f"② 장면 1 영상 창 가운데 투명(알파 {al.getpixel((cx, cy))}) · 창 바로 위/아래 바탕 불투명")
    need(blue(f_on.getpixel((cx, cy))), f"④ 장면 1 영상 창에 소스 영상(파랑) {f_on.getpixel((cx, cy))}")

paths = {"①편집화면": out / "editor.png", "②렌더레이어": pngs[0], "③썸네일": one, "④합성": fpng}
ref = dict(measure(flat(pngs[0]), spec))
need(all(ref.values()), f"② 기준 그림(장면 1)에 모든 글자 층이 찍힌다 {list(ref)}")
table = {}
for name, png in paths.items():
    if not pathlib.Path(png).exists():
        need(False, f"{name} 그림 없음"); continue
    got = dict(measure(flat(png), spec))
    table[name] = got
    tol = 12 if name.startswith("①") else 2
    for layer, box in got.items():
        rb = ref.get(layer)
        d = max(abs(a - b) for a, b in zip(box, rb)) if box and rb else None
        need(d is not None and d <= tol, f"{name} {layer:8s} {box} (기준 {rb}, 최대 차이 {d}px, 허용 {tol})")

# ⑤ 틀 끄기를 뺀 같은 설명서 — 장면 1은 픽셀이 같고, 장면 2는 틀이 그려지며 자막이 장면 1과 다르다
plain = copy.deepcopy(frame); plain["template_off"] = None
snap_on = scene_style.validate_snapshot(to_snapshot.to_snapshot(plain))
layers_on = scene_style.render_layers(timeline, snap_on, out / "layers_on", HEAD, "spec")
p_on = [out / "layers_on" / l["file"] for l in layers_on]
diff = ImageChops.difference(Image.open(pngs[0]).convert("RGBA"), Image.open(p_on[0]).convert("RGBA")).getbbox()
need(diff is None, f"⑤ 장면 1 레이어: 틀 끄기 있음/없음 픽셀 동일 (다른 영역 {diff})")
cap0, cap1 = dict(measure(flat(p_on[0]), spec)).get("caption"), dict(measure(flat(p_on[1]), spec)).get("caption")
need(max_alpha(p_on[1]) == 255 and cap0 and cap1 and cap0 != cap1, f"⑤ 끄기 없으면 장면 2에 틀이 그려지고 자막이 바뀐다 ({cap0} → {cap1})")

(out / "result.json").write_text(json.dumps({"fails": fails, "table": table, "ref": ref}, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n결과:", "전부 통과" if not fails else f"실패 {len(fails)}건")
sys.exit(1 if fails else 0)
