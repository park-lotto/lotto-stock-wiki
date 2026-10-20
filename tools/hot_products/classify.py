"""쇼츠 상품 분류기(주인 함수) — 상품명 → 쇼츠 분류(홈템·뷰티·장비템·차량템·반려템·육아템·디지털템·제외)·제외 사유·신박함·검색 키워드.
10-19 에이전트가 손으로 단 라벨(work/cls2_*.json + titles2_*.tsv, 1,552개)에서 **실제 예시를 골라** 프롬프트에 넣는다(규칙 문장보다 예시).
매일 수집(쿠팡·테무·아마존·1688·네이버 새 상품)은 이 함수 하나로 분류한다 — 다른 곳에 분류 기준을 따로 적지 않는다.

  py -I classify.py <입력.json> <출력.json>        입력 [{"id":..,"title":..,"site":..,"list":..}]  출력 {id: {cat,why,wow,kw}}
  py -I classify.py --agree [N]                    10-19 라벨 N개(기본 200)를 다시 분류해 일치율을 잰다(예시로 쓴 것은 뺌)
서버 공용풀로 돌리려면 HOT_SERVER_POOL=1."""
import json, os, random, re, sys, time
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); W = os.path.join(HERE, "work")
sys.path.insert(0, HERE)
import gkeys
from google import genai
from google.genai import types, errors

CATS = ["홈템", "뷰티", "장비템", "차량템", "반려템", "육아템", "디지털템", "제외"]

def labeled():
    """10-19 사람(에이전트) 라벨 — (제목, 사이트분야, 라벨)"""
    out = []
    for k, f in (("0", "cls2_0_v2.json"), ("1", "cls2_1.json"), ("2", "cls2_2.json")):
        lab = json.load(open(os.path.join(W, f), encoding="utf-8"))
        for line in open(os.path.join(W, f"titles2_{k}.tsv"), encoding="utf-8"):
            p = line.rstrip("\n").split("\t", 2)
            if len(p) == 3 and p[0] in lab: out.append((p[2], p[1], lab[p[0]]))
    return out

def examples(pool, n_per=7, seed=1):
    """분류마다 n개, 제외는 사유마다 고루 — 예시로 쓴 제목은 일치율 측정에서 뺀다"""
    rnd = random.Random(seed); ex = []
    for c in CATS[:-1]:
        cand = [x for x in pool if x[2]["cat"] == c]; ex += rnd.sample(cand, min(n_per, len(cand)))
    whys = {}
    for x in pool:
        if x[2]["cat"] == "제외": whys.setdefault(x[2]["why"], []).append(x)
    for w, xs in sorted(whys.items(), key=lambda t: -len(t[1]))[:8]:
        ex += rnd.sample(xs, min(4, len(xs)))
    return ex

PROMPT = """너는 쇼핑쇼츠(신박한 물건을 15~30초 영상으로 보여주고 쿠팡파트너스로 파는 쇼츠·릴스) 소재 담당이다.
각 상품을 아래 분류 중 하나로 정하라: 홈템 · 뷰티 · 장비템 · 차량템 · 반려템 · 육아템 · 디지털템 · 제외
- 제외: 영상으로 보여줄 '신박한 기능·장면'이 없는 것 — 흔한 가구·침구·기본 생활용품(식탁·매트리스커버·베개·멀티탭처럼 누구나 아는 형태), 식품, 생필품·화장품·반려·차량 소모품(휴지·세제·사료·필터 리필 등), 옷·신발·패션, 브랜드 대표상품(이름값으로 팔리는 것), 서비스·티켓
- 뷰티는 '기기·도구'만(고데기·마사지기·괄사). 바르는 화장품 단품은 제외(화장품 소모품)
- why: 제외면 사유(생필품 소모품·의류·패션·식품·반려 소모품·브랜드 대표상품·화장품 소모품·차량 소모품·기타 중), 아니면 ""
- wow: 신박함 0~3 (0 흔함 … 3 처음 보는 형태·기능)
- kw: 쇼핑 검색창에 칠 일반 상품명 2~4단어(브랜드·수량·용량·옵션 빼고) — 제외여도 반드시 적는다(사람 분류와 다를 때 쓴다)
아래는 사람이 실제로 분류한 예시다(이 기준을 따른다):
{ex}

분류할 상품(번호. [분야] 상품명):
{items}
JSON 배열만: [{{"i":번호,"cat":"홈템","why":"","wow":1,"kw":"..."}}]"""

def classify(items, ex, keys, batch=40):
    """items [{"id","title","list"}] → {id: {...}}"""
    ex_txt = "\n".join(f"- [{l}] {t[:60]} → {lab['cat']}{'(' + lab['why'] + ')' if lab['why'] else ''} kw={lab.get('kw','')}" for t, l, lab in ex)
    out, ki = {}, 0
    for s in range(0, len(items), batch):
        b = items[s:s + batch]
        txt = "\n".join(f"{i}. [{x.get('list','')}] {x['title'][:90]}" for i, x in enumerate(b))
        res, err = None, ""
        for _ in range(len(keys) * 2):
            try:
                client = genai.Client(api_key=keys[ki % len(keys)])   # 변수에 잡아둔다 — 한 줄로 쓰면 호출 전에 닫힌다
                r = client.models.generate_content(model="gemini-2.5-flash", contents=PROMPT.format(ex=ex_txt, items=txt),
                                                   config=types.GenerateContentConfig(temperature=0.1, response_mime_type="application/json"))
                res = json.loads(r.text); break
            except (errors.ClientError, errors.ServerError) as e:
                err = str(e)[:90]; ki += 1; time.sleep(5 if "429" in str(e) else 2)
        if res is None:
            raise RuntimeError(f"분류 실패 묶음 {s}: {err}")         # 조용히 넘기지 않는다
        for o in res:
            i = o.get("i")
            if isinstance(i, int) and 0 <= i < len(b) and o.get("cat") in CATS:
                out[b[i]["id"]] = {"cat": o["cat"], "why": o.get("why") or "", "wow": o.get("wow") or 0, "kw": (o.get("kw") or "").strip()}
        print(f"{min(s + batch, len(items))}/{len(items)}", flush=True)
    return out

if __name__ == "__main__":
    pool = labeled(); ex = examples(pool); keys = gkeys.gemini_keys()
    if sys.argv[1] == "--agree":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 200
        exset = {t for t, _, _ in ex}
        test = random.Random(int(os.environ.get("AGREE_SEED", "7"))).sample([x for x in pool if x[0] not in exset], n)
        got = classify([{"id": str(i), "title": t, "list": l} for i, (t, l, _) in enumerate(test)], ex, keys)
        same_cat = sum(1 for i, (_, _, lab) in enumerate(test) if got.get(str(i), {}).get("cat") == lab["cat"])
        same_ex = sum(1 for i, (_, _, lab) in enumerate(test) if (got.get(str(i), {}).get("cat") == "제외") == (lab["cat"] == "제외"))
        print(f"라벨 {n}개: 분류까지 일치 {same_cat} ({round(100*same_cat/n)}%) / 쇼츠 가능·제외 일치 {same_ex} ({round(100*same_ex/n)}%) / 응답 {len(got)}")
        bad = [(t[:40], lab["cat"], got.get(str(i), {}).get("cat")) for i, (t, _, lab) in enumerate(test) if (got.get(str(i), {}).get("cat") == "제외") != (lab["cat"] == "제외")]
        for x in bad[:20]: print("  다름:", x)
    else:
        items = json.load(open(sys.argv[1], encoding="utf-8"))
        json.dump(classify(items, ex, keys), open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
        print("저장", sys.argv[2])
