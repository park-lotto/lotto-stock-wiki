"""브라우저에 남은 옛 설정이 새 기본값을 이기나(B-14, reference_revert가_남긴_localStorage).
옛 키를 심고 로드 → 페이지가 에러 없이 뜨고 STEP_LABELS가 10개(기본 UI)면 초록.

★"옛 값이 브라우저에 남아 있는 것" 자체는 정상 상태다 — 문제는 그 값이 새 화면을 깨거나
기본 동작을 이기는 것뿐이다. 그래서 판정은 "localStorage에 값이 있나"가 아니라
"그 값을 심은 채로 새로고침해도 화면이 정상 개수(STEP_LABELS 10개)로 뜨고 콘솔·페이지 에러가
없나"로 한다."""
from shopping_shorts.checks.verdict import GREEN, RED, Result

META = {"name": "브라우저에 남은 옛 설정이 화면을 깨나", "needs_worker": False, "timeout_s": 60}
OLD_KEYS = {"촘촘히": "0", "sceneLab:tight": "1", "ssTheme": "dark"}


def run(session):
    p = session.page
    session.errors.reset()
    p.goto(session.base_url + "/produce", wait_until="networkidle")
    p.evaluate("(kv) => { for (const [k, v] of Object.entries(kv)) localStorage.setItem(k, v); }", OLD_KEYS)
    p.reload(wait_until="networkidle")
    n = p.evaluate("() => (window.STEP_LABELS || []).length")
    snap = session.errors.snapshot()
    bad = snap["pageerrors"] + snap["console_errors"]
    p.evaluate("(ks) => ks.forEach(k => localStorage.removeItem(k))", list(OLD_KEYS))
    ok = n == 10 and not bad
    return [Result("L2", META["name"], GREEN if ok else RED,
                   reason=f"STEP_LABELS {n}개, 에러 {bad[:1]}", signature="L2:localstorage_old", page="/produce")]
