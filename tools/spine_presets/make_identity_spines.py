# 제품정체형 스파인 늘리기(2026-09-18) — 55 뼈대 복제, 훅만 다르게. 재료: 자막 781편 실측(정체 86·구원 58·이건 바로 22)
import sys, json, copy; sys.path.insert(0, "/tmp/ab")
from shopping_shorts.store import Store
st = Store("/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db")
base = [x for x in st.list_spines(status="approved") if x["id"] == 55][0]
NEW = [
  ("유튜브 「OO의 정체」", "누가 왜 쓰는지 의문으로 열고 정체를 밝힌 뒤 효능으로 고조", "의 정체", ["{대상}이 더 많이 쓰는 {제품군}의 정체", "{장소}에서 난리난 {제품군}의 정체", "전국민이 속은 {제품군}의 정체"]),
  ("유튜브 「OO을 구원한 천재의 발명품」", "누구를 구원했는지로 열고 성과·정체·효능으로", "구원한|박살낸|되찾아주는|해방시킨", ["{대상}을 구원한 {나라} 천재의 발명품", "{성과} {나라} 천재의 발명품", "{대상} 해방시킨 {나라} 천재의 발명품"]),
  ("유튜브 「기가 막힌 해답, 바로 OO」", "고민하던 사람이 찾아낸 해답을 바로 밝히고 효능으로", "기가 막힌|바로 이|이게 바로", ["{대상}은 기가 막힌 해답을 찾아냈는데요", "{불편함} 싫은 {대상}이 찾아낸 해답", "바로 {제품}을 활용하는 거였죠"]),
]
existing = {x["name"] for x in st.list_spines(status="approved")}
made = []
for name, sit, pat, titles in NEW:
    if name in existing:
        print("이미 있음", name); continue
    sid = st.add_spine(name, situation_type=sit, beat_chain=base.get("beat_chain"), emotion_arc=base.get("emotion_arc"),
                       appeal=base.get("appeal"), fit_categories=["제품정체형"], status="approved")
    tpl = copy.deepcopy(base.get("templates") or {}); tpl["title"] = titles
    st.set_spine_style(sid, beat_roles=base.get("beat_roles"), templates=tpl, no_cta=True, hook_3s=base.get("hook_3s"),
                       hook_conceal=base.get("hook_conceal"), fit_categories=["제품정체형"])
    made.append((sid, name, pat)); print("만듦", sid, name)
json.dump(made, open("/tmp/identity_new.json", "w"), ensure_ascii=False)
