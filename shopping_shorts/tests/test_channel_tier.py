"""채널 등급제 — 과거 성적으로 방문 주기를 가른다(2026-08-17).

배경: 프록시 대역폭이 25GB/월인데 하루 6.35GB를 태워 4일만에 402(Payment Required).
실측(서버 reference.db 26일치): 441채널 중 275개가 댓글 500+ 히트를 한 건도 못 냈고,
C등급 227채널은 26일간 히트 0건인데도 매일 문을 두드리고 있었다.

★비용은 '문을 여는 순간' 나간다 — 프록시는 바이트, Apify는 run당 고정($0.005,
apify_client.py:173). 가져오는 개수를 줄여도 절감 0이다. 절감은 '안 여는 것'뿐이라
과거 성적으로 미리 골라야 한다.

기준을 조회수가 아니라 댓글로 잡은 이유(실측): 사장님이 실제 제작에 쓴 45채널을
얼마나 잡아내는지 비교하면 조회10만+2건=49%뿐인데 댓글500+2건=82%다. 실제 사용된
영상의 댓글 중앙값은 1,473(전체 P90이 579)이라 사장님 눈은 이미 댓글을 보고 있었다.
"""
import pytest

from shopping_shorts import channel_tier as ct


def _row(user, comments, seen):
    return {"username": user, "comments": comments, "first_seen": seen}


TODAY = "2026-08-17"


class TestComputeTiers:
    def test_히트2건이면_A(self):
        rows = [_row("a", 600, "2026-08-16"), _row("a", 900, "2026-08-15")]
        assert ct.compute_tiers(rows, today=TODAY)["a"] == ct.TIER_A

    def test_히트1건이면_B(self):
        rows = [_row("b", 600, "2026-08-16"), _row("b", 10, "2026-08-15")]
        assert ct.compute_tiers(rows, today=TODAY)["b"] == ct.TIER_B

    def test_히트0이면_C(self):
        rows = [_row("c", 100, "2026-08-16"), _row("c", 20, "2026-08-15")]
        assert ct.compute_tiers(rows, today=TODAY)["c"] == ct.TIER_C

    def test_14일_무업로드면_D(self):
        # 히트가 있어도 최근 업로드가 없으면 휴면 — 매일 열어봐야 빈손이다
        rows = [_row("d", 5000, "2026-07-20"), _row("d", 3000, "2026-07-19")]
        assert ct.compute_tiers(rows, today=TODAY)["d"] == ct.TIER_D

    def test_경계_댓글500은_히트(self):
        rows = [_row("e", 500, "2026-08-16"), _row("e", 500, "2026-08-15")]
        assert ct.compute_tiers(rows, today=TODAY)["e"] == ct.TIER_A

    def test_경계_댓글499는_히트아님(self):
        rows = [_row("f", 499, "2026-08-16"), _row("f", 499, "2026-08-15")]
        assert ct.compute_tiers(rows, today=TODAY)["f"] == ct.TIER_C

    def test_대소문자_정규화(self):
        rows = [_row("Mixed", 600, "2026-08-16"), _row("mixed", 700, "2026-08-15")]
        tiers = ct.compute_tiers(rows, today=TODAY)
        assert tiers["mixed"] == ct.TIER_A          # 같은 채널로 합산돼 A
        assert "Mixed" not in tiers                 # 키는 정규화형만

    def test_이력없는_채널은_비어있다(self):
        assert ct.compute_tiers([], today=TODAY) == {}

    def test_댓글None도_죽지않는다(self):
        rows = [_row("g", None, "2026-08-16")]
        assert ct.compute_tiers(rows, today=TODAY)["g"] == ct.TIER_C


class TestDueToday:
    def test_A는_매일_전부(self):
        tiers = {"a1": ct.TIER_A, "a2": ct.TIER_A}
        for d in range(30):
            assert ct.due_today(tiers, day_index=d) == {"a1", "a2"}

    def test_이력없는_신규채널은_매일_긁는다(self):
        # 등급을 매길 근거가 없으면 pending — 안 긁으면 영영 등급이 안 생긴다
        assert ct.due_today({}, day_index=0, known=["new1"]) == {"new1"}

    def test_B는_주기내_정확히_한번(self):
        tiers = {f"b{i}": ct.TIER_B for i in range(20)}
        period = ct.PERIOD_DAYS[ct.TIER_B]
        seen = []
        for d in range(period):
            seen += list(ct.due_today(tiers, day_index=d))
        assert sorted(seen) == sorted(tiers)        # 중복도 누락도 없다

    def test_C도_주기내_정확히_한번(self):
        tiers = {f"c{i}": ct.TIER_C for i in range(50)}
        period = ct.PERIOD_DAYS[ct.TIER_C]
        seen = []
        for d in range(period):
            seen += list(ct.due_today(tiers, day_index=d))
        assert sorted(seen) == sorted(tiers)

    def test_고르게_분산된다(self):
        # 한 날에 몰리면 그날만 대역폭이 터진다 — 해시로 균등 배분
        tiers = {f"c{i}": ct.TIER_C for i in range(140)}
        period = ct.PERIOD_DAYS[ct.TIER_C]
        per_day = [len(ct.due_today(tiers, day_index=d)) for d in range(period)]
        assert max(per_day) <= 140 // period * 2    # 평균의 2배를 넘지 않는다

    def test_같은날은_항상_같은결과(self):
        tiers = {f"x{i}": ct.TIER_C for i in range(30)}
        assert ct.due_today(tiers, day_index=3) == ct.due_today(tiers, day_index=3)

    def test_D도_언젠가_돌아온다(self):
        # 휴면이라고 영영 안 보면 부활을 못 잡는다
        tiers = {"d1": ct.TIER_D}
        period = ct.PERIOD_DAYS[ct.TIER_D]
        assert any(ct.due_today(tiers, day_index=d) for d in range(period))


class TestFetchLimit:
    def test_A는_기본개수(self):
        assert ct.fetch_limit(ct.TIER_A) == ct.RESULTS_DEFAULT

    def test_C는_1개만(self):
        # C는 재료창고가 아니라 승격 감지기 — 최신 1개만 봐도 터졌는지 안다
        assert ct.fetch_limit(ct.TIER_C) == 1

    def test_D도_1개만(self):
        assert ct.fetch_limit(ct.TIER_D) == 1


class TestSplitByTier:
    def test_등급별_인원수(self):
        tiers = {"a": ct.TIER_A, "b": ct.TIER_B, "c": ct.TIER_C, "d": ct.TIER_D}
        counts = ct.tier_counts(tiers)
        assert counts == {ct.TIER_A: 1, ct.TIER_B: 1, ct.TIER_C: 1, ct.TIER_D: 1}


class TestConfigurable:
    def test_기준값을_바꿀수있다(self):
        # 재료가 부족하면 기준을 낮춰 A를 넓힌다 — 코드 수정 없이 되돌릴 수 있어야 한다
        rows = [_row("h", 600, "2026-08-16")]
        assert ct.compute_tiers(rows, today=TODAY, hit_min_count=1)["h"] == ct.TIER_A
        rows2 = [_row("i", 300, "2026-08-16"), _row("i", 300, "2026-08-15")]
        assert ct.compute_tiers(rows2, today=TODAY, hit_comments=200)["i"] == ct.TIER_A
