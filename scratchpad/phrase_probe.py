"""후보끼리 같은 제품 표현을 반복하는가 — 베낀 티 실측."""
import json, os, re, sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shopping_shorts import mix_pipeline, bank_assemble, edit_plan as ep
from shopping_shorts.store import Store
from shopping_shorts.config import DB_PATH

fx = sys.argv[1]
raw = json.load(open(fx, encoding="utf-8")); ss = list(raw.values())
st = Store(DB_PATH)
res = ep.build_scene_first_plan(ss, "", 30, n_candidates=3, video_type=None,
        ping_pong=st.get_setting("ping_pong_enabled","")=="1",
        backbone_base=st.get_setting("backbone_base_enabled","")=="1",
        judge=True, bank_context=bank_assemble.parts_block(st),
        is_recipe=mix_pipeline._sources_is_recipe(ss))
cands = res.get("candidates") or []
if not cands:
    print("[x] 후보 0개"); sys.exit(1)

def words(t):
    return set(re.findall(r"[가-힣]{2,}", t or ""))

texts = []
for i, cd in enumerate(cands):
    b = cd["plan"].get("beats") or []
    full = " ".join(x.get("narration") or "" for x in b)
    texts.append(full)
    print(f"[{i}] {cd['plan'].get('slot_variant','-')}")
    for x in b:
        print("     ", (x.get("narration") or "")[:52])

print("\n=== 후보끼리 겹치는 낱말 ===")
tot = 0
for i in range(len(texts)):
    for j in range(i+1, len(texts)):
        sh = words(texts[i]) & words(texts[j])
        # 흔한 말은 뺀다
        sh = {w for w in sh if len(w) >= 2 and w not in {"이거","그냥","진짜","정말","해서","하고","있는","되는","같은","해도","라고","댓글","남겨","주세요","궁금","분들","하시"}}
        tot += len(sh)
        print(f"  {i}↔{j}: {len(sh)}개 {sorted(sh)[:10]}")
print(f"\n겹침 총합 {tot}개 (적을수록 서로 다른 말)")
