# 히트작 한 편 = 틀 하나. 칸 순서·말투·연결어는 그대로 두고 칸마다 **이 제품 재료로만** 바꿔 쓴다 (2026-09-19).
# 왜: 칸 조각을 섞어 조립하면(fill_templates) 틀에 남은 원래 제품 이야기가 새고(리클라이너·상판),
#     칸마다 인물이 바뀌어 이야기가 끊겼다(실측 제품 3×뼈대 5 전부). 한 편을 통째로 옮기면 이야기가 이어진다.
# 사장님 09-19: ①CTA가 두 번 나오는 게 많다(전사본 반복을 따라 함) → dedup
#              ②훅은 '시어머니만 동료로 바꾸고 욕 바가지는 동일하게' → hook_exact(빈칸만 바꾸고 글자 고정)
# 사용(서버):  python3 transpose_hit.py tpl.json out.json "<hit_id,...>" job_id [job_id ...]
# 코드 검사: 칸 순서 같음 / 재료에 없는 숫자 / 원래 제품 말 새어나옴 / 같은 말 반복 / 훅 글자 고정
import json, re, sys
sys.path.insert(0, "/tmp/ab")

SCHEMA = {"type": "object", "properties": {
    "cells": {"type": "array", "items": {"type": "object", "properties": {
        "role": {"type": "string"}, "text": {"type": "string"}}, "required": ["role", "text"]}},
    "hook_values": {"type": "array", "items": {"type": "object", "properties": {
        "slot": {"type": "string"}, "value": {"type": "string"}}, "required": ["slot", "value"]}}},
    "required": ["cells"]}
STORY_WORDS = {"인물", "장소", "반응", "결과"}
DUP = re.compile(r"(\S.{3,}?[.!?]?)\s*\1")


def dedup(t):
    """전사본의 같은 말 연달아 반복('세탁 남겨주세요. 세탁 남겨주세요.')을 한 번으로 — 원문 흠을 따라 하지 않게."""
    prev = None
    while prev != t:
        prev, t = t, DUP.sub(r"\1", t)
    return t.strip()


def _bones(tpl):
    return [re.sub(r"\s", "", b) for b in re.split(r"\{[^{}]+\}", tpl) if b.strip()]


AUTH = {"개발자", "개발진", "본사", "제조사", "천재", "천재들", "디자이너", "직원", "직원들", "사장님", "사장님들", "업계", "의사", "약사",
        "간호사", "셰프", "장인", "고수", "고수들", "주부", "주부들", "엄마들", "더쿠들", "과학자", "엔지니어"}
LOOP_END = re.compile(r"(근데|그런데|근데 진짜|하지만|는데|은데|하는|쓰이는|로도|해서|이게)\s*$")


def _orig_vals(hook_cell):
    out = {}
    for v in hook_cell.get("values") or []:
        out.setdefault((v.get("slot") or "").strip("{} "), []).append(v.get("value") or "")
    return out


def hook_exact(hook_cell, new_text, vals):
    """훅은 원문 글자 그대로 두고 빈칸만 바꾼다. 모델 결과가 뼈 글자를 전부 지키면 그대로,
    아니면 코드가 템플릿 빈칸을 채운다. 채울 값이 없으면 모델 결과(검사에서 '훅 글자 바뀜'으로 걸린다)."""
    tpl = hook_cell.get("template") or ""
    if hook_cell.get("why_bad") or not tpl:
        return new_text
    orig = _orig_vals(hook_cell)
    out = tpl
    for n in re.findall(r"\{([^{}]+)\}", tpl):
        o = (orig.get(n) or [""]).pop(0) if orig.get(n) else ""
        # ★'개발자도 예상 못한'의 개발자는 제품 말이 아니라 권위어 — 제품 이름으로 바꾸면
        #   '가스레인지 틈새도 예상 못한'이 된다(09-19 실측). 권위어는 원문 그대로 둔다.
        v = o if o.strip() in AUTH else ((vals or {}).get(n) or "")
        if not v:
            return new_text
        out = out.replace("{%s}" % n, v, 1)
    return out


def material(srcs):
    return "\n\n".join((s.get("full_text_ko") or s.get("full_text") or "")[:700] + "\n장면: " +
                       " / ".join((g.get("scene_desc") or "") for g in (s.get("segments") or [])[:12]) for s in srcs[:4])


def _hook(hit):
    return next((c for c in hit["cells"] if c.get("original") and c["role"] == "훅" and not c.get("why_bad")), None)


def transpose(hit, mat):
    from shopping_shorts import script_generate as sg
    cells = [c for c in hit["cells"] if c.get("original")]
    tpl = "\n".join("[%s] %s" % (c["role"], dedup(c["original"])) for c in cells)
    hook = _hook(hit)
    loop = bool(cells) and bool(LOOP_END.search(dedup(cells[-1]["original"]).rstrip(" .!?")) and not re.search(r"[.!?요다]\s*$", cells[-1]["original"]))
    loop_rule = ("- ★반복 재생 기법: 히트 대본의 마지막 칸은 문장을 끝맺지 않고 끊겨 첫 문장으로 이어진다. "
                 "새 대본의 마지막 칸도 **똑같이 끊어서** 첫 문장(훅)으로 이어지게 하라.\n") if loop else ""
    hook_rule = ("- ★훅(첫 칸)은 이 틀의 글자를 **한 글자도 바꾸지 말고** {}빈칸만 바꿔라: %s\n" % hook["template"]) if hook else ""
    p = f"""아래 [히트 대본]은 조회수 {hit['views']:,}회가 나온 쇼핑 숏폼이다. 이걸 틀로 삼아 [새 제품]의 대본을 써라.

규칙
{hook_rule}{loop_rule}- 칸 수와 순서를 똑같이. 칸 이름은 [히트 대본]의 한글 이름 그대로. 칸마다 히트 대본의 **말투·어미·연결어·문장 길이**를 최대한 그대로 살려라.
- 제품 이야기(제품 이름·효능·동작·불편·숫자)는 **전부 [새 제품] 재료에 있는 것으로만** 바꿔라. 히트 대본의 원래 제품 이야기는 한 조각도 남기지 마라.
- 인물·장소·반응 같은 이야기 장치는 새 제품에 자연스럽게 맞게 바꿔도 된다. 단, 대본 전체에서 인물은 한 사람으로 이어져야 한다.
- 재료에 없는 숫자·출처·수상·판매량은 쓰지 마라. 같은 문장을 두 번 쓰지 마라.
- hook_values = 훅 빈칸마다 넣은 값.

[히트 대본]
{tpl}

[새 제품 재료]
{mat}"""
    out = sg._call_json(p, SCHEMA) or {}
    new = out.get("cells") or []
    if hook and new:
        vals = {(v.get("slot") or "").strip("{} "): v.get("value") or "" for v in out.get("hook_values") or []}
        new[0]["text"] = hook_exact(hook, new[0]["text"], vals)
    for c in new:
        c["text"] = dedup(c["text"])
    return new


def checks(hit, new, mat):
    out = []
    if [c["role"] for c in new] != [c["role"] for c in hit["cells"] if c.get("original")]:
        out.append("칸 순서 다름")
    txt = " ".join(c["text"] for c in new)
    nums = [n for n in re.findall(r"\d+(?:[.,]\d+)?", txt) if n not in mat]
    if nums:
        out.append("재료에 없는 숫자 %s" % nums)
    leak = sorted({v["value"] for c in hit["cells"] if c["role"] != "훅" for v in (c.get("values") or [])
                   if (v.get("slot") or "").strip("{} ") not in STORY_WORDS and v["value"] not in AUTH and len(v.get("value") or "") >= 3
                   and v["value"] in txt and v["value"] not in mat})
    if leak:
        out.append("원래 제품 말 새어나옴 %s" % leak)
    if any(DUP.search(c["text"]) for c in new):
        out.append("같은 말 반복")
    hook = _hook(hit)
    if hook and new and not all(b in re.sub(r"\s", "", new[0]["text"]) for b in _bones(hook["template"])):
        out.append("훅 글자 바뀜")
    return out


def main():
    from shopping_shorts.store import Store
    from shopping_shorts import backbone_assemble as ba
    tpl, dst, hits, jobs = sys.argv[1], sys.argv[2], sys.argv[3].split(","), sys.argv[4:]
    T = {x["id"]: x for x in json.load(open(tpl, encoding="utf-8"))}
    st = Store("/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db")
    res = []
    for jid in jobs:
        srcs = ba.sources_from_extract((st.get_mix_job(jid) or {}).get("extract") or {})
        mat = material(srcs)
        prod = next((s.get("product") for s in srcs if s.get("product")), "")
        for hid in hits:
            hit = T[hid]
            new = transpose(hit, mat)
            res.append({"job": jid, "product": prod, "hit": hid, "hit_views": hit["views"], "hit_user": hit.get("user"),
                        "hit_cells": [{"role": c["role"], "text": dedup(c["original"])} for c in hit["cells"] if c.get("original")],
                        "cells": new, "flags": checks(hit, new, mat)})
            print(jid, hid, len(new), res[-1]["flags"], flush=True)
    json.dump(res, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
