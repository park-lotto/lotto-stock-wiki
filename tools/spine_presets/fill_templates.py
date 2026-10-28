# 검증된 칸 템플릿 → 뼈대 5개 → 실제 제품 재료로 채워 대본 뽑기 (2026-09-19).
# 사용(서버):  python3 fill_templates.py tpl.json out.json job_id [job_id ...]
#
# 뼈대 = 히트작 한 편의 칸 순서(같은 칸 연속은 하나로). 같은 순서끼리 묶어 편수·조회수 순 상위 5개.
# 채우기:
#   ① 제품 재료(job extract)에서 빈칸 값을 **한 번** 뽑는다 — 재료에 없는 효능·숫자·출처는 빈 값으로 둔다.
#      (인물·장소·반응·결과는 이야기 장치라 지어내도 된다 — 지인증언형의 본질)
#   ② 칸마다 **빈칸이 전부 채워지는** 템플릿만 후보. 없으면 그 칸은 건너뛴다(지어내지 않는다).
#   ③ 코드로 채운 뒤 조사·어미만 다듬는다(모델 1회). 다듬은 문장이 템플릿 뼈 글자를 80% 이상 지켜야 채택,
#      아니면 코드가 채운 그대로 쓴다 — 모델이 문장을 새로 쓰는 걸 막는다.
import json, random, re, sys, collections, difflib
sys.path.insert(0, "/tmp/ab")
from shopping_shorts import script_generate as sg
from shopping_shorts.store import Store
from shopping_shorts import backbone_assemble as ba
from templatize_hits import SLOTS, norm

DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
STORY = {"인물", "장소", "반응", "결과"}          # 이야기 장치 — 재료에 없어도 된다


def skeletons(T, k=5):
    groups = collections.defaultdict(list)
    for x in T:
        seq = []
        for c in x["cells"]:
            if c.get("why_bad"):
                continue
            if not seq or seq[-1] != c["role"]:
                seq.append(c["role"])
        if len(seq) >= 3:
            groups[tuple(seq)].append(x)
    ranked = sorted(groups.items(), key=lambda a: (-len(a[1]), -max(x["views"] for x in a[1])))
    return ranked[:k]


def bank(T):
    b = collections.defaultdict(list)
    for x in T:
        for c in x["cells"]:
            if not c.get("why_bad"):
                b[c["role"]].append({"t": c["template"], "views": x["views"], "src": x["id"]})
    return b


VAL_SCHEMA = {"type": "object", "properties": {k: {"type": "string"} for k in SLOTS}, "required": list(SLOTS)}


def slot_values(sources):
    mat = "\n\n".join((s.get("full_text_ko") or s.get("full_text") or "")[:700] + "\n장면: " +
                      " / ".join((g.get("scene_desc") or "") for g in (s.get("segments") or [])[:12]) for s in sources[:4])
    desc = "\n".join("- %s: %s" % kv for kv in SLOTS.items())
    p = f"""아래 제품 재료(영상 대사·장면)를 읽고 쇼핑 숏폼 대본 빈칸에 넣을 값을 정하라.
★인물·장소·반응·결과는 이야기 장치라 자연스럽게 지어내도 된다(예: 인물=와이프, 반응=소리질렀어요).
★나머지(제품군·기존물건·불편·동작·효능1~3·수치·출처·키워드)는 **재료에 있는 것만**. 없으면 빈 문자열.
값은 대본 문장 속에 그대로 끼워 넣을 짧은 말로(조사 빼고). 반말·존댓말 섞지 말 것.
빈칸:
{desc}

재료:
{mat}"""
    return sg._call_json(p, VAL_SCHEMA) or {}


POLISH_SCHEMA = {"type": "object", "properties": {"lines": {"type": "array", "items": {"type": "string"}}}, "required": ["lines"]}


def polish(lines):
    p = ("아래 문장들은 틀에 단어를 끼워 만든 것이라 조사·어미가 어색할 수 있다. **조사·어미·띄어쓰기만** 고쳐라. "
         "단어를 바꾸거나 문장을 더하거나 빼지 마라. 같은 개수로 돌려줘.\n\n" + "\n".join(lines))
    out = (sg._call_json(p, POLISH_SCHEMA) or {}).get("lines") or []
    return out if len(out) == len(lines) else lines


def keep_ratio(tpl, s):
    bones = norm(re.sub(r"\{[^{}]+\}", "", tpl))
    if not bones:
        return 1.0
    m = difflib.SequenceMatcher(None, bones, norm(s))
    return sum(b.size for b in m.get_matching_blocks()) / len(bones)


def fill(skel, B, vals, seed):
    rnd = random.Random(seed)
    have = {k for k, v in vals.items() if (v or "").strip()}
    lines, used = [], []
    for role in skel:
        cands = [c for c in B.get(role, []) if set(re.findall(r"\{([^{}]+)\}", c["t"])) <= have]
        if not cands:
            used.append((role, None))
            continue
        c = rnd.choice(sorted(cands, key=lambda c: -c["views"])[:8])
        s = c["t"]
        for n in re.findall(r"\{([^{}]+)\}", s):
            s = s.replace("{%s}" % n, vals[n].strip(), 1)
        lines.append(s)
        used.append((role, c))
    pol = polish(lines)
    fin, j = [], 0
    for role, c in used:
        if c is None:
            fin.append({"role": role, "text": "", "skipped": True})
            continue
        s = pol[j] if keep_ratio(c["t"], pol[j]) >= 0.8 else lines[j]
        fin.append({"role": role, "text": s, "template": c["t"], "src": c["src"], "src_views": c["views"]})
        j += 1
    return fin


def main():
    tpl, dst, jobs = sys.argv[1], sys.argv[2], sys.argv[3:]
    T = json.load(open(tpl, encoding="utf-8"))
    SK, B = skeletons(T), bank(T)
    st = Store(DB)
    out = {"skeletons": [{"seq": list(s), "n": len(L), "best": max(x["views"] for x in L),
                          "examples": [x["id"] for x in sorted(L, key=lambda x: -x["views"])[:3]]} for s, L in SK],
           "bank": {r: len(v) for r, v in B.items()}, "products": []}
    for jid in jobs:
        job = st.get_mix_job(jid)
        srcs = ba.sources_from_extract((job or {}).get("extract") or {})
        vals = slot_values(srcs)
        prod = {"job": jid, "values": vals, "scripts": []}
        for i, (s, L) in enumerate(SK):
            prod["scripts"].append({"skeleton": i + 1, "cells": fill(s, B, vals, seed=jid + str(i))})
        out["products"].append(prod)
        print(jid, vals.get("제품군"), flush=True)
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
