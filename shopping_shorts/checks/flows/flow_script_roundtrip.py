"""대본 고친 뒤 뒷단계 갔다 오면 대본이 그대로인가(B-10, 사장님 제보 ①).
★Task14 3차 실측(2026-09-07, 회색 원인규명): textarea#scriptText(produce.html:8205,
SCRIPT_MODE_HTML.manual)는 **패널0(제작소)의 AI PICK/빈 상태 안에서만** 렌더되는 죽은 갈래다
(2026-08-16 9단계 개편 이후 실제 '대본생성' 패널은 물리 data-step=8, ORB_TO_PANEL[1]=8). 그
패널엔 scriptText가 없다 — 있는 건 '② 대본 스타일' 카드 + '✍ 내가 직접 쓰기'(s2AddMineDraft)뿐이고,
그 버튼을 누르면 문장칸(contenteditable .s2-sent, id 없음)이 뜬다. 그래서 click_step("대본생성") 뒤
"#scriptText" 대기는 애초에 끝나지 않는 패널을 기다린 것 — 코드가 도는데 안 뜬 게 아니라 아예
없는 요소를 기다린 것이었다(실측: 패널8 진입 뒤 `textarea` count=1, id="hcText"뿐).
편집: '대본생성' 칩 → '✍ 내가 직접 쓰기' → 문장칸에 채움 → '✔ …확정'(s2Confirm, STATE.script 갱신).
이동: s2Confirm 자체가 3단계(화면 붙이기)로 넘어간다 — go_away/go_back은 그 왕복을 흉내낸다.
읽기: STATE.script를 evaluate로 직접 읽는다(UI가 패널마다 다시 그려도 STATE는 그대로다 — 화면
셀렉터에 기대지 않는 게 더 안정적이라는 판단, 서버 값은 여전히 API로 대조).
서버: GET /api/produce/works/{id} 응답의 state.script.
★state 키 실측(app.py:15413-15432, store.py:5245 get_produce_work): 응답은 항상 "state" 키만 쓰고
그 값은 서버가 이미 json.loads()로 파싱한 dict다("state_json"이라는 키는 응답에 없다) — 그래서
아래는 "state" 한 가지로 고정한다(브리프의 이중 폴백은 실측 뒤 제거)."""
from shopping_shorts.checks import browser
from shopping_shorts.checks.flows import base

META = {"name": "대본 고친 뒤 뒷단계 갔다 오면 그대로인가", "needs_worker": False, "timeout_s": 120}
TEXT = "점검용 대본 첫 줄입니다.\n두 번째 줄입니다.\n세 번째 줄입니다."


def _edit(page):
    browser.goto_produce(page, page.url.split("/produce")[0] + "/produce?new=1")
    written = base.write_mine_draft(page, TEXT)
    base.confirm_mine_draft(page)
    return written


def _read_local(page):
    return page.evaluate("() => (window.STATE && STATE.script) || ''")


def _read_server(session, work_id):
    r = session.page.request.get(f"{session.base_url}/api/produce/works/{work_id}")
    body = r.json()
    state = body.get("state") or {}
    return state.get("script")


def run(session):
    return [base.roundtrip(session, name=META["name"], signature="L2:script_roundtrip",
                           edit=_edit, read_local=_read_local, read_server=_read_server,
                           go_away=lambda p: base.click_step(p, "장면꾸미기"),
                           go_back=lambda p: base.click_step(p, "대본생성"))]
