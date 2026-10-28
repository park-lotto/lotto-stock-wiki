# -*- coding: utf-8 -*-
"""[서버용·읽기 전용] 태깅(새 지침)과 확정 대본이 있는 job 에서, 믹스용 지시문을 새로 써서 AI 에게 줄별 컷을 고르게 한다 (2026-10-01 사장님).

    set -a && . /etc/shopping-shorts.env && set +a && cd /home/ubuntu/lotto-stock-wiki
    python3 /tmp/mix_ai_match_trial.py 4a1d44721e8a --out /tmp/mixtrial_4a1d44721e8a

흐름: ①컷 목록(태그 전부: 화면·쓰임·대본화 소구점·소구 종류·훅 유형·속도·뒷컷) ②대본 줄(초) → AI 1차 배정
      ③코드 검사(중복·뒷컷·목록 밖·길이) → 걸린 줄만 AI 2차(이유를 적어 다시) ④줄별 프레임 → result.json
DB 에 아무것도 안 쓴다. 산출물은 --out 폴더.
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time

sys.path[:] = [os.getcwd()] + [p for p in sys.path if os.path.abspath(p or ".") != os.path.dirname(os.path.abspath(__file__))]
MIX = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/mix_jobs"
MIN_CUT = 0.8
SLOW = 1.2          # config.MAX_SLOWMO 와 같은 뜻 — 컷 길이 합 × 1.2 ≥ 대사 초면 늦춰서 채운다

BRIEF = """너는 쇼핑 쇼츠에서 **대본과 장면을 딱 맞게 배치하는 최고 전문가**다. 수천 편을 편집했고, 말과 그림이 한 박자라도
어긋나면 시청자가 바로 이탈한다는 걸 안다. 네 기준은 하나다 — **그 줄이 읽히는 동안 화면에 그 말이 보이는가.**
서두르지 마라. 시간이 걸려도 **한 단계씩 생각하고** 그 생각을 steps 에 적은 뒤에 고른다.

1단계 — 읽기: [주제]와 [대본]을 처음부터 끝까지 읽고 이 영상이 무엇을 파는지, 줄마다 시청자에게 **무엇을 보여줘야 설득되는지** 정하라.
   줄마다 "필요한 그림"을 한 구절로 적는다(예: 미끼 줄 → 냄비 앞에서 고생하는 모습 / 배수 줄 → 용기 기울여 물 빠지는 순간).
2단계 — 재료 파악: [컷 목록]을 전부 훑어 어떤 그림이 있고 없는지, 어느 영상에 무엇이 있는지 정리하라. 컷마다 1단계 태깅이 있다:
   번호 | 영상 | 길이 | 화면에 보이는 것 | 쓰임 | 소구점(이 장면 위에 읽힐 말) | 종류 | 훅 | 속도 | 뒷컷.
3단계 — 배치: 줄마다 고른다.
   a. **말과 같은 그림**이 1순위. 소구점 문장이 줄의 뜻과 가까우면 그 컷.
   b. 줄 유형별
      - [훅] 첫 줄: 훅 표시(클로즈업/반전/비포애프터/충격)가 있는 제품 컷. 제품이 또렷해야 한다.
      - [미끼]·불편을 말하는 줄: 종류가 '문제'인 컷(제품 없이 불편·기존 방식). **없으면 cuts를 비우고 why에 "문제 장면 없음"**.
        제품 시연 컷으로 때우지 마라 — 틀린 그림은 빈 화면보다 나쁘다.
      - [공개] "이건 바로 X": 제품 전체가 또렷이 보이는 컷.
      - 기능·결과 줄: 그 기능을 **하고 있는 순간**(배수 줄엔 물 빠지는 장면, 전자레인지 줄엔 넣고 돌리는 장면, 계량 줄엔 계량하는 손).
      - [반전]·충격 포인트 줄: 훅 '충격'·'반전' 컷이 있으면 그것.
      - [마무리]·CTA: 완성품·제품 전체 컷. 뒷컷(인사·채널 UI)은 절대 안 된다.
   c. **장면을 다양하게.** 같은 그림이 여러 영상에 있으면 **앞 줄과 다른 영상**의 컷을 골라 화면이 계속 바뀌게 하라.
      한 영상의 컷이 연달아 세 줄 이상 가지 않게. 같은 컷·같은 장면을 두 줄에 쓰지 마라.
   d. **시간을 맞춰라.** 줄마다 고른 컷 길이 합 × 1.2 ≥ 대사 초가 되게 하고, have(합)·need(대사 초)를 적어라.
      모자라면 같은 영상의 **같은 쓰임** 컷을 이어 붙이고, 그래도 모자라면 다른 영상의 같은 뜻 컷을 더한다.
      **딴 장면(다른 물건·다른 쓰임)으로 길이를 채우지 마라** — 길이보다 그림이 먼저다. 긴 줄(5초↑)은 2~3컷으로 나눠 리듬을 줘라.
   e. 뒷컷=예 인 컷은 어느 줄에도 쓰지 마라. 목록에 없는 번호를 만들지 마라.
4단계 — 점검: 다 고른 뒤 전체를 다시 보며 ①중복 컷 ②뒷컷 ③길이 부족 ④세 줄 연속 같은 영상 을 스스로 잡아 고쳐라.

출력 JSON만:
{"steps": "1단계·2단계·4단계에서 생각한 것(각 2~3문장)",
 "picks": [{"line": 1, "need_pic": "이 줄에 필요한 그림", "cuts": ["번호", "번호"], "have": 초, "need": 초, "why": "화면에 무엇이 보여서(15자 안팎)"}]}
줄을 빠짐없이, 줄 순서대로.
"""

RETRY = """아래 줄들은 앞선 배정에 문제가 있었다. **그 줄만** 다시 골라라(다른 줄의 컷은 그대로 두니 그 컷들은 쓰지 마라).
문제와 쓸 수 없는 컷을 적어 두었다. 같은 규칙(말과 같은 그림, 한 컷 한 줄, 길이, 뒷컷 금지)으로.
출력 JSON만: {"picks":[{"line":N,"cuts":[...],"why":"..."}]}

[다시 고를 줄]
%s

[쓸 수 없는 컷(다른 줄이 씀·뒷컷)]
%s
"""


def _loads(t):
    t = (t or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("{"):]
    return json.loads(t[t.find("{"):t.rfind("}") + 1])


def _call(prompt):
    from google.genai import types
    from shopping_shorts import vertex_route
    cl, m = vertex_route.client(0), vertex_route.model()
    cfg = types.GenerateContentConfig(response_mime_type="application/json")
    for n in range(4):
        try:
            return _loads(cl.models.generate_content(model=m, contents=[prompt], config=cfg).text), m
        except Exception as e:      # noqa: BLE001
            print("  재시도", n + 1, repr(e)[:100], flush=True)
            time.sleep(6 * (n + 1))
    raise RuntimeError("버텍스 4회 실패")


def _grab(video, t, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "%.3f" % t, "-i", video, "-frames:v", "1", "-vf", "scale=-2:300", out], check=False)
    return out if os.path.exists(out) else None


def load_job(jid):
    from shopping_shorts.config import DB_PATH
    from shopping_shorts.store import Store
    store = Store(DB_PATH)
    job = store.get_mix_job(jid)
    ext = job.get("extract") or {}
    lines = [l.strip() for l in (job.get("given_script") or "").split("\n") if l.strip()]
    roles = [b.get("role") or "" for b in ((job.get("script_structure") or {}).get("beat_sources") or [])]
    plan = job.get("edit_plan") or {}
    durs = {}
    for b in plan.get("beats") or []:
        durs[b.get("narration") or ""] = round(sum(b.get("cap_durs") or []) or float(b.get("target_seconds") or 0), 1)
    cuts, vid_of = [], {}
    for sn, ex in sorted(ext.items()):
        if not isinstance(ex, dict):
            continue
        for s in ex.get("segments") or []:
            if not isinstance(s, dict) or not s.get("seg_id"):
                continue
            secs = round(float(s.get("end") or 0) - float(s.get("start") or 0), 1)
            vid_of[s["seg_id"]] = sn
            cuts.append({"id": s["seg_id"], "vid": sn, "start": float(s.get("start") or 0), "end": float(s.get("end") or 0), "secs": secs,
                         "desc": (s.get("scene_desc") or "").strip(), "label": (s.get("label") or "").strip(),
                         "use": (s.get("use_point") or "").strip(), "kind": s.get("appeal_kind") or "", "hook": s.get("hook_type") or "",
                         "tempo": s.get("tempo") or "", "outro": bool(s.get("is_outro")) and not (s.get("hook_type") or s.get("product_benefits")),
                         "old_tag": not bool(s.get("appeal_kind") or s.get("hook_type") or s.get("tempo"))})
    return job, lines, roles, durs, cuts


def cut_rows(cuts):
    rows = []
    for c in cuts:
        if c["secs"] < MIN_CUT:
            continue
        rows.append("%s | %s | %.1f초 | %s | 쓰임:%s | 소구점:%s | 종류:%s | 훅:%s | 속도:%s | 뒷컷:%s" % (
            c["id"], c["vid"], c["secs"], c["desc"][:60], c["label"], c["use"][:40], c["kind"] or "-", c["hook"] or "-", c["tempo"] or "-", "예" if c["outro"] else "아니오"))
    return "\n".join(rows)


def check(picks, lines, durs, byid):
    """코드 검사 — 걸린 줄: {line_idx: 이유}"""
    bad, used = {}, {}
    for i, text in enumerate(lines):
        cs = picks.get(i, [])
        need = durs.get(text, 0) or 0
        why = []
        for c in cs:
            if c not in byid:
                why.append("목록 밖 %s" % c)
            elif byid[c]["outro"]:
                why.append("뒷컷 %s" % c)
            elif c in used and used[c] != i:
                why.append("중복 %s(줄%d)" % (c, used[c] + 1))
            else:
                used[c] = i
        have = sum(byid[c]["secs"] for c in cs if c in byid)
        if cs and need and have * SLOW < need - 0.3:
            why.append("길이 %.1f×1.2 < %.1f" % (have, need))
        if why:
            bad[i] = "; ".join(why)
    # 같은 영상이 세 줄 연속 — 화면이 안 바뀐다(사장님 10-01 "장면을 다양하게")
    vids = [sorted({byid[c]["vid"] for c in picks.get(i, []) if c in byid}) for i in range(len(lines))]
    for i in range(2, len(lines)):
        if vids[i] and vids[i] == vids[i - 1] == vids[i - 2] and len(vids[i]) == 1 and i not in bad:
            bad[i] = "같은 영상 %s 세 줄 연속" % vids[i][0]
    return bad, used


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    job, lines, roles, durs, cuts = load_job(a.job)
    byid = {c["id"]: c for c in cuts}
    print("줄", len(lines), "컷", len(cuts), "옛 태그 컷", sum(1 for c in cuts if c["old_tag"]), "뒷컷", sum(1 for c in cuts if c["outro"]), flush=True)
    lb = "\n".join("  %d. [%s] (%.1f초) %s" % (i + 1, roles[i] if i < len(roles) else "", durs.get(t, 0) or 0, t) for i, t in enumerate(lines))
    product = ""
    for ex in (job.get("extract") or {}).values():
        if isinstance(ex, dict) and isinstance(ex.get("source_brief"), dict) and ex["source_brief"].get("product"):
            product = ex["source_brief"]["product"]; break
    prompt = "%s\n[주제] 이 영상이 파는 것: %s\n\n[대본]\n%s\n\n[컷 목록] 번호 | 영상 | 길이 | 화면 | 쓰임 | 소구점 | 종류 | 훅 | 속도 | 뒷컷\n%s" % (BRIEF, product or "(제품명 미상 — 대본에서 읽어라)", lb, cut_rows(cuts))
    with open(os.path.join(a.out, "prompt_1.txt"), "w", encoding="utf-8") as f:
        f.write(prompt)
    r, model = _call(prompt)
    picks, whys = {}, {}
    for p in r.get("picks") or []:
        try:
            i = int(p.get("line")) - 1
        except (TypeError, ValueError):
            continue
        picks[i] = [str(x) for x in (p.get("cuts") or [])]
        whys[i] = ((p.get("need_pic") or "") + " → " if p.get("need_pic") else "") + (p.get("why") or "")
    steps = r.get("steps") or ""
    with open(os.path.join(a.out, "steps.txt"), "w", encoding="utf-8") as f:
        f.write(str(steps))
    bad, used = check(picks, lines, durs, byid)
    print("1차 배정 — 걸린 줄:", {i + 1: w for i, w in bad.items()}, flush=True)
    calls = 1
    if bad:
        blocked = sorted({c for i, cs in picks.items() if i not in bad for c in cs} | {c["id"] for c in cuts if c["outro"]})
        again = "\n".join("  %d. [%s] (%.1f초) %s — 문제: %s" % (i + 1, roles[i] if i < len(roles) else "", durs.get(lines[i], 0) or 0, lines[i], w) for i, w in bad.items())
        prompt2 = RETRY % (again, ", ".join(blocked)) + "\n\n[컷 목록]\n" + cut_rows(cuts)
        with open(os.path.join(a.out, "prompt_2.txt"), "w", encoding="utf-8") as f:
            f.write(prompt2)
        r2, _ = _call(prompt2)
        calls += 1
        for p in r2.get("picks") or []:
            try:
                i = int(p.get("line")) - 1
            except (TypeError, ValueError):
                continue
            if i in bad:
                picks[i] = [str(x) for x in (p.get("cuts") or [])]
                whys[i] = "(2차) " + (p.get("why") or "")
        bad2, used = check(picks, lines, durs, byid)
        print("2차 뒤 — 남은 문제:", {i + 1: w for i, w in bad2.items()}, flush=True)
    else:
        bad2 = {}
    # 줄별 프레임(컷당 2장)
    rows = []
    for i, text in enumerate(lines):
        cs = [c for c in picks.get(i, []) if c in byid]
        paths, descs = [], []
        for cid in cs[:4]:
            c = byid[cid]
            vids = sorted(glob.glob(os.path.join(MIX, a.job, c["vid"], "*.mp4")))
            if vids:
                for q in range(2):
                    p = _grab(vids[0], c["start"] + (c["end"] - c["start"]) * (q + 0.5) / 2, os.path.join(a.out, "line%02d_%s_%d.jpg" % (i, cid.replace("/", "_"), q)))
                    if p:
                        paths.append(p)
            descs.append("%s(%.1fs) %s | 훅:%s 종류:%s" % (cid, c["secs"], c["desc"][:40], c["hook"] or "-", c["kind"] or "-"))
        rows.append({"i": i, "text": text, "role": roles[i] if i < len(roles) else "", "need": durs.get(text, 0) or 0, "segs": cs,
                     "why": whys.get(i, ""), "problem": bad2.get(i, ""), "frames": paths, "descs": descs})
    out = {"job": a.job, "mode": "ai_mix_trial", "model": model, "calls": calls, "secs": round(time.time() - t0, 1),
           "given": "\n".join(lines), "beat_sources": [{"role": r["role"], "seg": (r["segs"] or [""])[0], "segs": r["segs"]} for r in rows],
           "rows": rows, "first_bad": {str(i + 1): w for i, w in bad.items()}, "left_bad": {str(i + 1): w for i, w in bad2.items()}}
    with open(os.path.join(a.out, "result.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("완료", a.job, model, "호출", calls, "%.0fs" % (time.time() - t0))
    for r in rows:
        print(" [%d] %-4s %s → %s | %s%s" % (r["i"], r["role"][:4], r["text"][:24], [s[-8:] for s in r["segs"]], r["why"][:30], (" ✗ " + r["problem"]) if r["problem"] else ""))


if __name__ == "__main__":
    main()
