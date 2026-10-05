"""자막팩 등장 효과 점검(관제 127) — 편집기 렌더러가 찍은 프레임과 최종 합성 영상으로 잰다.

  py tools/caption_pack/check_motions.py <출력폴더> [효과키,...] [--baseline <기준폴더>] [--compose] [--wordfx[=방식]] [--long]

효과마다(본문 장면 s1) render_layers 로 레이어를 찍고:
  ① 등장 프레임 묶음이 생겼나(animation.count)
  ② 첫 프레임 잉크 < 마지막 프레임 잉크(처음엔 덜 보이고 끝엔 다 보인다)
  ③ 마지막 등장 프레임 = 정지 레이어(등장이 끝나면 원래 자막과 같은 그림)
  ④ --baseline: 기준 폴더의 같은 효과 프레임과 픽셀 대조(옛 효과가 안 바뀌었나)
  ⑤ --compose: 최종 합성 mp4 에서 장면 시작 직후 vs 끝 프레임의 자막 영역이 다르다
그리고 효과별 프레임 시트(sheet_<키>.png)를 남긴다 — 눈으로 본다.
"""
import hashlib, json, pathlib, shutil, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from PIL import Image, ImageChops, ImageFilter
from shopping_shorts import scene_style, video_assemble as va

args = sys.argv[1:]
out = pathlib.Path(args.pop(0)).resolve()
baseline = None
if "--baseline" in args:
    i = args.index("--baseline"); baseline = pathlib.Path(args[i + 1]).resolve(); del args[i:i + 2]
compose = "--compose" in args
wordfx_arg = next((a for a in args if a.startswith("--wordfx")), None)   # --wordfx(상자) / --wordfx=circle 등 — 단어 강조를 같이 켠다
wordfx = wordfx_arg.split("=", 1)[1] if wordfx_arg and "=" in wordfx_arg else ("box" if wordfx_arg else "")
long_cap = "--long" in args   # 본문 자막을 길게 — 편집기가 글자 칸을 가로로 줄인다(scaleX). 등장 효과가 그 줄임을 덮지 않나   # 단어 강조(노란 상자·툭 커짐)를 같이 켠다 — 같은 자막 글자를 같이 쪼개 쓰므로 부딪히지 않나
args = [a for a in args if a not in ("--compose", "--long") and not a.startswith("--wordfx")]
keys = args[0].split(",") if args else ["rise", "grow", "pop", "slide", "drop", "fade", "wide"]
out.mkdir(parents=True, exist_ok=True)
fails = []
def need(ok, msg):
    print(("  통과  " if ok else "★ 실패  ") + msg)
    if not ok: fails.append(msg)

tts = out / "v.wav"
if not tts.exists():
    va._run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100", "-t", "2", str(tts)])
CAPS = ["주부들도 감탄한 천재 아이디어", "겉은 바삭 속은 촉촉" + (" 한 입 먹으면 멈출 수 없는 맛" if long_cap else ""), "단돈 9,900원에 끝"]
timeline = [{"beat_idx": i, "t0": i * 2, "dur": 2, "narration": c, "caption_lines": [c], "tts_path": str(tts), "target_seconds": 2,
             "role": "hook" if i == 0 else "body", "primary": {"video_id": "s0", "start": i * 2, "end": i * 2 + 2}}
            for i, c in enumerate(CAPS)]
TEXT = {"channel": "숏템메이커", "hook1": "주부들도 감탄한", "hook2": "천재 아이디어", "bodyTitle": "주부들도 감탄한 천재 아이디어?"}
HEAD = {"text": "주부들도 감탄한\n천재 아이디어"}

def near(a, b):   # 영역이 1px 안에서 같다(기존 확대·톡·펼치기도 고치기 전부터 1px 번짐 — 2026-10-05 기준 렌더 실측)
    return a is not None and b is not None and all(abs(x - y) <= 1 for x, y in zip(a, b))

def hard_diff(x, y):
    """진한 차이 점 수 — x 의 점이 y 의 1px 이웃 어디와도 128 넘게 다르면 센다(둥근 모서리 반 픽셀 번짐은 봐준다)."""
    xa, ya = x.split()[3], y.split()[3]
    hi, lo = ya.filter(ImageFilter.MaxFilter(3)), ya.filter(ImageFilter.MinFilter(3))
    over = ImageChops.subtract(xa, hi, offset=0)        # x 가 이웃 최댓값보다 진함
    under = ImageChops.subtract(lo, xa, offset=0)       # x 가 이웃 최솟값보다 옅음
    return sum(1 for v in ImageChops.lighter(over, under).get_flattened_data() if v > 128)

def ink(im):
    a = im.split()[3]
    return sum(1 for v in a.get_flattened_data() if v > 40)

def render(key, d):
    snap = scene_style.validate_snapshot({"version": 1, "mode": "story", "plainCaption": 2, "presetId": "plain", "sceneIndex": 0,
                                          "frameKind": "hook", "text": TEXT, **({"bodyCaptionMotion": key} if key else {}),
                                          **({"wordFx": {"style": wordfx, "color": "", "grow": "pop"}} if wordfx else {})})
    return snap, scene_style.render_layers(timeline, snap, d, HEAD, "cpqa")

# 효과 없는 자막 — 등장이 끝난 그림이 이것과 같아야 한다(글자를 쪼개도 자리·모양이 그대로)
shutil.rmtree(out / "_none", ignore_errors=True)
_, pl = render("", out / "_none")
plain = Image.open(out / "_none" / pl[1]["file"]).convert("RGBA").crop((0, 400, 1080, 1700))
plain_spans = pl[1].get("wordSpans") or []

for key in keys:
    d = out / key
    shutil.rmtree(d, ignore_errors=True)
    snap, layers = render(key, d)
    lay = layers[1]
    anim = lay.get("animation")
    need(bool(anim and anim["count"] >= 3), f"① [{key}] 본문 장면 등장 프레임 {anim and anim['count']}장")
    if not anim:
        continue
    frames = [d / anim["pattern"].replace("%04d", str(f).zfill(4)) for f in range(anim["count"])]
    # 자막 영역만 본다(제목은 정지) — 아래 절반
    crop = lambda p: Image.open(p).convert("RGBA").crop((0, 400, 1080, 1700))
    first, last, still = crop(frames[0]), crop(frames[-1]), crop(d / lay["file"])
    need(ink(first) < ink(last) * .25, f"② [{key}] 첫 프레임은 덜 보인다: 잉크 {ink(first)} (끝 프레임 {ink(last)}의 25% 미만 — 천천히 확대는 옅게 시작하는 게 정상)")
    # 가장자리 번짐(실측 최대 97/255 — 기존 확대·톡·펼치기도 그렇다)은 봐준다. 위치가 같고 진한 차이(>128)가 없으면 같은 그림.
    hard = hard_diff(last, still) + hard_diff(still, last)
    if wordfx:   # 단어 강조를 켜면 프레임이 장면 끝까지 가고 끝에선 마지막 단어가 강조돼 있다 — 정지 그림(첫 단어)과는 ⑥으로만 잰다
        pass
    else:
      need(near(last.getbbox(), still.getbbox()) and hard == 0, f"③ [{key}] 끝 프레임 = 정지 레이어 (영역 {last.getbbox()} / {still.getbbox()}, 진한 차이 {hard})")
    if plain is not None:
        hard = hard_diff(still, plain) + hard_diff(plain, still)
        need(near(still.getbbox(), plain.getbbox()) and hard == 0, f"⑥ [{key}] 정지 그림 = 효과 없는 자막 (영역 {still.getbbox()} / {plain.getbbox()}, 진한 차이 {hard})")
    if wordfx:   # ⑦ 캡컷은 단어마다 정지 그림 한 장 — 등장 도중이 아니라 '다 나온 자막 + 그 단어 강조'여야 한다(효과 없는 자막의 같은 단어 그림과 같다)
        spans = lay.get("wordSpans") or []
        ok = len(spans) == len(plain_spans) and len(spans) > 0
        bad = []
        for sp, ps in zip(spans, plain_spans):
            a_ = crop(d / sp["file"]); b_ = crop(out / "_none" / ps["file"])
            h = hard_diff(a_, b_) + hard_diff(b_, a_)
            if h or not near(a_.getbbox(), b_.getbbox()): bad.append((sp["word"], h))
        need(ok and not bad, f"⑦ [{key}] 캡컷 단어 그림 {len(spans)}장 = 다 나온 자막 (어긋남 {bad})")
    if baseline:
        b = baseline / key
        bl = json.loads((b / "scene-style-layers.json").read_text(encoding="utf-8"))[1].get("animation")
        same = bl and bl["count"] == anim["count"] and all(
            hashlib.md5((b / bl["pattern"].replace("%04d", str(f).zfill(4))).read_bytes()).digest() ==
            hashlib.md5(frames[f].read_bytes()).digest() for f in range(anim["count"]))
        need(bool(same), f"④ [{key}] 기준과 프레임 {anim['count']}장 픽셀 동일")
    # 시트: 0,2,4,… 최대 12장
    pick = frames[::max(1, len(frames) // 12)][:12]
    sw, sh = 270, 480
    sheet = Image.new("RGB", (sw * len(pick), sh), (40, 60, 90))
    for i, p in enumerate(pick):
        im = Image.open(p).convert("RGBA").resize((sw, sh))
        bgc = Image.new("RGBA", im.size, (40, 60, 90, 255)); bgc.alpha_composite(im)
        sheet.paste(bgc.convert("RGB"), (i * sw, 0))
    sheet.save(out / f"sheet_{key}.png")
    if compose:
        src = out / "src.mp4"
        if not src.exists():
            va._run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=1080x1920:d=6", "-r", "30", "-pix_fmt", "yuv420p", str(src)])
        final = d / "final.mp4"
        scene_style.compose(str(src), timeline, snap, str(final), d / "cw", HEAD)
        grab = lambda t, name: (va._run_ffmpeg(["ffmpeg", "-y", "-ss", str(t), "-i", str(final), "-frames:v", "1", str(d / name)]), Image.open(d / name).convert("RGB").crop((0, 400, 1080, 1700)))[1]
        early, late = grab(2.0 + 2 / 30, "early.png"), grab(3.5, "late.png")
        n = sum(1 for p in ImageChops.difference(early, late).get_flattened_data() if max(p) > 40)
        need(n > 500, f"⑤ [{key}] 완성 영상: 장면 시작 직후와 끝의 자막이 다르다(다른 점 {n})")
print("\n결과:", "전부 통과" if not fails else f"실패 {len(fails)}건")
sys.exit(1 if fails else 0)
