# -*- coding: utf-8 -*-
"""썰 훅 — 꼴 은행·홀린 요인 슬롯·베끼기 판정·결정적 폴백 (2026-09-26 사장님 "이렇게까지 고치고 라이브까지").

실사고: 씨앗 "개발자도 예상 못한 한국 주부의 활용법" → 훅 "개발자도 예상 못한 한국 주부의 미친 활용법"."""
from shopping_shorts import story_hook as sh

SEED = ("개발자도 예상 못한 한국 주부의 활용법 최근 딱 봤을 때는 평범한 필름지처럼 보이는 이 제품을 이용한 "
        "한국의 한 천재 주부의 활용법이 각종 SNS에서 수천만 조회수로 바이럴 폭발함에 논란이라는데")
SLOTS = {"권위자": "개발자", "대상": "주부들", "나라": "한국", "제품군": "열수축 필름", "불편함": "리모컨 손때",
         "장소": "다이소"}


def test_copied_detects_one_word_change_and_passes_new_sentence():
    assert sh.copied("개발자도 예상 못한 한국 주부의 미친 활용법", SEED)
    assert sh.copied("개발자도 예상 못한 한국 주부의 활용법", SEED)
    assert not sh.copied("리모컨 손때 싫은 주부들이 찾아낸 해답", SEED)
    assert not sh.copied("한국 천재가 만들어 떼돈 번 제품의 정체", SEED)


def test_candidates_skip_seed_shape_and_unfillable_molds():
    cands = sh.candidates(SLOTS, SEED)
    filled = [f for _, f in cands]
    assert filled, "슬롯이 있으면 후보가 있어야 한다"
    # 씨앗과 같은 꼴(「OO도 OO 못한 … 활용법」)·씨앗 베낀 문장은 후보에서 빠진다
    assert not any(sh.copied(f, SEED) for f in filled)
    assert "개발자도 예상 못한 미친 활용법" not in filled
    # {계기} 슬롯이 없으니 그 몰드는 안 나온다
    assert not any("{계기}" in m or "대박 터트린" in f for m, f in cands)
    # 나라 슬롯을 빼면 {나라} 몰드가 전부 빠진다(지어낸 나라 금지)
    no_country = sh.candidates({k: v for k, v in SLOTS.items() if k != "나라"}, SEED)
    assert not any("{나라}" in m for m, _ in no_country)


def test_pick_rotates_by_key_and_nth():
    picks = {sh.pick(SLOTS, "member-%d" % i, 0, SEED)[1] for i in range(40)}
    assert len(picks) >= 8, "회원 40명이 같은 씨앗을 써도 첫 줄이 여러 가지여야 한다 — %d가지" % len(picks)
    a, b = sh.pick(SLOTS, "same-job", 0, SEED)[1], sh.pick(SLOTS, "same-job", 1, SEED)[1]
    assert a != b, "같은 작업의 1안·2안은 다른 꼴"
    assert sh.pick(SLOTS, "same-job", 0, SEED) == sh.pick(SLOTS, "same-job", 0, SEED), "같은 키면 재현된다"


def test_resolve_replaces_copied_hook_deterministically_and_keeps_good_hook():
    good, why = sh.resolve("리모컨 손때 싫은 주부들이 찾아낸 해답", SLOTS, "k", 0, SEED)
    assert good == "리모컨 손때 싫은 주부들이 찾아낸 해답" and why == ""
    fixed, why = sh.resolve("개발자도 예상 못한 한국 주부의 미친 활용법", SLOTS, "k", 0, SEED)
    assert why == "copied→deterministic" and not sh.copied(fixed, SEED) and "{" not in fixed
    empty, why = sh.resolve("", SLOTS, "k", 0, SEED)
    assert why == "empty→deterministic" and empty
    # 슬롯이 하나도 없어도 예비 꼴로 채운다 — 안이 사라지는 길이 없다
    bare, why = sh.resolve("개발자도 예상 못한 한국 주부의 활용법", {}, "k", 0, SEED)
    assert bare and "{" not in bare and not sh.copied(bare, SEED)


def test_clean_slots_and_instruction_never_show_seed_sentence():
    s = sh.clean_slots({"권위자": " 개발자 ", "나라": "없음", "대상": "x" * 30, "장소": "다이소"})
    assert s == {"권위자": "개발자", "장소": "다이소"}
    ins = sh.instruction("{권위자}도 감탄한 천재 아이디어", s)
    assert "권위자=개발자" in ins and "개발자도 예상 못한" not in ins
