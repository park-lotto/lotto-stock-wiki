# -*- coding: utf-8 -*-
"""자막 줄을 나눴더니 **안 건드린 줄의 장면이 바뀐** 칸을 전 job에서 센다 (읽기 전용).

왜(2026-09-21 박세현님 job fe21f8a5dc71): 구절맞춤 짝을 개수로만 다시 나누던 규칙 때문에,
마지막 줄 하나를 나눴는데 2번째 줄의 장면이 바뀌었다. 한 job만 보고 끝내지 않는다 —
같은 꼴이 다른 고객에게 얼마나 났는지 전체를 잰다(CLAUDE.md 0순위-A1b).

재는 법: 렌더할 때마다 남는 편집안 스냅샷(mix_jobs/<job>/final_clean_*.plan.json, 시간순)과
지금 DB 편집안을 **앞뒤로 짝지어**, 같은 칸에서
  · 장면 목록(재료)과 대사가 그대로인데  · 자막 줄 수가 달라졌고
  · **앞뒤 양쪽에 같은 글자·같은 위치로 있는 줄**의 담당 장면이 바뀌었으면  → '밀림' 1건.
옛 규칙(개수로 다시 나누기)과 새 규칙(앞 상태에서 짝을 얼리고 뒤 줄에 적용)을 나란히 센다.

쓰는 법(서버에서):
    python3 tools/phrase_owner_audit.py                      # 전 job
    python3 tools/phrase_owner_audit.py --job fe21f8a5dc71   # 한 job 자세히
새 규칙 열은 shopping_shorts.video_assemble에 phrase_owners가 있을 때만 나온다(배포 전 서버는 옛 열만).
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "shopping_shorts" / "data"
va = None      # 비교할 때만 불러온다 — --dump는 서버의 옛 코드로도(=규칙과 무관하게) 돌아야 한다


def _load_va():
    global va
    if va is None:
        sys.path.insert(0, str(ROOT))
        from shopping_shorts import video_assemble as _va
        va = _va
    return va


def _even(k, n, m):
    return k if n <= m else (k * m) // n


def _mat_key(b):
    return [(s.get("video_id"), s.get("start"), s.get("end")) for s in va._beat_material(b)]


def _segs(b):
    return va._caption_segments(b.get("narration") or "", b.get("caption_lines"))


def _starts(segs):
    out, t = [], 0
    for s in segs:
        out.append(t)
        t += len(va.cap_preset_key(s))
    return out


def _new_owners(a, b):
    """새 규칙: 앞 상태(a)에서 짝을 얼리고, 뒤 상태(b)의 줄에 적용."""
    if not hasattr(va, "phrase_owners"):
        return None
    aa = dict(a)
    aa.pop("clip_anchor", None)
    va.ensure_clip_anchor(aa)
    bb = dict(b)
    if aa.get("clip_anchor"):
        bb["clip_anchor"] = aa["clip_anchor"]
    return va.phrase_owners(bb, len(va._beat_material(bb)))


def compare(a, b):
    """같은 칸의 앞(a)·뒤(b) 상태 → None(비교 대상 아님) 또는 {shift_old, shift_new, ...}."""
    if not (a.get("phrase_sync") and b.get("phrase_sync")):
        return None
    if va.cap_preset_key(a.get("narration") or "") != va.cap_preset_key(b.get("narration") or ""):
        return None
    if _mat_key(a) != _mat_key(b) or not _mat_key(a):
        return None
    sa, sb = _segs(a), _segs(b)
    if len(sa) == len(sb) or not sa or not sb:
        return None
    m = len(_mat_key(a))
    pa = {(st, va.cap_preset_key(s)): _even(k, len(sa), m) for k, (st, s) in enumerate(zip(_starts(sa), sa))}
    own_new = _new_owners(a, b)
    shift_old, shift_new, rows = 0, 0, []
    for k, (st, s) in enumerate(zip(_starts(sb), sb)):
        key = (st, va.cap_preset_key(s))
        if key not in pa:
            continue                        # 이 줄은 고객이 직접 나누거나 합친 줄 — 바뀌는 게 정상
        o_old = _even(k, len(sb), m)
        if o_old != pa[key]:
            shift_old += 1
        o_new = own_new[k] if own_new is not None else None
        if o_new is not None and o_new != pa[key]:
            shift_new += 1
        rows.append((s, pa[key], o_old, o_new))
    return {"lines": (len(sa), len(sb)), "clips": m, "shift_old": shift_old,
            "shift_new": shift_new if own_new is not None else None, "rows": rows}


def states_of(job_id, plan_now):
    d = DATA / "mix_jobs" / job_id
    snaps = []
    if d.is_dir():
        for f in sorted(d.glob("final_clean_*.plan.json"), key=lambda p: p.stat().st_mtime):
            try:
                p = json.loads(f.read_text(encoding="utf-8"))
                snaps.append((f.name[12:20], p.get("edit_plan") or p))
            except Exception:      # noqa: BLE001 — 깨진 스냅샷 하나가 전수 점검을 막으면 안 된다
                continue
    if plan_now:
        snaps.append(("DB", plan_now))
    return snaps


_KEEP = ("beat_idx", "narration", "caption_lines", "phrase_sync", "scene_override", "primary",
         "alternates", "clip_anchor")


def _slim(plan):
    """비교에 쓰는 칸만 남긴다(덤프를 작게)."""
    return {"beats": [{k: b.get(k) for k in _KEEP if k in b} for b in (plan or {}).get("beats") or []]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job")
    ap.add_argument("--db", default=str(DATA / "reference.db"))
    ap.add_argument("--dump", help="서버에서: 비교 재료만 뽑아 JSONL(gzip)로 쓴다 — 코드 버전과 무관")
    ap.add_argument("--from-dump", help="로컬에서: 덤프를 읽어 새 코드로 비교한다")
    args = ap.parse_args()
    if args.from_dump:
        import gzip
        with gzip.open(args.from_dump, "rt", encoding="utf-8") as fh:
            dumped = [json.loads(ln) for ln in fh if ln.strip()]
        rows = [(d["job_id"], d["cid"], d["states"]) for d in dumped if not args.job or d["job_id"] == args.job]
    else:
        con = sqlite3.connect("file:%s?mode=ro" % args.db, uri=True)
        q = "select job_id, customer_id, edit_plan_json from mix_jobs where edit_plan_json is not null"
        rows = con.execute(q + (" and job_id=?" if args.job else ""),
                           ((args.job,) if args.job else ())).fetchall()
    if args.dump:
        import gzip
        n = 0
        with gzip.open(args.dump, "wt", encoding="utf-8") as fh:
            for job_id, cid, pj in rows:
                try:
                    st = states_of(job_id, json.loads(pj))
                except Exception:      # noqa: BLE001
                    continue
                if len(st) < 2:
                    continue
                fh.write(json.dumps({"job_id": job_id, "cid": cid,
                                     "states": [[nm, _slim(p)] for nm, p in st]}, ensure_ascii=False) + chr(10))
                n += 1
        print("job %d개 중 상태 2개 이상 %d개를 %s 에 썼다" % (len(rows), n, args.dump))
        return
    _load_va()
    tot = {"jobs": 0, "jobs_multi": 0, "pairs": 0, "beats_cmp": 0, "beats_shift_old": 0,
           "beats_shift_new": 0, "jobs_shift": set(), "cust_shift": set()}
    has_new = hasattr(va, "phrase_owners")
    for job_id, cid, pj in rows:
        tot["jobs"] += 1
        if args.from_dump:
            st = [(nm, p) for nm, p in pj]
        else:
            try:
                st = states_of(job_id, json.loads(pj))
            except Exception:      # noqa: BLE001
                continue
        if len(st) < 2:
            continue
        tot["jobs_multi"] += 1
        for (na, a), (nb, b) in zip(st, st[1:]):
            tot["pairs"] += 1
            ba = {x.get("beat_idx"): x for x in a.get("beats") or []}
            for bb in b.get("beats") or []:
                x = ba.get(bb.get("beat_idx"))
                r = compare(x, bb) if x else None
                if not r:
                    continue
                tot["beats_cmp"] += 1
                if r["shift_old"]:
                    tot["beats_shift_old"] += 1
                    tot["jobs_shift"].add(job_id)
                    tot["cust_shift"].add(cid)
                if r["shift_new"]:
                    tot["beats_shift_new"] += 1
                if args.job or r["shift_old"]:
                    print("job %s cid %s 칸%s %s→%s 줄 %d→%d 장면 %d | 안 건드린 줄 중 장면 바뀜: 옛 규칙 %d / 새 규칙 %s"
                          % (job_id, cid, bb.get("beat_idx"), na, nb, r["lines"][0], r["lines"][1],
                             r["clips"], r["shift_old"], r["shift_new"] if has_new else "-"))
                    if args.job:
                        for s, was, o_old, o_new in r["rows"]:
                            print("      「%s」 원래 장면%d → 옛 규칙 장면%d%s / 새 규칙 %s"
                                  % (s, was + 1, o_old + 1, " ★밀림" if o_old != was else "",
                                     ("장면%d" % (o_new + 1)) if o_new is not None else "-"))
    print("\n== 전수 점검 ==")
    print("job %d개 (편집안 상태가 2개 이상 %d개) · 앞뒤 짝 %d쌍" % (tot["jobs"], tot["jobs_multi"], tot["pairs"]))
    print("장면·대사는 그대로인데 자막 줄 수만 바뀐 칸: %d" % tot["beats_cmp"])
    print("  그중 안 건드린 줄의 장면이 바뀐 칸 — 옛 규칙: %d (job %d개 · 고객 %d명)"
          % (tot["beats_shift_old"], len(tot["jobs_shift"]), len(tot["cust_shift"])))
    print("                                      새 규칙: %s" % (tot["beats_shift_new"] if has_new else "배포 전이라 계산 안 함"))


if __name__ == "__main__":
    main()
