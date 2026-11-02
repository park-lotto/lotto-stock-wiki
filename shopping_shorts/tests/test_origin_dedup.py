"""재업로드(같은 영상 두 파일) 원본은 빼고 간다 — 10-27 run4 a편(720p·1080p 같은 영상)·b편. 판정 주인 runner_ops.same_video·same_frames."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import flow as F  # noqa: E402
from tools.calcopy.hybrid import runner_ops as R  # noqa: E402


def test_same_video_by_shot_bounds():
    a = [3.3, 27.07, 28.13, 68.17, 70.57]
    assert R.same_video(a, 100, [x + 0.05 for x in a], 100.1) == 1.0
    assert R.same_video(a, 100, [1, 9, 15, 40, 77], 100) < 0.8
    assert R.same_video(a, 100, a, 140) == 0.0               # 길이가 다르면 다른 영상


def test_fetched_then_dedup_drops_reupload():
    st = {"log": [], "origins": [{"id": "A", "platform": "tt"}, {"id": "B", "platform": "yt"}], "tries": {}}
    m = {"og_0": {"files": [{"name": "A.mp4", "dur": 105.5}]}, "og_1": {"files": [{"name": "B.mp4", "dur": 105.4}]}}
    r = F.f_of_fetched(st, m, {}, {})
    assert r["do"][0]["cmd"] == "origin_dups" and r["then"] == "of_dedup"
    r2 = F.f_of_dedup(st, {"dups": {"dups": [{"dup": "B.mp4", "of": "A.mp4", "frames": 1.0}]}}, {}, {})
    assert r2 == {"goto": "f_product_sheet"} and [f["name"] for f in st["origin"]["files"]] == ["A.mp4"] and len(st["origins"]) == 1
