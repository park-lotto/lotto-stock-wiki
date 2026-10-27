"""배치가 '붙일 자리 없음'으로 남긴 스티커 종류는 완성본 배치 검사에서 반려하지 않는다(10-27 run4 c편 원·화살표 0/1 로 2번 반려·멈춤).
주인 = placement.place(sticker_short_why 남김) · placement.check_place(그 종류는 참고)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import placement as P  # noqa: E402


def _style():
    return {"placement": {"counted": {"videos": [{"id": "R", "stickers": {"circle_arrow": 1}, "slots": {}, "sfx": []}], "stickers": {"circle_arrow": 0.5}},
                          "rules": {"stickers": {"circle_arrow": {}}}}}


def test_short_without_reason_fails_with_reason_passes():
    placed = {"reference": "R", "rows": [], "sfx": []}
    bad = P.check_place(dict(placed), _style())
    assert any("circle_arrow" in b for b in bad.get("bad") or [])
    ok = P.check_place({**placed, "sticker_short_why": {"circle_arrow": "후보 2개 중 대상이 덩어리 내내 화면에 있는 곳 0개"}}, _style())
    assert not any("circle_arrow" in b for b in ok.get("bad") or [])
