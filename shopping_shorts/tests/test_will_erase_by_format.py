"""10-30 사장님 "모든 영상 — VMake 가 있으면 고급형으로 장면마다 골라서 지우고, 없으면 흐림 · 사용자가 바꿀 수 있게 · 이 채널(썰템쇼)은 흐림".
설치본 시험(썰템쇼 쇼핑형): 지우기 단계가 없는 형식인데 '지울 판'으로 보고 흐림을 안 넣어 남의 로고·자막이 남았다.
이제: 모든 형식이 렌더 전 f_render(지우기)를 탄다 · 방식 = 회원 설정(text.orig_text→SHORTEM_TEXT_MODE) > 판 칸 > 키 있으면 vmake·없으면 blur."""
from tools.calcopy import vmake_clean as V
from tools.calcopy.hybrid import flow as F


def _no_key(monkeypatch, tmp_path):
    monkeypatch.setenv("CALCOPY_VMAKE_VIA", "member")
    monkeypatch.delenv("VMAKE_API_KEY", raising=False)
    monkeypatch.delenv("SHORTEM_TEXT_MODE", raising=False)
    monkeypatch.delenv("CALCOPY_ERASE", raising=False)
    monkeypatch.setattr(V, "MEMBER_KEY_FILE", tmp_path / "none")


def test_every_format_has_erase_stage():
    for v in ("썰템쇼판", "썰템홈샷판", "키치잇판", "잇템로그판_v2"):
        assert F.erases_text(v) is True, v


def test_key_decides_and_channel_blur(monkeypatch, tmp_path):
    _no_key(monkeypatch, tmp_path)
    assert V.will_erase("키치잇판") is False                  # 키 없음 = 흐림
    monkeypatch.setenv("VMAKE_API_KEY", "ak:sk")
    assert V.will_erase("키치잇판") is True                   # 키 있음 = 장면마다 지우기
    assert V.will_erase("썰템쇼판") is False                  # 이 채널은 흐림(판 칸)


def test_member_setting_overrides(monkeypatch, tmp_path):
    _no_key(monkeypatch, tmp_path)
    monkeypatch.setenv("VMAKE_API_KEY", "ak:sk")
    monkeypatch.setenv("SHORTEM_TEXT_MODE", "blur")
    assert V.will_erase("키치잇판") is False
    monkeypatch.setenv("SHORTEM_TEXT_MODE", "vmake")
    assert V.will_erase("썰템쇼판") is True                   # 회원이 지우기를 고르면 판 칸보다 앞


def test_shop_flow_checks_text_mode_before_render():
    st = {"version": "썰템쇼판", "fmt": "쇼핑형", "phase": "render", "tries": {}, "log": [], "script": {"S": {"lines": []}, "M": {"cuts": {}}}}
    out = F.step(st, {}, {}, {})
    assert out["do"][0]["cmd"] == "clean_text" and out["do"][0]["check"] is True and st["phase"] == "f_text_check"
