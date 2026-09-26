# -*- coding: utf-8 -*-
"""매일 영상 점검 — 어제 고객이 만든 작업으로 '편집 화면 미리보기 vs 완성본'을 영상으로 비교하고, 어긋나면 관리자 쪽지(2026-09-27).

왜: 병합 관문(track.py finish)은 **배포 순간** 최근 작업 몇 개만 본다. 고객 작업은 매일 새 모양으로 들어온다
    (청소본·정지 컷·구절 맞춤…). 관문이 못 본 모양에서 어긋나면 고객이 먼저 안다 → 매일 새벽 전날 작업으로 다시 잰다.
    CLAUDE.md 0순위-C "결과물 점검은 매일 자동으로 돌고 어긋나면 관리자 화면에 경보".

하는 일(서버, 저장소 폴더에서):
  ① /tmp 여유 확인(min_free_gb 미만이면 못 돌린 것도 경보 — 조용히 넘기지 않는다)
  ② 최근 hours 시간 안에 미리보기가 준비된(preview_status='ready') 작업 최신순 jobs 개
  ③ tools/evf_run.py 로 비교(결과는 /tmp/video_audit_<날짜>/ 에 굽고) → report·사진을
     /home/ubuntu/video_audit/<날짜>/ 로 옮기고 임시 폴더 삭제
  ④ video_gate.judge(audit 기준) — 다른 장면 > max_scene · 오류 건너뜀 · 밀림(가운데) 칸 비율 > max_shift_ratio 면
     ops_alert.raise_alert("video_audit", …), 깨끗하면 resolve_kind("video_audit")
  --dry-run: ④에서 쪽지를 실제로 올리지 않고 무엇을 올릴지만 찍는다(시험 실행용)

등록: deploy/shopping-shorts-video-audit.{service,timer} (매일 04:30 KST). 설치 명령은 timer 파일 머리말.
수동: cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env && set +a && \
      python3 tools/daily_video_audit.py [--jobs 2] [--dry-run] [--out-root /tmp/gatecheck/audit]
종료코드: 0 깨끗 · 1 어긋남(경보) · 2 못 돌림(경보) · 3 대상 없음
"""
import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
import video_gate  # noqa: E402

KIND = "video_audit"
KST = timezone(timedelta(hours=9))
DB_REL = "shopping_shorts/data/reference.db"


def pick_jobs(db_path, hours, limit):
    """최근 hours 시간 안에 미리보기가 준비된 작업, 최신순.
    ★updated_at 은 ISO('T' 포함, +00:00) 문자열 — datetime('now') 와 비교하면 공백/T 차이로 오늘치가 다 걸린다
      (메모리 reference_apievents_ts_T비교함정). 같은 모양의 문자열로 만들어 비교한다."""
    con = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    try:
        rows = con.execute(
            "select job_id from mix_jobs where preview_status='ready' "
            "and updated_at >= strftime('%Y-%m-%dT%H:%M:%S','now',?) order by updated_at desc limit ?",
            ("-%d hours" % int(hours), int(limit))).fetchall()
    finally:
        con.close()
    return [r[0] for r in rows]


def _git_head(repo):
    try:
        return subprocess.run(["git", "rev-parse", "--short=10", "HEAD"], cwd=str(repo),
                              capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


def _issue_lines(report_text):
    """작업 줄 중 다른 장면·밀림·건너뜀이 있는 줄만(쪽지 detail 용)."""
    out = []
    for line in report_text.splitlines():
        if " 건너뜀" in line:
            out.append(line[:200])
        elif " 칸" in line and "| 다른장면 " in line:
            if "| 다른장면 [] " not in line or "| 밀림0.15+ [] " not in line:
                out.append(line.split(" | 최대거리")[0][:300])
    return out


class _Alerter:
    """ops_alert 를 감싼다 — dry-run 이면 찍기만, pytest 안에서는 아무것도 안 한다(raise 는 ops_alert 자체 가드,
    resolve 는 가드가 없어 여기서 막는다)."""

    def __init__(self, dry_run, printer=print):
        self.dry, self.p, self.calls = dry_run, printer, []

    def _live(self):
        return not self.dry and not os.environ.get("PYTEST_CURRENT_TEST")

    def raise_(self, title, detail, *, grade, signature, cooldown_sec, todo):
        self.calls.append(("raise", title, detail, grade, signature))
        if not self._live():
            self.p("[dry-run] raise_alert(%r, %r, grade=%r, signature=%r)\n  detail: %s" % (KIND, title, grade, signature, detail[:600]))
            return False
        from shopping_shorts import ops_alert
        from shopping_shorts.store import Store
        sent = ops_alert.raise_alert(KIND, title, detail, cooldown_sec=cooldown_sec, store=Store(str(REPO / DB_REL)),
                                     signature=signature, grade=grade, todo=todo)
        self.p("raise_alert → %s" % ("올림" if sent else "쿨다운·같은 서명이라 건너뜀"))
        return sent

    def resolve(self):
        self.calls.append(("resolve",))
        if not self._live():
            self.p("[dry-run] resolve_kind(%r)" % KIND)
            return 0
        from shopping_shorts import ops_alert
        from shopping_shorts.store import Store
        n = ops_alert.resolve_kind(KIND, store=Store(str(REPO / DB_REL)))
        self.p("resolve_kind → 닫은 쪽지 %d건" % n)
        return n


def run_audit(*, jobs, hours, out_root, tmp_root, alerter, cfg, printer=print, runner=None, free_gb=None, db_path=None,
              now=None):
    """→ 종료코드. runner(ids, work_dir, timeout) 는 비교 실행기(기본 = evf_run.py 서브프로세스)."""
    a = cfg["audit"]
    now = now or datetime.now(KST)
    day = now.strftime("%Y-%m-%d")
    stamp = now.strftime("%m-%d")
    out = Path(out_root) / day
    out.mkdir(parents=True, exist_ok=True)
    todo = "report: %s/report.txt · 사진 eye_<job>.jpg(위=화면·아래=완성본, 빨강=다른 장면)" % out

    free = free_gb if free_gb is not None else shutil.disk_usage(str(tmp_root)).free / 1e9
    if free < float(a.get("min_free_gb", 20)):
        msg = "/tmp 여유 %.0fGB < %sGB" % (free, a.get("min_free_gb", 20))
        printer("❌ 못 돌림: " + msg)
        alerter.raise_("[영상점검 %s] 못 돌림 — 디스크 부족" % stamp, msg, grade="운영주의",
                       signature="%s:disk" % day, cooldown_sec=int(a.get("cooldown_sec", 3600)), todo="디스크 정리 후 수동 실행")
        return 2

    ids = pick_jobs(db_path or str(REPO / DB_REL), hours, jobs)
    printer("대상: 최근 %d시간 미리보기 준비 작업 %d개 (상한 %d) %s" % (hours, len(ids), jobs, ids))
    if not ids:
        (out / "report.txt").write_text("대상 없음(최근 %d시간 preview_status=ready 0건)\n" % hours, encoding="utf-8")
        return 3

    head0 = _git_head(REPO)
    work = Path(tmp_root) / ("video_audit_%s" % now.strftime("%Y%m%d_%H%M%S"))
    t0 = time.time()
    try:
        rc_run, log = (runner or _run_evf)(ids, work, int(a.get("timeout_sec", 3000)))
        rep = (work / "report.txt").read_text(encoding="utf-8") if (work / "report.txt").exists() else ""
        crash = (work / "crash.txt").read_text(encoding="utf-8") if (work / "crash.txt").exists() else ""
        (out / "report.txt").write_text(rep, encoding="utf-8")
        for f in work.glob("eye_*.jpg"):
            shutil.copy2(f, out / f.name)
        if (work / "samples.jsonl").exists():
            shutil.copy2(work / "samples.jsonl", out / "samples.jsonl")
        if log:
            (out / "run.log").write_text(log[-20000:], encoding="utf-8")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    head1 = _git_head(REPO)

    parsed = video_gate.parse_report(rep)
    ok, fails, notes = video_gate.judge(parsed, a, tuple(cfg.get("benign_skips", ["음성 없음"])))
    if rc_run != 0 or crash.strip():
        ok = False
        fails.append("비교 실행 비정상(rc=%s)%s" % (rc_run, (" — " + crash.strip().splitlines()[-1][:200]) if crash.strip() else ""))
    if head0 != head1:
        notes.append("점검 중 배포됨(%s→%s) — 앞 작업과 뒤 작업이 다른 코드로 재였을 수 있다" % (head0, head1))

    summary = {"day": day, "jobs": ids, "ok": ok, "fails": fails, "notes": notes, "summary": parsed.get("summary"),
               "summary_line": parsed.get("summary_line"), "sec": round(time.time() - t0), "git": [head0, head1]}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    printer("판정 근거: %s" % (parsed.get("summary_line") or "(요약 줄 없음)"))
    for f_ in fails:
        printer("  ✗ " + f_)
    for n_ in notes:
        printer("  · " + n_)
    printer("결과: %s/report.txt (%d초)" % (out, summary["sec"]))

    if ok:
        alerter.resolve()
        return 0
    s = parsed.get("summary") or {}
    scene = int(s.get("scene") or 0)
    ran = s.get("cells") is not None and rc_run == 0 and not crash.strip()
    title = ("[영상점검 %s] 편집화면≠완성본 — 다른 장면 %d칸 · 밀림 %d칸 / %d칸 (%d작업)"
             % (stamp, scene, int(s.get("shift_center") or 0), int(s.get("cells") or 0), len(parsed.get("jobs", [])))
             if ran else "[영상점검 %s] 비교를 끝까지 못 돌림" % stamp)
    detail = "\n".join(fails + notes + ["— 작업별 —"] + _issue_lines(rep))
    alerter.raise_(title, detail, grade="고객영향" if scene > 0 else "운영주의",
                   signature="%s:%s" % (day, parsed.get("summary_line") or "|".join(fails)[:120]),
                   cooldown_sec=int(a.get("cooldown_sec", 3600)), todo=todo)
    return 1 if ran else 2


def _run_evf(ids, work, timeout):
    env = dict(os.environ, EVF_OUT=str(work))
    env.pop("PATCH_DIR", None)                         # 매일 점검은 **지금 라이브 코드**를 잰다
    try:
        p = subprocess.run([sys.executable, str(HERE / "evf_run.py"), *ids], cwd=str(REPO), env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired as e:
        return 124, "시간 초과 %ds: %s" % (timeout, (e.stdout or "")[-2000:] if isinstance(e.stdout, str) else "")


def _set_repo(path):
    global REPO
    REPO = Path(path).resolve()


def main(argv=None):
    cfg = video_gate.load_config()
    a = cfg["audit"]
    ap = argparse.ArgumentParser(description="매일 영상 점검(편집 화면 vs 완성본)")
    ap.add_argument("--jobs", type=int, default=int(a.get("jobs", 10)))
    ap.add_argument("--hours", type=int, default=int(a.get("hours", 24)))
    ap.add_argument("--out-root", default="/home/ubuntu/video_audit")
    ap.add_argument("--tmp-root", default="/tmp")
    ap.add_argument("--dry-run", action="store_true", help="쪽지를 올리지 않고 무엇을 올릴지만 찍는다")
    ap.add_argument("--repo", default=str(REPO), help="저장소 폴더(시험 실행 때 도구를 /tmp 에 두고 라이브 저장소를 가리킬 때)")
    args = ap.parse_args(argv)
    _set_repo(args.repo)
    os.chdir(str(REPO))                                  # 비교 도구는 저장소 상대경로(DB·mix_jobs)를 쓴다
    return run_audit(jobs=args.jobs, hours=args.hours, out_root=args.out_root, tmp_root=args.tmp_root,
                     alerter=_Alerter(args.dry_run), cfg=cfg)


if __name__ == "__main__":
    sys.exit(main())
