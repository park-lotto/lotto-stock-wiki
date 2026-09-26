"""칸 번호(beat_idx) 겹침 마이그레이션 — 09-06 이전에 번호가 복제된 job을 정리한다.

★판단은 store.dedupe_beat_idx 한 곳(0순위-B) — 저장 출구·/renumber와 **같은 함수**를 쓴다.
  겹친 뒤 칸만 새 번호 · 그 칸 tts_path/tts_ver 버림(다음 음성 단계가 재합성) ·
  빠진 번호 유지 · scene_lab.beats payload도 같은 매핑.

기본은 --dry-run(읽기 전용 — DB를 mode=ro로 연다, Store를 만들지 않는다).
--apply일 때만 store.update_mix_job(edit_plan=)로 저장한다(★사장님 승인 사항).

  py tools/fix_beat_idx_dups.py b875c3731b73 6c0e9194cdd7 98b910755039 e2458d76dbb3 1572bd6e8292
  py tools/fix_beat_idx_dups.py --db /path/reference.db <job...>          # 다른 DB
  py tools/fix_beat_idx_dups.py --apply <job...>                          # 실제 저장(승인 후)
"""
import argparse
import copy
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shopping_shorts.store import beat_idx_duplicates, dedupe_beat_idx  # noqa: E402

# 만드는 중·렌더 중에 번호를 바꾸면 돌던 작업과 어긋난다 — app /renumber와 같은 가드.
_BUSY = ("downloading", "extracting", "planning", "tts", "rendering", "removing_subtitles")


def _default_db():
    return ROOT / "shopping_shorts" / "data" / "reference.db"


def _read_ro(db, job_id):
    c = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
    try:
        r = c.execute("SELECT status, edit_plan_json FROM mix_jobs WHERE job_id=?", (job_id,)).fetchone()
    finally:
        c.close()
    if not r:
        return None, None
    return r[0], (json.loads(r[1]) if r[1] else None)


def plan_report(plan):
    """정리 전후 비교(순수). plan은 건드리지 않는다."""
    after = copy.deepcopy(plan)
    before_idx = [b.get("beat_idx") for b in plan.get("beats") or []]
    dups = beat_idx_duplicates(plan)
    n = dedupe_beat_idx(after)
    after_idx = [b.get("beat_idx") for b in after.get("beats") or []]
    moved = [(pos, a, b) for pos, (a, b) in enumerate(zip(before_idx, after_idx)) if a != b]
    tts_dropped = [pos for pos, _a, _b in moved
                   if (plan["beats"][pos] or {}).get("tts_path")]
    lab_b = [x.get("beat_idx") for x in ((plan.get("scene_lab") or {}).get("beats") or [])]
    lab_a = [x.get("beat_idx") for x in ((after.get("scene_lab") or {}).get("beats") or [])]
    return {"dups": dups, "changed": n, "before": before_idx, "after": after_idx,
            "moved": moved, "tts_dropped": tts_dropped,
            "tts_paths_dropped": [plan["beats"][p].get("tts_path") for p in tts_dropped],
            "lab_before": lab_b, "lab_after": lab_a, "plan_after": after}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("jobs", nargs="+")
    ap.add_argument("--db", default=None)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True)
    g.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    db = a.db or str(_default_db())
    rc = 0
    for jid in a.jobs:
        status, plan = _read_ro(db, jid)
        if plan is None:
            print(f"[{jid}] 작업/편성 없음 — 건너뜀")
            rc = 1
            continue
        rep = plan_report(plan)
        print(f"[{jid}] status={status} 겹친 번호={rep['dups']} 바뀌는 칸={rep['changed']}")
        if not rep["changed"]:
            print("   겹침 없음 — 그대로")
            continue
        print(f"   beat_idx  전 {rep['before']}")
        print(f"             후 {rep['after']}")
        for pos, old, new in rep["moved"]:
            tp = (plan["beats"][pos] or {}).get("tts_path") or "-"
            print(f"   칸 {pos + 1}(위치 {pos}): {old} → {new}  음성 버림: {Path(tp).name if tp != '-' else '(원래 없음)'}")
        print(f"   버려지는 tts_path {len(rep['tts_dropped'])}개")
        if rep["lab_before"] != rep["lab_after"]:
            print(f"   scene_lab.beats 전 {rep['lab_before']}")
            print(f"                   후 {rep['lab_after']}")
        else:
            print(f"   scene_lab.beats 변화 없음 {rep['lab_before']}")
        if not a.apply:
            continue
        if status in _BUSY:
            print(f"   ⚠ {status} 중 — 저장 안 함")
            rc = 1
            continue
        from shopping_shorts.store import Store
        store = Store(db)
        store.update_mix_job(jid, edit_plan=rep["plan_after"])
        _s, saved = _read_ro(db, jid)
        left = beat_idx_duplicates(saved or {})
        print(f"   저장함 — 저장본 겹침 {left or '없음'}")
        if left:
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
