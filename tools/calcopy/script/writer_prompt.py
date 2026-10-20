"""지침서 → 버텍스 대본 작가 프롬프트 조립(숏템메이커가 부를 자리). 대본 칼카피 엔진의 결과(지침서·잘된 편)를 그대로 쓴다.
2026-10-20 사장님: "숏템 클로드형은 Claude 가 대본을 쓰고, 숏템메이커는 노바 지침서로 두유노 스타일을 입혀 버텍스가 써라."
시험에서 1등 결을 재현한 조합만 넣는다:
  - B 정보형: 지침서(0.공통 + B) + 씨앗 히트작 1편·홀린 요인 분석 + 정보형 잘된 편 전문 10편 (정보형_원인결과.html ⑤)
  - A 체험형: 지침서(0.공통 + A) 만 — 참고 대본 전문을 넣으면 사용 설명서처럼 무너졌다 (체험형_원인결과.html ②)
  - 소재 관문: 정보형은 근거에 만든 사람·계기·사건 사실이 2개 이상일 때만(아니면 A 로 보낸다)
  - platform='ig' 이면 마지막 줄 = 댓글 키워드 CTA(두유노 인스타판 실측: 체험형 잘된 편 29% · 경고명령 56%)
사용(파이썬): build(style, facts, product, platform='yt', n=2) → prompt 문자열 · SCHEMA"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GUIDE = os.path.join(ROOT, "docs", "노바대본설명서", "두유노홈디노_지침서.html")
SLUG_DIR = os.path.join(ROOT, "out", "script_calcopy", "homedesignnote")

SCHEMA = {"type": "object", "properties": {"drafts": {"type": "array", "items": {"type": "object", "properties": {
    "mold": {"type": "string"}, "analysis": {"type": "string"},
    "lines": {"type": "array", "items": {"type": "object", "properties": {"text": {"type": "string"}, "facts": {"type": "array", "items": {"type": "string"}}},
                                         "required": ["text", "facts"]}}, "check": {"type": "string"}},
    "required": ["mold", "lines", "check"]}}}, "required": ["drafts"]}
LEN = {"A": (140, 190), "B": (180, 230)}
STORY_KEYS = re.compile(r"개발|만든|만들|창업|회사|방송|출시|판매|팔렸|특허|투자|발명|계기|유래")


def guide_text():
    h = open(GUIDE, encoding="utf-8").read()
    h = re.sub(r"<style.*?</style>", "", h, flags=re.S)
    h = re.sub(r"<(br|/tr|/li|/h[1-3]|/p|/div)>", "\n", h)
    h = re.sub(r"</t[dh]>", " | ", h)
    t = re.sub(r"<[^>]+>", "", h).replace("&gt;", ">").replace("&amp;", "&")
    return re.sub(r"\n\s*\n+", "\n", t)


def section(style):
    t = guide_text()
    common = t[t.index("0. 공통"):t.index("체험형 —")]
    a0, b0, c0 = t.index("체험형 —"), t.index("정보형 —"), t.index("검수 — 시안마다")
    return common + "\n" + (t[a0:b0] if style == "A" else t[b0:c0]) + "\n" + t[c0:]


def gate(facts):
    """소재 관문 — 정보형으로 쓸 이야기(만든 사람·계기·사건)가 근거에 2개 이상 있나."""
    return sum(1 for _, txt in facts if STORY_KEYS.search(txt)) >= 2


def info_refs(n=10, seed_hint="선제개발자가 만들어서"):
    tags = {}
    for l in open(os.path.join(SLUG_DIR, "tags.jsonl"), encoding="utf-8"):
        if l.strip():
            r = json.loads(l)
            tags[r["id"]] = r
    molds = json.load(open(os.path.join(SLUG_DIR, "hook_molds.json"), encoding="utf-8"))["map"]
    tr = json.load(open(os.path.join(SLUG_DIR, "transcripts.json"), encoding="utf-8"))
    info = sorted((r for r in tags.values() if r.get("usable") and str(molds.get(r["id"], "")).startswith("I") and r["views"] >= 100000), key=lambda r: -r["views"])
    seed = next(r for r in info if r["lines"][0]["text"].startswith(seed_hint))
    refs = [r for r in info if r["id"] != seed["id"]][:n]
    return (seed["views"], tr[seed["id"]]["text"]), [(r["views"], tr[r["id"]]["text"]) for r in refs]


def build(style, facts, product, platform="yt", n=2, missing=()):
    """facts: [(id, text)]. 정보형인데 관문을 못 넘으면 ValueError — 호출 쪽이 A 로 보낸다."""
    if style == "B" and not gate(facts):
        raise ValueError("소재 관문: 정보형 이야기 사실 2개 미만 — 체험형(A)으로")
    lo, hi = LEN[style]
    cta = ("- 인스타판: **마지막 줄 = 댓글 키워드 CTA 한 줄**('{바라는 것} 하고 싶으시면 댓글에 {키워드} 남겨주세요' 꼴, 키워드는 2~3자 낱말). CTA 줄은 길이에서 뺀다. 본문 닫기(첫 줄 회수)는 CTA 바로 앞 줄.\n"
           if platform == "ig" else "- 유튜브판: CTA 없음.\n")
    rule = ("- 사실(효능·수치·회사·사건)은 근거 번호가 있는 것만, 줄마다 facts 에 번호. 인물·사건·반응·감상은 지어내도 된다. 근거 없는 효과는 들은 얘기(~대요)로.\n"
            "- 상표 금지 — '이거'·제품군 낱말로. 존댓말 1인칭 체험·전언. 공백 빼고 %d~%d자, 7~9줄 — 넘으면 실격. 한 줄에 사실 하나.\n"
            "- 지침서의 '이야기 기술' 표를 전부 지킨다. 지침서·참고 대본 문장 8자 이상 그대로 베끼기 금지(예 문장은 구조만).\n"
            "- 대본 %d편 — 서로 다른 첫 줄 틀(번호)을 쓴다. mold 에 틀 번호, check 에 검수 체크리스트 결과 한 줄.\n%s") % (lo, hi, n, cta)
    miss = ("[없는 장면 — 효능으로 쓰지 마라] " + " / ".join(missing) + "\n") if missing else ""
    head = "아래 [대본 지침서] 0.공통과 스타일 %s(%s)가 이번 일의 지침 전부다. 지침서 순서(재료 확보 → 첫 줄 틀 → 블록 배치 → 이야기 기술 → 검수)대로 [소재]로 대본을 써라.\n%s" % (
        style, "체험형" if style == "A" else "정보형", rule)
    body = "[대본 지침서]\n%s\n\n[소재] %s\n[근거]\n%s\n%s" % (section(style), product, "\n".join("[%s] %s" % f for f in facts), miss)
    if style == "B":
        (sv, seed), refs = info_refs()
        body = ("[씨앗 대본](조회 %d만) — 먼저 이 대본이 사람들을 홀린 요인(궁금증·고충→해결→놀람 순서·믿게 만든 것)을 analysis 에 짧게 적고 그 흐름을 옮겨라\n%s\n\n"
                "[참고 대본 — 같은 채널 정보형 히트작 전문, 흐름만 본뜬다]\n%s\n\n" % (sv // 10000, seed, "\n\n".join("(%d만) %s" % (v // 10000, t) for v, t in refs))) + body
    return head + "\n" + body
