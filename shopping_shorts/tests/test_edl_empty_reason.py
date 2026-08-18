"""EDL 빈 원인 갈라내기 — 2026-08-19 사장님 총점검 지시.

종전 문구는 원인 2개를 뭉갰다: "대본 추출 실패 또는 Gemini 키 소진".
라이브 실측 13건에서 대부분은 **추출이 성공한 상태**였다(extract_json 9,091자인데
edit_plan_json 0). 즉 진짜 실패 지점은 추출이 아니라 편집안 생성인데, 화면엔
"추출 실패"라고 떠서 엉뚱한 데를 보게 만들었다.

원인이 다르면 처방이 다르다:
  extract_empty → 소스 자막·음성 문제(키와 무관)
  plan_empty    → Gemini 응답·파싱 문제(키 소진·차단 의심)
"""
from shopping_shorts.mix_pipeline import _edl_empty_reason


def test_추출은_됐는데_편집안만_빈_경우를_구분한다():
    """실측 다수 경로(e8835741: 9,091자 추출 성공 / plan 0)."""
    code, why = _edl_empty_reason([{"full_text": "가" * 9091}], {"generator": "scene_first"})
    assert code == "plan_empty", "추출 성공을 '추출 실패'로 말하면 안 된다"
    assert "9091자" in why, "실제 글자수를 보여줘야 어디가 문제인지 안다"
    assert "scene_first" in why, "어느 생성기였는지 남겨야 재현할 수 있다"


def test_추출이_통째로_실패한_경우():
    code, why = _edl_empty_reason([{"full_text": ""}, {"full_text": ""}], {})
    assert code == "extract_empty"
    assert "2편" in why
    assert "키 소진과는 다른" in why, "키 탓으로 오인하게 두면 안 된다"


def test_소스가_아예_없는_경우():
    code, _ = _edl_empty_reason([], {})
    assert code == "no_source"


def test_대본이_너무_짧은_경우():
    """실측 6ae44fe8: extract_json 116바이트(=본문 몇십 자)."""
    code, why = _edl_empty_reason([{"full_text": "가" * 40}], {})
    assert code == "extract_thin" and "40자" in why


def test_사유가_네_가지로_갈린다():
    """뭉개면 안 된다 — 각 상황이 서로 다른 코드를 내야 한다."""
    codes = {
        _edl_empty_reason([], {})[0],
        _edl_empty_reason([{"full_text": ""}], {})[0],
        _edl_empty_reason([{"full_text": "가" * 10}], {})[0],
        _edl_empty_reason([{"full_text": "가" * 9000}], {})[0],
    }
    assert len(codes) == 4, f"사유가 안 갈린다: {codes}"


def test_None과_빈값에도_안전하다():
    """실패 처리 경로가 또 예외를 내면 진짜 원인이 묻힌다."""
    assert _edl_empty_reason(None, None)[0] == "no_source"
    assert _edl_empty_reason([{}], {})[0] == "extract_empty"
    assert _edl_empty_reason([{"full_text": None}], None)[0] == "extract_empty"
