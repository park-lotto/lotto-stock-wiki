# -*- coding: utf-8 -*-
"""라이브 실측 — 카드가 병합된 **뒤에 생긴 실제 고객 작업**으로 결과물 검사 4층(영상·소리·자막·캡컷)을 서버에서 돌려
숫자를 카드에 붙인다(관제 설계 1-4, 카드 003). "됐다"의 정의: 이 숫자가 카드의 '됐다의 기준'을 채웠을 때.

흐름:
  ① 카드(origin/main)에서 병합 sha·시각을 읽는다 → 그 뒤 몇 시간이 지났나(hours)
  ② 서버에 ssh → 저장소 폴더에서 `tools/daily_video_audit.py --dry-run --hours <hours> --jobs <n> --out-root /tmp/live_check/<카드>`
     (같은 검사 도구 — 판단은 video_gate.judge 한 곳. 여기서 따로 판정을 적지 않는다)
  ③ 출력의 요약 줄(== 칸/잔상/컷/소리 … · ✅/❌)을 카드 '라이브 실측' 칸과 이력에 적고, 상태를
     라이브실측(전부 통과·비교 작업 ≥1) / 회귀(하나라도 ❌) 로 바꾼다. 대상 작업이 0이면 상태는 그대로 두고 "대상 없음"만 적는다.
  --all: 상태가 병합·서버반영 이고 병합 뒤 min_minutes 지난 카드 전부. --no-write: 카드에 안 적고 찍기만(시험용).

★서버 실측이 없으면 "됐다"가 아니다. ssh 가 안 되면 실패로 끝낸다(조용히 통과 없음).
사용:
    py tools/live_check.py --card 23 [--jobs 4] [--no-write]
    py tools/live_check.py --all
"""
import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import control  # noqa: E402
import video_gate  # noqa: E402

REMOTE_REPO = video_gate.REMOTE_REPO
HOST = video_gate.HOST
_MERGE = re.compile(r"^([0-9a-f]{7,40})\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2})")
_SUMMARY_PREFIX = ("==", "✅", "❌", "대상:", "판정", "  •", "  -")


def parse_merge(field):
    """카드 '병합' 칸 'sha YYYY-MM-DD HH:MM (트랙)' → (sha, epoch) 또는 None."""
    m = _MERGE.match((field or "").strip())
    if not m:
        return None
    t = time.mktime(time.strptime(m.group(2), "%Y-%m-%d %H:%M"))
    return m.group(1), t


def hours_since(epoch, now=None, lo=1, hi=72):
    h = ((now or time.time()) - epoch) / 3600.0
    return int(min(hi, max(lo, h + 0.999)))


def summary_lines(output):
    """서버 출력에서 사람이 볼 요약 줄만."""
    keep = []
    for ln in (output or "").splitlines():
        s = ln.rstrip()
        if s.startswith(_SUMMARY_PREFIX):
            keep.append(s)
    return keep


def verdict(rc, output):
    """daily_video_audit 종료코드: 0 깨끗 · 1 어긋남 · 2 못 돌림 · 3 대상 없음 → (상태, 한 줄)."""
    if rc == 0:
        return "라이브실측", "통과"
    if rc == 1:
        return "회귀", "어긋남"
    if rc == 3:
        return None, "대상 없음(병합 뒤 고객 작업 0) — 다음에 다시"
    return None, "못 돌림(rc=%s) — 서버·디스크 확인" % rc


def remote_command(card_no, hours, jobs):
    return ("cd %s && set -a && . /etc/shopping-shorts.env && set +a && "
            "python3 tools/daily_video_audit.py --dry-run --hours %d --jobs %d --out-root /tmp/live_check/%03d"
            % (REMOTE_REPO, hours, jobs, card_no))


def run_card(repo, card, *, jobs=4, write=True, sh=None, printer=print, now=None):
    pm = parse_merge(card.get("병합", ""))
    if pm is None:
        printer("카드 %03d: 병합 기록이 없다(%r) — finish 가 먹인 카드만 실측한다" % (card["번호"], card.get("병합", "")))
        return 2
    sha, t = pm
    hours = hours_since(t, now)
    if sh is None:
        key = video_gate._find_key()
        if not key:
            printer("❌ SSH 키를 못 찾았다 — 실측 없이 '됐다'로 만들지 않는다")
            return 2
        sh = video_gate._ssh_runner(key)
    cmd = remote_command(card["번호"], hours, jobs)
    printer("카드 %03d 실측: 병합 %s(%s, %d시간 전) · 서버에서 %d작업 검사 중…" % (card["번호"], sha, card.get("병합", "")[:27], hours, jobs))
    rc, out = sh(cmd, timeout=3600)
    lines = summary_lines(out)
    state, one = verdict(rc, out)
    stamp = time.strftime("%Y-%m-%d %H:%M")
    text = "%s %s · 병합 %s 뒤 %d시간 · %s" % (stamp, one, sha, hours, " / ".join(lines[-6:]) if lines else out.strip()[-300:])
    printer(("✅ " if rc == 0 else "❌ ") + text)
    if write:
        control.set_field(repo, card["번호"], "라이브 실측", text, printer=lambda *a: None)
        if state:
            control.set_status(repo, card["번호"], state, printer=lambda *a: None)
        else:
            control.note(repo, card["번호"], "라이브 실측 시도: " + one, printer=lambda *a: None)
        printer("   카드 %03d 에 기록%s" % (card["번호"], " · 상태 " + state if state else ""))
    return rc


def cards_due(cards, min_minutes=10, now=None):
    now = now or time.time()
    out = []
    for c in cards:
        if c.get("상태") not in ("병합", "서버반영"):
            continue
        pm = parse_merge(c.get("병합", ""))
        if pm and now - pm[1] >= min_minutes * 60:
            out.append(c)
    return out


def main(argv=None):
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, OSError, ValueError):
        pass
    ap = argparse.ArgumentParser(description="라이브 실측")
    ap.add_argument("--card", type=int)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args(argv)
    repo = control.main_worktree()
    control._git(repo, "fetch", "origin")
    cards = control.cards_from_ref(repo)
    if args.card:
        c = control.find_card(cards, args.card)
        if c is None:
            print("없는 카드: %d" % args.card, file=sys.stderr)
            return 2
        return run_card(repo, c, jobs=args.jobs, write=not args.no_write)
    if args.all:
        due = cards_due(cards)
        print("실측 대상 %d장: %s" % (len(due), ", ".join("%03d" % c["번호"] for c in due)))
        worst = 0
        for c in due:
            worst = max(worst, run_card(repo, c, jobs=args.jobs, write=not args.no_write))
        return worst
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
