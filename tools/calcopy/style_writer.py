# -*- coding: utf-8 -*-
"""갈래 규칙대로 대본 쓰기 — 주제 하나를 주면 그 갈래 말투·박자로 대본이 나온다 (관제 097, 2026-10-15).

    PYTHONUTF8=1 py tools/calcopy/style_writer.py rules  C:/숏템_칼카피/sseolpulda channel/sseolpulda 제품_이야기썰형
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
  이 각도가 훅·반전의 중심이 되게 써라. 각도 첫 줄 후보: {angle_hooks}
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
    facts = seedflow.research(topic, [], search_call)
    angle = seedflow.pick_angle(topic, [], facts, call)
    return {"facts": facts, "angle": angle}


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
        for f in g["facts"]:
            print(f"   {f['id']} ({f.get('kind')}) {f['text']}  [{seedflow.source_tier(f.get('source'))}]")
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
        out.append(d)
        print(f"제목: {d.get('title')}")
        for ln in d.get("lines", []):
            print(f"  ({ln['fn']}) {ln['text']}  {ln.get('facts') or ''}")
        print("  검사:", d["check"])
    return out


def _ngrams(s: str, n: int = 8) -> set:
    s = re.sub(r"\s+", "", s)
    return {s[i:i + n] for i in range(len(s) - n + 1)}


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
    polite = len(re.findall(r"(습니다|어요|아요|해요|세요)[.!?]?(\s|$)", text))
    return {"chars": n, "in_range": R["length_chars"]["p25"] <= n <= R["length_chars"]["p75"],
            "sec_est": round(n / CPS, 1), "first_is_hook": bool(fns) and fns[0] == "훅",
            "order_breaks": sum(1 for a, b in zip(order, order[1:]) if b < a - 1),
            "polite_endings": polite, "unsourced_numbers": unsourced_nums, "unknown_fact_ids": bad_ids, "copied_8grams": len(copied), "copied_sample": copied[:3]}


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "rules":
        build_rules(*sys.argv[2:5])
    elif cmd == "write":
        res = write(sys.argv[2], sys.argv[3:])
        Path(sys.argv[2]).with_name("시험대본_" + Path(sys.argv[2]).stem.split(".")[0] + ".json").write_text(
            json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
