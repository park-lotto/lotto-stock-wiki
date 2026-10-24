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
    pc = sub.add_parser("postcmp"); pc.add_argument("ref"); pc.add_argument("ours"); pc.add_argument("--x", type=int, default=20)
    pc.add_argument("--y1", type=int, default=760); pc.add_argument("--bands", default="100,250;600,720")
    a = ap.parse_args()
    if a.cmd == "postcmp":
        print(json.dumps(postcmp(a.ref, a.ours, a.x, a.y1, [tuple(int(v) for v in b.split(",")) for b in a.bands.split(";")]), ensure_ascii=False, indent=1))
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
