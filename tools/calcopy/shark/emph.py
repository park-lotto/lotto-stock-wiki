# -*- coding: utf-8 -*-
"""샥탬스토리 강조 낱말 자동 고르기 — 대본 줄의 자막 조각(caps)마다 '어느 덩어리를 무슨 색으로' (관제 097, 2026-10-18).

(판단 주인: 강조 덩어리·색) pick() 한 곳. 규칙 값은 rules.json emph 절(벤치 8편 256칸 판독 emph_read.json 에서 센 것).
편마다 손으로 고르지 않는다 — fill() 이 대본.json 줄마다 emph 칸을 채우고, 사람이 고친 칸(how='hand')은 건드리지 않는다.

    PYTHONUTF8=1 py tools/calcopy/shark/emph.py <편 폴더> [--dry]   # 대본.json final.lines[].emph 채움 + 표 출력
    PYTHONUTF8=1 py tools/calcopy/shark/emph.py --bench               # 벤치 256칸에 규칙을 돌려 종류·자리·비율이 벤치 분포와 맞나 대조
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.calcopy.shark.caption_style import rules  # noqa: E402


def _n(s: str) -> int:
    return len(re.sub(r"\s", "", s))


def kind_of(cap: str, line_kind: str) -> str:
    """칸 종류: 반응(원음 한 마디 감탄·질문) / 상황(*…*) / 보통."""
    E = rules()["emph"]
    c = cap.strip()
    if c.startswith("*") and c.endswith("*"):
        return "상황"
    if line_kind == "O" and _n(c) <= E["react_chars_le"] and (
            any(w in c for w in E["react_words"]) or c.endswith("?")):
        return "반응"
    return "보통"


def span_of(cap: str, line_kind: str) -> tuple[str, str]:
    """(덩어리, 까닭). 벤치 규칙: 짧은 칸·반응·상황 = 줄 전체 / 숫자 있으면 숫자 덩어리 / 아니면 서술 꼬리(약한 꼬리면 머리) 글자 비율 ≈ ratio_target."""
    E = rules()["emph"]
    words = cap.split(" ")
    k = kind_of(cap, line_kind)
    if k in E["whole_kinds"]:
        return cap, f"줄 전체({k})"
    if _n(cap) <= E["whole_if_chars_le"] or len(words) == 1 or (len(words) == 2 and _n(cap) <= E["whole_if_two_words_chars_le"]):
        return cap, f"줄 전체(≤{E['whole_if_chars_le']}자·한 낱말)"
    num = re.compile(E["number_re"])
    hit = [i for i, w in enumerate(words) if num.search(w)]
    if hit:
        a, b = hit[0], hit[-1]
        nxt = words[b + 1] if b + 1 < len(words) else ""
        if nxt and (words[b].endswith("의") or any(nxt.startswith(u) for u in E["unit_heads"])
                    or re.fullmatch(r"(한|두|세|네|다섯|열|몇)", words[b])):
            b += 1   # '4명의 투자자가' · '9만 달러' · '두 분이랑' · '수천 파운드죠'
        return " ".join(words[a:b + 1]), "숫자 덩어리"
    tgt = E["ratio_target"] * _n(cap)
    weak = words[-1] in E["weak_tail"] or len(words) >= 2 and _n(words[-1]) <= 1
    seq = list(range(len(words))) if weak else list(range(len(words) - 1, -1, -1))
    take, tot = [], 0
    for i in seq:
        if tot >= tgt * 0.85 or len(take) == len(words) - 1:
            break
        take.append(i); tot += _n(words[i])
    take.sort()
    return " ".join(words[take[0]:take[-1] + 1]), ("머리(꼬리 약함)" if weak else "서술 꼬리")


def color_seq(n: int, prev: str | None = None) -> list[str]:
    """색 순서: 벤치 색별 칸 수 비율대로 고르게(가중 라운드로빈) + 앞 칸과 같은 색 금지(no_repeat). 결정적."""
    E = rules()["emph"]
    cnt = E["color_counts"]
    tot = sum(cnt.values())
    acc = {c: 0.0 for c in cnt}
    out = []
    for _ in range(n):
        for c in acc:
            acc[c] += cnt[c] / tot
        cand = sorted(acc, key=lambda c: -acc[c])
        pick = next(c for c in cand if not (E["no_repeat"] and c == (out[-1] if out else prev)))
        acc[pick] -= 1.0
        out.append(pick)
    return out


def pick(lines: list[dict]) -> list[list[dict]]:
    """(판단 주인) 줄들([{kind:N|O, caps:[…]}]) → 줄마다 [{cap, span, color, whole, why}]. 색은 영상 전체 순서로 이어진다."""
    flat = [(li, c) for li, l in enumerate(lines) for c in l["caps"]]
    cols = color_seq(len(flat))
    out = [[] for _ in lines]
    for (li, c), col in zip(flat, cols):
        s, why = span_of(c, lines[li]["kind"])
        out[li].append({"cap": c, "span": s, "color": col, "whole": s == c, "why": why})
    return out


def fill(doc: Path, dry=False) -> list[list[dict]]:
    """대본.json final.lines[].emph 를 채운다(how='auto' 칸만 다시 씀, 사람이 고친 'hand' 칸은 그대로)."""
    p = doc / "대본.json"
    S = json.loads(p.read_text(encoding="utf-8"))
    L = S["final"]["lines"]
    norm = [{"kind": "O" if l.get("kind") in ("orig", "원음") else "N",
             "caps": l.get("caps") or [l.get("text") or l.get("tts")]} for l in L]
    res = pick(norm)
    for l, r in zip(L, res):
        old = l.get("emph") or []
        if old and all(e.get("how") == "hand" for e in old):
            continue
        l["emph"] = [{**e, "how": "auto", "rules": f"shark/rules.json v{rules()['version']}"} for e in r]
    if not dry:
        p.write_text(json.dumps(S, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return [l.get("emph") for l in L]


def bench_check():
    """벤치 256칸 판독에 규칙을 돌려 분포 대조(같은 칸을 얼마나 같게 고르나 + 종류 비율)."""
    R = json.loads((ROOT / "channel/foreignshowshow/preset/_hand/emph_read.json").read_text(encoding="utf-8"))["videos"]
    n = same_whole = same_span = 0
    for v, cells in R.items():
        for c in cells:
            if not c["colored"] or not c["colored"][0]:
                continue
            t = c["text"].replace(" / ", " ")
            k = "O" if c.get("cat") == "반응" else "N"
            s, _ = span_of(t, k)
            n += 1
            same_whole += (s == t) == bool(c["whole"])
            bench = c["colored"][0].replace(" / ", " ")
            same_span += s == bench or (bench in s and _n(bench) >= 0.7 * _n(s)) or (s in bench and _n(s) >= 0.7 * _n(bench))
    print(f"벤치 {n}칸: 전체/부분 판단 일치 {same_whole}/{n}({same_whole / n:.0%}) · 덩어리 일치(70% 겹침) {same_span}/{n}({same_span / n:.0%})")


def main():
    if sys.argv[1] == "--bench":
        bench_check(); return
    doc = Path(sys.argv[1])
    for l, em in zip(json.loads((doc / "대본.json").read_text(encoding="utf-8"))["final"]["lines"], fill(doc, "--dry" in sys.argv)):
        print(l["id"], " | ".join(f"{e['cap']}→[{e['span']}]{e['color']}" for e in em or []))


if __name__ == "__main__":
    main()
