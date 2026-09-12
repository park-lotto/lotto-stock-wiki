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
    "title_punct", "comma", "enum", "nonwhite_run", "formal",
    "h2_abstract", "card", "punch", "last_standalone", "copy",
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
