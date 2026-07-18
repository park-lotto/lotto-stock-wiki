"""규칙 4개가 **같이** 돌 때 서로를 밟지 않는지 — 5비트 실대본 전수.

★이 트랙의 실사고 재발 방지: 스테이지가 각자 맞아도 캡(max_tags_per_beat)을
먼저 먹는 쪽이 이겨 뒤 스테이지가 조용히 밀려난다(2026-07-17: 손으로 박은
감정태그가 캡을 먹어 whisper 샘플이 안 속삭였다 — 탭 이름이 거짓말이 됐다).
"""
import re

from shopping_shorts.narration_naturalize import merge_profile, naturalize_detail

SCRIPT = [
    ("훅", "요새 해외 인플루언서들 손에 하나씩 들려있는 이거."),
    ("페인포인트", "매번 뚜껑 열다가 다 흘리고 닦기도 귀찮지 않나요."),
    ("반전", "근데 이건 완전 다르더라고요."),
    ("실용", "뚜껑을 이렇게 딱 돌리면 끝이에요."),
    ("CTA", "지금 링크에서 확인해보세요."),
]


def _run_all():
    prof = merge_profile({})
    return {role: naturalize_detail(t, prof, beat_role=role,
                                    beat_index=i, beat_total=len(SCRIPT))
            for i, (role, t) in enumerate(SCRIPT)}


def test_hook_has_exclamation_filler_not_hesitation():
    out = _run_all()["훅"]["text"]
    for bad in ("음,", "그,", "뭐,", "자,"):
        assert bad not in out, f"머뭇거림이 살아있다: {out!r}"


def test_hook_tail_emphasised():
    assert ", 이거!" in _run_all()["훅"]["text"]


def test_painpoint_rises():
    assert _run_all()["페인포인트"]["text"].rstrip().endswith("?")


def test_reversal_still_whispers():
    """사장님 A/B 판정 '지금 라이브가 제일 좋다' — 반전 속삭임은 건드리지 않는다."""
    assert "[whispers]" in _run_all()["반전"]["text"]


def test_practical_conclusion_emphasised():
    assert "끝!이에요" in _run_all()["실용"]["text"]


# `test_no_beat_exceeds_tag_cap`(캡 경쟁 봉인) 삭제됨(whole-branch 최종 리뷰
# Finding2, Important, 2026-07-17) — 상한(`<= 2`)만 재는 단언은 태그가 밀려나서
# **줄어드는** 방향의 결함을 절대 못 잡는다(밀려나면 카운트가 작아지니 `<=2`는
# 오히려 더 잘 통과한다). 실측: 이 파일 docstring(`:3-5`)이 존재 이유로 지목한
# 그 실사고(2026-07-17, 손으로 박은 감정태그가 캡을 먹어 whisper가 안 속삭인
# 사고)를 두 가지로 재현해봐도 `<=2`는 둘 다 True로 통과했다(`tags=2`인 채로
# whisper가 빠진 상태). 대신 `test_tag_count_per_beat_and_total`(아래)가 비트별
# **정확한** 태그 개수를 고정하므로 이 테스트를 완전히 포함한다(상한 위반은
# 물론, "밀려나서 줄어듦"까지 잡는다) — 못 죽는 테스트를 남겨두는 대신 삭제.


def test_no_doubled_punctuation_anywhere():
    for role, out in _run_all().items():
        for bad in ("!!", ",,", "??", ", ,"):
            assert bad not in out["text"], f"{role}에 {bad!r} 겹침: {out['text']!r}"


# ── amendment 2: 브리프 넘어서는 검증 ──────────────────────────────────────

def test_full_five_beat_output_locked():
    """5비트 전수 output을 실측값으로 고정 — 어느 한 스테이지가 다른 스테이지의
    산출물을 조용히 바꾸면(트램플) 여기서 바이트 단위로 걸린다. 개별 assert보다
    강한 회귀 그물이다(실측: `python -c` 직접 호출로 캡처, 수기 추정 아님)."""
    out = {role: r["text"] for role, r in _run_all().items()}
    assert out["훅"] == "[curious] 와, 요새 해외 인플루언서들 손에 하나씩 들려있는, 이거!"
    assert out["페인포인트"] == "매번 뚜껑 열다가 다 흘리고 닦기도 귀찮지 않나요?"
    assert out["반전"] == "[whispers] 근데 이건, 완전 다르더라고요…"
    assert out["실용"] == "뚜껑을 이렇게, 딱 돌리면 끝!이에요…"
    assert out["CTA"] == "[excited] 지금 링크에서 확인해보세요…"


def test_tag_count_per_beat_and_total():
    """태그 예산(max_tags_per_beat=2, max_tags_total=3)이 비트별로 실제 몇 개
    쓰였는지 고정한다. 기본 프로파일에서 훅=[curious]·반전=[whispers]·CTA=[excited]
    1개씩, 페인포인트·실용은 0개 — 5비트 합계 3개로 max_tags_total과 정확히
    맞닿는다(이 이상은 이 프로파일에서 구조적으로 안 나온다: emotion_arc·whisper
    둘 다 비트당 최대 1개씩만 붙이므로)."""
    out = _run_all()
    expect_tags = {"훅": 1, "페인포인트": 0, "반전": 1, "실용": 0, "CTA": 1}
    total = 0
    for role, r in out.items():
        n = len(re.findall(r"\[[^\]]+\]", r["text"]))
        assert n == expect_tags[role], f"{role}: 태그 {n}개(기대 {expect_tags[role]})"
        total += n
    assert total == 3


def test_applied_counts_have_no_phantom_entries():
    """`_bump` 계약(ca92f9c8) — 실제 변화 없는 스테이지는 applied에 키 자체가
    없어야 한다(0으로도 안 남는다). 각 비트에서 실제로 발동한 스테이지만
    정확히 1씩 찍히는지 고정한다 — 스테이지가 겹칠 때 유령 카운트(같은 변화를
    두 번 세는 것)가 생기면 여기서 걸린다."""
    out = _run_all()
    expect_applied = {
        "훅": {"endings": 1, "fillers": 1, "emotion_arc": 1, "intonation": 1},
        "페인포인트": {"endings": 1},
        "반전": {"endings": 1, "whisper": 1, "intonation": 1},
        "실용": {"endings": 1, "conclusion": 1, "intonation": 1},
        "CTA": {"endings": 1, "emotion_arc": 1},
    }
    for role, r in out.items():
        assert r["applied"] == expect_applied[role], \
            f"{role}: applied={r['applied']!r} (기대 {expect_applied[role]!r})"
        assert all(v == 1 for v in r["applied"].values()), \
            f"{role}: 1이 아닌 카운트 존재 — 유령/중복 계상 의심 {r['applied']!r}"


def test_hook_interrogative_yields_question_mark_not_bang():
    """Task2(훅 꼬리 강조 !)와 Task3(의문형 ?)가 **같은 훅**에서 부딪히면 Task3가
    이겨야 한다 — 물음표를 삼켜 느낌표로 갈아치우면 의미가 뒤집힌다. SCRIPT의
    훅 문장은 의문형이 아니라서 이 충돌을 안 겪는다 — 별도 의문형 훅으로
    직접 부딪혀본다(주석에 실측 사례로 나온 문장 재사용)."""
    prof = merge_profile({})
    r = naturalize_detail("왜 다들 이걸 살까요.", prof, beat_role="훅",
                           beat_index=0, beat_total=5)
    out = r["text"]
    assert out.rstrip().endswith("?"), f"물음표로 안 끝남: {out!r}"
    assert "!" not in out, f"의문형인데 느낌표가 섞임: {out!r}"
    # Task2가 발동했다면 applied['intonation']에 훅꼬리 강조가 찍혔을 것 —
    # 의문형에서는 훅꼬리 규칙이 아예 접혀야 하므로 intonation 자체가 안 찍힌다
    # (이 문장엔 강조어(_EMPHASIS_WORDS)도 없어 intonation 발동 경로가 이것뿐).
    assert "intonation" not in r["applied"], \
        f"의문형 훅에서 Task2가 발동했다: {r['applied']!r}"


def test_practical_not_in_hook_tail_emphasis_roles_by_default():
    """Task4(실용 결론어 강조 '끝!이에요')와 Task2(마지막 어절 꼬리 강조)가
    같은 비트(실용)에서 동시에 노려볼 수 있는가 — 브리프가 '확인하라'고
    지시한 지점. 기본 프로파일 intonation.emphasis_roles=['훅']에는 실용이
    없으므로 구조적으로 부딪히지 않는다(코드 주석의 주장을 실측으로 확인,
    가정 아님)."""
    out = _run_all()["실용"]["text"]
    # Task4가 만드는 정확한 산출물만 남고, Task2의 "쉼표+마지막어절+!" 꼬리
    # 패턴(예: ", 이에요!")은 안 생겨야 한다.
    assert "끝!이에요" in out
    assert not re.search(r",\s*[가-힣]{1,5}!\s*$", out), \
        f"실용에 훅꼬리 강조 흔적: {out!r}"


def test_determinism_same_input_same_output():
    """같은 입력 → 바이트 동일 출력, 같은 applied. 두 번 돌려 비교(결정성 계약)."""
    prof = merge_profile({})
    for role, text in SCRIPT:
        r1 = naturalize_detail(text, prof, beat_role=role, beat_index=0, beat_total=5)
        r2 = naturalize_detail(text, prof, beat_role=role, beat_index=0, beat_total=5)
        assert r1["text"] == r2["text"], f"{role}: 비결정적 출력"
        assert r1["applied"] == r2["applied"], f"{role}: 비결정적 applied"
