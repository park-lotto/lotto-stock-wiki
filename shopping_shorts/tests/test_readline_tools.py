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

from tools.calcopy.engine.readline_tools import build_lr, capseg, cutdet, px, segsheet  # noqa: E402

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


def test_kal_analyze_frames_calls_readline(synth, tmp_path):
    from tools.calcopy.engine import kal_analyze as K
    lst = K.frames_cmd(synth, str(tmp_path), BAND[0], BAND[1], 2, 10)
    rl = lst["readline"]
    assert Path(rl["seg"]).exists() and Path(rl["cut"]).exists() and rl["segsheets"] and rl["window"] == [0, H]
    assert any(abs(c["t"] - 1.5) <= 1 / FPS for c in json.loads(Path(rl["cut"]).read_text(encoding="utf-8"))["cuts"])
    lst2 = K.frames_cmd(synth, str(tmp_path / "w"), 0, H, 2, 10)      # 창(큰 띠)만 주면 capseg 는 짐작하지 않고 건너뛴다
    assert "seg" not in lst2["readline"] and "건너뜀" in lst2["readline"]["capseg"] and lst2["readline"]["window"] == [0, H]


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
    doc = build_lr.build_doc(S, segs, cd, str(_SRC), sfx, build_lr.load_profile(str(TOOLS / "examples/ititemlog_profile.json")))
    ref = json.loads((ROOT / "channel/ititemlog/줄판독/SbWTqCnleC8.json").read_text(encoding="utf-8"))
    if sfx is None:
        pytest.skip("sfx_raw 없음")
    assert [k for k in set(doc) | set(ref) if doc.get(k) != ref.get(k)] == ["_tools"]   # 도구 경로 글만 다르다
