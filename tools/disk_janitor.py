# -*- coding: utf-8 -*-
"""서버 디스크 정리(관제 038) — "만들기만 하고 치우는 코드가 없던" 폴더를 매일 치운다.

왜(2026-09-29 실사고): 디스크 619GB가 100%가 되어 웹이 "임시 폴더를 만들 수 없음"으로 죽고
21:22~21:37 사이 195번 되살기를 반복했다. 실측 — 작업 중간산출물 150GB · 렌즈 임시 프레임 34GB
(하루 14GB씩, 정리 코드 없음) · 릴레이 원본 22GB(같은 영상 중복 13GB) · 방치 미완 32GB.

★판단의 주인 = 이 파일의 plan() 하나. 무엇을 지울지는 여기서만 정한다. --apply 가 그 목록을 지운다.
★지우는 것(전부 다시 만들 수 있거나 이미 쓸모가 끝난 것):
  A find_frames/*        렌즈 장면찾기 임시 프레임 — 1일 지난 것
  B yt_relay/*           PC 릴레이가 올린 원본 — 작업 폴더로 copy2 된 뒤라 전달 완료(status=done)면 1일,
                         DB에 기록이 없으면 7일 지난 것
  C mix_jobs/<job>       실패(failed)로 1일 지난 작업 · DB에 없는 고아 폴더(1일 지난 것) — 폴더 통째
  D mix_jobs/<job>/{pvproxy,capcut,seg_thumbs}   완료(done) 7일 지난 작업의 재생성 가능 조각
                         pvproxy=편집 화면 합본(열면 _pvproxy_prewarm 이 다시 굽는다) · capcut=내보내기 폴더
                         (버튼 누르면 다시 만든다) · seg_thumbs=구간 썸네일(요청 시 다시 뽑는다)
★지우지 않는 것: final*.mp4 · preview.mp4 · s0~s5(원본 — 인스타 재다운로드는 자주 실패) · join*(VMake 유료
  청소 합본, 재사용해 과금 0) · clean_preview.mp4(청소본 정본) · tts · json 전부 · wiki_media(도서관 영구보관)
  · ready_for_review(미완) 작업 — 고객 데이터라 사장님 기준이 나오면 그때.

쓰는 법(서버):
  cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env && set +a
  python3 tools/disk_janitor.py            # 계획만(dry-run) — 무엇을 얼마나 지울지
  python3 tools/disk_janitor.py --apply    # 실제 삭제 + 보고서 /home/ubuntu/disk_janitor/<날짜>.txt
매일 04:00 KST: deploy/shopping-shorts-disk-janitor.timer. 끝나고 여유가 ALERT_FREE_GB 미만이면 관리자 쪽지(ops_alert).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "shopping_shorts" / "data"
ALERT_FREE_GB = 50           # 이 아래로 남으면 관리자 쪽지
FIND_FRAMES_DAYS = 1
RELAY_DONE_DAYS = 1
RELAY_UNKNOWN_DAYS = 7
FAILED_DAYS = 1
ORPHAN_DAYS = 1
DONE_INTERMEDIATE_DAYS = 7
DONE_INTERMEDIATE_NAMES = ("pvproxy", "capcut", "seg_thumbs")
KIND = "disk_free"           # ops_alert 종류 키
_JOB_ID_RE = __import__("re").compile(r"^[0-9a-f]{12}$")


@dataclass
class Candidate:
    path: Path
    size: int
    rule: str        # A/B/C/D
    why: str


def _size(p: Path) -> int:
    if p.is_file() or p.is_symlink():
        try:
            return p.lstat().st_size
        except OSError:
            return 0
    total = 0
    for dp, _dn, fns in os.walk(p, onerror=lambda e: None):
        for fn in fns:
            try:
                total += os.lstat(os.path.join(dp, fn)).st_size
            except OSError:
                pass
    return total


def _age_days(p: Path, now: float) -> float:
    try:
        return (now - p.lstat().st_mtime) / 86400.0
    except OSError:
        return 0.0


def _parse_ts(s):
    """mix_jobs.updated_at(ISO, UTC 또는 tz 포함) → epoch. 못 읽으면 None."""
    if not s:
        return None
    try:
        t = _dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=_dt.timezone.utc)
    return t.timestamp()


def plan(data_dir: Path, jobs: dict, relay: dict, now: float | None = None) -> list[Candidate]:
    """★판단의 주인. jobs = {job_id: (status, updated_at)} · relay = {파일이름: status}.

    DB를 직접 안 읽는다(시험에서 dict로 준다). 실제 값은 load_db()가 만든다."""
    now = now or _dt.datetime.now().timestamp()
    out: list[Candidate] = []

    # A 렌즈 임시 프레임
    ff = data_dir / "find_frames"
    if ff.is_dir():
        for p in ff.iterdir():
            if _age_days(p, now) > FIND_FRAMES_DAYS:
                out.append(Candidate(p, _size(p), "A", "find_frames %d일+" % FIND_FRAMES_DAYS))

    # B 릴레이 원본(작업 폴더로 복사된 뒤의 사본)
    rl = data_dir / "yt_relay"
    if rl.is_dir():
        for p in rl.iterdir():
            if not p.is_file():
                continue
            st = relay.get(p.name)
            age = _age_days(p, now)
            if st == "done" and age > RELAY_DONE_DAYS:
                out.append(Candidate(p, _size(p), "B", "relay 전달완료 %d일+" % RELAY_DONE_DAYS))
            elif st is None and age > RELAY_UNKNOWN_DAYS:
                out.append(Candidate(p, _size(p), "B", "relay 기록없음 %d일+" % RELAY_UNKNOWN_DAYS))

    # C·D 작업 폴더
    mj = data_dir / "mix_jobs"
    if mj.is_dir():
        for d in mj.iterdir():
            if not d.is_dir():
                continue
            rec = jobs.get(d.name)
            if rec is None:
                # 고아 판정은 **job_id 꼴(16진수 12자)**만. _scene_style_lab·b1test…·sfx… 같은 실험·랩 폴더는
                # 다른 세션의 도구가 쓰는 것이라 여기서 판단하지 않는다(실측 2026-09-29: 58개 약 3GB).
                if _JOB_ID_RE.match(d.name) and _age_days(d, now) > ORPHAN_DAYS:
                    out.append(Candidate(d, _size(d), "C", "DB에 없는 고아 폴더 %d일+" % ORPHAN_DAYS))
                continue
            status, updated = rec
            ts = _parse_ts(updated)
            age = (now - ts) / 86400.0 if ts else _age_days(d, now)
            if status == "failed" and age > FAILED_DAYS:
                out.append(Candidate(d, _size(d), "C", "failed %d일+" % FAILED_DAYS))
            elif status == "done" and age > DONE_INTERMEDIATE_DAYS:
                for name in DONE_INTERMEDIATE_NAMES:
                    sub = d / name
                    if sub.exists():
                        out.append(Candidate(sub, _size(sub), "D", "done %d일+ 재생성 가능 조각" % DONE_INTERMEDIATE_DAYS))
    return out


def load_db():
    """라이브 DB에서 plan()에 줄 두 사전을 만든다."""
    import sqlite3
    from shopping_shorts import config
    c = sqlite3.connect(str(config.DB_PATH))
    jobs = {r[0]: (r[1], r[2]) for r in c.execute("SELECT job_id, status, updated_at FROM mix_jobs")}
    relay = {}
    for out_path, status in c.execute("SELECT out_path, status FROM yt_relay WHERE out_path IS NOT NULL"):
        relay[Path(out_path).name] = status
    c.close()
    return jobs, relay


def apply(cands: list[Candidate]) -> tuple[int, list[str]]:
    freed, errors = 0, []
    for c in cands:
        try:
            if c.path.is_dir() and not c.path.is_symlink():
                shutil.rmtree(c.path)
            else:
                c.path.unlink()
            freed += c.size
        except Exception as e:      # noqa: BLE001 — 하나 실패해도 나머지는 지운다, 실패는 보고서에
            errors.append("%s: %r" % (c.path, e))
    return freed, errors


def free_gb(path: Path) -> float:
    st = shutil.disk_usage(str(path))
    return st.free / 1024 ** 3


def summarize(cands: list[Candidate]) -> str:
    by = {}
    for c in cands:
        n, s = by.get(c.rule, (0, 0))
        by[c.rule] = (n + 1, s + c.size)
    lines = ["%s %5d개 %7.1fGB" % (r, n, s / 1024 ** 3) for r, (n, s) in sorted(by.items())]
    lines.append("합계 %d개 %.1fGB" % (len(cands), sum(c.size for c in cands) / 1024 ** 3))
    return "\n".join(lines)


def _alert(free_after: float, report_path: Path, dry: bool):
    """여유가 부족하면 관리자 쪽지, 넉넉하면 이전 경보 해제. 못 올려도 정리 자체는 성공이다."""
    try:
        from shopping_shorts import ops_alert
        if free_after < ALERT_FREE_GB:
            ops_alert.raise_alert(
                KIND, "서버 디스크 여유 %.0fGB — 자동 정리 뒤에도 %dGB 미만" % (free_after, ALERT_FREE_GB),
                "보고서: %s\n지운 뒤에도 부족하다 = 고객 데이터(원본·미완 작업)만 남았다는 뜻. "
                "사장님 기준으로 ready_for_review 오래된 작업 정리 여부를 정해야 한다." % report_path,
                grade="사고", signature="%.0f" % free_after)
        else:
            ops_alert.resolve_kind(KIND)
    except Exception as e:      # noqa: BLE001
        print("[경보 못 올림] %r" % e, file=sys.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="실제로 지운다(없으면 계획만)")
    ap.add_argument("--data-dir", default=str(DATA_DIR))
    ap.add_argument("--report-dir", default=os.environ.get("DISK_JANITOR_REPORT_DIR", str(Path.home() / "disk_janitor")))
    ap.add_argument("--no-alert", action="store_true")
    a = ap.parse_args(argv)
    data_dir = Path(a.data_dir)

    before = free_gb(data_dir)
    jobs, relay = load_db()
    cands = plan(data_dir, jobs, relay)
    head = "[disk_janitor] %s 여유 %.1fGB · 계획:\n%s" % (_dt.datetime.now().strftime("%Y-%m-%d %H:%M"), before, summarize(cands))
    print(head)
    if not a.apply:
        for c in sorted(cands, key=lambda c: -c.size)[:15]:
            print("  %s %7.2fGB %s  (%s)" % (c.rule, c.size / 1024 ** 3, c.path.relative_to(data_dir), c.why))
        print("(dry-run — 지우려면 --apply)")
        return 0

    freed, errors = apply(cands)
    after = free_gb(data_dir)
    rep_dir = Path(a.report_dir); rep_dir.mkdir(parents=True, exist_ok=True)
    rep = rep_dir / (_dt.datetime.now().strftime("%Y-%m-%d_%H%M") + ".txt")
    body = head + "\n지움 %.1fGB · 여유 %.1fGB → %.1fGB · 실패 %d건\n" % (freed / 1024 ** 3, before, after, len(errors))
    body += "\n".join("%s %s" % (c.rule, c.path) for c in cands) + ("\n\n[실패]\n" + "\n".join(errors) if errors else "")
    rep.write_text(body, encoding="utf-8")
    print("지움 %.1fGB · 여유 %.1fGB → %.1fGB · 실패 %d건 · 보고서 %s" % (freed / 1024 ** 3, before, after, len(errors), rep))
    if not a.no_alert:
        _alert(after, rep, dry=False)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
