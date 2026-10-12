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
        "role": {"type": "string"}, "text": {"type": "string"},
        "segs": {"type": "array", "items": {"type": "string"}}}, "required": ["role", "text", "segs"]}},
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


def _vid(s):
    """소스의 컷 번호 앞자리 — seg_id가 'lens_youtube_x-0'이면 'lens_youtube_x'.
    ★sources_from_extract의 video_id는 's2'처럼 소스 번호라 seg_id와 안 맞는다(09-19 실측)."""
    segs = s.get("segments") or []
    return str(segs[0].get("seg_id", "")).rsplit("-", 1)[0] if segs else (s.get("video_id") or "")


def seed_vid_of(srcs, backbone_main=None):
    """씨앗(원본) 소스의 video_id — 화면이 원본과 같아 보이지 않게 가리는 기준(09-18 '원본이랑 달라야')."""
    if backbone_main is not None:
        try:
            return _vid(srcs[int(backbone_main)])
        except Exception:      # noqa: BLE001
            pass
    ko = lambda t: sum(1 for c in t if "가" <= c <= "힣") / max(1, sum(1 for c in t if c.isalpha()))
    kor = [s for s in srcs if ko(s.get("full_text") or "") > 0.7]
    return (_vid(max(kor or srcs, key=lambda s: len(s.get("full_text") or ""))) if srcs else "")


def material_segs(srcs, per_src=18, seed_vid=""):
    """컷 번호가 붙은 재료. **서브를 먼저 적고** 원본은 (원본)으로 표시한다 — 모델이 목록 앞쪽을
    집는 성질 때문에 씨앗 컷만 골라 화면이 원본과 똑같아졌다(09-19 실측 문어인형 5/5줄)."""
    sub = [s for s in srcs if _vid(s) != seed_vid]
    out = []
    for s in (sub + [x for x in srcs if _vid(x) == seed_vid])[:5]:
        tag = "원본" if _vid(s) == seed_vid else "서브"
        for g in (s.get("segments") or [])[:per_src]:
            d = (g.get("scene_desc") or "").strip()
            if g.get("seg_id") and d:
                out.append("[%s] (%s) %s | 대사: %s" % (g["seg_id"], tag, d[:70], (g.get("text") or "")[:40]))
    return "\n".join(out)


def _hook(hit):
    return next((c for c in hit["cells"] if c.get("original") and c["role"] == "훅" and not c.get("why_bad")), None)


def seed_overlap(text, mat):
    """새 대본의 6글자 조각 중 재료(원본 대사)에 그대로 있는 비율(diff_from_seed와 같은 잣대)."""
    n = lambda t: re.sub(r"\s", "", t or "")
    M = {n(mat)[i:i + 6] for i in range(len(n(mat)) - 5)}
    t = n(text)
    g = [t[i:i + 6] for i in range(len(t) - 5)]
    return sum(x in M for x in g) / max(1, len(g))


def seed_cut_ratio(cells, seed_vid):
    ids = [x for c in cells for x in (c.get("segs") or [])]
    return (sum(1 for i in ids if str(i).rsplit("-", 1)[0] == seed_vid) / len(ids)) if ids else 0.0


def _stems(t):
    """어간 2글자 묶음 — 장면 설명과 대사를 맞대 볼 때 조사·어미를 버린다(인스타 매칭과 같은 방식)."""
    return {w[:2] for w in re.findall(r"[가-힣]{2,}", t or "")}


def prefer_sub(cells, srcs, seed_vid, keep=0.4):
    """모델이 고른 컷이 씨앗에 쏠리면(설명이 대사와 제일 닮아서) **같은 뜻의 서브 컷으로 바꾼다**.
    09-19 실측: 서브 컷 14개가 있는데도 모델이 씨앗 12컷만 골라 화면이 원본과 똑같았다.
    바꿀 서브 컷이 없으면 씨앗 컷을 그대로 둔다(빈 화면보다 낫다)."""
    pool = []
    for s in srcs:
        if _vid(s) == seed_vid:
            continue
        for g in (s.get("segments") or []):
            d = (g.get("scene_desc") or "").strip()
            if g.get("seg_id") and d:
                pool.append((g["seg_id"], _stems(d)))
    if not pool:
        return cells
    used = set()
    for c in cells:
        want = _stems(c.get("text"))
        segs = []
        for sid in (c.get("segs") or []):
            if str(sid).rsplit("-", 1)[0] != seed_vid:
                segs.append(sid)
                used.add(sid)
                continue
            cand = sorted(((len(want & st), sid2) for sid2, st in pool if sid2 not in used), reverse=True)
            if cand and cand[0][0] >= 1:
                segs.append(cand[0][1])
                used.add(cand[0][1])
            else:
                segs.append(sid)
        c["segs"] = segs
    return cells


def transpose(hit, mat, seg_list="", _retry=True):
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
- ★[새 제품 재료]의 대사 문장을 **베끼지 마라**. 재료에서는 사실(무엇이 어떻게 된다)만 가져오고, 문장은 [히트 대본]의 말투로 새로 써라.
  (원본 영상과 다른 영상이어야 한다 — 재료 문장이 6글자 넘게 그대로 이어지면 실패로 친다)
- hook_values = 훅 빈칸마다 넣은 값.

[히트 대본]
{tpl}

[새 제품 재료]
{mat}
""" + (("""
[화면 컷 목록] — 칸마다 그 칸 내용이 **실제로 보이는 컷** 번호를 segs에 1~3개(보여줄 순서대로). 목록에 없는 번호 금지.
훅은 가장 눈길 끄는 컷, 작동·심지어 칸은 그 동작이 보이는 컷.
★(서브) 컷을 먼저 쓴다. (원본) 컷은 그 장면이 서브에 없을 때만 — 화면이 원본 영상과 같아 보이면 안 된다.
""" + seg_list) if seg_list else "")
    out = sg._call_json(p, SCHEMA) or {}
    new = out.get("cells") or []
    if not new and _retry:            # 모델 혼잡으로 빈 응답 — 한 번 더
        out = sg._call_json(p, SCHEMA) or {}
        new = out.get("cells") or []
    if hook and new:
        vals = {(v.get("slot") or "").strip("{} "): v.get("value") or "" for v in out.get("hook_values") or []}
        new[0]["text"] = hook_exact(hook, new[0]["text"], vals)
    # ★씨앗 베끼기 막기(09-19 실측: 씨앗과 틀이 같은 유형이면 씨앗 대사 79% 복사) — 30% 넘으면 한 번 더
    body = " ".join(c.get("text") or "" for c in new[1:])
    if _retry and new and seed_overlap(body, mat) > 0.30:
        again = transpose(hit, mat, seg_list, _retry=False)
        if again and seed_overlap(" ".join(c.get("text") or "" for c in again[1:]), mat) < seed_overlap(body, mat):
            return again
    valid = set(re.findall(r"^\[([^\]]+)\]", seg_list, re.M))
    for c in new:
        c["text"] = dedup(c["text"])
        c["segs"] = [x for x in (c.get("segs") or []) if x in valid]
    return new


def transpose_job(hit, srcs, backbone_main=None):
    """한 번에: 재료 → 대본 옮기기 → 서브 컷 우선 교체. (cells, seed_vid)"""
    sv = seed_vid_of(srcs, backbone_main)
    cells = transpose(hit, material(srcs), material_segs(srcs, seed_vid=sv))
    return prefer_sub(cells, srcs, sv), sv


def checks(hit, new, mat, seed_vid=""):
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
    ov = seed_overlap(" ".join(c.get("text") or "" for c in new[1:]), mat)
    if ov > 0.30:
        out.append("원본 대사 베낌 %.0f%%" % (100 * ov))
    if any(not c.get("segs") for c in new) and any(c.get("segs") for c in new):
        out.append("컷 없는 칸 %d" % sum(1 for c in new if not c.get("segs")))
    if seed_vid:
        r = seed_cut_ratio(new, seed_vid)
        if r > 0.4:
            out.append("원본 컷 %.0f%%" % (100 * r))
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
        bm = (st.get_mix_job(jid) or {}).get("backbone_main")
        prod = next((s.get("product") for s in srcs if s.get("product")), "")
        for hid in hits:
            hit = T[hid]
            new, sv = transpose_job(hit, srcs, bm)
            res.append({"job": jid, "product": prod, "hit": hid, "hit_views": hit["views"], "hit_user": hit.get("user"),
                        "hit_cells": [{"role": c["role"], "text": dedup(c["original"])} for c in hit["cells"] if c.get("original")],
                        "seed_vid": sv, "cells": new, "flags": checks(hit, new, mat, sv)})
            print(jid, hid, len(new), res[-1]["flags"], flush=True)
    json.dump(res, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
