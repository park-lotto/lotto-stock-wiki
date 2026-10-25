# -*- coding: utf-8 -*-
"""공용 렌더러 장치(tools/calcopy/hybrid/render_bench.py, 관제 263 지시서 02 — 표준 §3-3 A1·A4·B1).

  A1 장면 전환: transitions_of(목록 한 곳) → window_fx(줌블러·검은 프레임, 창 안) / render_base(흰 번쩍, 화면 전체)
  A4 나레 덕킹: bgm.duck_narr_db → audio() 의 BGM volume 식 + bgm_bed.wav(BGM 만) · bed_contrast
  B1 틀 종류: frame.kind window|post|full → frame_png · frame_window
그림이 **실제로** 달라지는지 잰다(작은 합성 영상에 ffmpeg 를 진짜로 돌려 라플라시안 분산·검정 프레임을 본다).

실제 렌더 대조(키치잇판 회귀·시험 판 줌블러·덕킹 dB·게시글 틀 framecmp)는 아래 CLI 로 —
    PYTHONUTF8=1 py shopping_shorts/tests/test_render_bench_devices.py blur <final.mp4> <render_info.json|timeline.json> [--window x,y,w,h]
    PYTHONUTF8=1 py shopping_shorts/tests/test_render_bench_devices.py duck <off/render> <on/render>
    PYTHONUTF8=1 py shopping_shorts/tests/test_render_bench_devices.py framediff <a.mp4> <b.mp4> [--start 0.5 --n 10]
    PYTHONUTF8=1 py shopping_shorts/tests/test_render_bench_devices.py postcmp <설명서 렌더 0초.png> <우리 0초.png> [--x 20]
      = kal_analyze framecmp(제목 첫 줄·본문 글 띠) + 머리띠·줄·본문 상자 가장자리 y(세로 한 줄에서 색이 바뀌는 행) ±4px·색 ΔE<5
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import render_bench as RB  # noqa: E402

FPS = RB.FPS


def _cuts(ts, end=4.0):
    ts = [0.0] + list(ts)
    return {"cuts": [{"t0": a, "t1": (ts[i + 1] if i + 1 < len(ts) else end)} for i, a in enumerate(ts)], "end": end}


def _st(**cuts):
    return {"frame": {"window": [0, 0, 216, 216], "flash_sec": 0.1}, "cuts": cuts}


# ── A1 전환 목록 ───────────────────────────────────────────────────────
def test_flashes_old_key_reads_as_flash():
    tr = RB.transitions_of(_cuts([1.0, 2.0]), _st(transition={"kinds": {"cut": 1.0}, "ms": 0}), {"flashes": [1.5]})
    assert tr == [{"t": 1.5, "kind": "flash", "ms": 100, "sec": 0.1, "why": "placement flashes(옛 키)"}]


def test_ms_filled_from_style_then_default():
    """placement 가 ms 를 비우면(None) 판 cuts.transition.ms → 종류별 기본."""
    placed = {"transitions": [{"t": 1.0, "kind": "zoomblur", "ms": None}, {"t": 2.0, "kind": "black", "ms": None}]}
    tr = RB.transitions_of(_cuts([1.0, 2.0]), _st(transition={"kinds": {"cut": 1.0}, "ms": 0}), placed)
    assert [(e["kind"], e["ms"]) for e in tr] == [("zoomblur", 200.0), ("black", 33.0)]
    tr = RB.transitions_of(_cuts([1.0, 2.0]), _st(transition={"ms": 150}), placed)
    assert [e["ms"] for e in tr] == [150.0, 150.0]


def test_no_decision_without_placement():
    """자리 판단 주인은 placement 하나 — 옛 배치 결과(transitions 칸 없음)면 판 비율이 1.0 이어도 여기서 경계를 고르지 않는다(로그만)."""
    logs = []
    tr = RB.transitions_of(_cuts([1.0, 2.0]), _st(transition={"kinds": {"cut": 1.0, "zoomblur": 1.0}, "ms": 200}), {"flashes": []}, logs.append)
    assert tr == [] and logs and "placement" in logs[0]


def test_placement_transitions_win():
    placed = {"flashes": [9.9], "transitions": [{"t": 1.0, "kind": "black", "ms": 33}, {"t": 2.0, "kind": "cut"}]}
    tr = RB.transitions_of(_cuts([1.0, 2.0]), _st(transition={"kinds": {"zoomblur": 1.0}, "ms": 200}), placed)
    assert [(e["t"], e["kind"]) for e in tr] == [(1.0, "black")]      # 옛 flashes·판 비율보다 placement 가 이긴다, cut 은 그릴 것 없음


def test_unknown_kind_raises():
    with pytest.raises(RB.StageError):
        RB.transitions_of(_cuts([1.0]), _st(), {"transitions": [{"t": 1.0, "kind": "spin"}]})


def test_window_fx_off_is_empty():
    assert RB.window_fx([], 216, 216) == ""
    assert RB.window_fx([{"t": 1.0, "kind": "flash", "ms": 100}], 216, 216) == ""      # 흰 번쩍은 화면 전체(render_base) 몫


# ── A1 실제 그림(합성 영상에 ffmpeg) ─────────────────────────────────────
def _src(tmp: Path) -> Path:
    p = tmp / "win.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=s=216x216:r={FPS}:d=2", "-c:v", "libx264", "-crf", "16",
                    "-pix_fmt", "yuv420p", str(p)], check=True, stdin=subprocess.DEVNULL)
    return p


def _apply(src: Path, fx: str, out: Path) -> Path:
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-filter_complex", fx, "-map", "[v]", "-frames:v", str(2 * FPS), "-c:v", "libx264",
                    "-crf", "16", "-pix_fmt", "yuv420p", str(out)], check=True, stdin=subprocess.DEVNULL)
    return out


def frames_gray(p: Path, w: int, h: int, crop=None) -> np.ndarray:
    vf = (f"crop={crop[2]}:{crop[3]}:{crop[0]}:{crop[1]}," if crop else "") + "format=gray"
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-vf", vf, "-f", "rawvideo", "-"], capture_output=True,
                         stdin=subprocess.DEVNULL).stdout
    w, h = (crop[2], crop[3]) if crop else (w, h)
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w)


def lap_var(fr: np.ndarray) -> np.ndarray:
    import cv2
    return np.array([cv2.Laplacian(f, cv2.CV_64F).var() for f in fr])


def test_zoomblur_really_blurs(tmp_path):
    src = _src(tmp_path)
    tr = [{"t": 1.0, "kind": "zoomblur", "ms": 200.0}]
    out = _apply(src, RB.window_fx(tr, 216, 216), tmp_path / "zb.mp4")
    a, b = lap_var(frames_gray(src, 216, 216)), lap_var(frames_gray(out, 216, 216))
    band = slice(round(0.92 * FPS), round(1.08 * FPS))           # 경계 ±0.08초(띠 0.2초 안쪽)
    drop = 1 - b[band].mean() / a[band].mean()
    assert drop >= 0.30, drop
    far = np.r_[0:round(0.7 * FPS), round(1.3 * FPS):2 * FPS]    # 띠 밖은 그대로(재인코딩 오차만)
    assert abs(1 - b[far].mean() / a[far].mean()) < 0.05


def test_black_frame_drawn(tmp_path):
    src = _src(tmp_path)
    out = _apply(src, RB.window_fx([{"t": 1.0, "kind": "black", "ms": 33.0}], 216, 216), tmp_path / "bk.mp4")
    fr = frames_gray(out, 216, 216)
    assert fr[FPS].mean() < 20                                   # 경계 프레임(30) = 검정
    assert fr[FPS - 1].mean() > 60 and fr[FPS + 1].mean() > 60   # 앞뒤 프레임은 그대로


def test_transition_drop_same_ruler(tmp_path):
    """⑯ 자: 경계 띠 vs 앞뒤 바탕 — 줌블러 입힌 영상은 크게 떨어지고(≥0.5) 안 입힌 영상은 거의 0. 마스크로 뺀 픽셀은 안 센다."""
    src = _src(tmp_path)
    fx = _apply(src, RB.window_fx([{"t": 1.0, "kind": "zoomblur", "ms": 200.0}], 216, 216), tmp_path / "zb.mp4")
    a = RB.transition_drop(fx, [1.0], [0, 0, 216, 216])[0]
    b = RB.transition_drop(src, [1.0], [0, 0, 216, 216])[0]
    assert a["drop"] >= 0.5 and abs(b["drop"]) < 0.1, (a, b)
    assert 100 <= a["ms"] <= 300 and b["ms"] == 0
    whole = RB.rect_mask_of([[0, 0, 216, 216, 0, 9]], [0, 0, 216, 216])        # 다 가리면 잴 픽셀 없음 → nan
    assert RB.transition_drop(fx, [1.0], [0, 0, 216, 216], whole)[0]["drop"] != RB.transition_drop(fx, [1.0], [0, 0, 216, 216], whole)[0]["drop"]


def test_render_marks_and_line_cps():
    from tools.calcopy.hybrid import render_itssum as RI
    m = RB.render_marks("키치잇판", RB.__file__)
    import hashlib
    assert m["style_sha"] == hashlib.sha256((ROOT / "tools/calcopy/hybrid/styles/키치잇판.json").read_bytes()).hexdigest()
    assert m["renderer_sig"].startswith("render_bench@") and len(m["style_sha_effective"]) == 12
    assert RI.CPS_LINE_TOL == 0.35
    assert RI.line_cps([{"id": "n1", "chars": 14, "dur": 2.0}, {"id": "n2", "chars": 7, "dur": 0}]) == {"n1": 7.0}


def test_flash_expression_unchanged(monkeypatch, tmp_path):
    """흰 번쩍은 옛 길(flashes → render_base geq 식)과 같은 글자로 나와야 한다(장치 안 켠 판 그림 불변)."""
    cmds = []
    monkeypatch.setattr(RB, "run", lambda c, **k: cmds.append([str(x) for x in c]))
    monkeypatch.setattr(RB, "frame_png", lambda S, st, out: out)
    T = {"cuts": [{"frames": 60}]}
    st = {"frame": {"window": [0, 420, 1080, 1080], "flash_sec": 0.1}}
    RB.render_base({}, T, st, {"flashes": [0.5]}, tmp_path, tmp_path / "w.mp4")
    fc = cmds[-1][cmds[-1].index("-filter_complex") + 1]
    old = "between(T,0.500,0.600)*(1-(T-0.500)/0.1)"                # 옛 render_base 의 식 그대로
    assert f"geq=lum='min(255,lum(X,Y)+255*({old}))'" in fc


# ── 03 연결: 자리 검출·짤 ──────────────────────────────────────────────
def test_needs_locate_only_for_target_rules():
    assert not RB.needs_locate({"placement": {"rules": {"stickers": {"gem": {"lex": ["lux"]}}}}})          # 옛 규칙(자리 없음)
    assert RB.needs_locate({"placement": {"rules": {"stickers": {"circle_arrow": {"target": "face"}}}}})
    assert RB.needs_locate({"placement": {"rules": {"meme": {"rate": 0.3}}}})                               # 짤 기본 자리 = caption_side
    assert not RB.needs_locate({"placement": {"rules": {"meme": {"rate": 0}}}})


def test_meme_overlay_and_caption_rows_split():
    placed = {"rows": [{"line": "n1", "t0": 2.0, "show": [2.0, 3.0], "text": "가", "speaker": "narr", "enter": "cut", "stickers": [
        {"kind": "meme", "src": "m.mp4", "len_s": 1.2, "x": 50.0, "y": 50.0, "w": 300, "h": 300, "site": "detected"},
        {"kind": "meme", "src": "p.mp4", "site": "pending"},
        {"kind": "circle_arrow", "site": "pending", "target": {"kind": "face"}},
        {"kind": "circle_arrow", "site": "detected", "x": 40.0, "y": 30.0}]}]}
    assert RB.meme_overlays(placed) == [{"src": "m.mp4", "t0": 2.0, "len": 1.2, "box": [390, 810, 300, 300]}]   # 자리 못 받은 짤은 안 그림
    rows = RB.caption_rows(placed, {"caption": {}})
    assert [s["kind"] for s in rows[0]["stickers"]] == ["circle_arrow"] and rows[0]["stickers"][0]["x"] == 40.0   # 짤·pending 은 자막팩에 안 감


# ── B1 틀 종류 ─────────────────────────────────────────────────────────
POST = {
    "kind": "post", "bg": [95, 95, 95], "window": [0, 760, 1080, 1056],
    "post": {"head_bar": {"box": [0, 0, 1080, 234], "color": "#0F3B5F",
                          "icons": [{"kind": "bars", "x": 79, "ys": [130, 160, 193], "w": 88, "h": 10, "color": "#000002"},
                                    {"kind": "search", "x": 904, "y": 128, "size": 84, "stroke": 7, "color": "#000000"}]},
             "rules": [{"box": [0, 236, 1080, 240], "color": "#240400"}, {"box": [60, 446, 1020, 451], "color": "#111313"}],
             "author_line": {"text": "골방 | 14:25", "font": "Pretendard-SemiBold.otf", "px": 36, "color": "#222121", "x": 125, "cy": 392},
             "body_box": {"box": [0, 540, 1080, 802], "color": "#FDFDFD", "fade": [56, 74],
                          "rules": [{"box": [0, 583, 1080, 585], "color": "#3C3C3C"}, {"box": [0, 736, 1080, 737], "color": "#3C3C3C"}],
                          "text": {"text": "본문 한 줄", "font": "Pretendard-Regular.otf", "px": 53, "color": "#000000", "cx": 540, "cy": 658}}},
    "title": [],
}


def _png(F, S, tmp):
    from PIL import Image
    p = RB.frame_png(S, {"frame": F}, tmp / "f.png")
    return np.asarray(Image.open(p).convert("RGBA")).astype(int)


def test_post_frame_draws_board(tmp_path):
    a = _png(POST, {"title_lines": []}, tmp_path)
    assert tuple(a[20, 540][:3]) == (0x0F, 0x3B, 0x5F)                 # 머리띠
    assert tuple(a[238, 540][:3]) == (0x24, 0x04, 0x00)                # 머리띠 밑 줄
    assert tuple(a[700, 20][:3]) == (0xFD, 0xFD, 0xFD)                 # 본문 상자(번짐 밖 가운데)
    assert a[545, 20][3] == 255 and a[545, 20][0] < 120                # 번짐 시작(바탕 회색 쪽)
    assert a[1300, 540][3] == 0                                        # 창 = 투명
    assert tuple(a[1870, 540][:3]) == (95, 95, 95)                     # 바탕
    ink = (a[372:412, 125:400, :3].sum(2) < 300).sum()                 # 작성자 줄 잉크
    assert ink > 200


def test_post_frame_script_text_wins(tmp_path):
    a = _png(POST, {"title_lines": [], "post": {"author": "다른채널 | 09:00"}}, tmp_path)
    b = _png(POST, {"title_lines": []}, tmp_path)
    assert np.abs(a[372:412] - b[372:412]).sum() > 0                   # 대본 post.author 가 판 칸 글을 이긴다
    assert np.abs(a[:300] - b[:300]).sum() == 0


def test_post_views_line_and_meme_slot(tmp_path):
    from PIL import Image
    meme = tmp_path / "m.png"
    Image.new("RGB", (40, 20), (200, 30, 30)).save(meme)
    F = {**POST, "post": {**POST["post"], "views_line": {"text": "조회수 1.2만", "font": "Pretendard-Regular.otf", "px": 30, "color": "#FFFFFF",
                                                         "x": 125, "cy": 500},
                          "meme_slot": {"box": [800, 300, 200, 120]}}}
    a = _png(F, {"title_lines": [], "post": {"meme": str(meme)}}, tmp_path)
    assert tuple(a[360, 900][:3]) == (200, 30, 30)                       # 짤 자리 = 대본 post.meme 채워 자르기
    assert (a[485:515, 125:300, :3].min(2) > 200).sum() > 50              # 조회수 줄(흰 글)
    b = _png(F, {"title_lines": []}, tmp_path)
    assert tuple(b[360, 900][:3]) == (95, 95, 95)                         # 짤 없으면 바탕 그대로


def test_full_frame_is_transparent_window(tmp_path):
    F = {"kind": "full", "bg": [0, 0, 0], "full": {"band": {"cy": 1200, "h": 200, "rgba": [0, 0, 0, 128]}}}
    a = _png(F, {}, tmp_path)
    assert a[600, 540][3] == 0 and a[1900, 10][3] == 0                 # 화면 전체가 창
    assert a[1200, 540][3] == 128                                      # 가운데 자막 띠
    assert RB.frame_window(F) == [0, 0, 1080, 1920]


def test_unknown_frame_kind_raises():
    with pytest.raises(RB.StageError):
        RB.frame_kind({"kind": "poster"})


def test_window_kind_default():
    assert RB.frame_kind({"window": [0, 0, 1, 1]}) == "window"


def test_devices_marker():
    st = {"frame": {"window": [0, 0, 1, 1]}, "cuts": {"transition": {"kinds": {"cut": 1.0}}}, "bgm": {"duck_narr_db": -8}}
    d = RB.devices(st, [{"t": 1, "kind": "zoomblur", "ms": 200}], {"bed": {"narr_vs_gap": -8.0}})
    assert d == {"transition": {"kinds_set": {"cut": 1.0}, "drawn": {"zoomblur": 1}, "n": 1},
                 "duck_narr": {"db": -8.0, "bed": {"narr_vs_gap": -8.0}}, "frame_kind": "window"}


def test_bed_contrast(tmp_path):
    """BGM 만 트랙에서 나레 구간이 −8dB 면 narr_vs_gap ≈ −8."""
    import wave
    sr = 48000
    t = np.arange(int(4 * sr)) / sr
    x = 0.3 * np.sin(2 * np.pi * 440 * t)
    x[(t >= 1) & (t < 2)] *= 10 ** (-8 / 20)
    p = tmp_path / "bed.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((x * 32767).astype("<i2").tobytes())
    r = RB.bed_contrast(p, [[1.0, 2.0]], [], 4.0)
    assert abs(r["narr_vs_gap"] + 8.0) < 0.2, r


# ── 2차 장치(07 요청): 구간 틀 · 나레 없는 편 · 자막 쌓기 · 제목 정렬·자간 · 둥근 창 · 컷 그림 칸 · 그림 아이콘·글로우 ──────────
def _S2():
    return {"lines": [{"id": "N1", "kind": "tts", "tts": "첫 줄 글.", "caps": ["첫 줄 글"]}, {"id": "O1", "kind": "orig", "src": "a.mp4", "span": [0, 1]},
                      {"id": "N2", "kind": "tts", "tts": "둘째 줄.", "caps": ["둘째 줄"]}]}


def _T2():
    return {"lines": {"N1": [0.0, 1.62], "O1": [1.72, 2.72], "N2": [2.82, 4.0]}, "end": 4.3333}


def test_frame_segments_resolve():
    st = {"frame": {"kind": "window", "bg": [0, 0, 0], "window": [0, 400, 1080, 1080], "title": [{"px": 50}],
                    "segments": [{"t0": 0, "t1": "#1.end", "frame": {"kind": "post", "bg": [95, 95, 95], "window": [0, 760, 1080, 1056]},
                                  "captions": "hide", "body_text": "lines"},
                                 {"t0": "N2.start", "t1": 99, "frame": {"kind": "full"}}]}}
    g = RB.frame_segments(_S2(), _T2(), st)
    assert [(x["t0"], x["t1"], x["kind"]) for x in g] == [(0.0, round(round(1.62 * FPS) / FPS, 4), "post"), (2.8333, 4.3333, "full")]
    assert g[0]["frame"]["title"] == [{"px": 50}] and "segments" not in g[0]["frame"]        # 판 틀 위에 깊게 덮음(목록은 대신)
    assert g[0]["window"] == [0, 760, 1080, 1056] and g[1]["window"] == [0, 0, 1080, 1920]
    assert g[0]["body_text"] == "첫 줄 글." and g[0]["captions"] == "hide" and g[1]["body_text"] is None
    assert RB.frame_segments(_S2(), _T2(), {"frame": {"window": [0, 0, 1, 1]}}) == []
    for bad in ([{"t0": 0, "t1": 2}, {"t0": 1, "t1": 3}], [{"t0": 0, "t1": "N9.end"}], [{"t0": 0, "t1": 1, "captions": "x"}], [{"t0": 2, "t1": 1}]):
        with pytest.raises(RB.StageError):
            RB.frame_segments(_S2(), _T2(), {"frame": {"window": [0, 0, 1, 1], "segments": bad}})


def test_segment_switches_frame_in_render(tmp_path):
    """구간 틀이 실제로 화면에 그려지나(ffmpeg 진짜로): 0~0.5초 = 구간 틀(바탕 회색 95·창 아래쪽), 그 뒤 = 판 틀(바탕 빨강·창 위쪽)."""
    win = tmp_path / "win.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=0x00FF00:s=1080x600:r={FPS}:d=1", "-c:v", "libx264", "-pix_fmt",
                    "yuv420p", str(win)], check=True, stdin=subprocess.DEVNULL)
    st = {"frame": {"bg": [255, 0, 0], "window": [0, 200, 1080, 600], "title": [],
                    "segments": [{"t0": 0, "t1": 0.5, "frame": {"bg": [95, 95, 95], "window": [0, 1000, 1080, 800]}}]}}
    T = {"cuts": [{"frames": FPS}], "end": 1.0, "lines": {}}
    out = RB.render_base({"lines": []}, T, st, {}, tmp_path, win, [])
    fr = subprocess.run(["ffmpeg", "-v", "error", "-i", str(out), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True,
                        stdin=subprocess.DEVNULL).stdout
    v = np.frombuffer(fr, np.uint8).reshape(-1, 1920, 1080, 3).astype(int)
    a, b = v[5], v[25]                                                     # 0.17초(구간 안) · 0.83초(구간 밖)
    assert abs(a[100, 540] - [95, 95, 95]).max() < 12 and a[1400, 540][1] > 200 and a[500, 540][1] < 150   # 구간: 회색 바탕·창 아래(초록)
    assert b[100, 540][0] > 200 and b[500, 540][1] > 200 and b[1400, 540][0] > 200                          # 판: 빨강 바탕·창 위
    assert int(v[14, 1400, 540][1]) > 200 and int(v[15, 1400, 540][0]) > 200                                # 경계 = 15번째 프레임(0.5초)부터 판 틀


def test_caption_hidden_and_stack():
    rows = [{"line": "N1", "t0": 0.0, "t1": 1.0, "text": "가"}, {"line": "N1", "t0": 1.0, "t1": 2.0, "text": "나", "chars": [1.0, 1.5]},
            {"line": "N2", "t0": 2.0, "t1": 3.0, "text": "다"}, {"line": "N2", "t0": 3.0, "t1": 4.0, "text": "라"}]
    h = RB.caption_hidden([dict(r) for r in rows], [{"t0": 0.0, "t1": 1.5, "captions": "hide"}])
    assert [(r["text"], r["t0"]) for r in h] == [("다", 2.0), ("라", 3.0)]                 # 구간 안에서 시작한 덩어리는 통째로(끝 번쩍임 없음)
    h = RB.caption_hidden([dict(r) for r in rows], [{"t0": 1.2, "t1": 2.5, "captions": "hide"}])
    assert [(r["text"], r["t0"], r["t1"]) for r in h] == [("가", 0.0, 1.0), ("나", 1.0, 1.2), ("라", 3.0, 4.0)] and h[1]["chars"] == [1.0]
    assert RB.caption_hidden([dict(r) for r in rows], [{"t0": 0, "t1": 9, "captions": "show"}]) == rows
    st = {"caption": {"stack": {"lines": 2, "break": "full"}}}
    s = RB.stack_rows([dict(r) for r in rows], st)
    assert [r["text"] for r in s] == ["가", "가\n나", "다", "다\n라"] and "chars" not in s[1] and "place" not in s[0]
    s = RB.stack_rows([dict(r) for r in rows], {"caption": {"stack": {"lines": 3, "break": "line", "y": 500, "pitch": 100}}})
    assert [r["text"] for r in s] == ["가", "가\n나", "다", "다\n라"]                # 대본 줄이 바뀌면 지운다
    assert [r["place"]["y"] for r in s] == [round(500 / 1920 * 100, 3), round(550 / 1920 * 100, 3)] * 2    # 첫 줄 제자리 = 덩어리 가운데 내림
    assert RB.stack_rows([dict(r) for r in rows], {"caption": {}}) == rows
    with pytest.raises(RB.StageError):
        RB.stack_rows([dict(r) for r in rows], {"caption": {"stack": {"lines": 2, "y": 500}}})


def test_sub_lines_timeline_no_tts():
    """나레 없는 자막 줄(kind sub): dur·s0 그대로 시간표 — 컷은 재료 컷(w 비례), 자막은 narr 꼴."""
    S = {"lines": [{"id": "S1", "kind": "sub", "dur": 2.0, "caps": [{"text": "가나", "s0": 0}, {"text": "다라마", "s0": 0.8}]},
                   {"id": "S2", "kind": "sub", "dur": 1.5, "caps": ["바사", "아자차카"]}]}
    M = {"cuts": {"S1": [{"src": "x.mp4", "ss": 1.0}], "S2": [{"src": "x.mp4", "ss": 5.0, "w": 1}, {"src": "x.mp4", "ss": 9.0, "w": 1}]}}
    st = {"timing": {"gap_after_tts": 0.2, "tail": 0.3}}
    T = RB.timeline(S, M, st, None, None)
    assert T["lines"] == {"S1": [0.0, 2.0], "S2": [2.2, 3.7]}
    assert [(r["text"], r["t0"], r["speaker"]) for r in T["rows"]] == [("가나", 0.0, "narr"), ("다라마", 0.8, "narr"), ("바사", 2.2, "narr"), ("아자차카", 2.7, "narr")]
    assert [c["t0"] for c in T["cuts"]] == [0.0, 2.2, 3.1] and T["opos"] == []
    with pytest.raises(RB.StageError):
        RB.timeline({"lines": [{"id": "Z", "kind": "song"}]}, {"cuts": {}}, st, None, None)


def test_audio_without_narration(tmp_path):
    """나레·원음 0 인 편: 목소리 자리 무음, 배경음 크기 기준 = 판 목표 음량 — 소리가 실제로 나온다(마스터 −14 근처)."""
    from tools.calcopy.hybrid import styles as ST
    st = ST.load("잇템로그판")
    T = {"end": 3.0, "lines": {}, "opos": []}
    mix, A = RB.audio({}, {"cand_dir": str(tmp_path)}, st, T, [], {"sfx": []}, tmp_path)
    assert A["bgm_ref"] == "target" and A["narr_lufs"] != A["narr_lufs"]
    assert abs(A["mix"][0] - st["loudness"]["lufs"]) < 1.5, A["mix"]
    assert RB.dur_of(mix) == pytest.approx(3.0, abs=0.05)


def _ink_box(a, y0, y1, dark=True):
    m = (a[y0:y1, :, :3].sum(2) < 200) if dark else (a[y0:y1, :, :3].min(2) > 200)
    ys, xs = np.where(m)
    return (int(xs.min()), int(ys.min()) + y0, int(xs.max()), int(ys.max()) + y0) if len(xs) else None


def test_title_align_and_letter_spacing(tmp_path):
    base = {"font": "Pretendard-Bold.otf", "px": 70, "center": 300, "color": "#000000", "max_w": 1000}
    F = lambda sp: {"bg": [255, 255, 255], "window": [0, 600, 1080, 800], "title": [{**base, **sp}]}
    S = {"title_lines": [[["너무 쉬워 안 까먹는", None]]]}
    c = _ink_box(_png(F({}), S, tmp_path), 250, 350)
    l = _ink_box(_png(F({"align": "left", "x": 71}), S, tmp_path), 250, 350)
    r = _ink_box(_png(F({"align": "right", "x": 1000}), S, tmp_path), 250, 350)
    w = _ink_box(_png(F({"letter_spacing": 6}), S, tmp_path), 250, 350)
    assert abs(l[0] - 71) <= 2 and abs(r[2] - 1000) <= 2 and abs((c[0] + c[2]) / 2 - 540) <= 2
    assert l[2] - l[0] == c[2] - c[0]                                        # 정렬만 바뀌고 글은 같다
    assert (w[2] - w[0]) - (c[2] - c[0]) == pytest.approx(6 * (len("너무쉬워안까먹는") + 3 - 1), abs=4)   # 글자 사이(빈칸 포함) 10곳 × 6px
    with pytest.raises(RB.StageError):
        _png(F({"align": "middle"}), S, tmp_path)


def test_window_radius_corners(tmp_path):
    F = {"bg": [243, 243, 243], "window": [19, 541, 1022, 746], "window_radius": 60, "title": []}
    a = _png(F, {}, tmp_path)
    assert a[541, 19][3] == 255 and tuple(a[541, 19][:3]) == (243, 243, 243)       # 모서리 = 틀 바탕
    assert a[541 + 8, 19 + 8][3] == 255 and a[541 + 30, 19 + 30][3] == 0 and a[541 + 60, 19 + 60][3] == 0   # 곡선 밖 모서리 = 바탕 · 안쪽 = 투명(창)
    assert a[541, 540][3] == 0 and a[541 + 745, 540][3] == 0                         # 위·아래 가장자리 가운데 = 창
    b = _png({**F, "window_radius": 0}, {}, tmp_path)
    assert b[541, 19][3] == 0                                                       # 칸 없으면 옛 네모 창


def test_pic_box_clip(tmp_path):
    """컷 그림 칸: 창 1080×600 중 [200,100,600,400] 에만 그림, 나머지는 pic_bg 색 — 실제 조각 프레임을 본다."""
    src = tmp_path / "s.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=0x00FF00:s=640x360:r={FPS}:d=1", "-c:v", "libx264", "-pix_fmt",
                    "yuv420p", str(src)], check=True, stdin=subprocess.DEVNULL)
    pb = RB.pic_box({"pic": [200, 100, 601, 401]}, (1080, 600))
    assert pb == [200, 100, 600, 400]                                               # yuv420 짝수
    out = tmp_path / "c.mp4"
    RB.clip(src, 0.0, 10, [0, 0, 640, 360], (1080, 600), out, pic=pb, pic_bg=[30, 30, 200])
    f = frames_gray(out, 1080, 600)
    rgb = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", str(out), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                       capture_output=True, stdin=subprocess.DEVNULL).stdout, np.uint8).reshape(600, 1080, 3).astype(int)
    assert len(f) == 10 and rgb[300, 500][1] > 200 and rgb[50, 50][2] > 170 and rgb[50, 50][1] < 60      # 칸 안 초록 · 칸 밖 파랑 바탕
    assert rgb[300, 190][2] > 170 and rgb[300, 810][2] > 170 and rgb[300, 790][1] > 200
    with pytest.raises(RB.StageError):
        RB.pic_box({"pic": [600, 0, 600, 100]}, (1080, 600))
    assert RB.pic_box({}, (1080, 600)) is None


def test_head_image_icon_glow_stroke(tmp_path):
    from PIL import Image
    ic = tmp_path / "i.png"
    Image.new("RGBA", (10, 10), (250, 10, 10, 255)).save(ic)
    txt = {"kind": "text", "text": "맛템", "font": "Pretendard-Bold.otf", "px": 80, "color": "#FFFFFF", "cx": 540, "cy": 117}
    P = lambda extra: {"kind": "post", "bg": [255, 255, 255], "window": [0, 760, 1080, 1056], "title": [],
                       "post": {"head_bar": {"box": [0, 0, 1080, 234], "color": "#202020", "icons": [{**txt, **extra},
                                                                                                        {"kind": "image", "src": str(ic), "x": 900, "y": 80, "w": 60, "h": 60}]}}}
    plain, glow = _png(P({}), {}, tmp_path), _png(P({"glow": {"px": 8, "color": "#2BFFB0", "strength": 2.0}}), {}, tmp_path)
    assert tuple(plain[110, 930][:3]) == (250, 10, 10)                              # 그림 아이콘 자리
    halo = lambda a: int(((a[:234, :, 1] - a[:234, :, 0]) > 60).sum())             # 초록빛 번짐 픽셀(바탕 회색·글 흰색에는 없음)
    assert halo(plain) == 0 and halo(glow) > 2000
    assert _ink_box(plain, 0, 234, dark=False)[1] == _ink_box(glow, 0, 234, dark=False)[1]          # 글 잉크 자리 그대로(번짐만 밖으로)
    stroked = _png(P({"stroke": {"px": 4, "color": "#FF0000"}}), {}, tmp_path)
    assert int(((stroked[:234, :, 0] > 200) & (stroked[:234, :, 1] < 60)).sum()) > int(((plain[:234, :, 0] > 200) & (plain[:234, :, 1] < 60)).sum()) + 500
    with pytest.raises(RB.StageError):
        _png({**P({}), "post": {"head_bar": {"box": [0, 0, 1080, 234], "color": "#202020", "icons": [{"kind": "emoji"}]}}}, {}, tmp_path)


def test_logo_glow(tmp_path):
    LG = {"text": "신박리포트", "font": "Pretendard-ExtraBold.otf", "px": 72, "x": 225, "y": 275, "rgba": [0, 0, 0, 255], "stroke": 0}
    F = lambda lg: {"bg": [243, 243, 243], "window": [19, 541, 1022, 746], "title": [], "logo": lg}
    a, b = _png(F(LG), {}, tmp_path), _png(F({**LG, "glow": {"px": 6, "color": "#FFD27A", "strength": 1.5}}), {}, tmp_path)
    warm = lambda x: int(((x[200:450, :, 0] - x[200:450, :, 2]) > 40).sum())
    assert warm(a) == 0 and warm(b) > 1500


def test_devices_marker_second_round():
    st = {"frame": {"window": [0, 0, 1, 1]}, "caption": {"stack": {"lines": 2}}}
    T = {"cuts": [{"pic": [0, 0, 10, 10]}, {}]}
    g = [{"t0": 0.0, "t1": 1.5, "kind": "post", "window": [0, 760, 1080, 1056], "captions": "hide"}]
    d = RB.devices(st, [], None, g, T, 0)
    assert d["segments"] == [{"t0": 0.0, "t1": 1.5, "kind": "post", "window": [0, 760, 1080, 1056], "captions": "hide"}]
    assert d["caption_stack"] == {"lines": 2} and d["pic_cuts"] == 1 and d["narration"] == 0
    assert set(RB.devices({"frame": {"window": [0, 0, 1, 1]}}, [], None, [], {"cuts": [{}]}, 3)) == {"transition", "duck_narr", "frame_kind"}


# ── 연결(11 팩·15 말속도·07 2차 제목 잇기) ─────────────────────────────────
def test_title_join_draws_all_lines(tmp_path):
    TL = [[["연어로 만든", None]], [["경악한 외국인", None]]]
    assert RB.title_segs({"title": [{"px": 50}]}, {"title_lines": TL}) == [TL[0]]                       # 옛 짝 그대로(칸 1개 = 1줄째만)
    assert RB.title_segs({"title": [{"px": 50, "join": " "}]}, {"title_lines": TL}) == [[["연어로 만든", None], " ", ["경악한 외국인", None]]]
    assert RB.title_segs({"title": [{"px": 50}, {"px": 40}]}, {"title_lines": TL[:1]}) == [TL[0]]
    spec = {"font": "Pretendard-Bold.otf", "px": 60, "center": 300, "color": "#000000", "max_w": 1000}
    F = lambda j: {"bg": [255, 255, 255], "window": [0, 600, 1080, 800], "title": [{**spec, **j}]}
    one, both = _ink_box(_png(F({}), {"title_lines": TL}, tmp_path), 250, 350), _ink_box(_png(F({"join": " "}), {"title_lines": TL}, tmp_path), 250, 350)
    assert (both[2] - both[0]) > (one[2] - one[0]) * 1.6                                               # 두 줄이 한 줄로 그려졌다


def test_snapshot_pack_fields_from_pack_map():
    from tools.calcopy.hybrid import pack_map as PM, styles as ST
    st = ST.load("잇템로그판")
    s = RB.snapshot(st)
    f = PM.snapshot_fields(st)
    assert s["captionPack"] == f["captionPack"] == "ititemlog" and s["motionPack"] == f["motionPack"]
    g = ST.load("_test_mograph")
    assert RB.snapshot(g)["captionPack"] == "ititemlog"                                                 # 그래픽팩은 스냅샷 칸이 아니다(motion_graphics 가 그림)


def test_check_sfx_refuses_unknown_kind():
    st = {"sfx_files": {"pop": "팩01/pop.wav", "gain_db": -8}}
    RB.check_sfx(st, {"sfx": [{"t": 1.0, "kind": "pop"}]})
    with pytest.raises(RB.StageError, match="sfx_files 에 없다"):
        RB.check_sfx(st, {"sfx": [{"t": 1.0, "kind": "whoosh"}]})                                    # 옛: 조용히 팩01/whoosh.wav
    with pytest.raises(RB.StageError, match="파일 없음"):
        RB.check_sfx({"sfx_files": {"pop": "없는팩/pop.wav"}}, {"sfx": [{"t": 1.0, "kind": "pop"}]})


def test_motion_graphics_plan_and_draw(tmp_path):
    from tools.calcopy.hybrid import styles as ST
    T = {"lines": {"N1": [0.0, 1.0], "O1": [1.1, 1.8], "N2": [1.9, 2.6]}}
    assert RB.motion_graphics(ST.load("잇템로그판"), T) is None
    mg = RB.motion_graphics(ST.load("_test_mograph"), T)
    assert [(l["asset_id"], round(l["start"], 2)) for l in mg["layers"]] == [("swipe_left", 0.85), ("swipe_left", 1.65), ("sparkle", 0.0), ("sparkle", 1.9)]
    assert mg["color_filter"].startswith("eq=saturation") and "caption_effect" in mg["not_drawn"]
    with pytest.raises(RB.StageError):
        RB.motion_graphics({"packs": {"motion": {"graphics": "없는팩"}}}, T)
    v = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=0x202020:s=1080x1920:r={FPS}:d=2.6", "-c:v", "libx264", "-pix_fmt",
                    "yuv420p", str(v)], check=True, stdin=subprocess.DEVNULL)
    out = RB.draw_motion_layers(v, mg, tmp_path)
    a = frames_gray(v, 1080, 1920)[:, ::4, ::4].astype(int)
    b = frames_gray(out, 1080, 1920)[:, ::4, ::4].astype(int)
    d = np.abs(a - b).mean(axis=(1, 2))
    assert len(b) == len(a) and d[round(1.0 * FPS)] > 1.0 and d[round(0.6 * FPS)] < d[round(1.0 * FPS)]     # 첫 경계(1.1초) 전후 swipe 가 실제로 그려짐
    assert RB.draw_motion_layers(v, None, tmp_path) == v


def test_render_passes_speech_spread(monkeypatch, tmp_path):
    """15 연결: 판 targets.speech 목표가 make_sentences(spread=…) 로 간다 — 잇템로그판_v2 = 0.063, 잇템로그판 = None."""
    from tools.calcopy.hybrid import render_itssum as RI
    got = {}

    class Stop(Exception):
        pass

    def fake_ms(*a, **k):
        got["spread"] = k.get("spread", "없음")
        raise Stop
    monkeypatch.setattr(RI, "tts_once", lambda S, R, log=print: (R / "n.mp3", None))
    monkeypatch.setattr(RI, "make_sentences", fake_ms)
    d = tmp_path / "doc"
    d.mkdir()
    (d / "대본.json").write_text(json.dumps({"slug": "x", "lines": [{"id": "N1", "kind": "tts", "tts": "가.", "caps": ["가"]}]}, ensure_ascii=False), encoding="utf-8")
    (d / "재료.json").write_text(json.dumps({"cuts": {}}), encoding="utf-8")
    for name, want in (("잇템로그판_v2", 0.063), ("잇템로그판", None)):
        with pytest.raises(Stop):
            RB.render(name, d, tmp_path / name)
        assert got["spread"] == want, (name, got)


def _base_frames(tmp_path, trans, st_extra=None, t_list=()):
    win = tmp_path / "w.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=0x808080:s=1080x1052:r={FPS}:d=2", "-c:v", "libx264", "-crf", "8",
                    "-pix_fmt", "yuv420p", str(win)], check=True, stdin=subprocess.DEVNULL)
    st = {"frame": {"bg": [0, 0, 0], "window": [0, 434, 1080, 1052], "title": []}, **(st_extra or {})}
    out = RB.render_base({}, {"cuts": [{"frames": 2 * FPS}]}, st, {}, tmp_path, win, trans)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(out), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, stdin=subprocess.DEVNULL).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, 1920, 1080, 3)


def test_flash_color_curve_and_colors(tmp_path):
    """㉝ flash = 창 전체 색 덮기(경계 프레임 α → ms 뒤 0, 선형) — 색·α = 사건 칸 > 판 cuts.transition.flash. 색 없으면 옛 흰 번쩍(화면 전체 더하기)."""
    st = {"frame": {"window": [0, 0, 216, 216]}, "cuts": {"transition": {"flash": {"alpha": 0.5, "colors": [[0, 255, 0], [255, 0, 0]]}}}}
    tr = RB.transitions_of({}, st, {"transitions": [{"t": 1.0, "kind": "flash", "ms": 300}, {"t": 1.5, "kind": "flash", "rgb": [0, 0, 255], "alpha": 0.3}]})
    assert [(e["rgb"], e["alpha"], e["ms"]) for e in tr] == [([0, 255, 0], 0.5, 300.0), ([0, 0, 255], 0.3, 100.0)]
    assert "rgb" not in RB.transitions_of({}, {"frame": {}}, {"transitions": [{"t": 1.0, "kind": "flash"}]})[0]      # 판 색 없음 = 옛 흰 번쩍
    with pytest.raises(RB.StageError):
        RB.transitions_of({}, {"frame": {}}, {"transitions": [{"t": 1.0, "kind": "flash", "rgb": [0, 255, 0]}]})     # 색만 있고 α 없음
    v = _base_frames(tmp_path, [{"t": 1.0, "kind": "flash", "ms": 300.0, "rgb": [0, 255, 0], "alpha": 0.5}])
    a = (v[:, 960, 540, 1].astype(float) - v[:, 960, 540, 0]) / 255.0                       # 창 가운데 초록 세기 ≈ α(회색 바탕)
    assert abs(a[29]) < 0.03 and abs(a[30] - 0.5) < 0.05 and abs(a[35] - 0.5 * (1 - 5 / 9)) < 0.05 and abs(a[39]) < 0.03
    assert abs(v[30, 200, 540].astype(int) - v[29, 200, 540]).max() < 3                    # 창 밖(틀)은 안 물듦


def test_edge_glow_same_as_shark(tmp_path):
    """㉝ edge_glow = shark fx 가장자리 빛을 인자 그대로 옮긴 것 — 같은 인자로 그림 픽셀 같음 · α 곡선 같음 · 밝기 맞춤 같음. 1차 판(base 없음)은 거절."""
    from tools.calcopy.shark import fx as FXS
    F = FXS.R()["effects"]["flash"]
    E = {"alpha0": F["edge_alpha0"], "dur": F["edge_dur"], "clear": F["clear"], "soft": F["soft"], "tint": F["tint"], "bright": F["bright"]}
    for luma in (None, 60.0, 130.0, 200.0):
        assert RB.edge_look(luma, E["tint"], E["bright"]) == FXS.flash_look(luma)
    for al, tint in ((0.38, 0.25), (0.2, 0.1)):
        a = np.asarray(RB.edge_glow_image([0, 255, 0], al, 1080, 1044, E["clear"], E["soft"], tint))
        b = np.asarray(FXS.flash_image([0, 255, 0], al, 1080, 1044, tint))
        assert np.array_equal(a, b)
    ev = {"kind": "flash", "T": [1.0, 1.0 + F["dur"]]}
    for k in range(0, 14):
        t = 1.0 + k / FPS
        assert abs(RB.edge_glow_alpha(t - 1.0, E["alpha0"], E["dur"]) - FXS.pose(ev, t)["alpha"]) < 1e-9
    up = {"name": "x", "base": "잇템로그판", "frame": {}, "cuts": {"transition": {"edge_glow": {**E, "colors": [[0, 255, 0]]}}}}
    tr = RB.transitions_of({}, up, {"transitions": [{"t": 1.0, "kind": "edge_glow"}]})
    assert tr[0]["rgb"] == [0, 255, 0] and tr[0]["edge"]["alpha0"] == E["alpha0"] and tr[0]["ms"] == 450.0
    with pytest.raises(RB.StageError, match="업그레이드 판 전용"):
        RB.transitions_of({}, {**up, "base": None}, {"transitions": [{"t": 1.0, "kind": "edge_glow"}]})
    with pytest.raises(RB.StageError, match="칸 모자람"):
        RB.transitions_of({}, {**up, "cuts": {"transition": {"edge_glow": {"colors": [[0, 255, 0]]}}}}, {"transitions": [{"t": 1.0, "kind": "edge_glow"}]})
    v = _base_frames(tmp_path, tr)
    g = v[30, 434:1486].astype(int) - v[29, 434:1486]
    assert g[10, 10, 1] > 40 and abs(g[526, 540]).max() < 3                   # 가장자리는 초록빛, 가운데는 그대로


def test_fx_stickers_drawn_by_shark_fx(tmp_path):
    """꾸밈 스티커(빨간 원) = shark fx 그리기 그대로 render_base 에서 — 자리 받은 것만, 자막팩으로는 안 감."""
    win = tmp_path / "w.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=0x404040:s=1080x1052:r={FPS}:d=1", "-c:v", "libx264", "-pix_fmt",
                    "yuv420p", str(win)], check=True, stdin=subprocess.DEVNULL)
    st = {"frame": {"bg": [0, 0, 0], "window": [0, 434, 1080, 1052], "title": []}}
    rc = {"kind": "red_circle", "x": 500 / 1080 * 100, "y": 676 / 1920 * 100, "site": "detected", "len_s": 0.8}
    placed = {"rows": [{"line": "N1", "t0": 0.0, "show": [0.0, 1.0], "text": "가", "speaker": "narr", "enter": "cut",
                        "stickers": [rc, {**rc, "x": 20.0, "site": "pending"}]}]}
    assert len(RB.fx_effects(placed)) == 1
    out = RB.render_base({}, {"cuts": [{"frames": FPS}]}, st, placed, tmp_path, win, [])
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", "0.6", "-i", str(out), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, stdin=subprocess.DEVNULL).stdout
    f = np.frombuffer(raw, np.uint8).reshape(1920, 1080, 3).astype(int)
    from tools.calcopy.shark import fx_measure as FM
    m = FM.ring(f)
    assert m and abs(m["cx"] - 500) < 3 and abs(m["cy"] - 676) < 3 and m["cover"] > 0.9, m
    assert RB.caption_rows(placed, {"caption": {}})[0]["stickers"] == []      # 자막팩에는 안 감(두 번 그리기 금지)


# ── CLI: 실제 렌더 대조(합격 검사 1·2·3·4) ───────────────────────────────
def _img(p):
    import cv2
    return cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)[:, :, ::-1].astype(int)


def edges(col: np.ndarray, th: float = 10.0) -> list[tuple[int, list]]:
    """세로 한 줄(위→아래)에서 색이 ΔE>th 로 바뀌는 행과 그 아래 색 — 번짐(그러데이션)은 한 행 차가 작아 안 잡힌다."""
    from tools.calcopy.engine.kal_analyze import _lab
    lab = np.array([_lab(c) for c in col])
    d = np.linalg.norm(np.diff(lab, axis=0), axis=1)
    return [(int(i + 1), col[i + 1].tolist()) for i in np.where(d > th)[0]]


def postcmp(ref: str, ours: str, x: int = 20, y1: int = 760, bands=((100, 250), (600, 720))) -> dict:
    """게시글형 틀 대조: 설명서 렌더(preset 렌더) 0초 ↔ 우리 frame_png 0초. 판정 = 글 띠 framecmp 통과 + 가장자리 행 ±4px + 그 아래 색 ΔE<5."""
    from tools.calcopy.engine import kal_analyze as K
    A, B = _img(ref), _img(ours)
    ea, eb = edges(A[:y1, x]), edges(B[:y1, x])
    rows = []
    for y, c in ea:
        near = min(eb, key=lambda e: abs(e[0] - y)) if eb else None
        dE = float(np.linalg.norm(K._lab(c) - K._lab(near[1]))) if near else None
        rows.append({"ref_y": y, "ours_y": near[0] if near else None, "dy": (near[0] - y) if near else None, "ref_rgb": c,
                     "ours_rgb": near[1] if near else None, "dE": round(dE, 1) if dE is not None else None,
                     "pass": bool(near and abs(near[0] - y) <= K.FRAME_PASS["xy_px"] and dE < K.FRAME_PASS["dE"])})
    extra = [e[0] for e in eb if all(abs(e[0] - r["ref_y"]) > K.FRAME_PASS["xy_px"] for r in rows)]
    txt = {f"{b0}-{b1}": K.frame_compare(ref, ours, (b0, b1)) for b0, b1 in bands}
    ok = all(r["pass"] for r in rows) and not extra and all(t["verdict"] == "통과" for t in txt.values())
    return {"x": x, "edges": rows, "ours_extra_edges": extra,
            "text": {k: {"verdict": v["verdict"], "rows": v["rows"]} for k, v in txt.items()}, "ok": ok}


# ── CLI: 실제 렌더 대조(합격 검사 1·2·4) ─────────────────────────────────
def _cli():
    import argparse
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("blur"); b.add_argument("final"); b.add_argument("timeline"); b.add_argument("--window", default="0,420,1080,1080")
    d = sub.add_parser("duck"); d.add_argument("off"); d.add_argument("on")
    f = sub.add_parser("framediff"); f.add_argument("a"); f.add_argument("b"); f.add_argument("--start", type=float, default=0.5)
    f.add_argument("--n", type=int, default=10)
    ab = sub.add_parser("blurab"); ab.add_argument("plain"); ab.add_argument("fx"); ab.add_argument("timeline"); ab.add_argument("--window", default="0,420,1080,1080")
    td = sub.add_parser("tdrop"); td.add_argument("what", choices=["ours", "bench"]); td.add_argument("a"); td.add_argument("b")   # ours <render 폴더> <판> · bench <줄판독.json> <원본.mp4>
    pc = sub.add_parser("postcmp"); pc.add_argument("ref"); pc.add_argument("ours"); pc.add_argument("--x", type=int, default=20)
    pc.add_argument("--y1", type=int, default=760); pc.add_argument("--bands", default="100,250;600,720")
    a = ap.parse_args()
    if a.cmd == "postcmp":
        print(json.dumps(postcmp(a.ref, a.ours, a.x, a.y1, [tuple(int(v) for v in b.split(",")) for b in a.bands.split(";")]), ensure_ascii=False, indent=1))
    if a.cmd == "tdrop":        # ⑯ 같은 자(마스크 뺀 라플라시안 분산 하락·ms 실측)
        r = RB.render_transition_drop(Path(a.a), a.b) if a.what == "ours" else RB.bench_transition_drop(Path(a.a), Path(a.b))
        ds = [b["drop"] for b in r["boundaries"] if b["drop"] == b["drop"]]
        r["median_drop"] = float(np.median(ds)) if ds else None
        r["median_ms"] = float(np.median([b["ms"] for b in r["boundaries"]])) if r["boundaries"] else None
        print(json.dumps(r, ensure_ascii=False))
    if a.cmd == "blurab":       # 같은 편·같은 시각: 장치 끈 판(plain) ↔ 켠 판(fx) — 경계 ±0.1초 띠의 라플라시안 분산이 얼마나 떨어졌나
        x, y, w, h = (int(v) for v in a.window.split(","))
        T = json.loads(Path(a.timeline).read_text(encoding="utf-8"))
        T = T.get("timeline", T)
        lp = lap_var(frames_gray(Path(a.plain), 1080, 1920, (x, y, w, h))[:, ::2, ::2])
        lf = lap_var(frames_gray(Path(a.fx), 1080, 1920, (x, y, w, h))[:, ::2, ::2])
        rows = []
        for c in T["cuts"][1:]:
            n0 = round(c["t0"] * FPS)
            band = slice(max(0, n0 - 3), n0 + 3)
            far = np.r_[max(0, n0 - 12):max(0, n0 - 6), n0 + 6:n0 + 12]
            rows.append({"t": c["t0"], "drop_band": round(float(1 - lf[band].mean() / lp[band].mean()), 3),
                         "drop_far": round(float(1 - lf[far].mean() / lp[far].mean()), 3)})
        print(json.dumps({"boundaries": rows, "median_drop_band": float(np.median([r["drop_band"] for r in rows])),
                          "max_abs_drop_far": float(max(abs(r["drop_far"]) for r in rows))}, ensure_ascii=False))
    if a.cmd == "blur":
        x, y, w, h = (int(v) for v in a.window.split(","))
        T = json.loads(Path(a.timeline).read_text(encoding="utf-8"))
        T = T.get("timeline", T)
        fr = frames_gray(Path(a.final), 1080, 1920, (x, y, w, h))
        lv = lap_var(fr[:, ::2, ::2])
        rows = []
        for c in T["cuts"][1:]:
            n0 = round(c["t0"] * FPS)
            inb = lv[max(0, n0 - 3):n0 + 3].mean()                 # 경계 ±0.1초(띠 0.2초)
            ref = np.r_[lv[max(0, n0 - 12):max(0, n0 - 6)], lv[n0 + 6:n0 + 12]].mean()   # 띠 밖 앞뒤 0.2~0.4초
            rows.append({"t": c["t0"], "band": round(float(inb), 1), "around": round(float(ref), 1), "drop": round(float(1 - inb / ref), 3)})
        print(json.dumps({"boundaries": rows, "median_drop": float(np.median([r["drop"] for r in rows]))}, ensure_ascii=False, indent=1))
    elif a.cmd == "duck":
        off = json.loads((Path(a.off) / "render_info.json").read_text(encoding="utf-8"))["audio"]["bed"]
        on = json.loads((Path(a.on) / "render_info.json").read_text(encoding="utf-8"))["audio"]["bed"]
        print(json.dumps({"off": off, "on": on, "narr_on_minus_off": round(on["narr_db"] - off["narr_db"], 2),
                          "gap_on_minus_off": round(on["gap_db"] - off["gap_db"], 2) if on["gap_db"] is not None else None}, ensure_ascii=False))
    elif a.cmd == "framediff":
        out = []
        for k in range(a.n):
            t = a.start + k
            imgs = []
            for p in (a.a, a.b):
                raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", p, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                     capture_output=True, stdin=subprocess.DEVNULL).stdout
                imgs.append(np.frombuffer(raw, np.uint8).astype(np.int16))
            out.append(round(float(np.abs(imgs[0] - imgs[1]).mean()), 3))
        print(json.dumps({"t": [a.start + k for k in range(a.n)], "mean_abs_diff": out, "mean": round(float(np.mean(out)), 3)}))


if __name__ == "__main__":
    _cli()
