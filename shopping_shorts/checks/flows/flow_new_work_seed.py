"""새 작업을 열면 옛 작업 씨앗이 비나(B-13). 옛 작업에 대본을 넣고 저장 → /produce?new=1 →
S2.seed·STATE.script·HANDOFF가 비어 있어야 한다(handoff/OPUS_지시서_재발버그.md D절).
★Task14 3차 실측(2026-09-07): #scriptText는 패널0(제작소) AI PICK 카드 안에서만 렌더되는
죽은 갈래고, '대본생성' 칩이 여는 실제 패널(data-step=8)엔 그 요소가 없다 — 실제 입력은
'✍ 내가 직접 쓰기'(s2AddMineDraft) → 문장칸(.s2-sent) → '✔ 확정'(s2Confirm)이다
(flow_script_roundtrip.py 헤더 주석과 같은 실측, base.write_mine_draft/confirm_mine_draft로 공용화)."""
from shopping_shorts.checks import browser
from shopping_shorts.checks.flows import base
from shopping_shorts.checks.verdict import GREEN, RED, Result

META = {"name": "새 작업을 열면 옛 작업 씨앗이 비나", "needs_worker": False, "timeout_s": 90}


def run(session):
    p = session.page
    browser.goto_produce(p, session.base_url + "/produce?new=1")
    base.write_mine_draft(p, "옛 작업 대본")
    base.confirm_mine_draft(p)                # s2Confirm → STATE.script 갱신 + saveWork
    p.wait_for_timeout(800)
    browser.goto_produce(p, session.base_url + "/produce?new=1")
    p.wait_for_timeout(800)
    left = p.evaluate("() => ({seed: (window.S2 && S2.seed) || '', script: STATE.script || '', "
                      "handoff: (window.HANDOFF || []).length})")
    ok = not left["seed"] and not left["script"] and left["handoff"] == 0
    return [Result("L2", META["name"], GREEN if ok else RED, reason=f"남은 값 {left}",
                   signature="L2:new_work_seed", page="/produce?new=1")]
