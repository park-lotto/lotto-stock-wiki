# -*- coding: utf-8 -*-
"""narr_video 페이지 안 다중 컷 — 재료.json shots[i].cuts (관제 097, 10-16 바나나 2편 build_combos 를 엔진 안으로).
판단 주인 = narr_video.shot_pieces. 진짜로 렌더해서(빨강·파랑·회색 합성 영상 + 톤 '나레' + 썰풀다 틀 B) 프레임 색으로 잰다.
  ① 한 자막 페이지(0~1.2초, 톤 나레 실측) 안에서 0.6초에 빨강→파랑으로 바뀐다(경계 앞뒤 프레임 차이)
  ② 마지막 토막은 페이지 끝까지 늘어난다(dur 0.2 를 줘도 1.15초에 파랑)
  ③ 자막 잉크·꾸밈(빨간 원) 좌표·시각은 토막과 무관하게 그대로(회귀)
  ④ 사보타주 대조군: cuts 를 빼면 페이지 안에서 안 바뀐다(이 잣대가 컷 경계를 잡는다는 증거)"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shopping_shorts.tests.test_calcopy_caption_events import FRAME, _frame_at, _tts  # noqa: E402

WIN_Y = 347          # frame_mY video 층 y(창 위 끝) — 창 안 표본 자리
PROBE = (200, 700)   # (x, y) 창 안·자막 띠(1225~1320) 밖
RED_AT = (800, 600)  # 꾸밈 빨간 원 중심(완성본 좌표)


def test_shot_pieces_arithmetic():
    from tools.calcopy.narr_video import shot_pieces
    sh = {"src": "a.mp4", "ss": 5.0, "box": [0, 0, 10, 10], "src_crop": [1, 2, 3, 4],
          "cuts": [{"src": "r.mp4", "ss": 2.0, "dur": 0.9}, {"src": "b.mp4", "ss": 7.0, "dur": 0.4, "src_crop": [9, 9, 9, 9]}]}
    p = shot_pieces(sh, 0.0, 1.8)
    assert [(x["sh"]["src"], round(x["ss"], 3), round(x["t"], 3), round(x["dur"], 3)) for x in p] == [("r.mp4", 2.0, 0.0, 0.9), ("b.mp4", 7.0, 0.9, 0.9)]
    assert "src_crop" not in p[0]["sh"] and p[1]["sh"]["src_crop"] == [9, 9, 9, 9] and p[0]["sh"]["box"] == [0, 0, 10, 10]
    assert all("cuts" not in x["sh"] for x in p)
    q = shot_pieces(sh, 0.5, 1.0)            # 틀 경계로 0.5초 늦게 시작한 컷 — 첫 토막 소스도 0.5초 뒤부터
    assert [(x["sh"]["src"], round(x["ss"], 3), round(x["t"], 3), round(x["dur"], 3)) for x in q] == [("r.mp4", 2.5, 0.5, 0.4), ("b.mp4", 7.0, 0.9, 0.6)]
    assert shot_pieces({"src": "a.mp4", "ss": 5.0}, 0.5, 1.0) == [{"sh": {"src": "a.mp4", "ss": 5.0}, "ss": 5.5, "t": 0.5, "dur": 1.0}]
    r = shot_pieces({"src": "a", "cuts": [{"src": "x", "dur": 0.333}, {"src": "y", "dur": 1}]}, 0, 2)
    assert abs(r[1]["t"] * 30 - round(r[1]["t"] * 30)) < 1e-9   # 토막 경계 = 1/30초 격자


def _build(tmp_path, cuts: bool):
    from tools.calcopy import narr_video
    cand = tmp_path / "cand"; cand.mkdir(exist_ok=True)
    for name, c in (("red", "0xE02020"), ("blue", "0x2040E0"), ("gray", "0x606060")):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={c}:s=1280x720:d=7:r=30", "-pix_fmt", "yuv420p",
                        str(cand / f"{name}.mp4")], check=True)
    tts = tmp_path / "tts.wav"; _tts(tts)
    script = {"final": {"lines": [{"text": "첫 번째 문장이에요."}, {"text": "두 번째 문장이에요."}, {"text": "세 번째 문장이에요."}]}}
    (tmp_path / "s.json").write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")
    first = {"src": "red.mp4", "ss": 0, "full": True,
             "overlays": [{"kind": "red_circle", "size": 120, "stroke": 10, "at": list(RED_AT), "t": [0.8, 1.15]}]}
    if cuts:
        first["cuts"] = [{"src": "red.mp4", "ss": 0, "dur": 0.6}, {"src": "blue.mp4", "ss": 0, "dur": 0.2}]
    mats = {"cand_dir": str(cand), "shots": [first] + [{"src": "gray.mp4", "ss": 0, "full": True}] * 2}
    (tmp_path / "m.json").write_text(json.dumps(mats), encoding="utf-8")
    out = tmp_path / ("out_cuts" if cuts else "out_plain")
    final = narr_video.build({"frames": [{"frame": str(FRAME), "t_end": None}], "script": str(tmp_path / "s.json"), "tts": str(tts),
                              "materials": str(tmp_path / "m.json"), "out": str(out), "chunk": 30, "caption_mode": "replace"})
    tl = json.loads((out / "timeline.json").read_text(encoding="utf-8"))
    return Path(final), tl


def _rgb(final, t, tmp_path, xy=PROBE):
    a = _frame_at(final, t, tmp_path / f"p{t}_{xy[0]}.png")
    return a[xy[1], xy[0]]


@pytest.mark.skipif(not shutil.which("node") or not shutil.which("ffmpeg") or not FRAME.exists(), reason="렌더러(node)·ffmpeg·틀 필요")
def test_cuts_change_picture_inside_one_caption_page(tmp_path):
    final, tl = _build(tmp_path, cuts=True)
    a0, a1 = tl["shots"][0]
    assert a0 == 0.0 and a1 > 1.1, tl["shots"]           # 첫 페이지 = 첫 조각(1.2초) — 컷 경계 0.6초 = 페이지 안
    is_red = lambda c: c[0] > 180 and c[2] < 90          # noqa: E731
    is_blue = lambda c: c[2] > 180 and c[0] < 90         # noqa: E731
    c_a, c_b, c_end = _rgb(final, 0.3, tmp_path), _rgb(final, 0.9, tmp_path), _rgb(final, 1.15, tmp_path)
    assert is_red(c_a), c_a
    assert is_blue(c_b), c_b
    assert is_blue(c_end), f"마지막 토막은 페이지 끝까지(dur 0.2 를 넘어) — {c_end}"
    before, after = _rgb(final, 0.55, tmp_path), _rgb(final, 0.65, tmp_path)
    assert abs(before.astype(int) - after.astype(int)).sum() > 200, (before, after)   # 경계 앞뒤 프레임 차이
    # 회귀: 자막 잉크(페이지 내내) · 꾸밈 빨간 원(컷 안 0.8~1.15초, 파랑 토막 위) 좌표 그대로
    cap = _frame_at(final, 0.9, tmp_path / "cap.png")[1215:1330]
    assert int(((cap[..., 0] > 225) & (cap[..., 1] > 225) & (cap[..., 2] > 225)).sum()) > 500
    ring = _rgb(final, 1.0, tmp_path, (RED_AT[0] + 60 - 5, RED_AT[1]))   # 원 둘레(반지름 60 + 두께 10 의 가운데)
    centre = _rgb(final, 1.0, tmp_path, RED_AT)
    assert ring[0] > 180 and ring[2] < 90, f"빨간 원 둘레가 그 자리에 — {ring}"
    assert is_blue(centre), f"원 안은 파랑(토막 그림) — {centre}"
    assert _rgb(final, 0.7, tmp_path, (RED_AT[0] + 55, RED_AT[1]))[2] > 180, "꾸밈 시작 전(0.7초)엔 원이 없다"


@pytest.mark.skipif(not shutil.which("node") or not shutil.which("ffmpeg") or not FRAME.exists(), reason="렌더러(node)·ffmpeg·틀 필요")
def test_without_cuts_page_does_not_change(tmp_path):
    """대조군(사보타주): cuts 없이 같은 재료면 페이지 안 0.9초도 빨강 — 위 시험의 파랑은 cuts 덕분이다."""
    final, _ = _build(tmp_path, cuts=False)
    c = _rgb(final, 0.9, tmp_path)
    assert c[0] > 180 and c[2] < 90, c
