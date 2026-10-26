# -*- coding: utf-8 -*-
"""관제263 10-26 잇템로그 회원 실측 run4(98 #165) — 원본은 찾았는데 4/13 에서 '정해 주신 제품 이름을 알 수 없어요 — 이 영상은 여기서 마칠게요'(다시 시도 불가).
뿌리: 실행기 쿠팡 검색이 ImportError(설치 묶음에 개발 전용 모듈 없음) → flow 가 오류를 '후보 없음'으로 읽음 → 제작자 과제가 쿠팡 주소를 줌
→ ph_given 이 주소만 든 글을 '이름 모름' final 로 끝냄.
고친 것: ①_coupang_down = 실행기 오류도 '쿠팡 검색이 잠시 막혀 있어요'(스스로 다시·다시 시도 가능) ②ph_given = 주소만이면 상품번호 + 판독 검색어로
③coupang_customer = 개발 스위치가 켜져 있어도 모듈이 없으면 회원 길로(경보)."""
from __future__ import annotations

import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import flow as F  # noqa: E402


def _flow(src: str | None = None):
    if src is None:
        return F
    mod = types.ModuleType("flow_x")
    mod.__file__ = str(ROOT / "tools/calcopy/hybrid/flow.py")
    exec(compile(src, "flow_x.py", "exec"), mod.__dict__)
    return mod


def _check(mod):
    with pytest.raises(mod._Stop) as e:
        mod._coupang_down({"coupang": {"error": "ImportError: cannot import name 'coupang_api_search' from 'tools.calcopy'"}})
    assert e.value.auto and not e.value.final and "쿠팡 검색" in e.value.why
    st = mod.start("https://youtu.be/BENCH1", "잇템로그판_v2", "sid")
    st.update({"given": "https://www.coupang.com/vp/products/9392386079", "coupang_qs": ["보라색 치아 미백 스트립"], "read": {"product_words": ["teeth strips"]}})
    r = mod.ph_given(st, {}, {}, {})
    assert r["do"][0]["queries"] == ["보라색 치아 미백 스트립"]


def test_runner_error_is_search_down_and_url_only_product_searches():
    _check(F)


def test_old_flow_failed():
    """사보타주 기준 — 고치기 전 flow 는 실행기 오류를 그냥 지나가고(멈춤 없음) 주소만 든 제품을 final 로 끝냈다."""
    r = subprocess.run(["git", "-C", str(ROOT), "show", "HEAD:tools/calcopy/hybrid/flow.py"], capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0 or 'c.get("search_failed") or c.get("error")' in r.stdout:
        pytest.skip("HEAD 가 이미 새 길")
    with pytest.raises((AssertionError, pytest.fail.Exception)):      # 옛 길: 멈춤이 안 나거나(DID NOT RAISE) 주소만 든 제품이 final
        _check(_flow(r.stdout))


def test_dev_switch_without_module_falls_back(monkeypatch):
    from tools.calcopy import coupang_customer as C
    monkeypatch.setenv("CALCOPY_DEV_COUPANG_SERVER", "1")
    monkeypatch.delenv("COUPANG_ACCESS_KEY", raising=False)
    monkeypatch.delenv("COUPANG_SECRET_KEY", raising=False)
    monkeypatch.setitem(sys.modules, "tools.calcopy.coupang_api_search", None)     # 설치 묶음처럼 모듈 없음
    out = C.search(["치아 미백"])
    assert out["치아 미백"]["need"] == "chrome"                                       # 회원 길(크롬)로 — ImportError 로 죽지 않는다
