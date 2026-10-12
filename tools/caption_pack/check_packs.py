"""자막 스타일 + 등장 효과팩 점검(관제 127·144) — 렌더러가 찍은 레이어로 잰다.

  py tools/caption_pack/check_packs.py <출력폴더> [효과팩번호,...] [--style=<스타일키>]

장면 6개(훅·첫 본문·일반·일반·가격·마지막)로 효과팩마다 렌더해서:
  ② 장면별 등장 길이(enterMs) = 편집기 장면 계획(motionPlan)의 효과로 계산한 길이 — 편집기·렌더가 같은 효과를 쓴다
     + 계획 안에 같은 등장 연속 없음
  ⑦ 캡컷: 등장 도중·덜 그려진 때에 걸린 단어 그림은 전부 따로 다시 찍었다(scene-style-capcut-*)
  ⑧ 시트 sheet_<팩>.png — 장면 1~4 등장 중간·끝·캡컷 첫 단어 그림(눈으로 본다)
  ③ 서버 검증: 모르는 효과팩 번호 거절
스타일(--style)을 주면 그 스타일의 단어 강조까지 켠다(편집기가 스타일 카드를 누를 때 저장하는 그대로).
"""
import math, pathlib, re, shutil, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools/caption_pack"))
from PIL import Image
from shopping_shorts import scene_style, video_assemble as va
import _plan

args = sys.argv[1:]
out = pathlib.Path(args.pop(0)).resolve(); out.mkdir(parents=True, exist_ok=True)
style = next((a.split("=", 1)[1] for a in args if a.startswith("--style=")), "tension")
args = [a for a in args if not a.startswith("--style=")]
keys = [int(x) for x in args[0].split(",")] if args else [1, 7, 14, 20]
fails = []
def need(ok, msg):
    print(("  통과  " if ok else "★ 실패  ") + msg)
    if not ok: fails.append(msg)

tts = out / "v.wav"
if not tts.exists():
    va._run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100", "-t", "2", str(tts)])
CAPS = ["주부들도 감탄한 천재 아이디어", "겉은 바삭 속은 촉촉", "한 입 먹으면 멈출 수 없어요", "손에 딱 맞아요", "단돈 9,900원에 끝", "지금 바로 확인해 보세요"]
timeline = [{"beat_idx": i, "t0": i * 2, "dur": 2, "narration": c, "caption_lines": [c], "tts_path": str(tts), "target_seconds": 2,
             "role": "hook" if i == 0 else "body", "primary": {"video_id": "s0", "start": i * 2, "end": i * 2 + 2}}
            for i, c in enumerate(CAPS)]
TEXT = {"channel": "숏템메이커", "hook1": "주부들도 감탄한", "hook2": "천재 아이디어", "bodyTitle": "주부들도 감탄한 천재 아이디어?"}
wf = _plan.STYLES[style]["wordFx"]
BASE = {"version": 1, "mode": "story", "plainCaption": 2, "presetId": "plain", "sceneIndex": 0, "frameKind": "hook", "text": TEXT,
        "captionPack": style, "wordFx": {"style": wf.get("style", ""), "color": wf.get("color", ""), "grow": wf.get("grow", "")}}
snaps = [scene_style.validate_snapshot({**BASE, "motionPack": str(k)}) for k in keys]
plans = _plan.plans(scene_style.context_for(timeline, {"text": "x"}, snaps[0], None), snaps)

for k, snap, plan in zip(keys, snaps, plans):
    live = [x for x in plan if x]
    need(not any(a == b for a, b in zip(live, live[1:])), f"② [{k}번] 장면 계획 {plan} — 같은 등장 연속 없음")
    d = out / f"pack_{k}"; shutil.rmtree(d, ignore_errors=True)
    layers = scene_style.render_layers(timeline, snap, d, {"text": "x"}, "cpqa")
    for i in range(1, len(CAPS)):
        want = _plan.expect_ms(plan[i], CAPS[i]); got = layers[i].get("enterMs")
        need(got == want, f"② [{k}번] {i}장 등장 {got}ms = 편집기 계획 {plan[i]} 계산 {want}ms")
    for i in range(1, len(CAPS)):
        lay = layers[i]; enter_frames = math.ceil((lay.get("enterMs") or 0) / 1000 * 30) + 1
        spans = lay.get("wordSpans") or []
        early = [sp for sp in spans if int(re.search(r"(\d{4})\.png$", sp["file"]).group(1)) < enter_frames - 1 or "capcut" in sp["file"]]
        bad = [sp["file"] for sp in early if "capcut" not in sp["file"]]
        need(bool(spans) and not bad, f"⑦ [{k}번] {i}장 캡컷 단어 그림 {len(spans)}장 중 등장 도중 것 {len(early)}장은 다시 찍음 (안 찍은 것 {bad})")
    tiles = []
    for i in range(1, 5):
        lay = layers[i]; a = lay["animation"]; n = a["count"]; e = lay.get("enterMs") or 0
        fr = lambda f: Image.open(d / a["pattern"].replace("%04d", str(min(n - 1, f)).zfill(4))).convert("RGBA")
        tiles += [fr(math.ceil(e / 1000 * 30 * .4)), fr(math.ceil(e / 1000 * 30) + 2), Image.open(d / lay["wordSpans"][0]["file"]).convert("RGBA")]
    sheet = Image.new("RGBA", (900 * 3, 230 * 4), (40, 60, 90, 255))
    for j, t in enumerate(tiles):
        sheet.alpha_composite(t.crop((90, 330, 990, 560)), ((j % 3) * 900, (j // 3) * 230))
    sheet.convert("RGB").resize((1350, 460)).save(out / f"sheet_{k}.png")
try:
    scene_style.validate_snapshot({**BASE, "motionPack": "99"}); need(False, "③ 모르는 효과팩 번호를 거절해야 한다")
except ValueError:
    need(True, "③ 모르는 효과팩 번호는 서버가 거절")
print("\n결과:", "전부 통과" if not fails else f"실패 {len(fails)}건")
sys.exit(1 if fails else 0)
