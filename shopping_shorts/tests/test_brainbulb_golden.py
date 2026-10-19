# -*- coding: utf-8 -*-
"""정답 회귀 — **볼케이노가 실제로 만든 5편은 우리 린터를 전부 통과해야 한다.**

왜 필요한가 (2026-09-12 실사고):
  마지막 컷 규칙(`last_standalone`)을 새로 넣었더니 우리 편의 버그를 잡으면서
  **볼케이노 정답 2편(이동건·테이저건)까지 반려**했다. 종결 어미 목록에 '~셈'·'~아닌데'가
  빠져 있던 탓이다. 손으로 돌려보다 발견했고, 안 봤으면 그대로 커밋될 뻔했다.

  → 규칙을 넣거나 고칠 때 이 파일이 자동으로 막는다. 규칙이 늘수록 필요해진다.

이 테스트가 지키는 계약:
  ① 정답 5편은 어떤 REJECT 규칙에도 걸리지 않는다 (규칙별로 갈라 보고 — 어느 규칙이 범인인지 바로 나온다)
  ② 규칙을 추가하면 여기 등록도 해야 한다 (등록 안 된 새 규칙이 있으면 실패 → 검증 없이 늘어나는 걸 막는다)
  ③ ffmpeg 없이도 돈다 (배치가 필요한 규칙만 건너뛴다) — CI·다른 PC에서도 반드시 실행된다
"""
import json
from pathlib import Path

import pytest

from shopping_shorts.brainbulb import lint

FX = Path(__file__).parent / "fixtures" / "brainbulb"
GOLDEN = ["parksuhong", "leedonggun", "taser", "borneo", "parkwi"]

# 배치(줄나눔)가 있어야 판정할 수 있는 규칙 — ffmpeg 없이 도는 이 파일에서는 제외한다.
# (배치까지 포함한 검사는 test_brainbulb_pipeline.test_real_scripts_pass_lint 가 한다)
_NEEDS_LAYOUT = {r.id for r in lint.RULES if r.needs_layout}

# 정답 5편으로 검증되는 REJECT 규칙 목록. 규칙을 추가하면 여기에도 넣어라(②).
CHECKED = {
    "title_punct", "comma", "enum", "nonwhite_run", "formal", "ending_mix", "ending_declared",
    "h2_abstract", "card", "punch", "last_standalone", "copy", "cut_count", "card_img", "slot_seq", "slot_count",
}


def _script(job):
    """볼케이노 payload → 우리 대본 형식. 원문 그대로 쓴다(글자를 고치면 정답이 아니다)."""
    p = json.loads((FX / job / "payload.json").read_text(encoding="utf-8"))
    groups = []
    for g in p["groups"]:
        ng = {"text": g["text"], "color": g["color"], "role": g["role"]}
        if g.get("img") is not None:
            ng["img"] = g["img"]
        if g.get("meme"):
            ng["meme"] = "경악/충격"      # payload엔 파일 경로만 있다 → enum 통과용 감정
        groups.append(ng)
    return {"title": p["title"], "region": p.get("region"), "groups": groups}, (p.get("transcript") or "")


@pytest.mark.parametrize("job", GOLDEN)
@pytest.mark.parametrize("rule_id", sorted(CHECKED))
def test_golden_episode_passes_each_rule(job, rule_id):
    """정답 편 × 규칙 하나씩 — 실패하면 '어느 편의 어느 규칙'인지 이름에 바로 나온다."""
    rule = next(r for r in lint.RULES if r.id == rule_id)
    s, src = _script(job)
    issues = rule.check(s, {"source_text": src})
    bad = [i for i in issues if i.level == lint.REJECT]
    assert not bad, [f"{i.where} «{i.found}» — {i.why}" for i in bad]


@pytest.mark.parametrize("job", GOLDEN)
def test_golden_episode_passes_all_rules_at_once(job):
    """규칙 전체를 한 번에 — 규칙 사이 상호작용까지 본다."""
    s, src = _script(job)
    issues, _ = lint.lint(s, source_text=src, do_layout=False)
    bad = [i for i in issues if i.level == lint.REJECT]
    assert not bad, [f"{i.rule}: {i.where} «{i.found}»" for i in bad]


def test_every_reject_rule_is_registered():
    """새 REJECT 규칙을 넣으면 이 파일에도 등록해야 한다 — 검증 없이 규칙이 늘어나는 걸 막는다."""
    actual = {r.id for r in lint.RULES if r.level == lint.REJECT} - _NEEDS_LAYOUT
    missing = actual - CHECKED
    stale = CHECKED - actual
    assert not missing, (
        f"새 REJECT 규칙 {sorted(missing)} 이 정답 회귀에 등록되지 않았다. "
        f"test_brainbulb_golden.CHECKED 에 추가하고, 정답 5편이 통과하는지 확인하라")
    assert not stale, f"CHECKED 에 없는 규칙이 남아 있다: {sorted(stale)}"


def test_golden_fixtures_are_intact():
    """정답 표본이 통째로 갈리면 회귀가 무의미해진다 — 편수·컷수를 못박는다."""
    counts = {}
    for job in GOLDEN:
        s, _ = _script(job)
        counts[job] = len(s["groups"])
    assert counts == {"parksuhong": 28, "leedonggun": 25, "taser": 22, "borneo": 32, "parkwi": 28}, counts


# ── 말맛 규칙 (2026-09-16 사장님 "너무 나열식 밋밋하고 재미없는거 아닌가") ──────────

def test_speaker_voice_warns_only_when_none(tmp_path):
    """★말 거는 컷이 하나도 없을 때만 알린다. 실물 박위 편이 0/28 이므로 REJECT 면 안 된다."""
    from shopping_shorts.brainbulb import lint
    plain = {"groups": [{"text": "그는 열일곱이었다", "color": "WHITE"} for _ in range(22)]}
    assert lint.r_speaker_voice(plain, {}), "전부 3인칭인데 알리지 않는다"
    spoken = dict(plain)
    spoken["groups"] = list(plain["groups"])
    spoken["groups"][3] = {"text": "근데 카트리지가 끼워져 있었음", "color": "WHITE"}
    assert not lint.r_speaker_voice(spoken, {}), "말 거는 컷이 있는데도 알린다"


def test_speaker_voice_is_a_warning_not_a_reject():
    """실물 한 편(박위)이 0개다 — 반려로 만들면 정답 편이 막힌다."""
    from shopping_shorts.brainbulb import lint
    r = next(r for r in lint.RULES if r.id == "speaker_voice")
    assert r.level == lint.WARN


def test_speaker_voice_passes_four_of_five_golden():
    """★실물로 재라 — 규칙이 정답 편을 무더기로 막으면 그 규칙이 틀린 것이다.

    실측 2026-09-16: 말 거는 컷은 테이저건 5 · 박수홍 4 · 이동건 3 · 보르네오 1 · 박위 0.
    박위만 0개이므로 경고도 박위 하나여야 한다.
    """
    warned = [n for n in GOLDEN if lint.r_speaker_voice(_script(n)[0], {})]
    assert warned == ["parkwi"], f"실물에서 예상 밖 경고: {warned}"


def test_prompt_tells_which_ending_style_to_pick():
    """★«둘 중 하나로 통일»만 있으면 모델이 늘 뉴스체로 도망간다(우리 두 편 음슴 0)."""
    from shopping_shorts.brainbulb import prompt
    t = prompt.TARGETS
    assert "시간순으로 벌어지는" in t and "~함/~됨/~임" in t, "어느 소재에 어느 계열인지가 없다"


def _styled(style, eum, news):
    g = [{"text": "다가옴", "color": "WHITE"} for _ in range(eum)]
    g += [{"text": "열일곱이었다", "color": "WHITE"} for _ in range(news)]
    return {"ending_style": {"style": style}, "groups": g}


def test_declared_ending_style_must_match_the_script():
    """★밝힌 계열과 실제가 어긋나면 반려한다.

    사장님 2026-09-16: "어떤 소재이던 규칙을 지키게 해야지 / 소녀병도 음슴체를 한다면
    그렇게 나와야지 뉴스체가 나오면 검사하고."
    프롬프트에 «사건이 시간순이면 음슴체»라고 적어두고 판정을 안 붙였더니 모델이 늘
    뉴스체로 썼다 — 우리 편 3개가 전부 음슴 0이었다.
    """
    assert lint.r_ending_declared(_styled("음슴체", 2, 10), {}), "음슴체라 해놓고 뉴스체인데 통과시킨다"
    assert lint.r_ending_declared(_styled("뉴스체", 10, 1), {}), "뉴스체라 해놓고 음슴체인데 통과시킨다"
    assert not lint.r_ending_declared(_styled("음슴체", 10, 2), {}), "음슴체로 맞게 썼는데 반려한다"
    assert not lint.r_ending_declared(_styled("뉴스체", 1, 10), {}), "뉴스체로 맞게 썼는데 반려한다"


def test_declared_ending_style_is_optional():
    """안 밝힌 대본(옛 산출물·시험 데이터)은 막지 않는다 — 없는 필드로 반려하면 안 된다."""
    s = _styled("", 2, 10)
    s.pop("ending_style")
    assert not lint.r_ending_declared(s, {})


def test_declared_ending_counts_only_closed_cuts():
    """★분모는 '종결이 잡힌 컷'이다. 체언으로 끝나는 컷이 많아 전체 컷으로 나누면
    어떤 편도 과반을 못 넘어 규칙이 늘 반려하게 된다."""
    s = _styled("음슴체", 6, 2)
    s["groups"] += [{"text": "그때 그 소녀의 나이", "color": "WHITE"} for _ in range(14)]
    assert not lint.r_ending_declared(s, {}), "체언 종결 컷 때문에 과반 판정이 깨진다"
