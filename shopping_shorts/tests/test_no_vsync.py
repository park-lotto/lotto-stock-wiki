"""10-30 설치본 시험: 회원 설치본 ffmpeg 9.0.2 는 -vsync 를 없앴다('Unrecognized option vsync') → 썸네일 검사가 프레임 0개로 읽어
'썸네일 안 들어감' 오판 → 완성본 검사에서 4번 멈춤(사장님 PC ffmpeg 8.1 은 받아서 안 드러남). -fps_mode(5.1+) 만 쓴다."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_no_vsync_in_engine_code():
    bad = []
    for d in ("tools/calcopy", "shopping_shorts"):
        for p in (ROOT / d).rglob("*.py"):
            if "tests" in p.parts or "__pycache__" in p.parts:
                continue
            t = p.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"""["']-vsync["']""", t):
                bad.append(str(p.relative_to(ROOT)))
    assert not bad, f"ffmpeg 9 에 없는 -vsync: {bad}"
