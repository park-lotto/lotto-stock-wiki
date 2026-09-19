# 히트작 한 편 = 틀 하나. 칸 순서·말투·연결어는 그대로 두고 칸마다 **이 제품 재료로만** 바꿔 쓴다 (2026-09-19).
# 왜: 칸 조각을 섞어 조립하면(fill_templates) 틀에 남은 원래 제품 이야기가 새고(리클라이너·상판),
#     칸마다 인물이 바뀌어 이야기가 끊겼다(실측 제품 3×뼈대 5 전부). 한 편을 통째로 옮기면 이야기가 이어진다.
# 사용(서버):  python3 transpose_hit.py tpl.json out.json "<hit_id,...>" job_id [job_id ...]
# 코드 검사: 칸 수·순서 같음 / 재료에 없는 숫자 / 원래 제품 말이 새어나옴(원문 values가 새 대본에 있음)
import json, re, sys
sys.path.insert(0, "/tmp/ab")
from shopping_shorts import script_generate as sg
from shopping_shorts.store import Store
from shopping_shorts import backbone_assemble as ba

DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
SCHEMA = {"type": "object", "properties": {"cells": {"type": "array", "items": {"type": "object", "properties": {
    "role": {"type": "string"}, "text": {"type": "string"}}, "required": ["role", "text"]}}}, "required": ["cells"]}
STORY_WORDS = {"인물", "장소", "반응", "결과"}


def material(srcs):
    return "\n\n".join((s.get("full_text_ko") or s.get("full_text") or "")[:700] + "\n장면: " +
                       " / ".join((g.get("scene_desc") or "") for g in (s.get("segments") or [])[:12]) for s in srcs[:4])


def transpose(hit, mat):
    cells = [c for c in hit["cells"] if c.get("original")]
    tpl = "\n".join("[%s] %s" % (c["role"], c["original"]) for c in cells)
    p = f"""아래 [히트 대본]은 조회수 {hit['views']:,}회가 나온 쇼핑 숏폼이다. 이걸 틀로 삼아 [새 제품]의 대본을 써라.

규칙
- 칸 수와 순서를 똑같이. 칸마다 히트 대본의 **말투·어미·연결어·문장 길이**를 최대한 그대로 살려라.
- 제품 이야기(제품 이름·효능·동작·불편·숫자)는 **전부 [새 제품] 재료에 있는 것으로만** 바꿔라. 히트 대본의 원래 제품 이야기는 한 조각도 남기지 마라.
- 인물·장소·반응 같은 이야기 장치는 새 제품에 자연스럽게 맞게 바꿔도 된다. 단, 대본 전체에서 인물은 한 사람으로 이어져야 한다.
- 재료에 없는 숫자·출처·수상·판매량은 쓰지 마라.

[히트 대본]
{tpl}

[새 제품 재료]
{mat}"""
    return (sg._call_json(p, SCHEMA) or {}).get("cells") or []


def checks(hit, new, mat):
    out = []
    if [c["role"] for c in new] != [c["role"] for c in hit["cells"] if c.get("original")]:
        out.append("칸 순서 다름")
    txt = " ".join(c["text"] for c in new)
    nums = [n for n in re.findall(r"\d+(?:[.,]\d+)?", txt) if n not in mat]
    if nums:
        out.append("재료에 없는 숫자 %s" % nums)
    leak = sorted({v["value"] for c in hit["cells"] for v in (c.get("values") or [])
                   if (v.get("slot") or "").strip("{} ") not in STORY_WORDS and len(v.get("value") or "") >= 3
                   and v["value"] in txt and v["value"] not in mat})
    if leak:
        out.append("원래 제품 말 새어나옴 %s" % leak)
    return out


def main():
    tpl, dst, hits, jobs = sys.argv[1], sys.argv[2], sys.argv[3].split(","), sys.argv[4:]
    T = {x["id"]: x for x in json.load(open(tpl, encoding="utf-8"))}
    st = Store(DB)
    res = []
    for jid in jobs:
        srcs = ba.sources_from_extract((st.get_mix_job(jid) or {}).get("extract") or {})
        mat = material(srcs)
        for hid in hits:
            hit = T[hid]
            new = transpose(hit, mat)
            res.append({"job": jid, "hit": hid, "hit_views": hit["views"], "hit_user": hit.get("user"),
                        "hit_cells": [{"role": c["role"], "text": c["original"]} for c in hit["cells"] if c.get("original")],
                        "cells": new, "flags": checks(hit, new, mat)})
            print(jid, hid, len(new), res[-1]["flags"], flush=True)
    json.dump(res, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
