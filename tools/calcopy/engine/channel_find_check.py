# -*- coding: utf-8 -*-
"""채널 찾기 엔진 결과물 검사 — 아는 정답과 대조 (2026-10-18, 관제 097).

정답(사장님·다른 세션 분석으로 이미 아는 것):
  같은 결    핫템리포트(@핫템리포트) · 썰풀다(@썰풀다)  — 해외 원본 + 한국어 나레 + 제품
  같은 결 아님 펀박스 · 앞북이 · 재밌쇼 · 갓성비스토리   — 게시글형 틀·AI 그림(channel/<slug>/스타일분석_*.md)
검사:
  1) 결과 json 에 정답 6채널이 다 있고, 같은 결 2개는 same_kind=True, 아님 4개는 same_kind=False(None 도 실패 — 판정 못 한 건 통과가 아니다)
  2) 같은 결 판정 채널은 근거(reason)·실측(n≥3, 조회 중앙)이 있고 한국어 채널이다
  3) 비용 장부(cost)가 있고 SerpApi 새 호출이 씨앗 수 이하(씨앗당 1회 상한)
  4) 해외 원본 후보 목록이 씨앗마다 있다(빈 목록 허용, 칸은 있어야 한다)
  5) 같은결_채널.json(채널 찾기 에이전트가 표본 2편으로 확정)이 있으면 엔진 결과 속 그 채널은 같은 결이어야 한다 — 못 찾은 수는 따로 보고
한 명령:
  py -m tools.calcopy.engine.channel_find_check channel/스타일분석/현장썰/채널수집/결과_엔진_1차.json
  py -m tools.calcopy.engine.channel_find_check --bad-judge always_true|title_only|always_false   # 엉터리 판정으로 다시 판정 → 빨강이 떠야 정상
종료 코드 0 = 초록, 1 = 빨강.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TRUTH_SAME = {"핫템리포트": "UCTGApFlRXaGUpy1KJwFAJTQ", "썰풀다": "UCL12SCB2y7J-KX0_ghAf-xQ"}
TRUTH_NOT = ("펀박스", "앞북이", "재밌쇼", "갓성비")
CONFIRMED = ROOT / "channel" / "스타일분석" / "현장썰" / "채널수집" / "같은결_채널.json"


def _find(channels, name, cid=None):
    for c in channels:
        if cid and c.get("channel_id") == cid:
            return c
    from tools.calcopy.engine.channel_find import TRUTH_PROBE
    ref = TRUTH_PROBE.get(name, "")
    for c in channels:
        h = (c.get("handle") or "").lstrip("@")
        if ref and h and ref.endswith("@" + h):
            return c
    return None


def check(res: dict) -> list[str]:
    errs = []
    ch = res.get("channels") or []
    for name, cid in TRUTH_SAME.items():
        c = _find(ch, name, cid)
        if not c:
            errs.append(f"정답 같은 결 '{name}' 이 결과에 없다")
        elif c.get("same_kind") is not True:
            errs.append(f"'{name}' 은 같은 결인데 same_kind={c.get('same_kind')} ({c.get('reason')})")
    for name in TRUTH_NOT:
        c = _find(ch, name)
        if not c:
            errs.append(f"정답 아님 '{name}' 이 결과에 없다(검사용 채널 실측 실패)")
        elif c.get("same_kind") is not False:
            errs.append(f"'{name}' 은 같은 결 아님인데 same_kind={c.get('same_kind')} ({c.get('reason')})")
    for c in ch:
        if c.get("same_kind") is True:
            if not c.get("reason") or (c.get("n") or 0) < 3 or c.get("median_views") is None:
                errs.append(f"같은 결 '{c.get('name')}' 근거·실측 없음")
            if c.get("lang") != "ko":
                errs.append(f"같은 결 '{c.get('name')}' 이 한국어 채널이 아님({c.get('lang')})")
    cost = res.get("cost")
    if not isinstance(cost, dict) or "serpapi_calls_new" not in cost or "gemini_calls" not in cost:
        errs.append("비용 장부(cost) 없음")
    elif cost["serpapi_calls_new"] > len(res.get("seeds") or []):
        errs.append(f"SerpApi 새 호출 {cost['serpapi_calls_new']} > 씨앗 {len(res.get('seeds') or [])} (씨앗당 1회 상한 위반)")
    # 5) 채널 찾기 에이전트가 표본 2편으로 확정한 같은 결 채널(같은결_채널.json)이 있으면: 엔진 결과에 있는 것은 같은 결이어야 한다
    conf = CONFIRMED if CONFIRMED.exists() else None
    if conf and res.get("seeds"):
        try:
            d = json.loads(conf.read_text(encoding="utf-8"))
            rows = d if isinstance(d, list) else d.get("channels", [])
        except ValueError:
            rows = []
        by = {c.get("channel_id"): c for c in ch}
        miss = []
        for r in rows:
            if r.get("same_kind") is False:
                continue
            c = by.get(r.get("channel_id"))
            if c is not None and c.get("same_kind") is not True:
                errs.append(f"확정 같은 결 '{r.get('name')}' 을 엔진이 {c.get('same_kind')} 로 판정 ({c.get('reason')})")
            elif c is None:
                miss.append(r.get("name"))
        res["_confirmed_missing"] = miss    # 못 찾은 확정 채널(빨강은 아님 — 수확률로 보고)
    seeds = {s["id"] for s in res.get("seeds") or []}
    got = {o["seed"] for o in res.get("originals") or []}
    if seeds - got:
        errs.append(f"해외 원본 칸 없는 씨앗 {len(seeds - got)}개")
    return errs


def rejudge(bad: str) -> dict:
    """정답 6채널만 엉터리 판정으로 다시 판정한 가짜 결과(검사가 빨강을 내는지 보는 자리)."""
    from tools.calcopy.engine import channel_find as cf

    def always_true(st):
        return {"same_kind": True, "reason": "엉터리: 전부 같은 결", "stage": "bad"}

    def title_only(st):   # 제목 규칙만(화면 판정 없이 '규칙 통과 = 같은 결') — 게시글형을 못 거른다
        v = cf.judge_same_kind(st, use_gemini=False)
        return dict(v, same_kind=(v["same_kind"] is not False))
    def always_false(st):
        return {"same_kind": False, "reason": "엉터리: 전부 아님", "stage": "bad"}
    fn = {"always_true": always_true, "title_only": title_only, "always_false": always_false}[bad]
    ch = []
    for name, ref in cf.TRUTH_PROBE.items():
        st = cf.channel_stats(ref)
        if not st:
            continue
        v = fn(st)
        ch.append({"name": st["name"], "channel_id": st["channel_id"], "handle": st.get("handle"), "lang": st.get("lang"),
                   "n": st["n"], "median_views": st["median_views"], **v})
    return {"channels": ch, "seeds": [], "originals": [], "cost": {"serpapi_calls_new": 0, "gemini_calls": 0}}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("result", nargs="?", default="channel/스타일분석/현장썰/채널수집/결과_엔진_1차.json")
    ap.add_argument("--bad-judge", choices=["always_true", "title_only", "always_false"])
    a = ap.parse_args(argv)
    if a.bad_judge:
        res = rejudge(a.bad_judge)
        label = f"엉터리 판정 {a.bad_judge}"
    else:
        p = Path(a.result)
        p = p if p.is_absolute() else ROOT / p
        res = json.loads(p.read_text(encoding="utf-8"))
        label = p.name
    errs = check(res)
    if errs:
        print(f"빨강 — {label}: {len(errs)}건")
        for e in errs:
            print(" -", e)
        return 1
    print(f"초록 — {label}: 정답 6채널 대조·근거·비용·원본 칸 통과")
    if "_confirmed_missing" in res:
        print(f"  확정 같은 결(같은결_채널.json) 중 엔진 결과에 없는 채널 {len(res['_confirmed_missing'])}: {', '.join(map(str, res['_confirmed_missing'][:20]))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
