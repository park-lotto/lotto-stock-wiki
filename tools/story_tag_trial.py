# -*- coding: utf-8 -*-
"""[서버용·읽기 전용] "태깅부터 대본화" 시험 — AI 가 끝까지 주도 (2026-10-01 사장님).

  ① 영상마다 스토리: 컷 태그(대본화 소구점·화면·쓰임)로 "순서 있는 3~6줄 + 각 줄의 컷 번호 + 종류"를 만든다
  ② 대본: 스토리 줄들만 재료로, 틀(지금 대본의 말투·구조)에 맞춰 줄마다 **스토리 줄 번호(=컷)**를 달고 쓴다
  ③ 매칭: 줄에 달린 컷을 그대로 쓰되 전문가 매처가 검사(중복·길이·뒷컷·세 줄 연속)하고 걸린 줄만 다시 고른다
  산출: result.json(rows: 줄·컷·프레임) + stories.json + prompts. DB 무변경.

    set -a && . /etc/shopping-shorts.env && set +a && cd /home/ubuntu/lotto-stock-wiki
    PYTHONPATH=/tmp:. python3 /tmp/story_tag_trial.py 4a1d44721e8a --out /tmp/storytrial_4a1d44721e8a
"""
import argparse
import glob
import json
import os
import sys
import time

sys.path[:] = [os.getcwd(), "/tmp"] + [p for p in sys.path if os.path.abspath(p or ".") != os.path.dirname(os.path.abspath(__file__))]
from mix_ai_match_trial import _call, _grab, load_job, check, MIX, MIN_CUT, SLOW   # noqa: E402  (같은 재료·같은 검사)

STORY_PROMPT = """너는 쇼핑 쇼츠 **대본 작가 겸 편집자**다. 아래는 같은 제품을 찍은 영상 여러 편의 컷 태그다
(컷마다: 번호 | 길이 | 화면에 보이는 것 | 쓰임 | 소구점(이 장면 위에 읽힐 말) | 종류 | 훅).

영상마다 **스토리**를 써라 — 시청자에게 보여줄 순서대로 3~6줄. 줄마다:
- text: 대본에 **그대로 읽을** 한 문장(12~30자). ★설명문이 아니다 — 쇼핑 쇼츠 **말맛**으로 써라: 구어체, 리듬, 과장·감탄·의성어 OK
  (예 "물만 붓고 돌리면 끝, 냄비 설거지 안녕" / "거름망 하나로 물만 쏙, 손 델 일이 없어요" / "소스 부어 쓱쓱, 바로 한 끼 완성").
  "~하는 모습이다" "~을 보여준다" 같은 묘사·보고 문장은 금지. 단, 그 줄에 붙은 컷 위에서 읽히므로 **화면에 보이는 것만** 말한다.
- cuts: 그 문장을 보여주는 컷 번호들(1개 이상, 같은 장면 연속 컷은 같이).
- kind: 문제/기능/특징/장점/효과/외관/활용/구성/반응 중 하나.
- point: 이 줄이 파는 포인트 한 구절(예 "1인분 딱 맞는 계량", "거름망 배수 = 쉬운 조리").
규칙: 컷 번호는 목록에 있는 것만. 한 컷은 한 줄에만. 뒷컷(인사·채널 화면)은 쓰지 마라. 불편·기존 방식 장면이 있으면 '문제' 줄을 맨 앞에.
출력 JSON만: {"stories":[{"video":"s0","product":"제품명","lines":[{"text":"...","cuts":["..."],"kind":"...","point":"..."}]}]}

%s
"""

SCRIPT_PROMPT = """너는 쇼핑 쇼츠 **대본 작가**다. 아래 [스토리]는 영상마다 "대본 문장 + 그 문장을 보여주는 컷"이다. 재료는 이것뿐이다.
[틀]은 지금 쓰던 대본이다 — **말투·줄 수·구조(훅→미끼→공개→고조→반전→마무리)**만 따라 하고, 내용 문장은 전부 [스토리] 줄에서 가져와라.

규칙
- 줄마다 어느 스토리 줄을 썼는지 from 에 "영상:줄번호"로 적어라(예 "s1:2"). 훅·공개·마무리처럼 틀 문장이면 from 은 그 자리에 어울리는 스토리 줄을 고른다.
- 같은 스토리 줄을 두 번 쓰지 마라. 영상을 골고루 써라(한 영상 줄이 연달아 세 줄 이상 금지).
- 스토리에 없는 사실·숫자·기능을 지어내지 마라. [미끼] 자리에 '문제' 줄이 없으면 그 자리는 "요즘 ○○하는 사람들 사이에서"처럼 상황만 말하고 from 은 비워라.
- 줄 길이는 틀과 비슷하게(한 줄 8~30자). 총 %d줄 안팎.
- ★말맛을 살려라. 틀의 말투(…했다는 거, …난리가 났다는데, 진짜 미친 포인트는)를 그대로 타고, 스토리 문장은 뜻만 가져와 그 말투로 녹여라.
  설명문·보고문("~할 수 있습니다", "~하는 모습")은 한 줄도 넣지 마라.
출력 JSON만: {"lines":[{"role":"훅","text":"...","from":"s1:2"}]}

[틀]
%s

[스토리]
%s
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    job, lines0, roles0, durs0, cuts = load_job(a.job)
    byid = {c["id"]: c for c in cuts}
    # ① 스토리
    blocks = []
    for vid in sorted({c["vid"] for c in cuts}):
        rows = ["  %s | %.1f초 | %s | 쓰임:%s | 소구점:%s | 종류:%s | 훅:%s%s" % (c["id"], c["secs"], c["desc"][:60], c["label"], c["use"][:40], c["kind"] or "-", c["hook"] or "-", " | 뒷컷" if c["outro"] else "")
                for c in cuts if c["vid"] == vid and c["secs"] >= MIN_CUT]
        blocks.append("[영상 %s]\n%s" % (vid, "\n".join(rows)))
    p1 = STORY_PROMPT % "\n\n".join(blocks)
    open(os.path.join(a.out, "prompt_story.txt"), "w", encoding="utf-8").write(p1)
    r1, model = _call(p1)
    stories = r1.get("stories") or []
    json.dump(stories, open(os.path.join(a.out, "stories.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sref = {}
    stxt = []
    for st in stories:
        v = st.get("video") or ""
        stxt.append("[영상 %s] %s" % (v, st.get("product") or ""))
        for k, L in enumerate(st.get("lines") or [], 1):
            sref["%s:%d" % (v, k)] = L
            stxt.append("  %s:%d [%s] %s  (컷 %s)  ← %s" % (v, k, L.get("kind") or "", L.get("text") or "", ",".join(L.get("cuts") or []), L.get("point") or ""))
    print("① 스토리", len(stories), "편, 줄", len(sref), "(%.0fs)" % (time.time() - t0), flush=True)
    for s in stxt:
        print("   " + s)
    # ② 대본
    tpl = "\n".join("  %d. [%s] %s" % (i + 1, roles0[i] if i < len(roles0) else "", t) for i, t in enumerate(lines0))
    p2 = SCRIPT_PROMPT % (len(lines0), tpl, "\n".join(stxt))
    open(os.path.join(a.out, "prompt_script.txt"), "w", encoding="utf-8").write(p2)
    r2, _ = _call(p2)
    new_lines = [L for L in (r2.get("lines") or []) if (L.get("text") or "").strip()]
    print("② 대본", len(new_lines), "줄 (%.0fs)" % (time.time() - t0), flush=True)
    picks = {}
    for i, L in enumerate(new_lines):
        ref = sref.get(str(L.get("from") or "").strip())
        picks[i] = [c for c in ((ref or {}).get("cuts") or []) if c in byid]
        print("   [%d] %-4s %s ← %s %s" % (i, (L.get("role") or "")[:4], L.get("text"), L.get("from") or "-", picks[i]))
    # ③ 검사 → 걸린 줄만 전문가 매처로 다시
    lines = [{"role": L.get("role") or "", "text": L.get("text")} for L in new_lines]
    durs = {L["text"]: round(len(L["text"]) / 5.7, 1) for L in lines}    # TTS 전 추정(초당 5.7음절, edit_plan 정본과 같은 값)
    bad, used = check(picks, [L["text"] for L in lines], durs, byid)
    print("③ 검사 — 걸린 줄:", {i + 1: w for i, w in bad.items()}, flush=True)
    calls = 2
    if bad:
        from mix_ai_match_trial import BRIEF, cut_rows
        again = "\n".join("  %d. [%s] (%.1f초) %s — 문제: %s" % (i + 1, lines[i]["role"], durs[lines[i]["text"]], lines[i]["text"], w) for i, w in bad.items())
        blocked = sorted({c for i, cs in picks.items() if i not in bad for c in cs} | {c["id"] for c in cuts if c["outro"]})
        p3 = BRIEF + "\n\n★아래 줄들만 다시 골라라(다른 줄 컷은 그대로). 쓸 수 없는 컷: %s\n[다시 고를 줄]\n%s\n\n[컷 목록]\n%s" % (", ".join(blocked), again, cut_rows(cuts))
        r3, _ = _call(p3)
        calls += 1
        for p in r3.get("picks") or []:
            try:
                i = int(p.get("line")) - 1
            except (TypeError, ValueError):
                continue
            if i in bad:
                picks[i] = [str(x) for x in (p.get("cuts") or []) if str(x) in byid]
        bad2, used = check(picks, [L["text"] for L in lines], durs, byid)
        print("   2차 뒤 남은 문제:", {i + 1: w for i, w in bad2.items()}, flush=True)
    else:
        bad2 = {}
    # 프레임
    rows = []
    for i, L in enumerate(lines):
        cs = picks.get(i, [])
        paths, descs = [], []
        for cid in cs[:4]:
            c = byid[cid]
            vids = sorted(glob.glob(os.path.join(MIX, a.job, c["vid"], "*.mp4")))
            if vids:
                for q in range(2):
                    p = _grab(vids[0], c["start"] + (c["end"] - c["start"]) * (q + 0.5) / 2, os.path.join(a.out, "line%02d_%s_%d.jpg" % (i, cid.replace("/", "_"), q)))
                    if p:
                        paths.append(p)
            descs.append("%s(%.1fs) %s | 소구점:%s" % (cid, c["secs"], c["desc"][:36], c["use"][:30]))
        rows.append({"i": i, "text": L["text"], "role": L["role"], "need": durs[L["text"]], "segs": cs, "why": new_lines[i].get("from") or "",
                     "problem": bad2.get(i, ""), "frames": paths, "descs": descs})
    out = {"job": a.job, "mode": "story_tag_trial", "model": model, "calls": calls, "secs": round(time.time() - t0, 1),
           "given": "\n".join(L["text"] for L in lines), "beat_sources": [{"role": r["role"], "seg": (r["segs"] or [""])[0], "segs": r["segs"]} for r in rows],
           "rows": rows, "stories": stories, "old_script": lines0}
    json.dump(out, open(os.path.join(a.out, "result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("완료", a.job, model, "호출", calls, "%.0fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
