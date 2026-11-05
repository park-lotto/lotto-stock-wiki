# -*- coding: utf-8 -*-
"""#464 김용덕 — 재료 시트(fps=0.5 tile 6×5 한 장)는 칸에 초가 없어 '칸 번호×2초'로 읽혔고 실제 클립 초와 어긋났다(원본에서 손으로 프레임을 뽑아 맞춤).
60초 뒤는 시트에 아예 없었다. 주인 runner_ops.mat_sheets — 칸마다 원본 초를 적고, 칸 그림은 렌더와 같은 `-ss t -i`(frame), 원본 전체를 장으로 나눠 덮는다."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import runner_ops as RO  # noqa: E402

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 없음")


def _video(p: Path, sec: int) -> Path:
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc=size=160x90:rate=5:duration={sec}", "-pix_fmt", "yuv420p", str(p)], check=True)
    return p


def test_sheet_covers_whole_source_in_pages(tmp_path):
    v = _video(tmp_path / "a.mp4", 70)
    pages = RO.mat_sheets(v, tmp_path / "_sheet_a.jpg")
    assert len(pages) == 2 and all(p.exists() for p in pages)        # 36칸(0~70초, 2초) — 옛 시트는 한 장 30칸(60초까지)


def test_c_mat_sheets_lists_every_page(tmp_path):
    _video(tmp_path / "b.mp4", 70)
    out = RO.c_mat_sheets(tmp_path, {"files": ["b.mp4"]})
    assert len(out["sheets"]) == 2


def test_tile_time_is_render_seek_time(tmp_path):
    """칸에 적는 초 t 의 그림 = 렌더처럼 `-ss t -i` 로 뽑은 그림(1초 옆 그림보다 가깝다) — 시트 초와 재료 ss 가 같은 시계.
    옛 시트를 '칸 번호×2초'로 읽으면 이 비교가 1초 어긋난다(fps 필터가 간격 절반 밀린 화면을 낸다)."""
    import numpy as np
    from PIL import Image
    v = tmp_path / "t.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=240x136:rate=30:duration=20", "-pix_fmt", "yuv420p", str(v)], check=True)
    tiles = RO.mat_tiles(v, tmp_path / "tiles")
    assert len(tiles) >= 8
    for t, f in (tiles[3], tiles[7]):
        a = np.asarray(Image.open(f).convert("L"), float)

        def at(x):
            RO.frame(v, x, tmp_path / f"f{x}.jpg")
            return np.asarray(Image.open(tmp_path / f"f{x}.jpg").convert("L").resize(a.shape[::-1]), float)
        same, other = abs(a - at(t)).mean(), min(abs(a - at(t - 1.0)).mean(), abs(a - at(t + 1.0)).mean())
        assert same < other, (t, same, other)


def test_long_source_widens_step(tmp_path):
    v = _video(tmp_path / "c.mp4", 300)
    assert len(RO.mat_sheets(v, tmp_path / "_sheet_c.jpg")) <= RO.MAT_PAGES
