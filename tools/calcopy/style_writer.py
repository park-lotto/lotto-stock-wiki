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
- 사실이 확실하지 않은 숫자·회사명·연도는 지어내지 말고 빼라.
예문(조회 상위):
{examples}
출력 JSON만: {{"title":"영상 위 제목 2줄(줄바꿈 \\n)","lines":[{{"fn":"훅|정체공개|상황|의문|반전|원리|덤|결말|댓글유도","text":"한 문장"}}],"facts_to_check":["확인이 필요한 사실"]}}"""


def _client():
    from shopping_shorts.channelkit.providers import _gemini_client
    return _gemini_client(None, str(ROOT / ".env"))


def write(rules_path: str, topics: list[str]) -> list[dict]:
    from google.genai import types
    R = json.loads(Path(rules_path).read_text(encoding="utf-8"))
    ex = "\n\n".join(f"[{e['views']:,}회]\n" + "\n".join(f"({b['fn']}) {b['text']}" for b in e["beats"]) + f"\n전문: {e['script']}"
                     for e in R["examples"][:3])
    beats = " → ".join(f"{b['fn']}({b['start_ratio']:.0%})" for b in R["beats"])
    lo, hi = R["length_chars"]["p25"], R["length_chars"]["p75"]
    client, out = _client(), []
    for t in topics:
        p = PROMPT.format(topic=t, lo=lo, hi=hi, med=R["length_chars"]["median"], sec=R["seconds_at_cps"],
                          beats=beats, hooks=" / ".join(R["hooks"][:10]), examples=ex)
        r = client.models.generate_content(model="gemini-2.5-pro", contents=p,
                                           config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.8))
        d = json.loads(r.text)
        d["topic"] = t
        d["check"] = check(d, R)
        out.append(d)
        print(f"\n■ {t}\n제목: {d.get('title')}")
        for ln in d.get("lines", []):
            print(f"  ({ln['fn']}) {ln['text']}")
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
    polite = len(re.findall(r"(습니다|어요|아요|해요|세요)[.!?]?(\s|$)", text))
    return {"chars": n, "in_range": R["length_chars"]["p25"] <= n <= R["length_chars"]["p75"],
            "sec_est": round(n / CPS, 1), "first_is_hook": bool(fns) and fns[0] == "훅",
            "order_breaks": sum(1 for a, b in zip(order, order[1:]) if b < a - 1),
            "polite_endings": polite, "copied_8grams": len(copied), "copied_sample": copied[:3]}


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "rules":
        build_rules(*sys.argv[2:5])
    elif cmd == "write":
        res = write(sys.argv[2], sys.argv[3:])
        Path(sys.argv[2]).with_name("시험대본_" + Path(sys.argv[2]).stem.split(".")[0] + ".json").write_text(
            json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
