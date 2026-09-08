# -*- coding: utf-8 -*-
"""재배치 시뮬레이션 — 라이브 plan을 그대로 놓고 2차·3차를 돌려본다 (2026-09-08).

사장님 "2차까지 해보고 3차까지도 지금 해봐. 어떻게 바뀌는지, 시간은 얼마나 걸리는지."

DB를 **읽기만** 한다(쓰지 않는다). Gemini도 안 쓴다 — 낱말 대조뿐이라 비용 0.

  1차 = 지금 라이브 상태
  2차 = 어긋난 칸(fit<=2)을 **안 쓴 구간**에서 다시 찾는다
  3차 = 그래도 남은 칸을 **이미 쓴 칸과 맞바꾼다**(서로 더 맞으면 교환)
"""
import json
import re
import sqlite3
import sys
import time

DB = "shopping_shorts/data/reference.db"
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 120

# 화면 근거가 필요 없는 말(스토리·감정·CTA) — 이건 fit이 낮아도 정상이라 건드리지 않는다.
FREE = re.compile(r"(했거든|하더라|더라고|였어요|겠더라|생각|느낌|고생|충격|신기|진작|"
                  r"알았으면|댓글|링크|구독|좋아요|남겨|드릴게|왜냐|사실|솔직히|친구|엄마|남편)")


def stems(t):
    return {w[:2] for w in re.findall(r"[가-힣A-Za-z0-9]+", t or "") if len(w) >= 2}


def seg_text(s):
    return f"{s.get('scene_desc') or ''} {s.get('change') or ''} {s.get('text') or ''}"


def hits(narr_stems, seg):
    return len(narr_stems & stems(seg_text(seg)))


def main():
    con = sqlite3.connect(DB)
    rows = list(con.execute(
        "select job_id, edit_plan_json, extract_json from mix_jobs "
        "where edit_plan_json is not null and edit_plan_json<>'' "
        "order by created_at desc limit ?", (LIMIT,)))

    n_jobs = 0
    bad1 = bad2 = bad3 = 0          # 각 단계 뒤 남은 '어긋난 칸'
    fixed2 = fixed3 = 0
    t2 = t3 = 0.0

    for jid, pj, ej in rows:
        try:
            plan = json.loads(pj)
            ex = json.loads(ej or "{}")
        except Exception:
            continue
        beats = plan.get("beats") or []
        segs = []
        for vid, v in (ex.items() if isinstance(ex, dict) else []):
            if isinstance(v, dict):
                for s in (v.get("segments") or []):
                    s = dict(s)
                    s["_vid"] = vid
                    segs.append(s)
        if not beats or not segs:
            continue
        n_jobs += 1
        by_id = {s.get("seg_id"): s for s in segs}
        used = {(b.get("primary") or {}).get("seg_id") for b in beats}

        # ── 대상: fit<=2 이면서 '증거 필수'(자유 문장 제외)
        targets = []
        for i, b in enumerate(beats):
            if (b.get("fit") or 9) > 2:
                continue
            n = b.get("narration") or ""
            if FREE.search(n):
                continue          # 화면이 없어도 되는 말 — 정상이므로 그대로 둔다
            targets.append(i)
        bad1 += len(targets)

        # ── 2차: 안 쓴 구간에서 더 맞는 것 찾기
        st = time.perf_counter()
        cur = {i: (beats[i].get("primary") or {}).get("seg_id") for i in targets}
        left = []
        for i in targets:
            want = stems(beats[i].get("narration") or "")
            base = hits(want, by_id.get(cur[i]) or {})
            best, best_id = base, None
            for s in segs:
                if s.get("seg_id") in used:
                    continue
                h = hits(want, s)
                if h > best:
                    best, best_id = h, s.get("seg_id")
            if best_id:
                used.discard(cur[i])
                used.add(best_id)
                cur[i] = best_id
                fixed2 += 1
            else:
                left.append(i)
        t2 += time.perf_counter() - st
        bad2 += len(left)

        # ── 3차: 남은 칸을 **이미 쓴 칸과 맞바꾼다**(서로 더 맞으면 교환)
        st = time.perf_counter()
        left2 = []
        for i in left:
            want_i = stems(beats[i].get("narration") or "")
            base_i = hits(want_i, by_id.get(cur.get(i)) or {})
            done = False
            for j, b2 in enumerate(beats):
                if j == i or j in cur:
                    continue
                sid_j = (b2.get("primary") or {}).get("seg_id")
                if not sid_j:
                    continue
                want_j = stems(b2.get("narration") or "")
                base_j = hits(want_j, by_id.get(sid_j) or {})
                # 맞바꾸면 둘 다(또는 합이) 나아지나?
                new_i = hits(want_i, by_id.get(sid_j) or {})
                new_j = hits(want_j, by_id.get(cur.get(i)) or {})
                if new_i > base_i and (new_i + new_j) > (base_i + base_j):
                    fixed3 += 1
                    done = True
                    break
            if not done:
                left2.append(i)
        t3 += time.perf_counter() - st
        bad3 += len(left2)

    print("검사 job %d개" % n_jobs)
    print()
    print("  1차(지금)  어긋난 칸           : %4d" % bad1)
    print("  2차(안 쓴 구간에서 재배치) 고침: %4d  → 남은 %d" % (fixed2, bad2))
    print("  3차(쓴 칸과 맞바꾸기)      고침: %4d  → 남은 %d" % (fixed3, bad3))
    print()
    if bad1:
        print("  개선율  2차 %.0f%%  ·  2+3차 %.0f%%"
              % (100 * fixed2 / bad1, 100 * (fixed2 + fixed3) / bad1))
    print("  시간    2차 %.1fms/job · 3차 %.1fms/job  (합 %.1fms)"
          % (1000 * t2 / max(1, n_jobs), 1000 * t3 / max(1, n_jobs),
             1000 * (t2 + t3) / max(1, n_jobs)))


if __name__ == "__main__":
    main()
