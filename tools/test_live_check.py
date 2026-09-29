# -*- coding: utf-8 -*-
"""라이브 실측(live_check.py) — 순수 판단 + 카드 기록(서버는 가짜 sh 로)."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import control
import live_check as lc
from test_control import _install  # noqa: F401
from test_track import repo  # noqa: F401 (fixture)


def test_parse_merge_and_hours():
    sha, t = lc.parse_merge("5bd6c66612 2026-09-29 13:00 (관제)")
    assert sha == "5bd6c66612"
    assert lc.hours_since(t, now=t + 30 * 60) == 1, "최소 1시간"
    assert lc.hours_since(t, now=t + 5.5 * 3600) == 6, "올림"
    assert lc.hours_since(t, now=t + 100 * 3600) == 72, "상한 72"
    assert lc.parse_merge("") is None and lc.parse_merge("없음") is None


def test_summary_and_verdict():
    out = "대상: 최근 3시간 미리보기 준비 작업 2개\n블라\n== 칸 20 · 다른 장면 0 · 0.15초 이상 밀림(가운데) 1 · 경계 밀림 0 · 정지컷만 밀림 0\n✅ 깨끗\n"
    assert lc.summary_lines(out) == ["대상: 최근 3시간 미리보기 준비 작업 2개", "== 칸 20 · 다른 장면 0 · 0.15초 이상 밀림(가운데) 1 · 경계 밀림 0 · 정지컷만 밀림 0", "✅ 깨끗"]
    assert lc.verdict(0, out) == ("라이브실측", "통과")
    assert lc.verdict(1, out)[0] == "회귀"
    assert lc.verdict(3, out)[0] is None and "대상 없음" in lc.verdict(3, out)[1]
    assert lc.verdict(2, out)[0] is None


def test_cards_due_only_merged_and_settled():
    now = time.time()
    fresh = time.strftime("%Y-%m-%d %H:%M", time.localtime(now - 60))
    old = time.strftime("%Y-%m-%d %H:%M", time.localtime(now - 3600))
    cards = [{"번호": 1, "상태": "병합", "병합": "abc1234 %s (t)" % old},
             {"번호": 2, "상태": "병합", "병합": "abc1234 %s (t)" % fresh},
             {"번호": 3, "상태": "완료", "병합": "abc1234 %s (t)" % old},
             {"번호": 4, "상태": "등록", "병합": ""}]
    assert [c["번호"] for c in lc.cards_due(cards, now=now)] == [1]


def test_remote_command_uses_same_audit_tool_dry_run():
    cmd = lc.remote_command(23, 5, 4)
    assert "daily_video_audit.py --dry-run --hours 5 --jobs 4" in cmd and "/tmp/live_check/023" in cmd


def test_run_card_writes_result_and_state(repo):
    _install(repo)
    n = control.new_card(repo, "실측 대상", printer=lambda *a: None)
    control.set_field(repo, n, "병합", "deadbeef00 %s (t)" % time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() - 7200)), printer=lambda *a: None)
    control.set_status(repo, n, "병합", printer=lambda *a: None)
    c = control.find_card(control.cards_from_ref(repo), n)
    fake = lambda cmd, timeout=0: (0, "대상: 최근 3시간 미리보기 준비 작업 2개\n== 칸 20 · 다른 장면 0 · 밀림 0\n✅ 깨끗\n")  # noqa: E731
    assert lc.run_card(repo, c, sh=fake, printer=lambda *a: None) == 0
    c2 = control.find_card(control.cards_from_ref(repo), n)
    assert c2["상태"] == "라이브실측" and "통과" in c2["라이브 실측"] and "다른 장면 0" in c2["라이브 실측"]

    bad = lambda cmd, timeout=0: (1, "== 칸 20 · 다른 장면 3\n❌ 어긋남\n")  # noqa: E731
    assert lc.run_card(repo, c2, sh=bad, printer=lambda *a: None) == 1
    assert control.find_card(control.cards_from_ref(repo), n)["상태"] == "회귀"

    none = lambda cmd, timeout=0: (3, "대상 없음\n")  # noqa: E731
    lc.run_card(repo, control.find_card(control.cards_from_ref(repo), n), sh=none, printer=lambda *a: None)
    c3 = control.find_card(control.cards_from_ref(repo), n)
    assert c3["상태"] == "회귀", "대상 없음은 상태를 바꾸지 않는다"
    assert any("대상 없음" in h for h in c3["이력"])


def test_run_card_refuses_unmerged_card(repo):
    _install(repo)
    n = control.new_card(repo, "미병합", printer=lambda *a: None)
    c = control.find_card(control.cards_from_ref(repo), n)
    calls = []
    assert lc.run_card(repo, c, sh=lambda *a, **k: calls.append(1) or (0, ""), printer=lambda *a: None) == 2
    assert calls == [], "병합 기록 없는 카드는 서버를 부르지 않는다"
