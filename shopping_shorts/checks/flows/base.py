"""L2 표준 패턴(설계 D17·D18). 앱 함수를 evaluate로 부르지 않는다 — 클릭·입력·읽기만."""
import time
from urllib.parse import parse_qs, urlparse

from shopping_shorts.checks import browser
from shopping_shorts.checks.verdict import GREEN, RED, GRAY, Result
from shopping_shorts.checks.sweep import attach_evidence  # 단일 출구(0순위-B) — 사진 규칙은 sweep.py 하나뿐

AUTOSAVE_WAIT_MS = 1500     # scene_lab 1.2초 자동저장 창보다 길게


def current_work_id(page):
    q = parse_qs(urlparse(page.url).query)
    return (q.get("work") or [None])[0]


def roundtrip(session, *, name, signature, edit, read_local, read_server, go_away, go_back):
    page = session.page
    t0 = time.time()
    expected = edit(page)
    go_away(page)
    go_back(page)
    stages = [("복귀 직후", read_local(page))]
    browser.reload_produce(page)
    stages.append(("새로고침 뒤", read_local(page)))
    page.wait_for_timeout(AUTOSAVE_WAIT_MS)
    # ★새로고침 직후엔 맞아 보여도 자동저장 창(1.5초) 동안 화면 값이 조용히 되돌아갈 수 있다
    # (사장님 제보의 핵심 증상 — 화면 메모리엔 남았는데 서버 저장이 안 된 경우가 여기서 드러난다).
    # 그래서 대기 뒤 같은 화면을 한 번 더 읽어 안정적인지 확인한다.
    stages.append(("새로고침 뒤(자동저장 대기 후 재확인)", read_local(page)))
    wid = current_work_id(page)
    if wid is None:
        return Result("L2", name, GRAY, reason="URL에 ?work= 없음(저장이 안 됐거나 흐름이 다름)",
                      signature=signature, page="/produce")
    stages.append(("1.5초 뒤 서버", read_server(session, wid)))
    for label, got in stages:
        if got != expected:
            return Result("L2", name, RED, reason=f"{label}에 값이 달라짐: 기대 {expected!r} != 실제 {got!r}",
                          signature=signature, page="/produce", dur_ms=int((time.time() - t0) * 1000))
    return Result("L2", name, GREEN, reason="복귀·새로고침·서버 3곳 모두 동일", signature=signature,
                  page="/produce", dur_ms=int((time.time() - t0) * 1000))


def write_mine_draft(page, text):
    """대본생성(패널8) → '✍ 내가 직접 쓰기' → 문장칸에 text의 줄을 하나씩 채운다.
    ★Task14 3차 실측(2026-09-07): 실제 대본 입력 UI는 textarea#scriptText가 아니라
    s2AddMineDraft()가 만드는 contenteditable 문장칸(`.s2-sent`, id 없음)이다(produce.html
    S2_MINE_ROLES 기본 5칸: hook·problem·method·proof·cta). 칸이 contenteditable이라
    page.fill은 못 쓴다 — textContent를 채우고 oninput 핸들러(s2EditBeat)가 걸리도록
    input 이벤트를 직접 쏜다(핸들러가 STATE 대신 S2.drafts[i].beats[j]를 갱신하고,
    s2Confirm이 그걸 모아 STATE.script로 만든다).
    줄 수가 칸 수(5)보다 많으면 넘치는 줄은 마지막 칸에 개행으로 이어 붙인다(칸 부족으로
    입력한 문장이 조용히 사라지는 것을 막는다) — '+ 칸 추가'(s2MineAddRow)는 아직 안 쓴다."""
    click_step(page, "대본생성")
    page.click("#s2MineBtn", timeout=5000)
    page.wait_for_selector("#s2d-0 .s2-sent", timeout=5000)
    lines = [l for l in text.split("\n") if l.strip()] or [text]
    cells = page.locator("#s2d-0 .s2-sent")
    n = cells.count()
    if n == 0:
        return ""
    filled = lines[:n]
    if len(lines) > n:
        filled[-1] = "\n".join([filled[-1]] + lines[n:])
    for i, line in enumerate(filled):
        cells.nth(i).evaluate(
            "(el, t) => { el.textContent = t; el.dispatchEvent(new Event('input', {bubbles:true})); }",
            line)
    page.wait_for_timeout(300)
    return "\n".join(filled)


def confirm_mine_draft(page):
    """'✔ 내 대본으로 확정'(s2Confirm) — STATE.script를 채우고 3단계(화면 붙이기)로 넘어간다."""
    page.locator("#s2d-0 .s2-dfoot .btn-next").first.click(timeout=5000)
    page.wait_for_timeout(500)


def click_step(page, label):
    """단계 칩 클릭. ★Task14 2차 실측(2026-09-07): 칩에 보이는 글자는 STEP_LABELS(전체 이름, 예:
    '영상추출/분석')가 아니라 STEP_SHORT(줄인 이름, '영상추출')다 — 전체 이름은 `title` 속성에만
    있다(produce.html dockbar: `title="${STEP_LABELS[i]}"` + `<div class="dkl">${STEP_SHORT[i]}</div>`).
    그래서 get_by_text(label, exact=True)는 어떤 칩과도 절대 안 맞아 클릭이 항상 타임아웃났다 —
    title 속성으로 찾는다(전체 이름이 그대로 있음)."""
    page.locator(f'#steps [title="{label}"]').first.click(timeout=5000)
    page.wait_for_timeout(600)


def run_flow(session, module):
    """★0순위-B(2026-09-07 리뷰 지적): 근거 사진 붙이기가 sweep.py·flows/base.py 두 곳에
    거의 같은 코드로 있었다 — sweep.attach_evidence 하나로 통일했다."""
    try:
        results = module.run(session)
    except Exception as e:  # noqa: BLE001 — 흐름 하나의 예외가 다음 흐름을 막지 않는다
        return [Result("L2", module.META["name"], GRAY, reason=f"흐름 예외 {type(e).__name__}: {str(e)[:200]}",
                       signature=f"L2:{module.__name__.rsplit('.',1)[-1]}", page="/produce")]
    return attach_evidence(session, results)
