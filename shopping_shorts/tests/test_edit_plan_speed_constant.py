"""말 속도 상수 통합 회귀(2026-07-17, 결함②).

배경: 사장님 질문 — "대본과 영상 길이를 맞출 때 여기서 픽스된 걸로 해야 되는 건지,
아니면 속도조절 기능을 넣으면 영상 속 대본이 조절되면서 맞춰지는지". 실제 렌더(_render_mix)는
tts_dur = _probe_duration(tts)(실측)로 컷 길이를 정하므로 결과물은 안 깨진다 — 문제는 "예상
길이"를 계산하는 상수가 세 곳에 흩어져 있었고 값도 제각각(4.5/4.5/6.5)이었다는 것.

이 테스트는 edit_plan.py의 두 지점(① char_target — Gemini에게 "몇 글자 써라", ② narration
글자수 → target_seconds 재계산)이 **같은 이름 있는 상수**(_SYLLABLES_PER_SEC)를 쓰고, 그 값이
2026-07-17 성우 14명 실측치인 5.7인지 잠근다. produce.html의 세 번째 지점(lenText, JS라
파이썬 상수를 못 읽음)은 test_produce_len_text_speed_constant.py가 별도로 잠근다.

네트워크 회피: build_edit_plan()은 내부에서 key_vault.get_live_keys_cascade()를 거쳐 실제
Gemini를 호출한다(이 저장소의 다른 edit_plan 테스트 2건이 comment_gen을 몰래 몹킹하려다
_vault_call이 key_vault를 직접 쓰는 걸 놓쳐 실네트워크를 타는 걸 실측함 — 기존 baseline 결함,
이 파일이 고치는 범위 밖). 그 구멍을 다시 밟지 않도록 여기서는 edit_plan._vault_call
자체를 직접 몽키패치해 프롬프트 문자열을 캡처한다 — 네트워크 제로, 결정적.
"""
import pytest

from shopping_shorts import edit_plan


def _scripts():
    return [
        {"video_id": "A", "full_text": "가방이 흥건",
         "segments": [{"seg_id": "A-0", "start": 0.0, "end": 2.0, "text": "훅", "scene_desc": "컵"}]},
    ]


def test_syllables_per_sec_constant_is_5_7():
    assert edit_plan._SYLLABLES_PER_SEC == 5.7


def test_char_target_prompt_uses_syllables_per_sec_constant(monkeypatch):
    """Gemini에게 보내는 프롬프트의 char_target이 target_seconds * _SYLLABLES_PER_SEC이다."""
    captured = {}

    def fake_vault_call(prompt, schema, max_tries=4):
        captured["prompt"] = prompt
        return {"beats": [
            {"role": "훅", "narration": "가" * 20, "primary": {"seg_id": "A-0"}, "alternates": []},
        ]}

    monkeypatch.setattr(edit_plan, "_vault_call", fake_vault_call)
    edit_plan.build_edit_plan(_scripts(), target_seconds=10, structure="template",
                               video_type="product_reveal")
    expected_char_target = int(10 * edit_plan._SYLLABLES_PER_SEC)
    assert f"약 {expected_char_target}자 내외" in captured["prompt"], (
        f"char_target이 상수(_SYLLABLES_PER_SEC={edit_plan._SYLLABLES_PER_SEC})와 안 맞음 — "
        f"기대 {expected_char_target}, 프롬프트에서 못 찾음")


def test_beat_target_seconds_recalc_uses_same_syllables_per_sec_constant(monkeypatch):
    """narration 글자수 → target_seconds 재계산이 char_target과 같은 상수를 쓴다
    (하나만 바꿔도 화면·계획이 안 갈라진다는 잠금)."""
    narration = "가" * 20  # 20음절(=20글자, 한글 1글자≈1음절)

    def fake_vault_call(prompt, schema, max_tries=4):
        return {"beats": [
            {"role": "훅", "narration": narration, "primary": {"seg_id": "A-0"}, "alternates": []},
        ]}

    monkeypatch.setattr(edit_plan, "_vault_call", fake_vault_call)
    out = edit_plan.build_edit_plan(_scripts(), target_seconds=10, structure="template",
                                     video_type="product_reveal")
    expected_ts = round(max(1.5, len(narration) / edit_plan._SYLLABLES_PER_SEC), 1)
    assert out["beats"][0]["target_seconds"] == expected_ts
    # 220자 → 실제 기준 약 38.6초(220/5.7)이지 4.5 기준 약 48.9초가 아니다(회귀 명세 예시 검증).
    assert round(220 / edit_plan._SYLLABLES_PER_SEC, 1) == pytest.approx(38.6, abs=0.05)


def test_char_target_and_recalc_agree_for_a_given_duration(monkeypatch):
    """①(char_target)과 ②(recalc)가 왕복 일관: char_target 글자수만큼 나레이션을 쓰면
    재계산된 target_seconds가 원래 target_seconds에 가깝다(두 지점이 갈라져 있지 않다는 증거)."""
    target_seconds = 12
    char_target = int(target_seconds * edit_plan._SYLLABLES_PER_SEC)
    narration = "가" * char_target

    def fake_vault_call(prompt, schema, max_tries=4):
        return {"beats": [
            {"role": "훅", "narration": narration, "primary": {"seg_id": "A-0"}, "alternates": []},
        ]}

    monkeypatch.setattr(edit_plan, "_vault_call", fake_vault_call)
    out = edit_plan.build_edit_plan(_scripts(), target_seconds=target_seconds, structure="template",
                                     video_type="product_reveal")
    assert out["beats"][0]["target_seconds"] == pytest.approx(target_seconds, abs=0.2)
