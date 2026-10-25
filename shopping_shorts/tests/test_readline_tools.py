# -*- coding: utf-8 -*-
"""줄판독 픽셀 도구 tools/calcopy/engine/readline_tools 시험 (관제 263 지시서 13 · 표준 §11 ⑫).

판단 주인: capseg.capseg(자막 덩어리 경계) · cutdet.cutdet(컷·전환 종류) · px.fill_clusters/ink_box(채움색) ·
          build_lr.build_doc(줄판독 조립) · kal_analyze.readline_measure(frames 연결).
1) 합성 영상(글자 바뀜 1.0초·장면 컷 1.5초)으로 각 도구가 그 시각을 잡는가 — 어디서나 돈다.
2) 재현: 잇템로그 SbWTqCnleC8 원본이 이 PC 에 있으면 옛 산출물(work/lr6 seg_·cut_)·커밋된 줄판독과 같은 값인가.
3) 세션 임시 폴더(scratchpad) 참조 0.
사보타주: 문턱을 바꾸면 1)이 깨지는 것을 확인했다(보고서)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

from tools.calcopy.engine.readline_tools import build_lr, capseg, cutdet, measure, px, rangesheet, red, segsheet, tone  # noqa: E402

TOOLS = ROOT / "tools/calcopy/engine/readline_tools"
FPS = 30
W, H = 1080, 1920
BAND = (1150, 1460)
pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg 없음")


def _frame(i: int) -> "np.ndarray":
    f = np.zeros((H, W, 3), np.uint8)
    f[:] = (90, 90, 90) if i < 45 else (40, 120, 200)        # 1.5초(45프레임)에 장면 컷 — 배경이 바뀐다
    f[300:1000, 200:880] = (30, 200, 60) if i < 45 else (220, 220, 220)
    txt, col = ("AB", (0, 230, 255)) if i < 30 else ("CDEFGH", (255, 255, 255))   # 1.0초에 자막 바뀜(노랑 → 흰)
    org = (300, 1350)
    m = np.zeros((H, W), np.uint8)
    cv2.putText(m, txt, org, cv2.FONT_HERSHEY_SIMPLEX, 4.0, 255, 12, cv2.LINE_8)          # 채움 자리
    f[cv2.dilate(m, np.ones((17, 17), np.uint8)) > 0] = (0, 0, 0)                          # 검정 외곽 약 8px
    f[m > 0] = col                                                                          # 채움
    return f


@pytest.fixture(scope="module")
def synth(tmp_path_factory) -> str:
    d = tmp_path_factory.mktemp("rl")
    mp4 = str(d / "synth.mp4")
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "ultrafast", "-crf", "12", "-pix_fmt", "yuv420p", mp4], stdin=subprocess.PIPE)
    for i in range(90):
        p.stdin.write(_frame(i).tobytes())
    p.stdin.close()
    assert p.wait() == 0
    return mp4


def test_capseg_finds_caption_change(synth):
    segs = capseg.capseg(synth, *BAND)
    bounds = [s["t0"] for s in segs[1:]]
    assert any(abs(b - 1.0) <= 1 / FPS for b in bounds), bounds        # 글자 바뀐 1.0초 ±1프레임
    assert not any(abs(b - 1.5) <= 2 / FPS for b in bounds), bounds    # 배경 컷(1.5초)은 자막 경계가 아니다
    first = next(s for s in segs if s["t1"] <= 1.0 + 1e-6 and s["hex"])
    r, g, b = (int(first["hex"][i:i + 2], 16) for i in (1, 3, 5))
    assert r > 200 and g > 180 and b < 80, first["hex"]                   # 노랑 채움
    assert first["yr"] and BAND[0] <= first["yr"][0] < first["yr"][1] <= BAND[1]


def test_cutdet_finds_scene_cut(synth):
    d = cutdet.cutdet(synth, 0, H)
    ts = [c["t"] for c in d["cuts"]]
    assert any(abs(t - 1.5) <= 1 / FPS for t in ts), ts
    assert d["n"] == 90 and len(d["shots"]) == len(d["cuts"]) + 1


def test_px_fill_and_box(synth):
    r = px.fill_clusters(synth, 0.5, *BAND)
    big = max(r["groups"], key=lambda g: g["n"])
    rr, gg, bb = (int(big["hex"][i:i + 2], 16) for i in (1, 3, 5))
    assert rr > 200 and gg > 180 and bb < 80, big
    b = px.ink_box(synth, 2.0, *BAND)                                   # 흰 글자 상자
    assert b and b["fill"].upper().startswith("#F") and BAND[0] <= b["y"][0] < b["y"][1] <= BAND[1]


def test_segsheet_writes_rows(synth, tmp_path):
    segs = capseg.capseg(synth, *BAND)
    r = segsheet.segsheet(synth, segs, str(tmp_path / "ss"), *BAND)
    assert r["rows"] == len(segs) and r["sheets"] and all(Path(p).stat().st_size > 1000 for p in r["sheets"])


def test_build_lr_helpers():
    cuts = [{"t": 1.5, "t_end": 1.5, "kind": "zoomblur?"}]
    assert build_lr.trans_at(cuts, 1.52) == "zoomblur" and build_lr.trans_at(cuts, 1.0) == "none"
    assert build_lr.cuts_in(cuts, 1.0, 2.0) == [1.5] and build_lr.cuts_in(cuts, 1.48, 2.0) == []
    shots = [{"t0": 0, "t1": 1.5, "chg": 3.0}, {"t0": 1.5, "t1": 3, "chg": 20}]
    assert build_lr.motion_at(shots, 1.0) == "still" and build_lr.motion_at(shots, 2.0) == "cam"
    raw = {"v": [{"t": 1, "isolated": 0.9, "voiced": 0.1}, {"t": 2, "isolated": 0.2, "voiced": 0.1}]}
    assert [e["t"] for e in build_lr.sfx_ok_of(raw, "v")] == [1] and build_lr.sfx_ok_of(raw, "x") == []


def test_build_lr_v2_motion_and_dominant_fill():
    """06 보고 ⑬: v2 샷 motion 을 읽는다 · 강조색 섞인 줄은 최빈 색(흰)이 바탕 글자색."""
    shots = [{"t0": 0, "t1": 2, "chg": 30, "motion": "zoom_in"}, {"t0": 2, "t1": 3, "chg": 2, "motion": "still?"}]
    assert build_lr.motion_at(shots, 1.0) == "zoom_in" and build_lr.motion_at(shots, 2.5) == "still"
    px = np.array([[250, 252, 255]] * 70 + [[20, 240, 245]] * 30, np.float64)     # BGR: 흰 70% + 노랑 30%
    d = build_lr._dominant_hex(px)
    assert d[0] > 200 and d[1] > 200 and d[2] > 200                                  # 흰
    m = np.median(px, 0)
    assert m[0] > 200                                                                 # (중앙값도 이 경우는 흰 — 50:50 근처에서 번진다)
    px2 = np.array([[250, 252, 255]] * 45 + [[20, 240, 245]] * 30 + [[30, 60, 240]] * 25, np.float64)
    assert build_lr._dominant_hex(px2)[0] > 200 and np.median(px2, 0)[0] < 200          # 흰 45%·노랑 30%·빨강 25% → 중앙값은 번진다


def test_kal_analyze_frames_calls_readline(synth, tmp_path):
    from tools.calcopy.engine import kal_analyze as K
    lst = K.frames_cmd(synth, str(tmp_path), BAND[0], BAND[1], 2, 10)
    rl = lst["readline"]
    assert Path(rl["seg"]).exists() and Path(rl["cut"]).exists() and rl["segsheets"] and rl["window"] == [0, H]
    assert any(abs(c["t"] - 1.5) <= 1 / FPS for c in json.loads(Path(rl["cut"]).read_text(encoding="utf-8"))["cuts"])
    lst2 = K.frames_cmd(synth, str(tmp_path / "w"), 0, H, 2, 10)      # 창(큰 띠)만 주면 capseg 는 짐작하지 않고 건너뛴다
    assert "seg" not in lst2["readline"] and "건너뜀" in lst2["readline"]["capseg"] and lst2["readline"]["window"] == [0, H]


def test_bands_for_profile_then_layout():
    b = build_lr.bands_for("ititemlog", {"caption_band": [1257, 1342], "window": [0, 486, 1080, 1434]})
    assert b["cap_band"] == [1150, 1460] and b["window"] == [486, 1920] and "profiles/ititemlog.json" in b["why"]
    b = build_lr.bands_for("__없는채널__", {"caption_band": [1257, 1342], "window": [0, 486, 1080, 1434]})
    assert b["cap_band"] == [1257 - build_lr.CAP_PAD, 1342 + build_lr.CAP_PAD] and b["window"] == [486, 1920]
    b = build_lr.bands_for("__없는채널__", {})
    assert b["cap_band"] is None and b["window"] == [0, 1920]


def test_autoband_finds_caption_rows(synth):
    """합성 영상 자막 글자 행(약 1240~1360)을 핵으로 잡고, 장면 상자(300~1000)는 안 잡는다."""
    from tools.calcopy.engine.readline_tools import autoband
    r = autoband.find_band(synth, "color")
    c0, c1 = r["core"]
    assert 1180 <= c0 and c1 <= 1420 and c1 - c0 >= 40, r
    assert r["band"][0] % 2 == 0 and (r["band"][1] - r["band"][0]) % 2 == 0
    assert r["band"][1] - r["band"][0] >= autoband.TARGET_H - 2 and r["band"][0] < c0 and r["band"][1] > c1   # 한 줄 핵 → 두 줄 자리까지 넓힘


def test_autoband_trims_static_title_rows():
    """넓힌 띠가 고정 글자 행(제목·조회수 줄)에 걸리면 그 바깥까지 줄인다(이븐쇼핑: 띠 370 → 412, 줄판독 경계 0.875 → 1.0)."""
    from tools.calcopy.engine.readline_tools import autoband
    assert autoband._trim_static([370, 602], [452, 520], list(range(330, 402, 2))) == [406, 602]
    assert autoband._trim_static([370, 602], [452, 520], []) == [370, 602]
    assert autoband._trim_static([370, 602], [452, 520], list(range(560, 580, 2)))[1] == 554


def test_kal_step_frames_runs_capseg(synth, tmp_path, monkeypatch):
    """kal.py 흐름: 뜯기 layout 의 caption_band 로 capseg·segsheet 까지 돈다(05 뒤 연결)."""
    from tools.calcopy.engine import kal
    data = tmp_path / "data"
    (data / "zz/src").mkdir(parents=True)
    shutil.copy(synth, data / "zz/src/vv.mp4")
    cdir = tmp_path / "ch"
    (cdir / "뜯기/vv").mkdir(parents=True)
    (cdir / "뜯기/vv/뜯기.json").write_text(json.dumps({"layout": {"window": [0, 0, W, H], "caption_band": [1230, 1360]}}), encoding="utf-8")
    monkeypatch.setattr(kal, "DATA", data)

    class St:
        d = {"slug": "zz"}
        dir = cdir

        def step(self, n):
            return {"outputs": {"ids": ["vv"]}}
    state, out, _ = kal.step_frames(St())
    od = Path(out["dirs"]["vv"])
    lst = json.loads((od / "판독목록_vv.json").read_text(encoding="utf-8"))
    assert (od / "seg_vv.json").exists() and "autoband" in lst["readline"]["bands_why"]          # 프로필 없음 → 편마다 자동 띠
    b0, b1 = lst["readline"]["band"]
    assert b0 <= 1220 and b1 >= 1330 and b1 - b0 <= 400, lst["readline"]
    assert any(abs(s["t0"] - 1.0) <= 1 / FPS for s in json.loads((od / "seg_vv.json").read_text()))


def test_measure_white_caption_and_cut(synth):
    M = measure.measure(synth, *BAND)
    assert len(M["rows"]) == 90 and M["band"] == list(BAND)
    S = measure.summarize(M)
    assert any(abs(c["t"] - 1.5) <= 1 / FPS for c in S["cuts"]), S["cuts"]
    assert S["segs"] and abs(S["segs"][0]["t0"] - 1.0) <= 1 / FPS, S["segs"]     # 노랑(채도 높음)은 흰 글자가 아니다 → 1.0초부터


def test_rangesheet_tiles(synth, tmp_path):
    r = rangesheet.rangesheet(synth, str(tmp_path / "r.jpg"), 0.5, 1.5, 0.1, 5, 0.1)
    assert r["tiles"] == 11 and r["shape"][1] == 5 * 108 and (tmp_path / "r.jpg").stat().st_size > 1000


def test_tone_finds_ding(tmp_path):
    sr = 22050
    t = np.arange(int(sr * 3.0)) / sr
    rng = np.random.default_rng(0)
    x = 0.2 * rng.standard_normal(len(t)) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t))     # 말 비슷한 넓은 잡음
    on = (t >= 1.2) & (t < 1.7)
    x[on] += 0.3 * np.sin(2 * np.pi * 4300 * t[on])                                       # 0.5초 4.3kHz 띵
    wav = tmp_path / "d.wav"
    import wave
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    ev = tone.tone_events(str(wav))
    assert len(ev) == 1 and abs(ev[0]["t"] - 1.2) <= 0.1 and 0.35 <= ev[0]["dur"] <= 0.6 and any(abs(h - 4300) <= 50 for h in ev[0]["hz"]), ev


def test_red_tracks_mark(tmp_path):
    mp4 = str(tmp_path / "red.mp4")
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "ultrafast", "-crf", "12", "-pix_fmt", "yuv420p", mp4], stdin=subprocess.PIPE)
    for i in range(60):
        f = np.full((H, W, 3), 245, np.uint8)                                              # 흰 카드
        if i >= 30:
            cv2.circle(f, (540, 1000), 120, (0, 0, 230), 14)                               # 1.0초부터 빨간 원
        p.stdin.write(f.tobytes())
    p.stdin.close()
    assert p.wait() == 0
    rows = red.red_track(mp4, 0.0, 2.0, 590, 1220)
    before = [r for r in rows if r["t"] < 0.95]
    after = [r for r in rows if r["t"] > 1.05]
    assert before and after and all(r["box"] is None for r in before) and all(r["box"] for r in after)
    x0, y0, x1, y1 = after[0]["box"]
    assert abs((x0 + x1) / 2 - 540) <= 12 and abs((y0 + y1) / 2 - 1000) <= 12 and after[0]["white"] > 0.5


def _write_mp4(path, frames):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "ultrafast", "-crf", "12", "-pix_fmt", "yuv420p", str(path)], stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write(f.tobytes())
    p.stdin.close()
    assert p.wait() == 0


@pytest.fixture(scope="module")
def blurzoom(tmp_path_factory) -> str:
    """0.0~0.13 시작 블러 · 1.0초 컷 · 컷 뒤 8프레임에 걸쳐 풀리는 블러 · 컷 뒤 샷은 줌인(1.0→1.35)."""
    rng = np.random.default_rng(1)
    A = rng.integers(0, 255, (H // 8, W // 8, 3), dtype=np.uint8)
    A = cv2.resize(A, (W, H), interpolation=cv2.INTER_NEAREST)
    B = rng.integers(0, 255, (H // 6, W // 6, 3), dtype=np.uint8)
    B = cv2.resize(B, (W, H), interpolation=cv2.INTER_NEAREST)
    fr = []
    for i in range(30):
        f = A.copy()
        if i < 4:
            f = cv2.GaussianBlur(f, (0, 0), 12 - 2 * i)
        fr.append(f)
    for j in range(60):
        z = 1.0 + 0.35 * j / 59
        M = cv2.getRotationMatrix2D((W / 2, H / 2), 0, z)
        f = cv2.warpAffine(B, M, (W, H), flags=cv2.INTER_LINEAR)
        if j < 8:                                              # 컷 직후 블러가 8프레임에 걸쳐 풀린다 → 옛 '뒤 바탕'(b+5~11)이 흐린 프레임을 품는다
            f = cv2.GaussianBlur(f, (0, 0), 8.0 - j)
        fr.append(f)
    out = tmp_path_factory.mktemp("bz") / "bz.mp4"
    _write_mp4(out, fr)
    return str(out)


def test_cutdet_v2_blur_start_zoom(blurzoom):
    v1 = cutdet.cutdet(blurzoom, 0, H)
    v2 = cutdet.cutdet(blurzoom, 0, H, v2=True)
    c1 = [c for c in v1["cuts"] if abs(c["t"] - 1.0) <= 1 / FPS]
    c2 = [c for c in v2["cuts"] if abs(c["t"] - 1.0) <= 1 / FPS]
    assert c1 and "kind_v1" not in c1[0]                        # v2 없이 = 옛 출력 꼴 그대로(옛 분류가 놓치는 실물은 키치잇 대조 — 합성으로는 재현 못 함)
    assert c2 and c2[0]["kind"] == "zoomblur" and c2[0]["blur_ratio"] <= cutdet.V2_RATIO and c2[0]["blur_rise"] >= cutdet.V2_RISE
    assert v2["cuts"][0].get("start") and v2["cuts"][0]["kind"] == "zoomblur"
    after = [s for s in v2["shots"] if s["t0"] >= 0.99]
    assert after and after[-1]["motion"] == "zoom_in", v2["shots"]
    assert "motion" not in v1["shots"][-1] and "v2" not in v1


def test_cutdet_v2_zoom_out_and_pan(tmp_path):
    rng = np.random.default_rng(2)
    B = cv2.resize(rng.integers(0, 255, (H // 6, W // 6, 3), dtype=np.uint8), (W, H), interpolation=cv2.INTER_NEAREST)
    zo = [cv2.warpAffine(B, cv2.getRotationMatrix2D((W / 2, H / 2), 0, 1.35 - 0.35 * j / 44), (W, H)) for j in range(45)]
    pn = [cv2.warpAffine(B, np.float32([[1, 0, 6 * j], [0, 1, 0]]), (W, H), borderMode=cv2.BORDER_REFLECT) for j in range(45)]
    for name, frames, want in (("zo", zo, "zoom_out"), ("pn", pn, "pan")):
        p = tmp_path / f"{name}.mp4"
        _write_mp4(p, frames)
        d = cutdet.cutdet(str(p), 0, H, v2=True)
        assert d["shots"][0]["motion"] == want, (name, d["shots"])


def test_capseg_dark_and_box_modes(tmp_path):
    """검정 글(흰 상자) 자막: dark·box 모드가 1.0초 교체를 잡는다."""
    fr = []
    for i in range(60):
        f = np.full((H, W, 3), 150, np.uint8)
        cv2.rectangle(f, (120, 1200), (960, 1330), (255, 255, 255), -1)                      # 흰 상자(회색 바탕)
        cv2.putText(f, "AB" if i < 30 else "CDEFG", (200, 1300), cv2.FONT_HERSHEY_SIMPLEX, 3.0, (0, 0, 0), 10, cv2.LINE_8)
        fr.append(f)
    mp4 = tmp_path / "box.mp4"
    _write_mp4(mp4, fr)
    for mode in ("dark", "box"):
        segs = capseg.capseg(str(mp4), 1150, 1380, mode=mode)
        assert any(abs(x["t0"] - 1.0) <= 1 / FPS for x in segs[1:]), (mode, segs)


@pytest.mark.skipif(not (Path("C:/숏템_칼카피/ititemlog/src/SbWTqCnleC8.mp4").exists()), reason="잇템로그 원본 없음(집 PC 전용)")
def test_capseg_odd_band_not_garbage():
    """홀수 높이 띠(1137~1462 = 325줄): exact=1 전엔 ffmpeg 가 324줄로 잘라 프레임이 밀려 경계 38개 중 18개만 맞았다(10-25 실측).
    합성 영상은 단색 바탕이라 밀림이 경계를 안 바꿔 못 잡는다 — 실물로 잰다."""
    ref = [x["t0"] for x in json.loads(Path("C:/숏템_칼카피/ititemlog/work/lr6/seg_SbWTqCnleC8.json").read_text())[1:]]
    got = [x["t0"] for x in capseg.capseg("C:/숏템_칼카피/ititemlog/src/SbWTqCnleC8.mp4", 1137, 1462)[1:]]
    hit = sum(1 for t in ref if any(abs(t - u) <= 1 / FPS + 1e-6 for u in got))
    assert hit / len(ref) >= 0.95, (hit, len(ref))


_HS = Path("C:/숏템_칼카피/humorshowshow")


@pytest.mark.skipif(not (_HS / "work/lr6/mo_bfKkNmVTGPs.json").exists(), reason="유머쇼쇼 원본·옛 산출물 없음(집 PC 전용)")
def test_reproduce_humorshowshow_motion():
    from tools.calcopy.engine.readline_tools import shotmotion
    C = json.loads((_HS / "work/lr6/cut_bfKkNmVTGPs.json").read_text(encoding="utf-8"))
    ref = json.loads((_HS / "work/lr6/mo_bfKkNmVTGPs.json").read_text(encoding="utf-8"))
    r = shotmotion.run(str(_HS / "mp4/bfKkNmVTGPs.mp4"), C, 672, 1550)
    assert r["shots"] == ref["shots"] and r["cuts"] == ref["cuts"]


_KC = Path("C:/숏템_칼카피/kitchit/src")


@pytest.mark.skipif(not (_KC / "vSEaZ-BCELY.mp4").exists(), reason="키치잇 원본 없음(집 PC 전용)")
def test_kitchit_transition_v2():
    """키치잇 눈 정답: vSE 2.467 zoomblur 는 옛 분류가 cut 으로 본 자리 · Ks5k 시작 블러·black 2·zoomblur 1."""
    from tools.calcopy.engine.readline_tools import eval_transition as E
    tot = hit = fp = 0
    for vid in ("vSEaZ-BCELY", "Ks5kYYKAUlQ"):
        e = E.eval_video("kitchit", vid, str(_KC / f"{vid}.mp4"))
        tot += e["total"]; hit += e["hit"]; fp += e["fp"]
    assert tot == 5 and hit == 5 and fp <= 1                       # Ks5k 4.27 cut 을 flash 로 보는 1곳(10-25 실측, 전체 8편 오탐 2/57)


_KK = Path("C:/숏템_칼카피/kkultemnote/src")


@pytest.mark.skipif(not (_KK / "cLk6fJly6OY.mp4").exists(), reason="꿀템노트 원본 없음(집 PC 전용)")
def test_kkultemnote_60fps_and_radial_zoomblur():
    """60fps 원본: 30 으로 맞춰 컷 18(옛 72) · 방사 줌블러(cLk 12.0, 옛 flash)·검정 1프레임+페이드인(KCx 13.4, 옛 zoomblur) — 꿀템노트 눈 정답."""
    from tools.calcopy.engine.readline_tools import eval_transition as E
    assert len(cutdet.cutdet(str(_KK / "m0Ex0y1DN5s.mp4"), 0, 1920)["cuts"]) == 18
    tot = hit = 0
    for vid in ("cLk6fJly6OY", "KCxJ5qJft38"):
        e = E.eval_video("kkultemnote", vid, str(_KK / f"{vid}.mp4"))
        tot += e["total"]; hit += e["hit"]
    assert tot == 3 and hit == 3


@pytest.mark.skipif(not Path("C:/숏템_칼카피/itemhome/원본/cLxEI_U1e_E.mp4").exists(), reason="아이템홈 원본 없음(집 PC 전용)")
def test_itemhome_softfocus_not_zoomblur():
    """소프트포커스 원본(아이템홈 cLx): 옛 v2 규칙(바탕을 다음 컷 넘어 잡음)은 cut 3곳을 zoomblur 로 봤다 → 0."""
    from tools.calcopy.engine.readline_tools import eval_transition as E
    e = E.eval_video("itemhome", "cLxEI_U1e_E", "C:/숏템_칼카피/itemhome/원본/cLxEI_U1e_E.mp4")
    assert e["fp"] == 0 and e["cut_lines"] >= 10, e


_FS = Path("C:/숏템_칼카피/foreignshowshow")


@pytest.mark.skipif(not (_FS / "work/lr6/fs_QMJtjJz4M6w_seg.json").exists(), reason="샤크탱크 원본·옛 산출물 없음(집 PC 전용)")
def test_reproduce_foreignshowshow_shadow_flash_marks():
    from tools.calcopy.engine.readline_tools import marktrack
    mp4 = str(_FS / "src/QMJtjJz4M6w.mp4")
    assert capseg.capseg(mp4, 760, 1200, mode="shadow") == json.loads((_FS / "work/lr6/fs_QMJtjJz4M6w_seg.json").read_text(encoding="utf-8"))
    assert cutdet.color_flash(mp4, 434, 1486) == json.loads((_FS / "work/lr6/fs_QMJtjJz4M6w_flash.json").read_text(encoding="utf-8"))
    assert marktrack.marktrack(mp4, 434, 1486) == json.loads((_FS / "work/lr6/fx_QMJtjJz4M6w.json").read_text(encoding="utf-8"))


_HT = Path("C:/숏템_칼카피/hottemreport")


@pytest.mark.skipif(not (_HT / "work/lr6/th6/OE-11wb7vdY.jpg").exists(), reason="핫템리포트 썸네일 없음(집 PC 전용)")
def test_thumbmatch_hottemreport():
    """06 핫템리포트 손 측정: 썸네일 = OE 12.0초·Zq 18.83초 프레임."""
    from tools.calcopy.engine.readline_tools import thumbmatch
    for vid, t in (("OE-11wb7vdY", 12.0), ("ZqVgAg99gRI", 18.83)):
        r = thumbmatch.thumbmatch(str(_HT / f"mp4/{vid}.mp4"), str(_HT / f"work/lr6/th6/{vid}.jpg"))
        assert abs(r["best_t"] - t) <= 0.2 and r["best_corr"] > 0.9 > r["t0_corr"], r


_EV_SRC = Path("C:/숏템_칼카피/evenshopping/src/kC8fkx1Ve3Q.mp4")
_EV_OLD = Path("C:/숏템_칼카피/evenshopping/work/tone_detect.json")


@pytest.mark.skipif(not (_EV_SRC.exists() and _EV_OLD.exists()), reason="이븐쇼핑 원본·옛 산출물 없음(집 PC 전용)")
def test_reproduce_evenshopping_tone():
    P = json.loads((TOOLS / "profiles/evenshopping.json").read_text(encoding="utf-8"))["tone"]
    assert tone.tone_events(str(_EV_SRC), **P) == json.loads(_EV_OLD.read_text())["kC8fkx1Ve3Q"]


def _tex(seed, cell=8):
    rng = np.random.default_rng(seed)
    return cv2.resize(rng.integers(0, 255, (H // cell, W // cell, 3), dtype=np.uint8), (W, H), interpolation=cv2.INTER_NEAREST)


def test_cutdet_v2_same_shot_base_and_rise(tmp_path):
    """① 컷 뒤 샷이 원래 조금 흐리고(σ2.4→1.6) 12프레임 뒤 아주 선명한 샷으로 넘어가면: 같은 샷 바탕으로 재야 cut(다음 샷 바탕이면 zoomblur 오탐).
    ② 컷 뒤 8프레임 내내 흐리다 그 뒤에야 선명(6프레임째에 안 풀림): rise 조건이 있어야 cut."""
    A, B, C2 = _tex(11), _tex(12), _tex(13)
    fr = [A] * 30
    fr += [cv2.GaussianBlur(B, (0, 0), 2.4 - 0.8 * min(j, 6) / 6) for j in range(12)]   # 같은 샷 비율 0.47·rise 1.87 · 다음 샷 바탕이면 0.20
    fr += [C2] * 30
    p1 = tmp_path / "base.mp4"
    _write_mp4(p1, fr)
    d = cutdet.cutdet(str(p1), 0, H, v2=True, motion=False)
    c = [x for x in d["cuts"] if abs(x["t"] - 1.0) <= 1 / FPS]
    assert c and c[0]["kind"] == "cut", d["cuts"]
    fr = [A] * 30 + [cv2.GaussianBlur(B, (0, 0), 6) for _ in range(8)] + [B] * 30
    p2 = tmp_path / "rise.mp4"
    _write_mp4(p2, fr)
    d = cutdet.cutdet(str(p2), 0, H, v2=True, motion=False)
    c = [x for x in d["cuts"] if abs(x["t"] - 1.0) <= 1 / FPS]
    assert c and c[0]["kind"] == "cut" and c[0]["blur_ratio"] <= cutdet.V2_RATIO, d["cuts"]


def test_cutdet_v2_flash_needs_fade(tmp_path):
    """밝은 장면으로 그냥 컷(+60, 안 어두워짐) = cut · 흰 번쩍 뒤 서서히 어두워짐 = flash."""
    A = (_tex(21) * 0.4).astype(np.uint8)
    Bb = np.clip(A.astype(int) + 90, 0, 255).astype(np.uint8)
    p1 = tmp_path / "bright.mp4"
    _write_mp4(p1, [A] * 30 + [Bb] * 30)
    d = cutdet.cutdet(str(p1), 0, H, v2=True, motion=False)
    c = [x for x in d["cuts"] if abs(x["t"] - 1.0) <= 2 / FPS]
    assert c and c[0]["kind"] != "flash", d["cuts"]
    fl = [np.clip(A.astype(int) + int(150 * (0.8 ** j)), 0, 255).astype(np.uint8) for j in range(30)]
    p2 = tmp_path / "flash.mp4"
    _write_mp4(p2, [A] * 30 + fl)
    d = cutdet.cutdet(str(p2), 0, H, v2=True, motion=False)
    c = [x for x in d["cuts"] if abs(x["t"] - 1.0) <= 2 / FPS]
    assert c and c[0]["kind"] == "flash", d["cuts"]


def test_thumbmatch_landscape_crop(tmp_path):
    """가로 썸네일(16:9, 가운데 세로 프레임 + 양옆 다른 그림): 가운데 9:16 을 잘라야 맞는 프레임(1.5초)·상관 0.9 넘음."""
    from tools.calcopy.engine.readline_tools import thumbmatch
    frames = [_tex(30 + i // 15, 16) for i in range(60)]                 # 0.5초마다 다른 그림
    mp4 = tmp_path / "v.mp4"
    _write_mp4(mp4, frames)
    side = _tex(99, 16)
    tw = int(H * 16 / 9)
    canvas = cv2.resize(side, (tw, H))
    x0 = (tw - W) // 2
    canvas[:, x0:x0 + W] = frames[45]
    tp = tmp_path / "t.jpg"
    cv2.imencode(".jpg", canvas)[1].tofile(str(tp))
    r = thumbmatch.thumbmatch(str(mp4), str(tp))
    assert 1.5 - 0.2 <= r["best_t"] <= 2.0 and r["best_corr"] > 0.9, r


def test_rules_only_no_state_file(tmp_path, monkeypatch):
    """rules_only: kal_state.json 을 만들지 않고 규칙빈도만 낸다(잇템로그 줄판독 2편 사본으로)."""
    sys.path.insert(0, str(ROOT / "tools/calcopy/engine"))
    import kal
    from tools.calcopy.engine.readline_tools import rules_only
    ch = tmp_path / "channel/zz"
    (ch / "줄판독").mkdir(parents=True)
    for v in ("SbWTqCnleC8", "zOSpeiMw1nA"):
        shutil.copy(ROOT / f"channel/ititemlog/줄판독/{v}.json", ch / "줄판독" / f"{v}.json")
    monkeypatch.setattr(kal, "ROOT", tmp_path)
    real = kal.step_rules

    def saving_step(S):                                    # 단계가 저장까지 부른다고 쳐도(kal 본류는 mark→save) 파일이 안 생겨야 한다
        r = real(S)
        S.save()
        return r
    monkeypatch.setattr(kal, "step_rules", saving_step)
    (ch / "_kal").mkdir()
    hand = {"name": "zz판", "bench": {"channel": "@진짜채널", "ko": "진짜"}, "frame": {"window": [0, 486, 1080, 1434], "title": [{"text": "손"}]},
            "voice": {"name": "문정", "voice_id": "tc_abc", "candidates": [], "why": "사장님"}, "caption": {"pack": "손팩"}}
    (ch / "_kal/zz판_초안.json").write_text(json.dumps(hand, ensure_ascii=False), encoding="utf-8")
    st, out, note = rules_only.rules_only("zz", "@zz", ["SbWTqCnleC8", "zOSpeiMw1nA"])
    assert (ch / "_kal/규칙빈도.json").exists() and not (ch / "kal_state.json").exists()
    plan = json.loads((ch / "_kal/zz판_초안.json").read_text(encoding="utf-8"))   # 손칸은 그대로(06 보고: 재집계가 ref·창·목소리를 비웠다)
    assert plan["bench"]["channel"] == "@진짜채널" and plan["frame"]["window"] == [0, 486, 1080, 1434] and plan["voice"]["voice_id"] == "tc_abc"
    assert plan["frame"]["title"] == [{"text": "손"}] and plan["caption"]["pack"] == "손팩" and plan["placement"]["rules"]["fx_rate"]


def test_no_scratchpad_reference():
    hits = [str(p) for p in TOOLS.rglob("*") if p.is_file() and p.suffix in (".py", ".md", ".json")
            and "scratchpad" in p.read_text(encoding="utf-8", errors="replace")]
    assert hits == []


# ---------------------------------------------------------------- 재현(이 PC 에 잇템로그 원본이 있을 때)
_SRC = Path("C:/숏템_칼카피/ititemlog/src/SbWTqCnleC8.mp4")
_LR6 = Path("C:/숏템_칼카피/ititemlog/work/lr6")
_SFX = Path("C:/숏템_칼카피/ititemlog/kal/sfx_raw.json")


@pytest.mark.skipif(not (_SRC.exists() and (_LR6 / "seg_SbWTqCnleC8.json").exists()), reason="잇템로그 원본·옛 산출물 없음(집 PC 전용)")
def test_reproduce_ititemlog_SbW(tmp_path):
    segs = capseg.capseg(str(_SRC), 1150, 1460)
    assert segs == json.loads((_LR6 / "seg_SbWTqCnleC8.json").read_text())
    cd = cutdet.cutdet(str(_SRC), 486, 1920)
    assert cd == json.loads((_LR6 / "cut_SbWTqCnleC8.json").read_text())
    S = build_lr.load_spec(str(TOOLS / "examples/ititemlog_SbW.py"))
    sfx = json.loads(_SFX.read_text(encoding="utf-8")) if _SFX.exists() else None
    doc = build_lr.build_doc(S, segs, cd, str(_SRC), sfx, build_lr.load_profile(str(TOOLS / "profiles/ititemlog.json")))
    ref = json.loads((ROOT / "channel/ititemlog/줄판독/SbWTqCnleC8.json").read_text(encoding="utf-8"))
    if sfx is None:
        pytest.skip("sfx_raw 없음")
    assert [k for k in set(doc) | set(ref) if doc.get(k) != ref.get(k)] == ["_tools"]   # 도구 경로 글만 다르다
