# -*- coding: utf-8 -*-
"""이야기 작가 대본 감사 — 씨앗 베끼기·첫 줄 다양성·안끼리 유사도 (2026-09-26, 0순위-A1b "점검은 도구로 저장").

서버에서:  python3 tools/story_hook_audit.py [--days 3] [--limit 400]
읽기 전용. 재는 것:
  ① 줄별 씨앗 원문과의 최장 연속 겹침 비율(60%↑ = 베낌) — 대본·훅 따로
  ② 회원별 첫 줄 종류 수(같은 씨앗·다른 회원이 같은 첫 줄을 받나)
  ③ 같은 작업 안끼리 본문 겹침(자카드, 어절) — 훅 빼고
기준선(09-25): 한국어 씨앗 71편 중 60%↑ 겹침 줄이 있는 대본 18편(25%), 90%↑ 7편(10%).
"""
import argparse
import difflib
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict

sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
sys.path.insert(0, ".")


def _norm(s):
    return re.sub(r"[^가-힣0-9a-zA-Z]", "", str(s or ""))


def _run(a, b):
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    m = difflib.SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b))
    return m.size / len(a)


def _words(s):
    return set(re.findall(r"[가-힣0-9a-zA-Z]+", str(s or "")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="shopping_shorts/data/reference.db")
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--limit", type=int, default=400)
    ap.add_argument("--since", default="", help="ISO UTC — 이 시각 이후 갱신된 작업만(배포 전/후 비교)")
    a = ap.parse_args()
    c = sqlite3.connect(a.db)
    q = "select work_id,customer_id,updated_at,state_json from produce_works where updated_at > datetime('now','-%d days')" % a.days
    if a.since:
        q += " and updated_at > '%s'" % a.since.replace("'", "")
    q += " order by updated_at desc limit %d" % a.limit
    n_draft = n_copy60 = n_copy90 = n_hookcopy = 0
    hooks_by_seed = defaultdict(list)
    fixes = Counter()
    pair_sims = []
    seed_from = Counter()
    for wid, cid, ts, sj in c.execute(q):
        try:
            st = json.loads(sj)
        except Exception:      # noqa: BLE001
            continue
        s2 = st.get("s2") or {}
        seed = ((s2.get("seed") or {}).get("text") or "").strip()
        ds = [d for d in (s2.get("drafts") or []) if d.get("made_by") == "이야기작가"]
        if not ds:
            continue
        bodies = []
        for d in ds:
            n_draft += 1
            seed_from[d.get("seed_from") or "?"] += 1
            note = d.get("writer_note") or ((d.get("meta") or {}).get("note") or {})
            for k in ("hook_fix", "hook_retry", "escalation_retry"):
                if note.get(k):
                    fixes[k] += 1
            lines = [b.get("text") or "" for b in (d.get("beats") or [])]
            if not lines:
                continue
            if seed:
                runs = [_run(L, seed) for L in lines]
                if any(r >= 0.6 for r in runs):
                    n_copy60 += 1
                if any(r >= 0.9 for r in runs):
                    n_copy90 += 1
                seed_first = re.split(r"[.!?\n]", seed)[0]
                if _run(lines[0], seed_first) >= 0.6:
                    n_hookcopy += 1
                hooks_by_seed[_norm(seed)[:40]].append((cid, lines[0]))
            bodies.append(_words(" ".join(lines[1:])))
        for i in range(len(bodies)):
            for j in range(i + 1, len(bodies)):
                u = bodies[i] | bodies[j]
                if u:
                    pair_sims.append(len(bodies[i] & bodies[j]) / len(u))
    print("이야기작가 대본 %d편 (씨앗 출처 %s)" % (n_draft, dict(seed_from)))
    if n_draft:
        print("  씨앗 60%%↑ 겹침 줄 있는 대본: %d (%.0f%%) · 90%%↑: %d (%.0f%%) · 훅이 씨앗 첫 줄 60%%↑: %d (%.0f%%)"
              % (n_copy60, 100 * n_copy60 / n_draft, n_copy90, 100 * n_copy90 / n_draft, n_hookcopy, 100 * n_hookcopy / n_draft))
    print("  판정 작동: %s" % (dict(fixes) or "없음"))
    multi = {k: v for k, v in hooks_by_seed.items() if len(v) >= 2}
    if multi:
        print("  같은 씨앗을 2편 이상 쓴 경우 %d개 — 첫 줄 종류/편수:" % len(multi))
        for k, v in list(multi.items())[:8]:
            kinds = len({_norm(h) for _, h in v})
            print("    씨앗「%s…」 %d편 → 첫 줄 %d가지%s" % (k[:18], len(v), kinds, "  ★전부 같음" if kinds == 1 else ""))
    if pair_sims:
        pair_sims.sort()
        print("  같은 작업 안끼리 본문 어절 겹침(자카드) 중앙값 %.2f · 0.5↑ %d/%d쌍"
              % (pair_sims[len(pair_sims) // 2], sum(1 for x in pair_sims if x >= 0.5), len(pair_sims)))


if __name__ == "__main__":
    main()
