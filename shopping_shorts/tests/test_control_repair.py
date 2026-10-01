# -*- coding: utf-8 -*-
"""관제 수리 3건(2026-10-02 사장님 "관제 테스트 문제 많아 변경하자", 카드 069).

실측 배경(10-01 하루): 완료 1/68 · 병합 정체 28(영상 없는 카드는 live_check "대상 없음") ·
finish 4회 중 2회가 변경과 무관한 실패(낡은 기준선 / app.py 모듈 수준 한 줄 → 영상 관문 → 라이브 잔상)."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import live_check  # noqa: E402
import video_gate  # noqa: E402
import control  # noqa: E402


# ───────── ① 검사 종류 ─────────
def _card(no, **kw):
    c = {"번호": no, "제목": "t%d" % no, "상태": "병합", "병합": "abc1234567 2026-10-01 12:00 (t)",
         "판단 주인": "", "검사": "", "이력": [], "분배": ""}
    c.update(kw)
    return c


def test_검사_종류_추론_영상_주인이면_영상_아니면_수동():
    assert live_check.check_kind(_card(1, **{"판단 주인": "shopping_shorts/video_assemble.py:_plan"}))[0] == "영상"
    assert live_check.check_kind(_card(2, **{"판단 주인": "shopping_shorts/app.py:api_lens_trace_url"}))[0] == "수동"
    assert live_check.check_kind(_card(3, **{"검사": "url /pay/toss 880,000원"}))[0] == "url"
    assert live_check.check_kind(_card(4, **{"검사": "api /api/pricing amount=880000,cohort=2기"}))[0] == "api"


def test_url_api_검사는_HTTP로_재서_통과_실패를_가른다():
    pages = {"/pay/toss": "<h1>…</h1><div class=amt>880,000원</div>",
             "/api/pricing": json.dumps({"amount": 880000, "cohort": "2기"})}
    fetch = lambda path: (200, pages[path])
    ok, why = live_check.http_check("url /pay/toss 880,000원", fetch=fetch)
    assert ok and "880,000원" in why
    ok, why = live_check.http_check("url /pay/toss 770,000원", fetch=fetch)
    assert not ok
    ok, why = live_check.http_check("api /api/pricing amount=880000,cohort=2기", fetch=fetch)
    assert ok
    ok, why = live_check.http_check("api /api/pricing amount=770000", fetch=fetch)
    assert not ok and "770000" in why


def test_run_all은_영상_카드만_서버_영상비교로_보내고_url_카드는_HTTP로_닫는다(monkeypatch):
    cards = [_card(10, **{"판단 주인": "shopping_shorts/mix_pipeline.py:x"}),
             _card(11, **{"검사": "api /api/pricing amount=880000"}),
             _card(12, **{"판단 주인": "shopping_shorts/app.py:_with_pay"})]
    calls = {"video": 0, "status": [], "field": [], "note": []}

    def sh(cmd, timeout=0):
        if "daily_video_audit" in cmd:
            calls["video"] += 1
            return 0, "== 칸 10 · 다른 장면 0\nEVF_OK"
        if "merge-base --is-ancestor" in cmd:
            return 0, "DEPLOYED 2026-10-01 13:10:20"
        return 0, ""
    monkeypatch.setattr(live_check, "_fetch_live", lambda path: (200, json.dumps({"amount": 880000})))
    monkeypatch.setattr(control, "set_status", lambda repo, n, s, printer=None: calls["status"].append((n, s)))
    monkeypatch.setattr(control, "set_field", lambda repo, n, k, v, printer=None: calls["field"].append((n, k)))
    monkeypatch.setattr(control, "note", lambda repo, n, t, printer=None: calls["note"].append((n, t)))
    monkeypatch.setattr(live_check, "verdict", lambda rc, out: ("라이브실측", "깨끗"))
    out = []
    live_check.run_all("repo", cards, sh=sh, printer=out.append, now=1_800_000_000, write=True)
    assert calls["video"] == 1, "영상 카드 1장 → 서버 영상 비교 1번"
    assert (11, "완료") in calls["status"], "url/api 카드는 HTTP 검사 통과 → 완료"
    assert (10, "라이브실측") in calls["status"]
    assert not any(n == 12 for n, _ in calls["status"]), "수동 카드는 상태를 안 바꾼다"
    assert any("수동 확인 대기" in o for o in out) and any(o.strip().startswith("012") for o in out), "수동 카드는 목록으로 보여준다"


def test_url_카드는_서버에_병합_sha가_없으면_기다린다(monkeypatch):
    cards = [_card(11, **{"검사": "api /api/pricing amount=880000"})]
    sh = lambda cmd, timeout=0: (1, "NOT_YET") if "merge-base" in cmd else (0, "")
    st = []
    monkeypatch.setattr(control, "set_status", lambda repo, n, s, printer=None: st.append(s))
    monkeypatch.setattr(control, "note", lambda repo, n, t, printer=None: None)
    monkeypatch.setattr(control, "set_field", lambda repo, n, k, v, printer=None: None)
    out = []
    live_check.run_all("repo", cards, sh=sh, printer=out.append, now=1_800_000_000, write=True)
    assert not st and any("서버 미반영" in o for o in out)


def test_control_카드에_검사_칸이_있다():
    assert "검사" in control.CARD_KEYS
    c = control.parse_card("# 001 · 제목\n\n- 상태: 병합\n- 검사: url /x 123\n\n## 요청\n\n본문\n\n## 이력\n")
    assert c["검사"] == "url /x 123"
    assert "- 검사: url /x 123" in control.render_card(c)


# ───────── ② 영상 관문 모듈 수준 심볼 판정 ─────────
CFG = {"app_name_keys": ["pvproxy", "render", "clean", "capcut", "assemble", "export", "snap_segs"],
       "app_route_keys": ["/api/mix/render"]}
OLD = '''import os
_AUTH_ALLOW = ("/login",
               "/pay")
_PRICING_TMPL = """<h1>요금</h1>
<p>1기</p>"""
RENDER_FPS = 24
def _with_pay(h):
    return h
@app.get("/api/mix/render")
def api_render():
    return 1
'''


def _diff(old, new):
    import difflib
    return "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), "a", "b", n=0))


def test_모듈_수준_상수_템플릿_변경은_제작_라인_밖():
    new = OLD.replace('"/pay")', '"/pay", "/api/pricing")').replace("<p>1기</p>", "<p>2기</p>")
    run, why = video_gate.app_touches_video(OLD, new, _diff(OLD, new), CFG)
    assert run is False, why
    assert "_AUTH_ALLOW" in why and "_PRICING_TMPL" in why


def test_모듈_수준이라도_이름이_제작_라인이면_실행():
    new = OLD.replace("RENDER_FPS = 24", "RENDER_FPS = 30")
    run, why = video_gate.app_touches_video(OLD, new, _diff(OLD, new), CFG)
    assert run is True and "RENDER_FPS" in why


def test_import_변경은_여전히_실행():
    new = OLD.replace("import os", "import os, sys")
    run, why = video_gate.app_touches_video(OLD, new, _diff(OLD, new), CFG)
    assert run is True


# ───────── ③ 새 실패를 origin/main 에서 재실행 ─────────
def test_새로_깨진_테스트가_main에서도_깨지면_기존_실패로_뺀다():
    import track
    before = {"failed": []}
    after = {"failed": ["t/a.py::test_x", "t/b.py::test_y"]}
    problems = ["새로 깨진 테스트 2건:\n    - t/a.py::test_x\n    - t/b.py::test_y"]
    rerun = lambda ids: {"t/a.py::test_x"}            # main 에서도 깨지는 것
    out = []
    left = track._classify_new_failures(before, after, problems, rerun=rerun, printer=out.append)
    assert left and "test_y" in left[0] and "test_x" not in left[0]
    assert any("기존 실패" in o and "test_x" in o for o in out)
    rerun2 = lambda ids: set(ids)
    assert track._classify_new_failures(before, after, list(problems), rerun=rerun2, printer=out.append) == []
