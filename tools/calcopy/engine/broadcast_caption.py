# -*- coding: utf-8 -*-
"""(판단 주인) 완성 영상 위 방송 강조 자막 — 배치·크기·줄바꿈·색을 여기 한 곳이 정한다(관제 293, 사장님 11-01 "해봐 카피 → 1").

    PYTHONUTF8=1 py -m tools.calcopy.engine.broadcast_caption <영상.mp4> <자막.json> <결과.mp4> [--preset hot|lime|sky]

자막.json = [{"start": 1.0, "end": 3.0, "text": "*물때*는 **이렇게** 지운다"}, …]
  별표: *낱말* 강조1, **낱말** 강조2 — 강조는 크게·기울여·광택.
  선택 칸: role(pop 기본·talk 토크박스·tiles 글자 타일) · y(세로 위치, 화면 비율) · arrow(끝에 ↑) · tag(위 작은 태그).

원리 = ASS 층 쌓기(libass): 입체(겹쳐 민 층) → 얇은 테두리 → 글자를 띠로 잘라 겹친 광택. 폭은 실제 렌더한 잉크로 잰다 —
PIL·폰트 표 폭은 libass 와 어긋난다(메모리 brainbulb 실측함정, 가운뎃점 전각 폭 재현 11-01). 모양은 볼케이노 데모를 보고 원리만 따왔고
코드·프리셋은 쓰지 않는다. 라디오스타 색 조합은 쓰지 않는다.
검사 = tools/calcopy/engine/check_broadcast_caption.py (실제 영상 프레임으로 넘침·길이·소리 대조)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from tools.calcopy.engine import encoder as ENC
from tools.calcopy.engine.ad_mark import _probe
from tools.calcopy.engine.encoder import venc

ROOT = Path(__file__).resolve().parents[3]
FONT_DIR = ROOT / "shopping_shorts/static/fonts"
FONTS = {"heavy": ("BlackHanSans.ttf", "Black Han Sans"), "body": ("NanumGothic-Bold.ttf", "NanumGothic")}
MARK = "broadcast_caption:v1"
MARGIN = 0.06        # 좌우 여백(화면 너비 비율)
SIZE_PLAIN, SIZE_EMPH = 0.085, 0.118   # 글자 크기(화면 너비 비율)
SX, SY = 80, 120     # 글자를 좁고 길게 — 방송 굵은 고딕 느낌은 여기서 나온다(11-01 데모 대조)
FAX = -0.12
Y_DEFAULT = 0.64     # 화면 아래쪽 기존 자막 띠 위
WRAP_BELOW = 0.8     # 한 줄로 두면 이보다 작아질 때 두 줄로
DARK = "0A0A10"
PLAIN = [(0, "FFFFFF"), (.6, "F4F4F6"), (1, "B8BEC8")]
GOLD = [(0, "FFFFF0"), (.28, "FFE27A"), (.46, "E0A020"), (.54, "8A5208"), (.6, "FFF0B0"), (.8, "FFD24A"), (1, "D08A10")]
SILVER = [(0, "FFFFFF"), (.7, "F0F2F6"), (1, "A8B0BC")]
PRESETS = {
    "hot": {1: ("diag", [(0, "FFFFFF"), (.35, "FFF3A0"), (.65, "FFC21E"), (1, "FF7A14")]),
            2: ("diag", [(0, "FFF0E8"), (.4, "FF9A7A"), (.75, "FF3C3C"), (1, "D2141E")])},
    "lime": {1: ("diag", [(0, "FFFFFF"), (.3, "E8FFD8"), (.55, "8CF05A"), (.8, "3CD232"), (1, "1EA02D")]), 2: ("vert", GOLD)},
    "sky": {1: ("diag", [(0, "FFFFFF"), (.4, "C8F0FF"), (.75, "46BEFF"), (1, "1478E6")]), 2: ("vert", GOLD)},
}
TILES = [("7A3A14", "F06A14"), ("1C5A96", "1496F0"), ("6E1A6E", "F01EB4"), ("1E7850", "14C88C")]


def _rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _c(h):
    r, g, b = _rgb(h)
    return "&H%02X%02X%02X&" % (b, g, r)


def _grad(stops, t):
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if a <= t <= b:
            x, y = _rgb(ca), _rgb(cb)
            k = (t - a) / (b - a or 1)
            return "%02X%02X%02X" % tuple(round(x[i] + (y[i] - x[i]) * k) for i in range(3))
    return stops[-1][1]


def _ts(s):
    cs = round(s * 100)
    return "%d:%02d:%02d.%02d" % (cs // 360000, cs // 6000 % 60, cs // 100 % 60, cs % 100)


def _clean(s):
    return re.sub(r"[{}\\]", "", str(s)).strip()


def _header(w, h):
    return ("[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: S,Arial,60,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n") % (w, h)


def parse(s):
    """'*물때*는 **이렇게**' → [(글자, 등급, 앞에 띄어쓰기)] — 어절 단위."""
    out = []
    for m in re.finditer(r"\*\*(.+?)\*\*|\*(.+?)\*|([^*]+)", _clean(s)):
        raw, grade = (m.group(1), 2) if m.group(1) else (m.group(2), 1) if m.group(2) else (m.group(3), 0)
        gap = raw[0].isspace()
        for k, word in enumerate(raw.split()):
            out.append([word, grade, bool(k) or gap])
        if raw[-1].isspace() and m.end() < len(_clean(s)):
            out.append(["", grade, True])
    res = []
    pending = False
    for w, g, gap in out:
        if not w:
            pending = True
            continue
        res.append((w, g, (gap or pending) and bool(res)))
        pending = False
    return res


class Ink:
    """글자 폭을 libass 로 실제 렌더해 잰다(100 글자 크기·가로 100% 기준, 한 번에 몰아서 ffmpeg 1회)."""

    def __init__(self, work):
        self.work, self.cache = Path(work), {}

    def need(self, items):
        todo = sorted({i for i in items if i not in self.cache})
        if not todo:
            return
        row, w = 170, 3600
        ev = ["Dialogue: 0,0:00:00.00,0:00:02.00,S,,0,0,0,,{\\an4\\pos(60,%d)\\fn%s\\fs100}%s" % (row // 2 + i * row, FONTS[f][1], t)
              for i, (f, t) in enumerate(todo)]
        (self.work / "_ink.ass").write_text(_header(w, row * len(todo)) + "\n".join(ev) + "\n", encoding="utf-8-sig")
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=black:s=%dx%d:d=1" % (w, row * len(todo)),
                            "-vf", "subtitles=_ink.ass:fontsdir=fonts", "-frames:v", "1", "_ink.png"],
                           cwd=self.work, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode:
            raise RuntimeError("글자 폭 재기 실패: " + r.stderr[-300:])
        a = np.asarray(Image.open(self.work / "_ink.png").convert("L")) > 60
        for i, key in enumerate(todo):
            cols = np.where(a[i * row:(i + 1) * row].any(axis=0))[0]
            self.cache[key] = float(cols[-1] - cols[0] + 1) if len(cols) else 0.0

    def width(self, font, text, size, sx=100):
        self.need([(font, text)])
        return self.cache[(font, text)] * size / 100 * sx / 100


class Sheet:
    def __init__(self, w, h, ink):
        self.w, self.h, self.ink, self.ev, self.u = w, h, ink, [], w / 1080

    def add(self, layer, t0, t1, body):
        self.ev.append("Dialogue: %d,%s,%s,S,,0,0,0,,%s" % (layer, _ts(t0), _ts(t1), body))

    def glyph(self, t0, t1, x, y, s, size, mode, fill, layer=0):
        """입체 → 얇은 테두리 → 띠 광택. 띠는 뒤로 갈수록 겹쳐 칠해 틈이 없다."""
        f = r"\fn%s\fs%d\fscx%d\fscy%d\fax%.2f" % (FONTS["heavy"][1], size, SX, SY, FAX)
        at = r"{\an4\pos(%.1f,%.1f)%s" % (x, y, f)
        out, deep = max(2, round(size * .04)), max(3, round(size * .07))
        for i in range(deep, 0, -1):
            self.add(layer, t0, t1, r"{\an4\pos(%.1f,%.1f)%s\bord%d\1c%s\3c%s}%s" % (x + i * .75, y + i, f, out, _c(DARK), _c(DARK), s))
        self.add(layer + 1, t0, t1, at + r"\bord%d\1c%s\3c%s}%s" % (out, _c(DARK), _c(DARK), s))
        w = self.ink.width("heavy", s, size, SX)
        x0, x1, y0, y1 = x - size * .4, x + w + size * .6, y - size * 2, y + size * 2
        n = 36 if fill is not PLAIN else 8
        for i in range(n):
            col = _c(_grad(fill, i / (n - 1)))
            if mode == "diag":
                sl = size * .55
                a = x0 - sl + i * (x1 - x0 + sl) / n
                clip = r"\clip(m %d %d l %d %d l %d %d l %d %d)" % (a, y1, x1 + sl, y1, x1 + sl, y0, a + sl, y0)
            else:
                top = y - size * .72 + i * size * 1.44 / n if i else y0
                clip = r"\clip(m %d %d l %d %d l %d %d l %d %d)" % (x0, top + size * .1, x1, top - size * .1, x1, y1, x0, y1)
            self.add(layer + 2, t0, t1, at + r"\bord0\1c%s%s}%s" % (col, clip, s))
        return w

    def poly(self, layer, t0, t1, path, tags):
        self.add(layer, t0, t1, r"{\an7\pos(0,0)%s\p1}%s{\p0}" % (tags, path))

    def arrow(self, t0, t1, x, y, size):
        s = size / 100
        pts = [(0, -66), (58, -8), (30, -8), (30, 42), (-30, -8 + 50), (-30, -8), (-58, -8)]
        path = lambda dx, dy: "m " + " l ".join("%d %d" % (x + a * s + dx, y + b * s + dy) for a, b in pts)
        deep = max(3, round(size * .07))
        for i in range(deep, 0, -1):
            self.poly(0, t0, t1, path(i * .75, i), r"\bord4\1c%s\3c%s" % (_c(DARK), _c(DARK)))
        self.poly(1, t0, t1, path(0, 0), r"\bord4\1c%s\3c%s" % (_c(DARK), _c(DARK)))
        for i in range(20):
            self.poly(2, t0, t1, path(0, 0), r"\bord0\1c%s\clip(0,%d,%d,%d)" % (
                _c(_grad(SILVER, i / 19)), y - 70 * s + i * 112 * s / 20, self.w, y + 60 * s))

    def tag(self, t0, t1, cx, bottom, s):
        size = round(self.w * .044)
        w = self.ink.width("body", s, size) + size
        h = size * 1.32
        x0, y0 = cx - w / 2, bottom - h
        self.poly(3, t0, t1, "m %d %d l %d %d l %d %d l %d %d" % (x0, y0, x0 + w, y0, x0 + w, bottom, x0, bottom),
                  r"\bord2\1c%s\3c%s" % (_c("0C2A3C"), _c("C8AA5A")))
        self.add(4, t0, t1, r"{\an5\pos(%.1f,%.1f)\fn%s\fs%d\bord0\1c%s}%s" % (cx, y0 + h / 2, FONTS["body"][1], size, _c("FFFFFF"), s))

    def pop(self, cue, preset):
        """별표 문장 — 넘치면 줄이고, 많이 줄어야 하면 두 줄로."""
        t0, t1 = cue["start"], cue["end"]
        words = parse(cue["text"])
        if not words:
            return
        u = self.w
        avail = u * (1 - 2 * MARGIN)
        arrow = u * .13 if cue.get("arrow") else 0

        def size_of(g):
            return round(u * (SIZE_EMPH if g else SIZE_PLAIN))

        def gap_of(i):
            return size_of(words[i][1]) * .24 if words[i][2] else u * .004

        self.ink.need([("heavy", w) for w, _, _ in words])
        def line_w(a, b):
            return sum(self.ink.width("heavy", words[i][0], size_of(words[i][1]), SX) + (gap_of(i) if i > a else 0) for i in range(a, b))

        one = line_w(0, len(words)) + arrow
        lines = [(0, len(words))]
        cuts = [i for i in range(1, len(words)) if words[i][2]]
        if avail / one < WRAP_BELOW and cuts:
            cut = min(cuts, key=lambda i: max(line_w(0, i), line_w(i, len(words)) + arrow))
            lines = [(0, cut), (cut, len(words))]
        k = min(1.0, avail / max(line_w(a, b) + (arrow if b == len(words) else 0) for a, b in lines))
        pitch = max(size_of(w[1]) for w in words) * k * SY / 100 * 1.12
        cy = self.h * cue.get("y", Y_DEFAULT)
        ys = [cy + (i - (len(lines) - 1) / 2) * pitch for i in range(len(lines))]
        for (a, b), y in zip(lines, ys):
            runs = []                                   # 같은 등급·띄어쓰기로 이어진 어절은 광택 하나로
            for i in range(a, b):
                w, g, sp = words[i]
                if runs and runs[-1][1] == g and sp:
                    runs[-1][0] += " " + w
                else:
                    runs.append([w, g, i])
            sizes = [round(size_of(r[1]) * k) for r in runs]
            self.ink.need([("heavy", r[0]) for r in runs])
            total = sum(self.ink.width("heavy", r[0], z, SX) for r, z in zip(runs, sizes))
            total += sum(gap_of(r[2]) * k for r in runs[1:])
            end_arrow = cue.get("arrow") and b == len(words)
            x = (u - total - (arrow * k if end_arrow else 0)) / 2
            for j, (r, z) in enumerate(zip(runs, sizes)):
                if j:
                    x += gap_of(r[2]) * k
                mode, fill = ("vert", PLAIN) if r[1] == 0 else preset[r[1]]
                x += self.glyph(t0, t1, x, y, r[0], z, mode, fill)
            if end_arrow:
                self.arrow(t0, t1, x + arrow * k * .55, y, max(sizes))
        if cue.get("tag"):
            self.tag(t0, t1, u / 2, ys[0] - pitch * .62, _clean(cue["tag"]))

    def talk(self, cue):
        """흰 토크박스 — 별표는 빨강, 글자는 한 줄에 맞춰 줄인다."""
        t0, t1, u = cue["start"], cue["end"], self.w
        words = parse(cue["text"])
        if not words:
            return
        plain = " ".join(w for w, _, _ in words)
        size, pad = round(u * .058), u * .03
        self.ink.need([("body", plain)])
        size = round(size * min(1, (u * (1 - 2 * MARGIN) - pad * 2) / self.ink.width("body", plain, size)))
        tw = self.ink.width("body", plain, size)
        x0, x1 = (u - tw) / 2 - pad, (u + tw) / 2 + pad
        cy = self.h * cue.get("y", Y_DEFAULT)
        y0, y1 = cy - size * .8, cy + size * .8
        self.poly(0, t0, t1, "m %d %d l %d %d l %d %d l %d %d" % (x0 + 6, y0, x1, y0 + 5, x1 + 2, y1 + 3, x0, y1), r"\bord3\1c%s\3c%s" % (_c("FFFFFF"), _c(DARK)))
        out = ""
        for i, (w, g, sp) in enumerate(words):
            out += (" " if sp else "") + (r"{\1c%s\3c%s}" % ((_c("C8143C"),) * 2) if g else r"{\1c%s\3c%s}" % ((_c("16161E"),) * 2)) + w
        self.add(1, t0, t1, r"{\an5\pos(%.1f,%.1f)\fn%s\fs%d\fax-0.06\bord0.7}%s" % (u / 2, cy, FONTS["body"][1], size, out))

    def tiles(self, cue):
        """글자마다 색 칸 — 짧은 말(4~6자) 전용."""
        t0, t1, u = cue["start"], cue["end"], self.w
        chars = [c for c in _clean(cue["text"]).replace("*", "") if not c.isspace()]
        if not chars:
            return
        gap = u * .026
        tw = min(u * .17, (u * (1 - 2 * MARGIN) - gap * (len(chars) - 1)) / len(chars))
        th = tw * 1.24
        x = (u - tw * len(chars) - gap * (len(chars) - 1)) / 2
        y0 = self.h * cue.get("y", Y_DEFAULT) - th / 2
        box = lambda a, b, c, d: "m %d %d l %d %d l %d %d l %d %d" % (a, b, c, b, c, d, a, d)
        for i, ch in enumerate(chars):
            bg, edge = TILES[i % len(TILES)]
            sh = tw * .05
            self.poly(0, t0, t1, box(x + sh, y0 + sh, x + tw + sh, y0 + th + sh), r"\bord0\1c%s" % _c("000000"))
            self.poly(1, t0, t1, box(x, y0, x + tw, y0 + th), r"\bord2\1c%s\3c%s" % (_c(bg), _c("000000")))
            self.add(2, t0, t1, r"{\an5\pos(%.1f,%.1f)\fn%s\fs%d\bord%d\1c%s\3c%s}%s" % (
                x + tw / 2, y0 + th / 2, FONTS["heavy"][1], round(tw * .92), max(3, round(tw * .045)), _c("FFFFFF"), _c(edge), ch))
            x += tw + gap


def build_ass(cues, w, h, work, preset="hot"):
    sh = Sheet(w, h, Ink(work))
    for cue in cues:
        role = cue.get("role", "pop")
        if role == "talk":
            sh.talk(cue)
        elif role == "tiles":
            sh.tiles(cue)
        else:
            sh.pop(cue, PRESETS[preset])
    return _header(w, h) + "\n".join(sh.ev) + "\n"


def render(video, cues, out, preset="hot", log=print):
    """영상 + 자막 → 새 영상. 소리는 복사, 표식 comment 는 이어 붙인다(광고 표시 표식을 지우지 않는다)."""
    video, out = Path(video).resolve(), Path(out).resolve()
    w, h, comment = _probe(video)
    if not w:
        raise RuntimeError(f"영상을 못 읽음: {video}")
    with tempfile.TemporaryDirectory(prefix="bcap_") as tmp:
        work = Path(tmp)
        (work / "fonts").mkdir()
        for file, _ in FONTS.values():
            shutil.copyfile(FONT_DIR / file, work / "fonts" / file)
        (work / "sub.ass").write_text(build_ass(cues, w, h, work, preset), encoding="utf-8-sig")
        mark = comment if MARK in comment else (comment + " " if comment else "") + MARK
        r = ENC.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vf", "subtitles=sub.ass:fontsdir=fonts,format=yuv420p",
                     "-map", "0:v:0", "-map", "0:a?", *venc(16), "-c:a", "copy", "-metadata", f"comment={mark}",
                     "-movflags", "+faststart", str(out)], cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0 or not out.exists():
            raise RuntimeError("방송 자막 굽기 실패: " + (r.stderr or "")[-400:])
    log(f"[broadcast_caption] 자막 {len(cues)}개 {w}x{h} → {out.name}")
    return {"cues": len(cues), "size": [w, h]}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
    if len(args) != 3:
        sys.exit(__doc__)
    render(args[0], json.loads(Path(args[1]).read_text(encoding="utf-8")), args[2], opts.get("preset", "hot"))
