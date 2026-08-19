"""예열 영구래치 해제 — 일시 실패로 잘못 소진된 재시도 기회를 돌려준다(2026-08-19).

## 왜 필요한가

`produce_autoload.attempts >= 3`이면 예열이 그 영상을 **영원히 건너뛴다**
(`prewarm.run_prewarm` → `skipped_latched`). 래치는 "이 영상은 아무리 해도 안 된다"를
기억하는 장치인데, 여태 **일시 실패(구글 5xx·타임아웃·429)까지 같은 칸에 태웠다**.
그래서 서버가 잠깐 흔들린 동안 담긴 영상이 영구 제외됐다.

원인은 `prewarm.py`에서 고쳤다(`_is_transient` → `autoload_rollback_attempt`).
이 스크립트는 **그 전에 이미 물려 있는 것**을 구제한다. 새 코드가 배포된 뒤 한 번만 돌리면 된다.

## 무엇을 푸는가 (보수적으로)

```
푼다   ① 사유가 비어 있는 것(last_error IS NULL/'')  — 왜 실패했는지 기록이 없다.
          영구 실패라 단정할 근거가 없으므로 한 번 더 기회를 준다.
       ② 사유가 '일시'로 판정되는 것(prewarm._is_transient) — 5xx·타임아웃·429.
안 푼다 ③ 영구 실패로 판정되는 것 — 비공개·삭제·무자막·Unsupported URL 등.
          이건 다시 태워봐야 크레딧만 샌다.
       ④ 이미 대본이 있는 것 — 풀 이유가 없다(예열이 `already`로 끝난다).
```

★판정은 `prewarm._is_transient` **한 곳**을 그대로 쓴다 — 여기 따로 적으면
언젠가 두 판단이 어긋난다(CLAUDE.md 0순위-B).

## 쓰는 법

    python -m scripts.prewarm_unlatch            # 미리보기(아무것도 안 바꾼다)
    python -m scripts.prewarm_unlatch --apply    # 실제 적용

서버에서:
    cd /home/ubuntu/lotto-stock-wiki && python3 -m scripts.prewarm_unlatch --apply
"""
import argparse
import sqlite3
import sys

from shopping_shorts.config import DB_PATH
from shopping_shorts.prewarm import _is_transient

#: prewarm._PREWARM_MAX_ATTEMPTS 와 같은 뜻 — 그 상수를 그대로 읽어 쓴다.
try:
    from shopping_shorts.prewarm import _PREWARM_MAX_ATTEMPTS as MAX_ATTEMPTS
except ImportError:                       # 이름이 바뀌면 보수적 기본값
    MAX_ATTEMPTS = 3


def classify(shortcode, attempts, last_error, has_script):
    """(풀까?, 사유) — 판정 근거를 문자열로 함께 돌려준다(로그에 남기려고)."""
    if has_script:
        return False, "이미 대본 있음(풀 필요 없음)"
    if not (last_error or "").strip():
        return True, "사유 기록 없음 — 영구 실패 근거 없음"
    if _is_transient(last_error):
        return True, "일시 실패(5xx·타임아웃·429)"
    return False, "영구 실패로 판정 — 다시 태우면 크레딧만 샌다"


def main(argv=None):
    ap = argparse.ArgumentParser(description="예열 영구래치 해제(일시 실패분만)")
    ap.add_argument("--apply", action="store_true", help="실제로 적용(없으면 미리보기)")
    ap.add_argument("--db", default=DB_PATH, help="DB 경로")
    args = ap.parse_args(argv)

    con = sqlite3.connect(args.db)
    rows = con.execute(
        "SELECT a.shortcode, a.attempts, a.last_error, "
        "       (SELECT COUNT(*) FROM script_extracts s "
        "         WHERE s.shortcode = a.shortcode AND COALESCE(s.script_json,'') != '') "
        "  FROM produce_autoload a WHERE a.attempts >= ?", (MAX_ATTEMPTS,)).fetchall()

    unlatch, keep = [], []
    for sc, att, err, has_script in rows:
        ok, why = classify(sc, att, err, bool(has_script))
        (unlatch if ok else keep).append((sc, att, why, (err or "")[:60]))

    print(f"래치된 항목: {len(rows)}건 (attempts >= {MAX_ATTEMPTS})")
    print(f"\n▶ 풀 대상 {len(unlatch)}건")
    for sc, att, why, err in unlatch:
        print(f"   {sc[:30]:32} a={att}  {why}  {err}")
    print(f"\n▶ 그대로 둘 것 {len(keep)}건")
    for sc, att, why, err in keep:
        print(f"   {sc[:30]:32} a={att}  {why}  {err}")

    if not args.apply:
        print("\n(미리보기 — 실제로 바꾸려면 --apply)")
        return 0
    if not unlatch:
        print("\n풀 것이 없습니다.")
        return 0
    with con:
        con.executemany(
            "UPDATE produce_autoload SET attempts=0, "
            "       last_error='래치 해제(일시 실패 오분류 구제 2026-08-19)', "
            "       updated_at=datetime('now') WHERE shortcode=?",
            [(sc,) for sc, _a, _w, _e in unlatch])
    print(f"\n✅ {len(unlatch)}건 래치 해제 — 다음 예열부터 재시도합니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
