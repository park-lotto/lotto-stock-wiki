"""L2 표준 패턴(설계 D17·D18). 앱 함수를 evaluate로 부르지 않는다 — 클릭·입력·읽기만."""
import time
from urllib.parse import parse_qs, urlparse

from shopping_shorts.checks import browser
from shopping_shorts.checks.verdict import GREEN, RED, GRAY, Result
from shopping_shorts.checks.sweep import capture_red_evidence  # 단일 출구(0순위-B) — 사진 규칙은 sweep.py 하나뿐

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


def click_step(page, label):
    """단계 칩 클릭. ★Task14 2차 실측(2026-09-07): 칩에 보이는 글자는 STEP_LABELS(전체 이름, 예:
    '영상추출/분석')가 아니라 STEP_SHORT(줄인 이름, '영상추출')다 — 전체 이름은 `title` 속성에만
    있다(produce.html dockbar: `title="${STEP_LABELS[i]}"` + `<div class="dkl">${STEP_SHORT[i]}</div>`).
    그래서 get_by_text(label, exact=True)는 어떤 칩과도 절대 안 맞아 클릭이 항상 타임아웃났다 —
    title 속성으로 찾는다(전체 이름이 그대로 있음)."""
    page.locator(f'#steps [title="{label}"]').first.click(timeout=5000)
    page.wait_for_timeout(600)


def _attach_evidence(session, results):
    """빨강 결과가 나온 시점(흐름이 끝난 직후 화면)을 근거 사진으로 남긴다.
    ★사진 찍기가 실패해도 판정 자체는 그대로 기록된다 — capture_red_evidence가 이미 삼킨다."""
    for r in results:
        if r.verdict == RED and not r.evidence_dir:
            r.evidence_dir = capture_red_evidence(session, r.signature)
    return results


def run_flow(session, module):
    try:
        results = module.run(session)
    except Exception as e:  # noqa: BLE001 — 흐름 하나의 예외가 다음 흐름을 막지 않는다
        return [Result("L2", module.META["name"], GRAY, reason=f"흐름 예외 {type(e).__name__}: {str(e)[:200]}",
                       signature=f"L2:{module.__name__.rsplit('.',1)[-1]}", page="/produce")]
    return _attach_evidence(session, results)
