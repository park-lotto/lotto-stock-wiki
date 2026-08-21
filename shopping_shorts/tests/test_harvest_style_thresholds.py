"""축별 문턱(2026-08-21) — 신기템은 판정이 쉬워 문턱이 둘이다.

라이브 실측: min 3 · 하한 없음으로 하룻밤 549채널이 들어왔는데 구독 중앙값 264,
100명 미만 38%, 그리고 25편 중 3편만 우연히 맞은 대형 오탐이 섞여 있었다.
"""
import re
import pathlib

_SRC = (pathlib.Path(__file__).resolve().parents[2]
        / "scripts" / "harvest_styles_forever.py").read_text(encoding="utf-8")


def _cfg(style):
    m = re.search(r'"%s":\s*\{(.*?)\}' % style, _SRC, re.S)
    assert m, "%s 축이 STYLES에 없다" % style
    return m.group(1)


def test_신기템은_구독하한과_높은_문턱을_둘_다_가진다():
    c = _cfg("신기템")
    assert '"min": 5' in c, "문턱이 낮으면 대형 오탐이 통째로 들어온다"
    assert '"min_subs": 1000' in c, "구독 하한이 없으면 잡채널이 59% 찬다"


def test_다른_축은_구독하한을_걸지_않는다():
    """공식 자체가 어려워 그게 필터다 — 하한을 걸면 멀쩡한 채널이 잘린다."""
    for style in ("썰쇼핑", "연예인결합", "레시피쇼핑"):
        assert "min_subs" not in _cfg(style), style


def test_등록부가_두_문턱을_모두_본다():
    assert 'sc >= cfg["min"] and subs >= cfg.get("min_subs", 0)' in _SRC
