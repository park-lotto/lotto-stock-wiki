"""L1 전수 훑기 — 명세 없이 DOM에서 발견해 눌러보고 '터졌나'만 본다(설계 §4.4).
B-01 제작소 전수 · B-02 hit-test(요소 중앙의 elementFromPoint가 그 요소/자손이 아니면 '가려짐' —
투명 체크박스가 스위치 위에 깔려 클릭이 안 먹던 실사고) · B-03 목록 카드 무예외 · B-08 사이드바 쿠팡 ·
B-09 리포터 생존.

★거짓 빨강 방지:
- Session 생성/로그인 실패(RuntimeError), playwright 미설치(ImportError), 그 외 브라우저/네트워크 계열
  예외는 전부 이 층에서 잡아 GRAY(판정 불가)로 바꾼다 — "서비스가 아픔"이 아니라 "점검이 못 함"이다.
- 자동화 탭은 setInterval이 스로틀된다(이 프로젝트 실측: 3초에 4회, 정상은 25~30회). browser.timer_probe
  측정값이 25 미만이면 이번 run 전체를 GRAY로 낮춘다 — 타이밍에 의존한 판정을 못 믿기 때문이다.
- signature_of()는 discover_targets가 매기는 idx(DOM 순서 의존, 리렌더마다 바뀔 수 있음)를 절대 쓰지
  않는다 — id > onclick 함수명 > 텍스트 순으로만 정한다.
"""
import re
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from shopping_shorts.checks import browser
from shopping_shorts.checks.verdict import GRAY, GREEN, RED, Result

# ── 빨간 줄 증거 사진(2026-09-07 리뷰 반영) ─────────────────────────────────
#   ★경로는 app.py의 _EVIDENCE_ROOT·checks.html의 evidence_ok 계약과 반드시 맞아야 한다
#   (Task13 — /api/admin/checks/evidence/<id>/<filename>이 이 폴더 밑에서 shot.png를 찾는다).
#   run_checks.py는 수정 금지 목록이라 run_id를 함수 인자로 못 받는다 — 대신 캡처 순간의
#   ms 타임스탬프로 유일성을 보장한다(같은 run 안 재실행은 없고, check_runs.started~finished
#   구간과 폴더명 타임스탬프를 대조하면 어느 run인지 되짚을 수 있다).
EVIDENCE_ROOT = Path(__file__).resolve().parent.parent / "data" / "checks_evidence"
_EVIDENCE_SAFE_RE = re.compile(r"[^A-Za-z0-9_-]+")
_EVIDENCE_MAX_AGE_DAYS = 14  # 이보다 오래된 증거 폴더는 다음 sweep_produce() 시작 시 정리


def _evidence_slug(signature):
    s = _EVIDENCE_SAFE_RE.sub("_", signature or "x").strip("_")[:80]
    return s or "x"


def capture_red_evidence(session, signature):
    """빨강(필요시 회색)으로 판정되는 순간의 화면을 EVIDENCE_ROOT/<slug>_<ms>/shot.png로 남긴다.
    ★캡처 실패가 점검 자체를 죽이면 안 된다 — 무슨 예외든 삼키고 빈 문자열(증거 없음)로 폴백한다."""
    try:
        page = getattr(session, "page", None)
        if page is None:
            return ""
        dirname = f"{_evidence_slug(signature)}_{int(time.time() * 1000)}"
        outdir = EVIDENCE_ROOT / dirname
        outdir.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(outdir / "shot.png"))
        return dirname
    except Exception:  # noqa: BLE001 — 스크린샷 실패는 판정에 영향을 주지 않는다(evidence_dir="")
        return ""


def cleanup_old_evidence(max_age_days=_EVIDENCE_MAX_AGE_DAYS):
    """EVIDENCE_ROOT 안의 오래된 증거 폴더만 지운다 — 무한 누적으로 디스크가 차는 것을 막는다.
    ★삭제 대상이 EVIDENCE_ROOT 밖으로 못 나가게 resolve() 후 relative_to로 재검증(app.py의
    경로탈출 방어와 같은 원리 — 여기선 우리가 만든 폴더만 지우지만 방어를 한 번 더 겹친다)."""
    root = EVIDENCE_ROOT.resolve()
    if not root.is_dir():
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    removed = 0
    for child in root.iterdir():
        try:
            candidate = child.resolve()
            candidate.relative_to(root)  # 루트 밖이면 ValueError → 절대 안 지운다
            if not candidate.is_dir():
                continue
            mtime = datetime.fromtimestamp(candidate.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                shutil.rmtree(candidate, ignore_errors=True)
                removed += 1
        except Exception:  # noqa: BLE001 — 정리 실패도 점검을 막으면 안 된다
            continue
    return removed

_DISCOVER_JS = """() => {
  const els = [...document.querySelectorAll('button, [onclick], input, select, textarea, a[href^="/"]')];
  return els.map((el, idx) => {
    const r = el.getBoundingClientRect();
    const st = getComputedStyle(el);
    const visible = r.width > 2 && r.height > 2 && st.visibility !== 'hidden' && st.display !== 'none';
    el.dataset.chkIdx = idx;
    return {idx, tag: el.tagName.toLowerCase(), id: el.id || '', onclick: el.getAttribute('onclick') || '',
            text: (el.innerText || el.value || el.placeholder || '').trim().slice(0, 20),
            type: el.getAttribute('type') || '', visible, disabled: !!el.disabled,
            x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width, h: r.height};
  }).filter(e => e.visible && !e.disabled);
}"""

_HIT_JS = """(idx) => {
  const el = document.querySelector(`[data-chk-idx="${idx}"]`);
  if (!el) return false;
  const r = el.getBoundingClientRect();
  const top = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
  return !!top && (top === el || el.contains(top) || top.contains(el));
}"""

_TIMER_THROTTLE_MIN = 25   # browser.timer_probe(3초) 정상≈30, 스로틀=4. 이 밑이면 결과를 못 믿는다.
_BLANK_FLOOR = 60          # 백지 판정 절대 하한 — 리뷰 실측: 1000→80은 모달/패널이 닫힌 정상 축소일 뿐이라
                           # 상대비율(10%)로는 오탐. 정상 화면이면 최소 요약문·안내문 정도는 남으므로
                           # "본문이 60자 미만으로까지 떨어졌다"만 진짜 백지로 본다(에러 동반 여부와 무관하게
                           # 이 하한 자체가 실질적 백지 신호). 브리프 원 테스트(1000→50=RED)와
                           # 리뷰 재현(1000→80=GREEN) 둘 다 만족하는 값.


def signature_of(info):
    """id > onclick 함수명 > 텍스트 순. discover_targets가 매기는 idx는 절대 쓰지 않는다(DOM 순서 불안정)."""
    if info.get("id"):
        return f"{info['tag']}#{info['id']}"
    m = re.match(r"\s*(?:event\.stopPropagation\(\);)?\s*([A-Za-z_$][\w$]*)\s*\(", info.get("onclick") or "")
    if m:
        return f"{info['tag']}@{m.group(1)}"
    return f"{info['tag']}:{info.get('text', '')}"


def classify(before, after, body_before, body_after, navigated):
    """오탐 방지 핵심: 새로 늘어난 것만 본다(기존에 있던 실패는 카운트 안 함), 페이지 이동 중엔 백지 판정을
    쉰다(navigated), 원래 짧은 페이지는 백지 절대기준(200자) 밑이라 대상이 아니다."""
    if len(after["pageerrors"]) > len(before["pageerrors"]):
        return RED, "pageerror: " + after["pageerrors"][-1]
    if after["client_error_posts"] > before["client_error_posts"]:
        return RED, "화면 에러 리포트 발생"
    new_fail = after["failed_responses"][len(before["failed_responses"]):]
    if new_fail:
        return RED, f"응답 실패 {new_fail[0][1]} {new_fail[0][0]}"
    if len(after["console_errors"]) > len(before["console_errors"]):
        return RED, "console.error: " + after["console_errors"][-1]
    if not navigated and body_before > 200 and body_after < _BLANK_FLOOR:
        return RED, f"백지(본문 {body_before}→{body_after}, 절대하한 {_BLANK_FLOOR} 미만)"
    return GREEN, ""


def discover_targets(page):
    return page.evaluate(_DISCOVER_JS)


def hit_test(page, idx):
    return bool(page.evaluate(_HIT_JS, idx))


def _body_len(page):
    return page.evaluate("() => (document.body && document.body.innerText || '').length")


def _blocked_path(entry):
    """session.blocked 항목은 browser.py에서 'METHOD /path' 형태로 쌓인다(설계 D10 안전 그물)."""
    parts = entry.split(" ", 1)
    return parts[1] if len(parts) == 2 else entry


_GENERIC_NETFAIL_MARKERS = ("failed to load resource", "net::err_")
# ★Task14 2차 실측(2026-09-07): route.abort()로 막힌 요청이 실제 Chromium에서 내는 console 메시지는
# "Failed to load resource: net::ERR_FAILED"뿐 — 실패한 URL이 텍스트에 안 실린다(원래 필터의 텍스트
# 부분매칭 전제가 이 경우엔 애초에 성립 안 함). 그래서 client_error_posts와 같은 "개수만큼만 보수적으로
# 깎는" 방식을 콘솔에러에도 적용한다 — 무관한 진짜 JS 에러(TypeError 등)는 이 마커에 안 걸려 그대로 산다.


def filter_blocked_noise(after, before, blocked_paths):
    """안전 그물이 route.abort()로 막은 요청 때문에 생긴 에러는 판정에서 뺀다(오탐 방지 #2).
    새로 막힌 경로가 없으면 원본 그대로 통과시킨다 — 무관한 진짜 에러는 절대 지우지 않는다."""
    if not blocked_paths:
        return after

    def _hits(text):
        return any(p in text for p in blocked_paths)

    def _is_generic_netfail(text):
        low = text.lower()
        return any(m in low for m in _GENERIC_NETFAIL_MARKERS)

    filtered_pageerrors = [e for e in after["pageerrors"] if not _hits(e)]
    filtered_failed = [f for f in after["failed_responses"] if not any(p in f[0] for p in blocked_paths)]

    filtered_console = []
    generic_budget = len(blocked_paths)  # 새로 막힌 요청 수만큼만 "경로 없는 일반 실패 메시지"를 깎는다
    for e in after["console_errors"]:
        if _hits(e):
            continue                      # 경로가 텍스트에 그대로 있으면 확실한 매치
        if generic_budget > 0 and _is_generic_netfail(e) and e not in before["console_errors"]:
            generic_budget -= 1
            continue                      # 경로 없는 일반 네트워크 실패 — 우리가 막은 요청일 가능성이 크다
        filtered_console.append(e)

    # client_error_posts는 카운터뿐이라 메시지로 못 거른다 — 이번 조작이 새로 막은 요청 수만큼만
    # 늘어난 증가분을 깎는다(요청 하나가 대개 리포트 하나를 만든다는 보수적 가정). 그 이상 늘었다면
    # 진짜 앱 에러가 섞였다는 뜻이라 나머지는 그대로 살려둔다.
    delta = max(0, after["client_error_posts"] - before["client_error_posts"])
    adjusted_client_errors = after["client_error_posts"] - min(delta, len(blocked_paths))
    return {"pageerrors": filtered_pageerrors, "console_errors": filtered_console,
            "client_error_posts": adjusted_client_errors, "failed_responses": filtered_failed}


def _press(session, info, url):
    page, sink = session.page, session.errors
    before, body_before = sink.snapshot(), _body_len(page)
    blocked_before_n = len(session.blocked)
    t0 = time.time()
    sel = f'[data-chk-idx="{info["idx"]}"]'
    try:
        if info["tag"] in ("input", "textarea") and info["type"] not in ("checkbox", "radio", "file", "button", "submit"):
            page.fill(sel, "점검" if info["tag"] == "textarea" or info["type"] in ("", "text", "search") else "1", timeout=3000)
        elif info["type"] == "file":
            return Result("L1", info["text"] or info["tag"], GRAY, reason="파일 입력은 건너뜀",
                          signature=signature_of(info), page=url)
        else:
            page.click(sel, timeout=3000, no_wait_after=True)
        page.wait_for_timeout(1500)
    except Exception as e:  # noqa: BLE001 — 클릭 실패 자체가 판정 근거
        sig = signature_of(info)
        return Result("L1", info["text"] or info["tag"], RED, reason=f"조작 실패 {type(e).__name__}: {str(e)[:120]}",
                      signature=sig, page=url, dur_ms=int((time.time() - t0) * 1000),
                      evidence_dir=capture_red_evidence(session, sig))
    navigated = page.url.split("?")[0] != url.split("?")[0]
    new_blocked = [_blocked_path(e) for e in session.blocked[blocked_before_n:]]
    after = filter_blocked_noise(sink.snapshot(), before, new_blocked)
    v, why = classify(before, after, body_before, _body_len(page), navigated)
    sig = signature_of(info)
    ev = capture_red_evidence(session, sig) if v == RED else ""
    return Result("L1", info["text"] or info["tag"], v, reason=why, signature=sig, page=url,
                  dur_ms=int((time.time() - t0) * 1000), evidence_dir=ev)


def sweep_url(session, url, reopen=None, skip=None):
    """★2026-09-07 리뷰 지적: 지금 run_ui(run_checks.py) 경로에서는 아무도 이 함수를 안 부른다
    (sweep_produce가 위 주석대로 "패널이 열리는가"만 보는 축소판으로 바뀌었기 때문 — discover_targets·
    hit_test·_press도 이 함수 안에서만 쓰여 함께 프로덕션 호출부 0). 지우지 않는다 — 복구 조건은
    위 sweep_produce 주석에 적혀 있다(go(N) 포함 패널전환 조작을 걸러내거나 복귀판정을 URL이 아니라
    '현재 활성 패널' 기준으로 고치면 다시 켤 수 있다).

    한 URL의 조작 가능한 요소 전부. reopen(page)는 패널을 다시 여는 함수(제작소용).
    skip(info)가 True를 돌려주는 요소는 아예 안 누른다(제작소 전수가 처음 실제로 패널을 여는 데
    성공한 2026-09-07에야 드러난 문제: `discover_targets`는 패널이 아니라 페이지 전체를 훑는데,
    /produce엔 앱 공통 사이드바(로그아웃·작업삭제·다른 화면 이동)까지 같이 있어서 그것들까지
    실제로 눌러버렸다 — 로그아웃/작업삭제는 판정불가·안전사고로 이어질 수 있다)."""
    page = session.page
    browser.goto_produce(page, session.base_url + url)
    if reopen:
        reopen(page)
    targets = discover_targets(page)
    if skip:
        targets = [t for t in targets if not skip(t)]
    out = []
    for info in targets:
        if not hit_test(page, info["idx"]):
            sig = signature_of(info)
            out.append(Result("L1", info["text"] or info["tag"], RED, reason="가려짐(elementFromPoint 불일치)",
                              signature=sig, page=url, evidence_dir=capture_red_evidence(session, sig)))
            continue
        out.append(_press(session, info, url))
        if page.url.split("?")[0] != (session.base_url + url).split("?")[0]:
            browser.goto_produce(page, session.base_url + url)
            if reopen:
                reopen(page)
            page.evaluate(_DISCOVER_JS)   # 인덱스 재부여
    return out


def _throttled_results(name):
    return [Result("L1", name, GRAY, reason="점검 못 함: 서비스/브라우저 연결 실패 또는 로그인 안 됨", signature=f"L1:gray:{name}")]


def _run_guarded(name, fn):
    """RuntimeError(로그인·서버 실패)·ImportError(playwright 없음)·기타 브라우저/네트워크 예외를
    빨강이 아니라 회색(판정 불가)으로 감싼다. 이 층이 실측을 못 했을 뿐 서비스가 아픈 게 아니다."""
    try:
        return fn(), True
    except (RuntimeError, ImportError) as e:
        return [Result("L1", name, GRAY, reason=f"점검 못 함: {type(e).__name__}: {str(e)[:150]}",
                       signature=f"L1:gray:{name}")], False
    except Exception as e:  # noqa: BLE001 — playwright TimeoutError 등 브라우저 계열도 판정 불가로
        return [Result("L1", name, GRAY, reason=f"점검 못 함(연결/타임아웃): {type(e).__name__}: {str(e)[:150]}",
                       signature=f"L1:gray:{name}")], False


def _apply_throttle_gate(session, results):
    """browser.timer_probe로 실측한 setInterval 스로틀이 25회 미만이면 이번 run 전체를 GRAY로 낮춘다
    (타이밍 기반 판정을 못 믿기 때문 — Task 8은 측정만 하고 판정은 이 층에 위임했다)."""
    try:
        from shopping_shorts.checks import browser
        n = browser.timer_probe(session.page)
    except Exception:  # noqa: BLE001 — 측정 자체가 실패해도 결과는 그대로 둔다(측정 불가일 뿐)
        return results
    if n >= _TIMER_THROTTLE_MIN:
        return results
    return [Result(r.layer, r.name, GRAY, reason=f"타이머 스로틀(측정 {n}회<{_TIMER_THROTTLE_MIN}) — 판정 보류: {r.reason}",
                   signature=r.signature, page=r.page, evidence_dir=r.evidence_dir, dur_ms=r.dur_ms) for r in results]


_APP_SHELL_ONCLICK_MARKERS = ("__ssLogout", "__ssDelWork", "__ssRenWork", "ssOpenBugReport")


def _is_app_shell_nav(info):
    """제작소 콘텐츠가 아니라 (a) 앱 공통 사이드바(.ss-nav) 항목이거나 (b) 패널 이동용 단계 칩
    자체인가 — 둘 다 "이 패널의 콘텐츠"가 아니라 "다른 곳으로 옮기는 네비게이션 컨트롤"이라 눌러선
    안 된다.
    ★실측(2026-09-07): discover_targets가 패널이 아니라 페이지 전체를 훑어, 이걸 안 거르면
    제작소 전수가 실제로 '로그아웃'·작업 '✕'(삭제)·'✏️'(이름변경)·'🐞 오류신고' 버튼까지 누른다.
    이런 요소는 늘 있고(로그인만 하면 어느 화면에서든 동일) 제작소 화면 자체가 바뀌어도 안 바뀌므로
    B-01(제작소 전수)이 검증하려는 대상이 아니다 — 판정에서 빼되 누르지도 않는다(안전).
    ★2차 실측(같은 날): 단계 칩(jump(N))도 안 거르면 프레스 루프가 그 칩을 또 눌러 다른 패널로
    넘어가버려서 그 뒤 요소들이 전부 "가려짐/조작실패"로 연쇄 오탐났다(284건 빨강 폭증의 원인)."""
    oc = info.get("onclick") or ""
    if info.get("tag") == "a":
        # ★3차 실측(2026-09-07): "🔐 관리페이지"·"👤 마이페이지" 등은 onclick이 아니라 순수
        # <a href>라 문자열 마커·location.href 검사에 안 걸리고도 페이지를 통째로 벗어나 같은
        # 연쇄 오탐(가려짐/조작실패)을 냈다. 이 화면에서 패널 콘텐츠는 div/button/input이지
        # <a>가 아니다(사이드바·전역 링크만 앵커) — 태그로 통째로 뺀다.
        return True
    if any(m in oc for m in _APP_SHELL_ONCLICK_MARKERS):
        return True
    if oc.startswith("location.href="):
        return True   # 사이드바 메뉴 전부 이 형태 — 다른 화면으로 이동해버려 제작소 전수 취지에 안 맞음
    if re.fullmatch(r"jump\(\d+\)", oc):
        # ★실측(2026-09-07, 284건 빨강 폭증의 진짜 원인): 단계 칩(onclick="jump(N)") 자체도
        # discover_targets가 "패널 안 요소"로 주워서 눌러버렸다 — _open()이 이미 이 칩으로 패널을
        # 여는데, 프레스 루프가 같은 칩을 또 눌러 **다른 패널로 넘어가버려** 그 뒤로 발견된 요소들이
        # (원래 패널 기준 좌표라) 전부 "가려짐/조작실패"로 연쇄 오탐났다. 칩 자체는 네비게이션
        # 컨트롤이지 이 패널의 콘텐츠가 아니므로 판정 대상에서 뺀다(_open이 이미 검증 목적으로 누른다).
        return True
    return False




def sweep_produce(session, panels=range(10)):
    """제작소 10패널: 단계 칩을 눌러 각 패널이 실제로 열리는지만 확인한다.
    ★2026-09-07 서버 실측 축소(중요): 원래는 각 패널 안 요소를 discover+press로 전부 눌러봤는데,
    같은 코드·같은 데이터로 두 번 돌려 빨강이 13건→259건으로 **재현이 안 될 만큼 들쭉날쭉**했다.
    앱셸(로그아웃 등)·jump(N) 칩·<a href>는 걸렀지만 "← 이전"/"다음 →"(go(N))처럼 **같은 URL 안에서
    패널만 바꾸는** 조작이 더 있고, 그런 조작이 눌리면 `sweep_url`의 항해-복귀 로직(page.url 비교)이
    URL이 안 바뀌었으니 "복귀할 필요 없다"고 판단해 그 뒤 요소들은 옛 패널 기준 좌표로 계속 눌려
    "가려짐/조작실패"가 연쇄 오탐났다 — 그리고 그 순서·타이밍이 매번 달라 결과가 안정적이지 않았다.
    이유 있는 결과가 매번 달라지면(=재현 안 되면) 그 자체로 못 믿을 신호라, 원인(모든 단계이동 조작을
    다 걸러내는 것)을 이번 라운드 안에 안전하게 못 끝낼 바엔 **범위를 줄여서라도 안정적으로** 만들었다.
    각 요소별 조작 훑기(discover+press)는 다시 켜기 전에 반드시: (1) go(N) 포함 모든 "패널을 바꾸는"
    조작을 원천 배제하거나 (2) sweep_url이 URL이 아니라 '현재 활성 패널'로 복귀 여부를 판정하도록
    고쳐야 한다 — 코디네이터 판단 필요, 이번 라운드 범위 밖.
    ★run_ui가 L1 중 제일 먼저 부르는 함수라 여기서 오래된 증거 폴더 정리를 겸한다(정리 실패해도
    점검은 계속 — cleanup_old_evidence 내부에서 이미 삼킨다)."""
    cleanup_old_evidence()

    def _run():
        page = session.page
        browser.goto_produce(page, session.base_url + "/produce?new=1")
        labels = page.evaluate("() => (typeof STEP_LABELS !== 'undefined' ? STEP_LABELS : null)")
        if not labels:
            raise RuntimeError("STEP_LABELS 못 찾음 — 화면 구조가 바뀌었을 수 있음")
        out = []
        for o in panels:
            label = labels[o]
            try:
                page.locator(f'#steps [title="{label}"]').first.click(timeout=3000)
                page.wait_for_timeout(400)
                cur = page.evaluate(
                    "() => { const c = document.querySelector('#steps .dk.cur'); return c ? c.title : null; }")
                ok = (cur == label)
                out.append(Result("L1", f"패널 열림 — {label}", GREEN if ok else RED,
                                  reason="정상" if ok else f"열린 패널이 다름(cur={cur!r})",
                                  signature=f"L1:panel_open:{label}", page="/produce"))
            except Exception as e:  # noqa: BLE001 — 이 패널만 회색, 다음 패널은 계속 시도
                out.append(Result("L1", f"패널 열림 — {label}", GRAY, reason=f"{type(e).__name__}: {str(e)[:120]}",
                                  signature=f"L1:panel_open:{label}", page="/produce"))
        return out

    results, ok = _run_guarded("제작소 전수", _run)
    if ok:
        results = _apply_throttle_gate(session, results)
    return results


def attach_evidence(session, results):
    """빨강인데 아직 evidence_dir이 없는 결과만 채운다(다른 곳에서 이미 찍었으면 건드리지 않는다).
    ★0순위-B: flows/base.py가 거의 같은 코드를 따로 갖고 있었다(2026-09-07 리뷰 지적) — 공용화해
    이 함수 하나로 통일한다."""
    for r in results:
        if r.verdict == RED and not r.evidence_dir:
            r.evidence_dir = capture_red_evidence(session, r.signature)
    return results


def sweep_lists(session):
    """목록 화면이 카드 1장 때문에 통째로 비지 않나(B-03): 카드 수>0 & 에러 0."""
    def _run():
        out = []
        for url, sel in (("/", ".card, .item, article"), ("/library", ".card, .item"), ("/produce", "#steps .dockbar")):
            session.errors.reset()
            before = session.errors.snapshot()
            blocked_before_n = len(session.blocked)
            browser.goto_ready(session.page, session.base_url + url, sel)
            n = session.page.locator(sel).count()
            # ★Task14 실측(2026-09-07): filter_blocked_noise가 _press()에만 배선돼 있고 여긴 안 타서
            # 안전 그물(route.abort)이 막은 요청의 콘솔 에러(net::ERR_FAILED)를 앱 버그로 오판했다
            # (예: coupang identify_batch 차단 → "/"가 빨강). _press와 같은 필터를 여기도 태운다.
            new_blocked = [_blocked_path(e) for e in session.blocked[blocked_before_n:]]
            snap = filter_blocked_noise(session.errors.snapshot(), before, new_blocked)
            bad = snap["pageerrors"] or snap["console_errors"]
            out.append(Result("L1", f"목록 화면이 비지 않나 — {url}", RED if (n == 0 or bad) else GREEN,
                              reason=f"카드 {n}개, 에러 {len(bad)}건", signature=f"L1:list:{url}", page=url))
        return out

    results, ok = _run_guarded("목록 카드 무예외", _run)
    if ok:
        results = _apply_throttle_gate(session, results)
        attach_evidence(session, results)
    return results


def sweep_sidebar(session):
    """사이드바 쿠팡 버튼(B-08): 열고 닫은 뒤 콘솔 에러 0.
    ★Task14 2차 실측(2026-09-07): 작업 없이 연 `/produce`의 aside/nav/#sidebar(=`.ss-nav`, 앱 전역
    좌측 메뉴)엔 '쿠팡' 텍스트가 전혀 없다 — 실제 쿠팡 UI('🛒 쿠팡에 있나?')는 랭킹·담기 카드
    (`/`·`/library`)에 있지, 제작소 사이드바엔 없다(app.py:4959,5138 실측). 즉 B-08이 원래 겨냥한
    버튼이 지금 화면 구조엔 없거나 다른 화면에 있다는 뜻 — 셀렉터를 고쳐서 억지로 초록을 만들지 않고
    "이유 있는 회색"으로 남긴다(코디네이터 지시: 억지 초록 금지)."""
    def _run():
        session.errors.reset()
        p = session.page
        browser.goto_produce(p, session.base_url + "/produce")
        btn = p.locator("aside, nav, #sidebar").get_by_text("쿠팡", exact=False).first
        if btn.count() == 0:
            return [Result("L1", "사이드바 쿠팡 버튼", GRAY,
                           reason="사이드바(aside/nav/#sidebar)에 '쿠팡' 텍스트 없음 — 이 화면(작업 없는 "
                                  "/produce)엔 쿠팡 버튼이 없어 보임(실제 쿠팡 UI는 랭킹·담기 카드에 있음, "
                                  "B-08 대상 화면 재확인 필요)",
                           signature="L1:sidebar:coupang")]
        btn.click(timeout=3000)
        p.wait_for_timeout(800)
        p.keyboard.press("Escape")
        snap = session.errors.snapshot()
        bad = snap["pageerrors"] + snap["console_errors"]
        return [Result("L1", "사이드바 쿠팡 버튼", RED if bad else GREEN, reason=(bad[:1] or [""])[0],
                       signature="L1:sidebar:coupang", page="/produce")]

    results, ok = _run_guarded("사이드바 쿠팡", _run)
    if ok:
        results = _apply_throttle_gate(session, results)
        attach_evidence(session, results)
    return results


def reporter_alive(session):
    """화면 에러 리포터(B-09): 일부러 에러를 내고 /api/client_error POST가 나가는지."""
    def _run():
        session.errors.reset()
        p = session.page
        browser.goto_produce(p, session.base_url + "/produce")
        p.evaluate("() => setTimeout(() => { throw new Error('CHECKS_REPORTER_PROBE') }, 10)")
        p.wait_for_timeout(1500)
        n = session.errors.client_error_posts
        return [Result("L1", "화면 에러가 서버로 보고되나", GREEN if n >= 1 else RED,
                       reason=f"client_error POST {n}건", signature="L1:reporter_alive", page="/produce")]

    results, ok = _run_guarded("리포터 생존", _run)
    if ok:
        attach_evidence(session, results)
    return results[0]
