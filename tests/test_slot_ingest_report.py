import sys
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import slot_ingest as si


def test_disp_width_ascii():
    assert si._disp_width("abc") == 3


def test_disp_width_korean():
    assert si._disp_width("텔레그램") == 8


def test_pad_korean_label():
    assert si._pad("텔레그램", 10) == "텔레그램  "


def test_pad_ascii_label():
    assert si._pad("youtube", 10) == "youtube   "


def test_pad_already_over_width_no_truncate():
    assert si._pad("아주긴카테고리라벨", 4) == "아주긴카테고리라벨"


def test_extract_pending_korean_label():
    text = "[15/19] ...\n완료: 19개 채널, 124개 원자\n미처리 텔레그램: 6개\n"
    assert si._extract_pending(text) == 6


def test_extract_pending_english_label():
    text = "완료: 0개, 0개 원자\n미처리 youtube: 0개\n"
    assert si._extract_pending(text) == 0


def test_extract_pending_missing_pattern():
    assert si._extract_pending("아무 정보 없는 로그") == 0


def test_extract_error_quota():
    text = "google.api_core.exceptions.ResourceExhausted: 429 RESOURCE_EXHAUSTED"
    err = si._extract_error(text)
    assert err is not None
    assert "RESOURCE_EXHAUSTED" in err


def test_extract_error_traceback():
    text = "Traceback (most recent call last):\n  File x.py\nKeyError: 'x'"
    assert si._extract_error(text) is not None


def test_extract_error_none_on_clean_log():
    text = "[15/19] 2026-07-01_미래시황.md\n  → 13개 원자\n완료: 19개 채널, 124개 원자"
    assert si._extract_error(text) is None


def test_atoms_count_today_smoke():
    n = si._atoms_count_today("report", "2026-07-02")
    assert isinstance(n, int)
    assert n >= 0


def test_atoms_count_since_smoke():
    n = si._atoms_count_since("report", "2026-07-02T00:00:00")
    assert isinstance(n, int)
    assert n >= 0


def test_trailing_avg_smoke():
    avg = si._trailing_avg("report", "2026-07-02")
    assert isinstance(avg, float)
    assert avg >= 0.0


def test_trailing_avg_unknown_source_type_is_zero():
    avg = si._trailing_avg("존재하지않는소스타입", "2026-07-02")
    assert avg == 0.0


def test_diagnose_normal_no_pending(monkeypatch):
    monkeypatch.setattr(si, "_atoms_count_since", lambda st, s: 0)
    monkeypatch.setattr(si, "_atoms_count_today", lambda st, d: 9)
    monkeypatch.setattr(si, "_trailing_avg", lambda st, d, days=7: 5.0)

    def boom(*a, **k):
        raise AssertionError("원본 없으면 재시도하면 안 됨")
    monkeypatch.setattr(si, "ingest_cat", boom)

    output = "미처리 youtube: 0개\n완료: 0개, 0개 원자"
    r = si.diagnose("youtube", "2026-07-02", "2026-07-01", "2026-07-02T00:00:00", output)
    assert r == {"cat": "youtube", "delta": 0, "total_today": 9,
                 "icon": "✅", "note": "정상", "retried": False}


def test_diagnose_pending_but_zero_atoms_retries_and_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_since(st, s):
        calls["n"] += 1
        return 0 if calls["n"] == 1 else 5

    monkeypatch.setattr(si, "_atoms_count_since", fake_since)
    monkeypatch.setattr(si, "_atoms_count_today", lambda st, d: 46)
    monkeypatch.setattr(si, "_trailing_avg", lambda st, d, days=7: 10.0)
    monkeypatch.setattr(si, "ingest_cat",
                         lambda cat, date, extra_date=None: "재시도 완료, 에러없음")

    output = "미처리 리포트: 3개\n완료: 0개, 0개 원자"
    r = si.diagnose("report", "2026-07-02", "2026-07-01", "2026-07-02T00:00:00", output)
    assert r["icon"] == "✅"
    assert r["note"] == "재시도로 해결"
    assert r["delta"] == 5
    assert r["retried"] is True


def test_diagnose_retry_still_fails_flags_confirm_needed(monkeypatch):
    monkeypatch.setattr(si, "_atoms_count_since", lambda st, s: 0)
    monkeypatch.setattr(si, "_atoms_count_today", lambda st, d: 46)
    monkeypatch.setattr(si, "_trailing_avg", lambda st, d, days=7: 10.0)
    monkeypatch.setattr(si, "ingest_cat",
                         lambda cat, date, extra_date=None: "RESOURCE_EXHAUSTED 429 quota")

    output = "미처리 리포트: 3개\n완료: 0개, 0개 원자"
    r = si.diagnose("report", "2026-07-02", "2026-07-01", "2026-07-02T00:00:00", output)
    assert r["icon"] == "🔴"
    assert "확인필요" in r["note"]
    assert "RESOURCE_EXHAUSTED" in r["note"]
    assert r["retried"] is True


def test_diagnose_error_signature_triggers_retry_even_without_pending(monkeypatch):
    monkeypatch.setattr(si, "_atoms_count_since", lambda st, s: 0)
    monkeypatch.setattr(si, "_atoms_count_today", lambda st, d: 20)
    monkeypatch.setattr(si, "_trailing_avg", lambda st, d, days=7: 10.0)
    monkeypatch.setattr(si, "ingest_cat",
                         lambda cat, date, extra_date=None: "여전히 Traceback 있음")

    output = "미처리 텔레그램: 0개\nTraceback (most recent call last):\nKeyError"
    r = si.diagnose("telegram", "2026-07-02", "2026-07-01", "2026-07-02T00:00:00", output)
    assert r["icon"] == "🔴"
    assert r["retried"] is True


def test_diagnose_sharp_drop_warning_no_retry(monkeypatch):
    monkeypatch.setattr(si, "_atoms_count_since", lambda st, s: 3)
    monkeypatch.setattr(si, "_atoms_count_today", lambda st, d: 3)
    monkeypatch.setattr(si, "_trailing_avg", lambda st, d, days=7: 40.0)

    def boom(*a, **k):
        raise AssertionError("급감은 재시도하면 안 됨")
    monkeypatch.setattr(si, "ingest_cat", boom)

    output = "미처리 텔레그램: 0개\n완료: 6개 채널, 3개 원자"
    r = si.diagnose("telegram", "2026-07-02", "2026-07-01", "2026-07-02T00:00:00", output)
    assert r["icon"] == "⚠️"
    assert "급감" in r["note"]
    assert r["retried"] is False


def test_build_report_all_normal_no_issue_section():
    results = [
        {"cat": "telegram", "delta": 12, "total_today": 45, "icon": "✅", "note": "정상", "retried": False},
        {"cat": "youtube", "delta": 0, "total_today": 9, "icon": "✅", "note": "정상", "retried": False},
    ]
    text = si.build_report(["telegram", "youtube"], "2026-07-02", results)
    assert "45(+12)" in text
    assert "9(+0)" in text
    assert "확인 필요" not in text
    assert "<pre>" in text and "</pre>" in text


def test_build_report_with_critical_issue():
    results = [
        {"cat": "report", "delta": 0, "total_today": 46, "icon": "🔴",
         "note": "확인필요 — RESOURCE_EXHAUSTED 429", "retried": True},
    ]
    text = si.build_report(["report"], "2026-07-02", results)
    assert "🔴 확인 필요" in text
    assert "RESOURCE_EXHAUSTED" in text
    assert "46(+0)" in text


def test_build_report_with_warning_only_no_critical_header():
    results = [
        {"cat": "telegram", "delta": 3, "total_today": 3, "icon": "⚠️",
         "note": "급감(평균 40 대비 3)", "retried": False},
    ]
    text = si.build_report(["telegram"], "2026-07-02", results)
    assert "⚠️ 참고" in text
    assert "🔴 확인 필요" not in text


def test_pipeline_importable_when_run_as_script():
    """Task Scheduler와 동일한 방식(python scripts/slot_ingest.py)으로 실행했을 때
    diagnose()가 의존하는 pipeline 패키지가 import 가능해야 한다.
    cwd는 반드시 scripts/ 여야 한다 — cwd=ROOT로 두면 `python -c`가 빈 문자열
    sys.path[0](=cwd)로 ROOT를 암묵적으로 sys.path에 넣어버려서, slot_ingest.py의
    실제 수정(sys.path.insert) 없이도 이 테스트가 통과해버리는(가짜 GREEN) 문제가
    있었다 — 재발 방지를 위해 cwd를 scripts/로 고정한다."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        out_file = f.name
    try:
        code = (
            f"import sys; sys.path.insert(0, r'{str(ROOT / 'scripts')}'); "
            f"import slot_ingest; from pipeline.atoms.db import get_conn; "
            f"open(r'{out_file}', 'w').write('OK')"
        )
        # capture_output=True는 pytest의 stdout 캡처와 충돌해 Windows에서
        # OSError([WinError 6])를 낼 수 있어(핸들 상속 문제) 쓰지 않는다 —
        # 결과는 out_file 사이드채널로만 받는다.
        subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(ROOT / "scripts"), stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        result = Path(out_file).read_text().strip() if Path(out_file).exists() else ""
        assert result == "OK", f"Expected 'OK', got {result!r}"
    finally:
        Path(out_file).unlink(missing_ok=True)
