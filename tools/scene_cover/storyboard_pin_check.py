# -*- coding: utf-8 -*-
"""스토리보드 장면 고정 대조(관제 120) — 스토리보드 줄별 장면 ↔ 3단계 계획(상속·컷 리듬·저장 관문 뒤) 줄별 장면.

쓰는 법(서버, 운영 DB 읽기 전용):
    python3 storyboard_pin_check.py <job_id> <sbtrial_<job>.json> [--unpinned]
  --unpinned = 고정 표식을 빼고 돌린다(종전 동작 흉내 — 고정이 실제로 무엇을 막는지 전후 비교).
출력: 줄마다 [같음/다름] 스토리보드 장면 → 계획 장면, 끝에 '다른 줄 N / 전체 M'. 다른 줄이 0이어야 통과.
⚠️ 이건 계획 대조다 — 완성본·캡컷 대조는 실제 작업을 렌더한 뒤 tools/editor_vs_final_video.py 로 따로 한다.
"""
import json
import os
import sqlite3
import sys

ROOT = os.environ.get("SS_ROOT") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
DB = os.environ.get("SS_DB") or os.path.join(ROOT, "shopping_shorts", "data", "reference.db")

from shopping_shorts import edit_plan, story_writer, store as _store   # noqa: E402
from shopping_shorts.mix_pipeline import _trim_for_cut_rhythm          # noqa: E402


class _ReadOnly:
    """저장 관문이 읽는 것만 넘긴다 — 운영 DB 에 아무것도 쓰지 않는다."""
    def __init__(self, job):
        self.job = job

    def get_mix_job(self, _j):
        return self.job

    def get_setting(self, *_a, **_k):
        return None


def _ids(b):
    return [r["seg_id"] for r in [b.get("primary") or {}] + list(b.get("alternates") or []) if r.get("seg_id")]


def check(job_id, board, unpinned=False):
    db = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    row = db.execute("select extract_json from mix_jobs where job_id=?", (job_id,)).fetchone()
    ex = json.loads(row[0] or "{}") if row else {}
    srcs = [{"video_id": v, "segments": (e or {}).get("segments") or []} for v, e in ex.items() if isinstance(e, dict)]
    conv = story_writer.storyboard_to_beat_sources(board.get("slots") or [])
    if unpinned:
        for x in conv["beat_sources"]:
            x.pop("pinned", None)
    plan = edit_plan.build_inherit_plan(srcs, conv["script"], conv["beat_sources"])
    if not plan:
        return None, "상속 계획을 못 만듦(줄 수·출처 수 불일치 또는 장면 번호가 재료에 없음)"
    _trim_for_cut_rhythm(plan)
    job = {"customer_id": 0, "extract": ex, "script_structure": {"beat_sources": conv["beat_sources"]}}
    plan = _store._ensure_screen_time(plan, _ReadOnly(job), job_id)
    rows = []
    for x, b in zip(conv["beat_sources"], plan["beats"]):
        want, got = x["segs"], _ids(b)
        rows.append((want == got if want else None, x["role"], want, got))
    return rows, ""


def main(argv):
    unpinned = "--unpinned" in argv
    args = [a for a in argv if not a.startswith("--")]
    job_id, path = args[0], args[1]
    data = json.load(open(path, encoding="utf-8"))
    boards = data.get("boards") or {}
    tot = bad = 0
    for name, bd in (boards.items() if isinstance(boards, dict) else enumerate(boards)):
        rows, why = check(job_id, bd, unpinned)
        print("== 보드 %s %s" % (name, why))
        for ok, role, want, got in rows or []:
            if ok is None:
                continue
            tot += 1
            bad += (not ok)
            print("  [%s] %-10s %s → %s" % ("같음" if ok else "다름", role, ",".join(w[-12:] for w in want), ",".join(g[-12:] for g in got)))
    print("다른 줄 %d / 전체 %d%s" % (bad, tot, " (고정 뺀 종전 흉내)" if unpinned else ""))
    return 1 if bad or not tot else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
