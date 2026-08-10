"""후보 간 화면 차별화 측정 — v3 대비 얼마나 갈렸나."""
import json, os, sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shopping_shorts import mix_pipeline, bank_assemble, edit_plan as ep
from shopping_shorts.store import Store
from shopping_shorts.config import DB_PATH

FIX = sys.argv[1]
raw = json.load(open(FIX, encoding="utf-8")); ss = list(raw.values())
st = Store(DB_PATH)
args = dict(ping_pong=st.get_setting("ping_pong_enabled","")=="1",
            backbone_base=st.get_setting("backbone_base_enabled","")=="1",
            judge=True, bank_context=bank_assemble.parts_block(st),
            is_recipe=mix_pipeline._sources_is_recipe(ss))
r = ep.build_scene_first_plan(ss, "", 30, n_candidates=3, video_type=None, **args)
c = r.get("candidates") or []
print(f"{os.path.basename(FIX)} · 후보 {len(c)}")
if not c:
    print("  [x] 후보 0개 — 측정 불가"); sys.exit(1)
sets = []
for i, cd in enumerate(c):
    b = cd["plan"].get("beats") or []
    ids = [(x.get("primary") or {}).get("seg_id") for x in b]
    sets.append(set(ids))
    print(f"  [{i}] {cd['plan'].get('slot_variant','-'):<11} 점수{cd.get('score')} "
          f"{[x.split('-')[-1] if x else None for x in ids]}")
pairs = [(i, j) for i in range(len(sets)) for j in range(i+1, len(sets))]
for i, j in pairs:
    ov = len(sets[i] & sets[j]); tot = max(len(sets[i]), len(sets[j]))
    print(f"  겹침 {i}↔{j}: {ov}/{tot}")
