# 오용형 스파인 늘리기(2026-09-18 사장님 "오용형 고르면 스파인 5~10개 순번대로") — 56번 뼈대를 복제하고 훅만 다르게
import sys, json; sys.path.insert(0, "/tmp/ab")
from shopping_shorts.store import Store
st = Store("/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db")
base = [x for x in st.list_spines(status="approved") if x["id"] == 56][0]
NEW = [
  ("유튜브 「OO도 예상 못한 미친 활용법」", "권위자(개발자·제조사·본사)도 예상 못했다는 판을 깔고 본래 용도→엉뚱한 쓰임으로", "예상 ?못|예측 ?못|몰랐던"),
  ("유튜브 「OO의 실수」", "브랜드가 실수했다는 미끼로 열고 본래 용도→사람들의 엉뚱한 쓰임으로", "의 실수"),
  ("유튜브 「직원도 몰래 쓰는 활용법」", "직원·전문가가 몰래 쓴다는 은밀함으로 열고 본래 용도→엉뚱한 쓰임으로", "몰래"),
  ("유튜브 「OO도 감탄한 천재 아이디어」", "권위자가 감탄했다는 판으로 열고 본래 용도→천재들의 아이디어로", "감탄한|놀란 천재"),
]
existing = {x["name"] for x in st.list_spines(status="approved")}
made = []
for name, sit, pat in NEW:
    if name in existing:
        print("이미 있음", name); continue
    sid = st.add_spine(name, situation_type=sit, beat_chain=base.get("beat_chain"), emotion_arc=base.get("emotion_arc"),
                       appeal=base.get("appeal"), fit_categories=["오용형"], status="approved")
    st.set_spine_style(sid, beat_roles=base.get("beat_roles"), templates={r: [] for r in base.get("beat_roles") or []},
                       no_cta=True, hook_3s=base.get("hook_3s"), hook_conceal=base.get("hook_conceal"), fit_categories=["오용형"])
    made.append((sid, name, pat)); print("만듦", sid, name)
json.dump(made, open("/tmp/misuse_new.json", "w"), ensure_ascii=False)
