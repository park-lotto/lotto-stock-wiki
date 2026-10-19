"""스타일별 A(지금 라이브 프롬프트) / B(새 카드) 대본 뽑기 — 같은 소재·같은 모델(버텍스 gemini-3.6-flash).

A = 고객 기본 경로 스토리보드 작가를 숏템메이커 코드 그대로 부른다: storyboard._board(fam, …)
    = _writer_head(WRITER_BRIEF + YT/IG_BRIEF + winners_block + parts_block) + P3(칸·문장 틀·말투·장면 목록) → P4 사실 검수 → 신호어 보정.
    스타일 행은 서버 spine(승인) 사본. 칼카피 2개(even = 이븐쇼핑, hdn = 두유노홈디노)는 칼카피 엔진 run_frame(오늘 방식).
B = ../cards/<id>_*.md (카드_양식.md 형식) 설명서 + 같은 근거·장면 목록 → 시안 2개(서로 다른 후킹 유형) 한 번에.

사용: py ab_run.py --side A|B [--ids 55,56,even,hdn] [--src glasspaint,wrap]
결과: out/<side>_<id>_<src>.json  {side,id,src,family_ids,drafts:[{hook_type,title,lines:[{slot,text,ids,facts}]}],prompt_chars,calls}"""
import argparse, glob, json, os, sqlite3, sys
from pathlib import Path

import ab_common as C

STYLES = [52, 53, 54, 55, 56, 58, 59, 60, 61, 62, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, "even", "hdn"]
OUT = os.path.join(C.HERE, "out")


def load_input(src):
    return json.load(open(os.path.join(C.HERE, "inputs", src + ".json"), encoding="utf-8"))


def groups_txt(inp):
    """storyboard.make_boards 의 장면 목록 글과 같은 꼴(태그 없음)."""
    segs, texts = inp["segs"], inp["texts"]
    return "\n".join("  %s:\n%s" % (g["name"], "\n".join("    - %s(%.1f초): %s" % (c, segs[c], texts[c].strip()[:110]) for c in g["ids"]))
                     for g in inp["groups"])


# ── A: 라이브 스토리보드 ──────────────────────────────────────────────
def families():
    from shopping_shorts import config, storyboard
    path = C.server_db()
    config.DB_PATH = Path(path)          # _writer_head 가 부를 때 읽는 DB(전역) — 서버 사본
    db = sqlite3.connect(path)
    return {f["ids"][0]: f for _n, f, _t in storyboard._families(db)}


def family_of(fams, sid):
    return next(f for f in fams.values() if sid in f["ids"])


def run_A_spine(sid, inp, fams):
    from shopping_shorts import storyboard
    fam = family_of(fams, sid)
    r1 = {"kind": inp["kind"], "missing": inp["missing"], "groups": inp["groups"], "tag_of": {}}
    n0, p0 = len(C.CALLS), len(C.PROMPTS)
    b = storyboard._board(fam, "", r1, groups_txt(inp), [], inp["segs"], inp["texts"], roles_pick="", extra=[], key="ab:%s:%s" % (inp["key"], sid))
    lines = [{"slot": s.get("slot"), "text": s.get("line") or "", "ids": s.get("ids") or [], "need": s.get("need") or "",
              "weak": s.get("weak") or "", "fixed_from": s.get("line_before") or ""} for s in b.get("slots") or []]
    return {"family_ids": fam["ids"], "family_names": fam["names"], "first_line_style": b.get("first_line_style"),
            "drafts": [{"hook_type": "(스타일 고정)", "title": lines[0]["text"] if lines else "", "lines": lines}],
            "p4_fixed": b.get("fixed"), "left_flags": b.get("left_flags"),
            "prompt": C.PROMPTS[p0] if len(C.PROMPTS) > p0 else "", "calls": len(C.CALLS) - n0}


def run_A_calcopy(slug, inp):
    sys.path.insert(0, C.CALCOPY)
    from tools.calcopy.engine import script_engine as SE, topic_find as TF

    def vfn(prompt, tag):
        d = C.vertex_json(prompt, None, tag="calcopy:" + tag)
        if not d:
            return None, "vertex 실패"
        d = d if isinstance(d, dict) else {"lines": d}
        d["_model"] = "vertex:" + C.MODEL
        return d, None
    facts = {f["id"]: {"text": f["text"], "url": f["url"]} for f in inp["facts"]}
    n0 = len(C.CALLS)
    od = Path(OUT) / ("A_%s_%s_engine" % ({"evenshopping": "even", "homedesignnote": "hdn"}[slug], inp["key"]))
    S = SE.run_frame(slug, {"name": inp["product"]}, facts, od, llm=TF.LLM(fn=vfn, budget=8))
    lines = [{"slot": l.get("fn") or l.get("node"), "text": l.get("text") or "", "facts": l.get("facts") or []} for l in S["final"]["lines"]]
    return {"family_ids": [slug], "drafts": [{"hook_type": "(엔진)", "title": lines[0]["text"] if lines else "", "lines": lines}],
            "engine_status": S.get("status"), "prompt": S.get("prompt") or "", "calls": len(C.CALLS) - n0}


# ── B: 새 카드 ────────────────────────────────────────────────────────
B_SCHEMA = {"type": "object", "properties": {"drafts": {"type": "array", "items": {"type": "object", "properties": {
    "hook_type": {"type": "string"}, "title_mold": {"type": "string"}, "title": {"type": "string"},
    "lines": {"type": "array", "items": {"type": "object", "properties": {
        "slot": {"type": "string"}, "text": {"type": "string"},
        "ids": {"type": "array", "items": {"type": "string"}}, "facts": {"type": "array", "items": {"type": "string"}}},
        "required": ["slot", "text", "ids", "facts"]}},
    "check": {"type": "string"}}, "required": ["hook_type", "title", "lines"]}},
    "compare": {"type": "string"}}, "required": ["drafts"]}


def card_path(sid):
    pat = {"even": "calcopy_*", "hdn": "hdn_*"}.get(sid, "%s_*" % sid)
    hits = sorted(glob.glob(os.path.join(C.HERE, "..", "cards", pat + ".json")))
    return hits[0] if hits else None


# 카드 json → 노바 프롬프트 순서(역할·원칙 → 재료 → 제목 → 후킹 유형 → 칸 → 가공 장치 → 연결 → 말투 → 길이 → 시안 → 검수 → 참고 대본)
CARD_ORDER = [
    ("역할과 핵심 원리", ["name", "platform", "head", "role", "principles"]),
    ("1단계 — 재료 확보(쓰기 전에 채운다)", ["materials"]),
    ("2단계 — 제목(첫 줄) 먼저 확정: 틀 사전에서 고르고 슬롯만 채운다", ["title_rules", "title_molds", "title_slots", "title_slot_words", "slot_fill"]),
    ("3단계 — 후킹 유형(시안마다 다른 유형)", ["hook_types", "rotation"]),
    ("4단계 — 칸 배치(이 순서대로 전부)", ["slots", "slots_corrected", "story_rule", "points"]),
    ("사회적 증거 가공 장치(근거 필요 표시를 지켜라)", ["social_proof", "social_proof_order", "social_order"]),
    ("5단계 — 연결(브릿지)", ["bridges"]),
    ("6단계 — 말투·표기", ["tone", "cta"]),
    ("7단계 — 길이", ["length"]),
    ("8단계 — 시안 2개와 비교", ["drafts"]),
    ("9단계 — 검수(지키지 않으면 다시 쓴다)", ["checks", "forbid", "forbidden", "flags"]),
    ("변형 메모", ["variant_of", "variant_notes"]),
    ("참고 대본 — 구조·호흡만 본뜬다. 공백 뺀 7자 이상 같은 구절 금지", ["refs"]),
]
CARD_SKIP = {"id", "source", "live", "live_usage", "measured_from", "fixed_vs_live", "fixed", "engine"}


def card_prompt(card):
    used, parts = set(), []
    for title, keys in CARD_ORDER:
        body = []
        for k in keys:
            if k in card and card[k] not in (None, "", [], {}):
                used.add(k)
                v = card[k]
                body.append("%s: %s" % (k, v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, indent=1)))
        if body:
            parts.append("■ %s\n%s" % (title, "\n".join(body)))
    rest = [k for k in card if k not in used and k not in CARD_SKIP]
    if rest:
        parts.append("■ 기타\n" + "\n".join("%s: %s" % (k, json.dumps(card[k], ensure_ascii=False)) for k in rest))
    return "\n\n".join(parts)


def run_B(sid, inp):
    cp = card_path(sid)
    if not cp:
        return None
    card = card_prompt(json.load(open(cp, encoding="utf-8")))
    facts = "\n".join("[%s] %s" % (f["id"], f["text"]) for f in inp["facts"])
    prompt = ("아래 [스타일 설명서]가 이번 일의 지침 전부다. 설명서의 작업 순서(재료 확보 → 제목 확정 → 후킹 유형 → 칸 배치 → 연결 → 표기 → 길이 → 시안 비교 → 검수)대로 "
              "상품 하나로 대본 **시안 2개**를 써라. 두 시안은 설명서 4절의 **서로 다른 후킹 유형**을 쓰고 첫 줄이 확연히 달라야 한다.\n\n"
              "[스타일 설명서]\n%s\n\n[상품] %s\n[재료 종류] %s\n"
              "[쓸 수 있는 근거 — 줄마다 facts 에 번호를 적는다. 창작·연결 줄은 빈 목록]\n%s\n"
              "[장면 목록 — 묶음별 조각 번호(길이): 화면 설명. 제품이 무엇을 하는지는 이 화면 설명과 근거에서만 읽어라. 줄마다 ids 에 깔릴 조각 번호]\n%s\n"
              "[없는 장면 — 이 내용을 효능·사실로 쓰지 마라] %s\n"
              "출력: drafts 2개. 각 시안의 lines 는 설명서 5절 칸 순서대로 slot 에 칸 이름, text 에 한 줄. "
              "신호어가 코드로 붙는 칸이라도 이번엔 신호어까지 포함해 완성 문장으로 써라. check 에 자가 검수 결과 한 줄, compare 에 두 시안 비교와 추천 한 줄.")
    prompt = prompt % (card, inp["product"], inp["kind"], facts, groups_txt(inp), " / ".join(inp["missing"]))
    n0 = len(C.CALLS)
    d = C.vertex_json(prompt, B_SCHEMA, tag="B:%s" % sid)
    return {"card": os.path.basename(cp), "drafts": d.get("drafts") or [], "compare": d.get("compare") or "",
            "prompt": prompt, "calls": len(C.CALLS) - n0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--side", required=True, choices=["A", "B"])
    ap.add_argument("--ids", default=",".join(map(str, STYLES)))
    ap.add_argument("--src", default="glasspaint,wrap")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    ids = [int(x) if x.isdigit() else x for x in a.ids.split(",") if x]
    C.patch_shortem()
    fams = families() if a.side == "A" and any(isinstance(i, int) for i in ids) else {}
    done_family = {}
    for src in a.src.split(","):
        inp = load_input(src)
        for sid in ids:
            dst = os.path.join(OUT, "%s_%s_%s.json" % (a.side, sid, src))
            if os.path.exists(dst) and not a.force:
                print("건너뜀(있음)", dst); continue
            if a.side == "A":
                if sid in ("even", "hdn"):
                    r = run_A_calcopy({"even": "evenshopping", "hdn": "homedesignnote"}[sid], inp)
                else:
                    fam = family_of(fams, sid)
                    fk = (fam["ids"][0], src)
                    if fk in done_family:      # 스토리보드는 칸 구조가 같은 스파인을 한 묶음으로 쓴다(_families) — 같은 프롬프트라 다시 뽑지 않는다
                        r = dict(done_family[fk], same_as=fam["ids"][0], calls=0)
                    else:
                        r = run_A_spine(sid, inp, fams)
                        done_family[fk] = r
            else:
                r = run_B(sid, inp)
                if r is None:
                    print("카드 없음:", sid); continue
            r.update(side=a.side, id=sid, src=src)
            json.dump(r, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            d0 = (r.get("drafts") or [{}])[0]
            print("%s %s %s  줄 %d · 호출 %d · 첫 줄: %s" % (a.side, sid, src, len(d0.get("lines") or []), r.get("calls", 0), (d0.get("title") or "")[:40]), flush=True)
    import time as _t; json.dump(C.CALLS, open(os.path.join(OUT, "_calls_%s_%d.json" % (a.side, int(_t.time()))), "w", encoding="utf-8"), ensure_ascii=False)
    print("버텍스 호출 %d (실패 %d)" % (len(C.CALLS), sum(not c["ok"] for c in C.CALLS)))


if __name__ == "__main__":
    main()
