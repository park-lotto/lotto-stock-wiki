"""이미 만든 편 판단(tools/calcopy/done_list) — channel/<채널>/<편>/대본.json 의 소재 id 도 본다(10-29 샥템 QMJtjJz4M6w·숏템리폿 ZqVgAg99gRI 를
'안 만든 편'으로 놓쳐 회원 시험 두 편이 이미 만든 소재로 돌았다)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy import done_list as DL  # noqa: E402


def test_script_bench_ids_count_as_made():
    for vid in ("QMJtjJz4M6w", "ZqVgAg99gRI"):          # 1편_STORMBAG · 현장썰_07_주걱
        assert any("대본.json" in s for _, s in DL.made(vid)), vid


def test_unknown_id_is_not_made():
    assert not [h for h in DL.made("zzNotAVideo9") if "대본.json" in h[1]]
