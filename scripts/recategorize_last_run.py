# -*- coding: utf-8 -*-
"""이미 저장된 수집분의 카테고리만 새 규칙으로 다시 매긴다 (2026-09-04).

## 왜 필요한가
카테고리는 **수집 시점**에 박힌다(ranking.py의 빌더가 categorize()를 부른다).
그래서 categorize.py를 고쳐도 **이미 저장된 last_run은 옛 분류 그대로**라
다음 수집(유튜브는 하루 1회)까지 화면이 안 바뀐다.

## 하는 일 / 안 하는 일
- 한다  : settings의 last_run::<platform> 안 items의 `category` 필드만 다시 계산해 저장
- 안 한다: 크롤·API 호출(0회), 그 밖의 어떤 필드도 건드리지 않음

## 안전장치
- --dry-run 이 기본값이 아니지만, 실행 전 **자동으로 백업 행을 남긴다**
  (settings key = `backup::last_run::<platform>::<타임스탬프>`) → 되돌리려면 그 값을 복사.
- 변경 전/후 분포를 찍어 눈으로 확인하고 넘어간다.

사용:
    python -m scripts.recategorize_last_run --platform youtube --dry-run
    python -m scripts.recategorize_last_run --platform youtube
    python -m scripts.recategorize_last_run --platform youtube --restore <백업키>
"""
import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone

from shopping_shorts.categorize import categorize


def _load(c, key):
    row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", default="youtube")
    ap.add_argument("--db", default="shopping_shorts/data/reference.db")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--restore", default=None, help="백업 키를 주면 그 값으로 되돌린다")
    a = ap.parse_args()

    key = f"last_run::{a.platform}"
    with sqlite3.connect(a.db) as c:
        if a.restore:
            src = _load(c, a.restore)
            if not src:
                print("그 백업 키가 없습니다:", a.restore)
                return
            c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
                      (key, json.dumps(src, ensure_ascii=False)))
            print(f"되돌렸습니다 — {a.restore} → {key} ({len(src.get('items') or [])}편)")
            return

        data = _load(c, key)
        if not data:
            print("수집분이 없습니다:", key)
            return
        items = data.get("items") or []
        # ★원본을 **고치기 전에** 통째로 떠 둔다 — 아래에서 items를 제자리 수정하므로
        #   나중에 뜨면 '변경 후'가 백업으로 남아 되돌리기가 무의미해진다.
        original_json = json.dumps(data, ensure_ascii=False)
        before = Counter(x.get("category") for x in items)

        changed = 0
        for x in items:
            new = categorize(x.get("name") or "", x.get("caption") or "")
            if new != x.get("category"):
                x["category"] = new
                changed += 1
        after = Counter(x.get("category") for x in items)

        print(f"{key} — {len(items)}편 중 {changed}편의 카테고리가 바뀝니다")
        for k in sorted(set(before) | set(after), key=lambda k: -after.get(k, 0)):
            b, af = before.get(k, 0), after.get(k, 0)
            mark = f"  {af - b:+d}" if af != b else ""
            print(f"  {str(k):10s} {b:5d} → {af:5d}{mark}")

        if a.dry_run:
            print("\n--dry-run 이라 저장하지 않았습니다.")
            return

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        bkey = f"backup::{key}::{stamp}"
        c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
                  (bkey, original_json))          # ★고치기 전에 떠 둔 원본
        print(f"\n⚠️ 백업 키: {bkey}")
        c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
                  (key, json.dumps(data, ensure_ascii=False)))
        print("저장 완료 — 화면 새로고침하면 바로 보입니다.")


if __name__ == "__main__":
    main()
