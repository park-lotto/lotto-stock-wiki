# -*- coding: utf-8 -*-
"""다이소 스파인이 **대본 스타일 목록에 실제로 뜨는가** (2026-08-20 실사고).

사장님 제보: "다이소내부인형이 없는데" — 화면 목록에 5개뿐이었다.

스파인은 멀쩁했다(beat_roles·templates 완비, 조립 경로도 인식). 문제는 `status`였다:
라이브 5개가 전부 `approved`인데 시드 스크립트가 **`active`로 심어서**
`list_style_spines(status="approved")`가 통째로 걸러냈다. **오류는 안 났다.**

★교훈: 상태 문자열은 짐작하지 말고 **기존 행이 쓰는 값**을 따라라.
  "심었다"와 "목록에 뜬다"는 다른 일이다.
"""
import pytest

from shopping_shorts.store import Store

ROLES = ["hook", "problem", "demo"]
TMPL = {"hook": ["여러분 다이소 가면 이거 무조건 사오세요"],
        "problem": ["아니 {불편함} 때문에 진짜 스트레스였거든요"],
        "demo": ["방법도 진짜 간단해요. {사용법}, 이게 끝이에요"]}


@pytest.fixture()
def st(tmp_path):
    return Store(str(tmp_path / "t.db"))


def _seed(st, status="approved", fits=("다이소형", "홈템")):
    sid = st.add_spine(name="다이소 내부인형", fit_categories=list(fits), status=status)
    st.set_spine_style(sid, beat_roles=ROLES, templates=TMPL, chars_per_30s=226)
    return sid


def test_승인상태로_심으면_목록에_뜬다(st):
    _seed(st)
    assert any(s["name"] == "다이소 내부인형" for s in st.list_style_spines())


def test_active로_심으면_목록에서_사라진다(st):
    """★이 사고 자체를 붙잡는다 — 오류 없이 조용히 빠지는 게 제일 나쁘다."""
    _seed(st, status="active")
    assert not st.list_style_spines()


def test_홈템_영상에서도_목록에_남는다(st):
    """담은 영상은 대개 '홈템'으로 분류된다. '다이소형'만 달면 홈템 소재에서 밀린다."""
    _seed(st)
    names = [s["name"] for s in st.list_style_spines(category="홈템")]
    assert "다이소 내부인형" in names


def test_이미_심긴_행의_카테고리도_고칠_수_있다(st):
    """★없으면 잘못 심은 행을 영영 못 고친다(add_spine에서만 정해졌었다)."""
    sid = _seed(st, fits=("다이소형",))
    st.set_spine_style(sid, fit_categories=["다이소형", "홈템"])
    got = next(s for s in st.list_spines() if s["id"] == sid)
    assert got["fit_categories"] == ["다이소형", "홈템"]


def test_조립_경로도_여전히_알아본다(st):
    """화면용으로 '홈템'을 더해도 인스타 갈래 판정이 깨지면 안 된다."""
    from shopping_shorts import app
    sid = _seed(st)
    sp = next(s for s in st.list_spines() if s["id"] == sid)
    assert app._is_insta_context("", [sp]) is True
