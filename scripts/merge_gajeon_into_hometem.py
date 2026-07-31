"""옛 '가전' 라벨을 '홈템'으로 이관한다 — 2026-07-31 2차 병합(사장님 결정).

코드만 바꾸면 DB에 남은 '가전'이 통제 어휘 밖으로 떨어져 고아 버킷이 된다(2026-07-16
1차 병합에서 겪은 것과 같은 문제). 화면은 TOPIC_CTYPE에 가전→홈템 매핑을 남겨 흡수하지만,
저장된 데이터 자체도 정리해야 학습·통계·필터가 갈라지지 않는다.

★비가역이다(합치면 어느 쪽이었는지 정보가 사라진다). 실행 전 백업을 떴다:
   /tmp/gajeon_merge_backup/pre_merge.json

사용:  python3 -m scripts.merge_gajeon_into_hometem [--dry-run]
"""
import argparse
import json
import sqlite3

from shopping_shorts.config import DB_PATH

OLD, NEW = "가전", "홈템"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    c = sqlite3.connect(DB_PATH)
    report = {}

    # 1) 테이블의 category 컬럼들
    for table in ("script_extracts", "discovered_channels", "channel_categories"):
        try:
            n = c.execute(f"SELECT COUNT(*) FROM {table} WHERE category=?", (OLD,)).fetchone()[0]
        except sqlite3.OperationalError:
            continue          # 그 테이블/컬럼이 없는 배포도 있다 — 조용히 건너뛴다
        report[table] = n
        if n and not a.dry_run:
            c.execute(f"UPDATE {table} SET category=? WHERE category=?", (NEW, OLD))

    # 2) last_run 스냅샷(JSON 안에 들어 있어 UPDATE로 못 고친다)
    row = c.execute("SELECT items_json FROM last_run WHERE id=1").fetchone()
    if row:
        items = json.loads(row[0])
        n = sum(1 for i in items if i.get("category") == OLD)
        report["last_run"] = n
        if n and not a.dry_run:
            for i in items:
                if i.get("category") == OLD:
                    i["category"] = NEW
            c.execute("UPDATE last_run SET items_json=? WHERE id=1",
                      (json.dumps(items, ensure_ascii=False),))

    if not a.dry_run:
        c.commit()
    print(("[dry-run] " if a.dry_run else "") + f"'{OLD}' → '{NEW}' 이관: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
