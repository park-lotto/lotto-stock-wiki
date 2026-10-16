# -*- coding: utf-8 -*-
"""갈래 규칙대로 대본 쓰기 — 주제 하나를 주면 그 갈래 말투·박자로 대본이 나온다 (관제 097, 2026-10-15).

    PYTHONUTF8=1 py tools/calcopy/style_writer.py rules  C:/숏템_칼카피/sseolpulda channel/sseolpulda 제품_이야기썰형
    PYTHONUTF8=1 py tools/calcopy/style_writer.py captions <rules.json> <뜯기.json> "주제" 훅,반전,… <대본.json>   # 나레 없는 자막만 영상
    PYTHONUTF8=1 py tools/calcopy/style_writer.py write  channel/sseolpulda/제품_이야기썰형.rules.json "주제" ["주제2" …]

rules: 갈래 편들의 판독(judge)에서 길이·박자 위치·훅 꼴·말끝·예문을 뽑아 규칙 한 장(.rules.json)으로.
write: 규칙 + 예문 3편(조회 상위)을 보여 주고 '틀은 따라 하되 문장은 베끼지 말라'로 쓴다. 쓴 뒤 같은 자로 잰다(check).
"""
from __future__ import annotations

import collections
import json
import re
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

ORDER = ["훅", "정체공개", "상황", "의문", "반전", "원리", "덤", "결말", "댓글유도"]
CPS = 7.4   # 50편 받아쓰기 중앙(자/초)


def build_rules(base: str, chfolder: str, style_file_name: str) -> Path:
    base, ch = Path(base), Path(chfolder)
    groups = json.loads((ch / "갈래.json").read_text(encoding="utf-8"))["styles"]
    name = style_file_name.replace("_", " ")
    g = next(s for s in groups if s["name"] == name)
    pos, L, hooks, ends, scripts = collections.defaultdict(list), [], [], collections.Counter(), []
    for vid in g["ids"]:
        J = json.loads((base / "judge" / f"{vid}.json").read_text(encoding="utf-8"))
        bs = J.get("beats") or []
        T = bs[-1]["t1"] if bs else 0
        for b in bs:
            if T and b["fn"] in ORDER:
                pos[b["fn"]].append(b["t0"] / T)
        s = (J.get("script") or "").strip()
        L.append(len(s.replace(" ", "")))
        hooks.append((J.get("hook") or {}).get("text"))
        ends.update((J.get("tone") or {}).get("ending") or [])
        scripts.append({"id": vid, "views": next(r for r in json.loads((base / "top50.json").read_text(encoding="utf-8")) if r["id"] == vid)["views"],
                        "script": s, "beats": [{"fn": b["fn"], "text": b["text"]} for b in bs]})
    beats = sorted(((k, round(st.median(v), 2), len(v)) for k, v in pos.items() if len(v) >= 5), key=lambda x: x[1])
    rules = {
        "style": name, "n": g["n"], "views_median": g["views_median"],
        "length_chars": {"median": st.median(L), "p25": sorted(L)[len(L) // 4], "p75": sorted(L)[len(L) * 3 // 4]},
        "seconds_at_cps": round(st.median(L) / CPS, 1),
        "beats": [{"fn": k, "start_ratio": r, "seen_in": n} for k, r, n in beats],
        "tone": {"honorific": "반말(음슴체)", "endings_seen": ends.most_common(15)},
        "hooks": [h for h in hooks if h],
        "examples": sorted(scripts, key=lambda s: -s["views"])[:5],
    }
    out = ch / f"{style_file_name}.rules.json"
    out.write_text(json.dumps(rules, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"규칙 → {out}  길이 중앙 {rules['length_chars']['median']}자 · 박자 {[b['fn'] for b in rules['beats']]}")
    return out


PROMPT = """너는 한국어 쇼츠 채널의 대본 작가다. 아래 '갈래 규칙'과 '예문'은 이 채널에서 실제로 터진 영상들이다.
주제: {topic}

할 일: 이 주제로 같은 갈래의 새 대본을 써라.
- 길이: 공백 빼고 {lo}~{hi}자(중앙 {med}자 ≈ {sec}초).
- 박자 순서와 대략 위치(전체 중 시작 비율): {beats}
- 첫 문장은 훅. 이 채널 훅 꼴을 참고: {hooks}
- 말투: 반말 음슴체(~임, ~버림, ~는데, ~다는 거). 존댓말 금지. 1인칭 경험담 금지(지어낸 경험 금지).
- ★예문 문장을 그대로 베끼지 마라. 틀(박자·리듬·말끝)만 따르고 문장은 새로 써라.
- ★사실은 아래 '조사한 비하인드'에 있는 것만 써라. 거기 없는 숫자·회사명·연도·인증·효능은 쓰지 마라.
- 이 영상의 각도(가장 '아 그래?' 할 비하인드): {angle}
  이 각도가 훅·반전의 중심이 되게 써라.
- ★스토리가 탄탄해야 한다(시청자가 빠져들게): 다들 가진 의문/문제 제기 → 원인(몰랐던 비밀) → 주인공(누가)과 갈등 → 해결·반전 →
  시청자가 얻는 것 → 마지막 한 방(승리감·말해 주고 싶은 한 줄). 정보 나열 금지 — 한 줄기 이야기로.
- 과장·꾸밈 말투는 괜찮다(이 채널 스타일). 단 조사에 없는 사실·숫자는 금지. 각도 첫 줄 후보: {angle_hooks}
조사한 비하인드(출처 있음):
{facts}
예문(조회 상위):
{examples}
출력 JSON만: {{"title":"영상 위 제목 2줄(줄바꿈 \\n)","lines":[{{"fn":"훅|정체공개|상황|의문|반전|원리|덤|결말|댓글유도","text":"한 문장","facts":["f1"]}}]}}
lines[].facts = 그 줄이 기대는 조사 항목 id(사실 주장이 없는 줄만 빈 목록)."""


def _client():
    from shopping_shorts.channelkit.providers import _gemini_client
    return _gemini_client(None, str(ROOT / ".env"))


def _calls():
    """(일반 호출, 검색 붙은 호출) — 조사는 반드시 검색이 붙어야 한다(모델 지식만이면 지어낸다)."""
    import time
    from google.genai import types
    client = _client()

    def call(prompt, model="gemini-2.5-pro"):
        for wait in (0, 10, 30):
            time.sleep(wait)
            try:
                return client.models.generate_content(model=model, contents=prompt, config=types.GenerateContentConfig(
                    response_mime_type="application/json", temperature=0.8)).text
            except Exception as e:  # noqa: BLE001
                last = e
        raise last

    def search_call(prompt):
        for wait in (0, 10, 30):
            time.sleep(wait)
            try:
                return client.models.generate_content(model="gemini-2.5-pro", contents=prompt, config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())])).text
            except Exception as e:  # noqa: BLE001
                last = e
        raise last
    return call, search_call


def gather(topic: str, call, search_call) -> dict:
    """제품 비하인드 모으기 — 조사·각도 고르기는 seedflow 의 것을 그대로 부른다(판단 주인 = seedflow.research / pick_angle)."""
    from shopping_shorts import seedflow
    # 후보를 넓게 — 주제 하나를 여러 갈래로 나눠 각각 조사하고 합친다(사장님 2026-10-15 "여러 개 뽑아 1등")
    facets = [topic] + [f"{topic} — {f}" for f in FACETS]
    facts, seen = [], set()
    for q in facets:
        for f in seedflow.research(q, [x["text"] for x in facts][:20], search_call):
            key = re.sub(r"\W", "", f["text"])[:30]
            if key in seen:
                continue
            seen.add(key)
            f["id"] = "f%d" % (len(facts) + 1)
            facts.append(f)
    angle = seedflow.pick_angle(topic, [], facts, call)
    # 순위표 — 아는 주제·몰랐던 정도·재미 합(판정은 pick_angle 이 한 점수 그대로)
    sc = {s["id"]: s for s in angle.get("scores") or []}
    rank = sorted(({"id": f["id"], "text": f["text"], "kind": f.get("kind"), "source": f.get("source"),
                    **{k: sc.get(f["id"], {}).get(k) for k in ("known", "surprise", "fun", "throwable", "story", "gain")}} for f in facts),
                  key=lambda r: -sum((r[k] or 0) for k in ("known", "surprise", "fun", "story", "gain")))
    return {"facts": facts, "angle": angle, "ranking": rank}


FACETS = ["메뉴·음료 탄생 비화", "푸드·재료 숨은 사실", "브랜드·매장·로고 뒷이야기", "사건·논란·화제"]


def write(rules_path: str, topics: list[str]) -> list[dict]:
    R = json.loads(Path(rules_path).read_text(encoding="utf-8"))
    ex = "\n\n".join(f"[{e['views']:,}회]\n" + "\n".join(f"({b['fn']}) {b['text']}" for b in e["beats"]) + f"\n전문: {e['script']}"
                     for e in R["examples"][:3])
    beats = " → ".join(f"{b['fn']}({b['start_ratio']:.0%})" for b in R["beats"])
    lo, hi = R["length_chars"]["p25"], R["length_chars"]["p75"]
    from shopping_shorts import seedflow
    call, search_call = _calls()
    out = []
    for t in topics:
        g = gather(t, call, search_call)
        print(f"\n■ {t}  — 비하인드 {len(g['facts'])}개, 각도: {g['angle'].get('angle') or '(없음: ' + g['angle'].get('why_none', '') + ')'}")
        print("   순위  아는·몰랐던·재미·이야기·얻는것  소재")
        for n, r in enumerate(g["ranking"][:12], 1):
            print(f"   {n:>2}. {r['known']}·{r['surprise']}·{r['fun']}·{r['story']}·{r['gain']}  {r['text'][:70]}  [{seedflow.source_tier(r.get('source'))}]")
        if not g["angle"].get("angle"):
            out.append({"topic": t, "skipped": "썰감 없음 — " + g["angle"].get("why_none", ""), **g})
            print("  → 이 주제는 '아 그래?' 할 비하인드가 없어 대본을 쓰지 않는다")
            continue
        p = PROMPT.format(topic=t, lo=lo, hi=hi, med=R["length_chars"]["median"], sec=R["seconds_at_cps"],
                          beats=beats, hooks=" / ".join(R["hooks"][:10]), examples=ex,
                          angle=g["angle"]["angle"], angle_hooks=" / ".join(g["angle"].get("hooks") or []),
                          facts=seedflow._facts_block(g["facts"]))
        d = seedflow.parse(call(p))
        d.update({"topic": t, **g})
        d["check"] = check(d, R)
        bad = d["check"]
        if bad["lines_without_fact"] or bad["unsourced_numbers"] or not bad["in_range"] or bad["polite_endings"]:
            fix = (p + "\n\n방금 쓴 대본: " + json.dumps({"lines": d.get("lines")}, ensure_ascii=False) +
                   "\n고칠 것: 근거 번호 없는 사실 줄 " + json.dumps(bad["lines_without_fact"], ensure_ascii=False) +
                   " → 조사 항목에 기대게 고치거나 빼라(꾸밈말 금지) / 근거 없는 숫자 " + json.dumps(bad["unsourced_numbers"]) +
                   f" / 길이 {bad['chars']}자 → {lo}~{hi}자 / 존댓말 {bad['polite_endings']}개 → 0. 같은 JSON 꼴로 다시.")
            d2 = seedflow.parse(call(fix))
            d2.update({"topic": t, **g, "first_draft": d.get("lines")})
            d2["check"] = check(d2, R)
            d = d2
        out.append(d)
        print(f"제목: {d.get('title')}")
        for ln in d.get("lines", []):
            print(f"  ({ln['fn']}) {ln['text']}  {ln.get('facts') or ''}")
        print("  검사:", d["check"])
    return out


def _ngrams(s: str, n: int = 8) -> set:
    s = re.sub(r"\s+", "", s)
    return {s[i:i + n] for i in range(len(s) - n + 1)}


# ── 베낌(원본·벤치와 겹침) 판정 — 주인 한 곳(10-16 조율자: 5글자 겹침은 관용구 '인 줄 알았는'까지 잡았다, 창고 sseolpulda/16) ──
COPY_MIN_CHARS = 7        # 공백 뺀 연속 7자 이상 같으면 베낌
COPY_MIN_WORDS = 3        # 또는 연속 어절 3개 이상 같으면 베낌
COPY_IDIOMS = ("인 줄 알았는데", "알고 보니", "솔직히", "근데")   # 채널 공통 말버릇 — 겹침에서 뺀다


def _copy_norm(t: str) -> str:
    t = t or ""
    for idm in COPY_IDIOMS:
        t = t.replace(idm, " | ").replace(idm.replace(" ", ""), " | ")
    return re.sub(r"[^\w|\s]", " ", t)


def _copy_grams(t: str, n: int) -> set:
    out = set()
    for part in _copy_norm(t).split("|"):
        z = re.sub(r"\s+", "", part)
        out |= {z[i:i + n] for i in range(len(z) - n + 1)}
    return out


def _word_runs(t: str, n: int) -> set:
    out = set()
    for part in _copy_norm(t).split("|"):
        w = part.split()
        out |= {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}
    return out


def copied_from(texts: list[str], sources: list[str]) -> dict:
    """(판단 주인) 줄마다 원본·벤치 문장을 베꼈나 → {줄: 겹친 조각}. 연속 COPY_MIN_CHARS 자 또는 연속 COPY_MIN_WORDS 어절이 같으면 베낌.
    COPY_IDIOMS(말버릇)는 양쪽에서 빼고 잰다."""
    g = set().union(*(_copy_grams(t, COPY_MIN_CHARS) for t in sources)) if sources else set()
    w = set().union(*(_word_runs(t, COPY_MIN_WORDS) for t in sources)) if sources else set()
    out = {}
    for k, t in enumerate(texts):
        hit = sorted(_copy_grams(t, COPY_MIN_CHARS) & g) or [" ".join(x) for x in sorted(_word_runs(t, COPY_MIN_WORDS) & w)]
        if hit:
            out[k] = hit[0]
    return out


def check(d: dict, R: dict) -> dict:
    """같은 자로 잰다: 길이 범위 · 박자 순서 · 존댓말 · 예문 베낌(8글자 겹침)."""
    text = " ".join(l["text"] for l in d.get("lines", []))
    n = len(text.replace(" ", ""))
    fns = [l["fn"] for l in d.get("lines", [])]
    order = [ORDER.index(f) for f in fns if f in ORDER]
    ex = set().union(*(_ngrams(e["script"]) for e in R["examples"]))
    copied = sorted(_ngrams(text) & ex)
    ids = {f["id"] for f in d.get("facts") or []}
    facts_text = " ".join(f["text"] for f in d.get("facts") or [])
    nums = re.findall(r"\d[\d,.]*", text)
    unsourced_nums = [n for n in nums if n not in facts_text]
    bad_ids = sorted({i for l in d.get("lines", []) for i in (l.get("facts") or []) if i not in ids})
    # 근거 번호 없이 사실을 말하는 줄 — 훅·의문·댓글유도만 근거 없이 둘 수 있다
    bare = [l["text"] for l in d.get("lines", []) if not l.get("facts") and l.get("fn") not in ("훅", "의문", "댓글유도")]
    polite = len(re.findall(r"(습니다|어요|아요|해요|세요)[.!?]?(\s|$)", text))
    return {"chars": n, "in_range": R["length_chars"]["p25"] <= n <= R["length_chars"]["p75"],
            "sec_est": round(n / CPS, 1), "first_is_hook": bool(fns) and fns[0] == "훅",
            "order_breaks": sum(1 for a, b in zip(order, order[1:]) if b < a - 1),
            "polite_endings": polite, "unsourced_numbers": unsourced_nums, "unknown_fact_ids": bad_ids, "lines_without_fact": bare, "copied_8grams": len(copied), "copied_sample": copied[:3]}


# ── 대본 규칙 문장 — 판단 주인 한 곳(0순위-B, 10-16 조율자: script_engine.DRAFT_PROMPT 와 두 벌이었다) ──────────
# 프롬프트마다 같은 규칙을 따로 적지 말고 이 문장을 끼워 쓴다. script_engine 은 DRAFT_PROMPT·FIX_PROMPT 를 여기서 가져간다.
def rule_fact_ids(ids: str = "위 [f…]·[b…]") -> str:
    """근거 번호 규칙 — 줄마다 facts 에 근거 번호, 근거 밖 사실·숫자 금지(10-16 rGFX 반려: 지어낸 후기)."""
    return f"- 줄마다 facts 에 근거 번호({ids})를 1개 이상 적어라. 근거 없는 사실·숫자·이름·회사·연도를 지어내지 마라. 숫자는 [f…] 사실에 있는 그대로만."


RULE_NO_DESCRIBE = "- 화면을 묘사하지 마라(×'…하는 중' ×'웃음이 남' ×'소리가 흘러나옴'). 시청자에게 썰 푸는 말."   # 10-16 ZdeZ 반려
RULE_ENDING = "- 말끝이 적힌 칸은 그 글자로 문장을 끝낸다(자르지 마라)."                                          # 10-16 말끝 잘림
RULE_NO_COPY_BENCH = "- 벤치 영상·원본 문장을 베끼지 마라 — 포인트(각도·반전·반응)만 가져오고 문장은 새로."
RULE_NO_BRAND = "- 소재·근거(f*)에 없는 브랜드·제품명을 쓰지 않는다."                                                   # 10-16 엔진 담당 요청
RULE_KEEP_SPACES = "- 글자 수를 맞추려고 띄어쓰기를 지우지 않는다 — 폭이 넘치면 낱말을 줄인다."                       # 10-16 실측: '울트라나온다길래안믿었는데'
RULE_NO_SUPERLATIVE = "- 최상급·단정(가장·제일·최초·유일·세계에서·절대·역대급·1위·전설)은 그 줄 근거 글에 같은 주장이 있을 때만 쓴다."   # 10-16 다이소 c3 '절대 먹지 말라고'·'역대급으로'


DRAFT_PROMPT = ("""너는 한국 쇼츠 채널 '{slug}'의 {kind} 작가다. 소재 하나로 이 채널 틀 그대로 새 대본을 써라.

소재: {topic}
썰 각도(후보표): {angle}

쓸 수 있는 근거(이것만 — 번호를 줄마다 facts 에 적는다):
{grounds}

칸(정확히 {n}줄, 순서대로, 칸마다 역할·말끝·글자 수(공백 제외)):
{slots}

규칙:
- {honor}. {honor_rule}
""" + rule_fact_ids() + "\n" + RULE_NO_DESCRIBE + """
- 과장·꾸밈 말투는 괜찮다(이 채널 스타일). 단 근거 밖 사실은 금지.
""" + RULE_NO_COPY_BENCH + "\n" + RULE_ENDING + "\n" + RULE_NO_BRAND + "\n" + RULE_KEEP_SPACES + "\n" + RULE_NO_SUPERLATIVE + """
원본(이 채널 실제 영상, 구조 참고 — 베끼지 마라):
{orig}
출력 JSON만: {{"angle":"이 대본의 썰 각도 한 줄","twist":"반전이 몇 번째 줄인지와 무엇인지","title":"영상 위 제목(줄바꿈 \\n)",
"lines":[{{"fn":"칸 역할","text":"한 줄","facts":["f1"]}}, …]}}""")

FIX_PROMPT = """방금 쓴 대본에서 틀린 줄만 고친다. 나머지 줄은 그대로 둔다.
지금 대본: {lines}
고칠 줄(번호는 1부터):
{fixes}
같은 규칙(근거 번호 필수·지어낸 사실 금지·화면 묘사 금지·{honor}·칸 말끝·글자 수)을 지켜라.
출력 JSON만: {{"lines":[{{"i":번호,"fn":"칸 역할","text":"고친 줄","facts":["f1"]}}, …]}}  (고친 줄만)"""

# ── 대본 설명서(script_frame) 경로 — script_engine.draft 가 brief() 를 채워 쓴다(관제 097, 10-16 밤 3판) ──
# 창작 허용선(설명서 2판): 화자·지인·계기·감상·비유·과장은 지어내도 되고, 제품 속성·수치·사회적 반응·가격은 근거 번호 필수.
RULE_CREATIVE_LINE = ("- [창작 허용선] 화자 설정·지인·가족·계기·극단 행동·자기 위치·감상·체감 비유·결과 과장은 지어내도 된다(이 채널의 결). "
                      "제품 속성·원리·수치·쓰면 생기는 효과·사회적 반응(인기·품절·유행)·가격을 말하는 줄은 근거 번호 필수 — 근거 글에 없는 효과·속도·가격 표현을 덧붙이지 마라.")
FRAME_DRAFT_PROMPT = ("""너는 한국 쇼츠 채널 '{slug}'의 나레이션 작가다. 아래 [설명서] 결대로 상품 하나로 새 대본을 써라.
상품: {product}
[서사] 이 채널은 체험담형(구체 인물 계기: 와이프·친구·엄마가 보여줌/선물 + 극단 행동 + 자기 위치 + 결과 과장) 또는 전언해설형('~대요/~다는데')으로 말한다.
노드 출현율(원본): {nodes}. 계기·극단행동은 맨 앞, 체감비유는 가운데. **마지막 줄은 결과과장 노드**(쓴 뒤 달라진 삶을 과장 — 범용 권유 '써보세요'로 끝내지 마라).
속성 다음에는 '나에게 생긴 변화(체감·결과)'로 넘긴다. 체감 비유(A 같다, A vs B) 1개 이상. 첫 문장은 말이 되는 한 사건이어야 한다(계기와 극단 행동을 억지로 한 문장에 붙이지 마라).
[칸] {slots}  · 첫 문장 유형 {hooks}
[고른 사실] 이것을 중심으로(원리·스펙 사실은 {cap}개 이하): {picked}
[쓸 수 있는 근거 — 번호를 줄마다 facts 에 적는다(창작 줄은 빈 목록)]
{grounds}
[화법] 어미 {endings} 안에서만({foreign} 금지). 연결어미({conn})로 이어 쓴다 — 문장당 약 {cps}개. 전체 약 {chars}자, 문장 {nsent}개 안팎.
규칙:
""" + RULE_CREATIVE_LINE + "\n- 근거 없는 제품 사실·숫자·이름·회사·연도를 지어내지 마라. 숫자는 [f…] 사실에 있는 그대로만.\n" + RULE_NO_DESCRIBE + "\n" + RULE_NO_BRAND + "\n" + RULE_KEEP_SPACES + "\n"
                      + RULE_NO_SUPERLATIVE + """
- [예문]은 설명 방식만 참고하고, 예문과 공백 뺀 7자 이상 같은 구절을 쓰지 마라.
[예문]
{examples}
출력 JSON만: {{"title":"영상 위 제목","lines":[{{"text":"한 문장","node":"계기|극단행동|자기위치|불편공감|원리스펙|체감비유|체감사실|결과과장|사회반응|가격|감상|권유","facts":["f1"],"creative":true}}, …]}}""")
# 설명서 없는 채널(폴백, 경보와 함께) — 역할 칸(script_engine.ROLES[slug] 또는 DEFAULT_ROLES)만으로
FRAME_FALLBACK_PROMPT = ("""너는 한국 쇼츠 채널 '{slug}'의 나레이션 작가다. 상품 하나로 대본을 써라(이 채널 대본 설명서가 아직 없다 — 역할 칸만 따른다).
상품: {product}
칸(순서대로 한 줄씩): {slots}
[쓸 수 있는 근거]
{grounds}
규칙:
""" + rule_fact_ids("위 [f…]") + "\n" + RULE_NO_DESCRIBE + "\n" + RULE_NO_BRAND + "\n" + RULE_KEEP_SPACES + "\n" + RULE_NO_SUPERLATIVE + """
출력 JSON만: {{"title":"영상 위 제목","lines":[{{"fn":"칸 역할","text":"한 줄","facts":["f1"]}}, …]}}""")


CAP_PROMPT = """너는 한국 쇼츠 채널 '{style}' 갈래의 자막 작가다. 이 영상은 **한국어 나레이션이 없다** — 해외 원본 영상 위에 자막만 얹는다.
그래서 대본 = 화면 아래 자막 {n}줄이다. 한 줄이 한 화면(3~4초) 동안 떠 있다.

소재(제품): {topic}
같은 소재 해외 영상에서 나온 포인트(써도 됨, 지어내지는 마라): {points}

원본 자막 {n}줄의 **역할**(이 칸 순서·역할·말끝·길이만 따라 하고 문장은 새로 써라):
{structure}

규칙:
""" + RULE_NO_DESCRIBE + """
  화면은 줄마다 참고로만 준다 — 화면과 어긋나는 말(없는 물건·장소)만 피하면 된다.
- 반말. 칸마다 적힌 말끝으로 문장을 **끝낸다**(말끝 ~길래 → '…보이길래'처럼 그 글자가 문장 맨 끝. 글자를 자르거나 빼지 마라). 존댓말(습니다·어요·해요·세요) 0. 유치한 말('짱'·'대박짱'·'ㅋㅋ' 남발) 금지.
- 줄마다 글자 수(공백 제외)는 위 목표 범위 안. 쓰고 나서 직접 세어 확인해라.
- 사람이 실제로 쓸 법한 자연스러운 문장. 뜻이 어색한 말·억지 줄임말 금지.
- 원본 자막 문장을 베끼지 마라 — 원본과 5글자 넘게 이어서 같으면 실패다.
- 제품 사연(발명가·회사·탄생 비화)·가격·출력(W)·브랜드명·숫자는 쓰지 마라(확인 안 된 사실).
JSON으로만: {{"lines":[{{"fn":"역할","text":"자막"}}, ...]}}  (정확히 {n}줄)
"""

DESCRIBE_ENDS = ("하는 중", "는 중", "이 남", "가 남", "나옴", "흘러나옴")   # 화면 묘사 말끝(10-16 반려: '신기해서 웃음이 남')
OFF_TONE = ("짱",)                                                       # 채널 톤 밖(10-16 반려)


CAP_TOL = 0.15   # 줄 글자 수 허용(원본 그 줄 ±15%, 최소 ±1자) — ±30% 로는 대조 '줄 폭 중앙 ≤6%'를 못 맞췄다(10-16 실측 541 vs 583px)


def _cap_range(b: int) -> tuple[int, int]:
    import math
    # 긴 줄(≥14자)은 원본보다 길게 쓰지 않는다 — 17자 줄이 원본 16자보다 넓어 자막 띠 잉크 비율 0.167 vs 0.141(10-16 실측)
    hi = b if b >= 14 else max(b + 1, math.floor(b * (1 + CAP_TOL)))
    return min(b - 1, math.ceil(b * (1 - CAP_TOL))), hi


def _ngrams_n(s: str, n: int) -> set:
    s = re.sub(r"\s+", "", s)
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def line_ranges(orig: list[str], widths: list | None = None, px_per_char: float | None = None) -> list[tuple[int, int]]:
    """줄마다 허용 글자 수(공백 제외) — 판단 주인 한 곳.
    px_per_char 와 원본 줄 폭(뜯기 captions.items.widths)이 있으면 **폭 기준**: 목표 = 원본 폭 ÷ px_per_char, 범위 = [내림, 올림].
    (10-16 실측: 글자 수 ±15%로 맞춰도 '바이럴인 줄 알았는데...'처럼 점·공백이 많은 줄은 폭이 달라 줄 폭 중앙이 7.1% 밖이었다)
    없으면 원본 글자 수 기준 _cap_range."""
    import math
    out = []
    for k, t in enumerate(orig):
        w = (widths or [None] * len(orig))[k] if widths else None
        if px_per_char and w:
            tgt = w / px_per_char
            out.append((math.floor(tgt), max(math.floor(tgt), math.ceil(tgt))))
        else:
            out.append(_cap_range(len(t.replace(" ", ""))))
    return out


# 자막 쓰기 모델 — 10-16 gemini-3.5-flash 는 키 14개 전부 429(일일 한도 소진, 키 돌리기는 정상), lite 는 글 길이·말끝을 못 지켰다.
# 무료 키로 되는 상위 모델 순서(10-16 실측 OK: 3-flash-preview·flash-latest)
CAP_MODELS = ("gemini-flash-latest", "gemini-3-flash-preview", "gemini-flash-latest", "gemini-3-flash-preview", "gemini-flash-latest", "gemini-flash-lite-latest")
CAP_W_TOL = 0.10   # 폭 기준일 때 줄마다 원본 폭 ±10% — ±6%(대조 기준)는 lite 모델이 12개 후보 중 하나도 못 맞췄다(10-16). 중앙값은 width_median_pct 로 따로 잰다


def width_estimator(frame_path: str):
    """틀 설명서(frame.json)의 자막 층(글꼴·크기·자간·낱말 간격) → 글 → 렌더 잉크 폭(px) 추정 함수.
    폭 모형은 to_frame._css_line 하나(자간·낱말 간격을 정한 그 모형 — 렌더러 CSS 와 같은 규칙)를 그대로 쓴다.
    (10-16 1판은 'PIL 폭×0.843' 배율이었는데 낱말 간격을 바꾸면 배율이 틀어진다 → 틀 값으로 직접 계산)"""
    from tools.calcopy.engine import to_frame
    f = json.loads(Path(frame_path).read_text(encoding="utf-8"))
    cap = next(l for l in f["layers"] if l.get("kind") == "text" and l.get("role") == "caption")
    font = to_frame._pil_font(cap["font"], float(cap["size"]))
    ls, ws = float(cap.get("letter_spacing") or 0), float(cap.get("word_spacing") or 0)
    return lambda t: round(to_frame._css_line(font, t, ls, ws)[0])


def _core(t: str) -> str:
    return t.strip().rstrip("~;?!. ")


def ends_of(fns: list[str]) -> list[str | None]:
    """역할 칸 '… · 말끝 ~길래' → '길래'(문장이 이걸로 끝나야 한다). 없으면 None."""
    out = []
    for f in fns:
        m = re.search(r"말끝\s*~?(\S+)", f)
        out.append(m.group(1) if m else None)
    return out


def check_captions(lines: list[dict], orig: list[str], R: dict, ranges: list | None = None, width: dict | None = None,
                   ends: list | None = None) -> dict:
    """자막 대본을 같은 자로 잰다 — 줄 수 · 줄 길이(원본 ±CAP_TOL) · 존댓말 · 원본 자막과 5글자 겹침 · 갈래 예문과 8글자 겹침 · 숫자."""
    text = " ".join(l["text"] for l in lines)
    o5 = set().union(*(_ngrams_n(t, 5) for t in orig))
    copied5 = sorted({g for l in lines for g in _ngrams_n(l["text"], 5)} & o5)
    copied_lines = sorted(copied_from([l["text"] for l in lines], orig))   # 줄 단위 판정 = copied_from(5글자 집합 copied5 는 참고로만 남긴다)
    ex8 = set().union(*(_ngrams(e["script"]) for e in R["examples"]))
    lens = [len(l["text"].replace(" ", "")) for l in lines]
    olens = [len(t.replace(" ", "")) for t in orig]
    ranges = ranges or [_cap_range(b) for b in olens]
    off = [i for i, (a, r) in enumerate(zip(lens, ranges)) if not (r[0] <= a <= r[1])]
    est = None
    if width:   # 폭 기준이면 글자 수 범위는 힌트일 뿐 — 판정은 추정 렌더 폭
        est = [width["est"](l["text"]) for l in lines]
        off = [i for i, (e, w) in enumerate(zip(est, width["orig"])) if w and abs(e - w) / w > CAP_W_TOL]
    polite = len(re.findall(r"(습니다|어요|아요|해요|세요)[.!?]?(\s|$)", text))
    describe = [i for i, l in enumerate(lines) if l["text"].rstrip("?!.;~ ").endswith(DESCRIBE_ENDS)]
    off_tone = [w for w in OFF_TONE if w in text]
    # 말끝 — 10-16 lite 모델이 '말끝 ~는데'를 잘라 '싶었는'·'대기만 하'로 끝냈다 → 말끝으로 끝나는지 잰다
    ending_off = [i for i, (l, e) in enumerate(zip(lines, ends or [])) if e and not _core(l["text"]).endswith(_core(e))]
    wmed = None
    if est:
        import statistics as _st
        wmed = round((_st.median(est) - _st.median(width["orig"])) / _st.median(width["orig"]) * 100, 1)
    return {"n_lines": len(lines), "n_ok": len(lines) == len(orig), "width_median_pct": wmed, "describe_lines": describe, "copied_lines": copied_lines, "ending_off": ending_off, "off_tone": off_tone, "chars": lens, "orig_chars": olens, "ranges": [list(r) for r in ranges], "est_px": est, "orig_px": (width or {}).get("orig"), "len_off_lines": off,
            "polite_endings": polite, "copied_5grams_vs_orig": copied5, "copied_8grams_vs_examples": len(_ngrams(text) & ex8),
            "numbers": re.findall(r"\d[\d,.]*", text)}


def _cap_fix(prev: dict) -> str:
    """직전 답의 검사 결과를 줄 번호·목표 글자 수로 바꿔 말한다(막연한 '다시'는 같은 답이 돌아온다)."""
    c = prev.get("check") or {}
    out = []
    for i in c.get("len_off_lines") or []:
        lo, hi = c["ranges"][i]
        if c.get("est_px"):
            e, w = c["est_px"][i], c["orig_px"][i]
            out.append(f"{i + 1}번 줄이 화면에서 {e}px → {w}px 쯤이어야({'짧게' if e > w else '길게'}, 약 {lo}~{hi}자)")
        else:
            out.append(f"{i + 1}번 줄 {c['chars'][i]}자 → {lo}~{hi}자(공백 제외)")
    if c.get("polite_endings"):
        out.append(f"존댓말 {c['polite_endings']}개 → 0")
    if c.get("copied_5grams_vs_orig"):
        out.append(f"원본과 겹친 조각 {c['copied_5grams_vs_orig']} → 다른 말로")
    if c.get("numbers"):
        out.append(f"숫자 {c['numbers']} → 빼라")
    if c.get("ending_off"):
        out.append(f"{[i + 1 for i in c['ending_off']]}번 줄이 정해진 말끝으로 안 끝남(말끝 글자를 자르지 말고 온전히 붙여라)")
    if c.get("describe_lines"):
        out.append(f"{[i + 1 for i in c['describe_lines']]}번 줄이 화면 묘사 → 시청자에게 썰 푸는 말로")
    if c.get("off_tone"):
        out.append(f"톤 밖 낱말 {c['off_tone']} → 빼라")
    return " / ".join(out)


def _cap_ok(chk: dict) -> bool:
    return bool(chk.get("n_ok")) and not chk.get("len_off_lines") and not chk.get("polite_endings") and not chk.get("copied_lines")         and not chk.get("copied_8grams_vs_examples") and not chk.get("numbers") and not chk.get("describe_lines") and not chk.get("off_tone") and not chk.get("ending_off")


def write_captions(rules_path: str, ttj_path: str, topic: str, fns: list[str], scenes: list[str] | None = None,
                   px_per_char: float | None = None, width_spec: str | None = None, points: str = "") -> dict:
    """나레 없는(원음만+자막) 영상용 — 원본 자막 줄 구조를 틀로 우리 자막 N줄을 쓴다. 무료 제미나이 창구(gemini_free)만 쓴다."""
    from tools.calcopy.engine import gemini_free
    R = json.loads(Path(rules_path).read_text(encoding="utf-8"))
    J = json.loads(Path(ttj_path).read_text(encoding="utf-8"))
    items = {i["i"]: " ".join(i.get("text") or []) for i in J["captions"]["items"]}
    spans = J["captions"]["spans"]
    orig = [items.get(k, "") for k in range(len(spans))]
    widths = [((J["captions"]["items"][k].get("widths") or [None])[0] if k < len(J["captions"]["items"]) else None) for k in range(len(orig))]
    rng = line_ranges(orig, widths, px_per_char)
    EN = ends_of(fns)
    W = {"est": width_estimator(width_spec), "orig": widths} if width_spec and all(widths) else None
    structure = "\n".join(f"{k + 1}. 역할={fns[k]} · 목표 {rng[k][0]}~{rng[k][1]}자(공백 제외) · {b - a:.1f}초" + (f" · 그때 화면(참고, 묘사 금지): {scenes[k]}" if scenes else "") for k, (t, (a, b)) in enumerate(zip(orig, spans)))
    prompt = CAP_PROMPT.format(style=R["style"], n=len(orig), topic=topic, structure=structure, points=points or "(없음)", honorific=R["tone"]["honorific"],
                               endings=", ".join(e for e, _ in R["tone"]["endings_seen"][:12]), hooks=" / ".join(R["hooks"][:8]))
    tries = []
    for k in range(3):
        d, err = gemini_free.ask([], prompt if not tries else prompt + "\n\n직전 답: " + json.dumps(tries[-1], ensure_ascii=False) +
                                 "\n검사 실패 — 고쳐서 같은 꼴로 다시. " + _cap_fix(tries[-1]), tag=f"captions{k}", models=CAP_MODELS)
        if not d:
            tries.append({"error": err}); continue
        lines = d.get("lines") or d.get("items") or []
        chk = check_captions(lines, orig, R, rng, W, EN)
        tries.append({"lines": lines, "check": chk, "model": d.get("_model")})
        if _cap_ok(chk):
            break
    # 글자 수만 어긋난 줄이 남으면 그 줄만 후보 여러 개를 받아 범위 안의 첫 것으로 바꾼다
    # (temperature 0 이라 전체 다시 쓰기는 같은 답·한 줄 왔다갔다만 했다 — 10-16 실측 5번 모두 5번 줄 5↔13자)
    PER_LINE = ("len_off_lines", "ending_off", "describe_lines", "copied_lines")

    def _rank(t):   # 줄 단위로 못 고치는 문제(겹침·존댓말·숫자·톤·줄 수)가 없는 것 먼저, 그다음 어긋난 줄이 적은 것
        c = t.get("check") or {}
        if not t.get("lines") or not c.get("n_ok"):
            return (9, 99)
        return (0 if _cap_ok({**c, **{k: [] for k in PER_LINE}}) else 1, len({i for k in PER_LINE for i in c.get(k) or []}))
    last = min(tries, key=_rank) if tries else {}
    chk = last.get("check") or {}
    bad = sorted({i for k in PER_LINE for i in chk.get(k) or []})
    if last.get("lines") and chk.get("n_ok") and bad and _cap_ok({**chk, **{k: [] for k in PER_LINE}}):
        lines = [dict(l) for l in last["lines"]]
        for i in bad:
            lo, hi = chk["ranges"][i]
            q = (prompt + "\n\n지금 대본: " + json.dumps([l["text"] for l in lines], ensure_ascii=False) +
                 f"\n{i + 1}번 줄(역할 {fns[i]}" + (f", 그때 화면: {scenes[i]}" if scenes else "") +
                 f")만 다른 말로 12가지 써라. 각각 공백 빼고 {lo}~{hi}자" + (f"(화면 폭 약 {W['orig'][i]}px)" if W else "") + (f", 문장은 '{EN[i]}' 로 끝낸다(말끝을 자르지 마라)" if EN[i] else "") + (f". 원본 자막 {json.dumps(orig, ensure_ascii=False)} 과 5글자 넘게 같은 말 금지" if i in chk.get("copied_lines", []) else "") + f". 화면 묘사 말고 시청자에게 썰 푸는 말. JSON으로만: {{\"alts\":[\"…\", …]}}")
            d, err = gemini_free.ask([], q, tag=f"captions_line{i}", models=CAP_MODELS)
            # 말끝·묘사·겹침이 맞는 후보 중 목표 폭에 가장 가까운 것(범위 안이면 그대로 통과, 밖이어도 지금 줄보다 가까우면 바꾼다)
            def _dist(c, k=i):
                return abs(c["est_px"][k] - W["orig"][k]) if W and c.get("est_px") else abs(c["chars"][k] - sum(c["ranges"][k]) / 2)
            cur = check_captions(lines, orig, R, rng, W, EN)
            hard = any(i in cur[k] for k in ("ending_off", "describe_lines", "copied_lines"))   # 길이 말고 틀린 줄은 지금 줄을 버린다
            best = (float("inf") if hard else _dist(cur), lines)
            for alt in (d or {}).get("alts") or (d or {}).get("items") or []:
                if not isinstance(alt, str):
                    continue
                trial = lines[:i] + [{**lines[i], "text": alt}] + lines[i + 1:]
                c2 = check_captions(trial, orig, R, rng, W, EN)
                if i in c2["ending_off"] or i in c2["describe_lines"] or i in c2["copied_lines"] or c2["polite_endings"] or c2["numbers"] or c2["off_tone"]:
                    continue
                if _dist(c2) < best[0]:
                    best = (_dist(c2), trial)
            lines = best[1]
        chk = check_captions(lines, orig, R, rng, W, EN)
        tries.append({"lines": lines, "check": chk, "model": "line_repair"})
    return {"topic": topic, "orig": orig, "spans": spans, "fns": fns, "scenes": scenes, "ranges": rng, "px_per_char": px_per_char, "width_spec": width_spec, "points": points, "final": tries[-1], "tries": tries,
            "gemini_calls": gemini_free.CALLS}



NARR_PROMPT = """너는 한국 쇼츠 채널의 나레이션 작가다. 원본 영상의 나레이션 **구조**(문장 수·역할·문장 길이·말투)만 따라 하고 문장은 새로 써라.

소재: {topic}
쓸 수 있는 사실(이것만 — 지어내지 마라): {points}

원본 나레이션 문장(구조 참고용, 베끼지 마라):
{orig}

문장 {n}개를 써라. 문장마다 역할·목표 글자 수(공백 제외):
{structure}

규칙:
- 말투는 원본과 같은 반말 전언체(…했는데 / …다고 함 / …던 것 / …했다고). 존댓말(습니다·어요·해요·세요) 0.
- 원본 문장과 8글자 넘게 이어서 같으면 실패다. 같은 사실도 다른 말로.
- 위 '쓸 수 있는 사실'에 없는 숫자·이름·사건을 지어내지 마라.
""" + rule_fact_ids("위 [f…]·[o…]·[c…]") + """ 사실 번호 없이 평가·반응을 말하지 마라.
JSON으로만: {{"lines":[{{"fn":"역할","text":"문장","facts":["f1"]}}, ...]}}  (정확히 {n}개)
"""


def check_narration(lines: list[dict], orig: list[str], ranges: list, facts: str) -> dict:
    """나레이션 문장을 잰다 — 문장 수 · 글자 수(범위) · 존댓말 · 원본과 8글자 겹침 · 사실 밖 숫자."""
    text = " ".join(l["text"] for l in lines)
    copied = sorted(copied_from([l["text"] for l in lines], orig))
    lens = [len(l["text"].replace(" ", "")) for l in lines]
    off = [i for i, (a, r) in enumerate(zip(lens, ranges)) if not (r[0] <= a <= r[1])]
    polite = len(re.findall(r"(습니다|어요|아요|해요|세요)[.!?]?(\s|$)", text))
    nums = [n for n in re.findall(r"\d[\d,.]*", text) if n not in facts]
    ids = set(re.findall(r"\[([a-z]\d+)\]", facts))   # 사실 f·원본 영상 o·댓글 c 번호
    no_fact = [i for i, l in enumerate(lines) if ids and not (set(l.get("facts") or []) & ids)]   # 10-16 반려: 근거 없는 평가 문장
    return {"n_ok": len(lines) == len(orig), "lines_without_fact": no_fact, "chars": lens, "ranges": [list(r) for r in ranges], "len_off_lines": off,
            "copied_lines": copied, "polite_endings": polite, "unsourced_numbers": nums}


def write_narration(ttj_path: str, topic: str, roles: list[str], points: str = "", models: tuple | None = None) -> dict:
    """나레이션 있는 영상용 — 원본 받아쓰기(뜯기 audio.transcript) 문장 구조를 틀로 우리 나레이션을 쓴다(무료 제미나이만)."""
    from tools.calcopy.engine import gemini_free
    J = json.loads(Path(ttj_path).read_text(encoding="utf-8"))
    tr = (J.get("audio") or {}).get("transcript") or []
    tr = tr.get("segments") or [] if isinstance(tr, dict) else tr
    segs = [t for t in tr if isinstance(t, dict) and t.get("lang", "ko") == "ko"]
    orig = [t["text"].strip() for t in segs]
    olens = [len(t.replace(" ", "")) for t in orig]
    ranges = [(int(b * 0.9), int(b * 1.1) + 1) for b in olens]
    structure = "\n".join(f"{k + 1}. 역할={roles[k] if k < len(roles) else '-'} · 목표 {ranges[k][0]}~{ranges[k][1]}자" for k in range(len(orig)))
    prompt = NARR_PROMPT.format(topic=topic, points=points or "(없음)", orig="\n".join(f"- {t}" for t in orig), n=len(orig), structure=structure)
    tries = []
    for k in range(3):
        fix = ""
        if tries and tries[-1].get("check"):
            c = tries[-1]["check"]
            fix = ("\n\n직전 답: " + json.dumps([l["text"] for l in tries[-1]["lines"]], ensure_ascii=False) +
                   f"\n고칠 것: 글자 수 어긋난 문장 {[i + 1 for i in c['len_off_lines']]} (목표 범위로) / 원본과 겹친 문장 {[i + 1 for i in c['copied_lines']]} / "
                   f"존댓말 {c['polite_endings']} / 사실 밖 숫자 {c['unsourced_numbers']} / 사실 번호 없는 문장 {[i + 1 for i in c['lines_without_fact']]}")
        d, err = gemini_free.ask([], prompt + fix, tag=f"narr{k}", models=models or CAP_MODELS)
        if not d:
            tries.append({"error": err}); continue
        lines = d.get("lines") or d.get("items") or []
        c = check_narration(lines, orig, ranges, points + topic)
        tries.append({"lines": lines, "check": c, "model": d.get("_model")})
        if c["n_ok"] and not c["len_off_lines"] and not c["copied_lines"] and not c["polite_endings"] and not c["unsourced_numbers"] and not c["lines_without_fact"]:
            break
    ok = [t for t in tries if t.get("check")]
    best = min(ok, key=lambda t: (not t["check"]["n_ok"], len(t["check"]["copied_lines"]) + t["check"]["polite_endings"] * 3
                                   + len(t["check"]["unsourced_numbers"]) * 3 + len(t["check"]["lines_without_fact"]) * 3, len(t["check"]["len_off_lines"]))) if ok else (tries[-1] if tries else {})
    return {"topic": topic, "orig": orig, "roles": roles, "points": points, "final": best, "tries": tries, "gemini_calls": gemini_free.CALLS}


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "rules":
        build_rules(*sys.argv[2:5])
    elif cmd == "captions":   # captions <rules.json> <뜯기.json> <주제> <역할,역할,…> <출력.json> ["줄별 화면|…"] [px_per_char] [frame.json(폭 추정)] ["같은 소재 포인트"]
    # 역할 칸은 쉼표로: "발견 맥락(어디서 보고 알게 됐나) · 말끝 ~길래,…" — 원본 자막 줄마다 하나
        res = write_captions(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5].split(","), sys.argv[7].split("|") if len(sys.argv) > 7 and sys.argv[7] else None,
                             float(sys.argv[8]) if len(sys.argv) > 8 and sys.argv[8] else None, sys.argv[9] if len(sys.argv) > 9 else None,
                             sys.argv[10] if len(sys.argv) > 10 else "")
        Path(sys.argv[6]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        for ln in (res["final"].get("lines") or []):
            print(f"  ({ln.get('fn')}) {ln.get('text')}")
        print("  검사:", res["final"].get("check") or res["final"])
    elif cmd == "narration":   # narration <뜯기.json> <주제> <역할,…> <출력.json> ["쓸 수 있는 사실"]
        res = write_narration(sys.argv[2], sys.argv[3], sys.argv[4].split(","), sys.argv[6] if len(sys.argv) > 6 else "")
        Path(sys.argv[5]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        for ln in (res["final"].get("lines") or []):
            print(f"  ({ln.get('fn')}) {ln.get('text')}")
        print("  검사:", res["final"].get("check"))
    elif cmd == "write":
        res = write(sys.argv[2], sys.argv[3:])
        Path(sys.argv[2]).with_name("시험대본_" + Path(sys.argv[2]).stem.split(".")[0] + ".json").write_text(
            json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
