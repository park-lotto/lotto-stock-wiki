"""자막팩 × 장면효과팩 합본 점검(관제 127·124) — 두 트랙을 합친 폴더에서 돌린다(장면 성격·어둡게 강조 배치는 장면효과팩 코드).

  (합본 폴더에서) py tools/caption_pack/check_combo_emph.py <출력폴더> <바탕영상|gradients> [팩,...]   ※ 바탕 영상에 글자가 없어야 한다

5장면(훅·문제·공개·고조(어둡게 강조)·끝)을 팩마다 완성 영상으로 만들고:
  ① 장면마다 등장 길이(enterMs) = 팩 칸(first·problem·reveal·emph·end) 효과의 계산 길이
  ② 고조 장면 자막이 영상 위 강조 배치로 그려졌다(가운데 큰 글자 — 레이어 잉크가 영상 칸 가운데에 있다)
  ③ 완성 mp4 에서 장면마다 시작 직후·1.5초 뒤 프레임을 시트로 남긴다(눈으로 본다)
"""
import json, math, pathlib, shutil, sys
ROOT = pathlib.Path.cwd(); sys.path.insert(0, str(ROOT))
from PIL import Image
from shopping_shorts import scene_style, video_assemble as va

out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
src_in = sys.argv[2]
keys = sys.argv[3].split(",") if len(sys.argv) > 3 else ["", "tension", "premium", "soft"]
text = (ROOT / "shopping_shorts/static/caption-motions.js").read_text(encoding="utf-8")
PACKS = json.loads(text.split("/*PACKS*/")[1]); MOTIONS = json.loads(text.split("/*JSON*/")[1])
fails = []
def need(ok, msg):
    print(("  통과  " if ok else "★ 실패  ") + msg)
    if not ok: fails.append(msg)

CAPS = [("훅", "주부들도 감탄한 천재 아이디어"), ("문제", "옷 태그 달기 너무 귀찮죠"), ("공개", "이거 하나면 끝나요"),
        ("고조1", "무게도 버티고 설치도"), ("마무리", "지금 바로 확인해 보세요")]
SLOT = {1: "problem", 2: "reveal", 3: "emph", 4: "end"}
DUR = 2
tts = out / "v.wav"
va._run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100", "-t", str(DUR), str(tts)])
src = out / "src.mp4"   # 바탕 영상은 장면 전체보다 길어야 한다(짧으면 마지막 장면 합성이 멈춘다 — 10-05 시험 설정 실수)
# ★바탕에 글자가 박힌 영상을 쓰면 우리 자막과 겹쳐 판단이 안 된다(10-05 실수) — 'gradients' 는 글자 없는 움직이는 바탕
if src_in == "gradients":
    va._run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i", f"gradients=s=1080x1920:d={DUR * len(CAPS) + 1}:c0=0x2a6f97:c1=0xf4a259:c2=0x5b8e7d:speed=0.02", "-r", "30", "-pix_fmt", "yuv420p", str(src)])
else:
    va._run_ffmpeg(["ffmpeg", "-y", "-stream_loop", "-1", "-i", src_in, "-t", str(DUR * len(CAPS) + 1), "-vf", "scale=1080:1920,setsar=1",
                    "-r", "30", "-an", "-pix_fmt", "yuv420p", str(src)])
tl = [{"beat_idx": i, "t0": i * DUR, "dur": DUR, "narration": c, "caption_lines": [c], "tts_path": str(tts), "target_seconds": DUR,
       "role": r, "primary": {"video_id": "s0", "start": i * DUR, "end": (i + 1) * DUR}} for i, (r, c) in enumerate(CAPS)]
TEXT = {"channel": "숏템메이커", "hook1": "주부들도 감탄한", "hook2": "천재 아이디어", "bodyTitle": "주부들도 감탄한 천재 아이디어?"}

def expect_ms(motion, caption):
    m = MOTIONS[motion]; unit = m.get("unit")
    n = len(caption.split()) if unit == "word" else len(caption.replace(" ", "")) if unit == "char" else 1
    step = min(m.get("stagger", 0), m.get("spread", math.inf) / (n - 1)) if n > 1 else 0
    return math.ceil((n - 1) * step + m["ms"])

rows = []
for key in keys:
    d = out / (key or "none"); shutil.rmtree(d, ignore_errors=True); d.mkdir()
    snap = scene_style.validate_snapshot({"version": 1, "mode": "story", "plainCaption": 2, "presetId": "plain", "sceneIndex": 0, "frameKind": "hook",
                                          "text": TEXT, "effects": {"3": {"dim": {"level": .32, "sec": 0}}}, **({"captionPack": key} if key else {})})
    final = d / "final.mp4"
    scene_style.compose(str(src), tl, snap, str(final), d / "cw", {"text": "x"})
    L = json.loads((d / "cw" / "scene-style-layers.json").read_text(encoding="utf-8"))
    for i, slot in SLOT.items():
        motion = PACKS[key]["slots"][slot] if key else (json.loads(text.split("root.CAPTION_EMPH_DEFAULT = ")[1].split(";")[0])["motion"] if slot == "emph" else None)
        if motion:
            want = expect_ms(motion, CAPS[i][1])
            need(L[i].get("enterMs") == want, f"① [{key or '팩 없음'}] {i}장({slot}) 등장 {L[i].get('enterMs')}ms = {motion} 계산 {want}ms")
    lay = Image.open(d / "cw" / L[3]["file"]).convert("RGBA").split()[3]
    mid = lay.crop((0, 700, 1080, 1500)).getbbox()          # 영상 칸 가운데(제목·자막 띠는 위쪽 — 레이어에 같이 있어 전체 영역으로 재면 안 된다)
    norm = Image.open(d / "cw" / L[2]["file"]).convert("RGBA").split()[3].crop((0, 700, 1080, 1500)).getbbox()
    need(bool(mid) and not norm, f"② [{key or '팩 없음'}] 고조 장면만 자막이 영상 가운데에 그려졌다 (고조 {mid} / 일반 장면 {norm})")
    tiles = []
    for i in range(1, 5):
        for dt in (0.12, 1.5):
            f = d / f"f{i}_{dt}.png"; va._run_ffmpeg(["ffmpeg", "-y", "-ss", str(i * DUR + dt), "-i", str(final), "-frames:v", "1", str(f)])
            tiles.append(Image.open(f).convert("RGB").resize((216, 384)))
    row = Image.new("RGB", (216 * 8, 384)); [row.paste(x, (k * 216, 0)) for k, x in enumerate(tiles)]; rows.append(row)
sheet = Image.new("RGB", (216 * 8, 384 * len(rows)))
for k, r in enumerate(rows): sheet.paste(r, (0, k * 384))
sheet.save(out / "sheet.png")
print("\n결과:", "전부 통과" if not fails else f"실패 {len(fails)}건")
sys.exit(1 if fails else 0)
