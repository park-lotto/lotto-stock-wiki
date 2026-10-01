# -*- coding: utf-8 -*-
"""claim_trial_tagging 결과(result.json)의 컷 배정을 검사한다 — 사장님 2026-10-01 지시 셋 (카드 051).

    py tools/claim_trial_assign_check.py <result.json> [...]

  ① 뒷컷(is_outro) 이 어느 줄에도 안 붙었나
  ② 훅 줄의 첫 컷에 훅 유형(문제 제외)이 달렸나 (재료에 훅 컷이 하나라도 있을 때만)
  ③ 배속 힌트(speed_hints)가 데이터로 실렸나 — 렌더 적용은 아직 아님(결정 대기), 실린 줄 수만 센다
  + 태그 분포(훅 유형·소구·속도·뒷컷) 를 같이 찍는다.
고치기 전 코드로 만든 결과엔 ①②가 FAIL 나야 검사가 유효하다(0순위-A1c).
"""
import collections
import io
import json
import sys


def check(path):
    d = json.load(io.open(path, encoding="utf-8"))
    segs = {s["seg_id"]: s for v in (d.get("tags") or {}).values() for s in v if s.get("seg_id")}
    bs = d.get("beat_sources") or []
    lines = (d.get("given") or "").split("\n")
    bad = []
    # ① 뒷컷
    outro_used = [(i, sid) for i, b in enumerate(bs) for sid in (b or {}).get("segs") or [] if segs.get(sid, {}).get("is_outro")]
    if outro_used:
        bad.append("뒷컷 사용 %s" % outro_used)
    # ② 훅 줄 첫 컷
    hooks_avail = [sid for sid, s in segs.items() if s.get("hook_type") and s["hook_type"] != "문제" and not s.get("is_outro")]
    for i, b in enumerate(bs):
        if str((b or {}).get("role") or "").startswith("훅"):
            first = ((b or {}).get("segs") or [""])[0]
            ht = segs.get(first, {}).get("hook_type") or ""
            if hooks_avail and (not ht or ht == "문제"):
                bad.append("훅 줄[%d] 첫 컷 %s 훅 유형 없음(재료엔 훅 컷 %d개)" % (i, first, len(hooks_avail)))
    # ③ 배속 데이터
    n_speed = sum(1 for b in bs if (b or {}).get("speed_hints"))
    dist = {
        "훅유형": collections.Counter(s.get("hook_type") or "" for s in segs.values()).most_common(),
        "소구": collections.Counter(s.get("appeal_kind") or "" for s in segs.values()).most_common(),
        "속도": collections.Counter(s.get("tempo") or "" for s in segs.values()).most_common(),
        "뒷컷": sum(1 for s in segs.values() if s.get("is_outro")),
        "배속힌트≠1": sum(1 for s in segs.values() if s.get("speed_hint") not in (None, 1.0, "")),
    }
    print("%s: %s | 줄 %d · 배속힌트 실린 줄 %d" % (path, "FAIL" if bad else "PASS", len(bs), n_speed))
    for k, v in dist.items():
        print("   ", k, v)
    for x in bad:
        print("    ✗", x)
    for i, b in enumerate(bs):
        first = ((b or {}).get("segs") or [""])[0]
        print("    [%d] %-4s %s → %s %s%s" % (i, (b or {}).get("role") or "", lines[i][:28] if i < len(lines) else "", first,
                                             "훅:" + (segs.get(first, {}).get("hook_type") or "-"),
                                             " 배속" + str((b or {}).get("speed_hints")) if (b or {}).get("speed_hints") else ""))
    return not bad


if __name__ == "__main__":
    ok = all(check(p) for p in sys.argv[1:])
    sys.exit(0 if ok else 1)
