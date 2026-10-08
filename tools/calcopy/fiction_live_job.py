import sys, json, uuid
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
from shopping_shorts.store import Store
from shopping_shorts import config
st = Store(config.DB_PATH); src = st.get_mix_job("088e901d8955")
r = json.load(open("/tmp/fic_res.json", encoding="utf-8"))[0]
lines = [r["script"]["title"]] + [L["text"] for L in r["script"]["lines"]]
script = "\n".join(lines)
new = uuid.uuid4().hex[:12]
st.create_mix_job(new, src.get("urls") or [], src.get("target_seconds") or 25, src.get("structure") or "free",
                  subtitle_removal=bool(src.get("subtitle_removal")), given_script=script, customer_id=0)
d = json.loads(json.dumps(src.get("deco") or {}))
t = d.get("scene_style", {}).get("text")
if isinstance(t, dict):
    t.update({"hook1": "면도기 개발팀이", "hook2": "사장님 경악하게 만든 사연", "bodyTitle": r["script"]["title"]})
st.update_mix_job(new, voice=src.get("voice"), deco=d, caption_style=src.get("caption_style"), headcopy=src.get("headcopy"))
st.enqueue("mix", {"job_id": new})
print("NEW", new); print(script)
