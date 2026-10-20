"""두유노홈디노 지침서(../두유노홈디노_지침서.html) 시험 — 스타일 A 체험형·B 정보형 × 소재 2(밀착랩·유리 페인트), 스타일마다 버텍스 1회(시안 2).
정보형은 자료조사 사실(R*)을 근거에 더한다(2026-10-20 웹 검색). 결과: out/G_<A|B>.json
사용: py gen_hdn_guide.py [--styles A,B]"""
import argparse, json, os, re

import ab_common as C

HERE = os.path.dirname(os.path.abspath(__file__))
GUIDE = os.path.join(HERE, "..", "두유노홈디노_지침서.html")

RESEARCH = {
    "wrap": [
        {"id": "R1", "text": "같은 종류의 대표 제품(Glad Press'n Seal)은 손으로 누르는 압력에 반응하는 접착 기술(Griptex)이라 랩끼리, 그리고 플라스틱·종이·나무·금속·유리 같은 마른 표면에 붙는다(제품 소개 페이지).",
         "src": "kroger.com 제품 페이지 · packworld.com"},
        {"id": "R2", "text": "그 접착 기술은 Glad(Clorox)와 P&G의 합작에서 나왔고, P&G가 '랩이 잘 안 붙고 풀리는 문제'를 풀려고 개발했다는 업계 기사가 있다. 포장에 특허 번호 7개가 적혀 있었다(packworld). 출시 연도는 확인 못 함.",
         "src": "packworld.com/flexibles/article/13337962"},
        {"id": "R3", "text": "주의: 우리 소재 영상의 랩이 바로 그 제품인지는 확인되지 않았다 — '이런 압착 랩의 원조 기술' 식으로만 쓰고, 소재 제품을 그 회사가 만들었다고 단정하지 마라.", "src": "-"},
    ],
    "glasspaint": [
        {"id": "R1", "text": "젖빛(프로스트) 유리는 표면을 거칠게 만들어 빛이 지나가며 흩어지게 한다 — 그래서 방이 어두워지지 않고 시선만 가려진다(창문 프로스트 가이드).", "src": "engineerfix.com"},
        {"id": "R2", "text": "해외 생활 매체가 'People Are Losing It Over This Frosted Window Hack'(사람들이 이 젖빛 창문 꿀팁에 난리)라는 기사로 집 창문을 뿌옇게 만드는 방법이 화제라고 다뤘다.", "src": "hunker.com/13777599"},
        {"id": "R3", "text": "세입자에게는 영구 시공이 아닌 방법이 좋다는 안내가 많다(해외 가이드). 스프레이형은 용제로 지우는 제품도 있어 지우는 방법은 제품마다 다르다.", "src": "hunker.com · abeautifulmess.com"},
    ],
}


def guide_text():
    h = open(GUIDE, encoding="utf-8").read()
    h = re.sub(r"<style.*?</style>", "", h, flags=re.S)
    h = re.sub(r"<(br|/tr|/li|/h[1-3]|/p|/div)>", "\n", h)
    h = re.sub(r"</t[dh]>", " | ", h)
    t = re.sub(r"<[^>]+>", "", h)
    t = re.sub(r"&gt;", ">", t)
    return re.sub(r"\n\s*\n+", "\n", t)


def section(t, style):
    common = t[t.index("0. 공통"):t.index("A\n체험형") if "A\n체험형" in t else t.index("체험형 —")]
    a0 = t.index("체험형 —")
    b0 = t.index("정보형 —")
    c0 = t.index("검수 — 시안마다")
    body = t[a0:b0] if style == "A" else t[b0:c0]
    return common + "\n" + body + "\n" + t[c0:]


SCHEMA = {"type": "object", "properties": {"drafts": {"type": "array", "items": {"type": "object", "properties": {
    "product": {"type": "string"}, "mold": {"type": "string"}, "title": {"type": "string"},
    "lines": {"type": "array", "items": {"type": "object", "properties": {"block": {"type": "string"}, "text": {"type": "string"},
                                                                       "facts": {"type": "array", "items": {"type": "string"}}},
                                         "required": ["block", "text", "facts"]}},
    "check": {"type": "string"}}, "required": ["product", "mold", "lines", "check"]}}}, "required": ["drafts"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--styles", default="A,B")
    a = ap.parse_args()
    g = guide_text()
    inputs = {k: json.load(open(os.path.join(HERE, "inputs", k + ".json"), encoding="utf-8")) for k in ("wrap", "glasspaint")}
    for st in a.styles.split(","):
        prod = []
        for k, inp in inputs.items():
            facts = "\n".join("[%s] %s" % (f["id"], f["text"]) for f in inp["facts"])
            if st == "B":
                facts += "\n[자료조사]\n" + "\n".join("[%s] %s" % (r["id"], r["text"]) for r in RESEARCH[k])
            prod.append("● 소재 %s — %s\n%s\n[없는 장면 — 효능으로 쓰지 마라] %s" % (k, inp["product"], facts, " / ".join(inp["missing"])))
        prompt = ("아래 [두유노홈디노 대본 지침서]의 0.공통과 스타일 %s 부분이 이번 일의 지침 전부다. 지침서 순서(재료 확보 → 첫 줄 틀 사전에서 틀 고르기 → 블록 배치 → 검수)대로 "
                  "**소재마다 대본 1편씩, 모두 2편**을 써라. 두 편은 서로 다른 첫 줄 틀(번호)을 쓴다. ✗ 표시 틀은 쓰지 마라.\n"
                  "- 사실(효능·수치·회사·사건)은 근거 번호가 있는 것만, 줄마다 facts 에 번호. 인물·사건·감상·반응은 지어내도 된다(체험담 창작 허용). 효과 과장은 들은 얘기(~대요·~하더라고요)로.\n"
                  "- 제품 이름(상표)은 말하지 않는다 — '이거'·제품군 낱말로. 원본 대본 문장을 그대로 베끼지 말고 틀만 쓴다.\n"
                  "- ★길이: 체험형(A) 공백 빼고 140~190자 · 정보형(B) 180~230자, 7~9줄. 등장 비율 낮은 블록(불편·조언자·동작)은 합치거나 뺀다. 넘으면 다시 써라.\n"
                  "- ★지침서의 원본 예문(code 안 문장·'단체로 소리 질렀다는'·'정리업체 알바하는 친구'·'집주인이랑 싸울 뻔했어요' 등)은 **구조만** 본뜬다 — 원문 낱말 8자 이상 그대로 쓰면 실격. 꾸밈말·집단·사건은 이 소재에 맞게 새로 만든다.\n"
                  "- ★화자 하나: 첫 줄 사건의 주인공(나·친구·가족)이 끝까지 같은 사람이다. 첫 줄이 '나'의 일이면 본문도 '나'의 일.\n"
                  "- ★자료조사 주의(R3): 대표 제품 정보(회사·특허 수)를 소재 제품의 것처럼 쓰지 마라 — '이런 랩에 들어간 압력 접착 원리'처럼 종류의 이야기로.\n"
                  "- ★근거 없는 효과는 들은 얘기로만(~대요). 숫자는 근거에 있는 것만(지어낸 '1초 만에'·'30초' 금지). 사회 반응(품절대란·난리)은 한 편 한 번.\n"
                  "- lines 의 block 에 지침서 블록 이름(B1 훅 …), mold 에 첫 줄 틀 번호, check 에 검수 결과 한 줄(길이·베끼기·화자 포함).\n\n"
                  "[두유노홈디노 대본 지침서]\n%s\n\n[소재]\n%s") % (st, section(g, st), "\n\n".join(prod))
        r = C.vertex_json(prompt, SCHEMA, tag="hdn_guide:%s" % st)
        r["prompt"] = prompt
        r["research"] = RESEARCH if st == "B" else {}
        json.dump(r, open(os.path.join(HERE, "out", "G2_%s.json" % st), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        for d in r.get("drafts") or []:
            print("\n== 스타일 %s · %s · 틀 %s" % (st, d["product"], d["mold"]))
            for l in d["lines"]:
                print("  %-8s %s %s" % (l["block"][:8], l["text"], l["facts"] or ""))
            print("  검수:", d["check"])
    print("\n버텍스 %d회" % len(C.CALLS))


if __name__ == "__main__":
    main()
