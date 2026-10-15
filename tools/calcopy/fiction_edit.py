# -*- coding: utf-8 -*-
"""픽션 썰 시험 편집 — 결과 json 한 편 + 담긴 영상 컷(서버에서 잘라 온 mp4) → 세로 영상 1편.
기능 줄 = 그 기능 컷 / 설정·제목 줄 = 제품 소개 컷 / 윗선·실무자 대사와 이음 나레 = 대사 카드.
사용: PYTHONUTF8=1 py tools/calcopy/fiction_edit.py <결과.json> <번호(0부터)> <컷 폴더> <출력.mp4>
컷 폴더 = <seg_id>.mp4 들 (서버 /tmp/fic_clips 를 scp 로 받은 것).
"""
import json, os, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from shopping_shorts.channelkit import providers
from tools.calcopy.fiction_tts import VOICES, ROLE, EMO

W, H = 1080, 1920
BOX = (20, 470, 1060, 1354)          # 방구석 그림 상자 1040×884
FONT = "C:/Windows/Fonts/malgunbd.ttf"
INTRO = ["6mEa6Y3vzww-10", "6mEa6Y3vzww-3", "6mEa6Y3vzww-5", "6mEa6Y3vzww-9"]
WHO = {"윗선": ("사장님", (220, 60, 60)), "실무자": ("개발팀", (40, 110, 220))}


def font(n):
    return ImageFont.truetype(FONT, n)


def wrap(d, text, f, maxw):
    lines, cur = [], ""
    for w in text.split(" "):
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw:
            cur = t
        else:
            lines.append(cur); cur = w
    return lines + [cur] if cur else lines


def frame(title, sub, card=None):
    im = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(im)
    y = 200
    for i, ln in enumerate(wrap(d, title, font(66), 980)[:2]):
        d.text((W // 2, y + i * 86), ln, font=font(66), fill=(0, 0, 0) if i == 0 else (230, 40, 40), anchor="mm")
    d.rectangle(BOX, fill=(20, 20, 24))
    if card:
        who, col = WHO.get(card[0], ("", (90, 90, 90)))
        cx, cy = W // 2, BOX[1] + 250
        d.ellipse((cx - 110, cy - 110, cx + 110, cy + 110), fill=col)
        d.text((cx, cy), who, font=font(54), fill="white", anchor="mm")
        f = font(50); ls = wrap(d, card[1], f, 880) if card[1] else []
        top = BOX[1] + 430
        if ls: d.rounded_rectangle((70, top - 30, 1010, top + len(ls) * 70 + 20), 30, fill="white")
        for i, ln in enumerate(ls):
            d.text((W // 2, top + i * 70 + 10), ln, font=f, fill=(20, 20, 20), anchor="mt")
    f = font(54); ls = wrap(d, sub, f, 1000)
    for i, ln in enumerate(ls[:3]):
        d.text((W // 2, 1440 + i * 74), ln, font=f, fill=(0, 0, 0), anchor="mt", stroke_width=0)
    return im


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                capture_output=True, text=True).stdout.strip())


def main():
    src, idx, clips, out = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
    r = json.load(open(src, encoding="utf-8"))[idx]
    sc = r["script"]; cuts = {f["id"]: f.get("cuts") or [] for f in r["feats"]}
    seq = [{"speaker": "나레", "text": sc["title"], "feat": "", "beat": "제목"}] + sc["lines"]
    synth = providers.typecast_synth(VOICES, tempo=1.15)
    tmp = tempfile.mkdtemp(prefix="fic_"); parts = []; last_card = None; used = set()
    for i, L in enumerate(seq):
        a = os.path.join(tmp, "%02d.mp3" % i); sp = L["speaker"]; emo = EMO.get(sp, (None, None))
        synth(L["text"], a, role=ROLE.get(sp, "NARR"), emotion=emo[0], intensity=emo[1])
        d_ = dur(a) + 0.1
        card = None; pool = []
        if L["feat"]:                          # 기능 줄은 화자가 누구든 그 기능 컷(대답 대사 포함)
            if sp in WHO: last_card = sp
            pool = [c for c in cuts.get(L["feat"], []) if os.path.exists(os.path.join(clips, c + ".mp4"))]
        elif L["beat"] in ("제목", "설정"):
            pool = [c for c in INTRO if c not in used][:2]
        elif sp in WHO:
            card = (sp, L["text"]); last_card = sp
        else:                                  # 이음 나레 — 다음 대사 화자 카드로 미리 넘김(없으면 직전 카드)
            nxt = next((x["speaker"] for x in seq[i + 1:] if x["speaker"] in WHO), last_card)
            card = (nxt, "") if nxt else None
        used.update(pool)
        png = os.path.join(tmp, "%02d.png" % i)
        frame(sc["title"], "" if card and card[1] else (("[%s] " % WHO[sp][0]) if sp in WHO else "") + L["text"], card).save(png)
        seg = os.path.join(tmp, "seg%02d.mp4" % i)
        if pool:
            lst = os.path.join(tmp, "l%02d.txt" % i)
            files = [os.path.join(clips, c + ".mp4").replace("\\", "/") for c in pool]
            open(lst, "w", encoding="utf-8").write("".join("file '%s'\n" % f for f in files * 4))
            bw, bh = BOX[2] - BOX[0], BOX[3] - BOX[1]
            fc = ("[1:v]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,setsar=1[v];"
                  "[0:v][v]overlay=%d:%d,format=yuv420p[o]" % (bw, bh, bw, bh, BOX[0], BOX[1]))
            cmd = ["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", png, "-f", "concat", "-safe", "0", "-i", lst, "-i", a,
                   "-filter_complex", fc, "-map", "[o]", "-map", "2:a", "-t", "%.2f" % d_, "-r", "30",
                   "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-ar", "44100", "-ac", "2", seg]
        else:
            cmd = ["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", png, "-i", a, "-t", "%.2f" % d_, "-r", "30",
                   "-vf", "format=yuv420p", "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-ar", "44100", "-ac", "2", seg]
        subprocess.run(cmd, check=True); parts.append(seg)
        print(i, sp, L["beat"], "%.1f초" % d_, ("컷 " + ",".join(pool)) if pool else ("카드 " + card[0] if card else "-"))
    lst = os.path.join(tmp, "all.txt")
    open(lst, "w", encoding="utf-8").write("".join("file '%s'\n" % p.replace("\\", "/") for p in parts))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out], check=True)
    print(out, "%.1f초" % dur(out))


if __name__ == "__main__":
    main()
