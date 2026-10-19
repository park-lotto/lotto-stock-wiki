# -*- coding: utf-8 -*-
"""재료 — 원본 영상들의 말에서 '터진 포인트'와 갈래 재료를 뽑는다. **인용이 원문에 있는 것만** 남긴다.

판단 주인(이 묶음 안): 재료 칸 정의·인용 대조·갈래 자격 = 이 파일 한 곳.
왜 인용 대조인가: 버텍스 시험(2026-10-06)에서 어색한 문장은 전부 재료가 없는 칸을 모델이 메운 자리였다
  ("직구한다는"·"단순히 넉넉한 용량 때문이 아니라는데"). 지시문으로는 못 막는다 — 칸마다 **원문 그대로의 인용**을 받고
  코드가 원문과 대조해, 못 찾으면 그 칸을 버린다. 버려진 칸은 대본이 쓸 수 없다(script.py 가 재료에 있는 칸만 보여 준다).
"""
import json
import re

from . import spec

# 칸 이름 → 무엇인가(지시문과 점검표가 같이 쓴다)
FIELDS = {
    "kind_word":     "제품 종류를 가리키는 **낱말 하나**, 8자 이내(예: 이어폰, 텀블러, 보수제). 상표 말고 종류, '및'·쉼표 금지",
    "burst":         "이 영상이 사람들을 붙잡은 한 가지(왜 끝까지 봤겠나) — 영상의 말로",
    "buzz":          "누가·어디서 이걸 좋아한다/유명하다는 말(예: 살림고수들 사이에서 유명, 코스트코에 가면 꼭 산다)",
    "surface":       "사람들이 **겉으로 아는** 사는 이유 — '~하려고'·'~때문에' 꼴로(제품이 무엇인지 설명하는 말이 아니다)",
    "real":          "써 본 사람들이 꼽는 **뜻밖의** 이유·쓰임(겉 이유와 다른 것)",
    "real_who":      "그 뜻밖의 쓰임에 꽂힌 사람들(예: 패션 크리에이터들, 러너들) — 영상에 나온 무리만",
    "wonder":        "겉보기에 말이 안 되는 점(어떻게 그게 되지? 싶은 것)",
    "old_way":       "**같은 종류의 보통(기존) 제품**이 하는 방식 — 이 제품과 같은 일을 하던 옛 방법만(딴 얘기 금지)",
    "old_flaw":      "그 기존 방식의 단점",
    "how":           "이 제품이 그걸 해내는 **작동 방식·구조**(무엇이 어떻게 해서)",
    "original":      "이 제품이 **대신하는 것**(비싼 원조 제품·업체·서비스)",
    "original_lack": "그 원조의 아쉬운 점(값·구하기 어려움·번거로움)",
    "same_proof":    "원조만큼 된다는 근거",
    "gain":          "값·수고에서 얻는 이득",
    "bonus":         "위에 안 쓴 장점 하나 더",
}

PROMPT = """아래는 한 제품을 다룬 영상들의 말(받아쓰기)이다. 첫 번째가 가장 잘 된 영상(씨앗)이다.
이 제품으로 **커뮤니티 썰** 대본을 쓰려고 한다. 대본의 재료 칸을 채워라.

★규칙
- **영상의 말에 실제로 나온 것만** 쓴다. 안 나온 칸은 빈 문자열로 둔다 — 지어내면 대본이 거짓이 된다.
- 칸마다 text(짧게 정리한 말)와 quote(**그 근거가 된 영상의 말을 글자 그대로** 15~60자)를 같이 적는다.
  quote 를 못 대면 그 칸은 비워라. quote 는 고쳐 쓰지 말고 원문을 그대로 옮긴다.
- surface 와 real 은 **서로 다른 것**이어야 한다. 영상에 그런 대비가 없으면 둘 다 비워라.
- original 은 이 제품이 **대신하는** 비싼 것·업체·서비스다. 영상에 그런 비교 대상이 없으면 비워라.

칸:
%s

출력은 JSON 객체 하나: {"칸이름": {"text": "...", "quote": "..."}, ...} — 위 칸 이름을 전부 넣는다.

[제품] %s

%s"""


def _norm(t):
    return re.sub(r"[^가-힣A-Za-z0-9]", "", t or "")


def quote_share(quote, source, n=4):
    """인용의 n글자 조각 중 원문에도 있는 비율. 통째로 들어 있으면 1.0."""
    q, s = _norm(quote), _norm(source)
    if not q:
        return 0.0
    if q in s:
        return 1.0
    grams = [q[i:i + n] for i in range(max(1, len(q) - n + 1))]
    return sum(1 for g in grams if g in s) / len(grams)


def source_block(sources):
    """sources = [{"id": "...", "text": "받아쓰기"}] — 첫 항목이 씨앗."""
    rows = []
    for i, s in enumerate(sources or []):
        t = (s.get("text") or "").strip()
        if t:
            rows.append("[영상 %d%s]\n%s" % (i + 1, " — 씨앗" if i == 0 else "", t[:1800]))
    return "\n\n".join(rows)


def parse(raw):
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip(), flags=re.S)
    i = s.find("{")
    if i < 0:
        raise ValueError("응답에 JSON 객체가 없다")
    return json.JSONDecoder().raw_decode(s[i:])[0]


def verify(raw_fields, sources):
    """모델이 낸 칸 → (남긴 칸 {이름: {text, quote, share}}, 버린 칸 [(이름, 이유)])."""
    src = " ".join((s.get("text") or "") for s in sources or [])
    kept, dropped = {}, []
    for name in FIELDS:
        v = (raw_fields or {}).get(name)
        if isinstance(v, str):
            v = {"text": v, "quote": ""}
        text = ((v or {}).get("text") or "").strip()
        quote = ((v or {}).get("quote") or "").strip()
        if not text:
            continue
        if name == "kind_word":                       # 종류 낱말은 인용을 요구하지 않는다(문장 틀에 끼우는 짧은 말) — 길이만 본다
            if len(text) > spec.KIND_WORD_MAX or re.search(r"및|,|·|/", text):
                dropped.append((name, "종류 낱말이 길다"))
            else:
                kept[name] = {"text": text, "quote": quote, "share": 1.0}
            continue
        if len(_norm(quote)) < 8:
            dropped.append((name, "인용 없음"))
            continue
        sh = quote_share(quote, src)
        if sh < spec.QUOTE_MIN_SHARE:
            dropped.append((name, "인용이 원문에 없음(%.0f%%)" % (sh * 100)))
            continue
        kept[name] = {"text": text, "quote": quote, "share": round(sh, 2)}
    # surface 와 real 이 같은 말이면 대비가 아니다 → 둘 다 버린다
    if "surface" in kept and "real" in kept and quote_share(kept["surface"]["text"], kept["real"]["text"], 3) > 0.6:
        dropped += [("surface", "real 과 같은 말"), ("real", "surface 와 같은 말")]
        kept.pop("surface"); kept.pop("real")
    return kept, dropped


def eligible(material):
    """재료가 갖춰진 갈래 목록(spec.KINDS 순서). 비면 이 제품은 이 채널 틀로 못 쓴다."""
    return [k for k in spec.KINDS if all(n in material for n in spec.KIND_NEEDS[k])]


def missing(material):
    """갈래마다 모자란 칸 — 화면·기록에 '왜 못 썼나'를 보여 주는 용도."""
    return {k: [n for n in spec.KIND_NEEDS[k] if n not in material] for k in spec.KINDS}


def extract(sources, product, call, note=None):
    """→ material dict(검증을 통과한 칸만). call(prompt)->str 은 주입한다(키·모델은 호출자 몫)."""
    fields_txt = "\n".join("  %-13s %s" % (k, v) for k, v in FIELDS.items())
    prompt = PROMPT % (fields_txt, product or "(미상)", source_block(sources))
    out, err = None, ""
    for _ in range(2):                                # 응답이 JSON이 아니면 한 번 더 — 1차 시험에서 4개 영상 작업 1건이 0칸으로 끝났다
        try:
            out = parse(call(prompt))
            if isinstance(out, dict):
                break
            err, out = "JSON 객체가 아니다", None
        except ValueError as e:
            err = str(e)
    if out is None:
        if note is not None:
            note["material_error"] = err
        return {}
    kept, dropped = verify(out, sources)
    if note is not None:
        note["material_dropped"] = dropped
        note["material_missing"] = missing(kept)
    return kept


def extract_best(sources, product, call, note=None):
    """담긴 영상 전부로 한 번 + 씨앗만으로 한 번 뽑아 합친다(전부 쪽이 먼저). 호출 2회.
    ★왜 두 번인가(라이브 재료 시험 1차, 10건): 갈래가 하나라도 나온 작업이 씨앗만 6 · 전부 7인데, 서로 **다른** 작업이었다
      (전부 넣으면 4건이 늘고 2건이 줄었다 — 글이 길어지면 모델이 칸을 빠뜨린다). 합치면 9건."""
    n_all, n_seed = {}, {}
    m_all = extract(sources, product, call, note=n_all) if len(sources or []) > 1 else {}
    m_seed = extract((sources or [])[:1], product, call, note=n_seed)
    merged = dict(m_seed); merged.update(m_all)
    # 합친 뒤에도 surface↔real 대비는 다시 본다(한쪽씩 다른 호출에서 왔을 수 있다)
    if "surface" in merged and "real" in merged and quote_share(merged["surface"]["text"], merged["real"]["text"], 3) > 0.6:
        merged.pop("surface"); merged.pop("real")
    if note is not None:
        note["material_from"] = {k: ("all" if k in m_all else "seed") for k in merged}
        note["material_dropped"] = (n_all.get("material_dropped") or []) + (n_seed.get("material_dropped") or [])
        note["material_missing"] = missing(merged)
    return merged
