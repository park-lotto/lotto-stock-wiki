# 고객이 고른 채널 설정 → 작업 폴더 config.json
# 사용: python -X utf8 apply_style.py <설정.json>
# 설정 칸: channel_name, style(styles 폴더 이름), font(gmarket|pretendard|blackhan), photo_motion(pan|zoom),
#          logo_side(right|left), voice, tempo, outro_left, outro_right
import json, os, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.abspath(os.environ.get("LONGFORM_WORK") or os.getcwd())
FONTS = {"gmarket": "GmarketSansBold.otf", "pretendard": "Pretendard-Black.otf", "blackhan": "BlackHanSans-Regular.ttf"}
CHOICES = {"photo_motion": ("pan", "zoom"), "logo_side": ("right", "left"), "font": tuple(FONTS)}

pick = json.load(open(sys.argv[1], encoding="utf-8"))
style = pick.get("style", "mint")
path = os.path.join(HERE, "styles", style + ".json")
if not os.path.exists(path): sys.exit(f"없는 스타일: {style}")
for k, ok in CHOICES.items():
    if k in pick and pick[k] not in ok: sys.exit(f"{k} 는 {ok} 중 하나입니다")
if not str(pick.get("channel_name", "")).strip(): sys.exit("채널명을 넣어 주세요")
cfg = json.load(open(path, encoding="utf-8"))
cfg.update({k: pick[k] for k in ("channel_name", "photo_motion", "logo_side", "voice", "tempo", "outro_left", "outro_right") if k in pick})
if "font" in pick: cfg["font_main"] = FONTS[pick["font"]]
cfg["output_name"] = pick.get("output_name") or "완성본.mp4"
out = os.path.join(WORK, "config.json")
base = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
colors = dict(base["colors"]); colors.update(cfg.get("colors", {})); cfg["colors"] = colors
json.dump(cfg, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("저장:", out)
