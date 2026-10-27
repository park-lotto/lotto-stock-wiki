"""반복 감시 — 같은 실행기 일이 WATCH_N 번을 넘으면 실행 대신 회원 Claude(감독)에게 묻는다(사장님 10-27 "오푸스가 계속 깨어 있어야 한다").
옛 코드: clean_text↔write_doc 를 아무도 모르게 67번(37분) 돌았다(10-27 립글로스)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import flow as F  # noqa: E402


def _loop_phase(st, m, rp, u):
    st["log"].append("clean_text: VMake 0회 · 박힌 글자 없음")
    return {"do": [{"id": "c", "cmd": "clean_text"}], "then": "loopx"}


def _run(monkeypatch, go):
    monkeypatch.setitem(F.PHASES, "loopx", _loop_phase)
    monkeypatch.setattr(F, "_task", lambda *a, **k: None)
    st = {"sid": "s", "phase": "loopx", "fmt": "해외원본형", "tries": {}, "log": [], "version": "잇템로그판_v2"}
    outs = []
    for _ in range(F.WATCH_N + 2):
        r = F.step(st, measure={"c": {}})
        outs.append(r)
        if r["status"] == "review":
            break
    assert [o["status"] for o in outs] == ["execute", "review"]                 # 같은 입력 두 번째에 바로
    assert outs[-1]["review"][0]["id"] == "watch" and "박힌 글자 없음" in outs[-1]["review"][0]["ask"]
    return st, F.step(st, replies={"watch": {"go": go, "why": "같은 결과 반복"}})


def test_watch_stop(monkeypatch):
    st, r = _run(monkeypatch, False)
    assert r["status"] == "stop" and "감독" in " ".join(st["log"])


def test_watch_continue_then_asks_again_later(monkeypatch):
    st, r = _run(monkeypatch, True)
    assert r["status"] == "execute" and r["do"][0]["cmd"] == "clean_text"
    for _ in range(F.WATCH_N - 1):
        assert F.step(st, measure={"c": {}})["status"] == "execute"         # 감독이 정상이라 한 같은 입력은 다시 안 묻는다
    assert F.step(st, measure={"c": {}})["status"] == "review"           # 그래도 WATCH_N 번 더 돌면 다시 묻는다


def test_review_between_resets_count(monkeypatch):
    """바퀴마다 회원 Claude 에게 묻는 고리(원본 회원 찾기 등)는 깨어 있는 것 — 감시하지 않는다."""
    flip = {"n": 0}

    def ph(st, m, rp, u):
        flip["n"] += 1
        if flip["n"] % 2:
            return {"review": [F._rv("x", "q")], "then": "loopy"}
        return {"do": [{"id": "c", "cmd": "origin_foreign"}], "then": "loopy"}
    monkeypatch.setitem(F.PHASES, "loopy", ph)
    st = {"sid": "s", "phase": "loopy", "fmt": "해외원본형", "tries": {}, "log": [], "version": "잇템로그판_v2"}
    seen = [F.step(st, measure={"c": {}}, replies={"x": {}})["status"] for _ in range(F.WATCH_N * 4)]
    assert "review" in seen and all(x in ("review", "execute") for x in seen)
    assert not any(r for r in [st.get("watch_do")])


def test_same_input_second_time_asks_at_once(monkeypatch):
    """같은 do(입력)를 질문 없이 두 번째 내려 하면 바로 감독에게 묻는다(횟수 6번을 기다리지 않는다 — 10-27 재생 비교)."""
    monkeypatch.setitem(F.PHASES, "loopx", _loop_phase)
    st = {"sid": "s", "phase": "loopx", "fmt": "해외원본형", "tries": {}, "log": [], "version": "잇템로그판_v2"}
    assert F.step(st, measure={"c": {}})["status"] == "execute"
    r = F.step(st, measure={"c": {}})
    assert r["status"] == "review" and r["review"][0]["id"] == "watch"
    r = F.step(st, replies={"watch": {"go": True, "why": "정상"}})
    assert r["status"] == "execute"
    assert F.step(st, measure={"c": {}})["status"] == "execute"            # 감독이 정상이라 한 같은 입력은 다시 안 묻는다
