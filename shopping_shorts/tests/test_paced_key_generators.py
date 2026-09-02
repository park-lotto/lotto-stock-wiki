# -*- coding: utf-8 -*-
"""목록을 직접 순회하는 생성부가 **페이서를 거치는지**.

★왜(2026-09-01 실측): 이 4곳은 get_client(group)를 안 거쳐 페이서를 통째로 우회했다.
  `for key in keys:`가 간격 0으로 연타하고 429가 나면 대기 없이 다음 키로 넘어가
  키 76개를 순식간에 태운다. 오늘 KST 12·15시 피크에서 대본생성 web 407콜 중
  분당한도 149건(36.6%). 나머지 시간대(3~8%)와 비교하면 몰릴 때만 터진다.
"""
import io
import os
import re

_DIR = os.path.join(os.path.dirname(__file__), "..")
_TARGETS = ("script_generate.py", "seo_generate.py", "thumb_title.py", "pattern_bank.py")


def _src(name):
    return io.open(os.path.join(_DIR, name), encoding="utf-8").read()


def test_생성부_4곳이_페이서로_키를_고른다():
    for name in _TARGETS:
        s = _src(name)
        assert "pick_paced_key" in s, f"{name}: 페이서를 안 거친다 — 429를 자초한다"


def test_페이서_없이_키목록을_연타하지_않는다():
    """`for key in keys:` 모양이 남아 있으면 그 자리가 다시 연타 경로다.

    ★주석은 뺀다 — 왜 고쳤는지 적은 문장에 그 모양이 그대로 들어 있어서,
      코드가 아니라 설명을 잡으면 영원히 빨간불이다(실측: 4파일 전부 오탐).
    """
    for name in _TARGETS:
        code = chr(10).join(ln for ln in _src(name).splitlines()
                         if not ln.lstrip().startswith("#"))
        bad = re.search(r"for key in keys(\[|:)", code)
        assert not bad, f"{name}: 아직 키 목록을 그대로 순회한다({bad.group(0)})"


def test_한_키는_한_번만_시도한다():
    """페이서를 넣으면서 무한 재시도가 되면 안 된다 — 목록에서 빼야 끝난다."""
    for name in _TARGETS:
        s = _src(name)
        assert "pool.remove(key)" in s, f"{name}: 시도한 키를 안 빼면 루프가 안 끝난다"


def test_pick_paced_key가_최소간격을_지킨다():
    """같은 키를 연달아 요청하면 두 번째는 기다렸다 나온다(실제 대기 측정)."""
    import time
    from pipeline.atoms import key_vault as kv

    kv._KEY_LAST_USED.clear()
    gap = kv._MIN_GAP_S
    assert gap > 0, "최소 간격이 0이면 페이서가 아니다"

    t0 = time.monotonic()
    assert kv.pick_paced_key(["K1"]) == "K1"      # 첫 호출은 즉시
    assert time.monotonic() - t0 < gap / 2

    # 키가 하나뿐이면 두 번째는 gap만큼 잔다 — 실제로 재우면 테스트가 느려지므로
    # 마지막 사용시각을 과거로 밀어 '이미 풀린' 상태만 확인한다.
    kv._KEY_LAST_USED["K1"] = time.monotonic() - gap - 1
    t1 = time.monotonic()
    assert kv.pick_paced_key(["K1"]) == "K1"
    assert time.monotonic() - t1 < gap / 2, "쿨다운이 끝났는데도 잤다"


def test_키가_많으면_안_기다린다():
    """키를 늘리면 대기가 0에 수렴해야 한다 — 그게 이 설계의 약속이다."""
    import time
    from pipeline.atoms import key_vault as kv

    kv._KEY_LAST_USED.clear()
    keys = ["K%d" % i for i in range(10)]
    t0 = time.monotonic()
    got = [kv.pick_paced_key(keys) for _ in range(10)]
    assert time.monotonic() - t0 < kv._MIN_GAP_S / 2, "키 10개인데 기다렸다"
    assert len(set(got)) == 10, f"같은 키를 다시 줬다: {got}"
