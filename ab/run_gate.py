# -*- coding: utf-8 -*-
"""실험 2 — "모델이 문제인가, 문(gate)이 문제인가".

★왜 이걸 재나:
  실험 1에서 제미니도 `all_open`(문을 열어준 상태)에서 어긋남 3→0을 만들었다.
  그렇다면 라이브에서 훅이 '사용중'으로 나가는 진짜 원인은 **모델의 판단력**이 아니라
  **`fit=5`라 재픽 대상에 안 들어간 것**일 수 있다(08-18 핸드오프의 진단과 일치).

  이건 모델 교체와 완전히 다른 처방이다:
    · 모델이 문제 → 오푸스로 바꿔야 함 (원가 상승, 서버 배선 필요)
    · 문이 문제  → fit 판정을 고치면 됨 (제미니 그대로, 원가 0)

  두 처방은 비용이 100배 차이난다. 그래서 갈라서 재야 한다.

측정 방식:
  같은 비트·같은 인벤토리에 대해 `min_fit` 문턱만 바꿔가며(=문을 얼마나 여느냐)
  두 모델이 각각 얼마나 고치는지 본다.
"""
import io
import json
import os
import sys
import time
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = r"C:/Users/CH/Desktop/로또의 주식"
sys.path.insert(0, _ROOT)
sys.path.insert(0, _HERE)
os.chdir(_ROOT)

from shopping_shorts import edit_plan  # noqa: E402
from run_ab import load_job, score  # noqa: E402
from ab_repick import make_claude_call, make_gemini_call  # noqa: E402

LOG_DIR = os.path.join(_HERE, "logs_gate")
os.makedirs(LOG_DIR, exist_ok=True)
OUT = os.path.join(_HERE, "gate_results.json")
PROG = os.path.join(_HERE, "gate_progress.json")


def main():
    repeat = 5
    if "--repeat" in sys.argv:
        repeat = int(sys.argv[sys.argv.index("--repeat") + 1])
    beats, seg_map = load_job()

    # 라이브 그대로(fit=5) vs 문을 연 상태(fit=1). 그 사이를 fit 값으로 훑는다.
    #   fit=5 → 재픽 대상 0개(현재 라이브 동작)
    #   fit=3 → _repick_weak_beats의 기본 문턱(<=3)에 걸려 들어간다
    fits = [5, 4, 3, 2, 1]
    models = ["opus", "gemini"]

    rows = []
    total = len(fits) * len(models) * repeat
    done = 0
    t0all = time.time()
    print("문턱 실험: fit %s × 모델 %s × %d회 = %d건"
          % (fits, models, repeat, total), flush=True)

    for rep in range(repeat):
        for fit in fits:
            cb = [dict(b, fit=fit) for b in beats]
            base, _ = score(cb, seg_map)
            for m in models:
                done += 1
                tag = "fit%d_%s_r%d" % (fit, m, rep)
                row = {"fit": fit, "model": m, "rep": rep, "base_bad": base}
                try:
                    call = (make_claude_call(m, LOG_DIR, tag) if m != "gemini"
                            else make_gemini_call(LOG_DIR, tag))
                    t0 = time.time()
                    out = edit_plan._repick_weak_beats(
                        [dict(b) for b in cb], seg_map, call=call)
                    sec = round(time.time() - t0, 1)
                    after, det = score(out, seg_map)
                    row.update(after_bad=after, seconds=sec, ok=True,
                               called=sec > 0.5,
                               changed=sum(1 for d in det if d["repicked"]),
                               detail=det)
                    print("[%d/%d] %s  어긋남 %d→%d %s"
                          % (done, total, tag, base, after,
                             "(미호출)" if sec <= 0.5 else "(%.1fs)" % sec), flush=True)
                except Exception as e:
                    row.update(ok=False, error="%r" % (e,),
                               tb=traceback.format_exc()[-800:])
                    print("[%d/%d] %s  ✗ %r" % (done, total, tag, e), flush=True)
                rows.append(row)
                json.dump(rows, io.open(OUT, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=1)
                json.dump({"done": done, "total": total,
                           "elapsed_min": round((time.time() - t0all) / 60, 1)},
                          io.open(PROG, "w", encoding="utf-8"), ensure_ascii=False)

    print("\n완료 %d건 · %.1f분" % (len(rows), (time.time() - t0all) / 60), flush=True)


if __name__ == "__main__":
    main()
