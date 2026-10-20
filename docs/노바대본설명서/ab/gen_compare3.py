"""정보형 원인 가르기 — 같은 소재(스크럽 대디)·같은 사실로 ①지금 방식(지침서 규칙) ②노바 방식(씨앗 히트작 + 홀린 요인 분석 + 참고 대본 전문 10편)
을 gemini-flash 로 1회씩. ③ Claude 는 버텍스 사용 한도가 없어(429) 세션의 Claude 가 같은 재료로 직접 쓴다(out/C3_claude.json).
사용: py gen_compare3.py → out/C3_now.json · out/C3_nova.json"""
import json, os

import ab_common as C
import gen_hdn_guide as G

HERE = os.path.dirname(os.path.abspath(__file__))
SLUG = os.path.join(HERE, "..", "..", "..", "out", "script_calcopy", "homedesignnote")

PRODUCT = "웃는 얼굴 모양 수세미(스크럽 대디)"
FACTS = [
    ("S1", "개발자 에런 크라우스는 차 광택용 연마 패드 회사를 하다가 2008년 3M에 회사를 팔았는데, 3M은 공장에 남아 있던 폴리머 폼은 가져가지 않았다(femfounded 사례 기사)."),
    ("S2", "2011년 그가 그 남은 폼으로 집 마당 가구를 닦아 보다가 생각보다 너무 잘 닦이는 걸 발견했다(같은 기사)."),
    ("S3", "찬물에서는 단단해져 묵은 때를 박박 닦고, 따뜻한 물에서는 말랑해져 살살 닦는 소재(FlexTexture)다(여러 매체 공통)."),
    ("S4", "2012년 10월 미국 투자 오디션 방송 샤크탱크에 나가 10만 달러에 지분 10%를 제시했는데, 투자자들끼리 입찰 경쟁이 붙어 로리 그라이너에게 20만 달러에 20%로 투자받았다."),
    ("S5", "방송 다음 날 홈쇼핑(QVC)에서 7분 만에 4만 2천 개가 팔렸다."),
    ("S6", "제품은 웃는 얼굴 모양이다(제품 사진)."),
]
SOURCES = ["https://femfounded.org/case-studies/scrub-daddy/", "https://www.onmanorama.com/food/features/2024/10/21/all-about-the-viral-scrub-daddy-cleaning-sponge.amp.html"]
SEED_ID_HINT = "선제개발자가 만들어서"      # 배수구 트랩 130만 — 같은 청소용품 · 개발자 발명 이야기
SCH = {"type": "object", "properties": {"analysis": {"type": "string"}, "lines": {"type": "array", "items": {"type": "object", "properties": {
    "text": {"type": "string"}, "facts": {"type": "array", "items": {"type": "string"}}}, "required": ["text", "facts"]}}},
    "required": ["analysis", "lines"]}


def load():
    tags = {}
    for l in open(os.path.join(SLUG, "tags.jsonl"), encoding="utf-8"):
        if l.strip():
            r = json.loads(l)
            tags[r["id"]] = r
    molds = json.load(open(os.path.join(SLUG, "hook_molds.json"), encoding="utf-8"))["map"]
    tr = json.load(open(os.path.join(SLUG, "transcripts.json"), encoding="utf-8"))
    return tags, molds, tr


def main():
    tags, molds, tr = load()
    facts = "\n".join("[%s] %s" % f for f in FACTS)
    rule = ("- 사실(회사·수치·사건·원리)은 [S*] 근거에 있는 것만, 줄마다 facts 에 번호. 반응·감상은 들은 얘기(~대요·~하더라고요)로.\n"
            "- 제품 상표(스크럽 대디)는 말하지 마라 — '이 수세미'로. 존댓말 전언체. 공백 빼고 180~230자, 7~9줄.\n")
    # ① 지금 방식
    g = G.section(G.guide_text(), "B")
    p1 = ("아래 [두유노홈디노 대본 지침서] 0.공통과 스타일 B 정보형이 지침 전부다. 지침서 순서대로 대본 1편을 써라. analysis 에는 고른 첫 줄 틀과 이유.\n%s\n"
          "[지침서]\n%s\n\n[소재] %s\n[근거]\n%s") % (rule, g, PRODUCT, facts)
    r1 = C.vertex_json(p1, SCH, tag="C3:now")
    # ② 노바 방식 — 씨앗 + 홀린 요인 + 참고 대본 전문
    info = [r for r in tags.values() if r.get("usable") and str(molds.get(r["id"], "")).startswith("I") and r["views"] >= 100000]
    info.sort(key=lambda r: -r["views"])
    seed = next(r for r in info if r["lines"][0]["text"].startswith(SEED_ID_HINT))
    refs = [r for r in info if r["id"] != seed["id"]][:10]
    full = lambda r: tr[r["id"]]["text"]
    p2 = ("너는 생활용품 쇼츠 채널 '두유노홈디노'의 대본 작가다.\n"
          "1단계: [씨앗 대본](조회 %d만)이 사람들을 홀린 요인을 분석하라 — 어떤 궁금증으로 붙잡고, 어떤 순서로 고충→해결→놀람을 쌓고, 무엇으로 믿게 만들었나. analysis 에 적는다.\n"
          "2단계: 그 홀린 요인과 [참고 대본]들의 흐름을 그대로 옮겨, [소재]로 대본 1편을 써라. 참고 대본의 흐름이 정답지이고 소재는 채워 넣는 재료다. "
          "단 참고 대본 문장을 8자 이상 그대로 베끼지 마라 — 결과 말맛만.\n%s\n"
          "[씨앗 대본]\n%s\n\n[참고 대본 — 이 채널 정보형 히트작 전문]\n%s\n\n[소재] %s\n[근거]\n%s") % (
        seed["views"] // 10000, rule, full(seed), "\n\n".join("(%d만) %s" % (r["views"] // 10000, full(r)) for r in refs), PRODUCT, facts)
    r2 = C.vertex_json(p2, SCH, tag="C3:nova")
    for name, r, p in (("now", r1, p1), ("nova", r2, p2)):
        r["prompt"] = p
        r["facts"] = FACTS
        r["sources"] = SOURCES
        json.dump(r, open(os.path.join(HERE, "out", "C3_%s.json" % name), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("\n== %s\n분석: %s" % (name, r.get("analysis", "")[:400]))
        for l in r.get("lines") or []:
            print("  ", l["text"], l["facts"] or "")
    print("\n씨앗:", seed["lines"][0]["text"], "| 참고:", [r["lines"][0]["text"][:20] for r in refs])
    print("버텍스 %d회" % len(C.CALLS))


if __name__ == "__main__":
    main()
