# -*- coding: utf-8 -*-
"""CS #443(11-03) — VMake 확정 실패·회원 흐림은 재시도 없이 흐림으로 확정하고, 계획·렌더에 erase=False 를 싣는다."""
from tools.calcopy import vmake_clean as VC
from tools.calcopy.hybrid import flow as f


def _st():
    return {"version": "썰템쇼판", "fmt": "쇼핑형", "tries": {}, "log": [], "text_fix": {"mode": "vmake"},
            "script": {"S": {"lines": []}, "M": {"cuts": {}}}, "origin": {"files": []}}


def test_hard_fail_kinds():
    assert VC.hard_fail("RuntimeError: Switch to New API") == "new_api"
    assert VC.hard_fail("ConsumeDeniedError code 60001") == "not_pro"
    assert VC.hard_fail("err 10021 sign not equals") == "sign"
    assert VC.hard_fail("TimeoutError: 40분") == ""


def test_hard_fail_goes_blur_without_retry():
    st = _st()
    r = f.f_render_clean_got(st, {"clean": {"mode": "vmake", "why": "a.mp4: RuntimeError: Switch to New API", "done": {}}}, {}, {})
    assert r == {"goto": "render"} and st["text_fix"]["mode"] == "blur" and "vmake_fail" not in st["tries"]
    assert f.f_render(st, {}, {}, {})["do"][0]["cmd"] == "render"          # 다시 clean_text 를 부르지 않는다
    assert f._episode_erases(st) is False


def test_member_blur_confirmed_without_notice():
    st = _st()
    r = f.f_render_clean_got(st, {"clean": {"mode": "blur", "why": "판 orig_text.mode=blur", "done": {}}}, {}, {})
    assert r == {"goto": "render"} and st["text_fix"]["mode"] == "blur" and not st.get("notice")


def test_timeout_still_retries():
    st = _st()
    r = f.f_render_clean_got(st, {"clean": {"mode": "vmake", "why": "a.mp4: TimeoutError", "done": {}}}, {}, {})
    assert r == {"goto": "render"} and st["tries"]["vmake_fail"] == 1 and st["text_fix"]["mode"] == "vmake"
