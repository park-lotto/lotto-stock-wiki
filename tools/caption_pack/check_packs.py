"""자막팩 자동 배치 점검(관제 127 3단계) — 렌더러가 찍은 프레임으로 잰다.

  py tools/caption_pack/check_packs.py <출력폴더> [팩키,...]

장면 5개(훅·첫 본문·일반·가격·마지막)로 팩을 렌더하고, 장면마다 '그 칸의 효과를 직접 고른 렌더'와 프레임을 픽셀 대조한다.
  ① 칸 판정: 1장 첫 장면 · 2장 일반 줄 · 3장 가격·숫자 · 4장 마지막 장면 (훅 0장은 본문 등장 없음)
  ② 팩 렌더의 그 장면 등장 프레임 = 그 효과 하나만 고른 렌더의 같은 장면 프레임(장수·픽셀)
  ③ 서버 검증: 팩 값 저장 통과, 모르는 팩 거절
"""
import hashlib, json, pathlib, shutil, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from shopping_shorts import scene_style, video_assemble as va

out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
text = (ROOT / "shopping_shorts/static/caption-motions.js").read_text(encoding="utf-8")
PACKS = json.loads(text.split("/*PACKS*/")[1])
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

def render(extra, d):
    shutil.rmtree(d, ignore_errors=True)
    return scene_style.render_layers(timeline, scene_style.validate_snapshot({**BASE, **extra}), d, {"text": "x"}, "cpqa")

def frames(d, lay):
    a = lay.get("animation")
    if not a: return []
    return [hashlib.md5((d / a["pattern"].replace("%04d", str(f).zfill(4))).read_bytes()).hexdigest() for f in range(a["count"])]

single = {}
for key in keys:
    pack = PACKS[key]
    d = out / ("pack_" + key)
    layers = render({"captionPack": key}, d)
    for i, slot in SLOT_OF.items():
        motion = pack["slots"][slot]
        if motion not in single:
            sd = out / ("one_" + motion)
            single[motion] = (sd, render({"bodyCaptionMotion": motion}, sd))
        sd, sl = single[motion]
        a, b = frames(d, layers[i]), frames(sd, sl[i])
        need(bool(a) and a == b, f"② [{key}] {i}장({slot}) = {motion} 직접 고른 렌더와 프레임 {len(a)}/{len(b)}장 동일")
try:
    scene_style.validate_snapshot({**BASE, "captionPack": "nope"}); need(False, "③ 모르는 팩을 거절해야 한다")
except ValueError:
    need(True, "③ 모르는 팩은 서버가 거절")
print("\n결과:", "전부 통과" if not fails else f"실패 {len(fails)}건")
sys.exit(1 if fails else 0)
