"""원본 자막 지문(tools/calcopy/hybrid/rules.fingerprint) — 벤치 받아쓰기 토막을 낱말 경계에서 자른다(10-29 얜샷템 최화정 할아버지김).
글자 수로 14자씩 끊던 옛 판은 진짜 원본(RPuDFaMmpJI)에서 1줄만 맞아 회원 길이 '원본 못 찾음'으로 멈췄다(사장님 길은 막힘 과제가 손으로 4줄을 찾아 이어 감).
자료 = tools/calcopy/hybrid/fixtures/fp_choihwajung.json(벤치 받아쓰기 · 원본 0~90초 · 미끼 0~600초 자동자막)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import rules as RU  # noqa: E402

D = json.loads((ROOT / "tools/calcopy/hybrid/fixtures/fp_choihwajung.json").read_text(encoding="utf-8"))


def test_real_origin_matches_two_lines_in_first_90s():
    m = RU.fingerprint(D["bench"], D["real"])
    ts = sorted(x["origin_t"] for x in m)
    assert len(m) >= 2, m                                   # 옛 판 = 1줄(49.32초)
    assert any(36 <= t <= 42 for t in ts) and any(47 <= t <= 52 for t in ts), ts


def test_decoy_stays_empty():
    assert RU.fingerprint(D["bench"], D["decoy"]) == []
