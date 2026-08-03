"""대본 품질 백테스트 — 엔진 버전(v2/v3/v4…)을 같은 실데이터로 반복 비교한다.

왜 이렇게 만드는가(2026-07-30 실측):
- 대본 품질은 눈으로만 보면 매번 흔들린다. 감각어를 강화하니 어미가 무너지고
  (tone 1.00→0.67), 어미를 고치니 훅이 중복됐다.
- 결정적으로 **같은 입력·같은 코드인데 실행마다 tone이 ±0.4 흔들린다**(Gemini 비결정성:
  R1 0.90 → R2 0.34인 fixture가 있었다). 그래서 **1회 생성 비교는 노이즈**다.
  → fixture마다 여러 번(repeat) 돌려 평균·최저로 판단한다.

★가짜 하네스 금지: mix_pipeline이 부르는 그 함수(build_scene_first_plan)를
  그 인자(source_scripts = job.extract.values())로 그대로 부른다.

사용:
    python tools/script_backtest.py fixtures.json out.json --engine v3 --repeat 3
    python tools/script_backtest.py fixtures.json out.json --batch 10 --offset 0
    python tools/script_backtest.py --report out.json [이전.json]
"""
import argparse
import io
import json
import statistics
import sys
import traceback



def _live_kwargs():
    """★라이브(mix_pipeline)가 build_scene_first_plan에 실제로 넘기는 인자를 그대로 만든다.

    2026-07-31 실사고: 이 하네스가 기본값(핑퐁·백본·은행 OFF)으로만 돌아서 **라이브와 다른
    경로**를 재고 있었다. 같은 소재가 라이브 경로에선 67~94자, 기본 경로에선 157~185자로
    나왔다 — 그동안의 지표가 사장님이 받는 대본을 대표하지 못했다.
    설정값은 서버가 아니라 로컬 DB에서 읽히므로, 서버와 같게 강제로 켜서 맞춘다.
    """
    from shopping_shorts import bank_assemble
    from shopping_shorts.store import Store
    from shopping_shorts.config import DB_PATH
    bank_context = ""
    try:
        bank_context = bank_assemble.parts_block(Store(DB_PATH))
    except Exception:
        bank_context = ""      # 로컬 DB가 비면 은행 블록 없이 — 나머지 경로는 그대로 검증된다
    return {"ping_pong": True, "backbone_base": True, "judge": True,
            "bank_context": bank_context}


def _txt(rec):
    return "\n".join(n for _, n in (rec or {}).get("beats", []) if n)


def _key(job_id, run):
    return f"{job_id}#{run}"


def generate(fixtures, out_path, retries=4, only_missing=True, engine=None, repeat=1, live=False):
    """fixture × repeat회 실제 생성. 키는 'job_id#run'이라 반복분이 각각 남는다.

    retries: 키풀에 403/쿼터 소진 키가 섞여 빈 결과가 나온다(실측). 볼트 로테이션에 맡겨 재시도.
    only_missing: 이미 있는 (job, run)은 건너뛴다 — 중단 후 이어서 돌릴 수 있고 과금을 아낀다.
    """
    from shopping_shorts.edit_plan import build_scene_first_plan
    kw = _live_kwargs() if live else {}
    try:
        done = {r["key"]: r for r in json.load(io.open(out_path, encoding="utf-8"))}
    except Exception:
        done = {}
    for j in fixtures:
        for run in range(repeat):
            k = _key(j["job_id"], run)
            if only_missing and done.get(k, {}).get("beats"):
                continue
            src = list(j["extract"].values())          # mix_pipeline.py와 동일한 인자
            for attempt in range(retries):
                try:
                    sf = build_scene_first_plan(src, j.get("given_script") or "",
                                                j.get("target_seconds") or 30,
                                                n_candidates=3, engine=engine, **kw)
                except Exception:
                    traceback.print_exc()
                    continue
                cands = sf.get("candidates") or []
                if not cands:
                    continue
                rec = next((c for c in cands if c.get("recommended")), cands[0])
                done[k] = {
                    "key": k, "job_id": j["job_id"], "run": run, "engine": engine or "v3",
                    "live": bool(live),
                    "topic": (j.get("given_script") or "")[:40],
                    "beats": [(b.get("role", ""), (b.get("narration") or "").strip())
                              for b in (rec.get("plan") or {}).get("beats") or []]}
                print(f"  ok {j['job_id'][:8]}#{run} (시도 {attempt + 1})", flush=True)
                break
            else:
                print(f"  FAIL {j['job_id'][:8]}#{run}", flush=True)
            json.dump(list(done.values()), io.open(out_path, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)   # 중간 저장 — 중단돼도 앞 결과는 남는다
    return done


def measure(rec):
    """대본 1건의 품질 지표 — 사장님이 말한 축만 본다(말투·감각어·구조)."""
    from shopping_shorts import tone_score
    t = _txt(rec)
    if not t:
        return None
    prof = tone_score.ending_profile(t)
    sens = tone_score.sensory_profile(t)
    sc = tone_score.score_conversational(t)
    beats = [(r, n) for r, n in rec.get("beats", []) if n]
    roles = [r for r, _ in beats]
    return {
        "tone": sc["score"], "flags": sc["flags"],
        "live": prof["live_ratio"], "plain": prof["plain_ratio"],
        "sensory": sens["count"], "intens": sens["intensifiers"],
        "chars": len(t.replace("\n", "").replace(" ", "")),
        "cta_last": bool(roles) and "cta" in roles[-1].lower(),
        "long_beats": sum(1 for _, n in beats if len(n) > 55),
        "banmal_cta": bool(beats) and beats[-1][1].rstrip("!.?").endswith(("줘", "봐", "해")),
    }


def _by_job(path):
    """job_id → [측정치...] (반복분 묶음)."""
    out = {}
    for rec in json.load(io.open(path, encoding="utf-8")):
        m = measure(rec)
        if m:
            out.setdefault(rec.get("job_id", rec.get("key", "?")), []).append(m)
    return out


def report(cur_path, prev_path=None):
    cur = _by_job(cur_path)
    prev = _by_job(prev_path) if prev_path else {}
    if not cur:
        print("측정할 대본이 없다"); return
    print(f"{'job':<10}{'n':>3}{'tone평균':>9}{'최저':>7}{'전회':>7}"
          f"{'생생':>6}{'감각':>5}{'강조':>5}{'글자':>6}  구조결함")
    print("-" * 88)
    rows = []
    for jid, ms in sorted(cur.items(), key=lambda kv: statistics.fmean(m["tone"] for m in kv[1])):
        avg = statistics.fmean(m["tone"] for m in ms)
        lo = min(m["tone"] for m in ms)
        pv = prev.get(jid)
        pv_s = f"{statistics.fmean(m['tone'] for m in pv):.2f}" if pv else "  -"
        bad = []
        if any(not m["cta_last"] for m in ms):
            bad.append("CTA끝X")
        if any(m["long_beats"] for m in ms):
            bad.append("긴비트")
        if any(m["banmal_cta"] for m in ms):
            bad.append("반말CTA")
        print(f"{jid[:8]:<10}{len(ms):>3}{avg:>9.2f}{lo:>7.2f}{pv_s:>7}"
              f"{statistics.fmean(m['live'] for m in ms):>6.0%}"
              f"{statistics.fmean(m['sensory'] for m in ms):>5.1f}"
              f"{statistics.fmean(m['intens'] for m in ms):>5.1f}"
              f"{statistics.fmean(m['chars'] for m in ms):>6.0f}  {' '.join(bad) or 'OK'}")
        rows.append((jid, avg, lo, ms))
    allm = [m for _, _, _, ms in rows for m in ms]
    n_job, n_run = len(rows), len(allm)
    print("-" * 88)
    print(f"job {n_job}개 · 생성 {n_run}건 | 평균 tone {statistics.fmean(m['tone'] for m in allm):.3f}"
          f" | 최저 {min(m['tone'] for m in allm):.2f}"
          f" | tone<0.8 {sum(1 for m in allm if m['tone'] < 0.8)}건"
          f" | 감각어0 {sum(1 for m in allm if m['sensory'] == 0)}건"
          f" | 긴비트 {sum(1 for m in allm if m['long_beats'])}건"
          f" | 반말CTA {sum(1 for m in allm if m['banmal_cta'])}건"
          f" | CTA끝X {sum(1 for m in allm if not m['cta_last'])}건")
    # 반복이 2회 이상이면 흔들림을 보여준다 — 개선인지 노이즈인지 판단의 기준.
    multi = [ms for _, _, _, ms in rows if len(ms) >= 2]
    if multi:
        spread = statistics.fmean(max(m["tone"] for m in ms) - min(m["tone"] for m in ms)
                                  for ms in multi)
        print(f"같은 fixture 반복 편차 평균 {spread:.2f}  "
              f"→ 이보다 작은 버전 간 차이는 **노이즈로 본다**")
    if prev:
        common = [(jid, a) for jid, a, _, _ in rows if jid in prev]
        if common:
            d = statistics.fmean(a - statistics.fmean(m["tone"] for m in prev[jid])
                                 for jid, a in common)
            worse = [jid[:8] for jid, a in common
                     if a < statistics.fmean(m["tone"] for m in prev[jid]) - 0.05]
            print(f"전회 대비 평균 {d:+.3f}"
                  + (f"  ⚠️ 나빠진 job: {', '.join(worse)}" if worse else "  (뚜렷한 회귀 없음)"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("args", nargs="*")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--all", action="store_true", help="이미 성공한 것도 다시 생성")
    ap.add_argument("--engine", default=None, help="엔진 버전(v2/v3…)")
    ap.add_argument("--repeat", type=int, default=1, help="fixture당 생성 횟수(편차 흡수)")
    ap.add_argument("--batch", type=int, default=0, help="한 번에 돌릴 fixture 수(0=전부)")
    ap.add_argument("--live", action="store_true",
                    help="라이브와 동일한 파이프라인 인자로 생성(핑퐁·백본·은행·심사)")
    ap.add_argument("--offset", type=int, default=0, help="배치 시작 위치")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if a.report:
        report(a.args[0], a.args[1] if len(a.args) > 1 else None)
        return
    fx = json.load(io.open(a.args[0], encoding="utf-8"))
    if a.batch:
        fx = fx[a.offset:a.offset + a.batch]
    print(f"백테스트 — 엔진 {a.engine or 'v3'} · fixture {len(fx)}건 × {a.repeat}회"
          + ("  [라이브 설정: 핑퐁·백본·은행·심사 ON]" if a.live else "  [기본 설정]"))
    generate(fx, a.args[1], only_missing=not a.all, engine=a.engine, repeat=a.repeat,
             live=a.live)
    print()
    report(a.args[1], a.args[2] if len(a.args) > 2 else None)


if __name__ == "__main__":
    main()
