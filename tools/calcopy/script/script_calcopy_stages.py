"""대본 칼카피 엔진 — tag · cluster · card · report 단계(script_calcopy.py 가 부른다).
tag 만 버텍스를 쓴다(묶음 호출). 나머지는 tags.jsonl 집계뿐이라 버텍스 0 — 카드의 숫자는 전부 태그를 센 값이다."""
import json, os, re, statistics, time
from collections import Counter, defaultdict

from script_calcopy import load_json, out_dir, read_list, save_json

PROJECT, LOCATION, MODEL = "project-74eaf695-8229-44a1-876", "global", "gemini-3.6-flash"

BEATS = {
    "hook": "첫 줄 — 멈추게 하는 한마디",
    "setup": "상황·계기(누가 언제 무엇을 하다가)",
    "pain": "불편 공감(~잖아요)",
    "reveal": "정체 공개(이건/이게 바로 ~)",
    "authority": "권위·유래·출처(회사·전문가·장소·역사·매체·판매처·수치)",
    "mechanism": "원리·방식 설명",
    "demo": "쓰는 동작(~만 하면)",
    "wow": "와우 — 놀라운 효과·반전",
    "bonus": "덤 — 추가 장점(심지어·특히)",
    "result": "나·공간에 생긴 변화",
    "social": "사회 반응(난리·품절·유행·사람들이 물어봄)",
    "recommend": "권유(~해보세요)",
    "cta": "행동 유도(댓글·링크)",
    "end": "마무리 한마디(만족·감탄)",
}
HOOKS = {
    "지인사건": "가족·지인이 해 둔·사 온·보여 준 물건 + 반응",
    "고백체험": "내가 겪고 생각이 바뀐 일(혼났어요·안 사요·~인 줄 알았어요)",
    "경고명령": "~하지 마세요·~하지 말고 이거 해보세요",
    "만든사람": "개발자·회사·덕후가 만든 미친 제품(~버렸대요·~있어요)",
    "권위장소": "고급 장소·전문가·유행에서 쓴다는 물건",
    "질문도발": "질문·도발(아니 잠깐만요·망할 것 같은데요?)",
    "기타": "위에 없음",
}
DEVICES = ["authority", "wow", "social_proof", "comparison", "metaphor", "number", "sensory", "hearsay", "question", "cta", "price"]
AUTH_KINDS = ["회사·브랜드", "전문가·직업", "장소", "역사·유래", "방송·매체", "판매처", "수치", "인물", ""]

SCHEMA = {"type": "object", "properties": {"scripts": {"type": "array", "items": {"type": "object", "properties": {
    "id": {"type": "string"}, "usable": {"type": "boolean"}, "product": {"type": "string"}, "category": {"type": "string"},
    "tone": {"type": "string"},
    "narrator": {"type": "object", "properties": {"persona": {"type": "string"}, "stance": {"type": "string"}}, "required": ["persona", "stance"]},
    "characters": {"type": "array", "items": {"type": "object", "properties": {
        "role": {"type": "string"}, "modifier": {"type": "string"}, "function": {"type": "string"}}, "required": ["role", "modifier", "function"]}},
    "hook_type": {"type": "string"}, "hook_skeleton": {"type": "string"},
    "story": {"type": "object", "properties": {"arc": {"type": "string"}, "conflict": {"type": "string"}, "turn": {"type": "string"},
                                                "payoff": {"type": "string"}}, "required": ["arc", "conflict", "turn", "payoff"]},
    "lines": {"type": "array", "items": {"type": "object", "properties": {
        "text": {"type": "string"}, "beat": {"type": "string"}, "connector": {"type": "string"}, "ending": {"type": "string"},
        "devices": {"type": "array", "items": {"type": "string"}}, "authority_kind": {"type": "string"},
        "modifier": {"type": "string"}, "wow_kind": {"type": "string"}, "skeleton": {"type": "string"}},
        "required": ["text", "beat", "connector", "ending", "devices", "authority_kind", "modifier", "wow_kind", "skeleton"]}},
    "cta": {"type": "object", "properties": {"kind": {"type": "string"}, "text": {"type": "string"}}, "required": ["kind", "text"]}},
    "required": ["id", "usable", "product", "category", "tone", "narrator", "characters", "hook_type", "hook_skeleton", "story", "lines", "cta"]}}},
    "required": ["scripts"]}

PROMPT = """너는 한국 쇼츠 대본 분석가다. 아래 대본(받아쓰기 원문)을 한 편씩 **줄 단위로 뜯어** 칼카피(그대로 베껴 쓸 수 있는 틀) 재료를 만든다.
규칙:
- lines 의 text 는 원문을 **말 한 호흡 단위로 끊은 것 그대로**다. 한 줄은 대략 15~45자 — 긴 문장은 연결어미(~는데·~니까·~면서·~고·~해서·~더니)와 신호어(근데·심지어·특히) 앞에서 끊어 **여러 줄로** 나눈다(받아쓰기 한 문장 = 보통 2~4줄). 낱말을 바꾸거나 빼거나 요약하지 마라. 이어 붙이면 원문이 돼야 한다(받아쓰기 오타만 고쳐도 된다).
- beat: {beats}
- connector: 그 줄 **맨 앞** 연결어·신호어 원문(근데·심지어·특히·알고 보니·그래서·바로·와·아니 …). 없으면 "".
- ending: 그 줄 **말끝** 원문(~더라고요·~대요·~잖아요·~거든요·~어요·~는데 …). 반복 비교가 되게 끝 1~2어절만.
- devices: 해당하는 것 모두 — {devices}
- authority_kind: 권위를 쓴 줄이면 하나 — {auth}
- modifier: 그 줄에서 **인물·제품 앞에 붙은 꾸밈말** 원문(예: '커피 회사 다니는'(친구) · '천재'(로봇공학자) · '미친'(일본 회사)). 없으면 "".
- wow_kind: wow·bonus 줄이면 원리|효과|반전|비교|활용|가격 중 하나, 아니면 "".
- skeleton: 그 줄을 **다른 제품에도 쓸 수 있는 틀**로 — 제품·장소·인물 낱말만 {{제품}}·{{장소}}·{{인물}}·{{불편}}·{{효과}} 같은 슬롯으로 바꾸고 말투·연결어·어미는 그대로 둔다.
- hook_type: {hooks} 중 하나. hook_skeleton: 첫 줄의 틀(슬롯화).
- narrator.persona: 화자가 누구로 말하나(남편·아내·자취생·살림꾼·전문가·소개자 …). stance: 1인칭체험|전언|설명|혼합.
- characters: 대본에 나오는 인물마다 role(와이프·친구·엄마·개발자·사장님 …), modifier(그 인물 꾸밈말 원문), function(계기 제공|반응|조언·권위|만든 사람|비교 대상).
- story.arc: 이 대본이 **어떻게 이야기를 만드는지** 한 문장(예: '와이프가 해 둔 걸 보고 놀란 반응 → 와이프 취미 설명 → 방법 → 해외 유행으로 마무리'). conflict(불편·욕구), turn(어디서 뒤집나), payoff(어떻게 닫나).
- cta.kind: 댓글키워드|링크|팔로우|없음, text: 원문.
- usable: 제품 소개 대본이 아니면(인사·광고 문구만·말 없음) false — 그때 lines 는 빈 목록.
- tone: 존댓말|반말|섞임.

{scripts}"""


def _client():
    from google import genai
    return genai.Client(vertexai=True, project=PROJECT, location=LOCATION)


def _call(cl, prompt):
    from google.genai import types
    last = None
    for _ in range(3):
        try:
            r = cl.models.generate_content(model=MODEL, contents=prompt, config=types.GenerateContentConfig(
                response_mime_type="application/json", response_schema=SCHEMA))
            return json.loads(r.text)
        except Exception as e:      # noqa: BLE001
            last = repr(e)[:200]
            time.sleep(4)
    raise RuntimeError(last)


def ns(t):
    return re.sub(r"[\s.,!?~…'\"]", "", t or "")


def coverage(lines, text):
    """줄을 이어 붙인 글이 원문을 얼마나 덮나(글자 기준) — 모델이 줄을 빼거나 요약했는지 잰다."""
    a, b = ns("".join(l.get("text", "") for l in lines)), ns(text)
    if not b:
        return 0.0
    import difflib
    return round(difflib.SequenceMatcher(None, a, b, autojunk=False).ratio(), 3)


# ── tag ───────────────────────────────────────────────────────────────
def _tag_batch(cl, ids, tr):
    body = "\n\n".join("[%s]\n%s" % (k, tr[k]["text"]) for k in ids)
    prompt = PROMPT.format(beats=" · ".join("%s=%s" % kv for kv in BEATS.items()), devices=" · ".join(DEVICES),
                           auth=" · ".join(x for x in AUTH_KINDS if x), hooks=" · ".join("%s(%s)" % kv for kv in HOOKS.items()), scripts=body)
    return _call(cl, prompt)


def cmd_tag(a):
    """--workers N: 버텍스 묶음 N개를 동시에 부른다(호출 수는 같다). --follow: 받아쓰기가 따라오는 동안 새 편이 생기면 계속 태깅."""
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed
    d = out_dir(a.slug)
    path = os.path.join(d, "tags.jsonl")
    views = {r["id"]: r["views"] for r in read_list(a.slug)}
    cl = _client()
    lock = threading.Lock()
    calls = [0]
    while True:
        tr = load_json(os.path.join(d, "transcripts.json"), {})
        done = set()
        if os.path.exists(path):
            done = {json.loads(l)["id"] for l in open(path, encoding="utf-8") if l.strip()}
        todo = [k for k in sorted(tr, key=lambda k: -views.get(k, 0)) if k not in done and len(ns(tr[k]["text"])) >= 40]
        skip = [k for k in tr if k not in done and len(ns(tr[k]["text"])) < 40]
        with open(path, "a", encoding="utf-8") as f:
            for k in skip:     # 말이 거의 없는 편 — 버텍스 안 부르고 표시만
                f.write(json.dumps({"id": k, "usable": False, "reason": "말 40자 미만", "views": views.get(k, 0)}, ensure_ascii=False) + "\n")
        if a.limit:
            todo = todo[:a.limit]
        batches = [todo[i:i + a.batch] for i in range(0, len(todo), a.batch)]
        if a.follow and len(todo) % a.batch:
            batches = batches[:-1]       # 따라가는 중엔 덜 찬 묶음은 다음 바퀴로(호출 수 아끼기) — 2026-10-20 덜 찬 묶음을 보내 호출이 34회로 늘었던 것 고침
        print("태깅할 것 %d편(이미 %d · 말 없음 %d) · 묶음 %d개 · 동시 %d" % (len(todo), len(done), len(skip), len(batches), a.workers), flush=True)

        def run(ids):
            try:
                r = _tag_batch(cl, ids, tr)
            except RuntimeError as e:
                return ids, None, str(e)
            return ids, r, ""
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            for fut in as_completed([ex.submit(run, b) for b in batches]):
                ids, r, err = fut.result()
                if r is None:
                    print("실패 묶음", ids[0], err, flush=True)
                    continue
                got = {s.get("id"): s for s in r.get("scripts") or []}
                with lock, open(path, "a", encoding="utf-8") as f:
                    calls[0] += 1
                    for k in ids:
                        s = got.get(k)
                        if not s:
                            continue      # 빠진 편은 다음 바퀴에 다시
                        s["views"] = views.get(k, 0)
                        s["coverage"] = coverage(s.get("lines") or [], tr[k]["text"]) if s.get("usable") else None
                        f.write(json.dumps(s, ensure_ascii=False) + "\n")
                print("묶음 완료(누적 버텍스 %d회)" % calls[0], flush=True)
        if not a.follow:
            break
        n_audio = len([x for x in os.listdir(os.path.join(d, "audio")) if x.endswith(".m4a")])
        if not batches and os.path.exists(os.path.join(d, "_pull_done")) and len(tr) >= n_audio:
            a.follow = False              # 받아쓰기도 끝났다 — 남은 덜 찬 묶음까지 한 바퀴 더 돌고 끝
            continue
        if not batches:
            time.sleep(60)


def load_tags(slug, min_cov=0.85):
    rows = [json.loads(l) for l in open(os.path.join(out_dir(slug), "tags.jsonl"), encoding="utf-8") if l.strip()]
    last = {}
    for r in rows:
        last[r["id"]] = r          # 같은 편을 다시 태깅했으면 마지막 것
    ok = [r for r in last.values() if r.get("usable") and r.get("lines") and (r.get("coverage") or 0) >= min_cov]
    return ok, list(last.values())


# ── cluster ───────────────────────────────────────────────────────────
def arc_of(r):
    """줄 beat 순서 → 같은 beat 연속은 하나로. 유형 묶기의 기준."""
    out = []
    for l in r["lines"]:
        b = l.get("beat") if l.get("beat") in BEATS else "end"
        b = "bonus" if b == "wow" and out and out[-1] in ("wow", "bonus") else b
        if not out or out[-1] != b:
            out.append(b)
    return out


def family(arc):
    """전개 방식 이름 — 무엇으로 증명하고 어떻게 닫나(권위 유무 · 와우 수 · 닫는 법)."""
    has_auth = "authority" in arc
    wow = sum(b in ("wow", "bonus") for b in arc)
    close = arc[-1] if arc else "end"
    close = {"cta": "CTA", "social": "사회반응", "result": "변화", "recommend": "권유"}.get(close, "만족")
    reveal_early = "reveal" in arc[:3]
    return "%s · %s · 와우%s · %s닫기" % ("정체 먼저" if reveal_early else "정체 늦게", "권위O" if has_auth else "권위X", "2+" if wow >= 2 else str(wow), close)


def cmd_cluster(a):
    d = out_dir(a.slug)
    ok, allr = load_tags(a.slug)
    groups = defaultdict(list)
    for r in ok:
        groups[r.get("hook_type") if r.get("hook_type") in HOOKS else "기타"].append(r)
    types = []
    for ht, rs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        fam = Counter(family(arc_of(r)) for r in rs)
        types.append({"type": ht, "desc": HOOKS[ht], "n": len(rs), "views_median": int(statistics.median([r["views"] for r in rs])),
                      "views_sum": sum(r["views"] for r in rs), "families": fam.most_common(),
                      "ids": [r["id"] for r in sorted(rs, key=lambda r: -r["views"])]})
    meta = {"tagged": len(allr), "usable": len(ok), "dropped_low_coverage": sum(1 for r in allr if r.get("usable") and (r.get("coverage") or 0) < 0.85),
            "not_usable": sum(1 for r in allr if not r.get("usable"))}
    save_json(os.path.join(d, "types.json"), {"meta": meta, "types": types})
    print("태깅 %(tagged)d · 쓸 수 있음 %(usable)d · 원문 덮음 부족 %(dropped_low_coverage)d · 대본 아님 %(not_usable)d" % meta)
    for t in types:
        print(" %-6s %3d편 · 조회 중앙 %5d만 · 전개 %s" % (t["type"], t["n"], t["views_median"] // 10000, "; ".join("%s(%d)" % f for f in t["families"][:3])))


# ── card ──────────────────────────────────────────────────────────────
def _top(counter, n=12, min_n=2):
    return [{"v": k, "n": c} for k, c in counter.most_common(n) if k and c >= min_n]


# ── 원문 규칙 세기(버텍스 0) — 모델 태그와 별개로 받아쓰기 원문에서 직접 센다 ──────────────
RAW_CONN = ["근데", "그런데", "심지어", "특히", "알고 보니", "알고보니", "그래서", "게다가", "무엇보다", "진짜", "이게", "바로", "그리고", "덕분에",
            "아니", "와", "솔직히", "요즘", "얼마 전", "평소에", "이제", "오히려", "역시", "근데 진짜", "더 놀라운", "더 미친", "제일 좋은"]
RAW_END = ["더라고요", "더라구요", "거든요", "잖아요", "대요", "래요", "다던데", "는데요", "거예요", "이에요", "예요", "어요", "아요", "해요",
           "습니다", "죠", "네요", "군요", "거 있죠", "주세요", "보세요"]
RAW_CTA = {"댓글 키워드": r"댓글에|댓글로|남겨\s*주", "링크": r"링크|프로필|찾아왔|알아왔", "팔로우·저장": r"팔로우|저장해|구독"}


def _sents(t):
    return [x.strip() for x in re.split(r"(?<=[.?!])\s+", t or "") if x.strip()]


def raw_measure(rs, tr):
    conn, end, cta, first_len, total = Counter(), Counter(), Counter(), [], []
    for r in rs:
        t = (tr.get(r["id"]) or {}).get("text", "")
        ss = _sents(t)
        total.append(len(ns(t)))
        if ss:
            first_len.append(len(ss[0]))
        for x in ss:
            for c in sorted(RAW_CONN, key=len, reverse=True):
                if x.startswith(c + " ") or x.startswith(c + ","):
                    conn[c] += 1
                    break
            # 문장 안 절 머리(", 근데" " 심지어 ")도 센다
            for c in ("근데", "심지어", "특히", "알고 보니", "게다가", "덕분에", "오히려"):
                conn[c + "(문장 안)"] += len(re.findall(r"(?<=[가-힣요다]) %s " % c, x))
            for e in sorted(RAW_END, key=len, reverse=True):
                if re.search(e + r"[.?!]*$", x):
                    end[e] += 1
                    break
        for k, p in RAW_CTA.items():
            if re.search(p, " ".join(ss[-2:])):
                cta[k] += 1
    n = max(1, len(rs))
    return {"connectors_sentence_head": _top(conn, 20, 1), "endings_sentence": _top(end, 15, 1),
            "cta": [{"v": k, "n": c, "share": round(c / n, 2)} for k, c in cta.most_common()],
            "first_sentence_chars": {"p10": sorted(first_len)[len(first_len) // 10] if first_len else 0, "median": int(statistics.median(first_len)) if first_len else 0},
            "chars": {"median": int(statistics.median(total)) if total else 0}}


def agreement(card):
    """모델 태그 연결어 상위 vs 원문 규칙 세기 상위 — 겹치는 비율. 낮으면 태그를 의심한다."""
    a = {x["v"] for x in card["connectors"][:6]}
    b = {x["v"] for x in card["raw"]["connectors_sentence_head"][:8]} | {x["v"].replace("(문장 안)", "") for x in card["raw"]["connectors_sentence_head"]}
    return round(len(a & b) / max(1, len(a)), 2)


# ── 잘된 편 vs 안된 편 비교(버텍스 0) ─────────────────────────────────
def features(r):
    """편 하나의 특징 묶음(있다/없다). 잘된 편과 안된 편의 비율 차이를 잰다."""
    arc = arc_of(r)
    ls = r["lines"]
    f = {}
    for b in BEATS:
        f["칸: " + b] = b in arc
    f["정체 공개가 앞 3칸 안"] = "reveal" in arc[:3]
    f["권위 줄 있음"] = any(l.get("authority_kind") for l in ls)
    for k in AUTH_KINDS:
        if k:
            f["권위: " + k] = any(l.get("authority_kind") == k for l in ls)
    w = sum(1 for l in ls if l.get("wow_kind"))
    f["와우 0줄"], f["와우 1줄"], f["와우 2줄+"] = w == 0, w == 1, w >= 2
    for dv in DEVICES:
        f["장치: " + dv] = any(dv in (l.get("devices") or []) for l in ls)
    f["인물 꾸밈말 있음"] = any(c.get("modifier") for c in r.get("characters") or [])
    f["등장인물 있음(화자 말고)"] = bool(r.get("characters"))
    for c in r.get("characters") or []:
        f["인물: " + c.get("role", "")] = True
    f["CTA: " + (r["cta"].get("kind") or "없음")] = True
    f["닫기: " + (arc[-1] if arc else "")] = True
    f["화자: " + r["narrator"].get("persona", "")] = True
    n = len(ns("".join(l["text"] for l in ls)))
    f["글자 150 미만"], f["글자 150~220"], f["글자 220+"] = n < 150, 150 <= n < 220, n >= 220
    f0 = len(ns(ls[0]["text"])) if ls else 0
    f["첫 줄 25자 미만"], f["첫 줄 25~40자"], f["첫 줄 40자+"] = f0 < 25, 25 <= f0 < 40, f0 >= 40
    for l in ls:
        if l.get("connector"):
            f["연결어: " + l["connector"]] = True
    return f


def contrast(hits, flops, min_diff=0.12, min_n=3):
    fh, ff = Counter(), Counter()
    for r in hits:
        for k, v in features(r).items():
            if v:
                fh[k] += 1
    for r in flops:
        for k, v in features(r).items():
            if v:
                ff[k] += 1
    nh, nf = max(1, len(hits)), max(1, len(flops))
    rows = []
    for k in set(fh) | set(ff):
        if fh[k] + ff[k] < min_n:
            continue
        a, b = fh[k] / nh, ff[k] / nf
        if abs(a - b) >= min_diff:
            rows.append({"f": k, "hit": round(a, 2), "flop": round(b, 2), "diff": round(a - b, 2), "n_hit": fh[k], "n_flop": ff[k]})
    return sorted(rows, key=lambda x: -abs(x["diff"]))


def build_card(ht, rs):
    """유형 하나의 칼카피 카드 — 전부 태그 집계. 줄 배치는 가장 많은 전개를 뼈대로, 칸마다 연결어·어미·틀 예문."""
    rs = sorted(rs, key=lambda r: -r["views"])
    arcs = Counter(tuple(arc_of(r)) for r in rs)
    beat_stat = defaultdict(lambda: {"n": 0, "conn": Counter(), "end": Counter(), "skel": [], "chars": [], "pos": []})
    conn, end, dev, auth, wowk, modi, cta = Counter(), Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
    persona, stance, chars, cfun, tone = Counter(), Counter(), Counter(), Counter(), Counter()
    auth_lines, wow_lines, cta_lines, arcs_txt = [], [], [], []
    lens, nlines = [], []
    for r in rs:
        ls = r["lines"]
        nlines.append(len(ls))
        lens.append(len(ns("".join(l["text"] for l in ls))))
        persona[r["narrator"].get("persona", "")] += 1
        stance[r["narrator"].get("stance", "")] += 1
        tone[r.get("tone", "")] += 1
        cta[r["cta"].get("kind", "")] += 1
        if r["cta"].get("text"):
            cta_lines.append(r["cta"]["text"])
        arcs_txt.append({"id": r["id"], "views": r["views"], "arc": r["story"].get("arc", ""), "turn": r["story"].get("turn", ""),
                         "payoff": r["story"].get("payoff", "")})
        for c in r.get("characters") or []:
            chars[c.get("role", "")] += 1
            cfun["%s → %s" % (c.get("role", ""), c.get("function", ""))] += 1
            if c.get("modifier"):
                modi["인물: %s %s" % (c["modifier"], c.get("role", ""))] += 1
        for j, l in enumerate(ls):
            b = l.get("beat") if l.get("beat") in BEATS else "end"
            s = beat_stat[b]
            s["n"] += 1
            s["conn"][l.get("connector", "")] += 1
            s["end"][l.get("ending", "")] += 1
            s["chars"].append(len(ns(l["text"])))
            s["pos"].append(round(j / max(1, len(ls) - 1), 2))
            if len(s["skel"]) < 6 and l.get("skeleton"):
                s["skel"].append({"skel": l["skeleton"], "src": l["text"], "views": r["views"]})
            conn[l.get("connector", "")] += 1
            end[l.get("ending", "")] += 1
            for x in l.get("devices") or []:
                dev[x] += 1
            if l.get("authority_kind"):
                auth[l["authority_kind"]] += 1
                if len(auth_lines) < 10:
                    auth_lines.append({"kind": l["authority_kind"], "text": l["text"], "skel": l.get("skeleton", "")})
            if l.get("wow_kind"):
                wowk[l["wow_kind"]] += 1
                if len(wow_lines) < 10:
                    wow_lines.append({"kind": l["wow_kind"], "connector": l.get("connector", ""), "text": l["text"]})
            if l.get("modifier") and not any(l["modifier"] in k for k in modi):
                modi["줄: " + l["modifier"]] += 1
    # 뼈대 = 이 유형 편의 30% 이상에 나오는 칸을 대본 안 위치(중앙값) 순서로 — 같은 전개 순서가 그대로 반복되는 일은 드물다
    present = Counter(b for r in rs for b in set(arc_of(r)))
    main_arc = sorted([b for b, c in present.items() if c / len(rs) >= 0.3], key=lambda b: statistics.median(beat_stat[b]["pos"]))
    slots = []
    for b in main_arc:
        s = beat_stat[b]
        slots.append({"beat": b, "does": BEATS[b], "share": round(present[b] / len(rs), 2), "pos_median": statistics.median(s["pos"]),
                      "lines_per_script": round(s["n"] / max(1, present[b]), 1),
                      "chars_median": int(statistics.median(s["chars"])) if s["chars"] else 0,
                      "connectors": _top(s["conn"], 6, 1), "endings": _top(s["end"], 6, 1), "skeletons": s["skel"]})
    n = len(rs)
    return {
        "type": ht, "desc": HOOKS.get(ht, ""), "n": n, "views_median": int(statistics.median([r["views"] for r in rs])),
        "hook_skeletons": [{"skel": r.get("hook_skeleton", ""), "src": r["lines"][0]["text"], "views": r["views"]} for r in rs[:12]],
        "arc_main": main_arc, "arcs": [{"arc": " → ".join(k), "n": c} for k, c in arcs.most_common(8)],
        "families": Counter(family(arc_of(r)) for r in rs).most_common(),
        "slots": slots,
        "story_examples": arcs_txt[:10],
        "narrator": {"persona": _top(persona, 8, 1), "stance": _top(stance, 4, 1)},
        "characters": {"roles": _top(chars, 10, 1), "functions": _top(cfun, 10, 1)},
        "modifiers": _top(modi, 20, 1),
        "connectors": _top(conn, 15), "endings": _top(end, 15), "devices": _top(dev, 12, 1),
        "authority": {"kinds": _top(auth, 10, 1), "per_script": round(sum(1 for r in rs if any(l.get("authority_kind") for l in r["lines"])) / n, 2), "lines": auth_lines},
        "wow": {"kinds": _top(wowk, 8, 1), "per_script_median": statistics.median([sum(1 for l in r["lines"] if l.get("wow_kind")) for r in rs]), "lines": wow_lines},
        "cta": {"kinds": _top(cta, 6, 1), "texts": cta_lines[:10]},
        "tone": _top(tone, 3, 1),
        "length": {"chars_p10": sorted(lens)[n // 10], "chars_median": int(statistics.median(lens)), "chars_p90": sorted(lens)[min(n - 1, n * 9 // 10)],
                   "lines_median": statistics.median(nlines)},
        "refs": [{"id": r["id"], "views": r["views"], "lines": [{"beat": l["beat"], "text": l["text"], "skel": l.get("skeleton", "")} for l in r["lines"]]} for r in rs[:4]],
    }


def card_md(c):
    L = ["# %s — %s (잘된 편 %d · 조회 중앙 %d만)" % (c["type"], c["desc"], c["n"], c["views_median"] // 10000), ""]
    if c.get("base"):
        L += ["전체 %(all)d편 중 잘된 편 %(hits)d(%(hit_rate).0f%%) · 안된 편 %(flops)d — 카드 숫자·예문은 잘된 편만" % dict(c["base"], hit_rate=c["base"]["hit_rate"] * 100), ""]
    if c.get("contrast"):
        L += ["## 잘된 편 vs 안된 편 — 차이 20%p 이상", "| 특징 | 잘된 편 | 안된 편 | 차이 |", "|---|---|---|---|"]
        L += ["| %s | %.0f%% (%d) | %.0f%% (%d) | %+.0f%%p |" % (x["f"], x["hit"] * 100, x["n_hit"], x["flop"] * 100, x["n_flop"], x["diff"] * 100) for x in c["contrast"][:20]] + [""]
    L += ["## 전개(가장 많은 줄 배치)", " → ".join(c["arc_main"]), ""] + ["- %s (%d편)" % (x["arc"], x["n"]) for x in c["arcs"]] + [""]
    L += ["## 칸별 칼카피"]
    for s in c["slots"]:
        L.append("### %s — %s (%.0f%% 편 · 위치 %.2f · 편당 %s줄 · 줄 중앙 %d자)" % (s["beat"], s["does"], s["share"] * 100, s["pos_median"], s["lines_per_script"], s["chars_median"]))
        L.append("- 연결어: " + ", ".join("%s %d" % (x["v"] or "(없음)", x["n"]) for x in s["connectors"]))
        L.append("- 어미: " + ", ".join("%s %d" % (x["v"], x["n"]) for x in s["endings"]))
        L += ["- 틀: %s  ← %s" % (x["skel"], x["src"]) for x in s["skeletons"][:4]]
    L += ["", "## 첫 줄 틀"] + ["- %s  ← %s (%d만)" % (x["skel"], x["src"], x["views"] // 10000) for x in c["hook_skeletons"]]
    L += ["", "## 스토리 만드는 법(조회 상위)"] + ["- %s (전환: %s / 닫기: %s)" % (x["arc"], x["turn"], x["payoff"]) for x in c["story_examples"]]
    for k, title in [("connectors", "연결어"), ("endings", "어미"), ("modifiers", "꾸밈말"), ("devices", "장치")]:
        L += ["", "## " + title, ", ".join("%s %d" % (x["v"], x["n"]) for x in c[k])]
    L += ["", "## 인물·역할", "화자: " + ", ".join("%s %d" % (x["v"], x["n"]) for x in c["narrator"]["persona"]),
          "인물: " + ", ".join("%s %d" % (x["v"], x["n"]) for x in c["characters"]["functions"])]
    L += ["", "## 권위 (%.0f%% 편이 씀)" % (c["authority"]["per_script"] * 100), ", ".join("%s %d" % (x["v"], x["n"]) for x in c["authority"]["kinds"])]
    L += ["- [%s] %s" % (x["kind"], x["text"]) for x in c["authority"]["lines"]]
    L += ["", "## 와우 (편당 중앙 %s줄)" % c["wow"]["per_script_median"], ", ".join("%s %d" % (x["v"], x["n"]) for x in c["wow"]["kinds"])]
    L += ["- [%s · %s] %s" % (x["kind"], x["connector"] or "-", x["text"]) for x in c["wow"]["lines"]]
    L += ["", "## CTA", ", ".join("%s %d" % (x["v"], x["n"]) for x in c["cta"]["kinds"])] + ["- " + t for t in c["cta"]["texts"]]
    L += ["", "## 길이", "글자 %(chars_p10)d~%(chars_p90)d(중앙 %(chars_median)d) · 줄 중앙 %(lines_median)s" % c["length"]]
    if c.get("raw"):
        r = c["raw"]
        L += ["", "## 원문 규칙 세기(버텍스 0 — 모델 태그 검산)",
              "문장 머리 연결어: " + ", ".join("%s %d" % (x["v"], x["n"]) for x in r["connectors_sentence_head"]),
              "문장 끝 어미: " + ", ".join("%s %d" % (x["v"], x["n"]) for x in r["endings_sentence"]),
              "CTA(끝 두 문장): " + ", ".join("%s %d편(%.0f%%)" % (x["v"], x["n"], x["share"] * 100) for x in r["cta"]),
              "첫 문장 글자 중앙 %d · 전체 글자 중앙 %d" % (r["first_sentence_chars"]["median"], r["chars"]["median"]),
              "태그 연결어 상위 6개 중 원문에서도 확인된 비율: %.0f%%" % (c.get("tag_vs_raw_connectors", 0) * 100)]
    return "\n".join(L)


def cmd_card(a):
    d = out_dir(a.slug)
    ok, _ = load_tags(a.slug)
    tr = load_json(os.path.join(d, "transcripts.json"), {})
    by = defaultdict(list)
    for r in ok:
        by[r.get("hook_type") if r.get("hook_type") in HOOKS else "기타"].append(r)
    cd = os.path.join(d, "cards")
    os.makedirs(cd, exist_ok=True)
    allc = {}
    hit_th, flop_th = a.hit, a.flop
    allu = [r for rs in by.values() for r in rs]
    channel = {"hit_th": hit_th, "flop_th": flop_th, "n_hit": sum(r["views"] >= hit_th for r in allu), "n_flop": sum(r["views"] < flop_th for r in allu),
               "contrast": contrast([r for r in allu if r["views"] >= hit_th], [r for r in allu if r["views"] < flop_th])}
    save_json(os.path.join(d, "contrast_channel.json"), channel)
    for ht, rs in by.items():
        hits = [r for r in rs if r["views"] >= hit_th]
        flops = [r for r in rs if r["views"] < flop_th]
        if len(hits) < 3:
            print("카드 건너뜀 %s — 잘된 편 %d" % (ht, len(hits)))
            continue
        c = build_card(ht, hits)          # ★카드 = 잘된 편만으로
        c["base"] = {"all": len(rs), "hits": len(hits), "flops": len(flops), "hit_rate": round(len(hits) / len(rs), 2)}
        c["contrast"] = contrast(hits, flops, min_diff=0.2)
        rs = hits
        c["raw"] = raw_measure(rs, tr)
        c["tag_vs_raw_connectors"] = agreement(c)
        # 검증: 카드 숫자 = 태그 집계(다시 세서 맞는지)
        assert c["n"] == len(rs) and sum(x["n"] for x in c["cta"]["kinds"]) <= len(rs)
        save_json(os.path.join(cd, ht + ".json"), c)
        open(os.path.join(cd, ht + ".md"), "w", encoding="utf-8").write(card_md(c))
        allc[ht] = c
        print("카드 %s %d편" % (ht, c["n"]))
    save_json(os.path.join(d, "cards_all.json"), allc)


def cmd_report(a):
    import html
    d = out_dir(a.slug)
    allc = load_json(os.path.join(d, "cards_all.json"), {})
    ty = load_json(os.path.join(d, "types.json"), {})
    e = html.escape

    def chips(xs, n=10):
        return " ".join('<span class="chip">%s <b>%d</b></span>' % (e(x["v"] or "(없음)"), x["n"]) for x in xs[:n])
    rec = load_json(os.path.join(d, "recipes.json"), {})   # 사람이(또는 Claude가) 잘된 편을 읽고 쓴 공식 — 있으면 유형 맨 앞에
    secs = []
    if rec.get("channel"):
        ch = rec["channel"]
        secs.append('<section class="rec"><h2>채널 공통 — 잘된 편 vs 안된 편</h2>%s</section>' % "".join(
            "<h3>%s</h3>%s" % (e(k), ("<ul>%s</ul>" % "".join("<li>%s</li>" % e(x) for x in v)) if isinstance(v, list) else "<p>%s</p>" % e(v)) for k, v in ch.items()))
    for ht, c in sorted(allc.items(), key=lambda kv: -kv[1]["base"]["hits"] if kv[1].get("base") else -kv[1]["n"]):
        r = (rec.get("types") or {}).get(ht)
        rhtml = ""
        if r:
            rhtml = '<div class="recipe"><h3>칼카피 공식 — %s</h3><p class="mut">%s</p><ol>%s</ol>%s</div>' % (
                e(r.get("한 줄 정의", "")), e(r.get("히트율", "")), "".join("<li>%s</li>" % e(x) for x in r.get("공식", [])),
                "".join("<p><b>%s</b> %s</p>" % (e(k), e(v)) for k, v in r.items() if k not in ("한 줄 정의", "히트율", "공식")))
        slots = "".join('<tr><td><b>%s</b><div class="mut">%s</div></td><td>%d%%<br>%d자</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
            e(s["beat"]), e(s["does"]), s["share"] * 100, s["chars_median"], chips(s["connectors"], 4), chips(s["endings"], 4),
            "<br>".join("%s <span class='mut'>← %s</span>" % (e(x["skel"]), e(x["src"])) for x in s["skeletons"][:3])) for s in c["slots"])
        refs = "".join('<details><summary>%d만 · %s</summary><ol>%s</ol></details>' % (
            r["views"] // 10000, e(r["id"]), "".join("<li><span class='beat'>%s</span> %s</li>" % (e(l["beat"]), e(l["text"])) for l in r["lines"])) for r in c["refs"])
        base = c.get("base") or {}
        secs.append('''<section><h2>%s <span class="mut">%s · 잘된 편 %d · 조회 중앙 %d만</span></h2>''' % (e(ht), e(c["desc"]), c["n"], c["views_median"] // 10000)
                    + rhtml + ('<h3>잘된 편 vs 안된 편 (전체 %d · 잘된 %d · 안된 %d)</h3><div class="tbl"><table><tr><th>특징</th><th>잘된 편</th><th>안된 편</th><th>차이</th></tr>%s</table></div>' % (
                        base.get("all", 0), base.get("hits", 0), base.get("flops", 0), "".join('<tr><td>%s</td><td>%.0f%%</td><td>%.0f%%</td><td><b>%+.0f%%p</b></td></tr>' % (e(x["f"]), x["hit"] * 100, x["flop"] * 100, x["diff"] * 100) for x in (c.get("contrast") or [])[:12])) if c.get("contrast") else "")
                    + '''
<p><b>전개</b> %s</p><div class="mut">%s</div>
<div class="tbl"><table><tr><th>칸</th><th>비율·길이</th><th>연결어</th><th>어미</th><th>틀 ← 원문</th></tr>%s</table></div>
<div class="grid2"><div><h3>첫 줄 틀</h3><ul>%s</ul></div><div><h3>스토리 만드는 법</h3><ul>%s</ul></div></div>
<div class="grid2"><div><h3>권위 — %d%% 편</h3>%s<ul>%s</ul></div><div><h3>와우 — 편당 %s줄</h3>%s<ul>%s</ul></div></div>
<div class="grid2"><div><h3>꾸밈말</h3>%s<h3>인물 역할</h3>%s<h3>화자</h3>%s</div><div><h3>연결어</h3>%s<h3>어미</h3>%s<h3>CTA</h3>%s<ul>%s</ul><h3>길이</h3>%d~%d자(중앙 %d)</div></div>
<h3>원문 대본(조회 상위)</h3>%s</section>''' % (
            e(" → ".join(c["arc_main"])),
            " · ".join("%s(%d)" % (e(" → ".join(x["arc"].split(" → "))), x["n"]) for x in c["arcs"][:4]), slots,
            "".join("<li>%s <span class='mut'>← %s (%d만)</span></li>" % (e(x["skel"]), e(x["src"]), x["views"] // 10000) for x in c["hook_skeletons"][:8]),
            "".join("<li>%s <span class='mut'>전환: %s · 닫기: %s</span></li>" % (e(x["arc"]), e(x["turn"]), e(x["payoff"])) for x in c["story_examples"][:6]),
            c["authority"]["per_script"] * 100, chips(c["authority"]["kinds"]), "".join("<li>[%s] %s</li>" % (e(x["kind"]), e(x["text"])) for x in c["authority"]["lines"][:5]),
            c["wow"]["per_script_median"], chips(c["wow"]["kinds"]), "".join("<li>[%s · %s] %s</li>" % (e(x["kind"]), e(x["connector"] or "-"), e(x["text"])) for x in c["wow"]["lines"][:5]),
            chips(c["modifiers"], 14), chips(c["characters"]["functions"], 8), chips(c["narrator"]["persona"], 6),
            chips(c["connectors"], 12), chips(c["endings"], 12), chips(c["cta"]["kinds"]), "".join("<li>%s</li>" % e(t) for t in c["cta"]["texts"][:4]),
            c["length"]["chars_p10"], c["length"]["chars_p90"], c["length"]["chars_median"], refs))
    m = ty.get("meta", {})
    over = "".join("<tr><td>%s</td><td>%s</td><td>%d</td><td>%d만</td><td>%s</td></tr>" % (
        e(t["type"]), e(t["desc"]), t["n"], t["views_median"] // 10000, e("; ".join("%s(%d)" % tuple(f) for f in t["families"][:3]))) for t in ty.get("types", []))
    tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_tpl.html"), encoding="utf-8").read()
    page = tpl.replace("@@SLUG@@", e(a.slug)).replace("@@META@@", "목록 %s편 · 태깅 %d · 쓸 수 있음 %d · 원문 덮음 부족 제외 %d · 대본 아님 %d" % (
        load_json(os.path.join(d, "meta.json"), {}).get("n", "?"), m.get("tagged", 0), m.get("usable", 0), m.get("dropped_low_coverage", 0), m.get("not_usable", 0)))
    page = page.replace("@@OVER@@", over).replace("@@BODY@@", "\n".join(secs))
    open(os.path.join(d, "report.html"), "w", encoding="utf-8").write(page)
    print(os.path.join(d, "report.html"))
