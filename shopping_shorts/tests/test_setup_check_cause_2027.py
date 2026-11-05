"""#2027 이용재 · #502 정민혜 — 편 멈춤 직후 새 편 준비 확인(env)이 프리셋 빌림 busy 로 실패했는데 ph_setup_check 가
'이 PC 준비가 아직 덜 됐어요'로 덮어 원인이 안 보였다. busy 는 잠깐의 문제(스스로 한 번 다시), 그 밖은 원문을 detail 로 싣는다."""
from tools.calcopy.hybrid import flow as F


def _st():
    return {"version": "썰템쇼판", "fmt": "쇼핑형", "phase": "setup_check", "tries": {}, "log": [], "ref": "https://youtu.be/x"}


def test_busy_rent_is_transient_not_setup():
    st = _st()
    out = F.step(st, {"env": {"error": "프리셋을 받지 못했다: busy"}}, {}, {})
    assert "준비가 아직 덜" not in str(out), out
    assert any("busy" in x for x in st["log"])


def test_other_env_error_carries_cause():
    st = _st()
    out = F.step(st, {"env": {"error": "실행기를 띄우지 못했다: ENOENT python"}}, {}, {})
    assert out["status"] == "stop" and "ENOENT" in str(st.get("stopped", {}).get("detail")), (out, st.get("stopped"))
