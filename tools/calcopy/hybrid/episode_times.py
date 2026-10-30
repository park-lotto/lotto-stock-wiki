"""회원 길 한 편이 실제로 몇 분 걸렸나(사장님 10-30 "실제 몇 분이 걸리는지 체크 아주 중요") — 편 폴더만 읽는다(다시 돌리지 않는다).

    py tools/calcopy/hybrid/episode_times.py C:/t/hs_ep7 [C:/t/hs_ep6 …]

재는 것(전부 파일 시각 실측):
  전체 = 편 시작(flow.json 의 created) → 완성본 파일 시각
  회원 Claude 답 = AI 요청 폴더 이름 시각(요청이 나온 때) → answer.json 시각(답이 온 때) — 요청마다·단계마다 합
  엔진·대기 = 전체 − 회원 Claude 답(받기·렌더·목소리·검사 등)
  단계 벽시계 = 그 단계 첫 질문 → 다음 다른 단계 첫 질문(그 사이 엔진 일 — 렌더·목소리·검사 — 포함. 썸네일 칸이 큰 건 그 뒤 렌더가 들어가서)
  단계 = 요청 꼬리표(topic_read·script_·plan_·sheet_ …)로 묶는다 — 같은 단계가 다시 나오면(되돌이) 몇 번인지 같이
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

STAGE = [("topic", "소재"), ("ref_read", "소재"), ("origin", "원본"), ("of_", "원본"), ("shop_same", "제품"), ("product", "제품"),
         ("best", "제품"), ("named", "제품"), ("name_find", "제품"), ("research", "조사"), ("screen_pick", "재료"), ("shot_", "재료"),
         ("script", "대본"), ("line_fix", "줄 고치기"), ("plan", "장면 맞추기"), ("more_pick", "재료 더 찾기"), ("thumb", "썸네일"),
         ("render_fix", "렌더 고치기"), ("sheet_", "1초 시트"), ("final_fix", "완성본 고치기"), ("task", "제작자 과제"), ("eye", "눈 검수")]


def stage_of(tag: str) -> str:
    tag = re.sub(r"^s[0-9]+_", "", tag)      # 해외원본형 소재 칸 질문(s1_·s2_) = 같은 단계
    for k, name in STAGE:
        if tag.startswith(k):
            return name
    return "기타"


def times(ep: Path) -> dict:
    flows = sorted((ep / "home" / "창고" / "flow").glob("*/flow.json"))
    if not flows:
        return {"dir": str(ep), "error": "flow.json 없음"}
    f = json.loads(flows[0].read_text(encoding="utf-8"))
    t0 = float(f.get("created") or 0) / 1000 or flows[0].stat().st_ctime
    vids = sorted((ep / "work" / "완성본").glob("*.mp4"), key=lambda p: p.stat().st_mtime)
    rows = []
    for d in sorted((ep / "home" / "ai").glob("flow_*/*")):
        m = re.match(r"^(\d{8}-\d{6})-(.+)-[0-9a-f]{6}$", d.name)
        if not m:
            continue
        asked = datetime.strptime(m.group(1), "%Y%m%d-%H%M%S").timestamp()
        a = d / "answer.json"
        got = a.stat().st_mtime if a.exists() else None
        rows.append({"tag": m.group(2), "stage": stage_of(m.group(2)), "asked": asked, "sec": round(got - asked) if got else None})
    # 끝 = 편이 '완성'으로 저장된 때(flow.json 마지막 저장) — 완성본 파일 시각은 렌더 시각이라 마지막 1초 시트 답보다 앞설 수 있다
    end = max([flows[0].stat().st_mtime] + [r["asked"] + (r["sec"] or 0) for r in rows])
    total = end - t0
    ai = sum(r["sec"] or 0 for r in rows)
    by = {}
    for r in rows:
        s = by.setdefault(r["stage"], {"n": 0, "ai_sec": 0})
        s["n"] += 1
        s["ai_sec"] += r["sec"] or 0
    # 단계마다 벽시계 = 그 단계 첫 요청 → 다음 다른 단계 첫 요청(엔진 일 포함)
    wall, order = {}, []
    for i, r in enumerate(rows):
        if not order or order[-1][0] != r["stage"]:
            order.append([r["stage"], r["asked"]])
    for i, (s, a) in enumerate(order):
        b = order[i + 1][1] if i + 1 < len(order) else end
        wall[s] = wall.get(s, 0) + (b - a)
    return {"dir": str(ep), "start": datetime.fromtimestamp(t0).strftime("%H:%M:%S"), "end": datetime.fromtimestamp(end).strftime("%H:%M:%S"),
            "total_min": round(total / 60, 1), "before_first_ask_min": round(((rows[0]["asked"] if rows else end) - t0) / 60, 1),
            "member_claude_min": round(ai / 60, 1), "engine_wait_min": round((total - ai) / 60, 1), "asks": len(rows),
            "stages": {s: {"wall_min": round(wall.get(s, 0) / 60, 1), "asks": v["n"], "claude_min": round(v["ai_sec"] / 60, 1)} for s, v in by.items()},
            "order": [s for s, _ in order], "video": str(vids[-1]) if vids else None}


def say(r: dict) -> str:
    if r.get("error"):
        return f"{r['dir']}: {r['error']}"
    out = [f"{r['dir']}  {r['start']}→{r['end']}  전체 {r['total_min']}분 = 회원 Claude 답 {r['member_claude_min']}분 + 엔진·대기 {r['engine_wait_min']}분 (요청 {r['asks']}개, 첫 요청까지 {r['before_first_ask_min']}분)"]
    for s, v in sorted(r["stages"].items(), key=lambda x: -x[1]["wall_min"]):
        out.append(f"  {s:8} {v['wall_min']:5}분(벽시계) · Claude {v['claude_min']}분 · 요청 {v['asks']}")
    out.append("  흐름: " + " → ".join(r["order"]))
    return "\n".join(out)


if __name__ == "__main__":
    for a in sys.argv[1:]:
        print(say(times(Path(a))))
