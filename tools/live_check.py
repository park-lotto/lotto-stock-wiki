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
    # ★--card 도 검사 종류로 가른다(2026-10-02 실측: 056 api 카드가 --card 로는 영상 비교를 돌았다). 판정은 check_kind 한 곳.
    kind = check_kind(card)[0]
    if kind in ("url", "api"):
        _close_http_cards(repo, [card], sh=sh, write=write, printer=printer)
        return 0
    if kind == "수동":
        printer("카드 %03d: 검사=수동 — 자동으로 못 잰다. 보고 닫아라: py tools/control.py status %d 완료" % (card["번호"], card["번호"]))
        return 0
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


# ── 검사 종류(2026-10-02, 카드 069) ────────────────────────────────────────────
#   병합 28장이 '병합'에 멈춰 있던 뿌리: 영상 없는 카드(화면·가격·설정)는 daily_video_audit 대상 작업이 없어 "대상 없음"만 찍혔다.
#   카드 '검사' 칸이 **무엇으로 재나**를 말한다 — 판정은 check_kind 한 곳.
LIVE_BASE = "https://shoppingshorts.duckdns.org"
_VIDEO_HINT = ("video_assemble", "mix_pipeline", "clean_base", "frame_match", "seg_snap", "screen_clips", "capcut_draft",
               "export_bundle", "scene_play", "voice_presets", "typecast_tts", "audio_post", "tts", "sfx_pack", "render", "pvproxy",
               "preview_proxy", "assemble", "snap_segs")


def check_kind(card):
    """→ (종류, 지시문). 종류: 영상 | url | api | 수동. '검사' 칸이 비면 판단 주인으로 추론(제작 라인이면 영상, 아니면 수동)."""
    v = (card.get("검사") or "").strip()
    if v:
        kind = v.split()[0].lower()
        if kind in ("url", "api"):
            return kind, v
        if kind in ("영상", "video"):
            return "영상", v
        return "수동", v
    owner = (card.get("판단 주인") or "").lower()
    if any(h in owner for h in _VIDEO_HINT):
        return "영상", ""
    return "수동", ""


def _fetch_live(path):
    """라이브 GET → (status, text). 로그인 없는 공개 경로만 잴 수 있다."""
    import urllib.request
    req = urllib.request.Request(LIVE_BASE + path, headers={"User-Agent": "live_check/1"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 — 못 붙은 것도 '실패'로 적는다(조용히 통과 금지)
        return 0, "%r" % e


def http_check(spec, fetch=None):
    """'url <경로> <글자>' → 본문에 글자가 있나 / 'api <경로> k=v,k=v' → JSON 값이 같나. → (통과?, 한 줄 근거)."""
    import json as _json
    fetch = fetch or _fetch_live
    parts = spec.strip().split(None, 2)
    if len(parts) < 3:
        return False, "검사 지시문이 짧다(종류 경로 기대값): %r" % spec
    kind, path, want = parts[0].lower(), parts[1], parts[2].strip()
    st, body = fetch(path)
    if st != 200:
        return False, "%s %s → HTTP %s" % (kind, path, st)
    if kind == "url":
        hit = want in body
        return hit, "%s 에 %r %s" % (path, want, "있음" if hit else "없음")
    try:
        data = _json.loads(body)
    except ValueError:
        return False, "%s 응답이 JSON 이 아니다" % path
    bad = []
    for pair in [p for p in want.split(",") if p.strip()]:
        k, _, v = pair.partition("=")
        got = data.get(k.strip())
        if str(got) != v.strip():
            bad.append("%s=%r(기대 %s)" % (k.strip(), got, v.strip()))
    return (not bad), (path + " " + (" / ".join(bad) if bad else "전부 일치: " + want))


def _deployed(sh, sha):
    """서버 코드에 병합 sha 가 들어 있고(merge-base) 웹이 그 뒤 재시작됐나 → (반영?, 한 줄)."""
    rc, out = sh("cd %s && git merge-base --is-ancestor %s HEAD && echo DEPLOYED $(systemctl show shopping-shorts -p ActiveEnterTimestamp --value)"
                 % (REMOTE_REPO, sha), timeout=60)
    if rc != 0 or "DEPLOYED" not in out:
        return False, "서버 미반영(HEAD 에 %s 없음 — 자동배포 시간창 02~06시 또는 DEPLOY_NOW)" % sha
    return True, out.strip()


def _close_http_cards(repo, due, *, sh, write, printer):
    """url/api 카드: 서버 반영 확인 → HTTP 검사 → 완료 / 회귀. 서버에 아직 없으면 그대로 두고 알린다."""
    for c in due:
        kind, spec = check_kind(c)
        sha = parse_merge(c["병합"])[0]
        ok_dep, why_dep = _deployed(sh, sha)
        stamp = time.strftime("%Y-%m-%d %H:%M")
        if not ok_dep:
            printer("   카드 %03d: %s" % (c["번호"], why_dep))
            if write:
                control.note(repo, c["번호"], "라이브 실측 시도: " + why_dep, printer=lambda *a: None)
            continue
        ok, why = http_check(spec)
        text = "%s %s · %s · 병합 %s" % (stamp, "✅ 통과" if ok else "❌ 실패", why, sha)
        printer(("✅ " if ok else "❌ ") + "카드 %03d %s 검사: %s" % (c["번호"], kind, why))
        if write:
            control.set_field(repo, c["번호"], "라이브 실측", text, printer=lambda *a: None)
            control.set_status(repo, c["번호"], "완료" if ok else "회귀", printer=lambda *a: None)


def run_all(repo, cards, *, jobs=6, write=True, sh=None, printer=print, now=None, min_minutes=10):
    """병합·서버반영 상태 카드 전부를 **서버 한 번 실행**으로 잰다(2026-10-01 사장님 "고치면 묻지 않아도 라이브 뒤 테스트").
    카드마다 따로 돌리면 카드 수 × 10~20분 — 같은 시간대 병합은 같은 고객 작업을 보므로 가장 오래된 병합 기준 hours 로 한 번 재고
    결과를 전부에 적는다. 판정은 daily_video_audit(video_gate.judge) 한 곳."""
    due_all = cards_due(cards, min_minutes=min_minutes, now=now)
    if not due_all:
        printer("실측 대상 없음(병합·서버반영 상태 카드 없음)")
        return 0
    if sh is None:
        key = video_gate._find_key()
        if not key:
            printer("❌ SSH 키를 못 찾았다 — 실측 없이 '됐다'로 만들지 않는다")
            return 2
        sh = video_gate._ssh_runner(key)
    # ★검사 종류로 가른다(2026-10-02): 영상 → 서버 영상 비교 한 번 / url·api → HTTP 로 바로 닫는다 / 수동 → 목록만.
    kinds = {c["번호"]: check_kind(c)[0] for c in due_all}
    http_cards = [c for c in due_all if kinds[c["번호"]] in ("url", "api")]
    manual = [c for c in due_all if kinds[c["번호"]] == "수동"]
    due = [c for c in due_all if kinds[c["번호"]] == "영상"]
    if http_cards:
        _close_http_cards(repo, http_cards, sh=sh, write=write, printer=printer)
    if manual:
        printer("수동 확인 대기 %d장 — 사장님이 보고 닫는다: py tools/control.py status <번호> 완료  (또는 검사 칸: py tools/control.py set <번호> 검사 \"url /경로 글자\")" % len(manual))
        for c in manual:
            printer("   %03d %s · 주인 %s" % (c["번호"], c["제목"][:40], (c.get("판단 주인") or "-")[:50]))
    if not due:
        return 0
    oldest = min(parse_merge(c["병합"])[1] for c in due)
    hours = hours_since(oldest, now)
    printer("영상 실측 대상 %d장(%s) · 병합 뒤 최대 %d시간 · 서버에서 %d작업 검사 중…" % (
        len(due), ", ".join("%03d" % c["번호"] for c in due), hours, jobs))
    rc, out = sh(remote_command(0, hours, jobs), timeout=3600)
    lines = summary_lines(out)
    state, one = verdict(rc, out)
    stamp = time.strftime("%Y-%m-%d %H:%M")
    printer(("✅ " if rc == 0 else "❌ ") + one + " · " + " / ".join(lines[-6:]))
    if write:
        for c in due:
            sha = parse_merge(c["병합"])[0]
            text = "%s %s · 병합 %s 뒤 %d시간(묶음 실측 %d장) · %s" % (stamp, one, sha, hours, len(due), " / ".join(lines[-6:]) if lines else out.strip()[-300:])
            control.set_field(repo, c["번호"], "라이브 실측", text, printer=lambda *a: None)
            if state:
                control.set_status(repo, c["번호"], state, printer=lambda *a: None)
            else:
                control.note(repo, c["번호"], "라이브 실측 시도: " + one, printer=lambda *a: None)
        printer("   카드 %d장에 기록%s" % (len(due), " · 상태 " + state if state else ""))
    return rc


def schedule(printer=print, every_minutes=60):
    """Windows 작업 스케줄러에 매시간 `live_check.py --all` 등록 — 병합된 카드는 묻지 않아도 라이브 뒤 4층 실측을 받는다."""
    import shutil
    import subprocess
    repo = control.main_worktree()
    py = shutil.which("python") or sys.executable
    cmd = 'cmd /c "cd /d \\"%s\\" && \\"%s\\" tools\\live_check.py --all >> \\"%s\\" 2>&1"' % (
        repo, py, Path(repo) / "관제" / "live_check_auto.log")
    r = subprocess.run(["schtasks", "/Create", "/F", "/SC", "MINUTE", "/MO", str(every_minutes), "/TN", "숏템_관제_라이브실측", "/TR", cmd],
                       capture_output=True, text=True, encoding="cp949", errors="replace")
    printer(("✅ 작업 스케줄러 등록: 숏템_관제_라이브실측 매 %d분" % every_minutes) if r.returncode == 0
            else ("❌ 등록 실패: " + (r.stdout + r.stderr).strip()[:200]))
    return r.returncode == 0


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
    ap.add_argument("--schedule", action="store_true", help="작업 스케줄러에 매시간 --all 등록")
    args = ap.parse_args(argv)
    if args.schedule:
        return 0 if schedule() else 1
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
        print("[%s]" % time.strftime("%Y-%m-%d %H:%M"))
        return run_all(repo, cards, jobs=args.jobs, write=not args.no_write)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
