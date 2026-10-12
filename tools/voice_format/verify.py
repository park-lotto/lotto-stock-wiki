import json, sys, time
from google import genai
from google.genai import types
env = dict(l.strip().split("=",1) for l in open(r"C:/Users/TheRose/Desktop/로또의 주식/shopping_shorts/.env",encoding="utf-8") if "=" in l and not l.startswith("#"))
keys=[env[k].strip('"') for k in ("GEMINI_API_KEY","GEMINI_API_KEY_2","GEMINI_API_KEY_3","GEMINI_API_KEY_4") if env.get(k)]
o=json.load(open("voices_out.json",encoding="utf-8"))
P="""이 소리에서 '주 나레이터와 다른 목소리'가 나레이터 말 사이에 끼어들어 반응하는 순간만 찾아라.
같은 사람이 톤만 바꾼 것은 다른 목소리가 아니다. 영상 속 인물 인터뷰·대화 원음은 kind="원음"으로 따로 표시.
JSON: {"distinct_second_voice": true/false, "same_person_tone_change": true/false, "lines":[{"t":초,"text":"","kind":"리액션|원음"}]}"""
res=json.load(open("verify_out.json",encoding="utf-8")) if False else {}
pos=[sc for sc,v in o.items() if "err" not in v and (v.get("n_voices") or 0)>=2]
ki=0
for sc in pos:
    import glob; f=glob.glob(f"aud/{sc}.*")[0]
    for a in range(6):
        try:
            c=genai.Client(api_key=keys[ki%len(keys)],http_options=types.HttpOptions(timeout=90000))
            r=c.models.generate_content(model="gemini-2.5-flash",contents=[types.Part.from_bytes(data=open(f,"rb").read(),mime_type="audio/mp4"),P],config=types.GenerateContentConfig(response_mime_type="application/json",temperature=0))
            _j=json.loads(r.text); _j=_j[0] if isinstance(_j,list) and _j and isinstance(_j[0],dict) else _j; res[sc]=_j if isinstance(_j,dict) else {"raw":_j}; break
        except Exception as e: res[sc]={"err":str(e)[:120]};ki+=1;time.sleep(3)
    json.dump(res,open("verify_out.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
    print(sc,res[sc].get("distinct_second_voice"),res[sc].get("same_person_tone_change"),flush=True)
