# -*- coding: utf-8 -*-
"""행위 축(설치·조작·도포·정리·실증)을 슬롯이 **구분해서** 쓰는가 (2026-08-20).

축을 쪼개 놓고도 배치가 뭉뚱그려 집으면 "장점1 자리엔 이 장면" 지시를 못 한다.
반대로 좁히기만 하면 그 갈래가 없는 소재에서 슬롯이 통째로 빈다.
그래서 `roles`를 **우선순위 목록**으로 쓰고 마지막에 `사용중`을 남긴다.
"""
from shopping_shorts import edit_plan
from shopping_shorts import shot_roles as SR


def _seg(i, role, desc, key=False):
    return {"seg_id": "v-%d" % i, "start": float(i), "end": float(i) + 1,
            "shot_role": role, "scene_desc": desc, "is_key": key}


def _plan(vt, segs):
    return {r["slot"]: r["scene_desc"]
            for r in edit_plan._build_scene_spine({s["seg_id"]: s for s in segs}, vt)}


class TestExpand:
    def test_사용중만_계열_전체로_넓힌다(self):
        """★2026-08-20 실측 버그: '사용 계열이면 전부 넓힌다'로 짰더니 `도포`를 요구해도
        조작·정리·설치가 다 걸렸다 — 축을 쪼개 놓고 구분을 못 하는 상태였다."""
        assert SR.expand(["도포"]) == {"도포"}
        assert SR.expand(["사용중"]) == set(SR.USE_ROLES)

    def test_구체_갈래는_서로_안_섞인다(self):
        assert SR.matches("조작", ["도포"]) is False
        assert SR.matches("정리", ["설치"]) is False

    def test_사용중을_요구하면_모든_갈래가_걸린다(self):
        """폴백이 살아 있어야 옛 태깅(3,500여 건)이 안 죽는다."""
        for r in SR.USE_ROLES:
            assert SR.matches(r, ["사용중"]) is True
        assert SR.matches("조리", ["사용중"]) is True      # 옛 값도 흡수


class TestSlotPriority:
    def test_뷰티는_바르는_장면을_고른다(self):
        p = _plan("beauty", [
            _seg(1, "완성", "완성된 룩", True), _seg(2, "before", "맨얼굴"),
            _seg(3, "조작", "뚜껑을 돌려 연다"),          # 시간상 더 앞
            _seg(4, "도포", "크림을 얼굴에 바른다"),        # 갈래가 맞다
            _seg(5, "after", "촉촉해진 피부")])
        assert p["사용"] == "크림을 얼굴에 바른다"

    def test_청소는_닦는_장면을_고른다(self):
        p = _plan("cleaning", [
            _seg(1, "before", "때 낀 욕실", True),
            _seg(2, "도포", "세제를 뿌린다"),              # 시간상 더 앞
            _seg(3, "정리", "솔로 문질러 닦는다"),
            _seg(4, "after", "반짝이는 욕실", True)])
        assert p["사용"] == "솔로 문질러 닦는다"

    def test_그_갈래가_없으면_계열로_폴백한다(self):
        """★`사용중` 폴백을 빼면 이 슬롯이 통째로 빈다 — 회귀 0의 근거."""
        p = _plan("beauty", [
            _seg(1, "완성", "완성된 룩", True), _seg(2, "before", "맨얼굴"),
            _seg(3, "조작", "뚜껑을 돌려 연다"), _seg(5, "after", "촉촉해진 피부")])
        assert p["사용"] == "뚜껑을 돌려 연다"

    def test_옛_태깅만_있어도_종전과_같다(self):
        """라이브에 '사용중'으로만 남은 장면이 아직 1,200건 있다."""
        p = _plan("generic", [
            _seg(1, "완성", "완성품", True), _seg(2, "사용중", "쓰는 장면A"),
            _seg(3, "사용중", "쓰는 장면B", True), _seg(4, "after", "결과")])
        assert p["핵심실증"] == "쓰는 장면B"      # is_key가 우선순위보다 앞선다

    def test_실증컷은_우선순위보다_앞선다(self):
        """1순위 갈래에 실증컷이 없을 때 실증컷을 놓치면 그게 회귀다."""
        p = _plan("kitchen_tool", [
            _seg(1, "완성", "제품 전체샷", True), _seg(2, "문제", "안 열리는 병뚜껑"),
            _seg(3, "조작", "손잡이를 돌린다"),                    # 1순위 아님·key 아님
            _seg(4, "설치", "뚜껑에 끼워 고정한다", True),          # key다
            _seg(5, "after", "열린 병")])
        assert p["기능실증"] == "뚜껑에 끼워 고정한다"
