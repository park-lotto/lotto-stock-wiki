# -*- coding: utf-8 -*-
"""재료 짧은 값 칸이 **지시문 오염**을 막는가 (2026-08-21 실사고).

프롬프트에 "영상에 안 나오면 비워라"라고 적어 뒀더니 모델이 **그 지시를 값으로 되뱉었다.**
사장님이 담아주신 구명 팔찌 소재 5편 중 **4편**이 이랬다:

    origin_country = "중국 또는 정보 없음 (영상 불명확함으로 비움이나 중국어로
                      추정 가능하나 보수적으로 비움 적용) ※주의: 지…"

이대로면 대본의 "{나라}에서 바이럴이 터지며 매출이 폭발했다는데" 빈칸에 저 문장이
통째로 들어간다. **게이트는 문장틀만 보므로 못 잡는다.**

처방은 프롬프트 강화가 아니라 **저장 단일출구에서 막기**다
(메모리 `reference_prompt_says_but_nobody_checks`).
"""
from shopping_shorts import sul_facts as SF


# 라이브에서 실제로 나온 오염값(2026-08-21 실측). 문구를 바꾸지 마라 — 이게 증거다.
LIVE_DIRTY = [
    "대한민국이 아닌 경우 알 수 없음 또는 빈 문자열 처리 필요 (영상 내용상 확인 불가하여 비워둠 - 지침 준수)",
    "중국 또는 관련 정보 없음(영상 내 언급 없음 - 빈 값 처리함: 참고로 실제로는 미국 제품이 대다수)",
    "중국으로 추정됨(영상이 중국어 자막과 배경음으로 구성됨에 따름/지어내지 않으려면 공백이 맞으나)",
    "중국 또는 정보 없음 (영상 불명확함으로 비움이나 중국어로 추정 가능) ※주의: 지",
]


class TestCleanShort:
    def test_라이브_오염값을_전부_버린다(self):
        for v in LIVE_DIRTY:
            assert SF._clean_short(v, 12) == "", "오염값이 통과했다: %s" % v[:30]

    def test_정상_국가명은_통과한다(self):
        for v in ("한국", "중국", "미국", "일본", "독일"):
            assert SF._clean_short(v, 12) == v

    def test_자르지_않고_버린다(self):
        """★12자로 자르면 '중국 또는 정보 없'이 남아 더 나쁘다.
        비면 그 슬롯을 쓰는 템플릿이 자동으로 안 걸린다(안전한 폴백)."""
        out = SF._clean_short(LIVE_DIRTY[3], 12)
        assert out == ""
        assert "중국 또는" not in out

    def test_칸마다_상한이_다르다(self):
        """나라는 짧고 탄생배경은 문장이다 — 같은 상한을 걸면 한쪽이 죽는다."""
        story = "혼자서 신발을 신고 싶다는 뇌성마비 소년의 편지 한 통"
        assert SF._clean_short(story, SF._SHORT_MAX["origin_story"]) == story
        assert SF._clean_short(story, SF._SHORT_MAX["origin_country"]) == ""

    def test_추출_결과에서도_걸러진다(self):
        """단일출구(_normalize 경로)를 거치는지 — 여기서 안 막으면 소용없다."""
        raw = {"product_name": "구명 팔찌", "origin_country": LIVE_DIRTY[0],
               "category_word": "구명장비", "misuse_genre": False}
        out = SF._norm_facts(raw) if hasattr(SF, "_norm_facts") else None
        if out is None:                      # 함수명이 바뀌면 이 테스트가 알려준다
            import inspect
            src = inspect.getsource(SF)
            assert "_clean_short(data.get(k)" in src, "저장 출구가 _clean_short를 안 쓴다"
        else:
            assert "origin_country" not in out
            assert out.get("product_name") == "구명 팔찌"
