# -*- coding: utf-8 -*-
"""매칭 A/B 러너 — 오푸스(구독 CLI) vs 제미니(프로덕션 경로).

채점은 **프로덕션 판정축** `backbone.beat_role_mismatch`를 그대로 쓴다.
내가 새 기준을 지어내면 그게 곧 거짓말이 된다(0순위-B).

진행상황을 매 케이스마다 progress.json에 쓴다 —
  ⚠️ 백그라운드 작업은 조용히 죽을 수 있다(exit 255 전례). 죽어도 어디까지 갔는지 보여야 한다.
"""
import io
import json
import os
import random
import sys
import time
import traceback


_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = r"C:/Users/CH/Desktop/로또의 주식"
sys.path.insert(0, _ROOT)
sys.path.insert(0, _HERE)

os.chdir(_ROOT)   # ★.env(제미니 키)는 main 폴더 기준으로 찾힌다 — 실행 위치 무관하게 고정
from shopping_shorts import edit_plan, backbone  # noqa: E402
from ab_repick import make_claude_call, make_gemini_call  # noqa: E402

LOG_DIR = os.path.join(_HERE, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
PROGRESS = os.path.join(_HERE, "progress.json")
RESULTS = os.path.join(_HERE, "results.json")


def load_job():
    with open(os.path.join(_HERE, "job_409f894230c6.json"), encoding="utf-8") as f:
        d = json.load(f)
    seg_map = {}
    for _sid, v in (d["extract"] or {}).items():
        # ★video_id는 소스 레벨에 있고 세그에는 없다 — 프로덕션 `_build_inventory`
        #   (edit_plan.py:1684)가 세그마다 실어주는 값이라 여기서도 똑같이 실어야
        #   `_ground_ref`(edit_plan.py:1756 `seg["video_id"]`)가 산다.
        vid = (v or {}).get("video_id", "")
        for s in (v or {}).get("segments") or []:
            seg_map[s["seg_id"]] = dict(s, video_id=s.get("video_id", vid))
    return d["edit_plan"]["beats"], seg_map


def score(beats, seg_map):
    """프로덕션 판정축으로 채점. 어긋난 비트 수(적을수록 좋다)."""
    bad, detail = 0, []
    for b in beats:
        pid = (b.get("primary") or {}).get("seg_id")
        seg = seg_map.get(pid) or {}
        # beat_role_mismatch는 primary 안의 shot_role을 본다 → 인벤토리 값을 실어준다.
        probe = dict(b)
        probe["primary"] = dict(b.get("primary") or {}, shot_role=seg.get("shot_role"))
        m = backbone.beat_role_mismatch(probe)
        if m:
            bad += 1
        detail.append({
            "beat_idx": b.get("beat_idx"), "role": b.get("role"),
            "seg_id": pid, "shot_role": seg.get("shot_role"),
            "scene_desc": (seg.get("scene_desc") or "")[:70],
            "fit": b.get("fit"), "repicked": bool(b.get("repicked")),
            "mismatch": bool(m),
        })
    return bad, detail


def build_cases(beats, seg_map):
    """합성 표본 — 라이브 잡 1건의 **진짜 세그먼트**를 재료로 케이스를 늘린다.

    ★무엇을 합성하고 무엇을 안 하나:
      · 세그먼트(scene_desc·shot_role)는 **손대지 않는다** — 1단계 태깅의 진짜 결과물이다.
      · 비트의 대사도 **손대지 않는다** — 진짜 대본이다.
      · 바꾸는 건 **어느 화면이 배정돼 있었나**뿐이다. 이게 매칭이 푸는 문제다.
      즉 "같은 재료, 다른 출발점"에서 모델이 정답으로 수렴하는지를 본다.
    """
    cases = []
    pool = sorted(seg_map.keys())

    # ① 원본 그대로 — 라이브에서 실제로 나온 상태(훅·CTA가 '사용중')
    cases.append(("live_asis", [dict(b) for b in beats]))

    # ② 전 비트를 강제 재픽 대상으로(fit=1) — 모델이 처음부터 고르게 한다.
    #    ★재픽은 fit<=3 또는 forced만 대상이라, 라이브의 fit=5는 손도 못 댄다.
    #    "모델이 고를 능력이 있나"를 보려면 문을 열어줘야 한다.
    c2 = [dict(b, fit=1) for b in beats]
    cases.append(("all_open", c2))

    # ③ 최악 출발점 — 모든 비트에 '준비/재료' 계열을 억지로 물린다.
    #    규칙이 명시적으로 금지한 상태("준비동작·계량으로 훅을 열지 마라")에서
    #    모델이 빠져나오는지 본다.
    worst = [sid for sid in pool
             if (seg_map[sid].get("shot_role") or "") not in ("완성", "after")]
    if worst:
        c3 = []
        for i, b in enumerate(beats):
            nb = dict(b, fit=1)
            sid = worst[i % len(worst)]
            nb["primary"] = dict(seg_map[sid])
            c3.append(nb)
        cases.append(("worst_start", c3))

    # ④ 역할 셔플 — 비트 순서를 돌려 역할↔화면 짝을 어긋뜨린다(여러 벌).
    n = len(beats)
    for k in range(1, min(n, 5)):
        ck = []
        for i, b in enumerate(beats):
            nb = dict(b, fit=1)
            src = beats[(i + k) % n]
            nb["primary"] = dict(src.get("primary") or {})
            ck.append(nb)
        cases.append(("shift%d" % k, ck))

    # ⑤ 단일 비트 격리 — 비트마다 그것만 열어 재픽시킨다(역할별 능력을 따로 본다).
    for b in beats:
        one = []
        for x in beats:
            nx = dict(x)
            nx["fit"] = 1 if x["beat_idx"] == b["beat_idx"] else 5
            one.append(nx)
        cases.append(("only_%s" % (b.get("role") or b["beat_idx"]), one))

    # ⑥ 무작위 출발점 — 시드 고정으로 재현 가능하게, 전 비트에 임의 세그를 물린다.
    #    ★대조군의 의미(2026-08-30 교훈 "정렬률은 대조군 없으면 과장"): 재고가 좋으면
    #      아무거나 골라도 우연히 맞을 수 있다. 무작위 출발이 얼마나 나쁜지를 같이 재야
    #      "모델이 고쳤다"가 진짜인지 안다.
    rnd = random.Random(20260902)
    for k in range(12):
        ck = []
        for b in beats:
            nb = dict(b, fit=1)
            sid = rnd.choice(pool)
            nb["primary"] = dict(seg_map[sid])
            ck.append(nb)
        cases.append(("rand%02d" % k, ck))

    # ⑦ 역할만 남기고 화면을 통째로 비운다 — 백지에서 고르는 능력.
    blank = [dict(b, fit=1, primary={}) for b in beats]
    cases.append(("blank", blank))

    return cases


def main():
    # 사용법: py run_ab.py [모델...] [--repeat N]
    argv = list(sys.argv[1:])
    repeat = 1
    if "--repeat" in argv:
        i = argv.index("--repeat")
        repeat = int(argv[i + 1])
        del argv[i:i + 2]
    models = argv or ["opus", "gemini"]
    beats, seg_map = load_job()
    cases = build_cases(beats, seg_map)
    print("케이스 %d개 · 세그 %d개 · 모델 %s" % (len(cases), len(seg_map), models), flush=True)

    results, done = [], 0
    total = len(cases) * len(models) * repeat
    t_start = time.time()

    for rep in range(repeat):
      for cname, cbeats in cases:
        base_bad, base_detail = score(cbeats, seg_map)
        for model in models:
            done += 1
            tag = "%s_%s_r%d" % (cname, model, rep)
            print("[%d/%d] %s (출발 어긋남 %d)" % (done, total, tag, base_bad), flush=True)
            row = {"case": cname, "model": model, "rep": rep, "base_bad": base_bad,
                   "base_detail": base_detail, "n_beats": len(cbeats)}
            try:
                call = (make_claude_call(model, LOG_DIR, tag) if model != "gemini"
                        else make_gemini_call(LOG_DIR, tag))
                t0 = time.time()
                out = edit_plan._repick_weak_beats([dict(b) for b in cbeats], seg_map, call=call)
                row["seconds"] = round(time.time() - t0, 1)
                bad, detail = score(out, seg_map)
                row.update(after_bad=bad, after_detail=detail,
                           changed=sum(1 for d in detail if d["repicked"]),
                           delta=base_bad - bad, ok=True)
                print("      → 어긋남 %d→%d (교체 %d건, %.1fs)"
                      % (base_bad, bad, row["changed"], row["seconds"]), flush=True)
            except Exception as e:
                row.update(ok=False, error="%r" % (e,), tb=traceback.format_exc()[-1500:])
                print("      ✗ 예외: %r" % (e,), flush=True)
            results.append(row)
            # 매 건 저장 — 죽어도 여기까지는 남는다.
            with open(RESULTS, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=1)
            with open(PROGRESS, "w", encoding="utf-8") as f:
                json.dump({"done": done, "total": total,
                           "elapsed_min": round((time.time() - t_start) / 60, 1),
                           "last": tag}, f, ensure_ascii=False)

    print("\n완료: %d건 · %.1f분" % (len(results), (time.time() - t_start) / 60), flush=True)


if __name__ == "__main__":
    main()
