# -*- coding: utf-8 -*-
"""업그레이드 자(tools/calcopy/engine/upgrade_table.py) — 관제 263 지시서 05 합격 검사 2.
픽스처 업그레이드 판(upgrades 2건: scene_fit·cut_rhythm) + 완성본 두 개(fit 평균 5.0/7.5 · 멈춤 1건/0건) → better 가 false/true 로 갈린다.
축 이름이 표준 15종 밖이면 거절 · _diff 만 있는 옛 변형판은 upgrades 꼴로 읽힌다(근거 기록 ×)."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.engine import upgrade_table as U  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 없음")

W, H = 108, 192


def _mp4(dst: Path, freeze: bool):
    """2초 영상 — freeze=True 면 뒤 1초가 같은 그림(멈춤 1건), False 면 끝까지 움직임."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    vf = "tpad=stop_mode=clone:stop_duration=1" if freeze else "null"
    d = 1 if freeze else 2
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s={W}x{H}:r=30:d={d}", "-vf", vf,
                    "-pix_fmt", "yuv420p", str(dst)], check=True, stdin=subprocess.DEVNULL)


def _bench(tmp: Path) -> Path:
    lr = tmp / "줄판독"
    lr.mkdir(parents=True)
    for i, fits in enumerate(([7, 7, 8, 6], [7, 8, 7, 6])):            # 편별 평균 7.0 · 7 미만 0.25 → 중앙 7.0 / 0.25
        lines = [{"t0": k * 0.5, "t1": k * 0.5 + 0.5, "speaker": "나레", "text": "가나다라마바", "fit": f} for k, f in enumerate(fits)]
        (lr / f"b{i}.json").write_text(json.dumps({"id": f"b{i}", "dur": 2.0, "lines": lines}, ensure_ascii=False), encoding="utf-8")
    return lr


def _style(lr: Path, ups: list) -> dict:
    return {"name": "_픽스처_v2", "base": "잇템로그판", "bench": {"channel": "_fixture_none", "line_reads": str(lr)},
            "frame": {"window": [0, 0, W, H]}, "upgrades": ups}


UPS = [{"axis": "scene_fit", "what": "장면↔대사", "why": "픽스처", "source": "test", "expect": "fit 평균↑", "verify": "측정값"},
       {"axis": "cut_rhythm", "what": "멈춤 0", "why": "픽스처", "source": "test", "expect": "멈춤 0", "verify": "측정값"}]


def _episode(tmp: Path, tag: str, fit_mean: float, below: float, freeze: bool) -> tuple[Path, Path]:
    doc, work = tmp / f"doc_{tag}", tmp / f"work_{tag}"
    doc.mkdir(parents=True)
    _mp4(work / "render" / "final.mp4", freeze)
    (doc / "장면대사.json").write_text(json.dumps({"summary": {"n": 8, "judged": 8, "mean": fit_mean, "below_rate": below}}), encoding="utf-8")
    return doc, work


def test_better_splits_false_true(tmp_path):
    lr = _bench(tmp_path)
    st = _style(lr, UPS)
    da, wa = _episode(tmp_path, "a", 5.0, 0.5, freeze=True)
    db, wb = _episode(tmp_path, "b", 7.5, 0.125, freeze=False)
    ra = U.measure(st, da, wa)
    rb = U.measure(st, db, wb)
    ba = {x["axis"]: x["better"] for x in ra["items"]}
    bb = {x["axis"]: x["better"] for x in rb["items"]}
    assert ba == {"scene_fit": False, "cut_rhythm": False}, ra["items"]
    assert bb == {"scene_fit": True, "cut_rhythm": True}, rb["items"]
    a_cut = next(x for x in ra["items"] if x["axis"] == "cut_rhythm")
    assert a_cut["ours"]["freezes"] == 1, a_cut
    assert next(x for x in rb["items"] if x["axis"] == "cut_rhythm")["ours"]["freezes"] == 0
    assert (ra["better_n"], rb["better_n"], rb["total"]) == (0, 2, 2)
    assert rb["gates"]["upgrade"]["ok"] is True and ra["gates"]["upgrade"]["ok"] is False
    out = json.loads((db / "업그레이드_측정.json").read_text(encoding="utf-8"))   # 결과 파일 = 반환값
    assert out["better_n"] == 2 and out["items"][0]["bench"]["mean"] == 7.0


def test_axis_outside_15_rejected(tmp_path):
    lr = _bench(tmp_path)
    d, w = _episode(tmp_path, "x", 7.5, 0.1, freeze=False)
    with pytest.raises(ValueError):
        U.measure(_style(lr, [{"axis": "자막", "what": "옛 축 이름", "why": "x", "source": "x"}]), d, w)


def test_human_and_unmeasured_counted_apart(tmp_path):
    lr = _bench(tmp_path)
    d, w = _episode(tmp_path, "h", 7.5, 0.1, freeze=False)
    (d / "장면대사.json").unlink()                                       # 장면대사 없음 → 미측정(나아짐으로 안 친다)
    ups = [{"axis": "script", "what": "끝 혼잣말", "why": "사장님 컨펌", "source": "커밋"}, {"axis": "scene_fit", "what": "fit", "why": "x", "source": "x"}]
    r = U.measure(_style(lr, ups), d, w)
    assert [x["better"] for x in r["items"]] == ["human", None]
    assert (r["better_n"], r["human_n"], r["unmeasured_n"]) == (0, 1, 1) and r["gates"]["upgrade"]["ok"] is False


def test_diff_only_style_reads_as_upgrades():
    from tools.calcopy.hybrid import styles as ST
    st = ST.load("연예인레시피판")
    ups, src = U.upgrades_of(st)
    assert src == "_diff" and len(ups) == 7, ups
    U.check_axes(ups)
    assert all(not U.evidence_ok(x) for x in ups)                       # _diff 글 = 전후 비교일 뿐 근거(수치·편) 아님
