"""태깅층 기준선 측정 — 저장된 추출 결과를 tag_qa로 채점해 숫자로 남긴다 (Layer 3).

왜 하는가: 슬롯 기반 화면조합(대본퀄v3)이 이 태깅 위에 전부 서 있는데, 지금은 태깅층이
좋은지 나쁜지 **아무도 숫자로 모른다**. 대본퀄v3의 실측 결과가 나빴을 때 "슬롯 문제냐
태깅 문제냐"를 가르려면 그 전에 찍어둔 기준선이 있어야 한다.

═══════════════════════════════════════════════════════════════════════════
★★ 기준선 규칙 — 이걸 어기면 다음 측정이 통째로 무의미해진다 ★★

  1. **기준선은 서버 DB로 잡는다** (ubuntu@3.39.179.148:/home/ubuntu/lotto-stock-wiki).
     회사PC·집PC 로컬 DB는 각각 다른 데이터가 들어 있어 숫자가 서로 다르다.
     한 번 서버로 잡았으면 **이후 측정도 계속 서버에서** 돌려야 비교가 된다.
     로컬에서 돌린 값을 서버 기준선과 비교하지 마라 — 그건 개선/악화가 아니라 딴 표본이다.

  2. **코호트를 섞지 마라.** 아래 A/B는 점수 체계가 다르다(커버리지 검사 유무).
     한 평균에 합치면 배포 전후 비교가 조용히 틀어진다. 이 도구는 절대 안 합친다.

  3. 출력 머리말의 `측정 기준`(DB 경로·행수·mtime)을 **기록과 함께 남겨라.**
     나중에 "이 숫자 어느 DB였지?"가 되면 그 기준선은 버리는 수밖에 없다.
═══════════════════════════════════════════════════════════════════════════

코호트가 왜 갈리나 (★핵심 함정):
  `validate_extract(result, duration)`는 duration이 None이면 **커버리지 검사(가중 0.20)를
  건너뛴다**(tag_qa.py `_check_coverage`, fail-open). DB엔 `script_json`만 있고 원본 영상은
  없으므로, 여기서 재계산한 점수는 실시간 채점보다 **최대 0.20 높게** 나온다.
  - 코호트 A = `tag_qa`가 result에 이미 박혀 있는 건(Layer 1 배포 후 추출).
    실시간에 영상 길이를 알고 매긴 **커버리지 포함** 점수. → 이게 진짜 기준선이다.
    (`_attach_qa`가 결과 dict에 넣고, 그게 script_json에 통째로 저장되는 경로를 탄다)
  - 코호트 B = `tag_qa`가 없는 레거시(배포 전 추출). 재계산할 수밖에 없고
    **커버리지 제외** 점수다. 상한 편향이 있으니 A와 비교하지 말고 추세만 봐라.

사용:
    python tools/tag_audit.py                      # 기본 20건, config.DB_PATH
    python tools/tag_audit.py --n 50
    python tools/tag_audit.py --db /path/reference.db --json out.json

서버에서:
    cd /home/ubuntu/lotto-stock-wiki && python3 tools/tag_audit.py --n 50
"""
import argparse
import json
import sqlite3
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shopping_shorts import tag_qa  # noqa: E402

# 점수 히스토그램 구간 — 0.6은 script_extract._QA_RETRY_BELOW(재시도 기준선)와 같은 값이라
# "재시도가 걸렸어야 할 수준"이 한눈에 보인다.
_BUCKETS = ((0.0, 0.4, "0.0~0.4 심각"),
            (0.4, 0.6, "0.4~0.6 불량"),
            (0.6, 0.8, "0.6~0.8 보통"),
            (0.8, 1.01, "0.8~1.0 양호"))

_WORST_N = 5          # 최악 몇 건까지 shortcode를 찍을까
_FLAG_TOP = 6         # 최빈 flags 몇 개까지


def _flag_kind(flag):
    """flags 문구에서 검사 종류만 뽑는다 — 뒤의 수치까지 붙으면 전부 다른 문자열이 돼
    빈도 집계가 무의미해진다('커버리지 부족: 68%' vs '...71%')."""
    return (flag or "").split(":", 1)[0].strip() or "(빈 flag)"


def load_rows(db_path, limit):
    """script_extracts에서 최근 N건. 최근순인 이유: 기준선은 '지금 태깅층'을 재는 것이라
    1년 전 추출까지 섞으면 과거 프롬프트의 성적이 현재 점수를 오염시킨다.

    extracted_at이 NULL인 옛 행은 뒤로 밀린다(NULLS LAST를 sqlite 식으로)."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=15.0)
    try:
        cur = con.execute(
            "SELECT shortcode, script_json, extracted_at FROM script_extracts "
            "ORDER BY (extracted_at IS NULL), extracted_at DESC LIMIT ?",
            (limit,),
        )
        return cur.fetchall()
    finally:
        con.close()


def score_rows(rows):
    """행 → 채점 레코드. 코호트를 여기서 가른다(위 머리말 참조).

    파싱 실패는 버리지 않고 cohort='깨짐'으로 남긴다 — 조용히 빼면 표본이 실제보다
    건강해 보인다(fail-open의 대가는 '이상한 게 있다'는 사실 자체를 숨기지 않는 것)."""
    out = []
    for shortcode, raw, extracted_at in rows:
        try:
            result = json.loads(raw)
        except Exception:
            out.append({"shortcode": shortcode, "cohort": "깨짐", "score": None,
                        "flags": ["script_json 파싱 실패"], "extracted_at": extracted_at})
            continue
        stored = (result or {}).get("tag_qa") or {}
        if isinstance(stored, dict) and stored.get("score") is not None:
            out.append({"shortcode": shortcode, "cohort": "A",
                        "score": float(stored.get("score")),
                        "flags": list(stored.get("flags") or []),
                        "retried": bool(stored.get("retried")),
                        "extracted_at": extracted_at})
            continue
        # 레거시 — 재계산. duration을 모르므로 커버리지는 빠진다(상한 편향).
        # ★try로 감싸는 이유: 여기 들어오는 건 **정체불명의 옛 행**이다. 지금 스키마와 다른
        #   타입(예: change가 bool)이 한 줄만 섞여도 validate_extract가 죽으면 감사 전체가
        #   중단된다 — 기준선을 재려고 만든 도구가 표본 하나 때문에 아무 숫자도 못 내는 건
        #   본말전도다. 죽은 행은 숨기지 않고 '깨짐'으로 세어 표본에서 눈에 띄게 남긴다.
        try:
            score, flags = tag_qa.validate_extract(result, None)
        except Exception as e:
            out.append({"shortcode": shortcode, "cohort": "깨짐", "score": None,
                        "flags": [f"채점 실패({type(e).__name__}): {e}"],
                        "extracted_at": extracted_at})
            continue
        out.append({"shortcode": shortcode, "cohort": "B", "score": score,
                    "flags": flags, "retried": None, "extracted_at": extracted_at})
    return out


def summarize(records, cohort):
    """한 코호트의 분포·최빈 flags·최악 목록. 순수 함수라 DB 없이 테스트된다."""
    picked = [r for r in records if r["cohort"] == cohort and r["score"] is not None]
    if not picked:
        return None
    scores = [r["score"] for r in picked]
    hist = []
    for lo, hi, label in _BUCKETS:
        n = sum(1 for s in scores if lo <= s < hi)
        hist.append({"label": label, "n": n, "pct": round(n * 100 / len(scores), 1)})
    flags = Counter(_flag_kind(f) for r in picked for f in r["flags"])
    worst = sorted(picked, key=lambda r: r["score"])[:_WORST_N]
    retried = [r for r in picked if r.get("retried")]
    return {
        "cohort": cohort,
        "n": len(picked),
        "avg": round(statistics.mean(scores), 3),
        "median": round(statistics.median(scores), 3),
        "min": round(min(scores), 3),
        "max": round(max(scores), 3),
        "below_retry_line": sum(1 for s in scores if s < 0.6),
        "clean": sum(1 for r in picked if not r["flags"]),
        "retried": len(retried) if cohort == "A" else None,
        "hist": hist,
        "top_flags": flags.most_common(_FLAG_TOP),
        "worst": [{"shortcode": r["shortcode"], "score": r["score"],
                   "flags": r["flags"]} for r in worst],
    }


_COHORT_DESC = {
    "A": "저장 점수(실시간 채점, 커버리지 포함) — ★진짜 기준선",
    "B": "레거시 재계산(커버리지 제외, 최대 +0.20 상한 편향) — A와 비교 금지",
}


def _print_summary(s):
    print(f"\n── 코호트 {s['cohort']}: {_COHORT_DESC[s['cohort']]}")
    print(f"   표본 {s['n']}건 | 평균 {s['avg']} | 중앙 {s['median']} | "
          f"최저 {s['min']} | 최고 {s['max']}")
    line = f"   무결점(flags 0) {s['clean']}건 | 재시도선(0.6) 미만 {s['below_retry_line']}건"
    if s["retried"] is not None:
        line += f" | 실제 재시도됨 {s['retried']}건"
    print(line)
    print("   분포:")
    for b in s["hist"]:
        bar = "█" * int(b["pct"] / 5)
        print(f"     {b['label']:<14} {b['n']:>4}건 {b['pct']:>5.1f}% {bar}")
    if s["top_flags"]:
        print("   최빈 flags:")
        for kind, n in s["top_flags"]:
            print(f"     {n:>4}회  {kind}")
    print(f"   최악 {len(s['worst'])}건:")
    for r in s["worst"]:
        head = "; ".join(r["flags"])[:90] or "(flags 없음)"
        print(f"     {r['score']:<6} {r['shortcode']:<16} {head}")


def main(argv=None):
    # 윈도우 콘솔 기본은 cp949라 ❌·█·⚠️에서 UnicodeEncodeError로 죽는다(실측).
    # 기준선은 회사PC에서도 돌려볼 수 있어야 하므로 stdout을 UTF-8로 돌린다
    # (script_backtest.py:199와 같은 처방). 서버는 원래 UTF-8이라 무해.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="태깅층 QA 기준선 측정 (Layer 3)")
    ap.add_argument("--n", type=int, default=20, help="표본 수(기본 20)")
    ap.add_argument("--db", default=None, help="reference.db 경로(기본 config.DB_PATH)")
    ap.add_argument("--json", default=None, help="결과를 JSON으로도 저장할 경로")
    args = ap.parse_args(argv)

    if args.db:
        db_path = Path(args.db)
    else:
        from shopping_shorts.config import DB_PATH
        db_path = Path(DB_PATH)

    if not db_path.exists():
        print(f"❌ DB가 없다: {db_path}")
        print("   트랙 폴더는 DB가 gitignore라 비어 있다 — 서버에서 돌려라(머리말 규칙 1).")
        return 2

    rows = load_rows(db_path, args.n)
    if not rows:
        print(f"❌ script_extracts가 비었다: {db_path}")
        print("   빈 DB의 '0건'을 기준선으로 남기지 마라 — 다음 측정이 개선으로 오독된다.")
        return 2

    records = score_rows(rows)
    stamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    mtime = datetime.fromtimestamp(db_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")

    print("=" * 72)
    print("태깅층 QA 기준선 (tools/tag_audit.py)")
    print("=" * 72)
    print("측정 기준 ★이 4줄을 숫자와 함께 남겨라 — 없으면 나중에 비교 못 한다:")
    print(f"  DB     : {db_path}")
    print(f"  DB갱신 : {mtime}   (표본 {len(rows)}건 요청 {args.n}건)")
    print(f"  측정시 : {stamp}")
    print("  ⚠️ 기준선은 서버 DB 기준으로 통일한다. 로컬 값과 섞어 비교하지 마라.")

    broken = [r for r in records if r["cohort"] == "깨짐"]
    printed = False
    for cohort in ("A", "B"):
        s = summarize(records, cohort)
        if s:
            _print_summary(s)
            printed = True
    if not printed:
        print("\n채점 가능한 행이 없다(전부 파싱 실패).")
    if broken:
        print(f"\n⚠️ script_json 파싱 실패 {len(broken)}건: "
              + ", ".join(r["shortcode"] for r in broken[:_WORST_N]))

    a = summarize(records, "A")
    if not a:
        print("\n※ 코호트 A가 0건이다 = Layer 1 배포 후 추출된 영상이 아직 없다는 뜻.")
        print("  B(재계산)는 커버리지가 빠져 점수가 후하다 — 이걸 기준선으로 삼지 마라.")
        print("  영상 몇 건을 새로 담아 추출을 태운 뒤 다시 돌리는 게 맞다.")

    if args.json:
        payload = {"db": str(db_path), "db_mtime": mtime, "measured_at": stamp,
                   "requested_n": args.n, "rows": len(rows),
                   "cohort_A": summarize(records, "A"),
                   "cohort_B": summarize(records, "B"),
                   "broken": [r["shortcode"] for r in broken]}
        Path(args.json).write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        print(f"\n💾 {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
