"""가편집 v2 — 문장(비트)마다 화면을 따로 정한다(Jev: 원인 '장면=그림 하나' 0.91, 해결 '문장 비트' 0.87).
비트 시각 = 음성 길이를 문장 글자 수로 나눈 것(자막과 같은 계산 — 한 곳: beat_times).
비트 종류: one(쇼츠 한 편 크게) · tiles(여러 칸) · full(16:9 영상) · img(정지 그림) · sk(손그림 쪽 — 같은 쪽이면 이어 그림, 문장마다 새 요소).
사용: py build2.py seg [장면id...] / py build2.py final
"""
import math, re, shutil, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import build as B
from build import jl, jrect, jcirc, arrow, tx, person, monitor, claude_char, stamp, INK, RED, YEL, ORANGE, BLUE, PEN, GAEGU, JA, VW, VH, FPS, R

W = B.W
TEXT = {s["id"]: s["text"] for s in B.SCENES}


def big(s, y=540, c=INK, size=150, font=GAEGU):
    return lambda d: tx(d, (960, y), s, size, c, font, "mm")


def xmark(cx, cy, r=120):
    return lambda d: (jl(d, (cx - r, cy - r), (cx + r, cy + r), RED, 12), jl(d, (cx + r, cy - r), (cx - r, cy + r), RED, 12))


def check(x, y, s=1.0, c=RED):
    return lambda d: (jl(d, (x, y), (x + 30 * s, y + 30 * s), c, 9), jl(d, (x + 30 * s, y + 30 * s), (x + 80 * s, y - 40 * s), c, 9))


def hlbox(x0, y0, x1, y1):
    return lambda d: d.rectangle((x0, y0, x1, y1), fill=YEL + (120,))


def scissors(cx, cy):
    return lambda d: (jcirc(d, cx - 40, cy + 60, 28), jcirc(d, cx + 40, cy + 60, 28), jl(d, (cx - 25, cy + 38), (cx + 60, cy - 90)), jl(d, (cx + 25, cy + 38), (cx - 60, cy - 90)))


def mic(cx, cy):
    return lambda d: (d.rounded_rectangle((cx - 40, cy - 110, cx + 40, cy + 20), 40, outline=INK, width=6), jcirc(d, cx, cy, 70, INK, 5, 0, 180), jl(d, (cx, cy + 70), (cx, cy + 120)), jl(d, (cx - 50, cy + 120), (cx + 50, cy + 120)))


def subs_icon(cx, cy):
    return lambda d: (jrect(d, cx - 110, cy - 90, cx + 110, cy + 90), [d.rounded_rectangle((cx - 80, cy + 20 + k * 30 - 10, cx + 80 - k * 40, cy + 20 + k * 30 + 10), 6, fill=(60, 60, 60)) for k in range(2)])


def clwin(x0, y0, x1, y1, P=18):
    return lambda d: (jrect(d, x0, y0, x1, y1), jl(d, (x0, y0 + 60), (x1, y0 + 60)), claude_char(d, (x0 + x1) // 2, (y0 + y1) // 2 + 40, P))


# 손그림 쪽(page): 요소 이름 → 그리는 함수
PAGES = {
 "member": {
   "person": lambda d: person(d, 330, 560, 1.4), "label": lambda d: tx(d, (330, 760), "50대 회원", 72, INK, PEN, "mm"),
   "email": lambda d: (tx(d, (330, 850), "컴퓨터 = 이메일만", 60, BLUE, PEN, "mm"), hlbox(150, 820, 510, 880)(d)),
   "r1": lambda d: (jrect(d, 640, 220, 980, 420), tx(d, (690, 370), "강의 1   ₩", 60, INK, PEN, "lm"), d.rectangle((830, 348, 950, 392), fill=INK)),
   "r2": lambda d: (jrect(d, 640, 470, 980, 670), tx(d, (690, 620), "강의 2   ₩", 60, INK, PEN, "lm"), d.rectangle((830, 598, 950, 642), fill=INK)),
   "won": lambda d: tx(d, (810, 760), "수백만 원 x 2", 80, RED, GAEGU, "mm"),
   "mon": lambda d: (monitor(d, 1130, 220, 1700, 560), [jl(d, (1170, 300 + k * 50), (1170 + 120 + k * 70 % 300, 300 + k * 50), (160, 160, 160), 10) for k in range(5)]),
   "hand": lambda d: tx(d, (1415, 700), "결국 손편집 강의", 74, INK, PEN, "mm"),
 },
 "work": {
   "a": lambda d: (scissors(380, 460)(d), tx(d, (380, 700), "장면 자르고", 80, INK, PEN, "mm")),
   "b": lambda d: (subs_icon(960, 460)(d), tx(d, (960, 700), "자막 하나하나", 80, INK, PEN, "mm")),
   "c": lambda d: (mic(1540, 440)(d), tx(d, (1540, 700), "목소리 맞추고", 80, INK, PEN, "mm")),
 },
 "months": {
   "cal": lambda d: (jrect(d, 560, 180, 1360, 760), jl(d, (560, 280), (1360, 280)), [jl(d, (560 + k * 114, 280), (560 + k * 114, 760), INK, 3) for k in range(1, 7)], [jl(d, (560, 280 + k * 96), (1360, 280 + k * 96), INK, 3) for k in range(1, 5)], tx(d, (960, 230), "몇 달 뒤", 70, INK, PEN, "mm")),
   "zero": lambda d: tx(d, (960, 880), "올린 영상 ... 거의 0", 96, RED, GAEGU, "mm"),
 },
 "lazy": {
   "q": big("게을러서?", 330, INK, 170),
   "no": lambda d: (xmark(960, 330, 150)(d), tx(d, (1300, 330), "아닙니다", 90, RED, GAEGU, "lm")),
   "honest": big("솔직해집시다", 610, BLUE, 120),
   "era": lambda d: (hlbox(300, 790, 1620, 900)(d), tx(d, (960, 845), "이제 그런 시대가 아니잖아요", 100, INK, GAEGU, "mm")),
 },
 "right": {
   "ok": lambda d: (tx(d, (960, 330), "그 강의들, 방향은 맞다", 120, INK, GAEGU, "mm"), check(330, 330, 1.4, BLUE)(d)),
   "quote": lambda d: (jrect(d, 360, 560, 1560, 780, RED, 7), tx(d, (960, 670), "\"잘된 채널을 벤치마킹하라\"", 96, RED, GAEGU, "mm")),
 },
 "bench": {
   "how": lambda d: tx(d, (960, 90), "방법", 90, INK, GAEGU, "mm"),
   "ch": lambda d: (jrect(d, 120, 330, 500, 750), tx(d, (310, 400), "터진 채널", 70, INK, PEN, "mm"), tx(d, (310, 530), "조회 300만", 62, RED, GAEGU, "mm"), tx(d, (310, 630), "조회 120만", 62, RED, GAEGU, "mm")),
   "mag": lambda d: (jcirc(d, 680, 520, 90), jl(d, (744, 584), (830, 670), INK, 12), arrow(d, (850, 540), (970, 540))),
   "k1": lambda d: (jrect(d, 1010, 180, 1380, 500), tx(d, (1195, 340), "첫 3초 후킹", 76, INK, PEN, "mm")),
   "k2": lambda d: (jrect(d, 1420, 180, 1790, 500), tx(d, (1605, 340), "이야기 흐름", 76, INK, PEN, "mm")),
   "k3": lambda d: (jrect(d, 1010, 560, 1380, 880), tx(d, (1195, 720), "장면 순서", 76, INK, PEN, "mm")),
   "k4": lambda d: (jrect(d, 1420, 560, 1790, 880), tx(d, (1605, 720), "자막 위치", 76, INK, PEN, "mm")),
   "rule": lambda d: (hlbox(130, 940, 1790, 1020)(d), tx(d, (960, 980), "방식은 따라, 영상과 말은 내 것", 78, BLUE, GAEGU, "mm")),
   "std": lambda d: stamp(d, 310, 900, "정석"),
 },
 "mis": {
   "q": lambda d: (tx(d, (960, 300), "흔한 오해", 150, RED, GAEGU, "mm"), tx(d, (960, 470), "\"벤치마킹 = 남의 영상 베끼기?\"", 90, INK, PEN, "mm")),
   "x": lambda d: (xmark(960, 470, 260)(d), tx(d, (960, 820), "그대로 베끼는 게 아닙니다", 110, INK, GAEGU, "mm")),
 },
 "what": {
   "t": lambda d: (tx(d, (960, 170), "가져오는 것은 영상이 아니라", 90, INK, PEN, "mm"),
                   jrect(d, 260, 330, 860, 650, RED, 7), tx(d, (560, 440), "후킹을", 110, RED, GAEGU, "mm"), tx(d, (560, 560), "어떻게 잡나", 80, INK, PEN, "mm"),
                   jrect(d, 1060, 330, 1660, 650, RED, 7), tx(d, (1360, 440), "이야기를", 110, RED, GAEGU, "mm"), tx(d, (1360, 560), "어떻게 끌고 가나", 80, INK, PEN, "mm"),
                   hlbox(360, 780, 1560, 880)(d), tx(d, (960, 830), "= 채널 스타일 벤치마킹", 96, INK, GAEGU, "mm")),
 },
 "prob": {"t": big("문제는 여기서부터", 540, RED, 150)},
 "limit": {
   "copy": lambda d: (tx(d, (960, 120), "뼈대를 알아낸 다음 → 손으로 따라 만들기", 76, INK, PEN, "mm")),
   "ch": lambda d: [(jrect(d, 220 + i * 560, 220, 580 + i * 560, 360), tx(d, (400 + i * 560, 290), f"채널 {i + 1}", 72, INK, PEN, "mm")) for i in range(3)],
   "x": lambda d: ([jrect(d, 220 + i * 560 + (k % 4) * 90, 420 + (k // 4) * 90, 290 + i * 560 + (k % 4) * 90, 490 + (k // 4) * 90, (120, 120, 120), 4) for i in range(3) for k in range(8)], tx(d, (960, 760), "손편집 x2   x3", 120, RED, GAEGU, "mm")),
   "stop": lambda d: tx(d, (960, 940), "결국 편집 화면 앞에서 멈춘다", 80, INK, GAEGU, "mm"),
 },
 "many": {
   "wins": lambda d: [(jrect(d, x, y, x + 380, y + 240, (130, 130, 130), 5), jl(d, (x, y + 40), (x + 380, y + 40), (130, 130, 130), 4)) for x, y in ((150, 160), (330, 300), (190, 470), (420, 600))],
   "x": lambda d: (jl(d, (130, 140), (840, 880), RED, 12), jl(d, (840, 140), (130, 880), RED, 12), tx(d, (480, 960), "여러 개 켤 필요 없음", 70, RED, GAEGU, "mm")),
   "one": lambda d: (arrow(d, (900, 520), (1060, 520), INK, 8), clwin(1100, 220, 1790, 760, 22)(d)),
   "both": lambda d: tx(d, (1445, 860), "뜯어보기 + 만들기 = 클로드", 66, BLUE, PEN, "mm"),
 },
 "ddal": {"t": lambda d: (claude_char(d, 960, 470, 26), tx(d, (960, 800), "딸깍 시대", 170, ORANGE, GAEGU, "mm"))},
 "other": {
   "hd": lambda d: tx(d, (160, 110), "다른 길도 있죠", 90, INK, GAEGU, "lm"),
   "a1": lambda d: tx(d, (160, 300), "강의 더 듣기", 84, INK, PEN, "lm"),
   "a2": lambda d: (tx(d, (760, 305), "손편집 실력만 늘어남", 70, (90, 90, 90), PEN, "lm"), jl(d, (150, 300), (1300, 300), RED, 5)),
   "b1": lambda d: tx(d, (160, 500), "편집 앱 바꾸기", 84, INK, PEN, "lm"),
   "b2": lambda d: (tx(d, (760, 505), "누르는 건 여전히 내 손", 70, (90, 90, 90), PEN, "lm"), jl(d, (150, 500), (1300, 500), RED, 5)),
   "c1": lambda d: tx(d, (160, 700), "편집자 맡기기", 84, INK, PEN, "lm"),
   "c2": lambda d: (tx(d, (760, 705), "채널 늘면 비용도 늘어남", 70, (90, 90, 90), PEN, "lm"), jl(d, (150, 700), (1300, 700), RED, 5)),
   "st": lambda d: stamp(d, 1600, 500, "결국 내 손"),
 },
 "room": {
   "say": lambda d: tx(d, (960, 260), "저희 방에서는...", 100, INK, GAEGU, "mm"),
   "fool": lambda d: (monitor(d, 300, 420, 820, 760), xmark(560, 590, 130)(d), tx(d, (1300, 600), "바보 소리", 170, RED, GAEGU, "mm")),
 },
 "hist": {
   "l": lambda d: (jl(d, (180, 520), (1740, 520), INK, 8), jcirc(d, 300, 520, 26, ORANGE, 10), tx(d, (300, 430), "숏템메이커", 72, INK, PEN, "mm")),
   "money": lambda d: tx(d, (960, 230), "돈 + 시간을 갈아 넣었다", 96, INK, GAEGU, "mm"),
   "rest": lambda d: ([(jcirc(d, x, 520, 26, ORANGE, 10), tx(d, (x, 430), t, 72, INK, PEN, "mm")) for x, t in ((760, "숏템 v2"), (1220, "숏클"), (1640, "오늘"))], tx(d, (960, 720), "고친 기록 3,926건+", 120, RED, GAEGU, "mm")),
   "in": lambda d: (jrect(d, 560, 830, 1360, 990, BLUE, 6), tx(d, (960, 910), "시행착오 → 전부 이 안에", 76, BLUE, PEN, "mm")),
 },
 "global": {
   "g": lambda d: (B.SK("global")[0](d), jrect(d, 1100, 240, 1700, 360), tx(d, (1400, 300), "한국 채널", 62, INK, PEN, "mm")),
   "more": lambda d: (jrect(d, 1100, 410, 1700, 530), tx(d, (1400, 470), "English channel", 62, INK, GAEGU, "mm"), jrect(d, 1100, 580, 1700, 700), tx(d, (1400, 640), "日本チャンネル", 62, INK, JA, "mm"), tx(d, (1400, 860), "대본, 목소리 = 클로드", 70, BLUE, PEN, "mm")),
 },
 "now": {
   "p": lambda d: (person(d, 380, 600, 1.4), arrow(d, (620, 520), (820, 520)), clwin(880, 260, 1720, 780)(d), jrect(d, 940, 660, 1660, 740, BLUE, 5), tx(d, (970, 700), "\"이 스타일로 만들어줘\"", 54, INK, PEN, "lm")),
   "mail": lambda d: tx(d, (960, 930), "이메일만 보내던 분도 됩니다", 84, ORANGE, GAEGU, "mm"),
 },
 "recap": {
   "a": lambda d: (tx(d, (960, 300), "벤치마킹 = 맞다", 130, INK, GAEGU, "mm"), check(430, 300, 1.4, BLUE)(d)),
   "b": lambda d: (tx(d, (960, 650), "손으로 하는 시대 = 끝", 130, RED, GAEGU, "mm")),
 },
}

# 장면별 비트(문장 수와 같다). 손그림 비트: ("sk", 쪽, [이번 문장에 그릴 요소])
BEATS = {
 "s00": [("one", "tattoo", 3), ("img", "claude_last"), ("tiles", ["spat", "choco", "sun"], [4, 2, 3]), ("tiles", ["ottogi", "tint", "lego"], [3, 3, 4]), ("tiles", ["choco", "spat", "lego", "sun", "tint"], [10, 12, 12, 14, 10])],
 "s01": [("sk", "member", ["person", "label"]), ("sk", "member", ["email"]), ("sk", "member", ["r1", "r2", "won"]), ("sk", "member", ["mon", "hand"]),
         ("sk", "work", ["a", "b", "c"]), ("sk", "months", ["cal", "zero"]), ("sk", "lazy", ["q"]), ("sk", "lazy", ["no"]), ("sk", "lazy", ["honest"]), ("sk", "lazy", ["era"])],
 "s02": [("sk", "right", ["ok"]), ("sk", "right", ["quote"]), ("sk", "mis", ["q"]), ("sk", "mis", ["x"]),
         ("tiles", ["tint", "tattoo", "spat"], [6, 8, 6], "같은 주제 · 원본은 다 다르다"), ("sk", "what", ["t"]), ("sk", "bench", ["how"]), ("sk", "bench", ["ch", "mag"]), ("sk", "bench", ["k1", "k2", "k3", "k4"]), ("sk", "bench", ["rule"]), ("sk", "bench", ["std"])],
 "s03": [("sk", "prob", ["t"]), ("sk", "limit", ["copy"]), ("sk", "limit", ["ch"]), ("sk", "limit", ["x"]), ("sk", "limit", ["stop"])],
 "s04": [("img", "claude_last"), ("sk", "many", ["wins", "x"]), ("sk", "many", ["one", "both"]), ("sk", "ddal", ["t"])],
 "s05": [("sk", "other", ["hd"]), ("sk", "other", ["a1"]), ("sk", "other", ["a2"]), ("sk", "other", ["b1"]), ("sk", "other", ["b2"]), ("sk", "other", ["c1"]), ("sk", "other", ["c2"]),
         ("sk", "other", ["st"]), ("sk", "room", ["say"]), ("sk", "room", ["fool"])],
 "s06": [("sk", "hist", ["l"]), ("sk", "hist", ["money"]), ("sk", "hist", ["rest"]), ("sk", "hist", ["in"])],
 "s07": [("tiles", ["ottogi", "tint", "sun", "lego"], [3, 3, 8, 4], "전부 클로드가 만든 영상"), ("tiles", ["spat", "choco", "tattoo", "chal"], [8, 6, 10, 4], "스타일이 다 다르다"), ("img", "claude_last")],
 "s08": [("tiles", ["chal", "tattoo"], [6, 6], "똑같이 만들면 = 남의 채널"), ("tiles", ["choco", "spat"], [12, 14], "채널명 + 템플릿 바꾸기"), ("tiles", ["ottogi", "tint"], [10, 12], "글꼴 · 색 · 목소리 · 음악"),
         ("one", "sun", 10, "골라서 바꾸면 끝"), ("tiles", ["lego", "tattoo"], [14, 16], "후킹 · 흐름은 그대로, 옷은 내 것으로"), ("one", "choco", 16, "나만의 스타일")],
 "s09": [("tiles", ["choco", "spat", "lego", "sun", "tint"], [10, 12, 12, 14, 10], "채널 하나만 할 이유가 없다"), ("tiles", ["ottogi", "chal", "tattoo"], [14, 16, 18], "같은 방식 → 채널 여러 개"),
         ("tiles", ["sun", "lego", "spat", "choco"], [18, 20, 20, 18], "형식 6 · 채널 스타일 24")],
 "s10": [("sk", "global", ["g"]), ("sk", "global", ["more"])],
 "s11": [("sk", "now", ["p"]), ("sk", "now", ["mail"]), ("sk", "ddal", ["t"])],
 "s12": [("full", "gdp", 5, "정리"), ("sk", "recap", ["a"]), ("sk", "recap", ["b"]), ("tiles", ["tattoo", "choco", "lego"], [20, 18, 22]), ("full", "gdp", 110),
         ("one", "tattoo", 18, "강의에서 처음부터"), ("img", "claude_last"), ("full", "gdp", 210, "신청은 고정 댓글에")],
}


def sentences(text):
    return [x.strip() for x in re.split(r"(?<=[.?!])\s+", text) if x.strip()]


def beat_times(sid):
    """문장 시각 — 자막과 화면이 같이 쓰는 한 곳. → [(시작, 끝, 문장)], 장면 길이"""
    A = B.dur(W / "voice" / f"{sid}.mp3")
    ss = sentences(TEXT[sid])
    tot = sum(len(x) for x in ss)
    out, c = [], 0.0
    for x in ss:
        d = A * len(x) / tot
        out.append((c, c + d, x)); c += d
    D = A + 0.6
    return out, D


def label_img(text):
    im = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d = ImageDraw.Draw(im, "RGBA")
    f = ImageFont.truetype(GAEGU, 76)
    w = d.textlength(text, font=f)
    d.rounded_rectangle((960 - w / 2 - 40, 22, 960 + w / 2 + 40, 132), 22, fill=(255, 255, 255, 240))
    d.text((960, 77), text, font=f, fill=RED, anchor="mm")
    p = W / "lab" / (re.sub(r"\W", "_", text)[:40] + ".png")
    p.parent.mkdir(exist_ok=True); im.save(p); return p


def enc(args, out):
    B.run(["ffmpeg", "-y", "-v", "error", *args, "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-an", "-r", str(FPS), str(out)])


def video_beat(b, D, out):
    kind = b[0]
    lab = None
    if kind == "one":
        keys, ss, lab = [b[1]], [b[2]], (b[3] if len(b) > 3 else None)
        v = {"tiles": keys, "ss": ss}
    elif kind == "tiles":
        v = {"tiles": b[1], "ss": b[2]}; lab = b[3] if len(b) > 3 else None
    else:  # full
        v = {"full": b[1], "ss": b[2]}; lab = b[3] if len(b) > 3 else None
    tmp = out.with_suffix(".raw.mp4")
    B.tiles_segment(v, D, tmp)
    if lab:
        lp = label_img(lab)
        enc(["-i", str(tmp), "-i", str(lp), "-filter_complex", "[0:v][1:v]overlay=0:0", "-t", f"{D:.3f}"], out)
    else:
        shutil.move(tmp, out)


def img_beat(name, D, out):
    p = W / f"{name}.png"
    enc(["-loop", "1", "-t", f"{D:.3f}", "-i", str(p), "-vf", f"scale={VW}:{VH},zoompan=z='1+0.0006*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={VW}x{VH}:fps={FPS}"], out)


class Page:
    def __init__(self):
        self.name, self.img = None, None

    def beat(self, name, els, D, out, fdir):
        if name != self.name:
            self.name, self.img = name, B.paper().convert("RGBA")
        fdir.mkdir(parents=True, exist_ok=True)
        lays = [B.draw_layer(PAGES[name][e]) for e in els]
        draw_t = min(1.4, D * 0.55)
        per = draw_t / max(1, len(lays))
        steps, lines, n = 5, [], 0
        cur = self.img
        for lay in lays:
            bb = lay.getbbox() or (0, 0, 1, 1)
            for k in range(1, steps + 1):
                x = bb[0] + (bb[2] - bb[0]) * k // steps
                m = Image.new("L", (VW, VH), 0); ImageDraw.Draw(m).rectangle((0, 0, x, VH), fill=255)
                part = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
                part.paste(lay, (0, 0), Image.composite(lay.getchannel("A"), Image.new("L", (VW, VH), 0), m))
                p = fdir / f"{n:03d}.jpg"; Image.alpha_composite(cur, part).convert("RGB").save(p, quality=90); n += 1
                lines.append(f"file '{p.as_posix()}'\nduration {per / steps:.3f}")
            cur = Image.alpha_composite(cur, lay)
        p = fdir / f"{n:03d}.jpg"; cur.convert("RGB").save(p, quality=90)
        lines.append(f"file '{p.as_posix()}'\nduration {max(0.1, D - draw_t):.3f}")
        lines.append(f"file '{p.as_posix()}'")
        (fdir / "l.txt").write_text("\n".join(lines), encoding="utf-8")
        enc(["-f", "concat", "-safe", "0", "-i", str(fdir / "l.txt"), "-vf", f"fps={FPS}", "-t", f"{D:.3f}"], out)
        self.img = cur


def seg(ids):
    (W / "seg").mkdir(exist_ok=True)
    for sid in BEATS:
        if ids and sid not in ids:
            continue
        bt, D = beat_times(sid)
        beats = BEATS[sid]
        assert len(beats) == len(bt), f"{sid}: 비트 {len(beats)} != 문장 {len(bt)}"
        bdir = W / "beats" / sid
        if bdir.exists(): shutil.rmtree(bdir)
        bdir.mkdir(parents=True)
        page = Page()
        parts = []
        for i, (b, (t0, t1, _)) in enumerate(zip(beats, bt)):
            d = (t1 - t0) if i < len(bt) - 1 else D - t0
            out = bdir / f"{i:02d}.mp4"
            if b[0] == "sk":
                page.beat(b[1], b[2], d, out, bdir / f"f{i:02d}")
            elif b[0] == "img":
                img_beat(b[1], d, out)
            else:
                video_beat(b, d, out)
            parts.append(out)
        (bdir / "list.txt").write_text("\n".join(f"file '{p.as_posix()}'" for p in parts), encoding="utf-8")
        v = bdir / "v.mp4"
        B.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(bdir / "list.txt"), "-c", "copy", str(v)])
        a = W / "voice" / f"{sid}.mp3"
        B.run(["ffmpeg", "-y", "-v", "error", "-i", str(v), "-i", str(a), "-af", "apad=pad_dur=0.6", "-map", "0:v", "-map", "1:a",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{D:.3f}", str(W / "seg" / f"{sid}.v2.mp4")])
        print("장면", sid, len(beats), "비트", round(D, 2), "초", flush=True)


def final():
    order = ["open"] + list(BEATS)
    files = [W / "seg" / ("open.av.mp4" if s == "open" else f"{s}.v2.mp4") for s in order]
    (W / "concat2.txt").write_text("\n".join(f"file '{p.as_posix()}'" for p in files), encoding="utf-8")
    ev, t = [], B.dur(files[0])
    for sid in BEATS:
        bt, D = beat_times(sid)
        for a, b, x in bt:
            ev.append((t + a + 0.1, t + b + 0.05, x))
        t += B.dur(W / "seg" / f"{sid}.v2.mp4")
    head = (W / "subs.ass").read_text(encoding="utf-8").split("[Events]")[0]
    body = "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n" + "\n".join(
        f"Dialogue: 0,{B.ass_time(a)},{B.ass_time(b)},S,,0,0,0,,{x}" for a, b, x in ev)
    (W / "subs2.ass").write_text(head + body + "\n", encoding="utf-8")
    import os
    os.chdir(W)
    fontsdir = (W / "fonts").as_posix().replace(":", "\\:")
    out = W / "yt4_draft_v3.mp4"
    B.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "concat2.txt", "-vf", f"subtitles=subs2.ass:fontsdir='{fontsdir}'",
           "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", str(out)])
    print("완성", out, round(B.dur(out), 2), "초")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("seg", "all"):
        seg(sys.argv[2:])
    if what in ("final", "all"):
        final()
