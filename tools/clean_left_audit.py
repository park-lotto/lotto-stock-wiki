# -*- coding: utf-8 -*-
"""자막 남음 대조 — 자막제거를 켠 job에서 **청소본이 있어야 할 칸인데 원본 재료(자막 있음)로 나가는 칸**을 센다(2026-09-28).

왜: 영상 비교(editor_vs_final_video)는 과금 없이(allow_clean=False) 원본을 틀어 **장면은 같게** 나온다 — 판정이
  "안 덮였다"고 잘못 봐도(52a1ef1723a8: 고객이 안 고른 컷을 못 덮은 구간으로 쳐 7칸) 다른 장면 0으로 통과한다.
  그 칸은 실제 렌더에선 동의창·과금(증분 청소)이 뜨거나, 자막제거 없이 렌더하면 **자막이 남는다**.
판정: shopping_shorts.mix_pipeline.clean_left_beats 한 곳(도구는 세기만).
  자막 남음 = 결함(편성은 그대로인데 못 덮음 / 덮인 칸의 원본 조각이 고객이 안 고른 컷 자리가 아님) → 관문 기준 0
  증분 대기 = 청소 뒤 편성이 바뀐 칸·음성이 길어진 칸(렌더하면 동의창을 거쳐 지워진다) → 보고만
  원인 미상 = 안 덮였는데 스냅샷 편성이 없어 못 가림 → 보고만
두 모드:
  (기본) 지금 편성으로 — 관문(병합본 모듈 PATCH_DIR)·수동 점검.
  --delivered  고객이 **받은 실물 완성본** 기준 — status=done 이고 완성본 파일이 마지막 수정 뒤에 만들어진 job 만
               (렌더 뒤 편집한 job 은 완성본이 지금 편성이 아니라 '재구성 불가'로 센다). 실물엔 증분 대기도 원본으로
               나갔으므로 자막 남음(실물) = 자막 남음 + 증분 대기.
  ★렌더 로그 `[clean-base] 원본 재료 잔존 비트`는 쓰지 않는다 — job id 가 없고 미리보기·프레임 요청마다 찍힌다
    (서버 3일 2,830줄, 부분 정본 skip 칸까지 포함).

읽기 전용: DB mode=ro · clean_base._write 막음 · 장면 전환 캐시는 결과 폴더 아래.
서버:  cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env && set +a && \\
       CL_OUT=/tmp/clean_left [PATCH_DIR=/tmp/x] python3 tools/clean_left_audit.py [--delivered] [N최근=30] [job_id ...]
결과: $CL_OUT/report.txt (job별 한 줄 + `== 작업 N · 자막 남음 X칸 · 증분 대기 Y칸 · 원인 미상 Z칸 · 대상 아님 K작업[ · 재구성 불가 R작업]`)
      $CL_OUT/done.txt(`CLA_DONE rc=N`) · 예외면 $CL_OUT/crash.txt
"""
import importlib.util
import os
import re
import sqlite3
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, ".")

OUT = Path(os.getenv("CL_OUT", "/tmp/clean_left"))
os.environ.setdefault("SEG_SNAP_CACHE_DIR", str(OUT / "snapcache"))
DB = "shopping_shorts/data/reference.db"
WORK_ROOT = Path("shopping_shorts/data/mix_jobs")
SUMMARY_RE = re.compile(r"^== 작업 (\d+) · 자막 남음 (\d+)칸 · 증분 대기 (\d+)칸 · 원인 미상 (\d+)칸 · 대상 아님 (\d+)작업"
                        r"(?: · 재구성 불가 (\d+)작업)?\s*$")
# PATCH_DIR 에서 얹는 모듈(import 의존 순서) — 관문(video_gate.PATCH_RELS)에 전부 있어야 한다(test_clean_left_audit 가 대조)
PATCH_MODULES = ("frame_match", "screen_clips", "video_assemble", "clean_base", "mix_pipeline")
FINAL_SLACK = 180       # 완성본 파일 시각이 job updated_at 보다 이만큼 이상 앞서면 '렌더 뒤 편집'(done 저장이 파일 뒤에 온다)


def load_patches():
    pd = os.getenv("PATCH_DIR")
    if not pd:
        return None
    import shopping_shorts
    for n in PATCH_MODULES:
        f = Path(pd) / ("%s.py" % n)
        if f.exists():
            sp = importlib.util.spec_from_file_location("shopping_shorts." + n, str(f))
            m = importlib.util.module_from_spec(sp)
            sys.modules["shopping_shorts." + n] = m
            sp.loader.exec_module(m)
            setattr(shopping_shorts, n, m)
    return Path(pd)


def ro_store():
    from shopping_shorts import store as _st
    S = _st.Store
    if getattr(S, "_audit_ro", False):
        return S

    def _init(self, db_path):
        self.db_path = Path(db_path)

    def _conn(self):
        return sqlite3.connect("file:%s?mode=ro" % Path(self.db_path).resolve().as_posix(), uri=True, timeout=15.0)

    S.__init__ = _init
    S._conn = _conn
    S._audit_ro = True
    return S


def parse_summary(text):
    """report.txt → {"jobs","left","pending","unknown","na","stale"} 또는 None(요약 줄 없음 = 판정 불가)."""
    for line in (text or "").splitlines():
        m = SUMMARY_RE.match(line)
        if m:
            a, b, c, d, e, f = m.groups()
            return {"jobs": int(a), "left": int(b), "pending": int(c), "unknown": int(d), "na": int(e), "stale": int(f or 0)}
    return None


def _ts(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def delivered_current(job):
    """완성본이 지금 편성으로 만든 것인가(렌더 뒤 편집 없음) — status done + 완성본 파일 시각 ≥ updated_at − FINAL_SLACK."""
    vp = (job or {}).get("video_path")
    if (job or {}).get("status") != "done" or not vp or not Path(vp).exists():
        return False
    up = _ts(job.get("updated_at"))
    return up is None or Path(vp).stat().st_mtime >= up - FINAL_SLACK


def classify_line(jid, r, delivered=False):
    """clean_left_beats 결과 → (report 줄, 자막 남음 칸 수, 증분 대기 칸 수, 원인 미상 칸 수).
    ★등급 상향(tier_upgrade): 렌더는 정본 대신 요청 등급 전체를 지운다 → 지금 편성 모드에선 결함·대기 둘 다 대기로 센다."""
    left, pend, unk = list(r["left"]), list(r["pending"]), list(r["unknown"])
    if r.get("tier_upgrade") and not delivered:
        pend, left = sorted(set(pend) | set(left)), []
    if delivered:                       # 실물엔 대기 칸도 원본으로 나갔다
        left, pend = sorted(set(left) | set(pend)), []
    line = "%s | 자막 남음 %s | 증분 대기 %s | 원인 미상 %s | 고른 원본 %s%s" % (
        jid, left, pend, unk, r["chosen"], " | 등급 상향(전체 청소)" if r.get("tier_upgrade") else "")
    return line, len(left), len(pend), len(unk)


def pick_jobs(n, delivered=False):
    con = sqlite3.connect("file:%s?mode=ro" % Path(DB).resolve().as_posix(), uri=True)
    try:
        q = ("select job_id from mix_jobs where subtitle_removal=1 and status='done' order by updated_at desc limit ?"
             if delivered else "select job_id from mix_jobs where subtitle_removal=1 order by updated_at desc limit ?")
        return [r[0] for r in con.execute(q, (n,))]
    finally:
        con.close()


def run(ids_or_n, delivered=False, *, mp=None, store=None, get_job=None, work_root=None):
    OUT.mkdir(parents=True, exist_ok=True)
    if mp is None:
        load_patches()
        S = ro_store()
        from shopping_shorts import clean_base as cb, mix_pipeline as mp
        cb._write = lambda work, base: None      # ★고객 clean_base.json 보호(보정·지도 바로잡기가 쓰려 한다)
        store = S(DB)
        get_job = store.get_mix_job
    work_root = Path(work_root or WORK_ROOT)
    ids = ids_or_n if isinstance(ids_or_n, list) else pick_jobs(int(ids_or_n), delivered)
    rep = open(OUT / "report.txt", "w", encoding="utf-8")
    print("판정: mix_pipeline.clean_left_beats — 자막 남음=청소본이 있어야 할 칸인데 원본 재료(결함) · 증분 대기=청소 뒤 편성 변경·"
          "늘림(렌더 때 동의창) · 고른 원본=고객이 안 지우기로 고른 칸/컷%s" % (
              " · 실물 모드: 대기 칸도 원본으로 나갔으므로 자막 남음에 합친다" if delivered else ""), file=rep, flush=True)
    n = left = pend = unk = na = stale = 0
    for jid in ids:
        t0 = time.time()
        try:
            job = get_job(jid)
            if not job:
                print(jid, "건너뜀 job 없음", file=rep, flush=True)
                continue
            if delivered and not delivered_current(job):
                stale += 1
                print(jid, "재구성 불가(완성본 없음 또는 렌더 뒤 편집)", file=rep, flush=True)
                continue
            r = mp.clean_left_beats(store, job, work_root / jid)
        except Exception as e:      # noqa: BLE001
            traceback.print_exc(file=sys.stderr)
            print(jid, "건너뜀 %s: %s" % (type(e).__name__, str(e)[:160]), file=rep, flush=True)
            continue
        if r is None:
            na += 1
            print(jid, "대상 아님(자막제거 끔·정본 없음)", file=rep, flush=True)
            continue
        line, a, b, c = classify_line(jid, r, delivered)
        n += 1
        left += a
        pend += b
        unk += c
        print("%s | %.0fs" % (line, time.time() - t0), file=rep, flush=True)
    print("== 작업 %d · 자막 남음 %d칸 · 증분 대기 %d칸 · 원인 미상 %d칸 · 대상 아님 %d작업%s" % (
        n, left, pend, unk, na, (" · 재구성 불가 %d작업" % stale) if delivered else ""), file=rep, flush=True)
    rep.close()


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    delivered = "--delivered" in args
    args = [a for a in args if a != "--delivered"]
    ids = [a for a in args if not a.isdigit()]
    target = ids if ids else (int(args[0]) if args and args[0].isdigit() else 30)
    OUT.mkdir(parents=True, exist_ok=True)
    done = OUT / "done.txt"
    for f in (done, OUT / "crash.txt"):
        if f.exists():
            f.unlink()
    rc = 1
    try:
        run(target, delivered)
        rc = 0
    except BaseException:      # noqa: BLE001 — 죽은 이유를 판정 쪽(관문·매일 점검)이 볼 수 있게
        (OUT / "crash.txt").write_text(traceback.format_exc(), encoding="utf-8")
    done.write_text("CLA_DONE rc=%d\n" % rc, encoding="utf-8")
    return rc


if __name__ == "__main__":
    sys.exit(main())
