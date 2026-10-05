"""자막팩 점검(관제 127) — 렌더러가 찍은 레이어로 잰다.

  py tools/caption_pack/check_packs.py <출력폴더> [팩키,...]

장면 5개(훅·첫 본문·일반·가격·마지막)로 팩마다 렌더해서:
  ② 칸 판정: 1장 first · 2장 body · 3장 price · 4장 end 의 등장 길이(enterMs)가 그 칸 효과의 계산 길이와 같다
  ⑦ 캡컷: 등장 도중·덜 그려진 때에 걸린 단어 그림은 전부 따로 다시 찍었다(scene-style-capcut-*)
  ⑧ 모양: 팩 글꼴·상자·강조가 실제로 그려졌다 — 장면 시트 sheet_<팩>.png 를 남긴다(눈으로 본다)
  ③ 서버 검증: 모르는 팩 거절
"""
import json, math, pathlib, re, shutil, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from PIL import Image
from shopping_shorts import scene_style, video_assemble as va

out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
text = (ROOT / "shopping_shorts/static/caption-motions.js").read_text(encoding="utf-8")
PACKS = json.loads(text.split("/*PACKS*/")[1]); MOTIONS = json.loads(text.split("/*JSON*/")[1])
keys = sys.argv[2].split(",") if len(sys.argv) > 2 else list(PACKS)
fails = []
def need(ok, msg):
    print(("  통과  " if ok else "★ 실패  ") + msg)
    if not ok: fails.append(msg)

tts = out / "v.wav"
if not tts.exists():
    va._run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100", "-t", "2", str(tts)])
CAPS = ["주부들도 감탄한 천재 아이디어", "겉은 바삭 속은 촉촉", "한 입 먹으면 멈출 수 없어요", "단돈 9,900원에 끝", "지금 바로 확인해 보세요"]
SLOT_OF = {1: "first", 2: "body", 3: "price", 4: "end"}
timeline = [{"beat_idx": i, "t0": i * 2, "dur": 2, "narration": c, "caption_lines": [c], "tts_path": str(tts), "target_seconds": 2,
             "role": "hook" if i == 0 else "body", "primary": {"video_id": "s0", "start": i * 2, "end": i * 2 + 2}}
            for i, c in enumerate(CAPS)]
TEXT = {"channel": "숏템메이커", "hook1": "주부들도 감탄한", "hook2": "천재 아이디어", "bodyTitle": "주부들도 감탄한 천재 아이디어?"}
BASE = {"version": 1, "mode": "story", "plainCaption": 2, "presetId": "plain", "sceneIndex": 0, "frameKind": "hook", "text": TEXT}

def expect_ms(motion, caption):
    """편집기 runCaptionEnter 와 같은 셈: 단위 수 → 간격(stagger, spread 상한) → 마지막 단위 시작 + 한 단위 길이."""
    m = MOTIONS[motion]; unit = m.get("unit")
    n = len(caption.split()) if unit == "word" else len(caption.replace(" ", "")) if unit == "char" else 1
    step = min(m.get("stagger", 0), m.get("spread", math.inf) / (n - 1)) if n > 1 else 0
    return math.ceil((n - 1) * step + m["ms"])

for key in keys:
    pack = PACKS[key]; d = out / ("pack_" + key); shutil.rmtree(d, ignore_errors=True)
    # 편집기가 저장하는 그대로 — 팩을 누르면 단어 강조(wordFx)도 같이 저장된다(팩 값만 넣으면 ⑦이 아무것도 안 잰다: 10-05 실측)
    wf = {"style": pack["wordFx"].get("style", ""), "color": pack["wordFx"].get("color", ""), "grow": pack["wordFx"].get("grow", "")}
    layers = scene_style.render_layers(timeline, scene_style.validate_snapshot({**BASE, "captionPack": key, **({"wordFx": wf} if wf["style"] else {})}), d, {"text": "x"}, "cpqa")
    for i, slot in SLOT_OF.items():
        motion = pack["slots"][slot]; want = expect_ms(motion, CAPS[i]); got = layers[i].get("enterMs")
        need(got == want, f"② [{key}] {i}장({slot}) 등장 {got}ms = {motion} 계산 {want}ms")
    for i in SLOT_OF:
        lay = layers[i]; enter_frames = math.ceil((lay.get("enterMs") or 0) / 1000 * 30) + 1
        early = [sp for sp in lay.get("wordSpans") or [] if int(re.search(r"(\d{4})\.png$", sp["file"]).group(1)) < enter_frames - 1 or "capcut" in sp["file"]]
        bad = [sp["file"] for sp in early if "capcut" not in sp["file"]]
        need(bool(lay.get("wordSpans")) or not pack["wordFx"].get("style"), f"⑦ [{key}] {i}장 단어 강조가 켜져 캡컷 단어 그림이 있다")
        if lay.get("wordSpans"):
            need(not bad, f"⑦ [{key}] {i}장 캡컷 단어 그림 {len(lay['wordSpans'])}장 중 등장 도중 것 {len(early)}장은 다시 찍음 (안 찍은 것 {bad})")
    # ⑧ 시트: 장면 1~4 — 등장 중간 / 등장 끝 / 캡컷 첫 단어 그림
    tiles = []
    for i in SLOT_OF:
        lay = layers[i]; a = lay["animation"]; n = a["count"]
        mid = math.ceil((lay.get("enterMs") or 0) / 1000 * 30 * .4)
        fr = lambda f: Image.open(d / a["pattern"].replace("%04d", str(min(n - 1, f)).zfill(4))).convert("RGBA")
        cap = Image.open(d / lay["wordSpans"][0]["file"]).convert("RGBA") if lay.get("wordSpans") else Image.open(d / lay["file"]).convert("RGBA")
        tiles += [fr(mid), fr(math.ceil((lay.get("enterMs") or 0) / 1000 * 30) + 2), cap]
    sheet = Image.new("RGBA", (900 * 3, 230 * 4), (40, 60, 90, 255))
    for k, t in enumerate(tiles):
        sheet.alpha_composite(t.crop((90, 330, 990, 560)), ((k % 3) * 900, (k // 3) * 230))
    sheet.convert("RGB").resize((1350, 460)).save(out / f"sheet_{key}.png")
try:
    scene_style.validate_snapshot({**BASE, "captionPack": "nope"}); need(False, "③ 모르는 팩을 거절해야 한다")
except ValueError:
    need(True, "③ 모르는 팩은 서버가 거절")
print("\n결과:", "전부 통과" if not fails else f"실패 {len(fails)}건")
sys.exit(1 if fails else 0)
