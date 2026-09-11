# -*- coding: utf-8 -*-
"""libass로 **실제 렌더**해서 글자의 잉크 폭을 잰다 — 볼케이노 실행기 `_fontprobe`와 같은 방식.

왜 PIL이 아닌가: PIL `getlength`는 libass보다 1.3~1.4배 크게 나온다(ASS Fontsize 해석 차이, 8편 문서 §3-②).
  이 값으로 판정하면 멀쩡한 줄을 반려하고, 제목 축소 크기가 틀린다.

한 번의 ffmpeg 호출로 여러 줄을 세로로 쌓아 재므로 호출당 비용이 거의 같다. 결과는 메모리 캐시.
"""
import os
import subprocess
import tempfile

from . import spec

_CACHE = {}
_BAND = 220           # 줄 간 세로 간격(px). 최대 폰트 134 + 여유
_PLAY_W = 2560


def _ffmpeg():
    return os.environ.get("BRAINBULB_FFMPEG", "ffmpeg")


def _fontsdir_arg(fonts_dir, cwd):
    """subtitles 필터의 fontsdir 값 — 절대경로의 'C:'는 필터 파서가 깨뜨린다(실측 2026-09-12).
    같은 드라이브면 cwd 기준 상대경로로, 아니면 콜론만 이스케이프한다. 두 렌더가 같은 함수를 쓴다(0순위-B)."""
    same = os.path.splitdrive(os.path.abspath(fonts_dir))[0].lower() == os.path.splitdrive(os.path.abspath(cwd))[0].lower()
    fd = os.path.relpath(fonts_dir, cwd) if same else fonts_dir
    return fd.replace("\\", "/").replace(":", "\\:")


def ink_widths(items, fonts_dir=None):
    """items: [(font_name, size, text)] → [ink_px]. font_name은 ASS 폰트 이름(spec.STYLE_FONT[*][0])."""
    fonts_dir = fonts_dir or spec.FONTS_DIR
    todo = [(i, it) for i, it in enumerate(items) if tuple(it) not in _CACHE]
    if todo:
        _render_measure([it for _, it in todo], fonts_dir)
    return [_CACHE[tuple(it)] for it in items]


def ink_width(font_name, size, text, fonts_dir=None):
    return ink_widths([(font_name, size, text)], fonts_dir)[0]


def fit_size(font_name, text, base, max_ink, fonts_dir=None, floor=40):
    """잉크 폭이 max_ink 이하가 되는 가장 큰 크기(≤ base). 후보를 한 번에 재서 ffmpeg 1회."""
    sizes = list(range(base, floor - 1, -1))
    ws = ink_widths([(font_name, s, text) for s in sizes], fonts_dir)
    for s, w in zip(sizes, ws):
        if w <= max_ink:
            return s
    return floor


def _render_measure(items, fonts_dir):
    from PIL import Image
    import numpy as np
    fonts = sorted({it[0] for it in items})
    style_lines = ["[V4+ Styles]",
                   "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"]
    sname = {}
    for k, f in enumerate(fonts):
        sname[f] = f"f{k}"
        style_lines.append(f"Style: f{k},{f},100,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1")
    h = 40 + _BAND * len(items)
    ev = ["[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for i, (f, size, text) in enumerate(items):
        ev.append(f"Dialogue: 0,0:00:00.00,0:00:10.00,{sname[f]},,0,0,0,,"
                  f"{{\\an7\\pos(20,{20 + _BAND * i})\\fs{int(size)}\\bord0\\shad0\\c&HFFFFFF&}}{text}")
    ass = "\n".join(["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {_PLAY_W}", f"PlayResY: {h}",
                     "WrapStyle: 2", "ScaledBorderAndShadow: yes", ""] + style_lines + [""] + ev) + "\n"
    with tempfile.TemporaryDirectory() as td:
        ap = os.path.join(td, "m.ass"); pp = os.path.join(td, "m.png")
        with open(ap, "w", encoding="utf-8") as fh:
            fh.write(ass)
        fd = _fontsdir_arg(fonts_dir, td)
        r = subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=black:s={_PLAY_W}x{h}:d=1",
                            "-vf", f"subtitles=m.ass:fontsdir={fd}", "-frames:v", "1", "m.png"],
                           cwd=td, capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            raise RuntimeError(f"measure: ffmpeg 렌더 실패 — {r.stderr[-300:]}")
        a = np.asarray(Image.open(pp).convert("L"))
    for i, it in enumerate(items):
        band = a[20 + _BAND * i: 20 + _BAND * (i + 1) - 10, :]
        xs = np.where(band.max(axis=0) > 40)[0]
        _CACHE[tuple(it)] = int(xs.max() - xs.min() + 1) if len(xs) else 0


_EDGE_CACHE = {}
_EDGE_X0 = 1280          # 넓은 캔버스 가운데 앵커 → 화면 밖으로 나가는 글자도 잘린 채가 아니라 그대로 재진다


def edges(items, fonts_dir=None):
    """본문 실제 조건으로 렌더한 **외곽선 포함** 좌·우 경계 — 아스트라 (2): 폭 상수 대신 좌표 검사.

    items: [(style, text, scale_pct)] (style = spec.STYLE_FONT 키, scale 100 또는 108)
    → [(left, right)]: 앵커 x(=spec.BODY_X)를 0으로 둔 상대 좌표. 화면 안 조건: BODY_X+left ≥ 0, BODY_X+right ≤ 1080
    """
    fonts_dir = fonts_dir or spec.FONTS_DIR
    todo = [it for it in items if tuple(it) not in _EDGE_CACHE]
    if todo:
        _render_edges(todo, fonts_dir)
    return [_EDGE_CACHE[tuple(it)] for it in items]


def _render_edges(items, fonts_dir):
    from PIL import Image
    import numpy as np
    h = 40 + _BAND * len(items)
    ev = ["[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for i, (style, text, sc) in enumerate(items):
        ev.append(f"Dialogue: 0,0:00:00.00,0:00:10.00,{style},,0,0,0,,"
                  f"{{\\an8\\pos({_EDGE_X0},{20 + _BAND * i})\\fscx{sc}\\fscy{sc}\\c&HFFFFFF&\\3c&HFFFFFF&}}{text}")
    styles = spec.STYLE_BLOCK.replace("PlayResX", "")  # 실제 스타일 블록 그대로(Outline 4 포함)
    ass = "\n".join(["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {_PLAY_W}", f"PlayResY: {h}",
                     "WrapStyle: 2", "ScaledBorderAndShadow: yes", "", styles.rstrip("\n"), ""] + ev) + "\n"
    with tempfile.TemporaryDirectory() as td:
        ap = os.path.join(td, "e.ass"); pp = os.path.join(td, "e.png")
        with open(ap, "w", encoding="utf-8") as fh:
            fh.write(ass)
        fd = _fontsdir_arg(fonts_dir, td)
        r = subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=black:s={_PLAY_W}x{h}:d=1",
                            "-vf", f"subtitles=e.ass:fontsdir={fd}", "-frames:v", "1", "e.png"],
                           cwd=td, capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            raise RuntimeError(f"measure.edges: ffmpeg 렌더 실패 — {r.stderr[-300:]}")
        a = np.asarray(Image.open(pp).convert("L"))
    for i, it in enumerate(items):
        band = a[20 + _BAND * i: 20 + _BAND * (i + 1) - 10, :]
        xs = np.where(band.max(axis=0) > 40)[0]
        _EDGE_CACHE[tuple(it)] = (int(xs.min()) - _EDGE_X0, int(xs.max()) + 1 - _EDGE_X0) if len(xs) else (0, 0)


def font_probe(fonts_dir=None):
    """폰트 4종이 진짜 잡히는지 — 없는 글꼴의 폴백 폭과 대조 (볼케이노 _fontprobe 방식)."""
    fonts_dir = fonts_dir or spec.FONTS_DIR
    probe = "가나다라마바사"
    names = sorted({v[0] for v in spec.STYLE_FONT.values()})
    ws = ink_widths([(n, 120, probe) for n in names] + [("절대없는글꼴9999", 120, probe)], fonts_dir)
    fallback = ws[-1]
    return {n: {"ink": w, "ok": w != fallback} for n, w in zip(names, ws[:-1])}
