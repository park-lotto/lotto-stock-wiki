"""10-30 설치본 시험: 재료 받기 형식 '137 없으면 1080 이상 아무거나' → 4K·AV1·60fps 197초 → 장면 계획 해석 120초 시간 초과 3번.
받기 화질 상한 = yt_fetch.SORT_1080(짧은 변 1080·H.264 먼저) 한 곳. 실측: xE-4UURonAY 옛 형식 401(3840x2160 av01) → 새 299(1920x1080 avc1) · 세로 쇼츠 NBdm 137(1080x1920)."""
from pathlib import Path

from tools.calcopy.engine import yt_fetch as YF


def test_full_and_section_downloads_carry_sort(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(YF, "_yt", lambda args, **k: seen.append(args) or None, raising=False)
    src = Path(YF.__file__).read_text(encoding="utf-8")
    assert YF.SORT_1080 == ["-S", "res:1080,vcodec:h264"]
    assert src.count("*SORT_1080") >= 2                     # 통째 받기·구간 받기 둘 다
    ro = (Path(YF.__file__).parents[1] / "hybrid" / "runner_ops.py").read_text(encoding="utf-8")
    assert ro.count("*SORT_1080") >= 2                      # 벤치·틱톡/인스타 원본 받기
