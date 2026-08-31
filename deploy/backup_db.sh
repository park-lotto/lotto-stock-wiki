#!/usr/bin/env bash
# 라이브 DB 자동 백업 (2026-09-01 신설)
#
# ★왜 만들었나: 3차 이전(EC2 c5a.4xlarge) 뒤 **자동 백업이 하나도 없었다**.
#   수동 스냅샷 1개(08-27)뿐이라, 그 뒤 고객 데이터가 통째로 무방비였다.
#   실측 당시 customers 350 · mix_jobs 1,054 · job_queue 6,351.
#
# ★무엇을 백업하나 — 되살릴 수 없는 것만.
#     reference.db (381MB)  고객·잡·키·레퍼런스 = **유일본**
#     /etc/shopping-shorts.env  API키·워커수·YT_RELAY 설정
#   mix_jobs(84G)·find_frames(18G) 같은 미디어는 뺀다 — 용량이 200배인데
#   다시 만들 수 있다. 여기까지 담으면 디스크가 먼저 죽는다.
#
# ★sqlite는 cp로 뜨면 깨질 수 있다(WAL 중간 상태). 온라인 백업 API를 쓴다 —
#   쓰기가 돌고 있어도 일관된 스냅샷을 만든다.
#   ⚠️`sqlite3` CLI는 이 서버에 **없다**(실측 2026-09-01). 설치하지 않고
#     파이썬 표준 sqlite3의 conn.backup()을 쓴다 — 같은 API다.
#
# 복구: gunzip -c <파일> > reference.db  (서비스 정지 후 교체)
set -euo pipefail

DATA=/home/ubuntu/lotto-stock-wiki/shopping_shorts/data
DEST=/home/ubuntu/backups/db
KEEP_DAYS=14                       # 2주치 보관 (하루 1개 × 약 90MB 압축 ≒ 1.3G)
STAMP=$(date +%Y%m%d-%H%M)

mkdir -p "$DEST"

# ── reference.db ──────────────────────────────────────────────
TMP="$DEST/.reference-$STAMP.db"
# 백업 + 무결성 검사를 한 번에. 깨진 백업을 남기면 있으나 마나라 여기서 거른다.
if ! python3 - "$DATA/reference.db" "$TMP" <<'PY'
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
s = sqlite3.connect("file:%s?mode=ro" % src, uri=True)
d = sqlite3.connect(dst)
s.backup(d)                      # 온라인 백업 — 쓰기 중에도 일관된 스냅샷
d.close(); s.close()
c = sqlite3.connect(dst)
ok = c.execute("PRAGMA integrity_check").fetchone()[0]
c.close()
if ok != "ok":
    sys.exit("integrity_check=%s" % ok)
PY
then
    rm -f "$TMP"
    echo "$(date '+%F %T') FAIL 백업/무결성 실패 — 버림" >&2
    exit 1
fi
gzip -f "$TMP"
mv "$TMP.gz" "$DEST/reference-$STAMP.db.gz"
echo "$(date '+%F %T') OK reference-$STAMP.db.gz ($(du -h "$DEST/reference-$STAMP.db.gz" | cut -f1))"

# ── 설정 파일(키 포함) ────────────────────────────────────────
# 640이라 ubuntu가 읽을 수 있다. 백업본도 같은 권한으로 좁혀 둔다.
if [ -r /etc/shopping-shorts.env ]; then
    cp /etc/shopping-shorts.env "$DEST/shopping-shorts.env-$STAMP"
    chmod 600 "$DEST/shopping-shorts.env-$STAMP"
fi

# ── 오래된 것 정리 ────────────────────────────────────────────
find "$DEST" -name 'reference-*.db.gz'        -mtime +$KEEP_DAYS -delete
find "$DEST" -name 'shopping-shorts.env-*'    -mtime +$KEEP_DAYS -delete

echo "$(date '+%F %T') 보관중 $(ls -1 "$DEST"/reference-*.db.gz 2>/dev/null | wc -l)개 · 총 $(du -sh "$DEST" | cut -f1)"
