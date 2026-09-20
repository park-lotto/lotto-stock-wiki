"""꾸미기(머리카피) 고른 뒤 갔다 오면 그대로인가(B-11). 머리카피 카드 #hcCopyCards의 첫 카드를 클릭
(produce.html:2235 → STATE.headcopy L7301). 값 읽기는 STATE를 '읽기만' 한다(함수 호출 아님).

★서버 저장 경로 실측(produce.html:8138-8141 saveHeadcopy): 헤드카피는 /api/produce/works가 아니라
/api/produce/mix/settings로 **job에** 저장된다(MIX_JOB 없으면 아예 저장 안 함 — saveHeadcopy 첫 줄
`if(!MIX_JOB) return;`). 그래서 서버값은 GET /api/produce/works/{id} 응답의 "state.headcopy"가 아니라
"settings.headcopy"에 있다(app.py:15426-15435 — settings는 job.get("headcopy")를 실어 보낸다).
브리프 예시 코드는 state.headcopy로 적혀 있었으나 실측 결과와 달라 이 파일에서 settings.headcopy로 고쳤다.
"""
from shopping_shorts.checks.flows import base
from shopping_shorts.checks.verdict import GRAY, Result

META = {"name": "꾸미기(머리카피) 고른 뒤 갔다 오면 그대로인가", "needs_worker": False, "timeout_s": 120}


def _edit(page):
    base.click_step(page, "장면꾸미기")
    cards = page.locator("#hcCopyCards > *")
    if cards.count() == 0:
        raise RuntimeError("머리카피 카드 0개")
    cards.first.click(timeout=3000)
    page.wait_for_timeout(300)
    return page.evaluate("() => STATE.headcopy")


def _read_local(page):
    base.click_step(page, "장면꾸미기")
    return page.evaluate("() => STATE.headcopy")


def _read_server(session, work_id):
    body = session.page.request.get(f"{session.base_url}/api/produce/works/{work_id}").json()
    settings = body.get("settings") or {}
    return settings.get("headcopy")


def run(session):
    try:
        return [base.roundtrip(session, name=META["name"], signature="L2:deco_roundtrip",
                               edit=_edit, read_local=_read_local, read_server=_read_server,
                               go_away=lambda p: base.click_step(p, "제목·태그"),
                               go_back=lambda p: base.click_step(p, "장면꾸미기"))]
    except RuntimeError as e:
        return [Result("L2", META["name"], GRAY, reason=str(e), signature="L2:deco_roundtrip", page="/produce")]
