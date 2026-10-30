"""10-30 설치본 시험(썰템쇼 쇼핑형): 지우기(VMake) 단계가 없는 형식인데 will_erase=True → 관문이 흐림을 안 넣고 고치기 질문도 '흐림 넣지 마라'
→ 남의 로고·자막이 남아 1초 시트에서 4번 걸림. 판단 = 형식에 f_clean 이 있나(flow.erases_text) + 판 칸(orig_text.mode)."""
from tools.calcopy import vmake_clean as V
from tools.calcopy.hybrid import flow as F


def test_shop_and_celeb_formats_do_not_erase():
    for v in ("썰템쇼판", "썰템홈샷판", "키치잇판"):
        assert F.erases_text(v) is False and V.will_erase(v) is False, v


def test_foreign_format_erases():
    assert F.erases_text("잇템로그판_v2") is True
    assert V.will_erase("잇템로그판_v2") is True        # 키 없음(need_key)도 '지울 판'(키는 f_clean 이 따로 받는다)
