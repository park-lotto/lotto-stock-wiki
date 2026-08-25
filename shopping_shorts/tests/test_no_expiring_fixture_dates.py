# -*- coding: utf-8 -*-
"""테스트가 '며칠 뒤에 저절로 깨지는' 고정 날짜를 쓰지 못하게 막는다.

## 실사고 (2026-08-26)

`test_aipick_fresh_comments.py`가 수집 시각으로 `"2026-07-26T00:00:00"`을 박아뒀다.
그런데 `reel_history`는 **저장하는 그 순간** last_seen이 30일 지난 행을 지운다
(`store._record_history` 끝의 정리). 그래서 **딱 30일 뒤인 08-26부터** 저장 즉시
삭제돼 2건이 조용히 깨졌다 — 아무도 코드를 안 건드렸는데 어제까진 통과했다.

같은 계열 사고가 이 저장소에서 반복된다(메모리 `reference_테스트_시한폭탄_침묵except`).
그래서 규칙을 코드로 박는다: **보존창(30일)을 타는 표에 넣는 시각은 '지금' 기준으로 만들어라.**

## 무엇을 막고 무엇을 허용하나

- 막는다: `save_last_run(..., "2026-07-26T00:00:00")` 처럼 **날짜 리터럴**을 넘기는 것.
  이 값은 `reel_history.last_seen`이 되어 30일 정리에 걸린다.
- 허용한다: `_now()` / `datetime.now(...)` / `"t1"` 같은 **날짜가 아닌 라벨**.
  라벨은 `settings`(단일 행)에만 들어가고 보존창과 무관하다 —
  실제로 test_store·test_reference_adopt·test_last_run_cap이 그렇게 쓴다.
"""
import pathlib
import re

TESTS = pathlib.Path(__file__).resolve().parent
# ISO 날짜처럼 보이는 문자열 리터럴 (YYYY-MM-DD…)
_DATE_LIT = re.compile(r'"(\d{4})-(\d{2})-(\d{2})[^"]*"')


def _save_last_run_calls(text):
    """save_last_run( ... ) 호출의 인자 부분만 뽑는다(여러 줄 호출 포함)."""
    out = []
    for m in re.finditer(r"save_last_run\(", text):
        i = m.end()
        depth, j = 1, i
        while j < len(text) and depth:
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
            j += 1
        out.append(text[i:j])
    return out


def test_보존창을_타는_시각에_날짜리터럴을_쓰지_않는다():
    """★이 테스트가 실패하면: 그 날짜가 30일을 넘기는 날 조용히 깨진다.
    `datetime.now(timezone.utc).isoformat()`(또는 그걸 감싼 헬퍼)로 바꿔라."""
    bad = []
    for p in sorted(TESTS.glob("test_*.py")):
        if p.name == pathlib.Path(__file__).name:
            continue
        text = p.read_text(encoding="utf-8")
        for call in _save_last_run_calls(text):
            for m in _DATE_LIT.finditer(call):
                # reel_history를 실제로 조회하는 테스트만 위험하다.
                # (settings만 보는 load_last_run 계열은 보존창과 무관 — 위 독스트링)
                if "latest_comments" in text or "_load_work_sources" in text:
                    bad.append(f"{p.name}: {m.group(0)}")
    assert not bad, (
        "30일 보존창을 타는 자리에 고정 날짜가 있다 — 그 날짜가 30일을 넘기는 날 "
        "저절로 깨진다(2026-08-26 실사고):\n  " + "\n  ".join(bad)
        + "\n\n  고치는 법: datetime.now(timezone.utc).isoformat() 을 써라."
    )


def test_보존창_정리가_실제로_30일인지_확인한다():
    """위 검사가 전제하는 '30일'이 코드와 맞는지 — 코드가 바뀌면 여기서 알려준다."""
    store = (TESTS.parent / "store.py").read_text(encoding="utf-8")
    m = re.search(r"timedelta\(days=(\d+)\)\s*\)\.isoformat\(\)\s*\n\s*c\.execute\(\s*\n?\s*"
                  r'"DELETE FROM reel_history', store)
    assert m, "reel_history 30일 정리 코드를 못 찾았다 — 이 테스트의 전제를 다시 확인하라"
    assert m.group(1) == "30", f"보존창이 {m.group(1)}일로 바뀌었다 — 위 독스트링을 갱신하라"
