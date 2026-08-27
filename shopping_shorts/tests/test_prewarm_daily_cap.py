# -*- coding: utf-8 -*-
"""예열 일일 상한 — 한국 날짜로 리셋, 상한 100 (2026-08-27).

★사고: 상한의 '하루'가 UTC였다 → 리셋이 **한국 오전 9시**.
  낮에 상한을 다 쓰면 그날 저녁부터 다음날 아침 9시까지 담는 건 전부 조용히 스킵됐다.
  실측(서버 워커 로그): KST 00~08시 44건 skipped_cap → 09시 정각부터 done.
  사장님 제보 "담아둔것도 분석이 안되고 그런건 모지"의 정체가 이것이었다.

★기능이 죽는 건 아니다 — 스킵돼도 제작소에서 쓸 때 그때 추출한다. 다만 조용해서 몰랐다.
"""
import pytest

from shopping_shorts import prewarm as pw


class _S:
    def __init__(self, v=""):
        self.v = v
    def get_setting(self, k, d=""):
        return self.v
    def set_setting(self, k, v):
        self.v = v


def _kst_today():
    from datetime import datetime, timedelta, timezone
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")


class Test한국날짜로_센다:
    def test_오늘은_한국_날짜(self):
        assert pw._today_kst() == _kst_today()

    def test_UTC와_다른_시간대에도_한국_기준(self):
        """★KST 00~09시엔 UTC 날짜가 하루 전이다 — 그때 리셋이 안 되던 것이 사고였다."""
        from datetime import datetime, timedelta, timezone
        kst = datetime.now(timezone(timedelta(hours=9)))
        utc = datetime.now(timezone.utc)
        if kst.strftime("%Y-%m-%d") != utc.strftime("%Y-%m-%d"):
            assert pw._today_kst() != utc.strftime("%Y-%m-%d"), "UTC를 다시 쓰고 있다"

    def test_어제_기록은_0으로_리셋(self):
        s = _S("2020-01-01|99")
        assert pw._daily_used(s) == 0

    def test_오늘_기록은_그대로_읽는다(self):
        s = _S(f"{_kst_today()}|7")
        assert pw._daily_used(s) == 7

    def test_망가진_값도_0(self):
        assert pw._daily_used(_S("이상한값")) == 0
        assert pw._daily_used(_S("")) == 0


class Test상한:
    def test_상한은_100(self):
        assert pw._PREWARM_DAILY_CAP == 100

    def test_상한_안이면_통과하고_1_올린다(self):
        s = _S(f"{_kst_today()}|5")
        assert pw._daily_take(s) is True
        assert s.v == f"{_kst_today()}|6"

    def test_상한에_닿으면_막고_안_올린다(self):
        s = _S(f"{_kst_today()}|100")
        before = s.v
        assert pw._daily_take(s) is False
        assert s.v == before, "막았는데 카운터가 올라갔다"

    def test_어제_100건이어도_오늘은_통과(self):
        """★이게 사고의 핵심 — 날짜가 바뀌면 다시 쓸 수 있어야 한다."""
        s = _S("2020-01-01|100")
        assert pw._daily_take(s) is True


class Test남은_몫_안내:
    def test_남은_건수를_센다(self):
        assert pw.daily_remaining(_S(f"{_kst_today()}|30")) == 70

    def test_다_썼으면_0(self):
        assert pw.daily_remaining(_S(f"{_kst_today()}|100")) == 0

    def test_넘겨도_음수가_아니다(self):
        assert pw.daily_remaining(_S(f"{_kst_today()}|999")) == 0

    def test_세기만_하고_쓰지_않는다(self):
        """★안내용이다 — 조회가 몫을 까먹으면 담을 때마다 한도가 준다."""
        s = _S(f"{_kst_today()}|10")
        pw.daily_remaining(s); pw.daily_remaining(s)
        assert s.v == f"{_kst_today()}|10"
