"""유튜브 스파인 2종 시드 — 실제로 쓸 수 있는 상태로 들어가는가 (2026-08-19).

시드는 '넣었다'로 끝나면 안 된다. 라이브에서 이 스파인이 쓰이려면 네 관문을 다 넘어야 한다:
  ① list_style_spines에 뜬다(beat_roles 있음 + status approved + 카테고리 일치)
  ② no_cta가 DB 왕복에서 살아남는다 → 게이트가 CTA 검사를 건너뛴다
  ③ 실측 문장으로 쓴 대본이 문장틀 검사를 통과한다(틀이 실제 원문과 안 맞으면 무용지물)
  ④ 밀도 목표가 유튜브 실측(262~283자/30초)에 맞다
한 관문만 어긋나도 조용히 안 쓰이거나 영구 FAIL이라, 시드 스크립트를 직접 돌려 검사한다.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

from shopping_shorts import script_gate
from shopping_shorts.store import Store

ROOT = Path(__file__).resolve().parents[2]


def _load_seed():
    spec = importlib.util.spec_from_file_location(
        "seed_yt", str(ROOT / "tools" / "seed_style_youtube.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules["seed_yt"] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture()
def seeded(tmp_path, monkeypatch):
    """시드 스크립트를 임시 DB에 실제로 돌린다(라이브 DB는 안 건드린다)."""
    m = _load_seed()
    st = Store(str(tmp_path / "t.db"))
    monkeypatch.setattr(m, "Store", lambda *_a, **_k: st)
    m.main()
    return st


def _get(st, name):
    hit = [s for s in st.list_spines() if s["name"] == name]
    assert hit, "%s 스파인이 없다" % name
    return hit[0]


def test_두_스파인이_들어간다(seeded):
    assert _get(seeded, "유튜브 은폐형")
    assert _get(seeded, "유튜브 오용형")


def test_스타일_목록에_뜬다(seeded):
    """★list_style_spines에 안 뜨면 화면 드롭다운에 없어서 아무도 못 고른다."""
    hid = seeded.list_style_spines(category="제품정체형", status="approved")
    assert any(s["name"] == "유튜브 은폐형" for s in hid), "은폐형이 제품정체형 목록에 없다"
    mis = seeded.list_style_spines(category="오용형", status="approved")
    assert any(s["name"] == "유튜브 오용형" for s in mis), "오용형이 오용형 목록에 없다"


def test_인스타_카테고리를_침범하지_않는다(seeded):
    """유튜브 스파인이 홈템(인스타 시월드형 자리)에 뜨면 안 된다."""
    home = seeded.list_style_spines(category="홈템", status="approved")
    assert not [s for s in home if s["name"].startswith("유튜브")]


def test_no_cta가_켜져있고_게이트가_CTA를_안_본다(seeded):
    """★이게 없으면 유튜브 스파인은 아무리 잘 써도 영구 FAIL이다."""
    for name in ("유튜브 은폐형", "유튜브 오용형"):
        sp = _get(seeded, name)
        assert sp.get("no_cta") is True, "%s에 no_cta가 안 붙었다" % name
    sp = _get(seeded, "유튜브 오용형")
    checks, _ = script_gate.check(sp, [
        {"role": "title", "text": "개발자도 예상 못한 미친 사용법"},
        {"role": "origin", "text": "이게 원래는 의류 태그 부착용으로 개발된 제품이었음"},
        {"role": "notice", "text": "그런데 사람들은 옷감 손상이 없다는 걸 눈치채고 이걸 엉뚱한 용도로 사용하기 시작하는데"},
        {"role": "cases", "text": "바지 밑단 줄임용으로 쓰는가 하면 커튼 길이 조절에도 썼다는 거"},
        {"role": "twist", "text": "근데 미친 사용법은 따로 있었는데 맨날 밀리는 침대 커버 고정용"},
    ])
    assert not [c for c in checks if c["name"] == "CTA 단어유도"]


def test_실측_문장이_문장틀을_통과한다(seeded):
    """★틀이 실제 원문과 안 맞으면 게이트가 정상 대본을 FAIL로 잡는다.

    아래 문장은 살림킹왕짱 697OHq-VhkY(1,047만) 자막 실측 원문이다."""
    sp = _get(seeded, "유튜브 오용형")
    checks, _ = script_gate.check(sp, [
        {"role": "title", "text": "개발자도 예상 못한 미친 사용법"},
        {"role": "origin", "text": "이게 원래는 딸깍 한 방으로 의류 태그를 부착하라고 개발된 제품이었음"},
        {"role": "notice", "text": "그런데 사람들은 옷감 손상 제로에 티도 거의 안 난다는 걸 눈치채고 이걸 엉뚱한 용도로 사용하기 시작하는데"},
        {"role": "cases", "text": "바닥 쓸고 다니는 바지들 밑단 줄임용으로 사용하는가 하면 온갖 고정이 필요한 의류들 임시 수선용으로 사용했다는 거"},
        {"role": "twist", "text": "근데 미친 사용법은 따로 있었는데 바닥에 질질 끌리는 커튼 밑단 올림용으로 사용한다고"},
    ])
    bad = [c["name"] for c in checks if c["name"].endswith("문장틀 준수") and not c["ok"]]
    assert not bad, "실측 원문이 문장틀에서 떨어졌다: %s" % bad


def test_은폐형도_실측_문장이_통과한다(seeded):
    """이븐쇼핑 eDHoIXyXOq0(78.2만) 자막 실측 원문."""
    sp = _get(seeded, "유튜브 은폐형")
    checks, _ = script_gate.check(sp, [
        {"role": "title", "text": "요아정 망하게 한 천재의 발명품"},
        {"role": "bait", "text": "최근 딱 봤을 때는 도저히 용도를 알기 힘든 이 제품이"},
        {"role": "authority", "text": "이걸 개발한 한국의 천재가 돈방석에 앉았다는데"},
        {"role": "reveal", "text": "이건 바로 가정용 유청 거르개"},
        {"role": "benefit", "text": "이게 말도 안 되는 게 통에 마시는 요거트를 넣고 냉장고에 두기만 하면 꾸덕한 그릭요거트가 뚝딱 만들어져"},
        {"role": "twist", "text": "근데 진짜 충격적인 포인트는 스프링 조절로 질감까지 조절할 수 있다는 거"},
    ])
    bad = [c["name"] for c in checks if c["name"].endswith("문장틀 준수") and not c["ok"]]
    assert not bad, "실측 원문이 문장틀에서 떨어졌다: %s" % bad


def test_밀도가_유튜브_실측치다(seeded):
    """인스타 시월드형은 300 — 유튜브는 실측 262~283이라 270."""
    for name in ("유튜브 은폐형", "유튜브 오용형"):
        assert _get(seeded, name)["chars_per_30s"] == 270


def test_두번_돌려도_안_늘어난다(seeded, monkeypatch):
    """멱등 — 시드를 다시 돌려도 중복 행이 안 생긴다."""
    m = sys.modules["seed_yt"]
    monkeypatch.setattr(m, "Store", lambda *_a, **_k: seeded)
    m.main()
    names = [s["name"] for s in seeded.list_spines()]
    assert names.count("유튜브 은폐형") == 1
    assert names.count("유튜브 오용형") == 1
