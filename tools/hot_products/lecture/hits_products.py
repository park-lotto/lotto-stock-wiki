"""정답지 만들기 — 레퍼런스랭킹에서 실제로 터진 쇼핑쇼츠(캡션)에서 '무슨 상품인지'를 제미나이가 뽑는다.
입력 work/hits_dump.json(서버 hits_since 60일·archive_hits) → 출력 work/hits_products.json
[{shortcode, platform, views, comments, category, product, kw, is_product}]"""
import json, os, re, sys, time
sys.stdout.reconfigure(encoding="utf-8")
from google import genai
from google.genai import types, errors

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "..", "work")
env = {}
for line in open(os.path.join(HERE, "..", "..", "..", ".env"), encoding="utf-8"):
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1); env[k.strip()] = v.strip().strip('"')
KEYS = [v for k, v in env.items() if re.match(r"^GEMINI_API_KEY(_\d+)?$", k) and v]
D = json.load(open(os.path.join(WORK, "hits_dump.json"), encoding="utf-8"))
rows = []
for plat, items in D.items():
    for x in items:
        cap = (x.get("caption") or "").strip()
        if len(cap) < 8: continue
        rows.append({"shortcode": x.get("shortcode"), "platform": plat, "views": x.get("views"), "comments": x.get("comments"),
                     "category": x.get("category"), "caption": cap[:400]})
out_path = os.path.join(WORK, "hits_products.json")
done = {r["shortcode"]: r for r in json.load(open(out_path, encoding="utf-8"))} if os.path.exists(out_path) else {}
todo = [r for r in rows if r["shortcode"] not in done]
PROMPT = """아래는 SNS에서 조회수가 크게 터진 쇼츠·릴스의 캡션이다. 각 줄마다 이 영상이 소개하는 '상품'을 뽑아라.
- is_product: 실제로 살 수 있는 물건을 소개하는 영상이면 true (레시피·일상·연예·정보만이면 false)
- product: 상품을 한국어로 구체적으로(예: "뜨개 꽃 티코스터", "좀벌레 퇴치제"). 모르면 ""
- kw: 쇼핑 검색창에 칠 검색어 2~4단어(브랜드·수량 없이). 모르면 ""
JSON 배열만, 입력 순서대로: [{"i":번호,"is_product":true,"product":"...","kw":"..."}]
"""
ki = 0
for s in range(0, len(todo), 40):
    batch = todo[s:s + 40]
    text = "\n".join(f"{i}. {r['caption'].replace(chr(10), ' ')}" for i, r in enumerate(batch))
    res = None
    for _ in range(len(KEYS) * 2):
        try:
            client = genai.Client(api_key=KEYS[ki % len(KEYS)])   # 변수에 잡아둔다 — 한 줄로 쓰면 호출 전에 닫힌다
            r = client.models.generate_content(
                model="gemini-2.5-flash", contents=PROMPT + "\n" + text,
                config=types.GenerateContentConfig(temperature=0.1, response_mime_type="application/json"))
            res = json.loads(r.text); break
        except (errors.ClientError, errors.ServerError) as e:
            ki += 1; time.sleep(3)
        except Exception as e:
            print("ERR", str(e)[:100]); break
    if not res: continue
    for o in res:
        i = o.get("i")
        if isinstance(i, int) and 0 <= i < len(batch):
            b = dict(batch[i]); b.update({k: o.get(k) for k in ("is_product", "product", "kw")}); b.pop("caption", None)
            done[b["shortcode"]] = b
    json.dump(list(done.values()), open(out_path, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{min(s + 40, len(todo))}/{len(todo)}", flush=True)
p = [r for r in done.values() if r.get("is_product")]
print("끝: 전체", len(done), "상품 영상", len(p))
