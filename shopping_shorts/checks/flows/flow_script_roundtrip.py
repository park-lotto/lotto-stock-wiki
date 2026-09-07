"""대본 고친 뒤 뒷단계 갔다 오면 대본이 그대로인가(B-10, 사장님 제보 ①).
편집: textarea#scriptText(produce.html:8205) 입력 → STATE.script. 이동: 단계 칩 '장면꾸미기' → '대본생성'.
서버: GET /api/produce/works/{id} 응답의 state.script.
★state 키 실측(app.py:15413-15432, store.py:5245 get_produce_work): 응답은 항상 "state" 키만 쓰고
그 값은 서버가 이미 json.loads()로 파싱한 dict다("state_json"이라는 키는 응답에 없다) — 그래서
아래는 "state" 한 가지로 고정한다(브리프의 이중 폴백은 실측 뒤 제거)."""
from shopping_shorts.checks.flows import base

META = {"name": "대본 고친 뒤 뒷단계 갔다 오면 그대로인가", "needs_worker": False, "timeout_s": 120}
TEXT = "점검용 대본 첫 줄입니다.\n두 번째 줄입니다.\n세 번째 줄입니다."


def _edit(page):
    page.goto(page.url.split("/produce")[0] + "/produce?new=1", wait_until="networkidle")
    base.click_step(page, "대본생성")
    page.fill("#scriptText", TEXT)
    page.wait_for_timeout(300)
    return TEXT


def _read_local(page):
    base.click_step(page, "대본생성")
    return page.input_value("#scriptText")


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
