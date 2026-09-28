# -*- coding: utf-8 -*-
"""frame_match 두 띠 거리(dist_any) — 청소본이 원본 **위쪽 글자 띠**를 지워 채운 칸을 '다른 장면'으로 보지 않는다(2026-09-27 fab5e5d4662a).

실측: 같은 프레임인데 가운데 띠(10~70%) 0.65~0.77(=다른 장면), 아래 띠(25~95%) 0.00~0.03. 영상 비교 도구가 청소본 3칸을 다른 장면으로
보고했고, 정본 바로잡기(map_scene_score)도 같은 자라 그 컷을 '안 맞음'으로 셌다.
"""
import subprocess

import numpy as np

from shopping_shorts import frame_match as fm


def _mk(path, vf):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=180x320:r=30:d=2", "-vf", vf,
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True, capture_output=True,
                   stdin=subprocess.DEVNULL)


def test_erased_top_text_band_is_same_scene(tmp_path):
    src = tmp_path / "src.mp4"
    clean = tmp_path / "clean.mp4"
    other = tmp_path / "other.mp4"
    # 원본: 위 12~22% 에 검정 글자 띠 / 청소본: 그 자리를 밝게 채움 / 다른 장면: 좌우 뒤집고 색 돌림
    _mk(src, "drawbox=x=0:y=38:w=iw:h=32:color=black:t=fill")
    _mk(clean, "drawbox=x=0:y=38:w=iw:h=32:color=white@1:t=fill")
    _mk(other, "hflip,vflip,hue=h=150")
    S, C, O = (fm.frames(p) for p in (src, clean, other))
    s1, s2 = fm.feats(S), fm.feats_low(S)
    c1, c2 = fm.feats(C), fm.feats_low(C)
    o1, o2 = fm.feats(O), fm.feats_low(O)
    js = np.arange(28, 33)
    old = float(fm.dist(s1, js, c1[30]).min())
    new = float(fm.dist_any(s1, s2, js, c1[30], c2[30]).min())
    far = float(fm.dist_any(s1, s2, js, o1[30], o2[30]).min())
    assert old >= fm.SCENE_T or old > new, (old, new)   # 가운데 띠만 보면 멀다(또는 적어도 더 멀다)
    assert new < fm.SCENE_T, new                          # 두 띠 중 가까운 쪽 = 같은 장면
    assert far >= fm.SCENE_T, far                         # 진짜 다른 장면은 여전히 다른 장면


def test_dist_any_is_min_of_bands():
    a = np.zeros((3, 4, 4), np.float32)
    b = np.ones((3, 4, 4), np.float32)
    ref_a, ref_b = np.ones((4, 4), np.float32), np.ones((4, 4), np.float32)
    d = fm.dist_any(a, b, [0, 1, 2], ref_a, ref_b)
    assert list(d) == [0.0, 0.0, 0.0]
