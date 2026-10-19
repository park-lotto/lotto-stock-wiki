"""2차 판 B2 대본 뽑기 — ../cards_v2/*.json(13개) × 소재 2 × 시안 2. 같은 버텍스 모델·같은 입력. A 는 1차 결과(out/A_*)를 재사용.
사용: py ab_run_v2.py [--ids jungche,oyong,52,...] [--src glasspaint,wrap] [--force]
결과: out/B2_<id>_<src>.json"""
import argparse, glob, json, os

import ab_common as C
import ab_run as R

V2 = os.path.join(C.HERE, "..", "cards_v2")
CARDS = {"jungche": "정체숨김", "oyong": "오용활용법", "60": "60_", "66": "66_", "52": "52_", "53": "53_", "54": "54_", "58": "58_", "59": "59_",
         "61": "61_", "62": "62_", "even": "이븐쇼핑", "hdn": "두유노홈디노"}
A_OF = {"jungche": "55", "oyong": "56"}          # 통합 스타일의 A 비교 대상(라이브에서 같은 프롬프트였던 묶음 대표)

ORDER_V2 = [
    ("★공통 — 첫 줄 공식(지키지 않으면 다시 쓴다)", ["first_line"]),
    ("★공통 — 사실 지어냄은 0, 분위기 과장은 세게", ["fact_vs_mood", "banned_words"]),
    ("역할과 핵심 원리", ["name", "platform", "head", "role", "principles", "material_note"]),
    ("1단계 — 재료 확보(쓰기 전에 채운다)", ["materials"]),
    ("2단계 — 제목(첫 줄) 먼저 확정: 틀 사전에서 고르고 슬롯을 이 제품 말로 채운다", ["title_rules", "title_molds", "title_slots", "title_slot_words", "slot_fill"]),
    ("3단계 — 후킹 유형(시안마다 다른 유형)", ["hook_types", "bodies", "rotation"]),
    ("4단계 — 칸 배치(이 순서대로 전부)", ["slots", "slots_corrected", "story_rule", "points", "line_rule"]),
    ("사회적 증거 가공 장치", ["social_proof", "social_proof_order", "social_order"]),
    ("5단계 — 연결(브릿지)", ["bridges"]),
    ("6단계 — 말투·표기", ["tone", "cta", "cta_rule"]),
    ("7단계 — 길이", ["length"]),
    ("8단계 — 마무리", ["landing"]),
    ("9단계 — 시안 2개와 비교", ["drafts"]),
    ("10단계 — 검수(지키지 않으면 다시 쓴다)", ["checks", "forbid", "forbidden", "flags"]),
    ("참고 대본 — 줄별 뼈대([글자 수] …끝말)만 실었다. 호흡·끝말만 본뜬다", ["refs", "copy_rule"]),
]
SKIP = R.CARD_SKIP | {"merged_from", "v2_notes", "variant_of", "variant_notes"}


def card_prompt(card):
    used, parts = set(), []
    for title, keys in ORDER_V2:
        body = []
        for k in keys:
            if k in card and card[k] not in (None, "", [], {}):
                used.add(k)
                v = card[k]
                body.append("%s: %s" % (k, v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, indent=1)))
        if body:
            parts.append("■ %s\n%s" % (title, "\n".join(body)))
    rest = [k for k in card if k not in used and k not in SKIP]
    if rest:
        parts.append("■ 기타\n" + "\n".join("%s: %s" % (k, json.dumps(card[k], ensure_ascii=False)) for k in rest))
    return "\n\n".join(parts)


def card_file(cid):
    return sorted(glob.glob(os.path.join(V2, CARDS[cid] + "*.json")))[0]


def run_B2(cid, inp):
    cp = card_file(cid)
    card = card_prompt(json.load(open(cp, encoding="utf-8")))
    facts = "\n".join("[%s] %s" % (f["id"], f["text"]) for f in inp["facts"])
    prompt = ("아래 [스타일 설명서]가 이번 일의 지침 전부다. 맨 앞 ★공통 두 절(첫 줄 공식 · 사실 지어냄 vs 분위기 과장)을 먼저 지키고, "
              "설명서의 작업 순서(재료 확보 → 제목 확정 → 후킹 유형 → 칸 배치 → 연결 → 표기 → 길이 → 마무리 → 시안 비교 → 검수)대로 상품 하나로 대본 **시안 2개**를 써라. "
              "두 시안은 서로 다른 후킹 유형(몸통이 있으면 몸통도 다르게)을 쓰고 첫 줄이 확연히 달라야 한다.\n\n"
              "[스타일 설명서]\n%s\n\n[상품] %s\n[재료 종류] %s\n"
              "[쓸 수 있는 근거 — 줄마다 facts 에 번호를 적는다. 창작·연결 줄은 빈 목록]\n%s\n"
              "[장면 목록 — 묶음별 조각 번호(길이): 화면 설명. 제품이 무엇을 하는지는 이 화면 설명과 근거에서만 읽어라. 줄마다 ids 에 깔릴 조각 번호]\n%s\n"
              "[없는 장면 — 이 내용을 효능·사실로 쓰지 마라] %s\n"
              "출력: drafts 2개. 각 시안의 lines 는 설명서 칸 순서대로 slot 에 칸 이름, text 에 한 줄. "
              "신호어가 코드로 붙는 칸이라도 이번엔 신호어까지 포함해 완성 문장으로 써라. check 에 자가 검수 결과 한 줄(첫 줄 두 덩어리·사실 지어냄 0·7자 겹침 0), compare 에 두 시안 비교와 추천 한 줄.")
    prompt = prompt % (card, inp["product"], inp["kind"], facts, R.groups_txt(inp), " / ".join(inp["missing"]))
    n0 = len(C.CALLS)
    d = C.vertex_json(prompt, R.B_SCHEMA, tag="B2:%s" % cid)
    return {"card": os.path.basename(cp), "drafts": d.get("drafts") or [], "compare": d.get("compare") or "",
            "prompt": prompt, "calls": len(C.CALLS) - n0, "a_of": A_OF.get(cid, cid)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default=",".join(CARDS))
    ap.add_argument("--src", default="glasspaint,wrap")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    os.makedirs(R.OUT, exist_ok=True)
    for src in a.src.split(","):
        inp = R.load_input(src)
        for cid in a.ids.split(","):
            dst = os.path.join(R.OUT, "B2_%s_%s.json" % (cid, src))
            if os.path.exists(dst) and not a.force:
                print("건너뜀(있음)", dst); continue
            r = run_B2(cid, inp)
            r.update(side="B2", id=cid, src=src)
            json.dump(r, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            d0 = (r.get("drafts") or [{}])[0]
            print("B2 %s %s 시안 %d · 첫 줄: %s" % (cid, src, len(r["drafts"]), (d0.get("title") or "")[:50]), flush=True)
    import time
    json.dump(C.CALLS, open(os.path.join(R.OUT, "_calls_B2_%d.json" % int(time.time())), "w", encoding="utf-8"), ensure_ascii=False)
    print("버텍스 호출 %d (실패 %d)" % (len(C.CALLS), sum(not c["ok"] for c in C.CALLS)))


if __name__ == "__main__":
    main()
