"""새 작업을 열면 옛 작업 씨앗이 비나(B-13). 옛 작업에 대본을 넣고 저장 → /produce?new=1 →
S2.seed·STATE.script·HANDOFF가 비어 있어야 한다(handoff/OPUS_지시서_재발버그.md D절)."""
from shopping_shorts.checks import browser
from shopping_shorts.checks.flows import base
from shopping_shorts.checks.verdict import GREEN, RED, Result

META = {"name": "새 작업을 열면 옛 작업 씨앗이 비나", "needs_worker": False, "timeout_s": 90}


def run(session):
    p = session.page
    browser.goto_produce(p, session.base_url + "/produce?new=1")
    base.click_step(p, "대본생성")
    p.fill("#scriptText", "옛 작업 대본")
    base.click_step(p, "장면꾸미기")           # jump → saveWork
    p.wait_for_timeout(800)
    browser.goto_produce(p, session.base_url + "/produce?new=1")
    p.wait_for_timeout(800)
    left = p.evaluate("() => ({seed: (window.S2 && S2.seed) || '', script: STATE.script || '', "
                      "handoff: (window.HANDOFF || []).length})")
    ok = not left["seed"] and not left["script"] and left["handoff"] == 0
    return [Result("L2", META["name"], GREEN if ok else RED, reason=f"남은 값 {left}",
                   signature="L2:new_work_seed", page="/produce?new=1")]
