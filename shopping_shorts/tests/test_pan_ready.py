"""판 준비(tools/calcopy/hybrid/pan_ready) — 빈칸을 찾기만 하지 않고 벤치 실측으로 채운 뒤 다시 잰다(사장님 10-29 '멈추는 게 아니라 다시 되게').
진짜 판(샥탬판)을 임시 이름으로 복사해 일부러 망가뜨린다: 배치 셈 전환을 옛 이름 'colorflash'로 · rhythm plain_share·photo_share_max 지움 → repair 뒤 빈 목록."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import pan_ready as PR, styles as S  # noqa: E402

NAME = "_test_pan_ready"


def _broken(tmp_dir):
    raw = json.loads(S.path_of("샥탬판").read_text(encoding="utf-8"))
    for v in raw["placement"]["counted"]["videos"]:
        t = v.get("transitions") or {}
        if "flash" in t:
            t["colorflash"] = t.pop("flash")              # 10-25 전 옛 이름으로 센 셈(렌더러는 모름)
    for k in ("plain_share", "photo_share_max"):
        raw["rhythm"].pop(k, None)
    p = S.DIR / f"{NAME}.json"
    p.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def test_diagnose_then_repair_makes_ready(tmp_path):
    p = _broken(tmp_path)
    try:
        fixes = {g["fix"] for g in PR.diagnose(NAME)}
        assert fixes == {"count", "rhythm"}, fixes                    # 망가뜨린 두 가지를 다 찾는다
        assert PR.repair(NAME, log=lambda *_: None) == []             # 고친 뒤 남은 것 없음
        r = json.loads(p.read_text(encoding="utf-8"))["rhythm"]
        assert r["plain_share"]["v"] == json.loads(S.path_of("샥탬판").read_text(encoding="utf-8"))["rhythm"]["plain_share"]["v"]
    finally:
        p.unlink(missing_ok=True)


def test_unfixable_is_reported_not_hidden():
    left = PR.diagnose("없는판_zz")
    assert left and left[0]["fix"] is None
