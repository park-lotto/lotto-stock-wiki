"""렌더 전 관문 속도(10-26 회원 마스크편 --plan 9분, 98 #132) — 프레임 뽑기 주인 render_bench.cut_frames 를 접촉 시트·관문 ④가 나눠 쓰고,
글자 상자는 프레임 열쇠로 캐시하고, ⑦은 컷끼리 동시에 읽어도 **판정·픽셀이 옛 길(컷마다 따로 ffmpeg)과 같은가**."""
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import render_bench as RB  # noqa: E402
from tools.calcopy.hybrid import thumb as TH  # noqa: E402

WIN = (540, 526)


def _src(tmp_path, name="a.mp4", d=4):
    p = tmp_path / name
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc=s=640x360:r=30:d={d}", "-pix_fmt", "yuv420p", str(p)],
                   check=True, stdin=subprocess.DEVNULL)
    return p


def _clear():
    RB._FRAME_MEMO.clear()
    RB._FRAME_MEMO_N[0] = 0


def test_cut_frames_same_pixels_as_owner_and_read_once(tmp_path, monkeypatch):
    src = _src(tmp_path)
    _clear()
    crop, blur = [100, 20, 300, 292], [[0, 0, 640, 60, 0.5, 1.5]]
    ts = [0.2, 1.0, 1.0 + RB.CONTENT_PAIR, 2.9]
    want = [TH.card_scene_frame({"file": str(src), "ss": t, "crop": crop}, {}, Path("."), WIN, blur=blur)[0] for t in ts]   # 옛 길 = 주인 직접
    calls = []
    real = TH.card_scene_frame
    monkeypatch.setattr(TH, "card_scene_frame", lambda *a, **k: (calls.append(a[0]["ss"]), real(*a, **k))[1])
    got = RB.cut_frames([(src, t, crop, WIN, blur) for t in ts])              # 동시 뽑기
    assert all(np.array_equal(a, b) for a, b in zip(want, got))
    assert sorted(calls) == sorted(ts)
    again = [RB.cut_frame(src, t, crop, WIN, blur) for t in ts]                # 기억 — ffmpeg 다시 안 부른다
    assert len(calls) == len(ts) and all(np.array_equal(a, b) for a, b in zip(want, again))
    os.utime(src, ns=(src.stat().st_atime_ns, src.stat().st_mtime_ns + 10**9))  # 원본이 바뀌면(mtime) 다시 뽑는다
    RB.cut_frame(src, ts[0], crop, WIN, blur)
    assert len(calls) == len(ts) + 1


def test_ocr_cache_gives_same_feats_without_ocr(tmp_path, monkeypatch):
    from shopping_shorts.channelkit import vision as V
    src = _src(tmp_path)
    _clear()
    crop = [100, 20, 300, 292]
    base = RB.cut_content_feats(src, 1.0, 45, crop, WIN)                       # 캐시 없이(옛 길)
    ocr = {}
    first = RB.cut_content_feats(src, 1.0, 45, crop, WIN, ocr=ocr)
    assert len(ocr) == 3 and first == base
    monkeypatch.setattr(V, "text_boxes_scored", lambda im: (_ for _ in ()).throw(AssertionError("캐시가 있는데 다시 잼")))
    _clear()                                                                     # 프레임은 새로 뽑고 글자 상자만 캐시에서
    assert RB.cut_content_feats(src, 1.0, 45, crop, WIN, ocr=ocr) == base


def test_content_gate_keeps_old_cuts_in_cache(tmp_path, monkeypatch):
    src = _src(tmp_path)
    _clear()
    st = {"frame": {"kind": "window", "window": [0, 0, WIN[0], WIN[1]]}}
    M = {"cand_dir": str(tmp_path), "blur": {}}
    cut = lambda ss: {"line": "N1", "src": src.name, "ss": ss, "t0": 0.0, "t1": 1.5, "frames": 45, "crop": [100, 20, 300, 292]}
    R = tmp_path / "R"
    R.mkdir()
    assert RB.cut_content_gate({"cuts": [cut(0.5)]}, M, st, None, R, log=lambda m: None) == []
    assert RB.cut_content_gate({"cuts": [cut(2.0)]}, M, st, None, R, log=lambda m: None) == []
    c = RB.jload(R / "cut_content.json")
    assert len(c) == 2                                                          # 앞 계획 컷도 남는다(대본↔장면을 오가면 돌아온다)
    assert len(RB.jload(R / "cut_ocr.json")) == 6
    monkeypatch.setattr(RB, "cut_content_feats", lambda *a, **k: (_ for _ in ()).throw(AssertionError("캐시 컷을 다시 잼")))
    assert RB.cut_content_gate({"cuts": [cut(0.5), cut(2.0)]}, M, st, None, R, log=lambda m: None) == []


def test_still_gate_parallel_same_as_one_by_one(tmp_path):
    a = _src(tmp_path, "a.mp4")
    b = tmp_path / "b.mp4"         # 멈춘 그림 원본(한 색 3초)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=640x360:r=30:d=3", "-pix_fmt", "yuv420p", str(b)],
                   check=True, stdin=subprocess.DEVNULL)
    st = {"frame": {"kind": "window", "window": [0, 0, WIN[0], WIN[1]]}}
    M = {"cand_dir": str(tmp_path), "blur": {}}
    cuts = [{"line": f"N{i}", "src": s, "ss": 0.2, "t0": 0.0, "t1": 2.0, "frames": 60, "kind": "tts", "crop": [100, 20, 300, 292]}
            for i, s in enumerate(["a.mp4", "b.mp4", "a.mp4", "b.mp4"])]
    one = []
    for k, c in enumerate(cuts):
        one += [x.replace("컷 멈춤 0 ", f"컷 멈춤 {k + 10} ", 1) for x in RB.cut_still_gate({"cuts": [c]}, M, st)]
    many = RB.cut_still_gate({"cuts": cuts}, M, st, ks=[k + 10 for k in range(len(cuts))])
    assert many == one and len(many) == 2 and many[0].startswith("컷 멈춤 11 ") and many[1].startswith("컷 멈춤 13 ")
