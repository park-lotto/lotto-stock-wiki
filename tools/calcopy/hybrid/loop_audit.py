# -*- coding: utf-8 -*-
"""완주 기록에서 '같은 반려가 되풀이된 곳'을 센다(사장님 10-27 "고칠 수 있고 막을 수 있는 문제인데 또 왜 그러냐 / 하기 전에 계획을 다 짜라").

flow_dev 가 남긴 flow_log.jsonl · job/reviews/*/answer.json 을 읽기만 한다.
  ① 세부 단계별 걸린 분(다음 기록까지의 시간을 그 단계에 붙인다)
  ② 판정(review) 종류별 횟수·평균 초
  ③ 반려 사유 묶음 — 사유 글의 열쇠말로 묶는다(KINDS). 묶음에 안 드는 것은 '기타'로 원문 앞부분을 보여 준다

    PYTHONUTF8=1 py -m tools.calcopy.hybrid.loop_audit <작업 폴더> [<작업 폴더> …] [--other 10]
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

KINDS = [   # (묶음 이름, 열쇠말) — 위에서부터 처음 맞는 것 하나
    ("장면 전환 걸침", r"샷 .{0,12}(끝|경계).{0,6}넘|걸쳐|장면 전환|장면이 바뀌|장면 경계|편집 전환|끊김|다음 샷으로"),
    ("같은 샷 겹침·재사용", r"같은 샷|같은 화면|겹쳐|재사용|같은 장면"),
    ("남의 얼굴", r"얼굴|리뷰어|광고 모델"),
    ("컷 수·길이 맞추기", r"컷이 적|컷 하나였|컷 하나와|컷뿐|나눴다|중앙값|컷이 바뀌는 곳이 없"),
    ("사진 컷", r"사진|photo_share"),
    ("대사-화면 안 맞음", r"대사.*(맞지|안 맞|약하)|보이지 않|빠지면서|맞는 장면이 없"),
    ("컷 길이", r"컷 길이|길다|짧다"),
    ("말속도·목소리", r"말속도|목소리|TTS"),
    ("박힌 글자", r"글자|자막|워터마크"),
    ("확인 못 함", r"확인하지 못|확인 못|보지 못|권한이 없"),
]


def _sec(t: str) -> int:
    h, m, s = map(int, t.split(":"))
    return h * 3600 + m * 60 + s


def kind_of(p: str) -> str:
    return next((k for k, rx in KINDS if re.search(rx, p)), "기타")


def audit(W: Path, n_other: int = 10) -> dict:
    rows = [json.loads(x) for x in (W / "flow_log.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    phase_min: dict = collections.Counter()
    for a, b in zip(rows, rows[1:]):
        if a.get("phase") and a.get("t") and b.get("t"):
            d = _sec(b["t"]) - _sec(a["t"])
            phase_min[a["phase"]] += d + (86400 if d < 0 else 0)
    rv = collections.defaultdict(list)
    for r in rows:
        if r.get("review") and r.get("sec") is not None:
            rv[re.sub(r"_.*", "", str(r["review"]))].append(int(r["sec"]))
    reasons, other, rejects = collections.Counter(), [], collections.Counter()
    d = W / "job" / "reviews"
    for a in sorted(d.glob("*/answer.json")) if d.exists() else []:
        try:
            ans = json.loads(a.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if not isinstance(ans, dict) or ans.get("ok") is not False:
            continue
        rejects[re.sub(r"^\d+_|_.*$", "", a.parent.name)] += 1
        for p in ans.get("problems") or []:
            k = kind_of(str(p))
            reasons[k] += 1
            if k == "기타" and len(other) < n_other:
                other.append(str(p)[:120])
    starts = [r for r in rows if "start" in r]
    ends = [r for r in rows if "end" in r]
    return {"work": str(W), "runs": len(starts), "ends": [(e.get("t"), e.get("end"), (e.get("stage") or {}).get("text")) for e in ends],
            "phase_min": {k: round(v / 60, 1) for k, v in phase_min.most_common(8)},
            "reviews": {k: [len(v), round(sum(v) / len(v))] for k, v in sorted(rv.items(), key=lambda x: -sum(x[1]))},
            "rejects": dict(rejects), "reasons": dict(reasons.most_common()), "other": other}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work", nargs="+")
    ap.add_argument("--other", type=int, default=10)
    a = ap.parse_args()
    for w in a.work:
        r = audit(Path(w), a.other)
        print(f"\n== {r['work']}  실행 {r['runs']}번  끝 {r['ends']}")
        print("  단계별 분:", r["phase_min"])
        print("  판정 [횟수, 평균초]:", r["reviews"])
        print("  반려 수:", r["rejects"])
        print("  반려 사유:", r["reasons"])
        for o in r["other"]:
            print("   · 기타:", o)


if __name__ == "__main__":
    main()
