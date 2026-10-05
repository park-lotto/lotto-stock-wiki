"""저장 관문(store._ensure_screen_time + _dedupe_on_save)이 고정점인가 — 같은 편성을 다시 저장하면 또 바뀌는가(관제 126).
  서버에서: cd /home/ubuntu/lotto-stock-wiki && PYTHONPATH=. python3 tools/render_stamp/check_gate_idempotent.py [최근 job 수=300]
DB 에 **쓰지 않는다** — 관문 함수를 편성 사본에 두 번 돌려 지문(plan_signature)과 바뀐 칸 키를 센다.
'1회차 변화' = 지금 DB 편성이 관문 고정점이 아님 / '2회차 변화' = 한 번 더 저장해도 또 바뀜(비수렴)."""
import copy, sys, collections
from shopping_shorts import app as m, mix_pipeline as mp, store as st
from shopping_shorts.screen_clips import _VOLATILE

N = int(sys.argv[1]) if len(sys.argv) > 1 else 300
S = st.Store(m.DB_PATH)
with S._conn() as c:
    ids = [r[0] for r in c.execute(
        "SELECT job_id FROM mix_jobs WHERE edit_plan_json IS NOT NULL ORDER BY updated_at DESC LIMIT ?", (N,))]


def gate(plan, jid):
    q = st._ensure_screen_time(copy.deepcopy(plan), S, jid)
    q = copy.deepcopy(q)
    st._dedupe_on_save(q, jid)
    return q


def changed_keys(p, q):
    out = collections.Counter()
    for a, b in zip(p.get("beats") or [], q.get("beats") or []):
        for k in set(a) | set(b):
            if k in _VOLATILE or str(k).startswith("_"):
                continue
            if a.get(k) != b.get(k):
                out[k] += 1
    if len(p.get("beats") or []) != len(q.get("beats") or []):
        out["beat_count"] += 1
    return out


n = c1 = c2 = 0
keys1, keys2, samples = collections.Counter(), collections.Counter(), []
for jid in ids:
    p0 = (S.get_mix_job(jid) or {}).get("edit_plan")
    if not p0 or not p0.get("beats"):
        continue
    n += 1
    p1 = gate(p0, jid)
    p2 = gate(p1, jid)
    if mp.plan_signature(p1) != mp.plan_signature(p0):
        c1 += 1; keys1.update(changed_keys(p0, p1))
    if mp.plan_signature(p2) != mp.plan_signature(p1):
        c2 += 1; keys2.update(changed_keys(p1, p2))
        if len(samples) < 8:
            samples.append(jid)
print(f"job {n}개 · 1회차 저장에 바뀜 {c1} · 2회차(같은 걸 또 저장)에도 바뀜 {c2}")
print("1회차 바뀐 키:", dict(keys1.most_common(8)))
print("2회차 바뀐 키:", dict(keys2.most_common(8)))
print("비수렴 예:", samples)
sys.exit(1 if c2 else 0)
