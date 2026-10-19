# 숏템메이커 칼카피 엔진 run_frame 을 Vertex(ADC)로 — 저장소 파일은 고치지 않음
import json, sys
from pathlib import Path
ROOT = r"C:\Users\TheRose\Desktop\로또의 주식\.tracks\칼카피숏템엔진"; sys.path.insert(0, ROOT)
from google import genai
from google.genai import types
from tools.calcopy.engine import script_engine as SE, topic_find as TF
cl = genai.Client(vertexai=True, project="project-74eaf695-8229-44a1-876", location="global")
M = "gemini-3.6-flash"
if sys.argv[1] == "ping":
    print(cl.models.generate_content(model=M, contents="한 단어로: 안녕").text); sys.exit()
def vfn(prompt, tag):
    try:
        r = cl.models.generate_content(model=M, contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0, seed=7))
        d = json.loads(r.text); d = d if isinstance(d, dict) else {"lines": d}
        d["_model"] = "vertex:" + M; return d, None
    except Exception as e:
        return None, repr(e)[:300]
res = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
facts = {f"f{i+1}": {"text": x["text"], "url": x.get("url", "")} for i, x in enumerate(res["facts"])}
S = SE.run_frame(sys.argv[2], {"name": res["product"]}, facts, Path(sys.argv[3]), llm=TF.LLM(fn=vfn, budget=8))
print("status:", S["status"], "llm_calls:", S.get("llm_calls"))
for l in S["final"]["lines"]: print(l.get("fn") or l.get("node"), "|", l["text"])
