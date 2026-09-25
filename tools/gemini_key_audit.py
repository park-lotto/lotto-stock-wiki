# -*- coding: utf-8 -*-
"""제미니 공용 풀에서 '쓸 수 없는 키'를 서버 실제 에러 원문으로 점검한다(읽기 전용).

왜 만들었나(2026-09-25): 할당량 0·선불 소진·월 한도 키가 잠금 0번으로 일주일에 약 1만 5천 번
불렸다. 판정(key_vault.unusable_reason)을 처음엔 지어낸 에러 문자열로 테스트해 통과했는데,
서버 원문 9,097건을 하나도 못 잡았다 — 원문 재생으로만 드러났다. 그래서 이 점검을 도구로 남긴다.

서버에서:
    cd /home/ubuntu/lotto-stock-wiki && python3 tools/gemini_key_audit.py            # 최근 7일
    python3 tools/gemini_key_audit.py --days 1 --since-deploy "2026-09-25T20:00"   # 배포 뒤만

보는 것:
  ① 판정별 키 목록 — 기간 호출·성공·헛호출 수, 회원 번호(customer_keys.label 끝자리 대조)
  ② 놓친 것 — quota_limit_value 0 / 402 / spending cap 인데 판정이 None인 건(0이어야 한다)
  ③ 잘못 잡은 의심 — 판정된 키인데 판정 뒤에도 성공이 많은 키
  ④ 지금 정지 표시(key_vault 상태파일) — 몇 개가 빠져 있고 언제 다시 시험받나
키 원문은 출력하지 않는다(끝 6자만).
"""
import argparse
import collections
import datetime as dt
import os
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.atoms import key_vault  # noqa: E402

DB = ROOT / "shopping_shorts" / "data" / "reference.db"
_MISSED_HINT = re.compile(
    r"quota_limit_value['\"]?\s*:\s*['\"]?0(?![0-9.])|prepayment credits|spending cap", re.I)


def _ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=float, default=7.0)
    ap.add_argument("--since-deploy", default=None, help="UTC ISO — 이 시각 뒤만 센다(배포 효과 측정)")
    ap.add_argument("--db", default=str(DB), help="reference.db 경로(기본: 서버 위치)")
    a = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    since = a.since_deploy or (now - dt.timedelta(days=a.days)).isoformat()
    db = _ro(a.db)
    rows = db.execute("SELECT ts, key_tail, outcome, detail FROM api_events "
                      "WHERE service='gemini' AND ts>=? ORDER BY ts", (since,)).fetchall()
    print(f"[범위] {since} ~ 지금 · 제미니 이벤트 {len(rows):,}건")

    tot = collections.Counter()
    ok = collections.Counter()
    flagged = collections.defaultdict(collections.Counter)   # reason -> key -> 건수
    first_flag = {}
    ok_after_flag = collections.Counter()
    missed = collections.Counter()
    for ts, kt, oc, det in rows:
        tot[kt] += 1
        if oc == "ok":
            ok[kt] += 1
            if kt in first_flag and ts > first_flag[kt]:
                ok_after_flag[kt] += 1
            continue
        if oc == "lock":            # 우리 쪽 잠금 이벤트 — 구글 응답이 아니다
            continue
        r = key_vault.unusable_reason(Exception(det or ""))
        if r:
            flagged[r][kt] += 1
            first_flag.setdefault(kt, ts)
        elif _MISSED_HINT.search(det or ""):
            missed[kt] += 1

    # 회원 번호 대조(label 끝 5자 = 키 끝 5자). 원문 복호는 하지 않는다.
    owners = collections.defaultdict(list)
    try:
        for cid, label, status in db.execute(
                "SELECT customer_id, label, status FROM customer_keys WHERE service='gemini'"):
            if label:
                owners[str(label)[-5:]].append(f"회원{cid}({status})")
    except sqlite3.Error:
        pass

    names = {key_vault.UNUSABLE_NO_QUOTA: "할당량 0", key_vault.UNUSABLE_PREPAY: "선불 소진",
             key_vault.UNUSABLE_SPEND_CAP: "월 지출 한도", key_vault.UNUSABLE_AUTH: "무효·삭제·비활성"}
    wasted = 0
    print("\n① 판정별")
    for r, keys in flagged.items():
        print(f"  [{names.get(r, r)}] 키 {len(keys)}개")
        for kt, n in keys.most_common():
            wasted += n
            who = ",".join(owners.get((kt or "")[-5:], [])) or "사장님 env/미상"
            print(f"     …{kt}: 호출 {tot[kt]:,} · 성공 {ok[kt]:,} · 이 판정 {n:,} · {who}")
    print(f"  → 헛호출 합계 {wasted:,}건")

    print("\n② 놓친 것(0이어야 한다):", sum(missed.values()), "건 / 키", len(missed))
    for kt, n in missed.most_common(10):
        print(f"     …{kt}: {n}")

    print("\n③ 판정 뒤에도 성공한 키(잘못 잡은 의심 — 충전·한도 상향으로 살아났을 수도)")
    sus_ok = [(k, n) for k, n in ok_after_flag.most_common() if n]
    if not sus_ok:
        print("     없음")
    for kt, n in sus_ok[:15]:
        print(f"     …{kt}: 판정 뒤 성공 {n}")

    print("\n④ 지금 정지 표시(key_vault 상태파일)")
    info = key_vault.suspension_info()
    nowts = now.timestamp()
    if not info:
        print("     없음")
    for fp, ent in sorted(info.items(), key=lambda x: x[1].get("since", 0)):
        until = float(ent.get("until", 0))
        left = (until - nowts) / 3600
        state = f"{left:.1f}시간 남음" if left > 0 else "만료(다시 시험 대기)"
        print(f"     …{ent.get('tail', '?')}: {names.get(ent.get('reason'), ent.get('reason'))} · {state}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
