"""10-29 썰템쇼 회원 시험 — 쇼핑형 '이야기 대상 ≠ 파는 제품'(못 사는 원조 아웃백 망고스프레드 → 대체품 무스 메이플버터).
'제조원이 분명 오뚜기인데' 줄에 영국 제품 무스 화면이 나와 무스를 오뚜기 것으로 오해하게 만들었다.
판정 = flow.subject_scene_problems(대본 검사 audit_script 의 subject_scene 칸) · 재료 찾기 = ph_material 이 이야기 대상 낱말도 검색."""
from tools.calcopy.hybrid import flow as F

ST = {"read": {"subject_words": ["아웃백 망고스프레드"], "celeb": ""}, "product": {"name": "무스 메이플버터"},
      "screen_pick": {"chosen": [{"id": "SUBJvid0001", "why": "[이야기 대상] 망고스프레드 레시피"}, {"id": "PRODvid0001", "why": "무스 리뷰"}]}}


def test_subject_line_with_product_picture_rejected():
    S = {"lines": [{"id": "l2", "kind": "tts", "about": "subject"}, {"id": "l5", "kind": "tts", "about": "product"}]}
    M = {"cuts": {"l2": [{"src": "prod_1_2.jpg"}, {"src": "PRODvid0001.mp4"}, {"src": "SUBJvid0001.mp4"}], "l5": [{"src": "prod_1_0.jpg"}]}}
    bad = F.subject_scene_problems(dict(ST), S, M)
    assert len(bad) == 2 and all(b.startswith("l2:") for b in bad)          # 대상 줄의 제품 사진·제품 영상만, 제품 줄은 괜찮다


def test_missing_about_is_a_problem_and_no_subject_is_silent():
    assert F.subject_scene_problems(dict(ST), {"lines": [{"id": "l2", "kind": "tts"}]}, {"cuts": {}})
    assert F.subject_scene_problems({"read": {}}, {"lines": [{"id": "l2", "kind": "tts"}]}, {"cuts": {"l2": [{"src": "prod_1.jpg"}]}}) == []


def test_no_subject_footage_skips_but_logs():
    st = {**ST, "screen_pick": {"chosen": [{"id": "PRODvid0001", "why": "무스"}]}, "log": []}
    S = {"lines": [{"id": "l2", "kind": "tts", "about": "subject"}]}
    assert F.subject_scene_problems(st, S, {"cuts": {"l2": [{"src": "prod_1.jpg"}]}}) == [] and st["log"]


def test_material_search_includes_subject_words():
    st = {**ST, "research": {"queries": ["무스 메이플버터 리뷰"], "keywords": ["무스 메이플버터"]}, "bench": {"id": "b"}}
    do = F.ph_material(st, {}, {}, None)["do"][0]
    assert "아웃백 망고스프레드" in do["queries"] and "아웃백 망고스프레드" in do["keywords"] and do["top"] == 10
