# -*- coding: utf-8 -*-
"""장면 분량 결손 감사 — "빈칸이 얼마나 생겼나"를 job 단위로 잰다(2026-09-16).

왜 이 도구가 필요한가:
  사장님 제보("중복 많고 대본이랑 맞냐", job 26698eb0a362)의 뿌리는 채우는 방법이 아니라
  **2단계가 지목한 화면이 대사보다 짧다**는 것이었다. 그 빈칸을 3단계
  `_fill_beat_screen_time`이 대본을 안 보고 메우면서 중복·시간역행이 났다.
  고친 뒤 **실제로 줄었는지**는 이 세 숫자로만 말할 수 있다:
      ① 결손률 = 1 - (2단계 지목 화면 초 / 대사 초)
      ② 덧붙은 컷 수 = 최종 컷 - 2단계 지목 컷
      ③ 같은 그림 반복 수(설명 자카드 ≥ 0.6)
  ★"고쳤다"는 주장은 이 출력으로만 한다(0순위-A1).

쓰는 법(서버에서):
    python3 tools/scene_fill_audit.py                 # 최근 20건
    python3 tools/scene_fill_audit.py --job <job_id>  # 한 건 자세히
    python3 tools/scene_fill_audit.py --since 2026-09-16T04:00  # 배포 뒤 것만
"""
import argparse
import json
import os
import sqlite3
import sys

# ★짧은 컷 기준은 edit_plan이 정본(집 세션 ffad9c56a). 서버 /tmp에서 단독 실행될 때(sys.path에 repo 없음)를 위해 폴백.
try:
    from shopping_shorts.edit_plan import MIN_GOOD_CUT_SECS
except Exception:
    MIN_GOOD_CUT_SECS = float(os.environ.get("MIN_GOOD_CUT_SECS", "1.2") or 1.2)

DB_CANDIDATES = [
    "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db",
    os.path.join(os.path.dirname(__file__), "..", "shopping_shorts", "data", "reference.db"),
]


def _db():
    for p in DB_CANDIDATES:
        if os.path.exists(p):
            return sqlite3.connect(p)
    sys.exit("reference.db를 못 찾았다: " + " / ".join(DB_CANDIDATES))


def _tokens(text):
    """설명 겹침 판정용 낱말 — edit_plan._same_look과 같은 취지(자카드 0.6)."""
    return {w for w in "".join(c if c.isalnum() else " " for c in (text or "")).split() if len(w) > 1}


def _seg_len_map(plan, extract):
    """seg_id -> 길이(초). plan·extract 어디에 있든 긁어모은다."""
    out = {}

    def walk(o):
        if isinstance(o, dict):
            sid = o.get("seg_id")
            if sid and o.get("end") is not None:
                try:
                    out[str(sid)] = float(o["end"]) - float(o.get("start") or 0)
                except (TypeError, ValueError):
                    pass
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(extract)
    walk(plan)
    return out


def _desc_map(plan, extract):
    out = {}

    def walk(o):
        if isinstance(o, dict):
            sid = o.get("seg_id")
            if sid and (o.get("scene_desc") or o.get("change")):
                out.setdefault(str(sid), f"{o.get('scene_desc') or ''} {o.get('change') or ''}")
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(extract)
    walk(plan)
    return out


def audit(job_id, plan_json, struct_json, extract_json, verbose=False):
    try:
        plan = json.loads(plan_json or "{}")
    except Exception:
        return None
    beats = plan.get("beats") or []
    if not beats:
        return None
    struct = json.loads(struct_json or "{}")
    extract = json.loads(extract_json or "{}")
    bs = struct.get("beat_sources") or []
    seglen = _seg_len_map(plan, extract)
    descs = _desc_map(plan, extract)

    narr_secs = have2 = 0.0
    picked = final = 0
    final_ids = []
    rows = []
    for i, b in enumerate(beats):
        need = float(b.get("target_seconds") or 0)
        src = (bs[i].get("segs") or []) if i < len(bs) else []
        got2 = sum(seglen.get(str(s), 0.0) for s in src)
        cuts = b.get("scene_override") or ([b.get("primary")] + list(b.get("alternates") or []))
        cuts = [c for c in cuts if c]
        narr_secs += need
        have2 += got2
        picked += len(src)
        final += len(cuts)
        final_ids += [str(c.get("seg_id")) for c in cuts if c.get("seg_id")]
        rows.append((i, b.get("role"), need, got2, len(src), len(cuts), b.get("narration")))

    # 같은 그림 반복(설명 자카드 ≥ 0.6)
    dup = 0
    seen = []
    for sid in final_ids:
        t = _tokens(descs.get(sid, ""))
        if not t:
            continue
        if any(len(t & p) / max(1, len(t | p)) >= 0.6 for p in seen):
            dup += 1
        else:
            seen.append(t)

    # ★조각남(2026-09-17 사장님 "1.2초 이상이면 좋겠다는 반응이 많다"):
    #   결손·중복이 0이어도 컷이 잘면 "너무 조각난다"는 불만이 나온다 — 덧붙음·같은그림으로는
    #   안 보이는 축이라 따로 잰다. 실측(reference.db 컷 100,658개): 중앙값 1.67초,
    #   1.2초 미만이 29.3%. 원본은 충분히 긴데 채우기가 짧은 쪽까지 긁어 쓰는 게 조각남의 뿌리다.
    final_lens = [seglen.get(sid, 0.0) for sid in final_ids if seglen.get(sid)]
    short_cuts = sum(1 for x in final_lens if x < MIN_GOOD_CUT_SECS)

    res = {
        "job": job_id,
        "beats": len(beats),
        "narr_secs": round(narr_secs, 1),
        "picked_secs": round(have2, 1),
        "gap_pct": round((1 - have2 / narr_secs) * 100, 0) if narr_secs else 0,
        "picked_cuts": picked,
        "final_cuts": final,
        "added_cuts": final - picked,
        "dup_cuts": dup,
        "avg_cut_secs": round(sum(final_lens) / len(final_lens), 2) if final_lens else 0,
        "short_cuts": short_cuts,
        "short_pct": round(short_cuts / len(final_lens) * 100, 0) if final_lens else 0,
        "generator": plan.get("generator") or "",
    }
    if verbose:
        res["rows"] = rows
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job")
    ap.add_argument("--since")
    ap.add_argument("--limit", type=int, default=20)
    a = ap.parse_args()
    c = _db()
    q = ("select job_id, edit_plan_json, script_structure_json, extract_json from mix_jobs "
         "where edit_plan_json is not null")
    args = []
    if a.job:
        q += " and job_id like ?"
        args.append(a.job + "%")
    if a.since:
        q += " and created_at >= ?"
        args.append(a.since)
    q += " order by created_at desc limit ?"
    args.append(a.limit)

    outs = []
    for jid, ep, ss, ex in c.execute(q, args):
        r = audit(jid, ep, ss, ex, verbose=bool(a.job))
        if r:
            outs.append(r)
    if not outs:
        print("대상 job 없음")
        return

    print("job          비트 대사초 지목초 결손%  지목컷 최종컷 덧붙음 같은그림 생성기")
    for r in outs:
        print("%-12s %3d %6.1f %6.1f %5.0f%% %6d %6d %6d %7d  %s" % (
            r["job"][:12], r["beats"], r["narr_secs"], r["picked_secs"], r["gap_pct"],
            r["picked_cuts"], r["final_cuts"], r["added_cuts"], r["dup_cuts"], r["generator"]))
    n = len(outs)
    print("\n-- 평균 %d건: 결손 %.0f%% · 덧붙은 컷 %.1f · 같은그림 %.1f" % (
        n, sum(x["gap_pct"] for x in outs) / n,
        sum(x["added_cuts"] for x in outs) / n,
        sum(x["dup_cuts"] for x in outs) / n))

    if a.job and outs and "rows" in outs[0]:
        print("\n[줄별]")
        for i, role, need, got2, ns, nc, narr in outs[0]["rows"]:
            flag = " <<< 빔" if got2 + 1.0 < need else ""
            print("  [%d] %-10s 대사%5.1fs 지목%5.1fs (%d컷) -> 최종%d컷%s\n      %s" % (
                i, role or "", need, got2, ns, nc, flag, (narr or "")[:60]))


if __name__ == "__main__":
    main()
