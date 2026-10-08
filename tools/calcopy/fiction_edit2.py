# -*- coding: utf-8 -*-
"""픽션 썰 편집 2판 — 썰풀다(Whispered Tales) 화면 규칙을 따른다(2026-10-08 실측 4편 94컷).
- 틀: 흰 바탕 · 위 14% 제목 2줄(검정+분홍, 끝까지 고정) · 14~84% 영상(가로 꽉 채움) · 자막은 영상 안 2/3 높이
- 구절 하나 = 컷 하나(자막이 바뀌면 컷도 바뀐다), 하드 컷만
- 나레 = 흰 글자+검은 테두리, 줄마다 강조 구절 하나만 색
- 대사 = 기능 컷(또는 인물 컷) 위에 검은 둥근 상자+초록 글자+따옴표 — 카드 화면 없음
- 인물 줄(윗선 대사·이음 나레) = 담긴 영상 속 사람 얼굴 컷을 그 역할로 쓴다
사용: PYTHONUTF8=1 py tools/calcopy/fiction_edit2.py <결과.json> <번호> <컷 폴더> <출력.mp4> <배정.json>
배정.json = {"줄번호(0=제목)": ["seg_id", ...]} — 줄마다 쓸 컷(구절 수만큼 돌려 씀).
"""
import json, os, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from shopping_shorts.channelkit import providers
from tools.calcopy.fiction_tts import VOICES, ROLE, EMO

W, H = 1080, 1920
TOP, BOT = 270, 1613                      # 영상 자리 14%~84%
SUB_Y = 1270                              # 자막 가운데(2/3 높이)
FB = "C:/Windows/Fonts/malgunbd.ttf"
HL = ["미친", "완전 방수", "소름", "경악", "맨살", "이중보호", "박아버리더니", "뻔뻔하게", "식은땀"]
HL_COL = [(255, 214, 0), (255, 90, 170), (90, 220, 255), (255, 140, 0)]


def font(n):
    return ImageFont.truetype(FB, n)


def chunks(text, maxc=13):
    out, cur = [], ""
    for w in text.split():
        if cur and len((cur + " " + w).replace(" ", "")) > maxc:
            out.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    return out + ([cur] if cur else [])


def base(title):
    im = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(im)
    l1, l2 = (title.split("|") + [""])[:2]
    d.text((W // 2, 92), l1, font=font(78), fill=(0, 0, 0), anchor="mm")
    d.text((W // 2, 190), l2, font=font(78), fill=(230, 30, 120), anchor="mm")
    d.text((W - 30, 20), "[광고]", font=font(26), fill=(120, 120, 120), anchor="rt")
    return im


def sub_png(text, kind, hl_col, path):
    im = Image.new("RGBA", (W, 400), (0, 0, 0, 0)); d = ImageDraw.Draw(im); cy = 200
    if kind == "talk":
        f = font(56); t = text; tw = d.textlength(t, font=f)
        d.rounded_rectangle((W / 2 - tw / 2 - 34, cy - 50, W / 2 + tw / 2 + 34, cy + 50), 22, fill=(0, 0, 0, 235))
        d.text((W // 2, cy), t, font=f, fill=(40, 255, 100), anchor="mm")
    else:
        f = font(60) if not hl_col else font(70)
        d.text((W // 2, cy), text, font=f, fill=hl_col or (255, 255, 255), anchor="mm", stroke_width=7, stroke_fill=(0, 0, 0))
    im.save(path)


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                capture_output=True, text=True).stdout.strip())


def main():
    src, idx, clips, out, plan_f = sys.argv[1:6]
    r = json.load(open(src, encoding="utf-8"))[int(idx)]
    plan = json.load(open(plan_f, encoding="utf-8"))
    sc = r["script"]; title = plan.get("title2") or sc["title"]
    seq = [{"speaker": "나레", "text": sc["title"].replace("|", " ")}] + sc["lines"]
    synth = providers.typecast_synth(VOICES, tempo=1.15)
    tmp = tempfile.mkdtemp(prefix="fic2_"); bg = os.path.join(tmp, "bg.png"); base(title).save(bg)
    segs, auds = [], []; nhl = 0
    for i, L in enumerate(seq):
        a = os.path.join(tmp, "a%02d.mp3" % i); sp = L["speaker"]; emo = EMO.get(sp, (None, None))
        synth(L["text"], a, role=ROLE.get(sp, "NARR"), emotion=emo[0], intensity=emo[1])
        ad = dur(a); auds.append(a)
        talk = sp in ("윗선", "실무자")
        cs = chunks(L["text"]); tot = sum(len(c) for c in cs)
        if talk:
            cs[0] = "“" + cs[0]; cs[-1] = cs[-1] + "”"
        hl_i = next((k for k, c in enumerate(cs) if any(h in c for h in HL)), None) if not talk else None
        pool = plan[str(i)]
        for k, c in enumerate(cs):
            cd = ad * len(c.strip("“”")) / tot
            col = HL_COL[nhl % len(HL_COL)] if k == hl_i else None
            if col: nhl += 1
            sp_png = os.path.join(tmp, "s%02d_%d.png" % (i, k)); sub_png(c, "talk" if talk else "narr", col, sp_png)
            clip = os.path.join(clips, pool[k % len(pool)] + ".mp4"); o = os.path.join(tmp, "v%02d_%d.mp4" % (i, k))
            bh = BOT - TOP
            fc = ("[1:v]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,setsar=1[v];[0:v][v]overlay=0:%d[b];"
                  "[b][2:v]overlay=0:%d,format=yuv420p[o]" % (W, bh, W, bh, TOP, SUB_Y - 200))
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", bg, "-stream_loop", "-1", "-i", clip, "-loop", "1", "-i", sp_png,
                            "-filter_complex", fc, "-map", "[o]", "-t", "%.3f" % cd, "-r", "30", "-c:v", "libx264", "-crf", "20", o], check=True)
            segs.append(o)
        print(i, sp, "%.1f초" % ad, len(cs), "구절", pool)
    vl = os.path.join(tmp, "v.txt"); al = os.path.join(tmp, "a.txt")
    open(vl, "w", encoding="utf-8").write("".join("file '%s'\n" % s.replace("\\", "/") for s in segs))
    open(al, "w", encoding="utf-8").write("".join("file '%s'\n" % s.replace("\\", "/") for s in auds))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", vl, "-f", "concat", "-safe", "0", "-i", al,
                    "-c:v", "copy", "-c:a", "aac", "-shortest", out], check=True)
    print(out, "%.1f초" % dur(out), "컷", len(segs))


if __name__ == "__main__":
    main()
