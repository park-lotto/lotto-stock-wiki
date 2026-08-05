# -*- coding: utf-8 -*-
"""채널 히트작 대본 백필 (대본퀄 v6 채널스타일, 2026-08-05).

사장님 지시: 상위 채널(최우선 maison_homedino)의 대본을 확보해 채널별
'대본 스타일'을 학습시킨다. channel_archive의 조회수 상위 릴스 중
script_extracts에 대본이 없는 것을 내려받아 추출·저장한다.

- 호출당 상한(--limit, 기본 10) — 무한루프·429 사고 계보(2026-07-26) 준수
- 릴스당 다운로드 실패·추출 실패는 건너뛰고 계속(부분 성공 허용)
- 반드시 서버에서 환경 실어 실행할 것(세션 없이 돌면 login_wall):
    set -a; . /etc/shopping-shorts.env; set +a
    python3 -m shopping_shorts.scripts.backfill_channel_scripts --username maison_homedino
"""
import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path

from shopping_shorts import config
from shopping_shorts.store import Store


def backfill(store, username, limit=10, sleep_s=8, out=print):
    from shopping_shorts.media_download import download_any
    from shopping_shorts.script_extract import extract_auto

    with store._conn() as c:
        rows = c.execute(
            """SELECT a.shortcode, a.views FROM channel_archive a
               LEFT JOIN script_extracts e ON e.shortcode=a.shortcode
               WHERE a.username=? AND (e.shortcode IS NULL OR e.script_json IS NULL)
               ORDER BY a.views DESC LIMIT ?""", (username, limit)).fetchall()
    out(f"[{username}] 대상 {len(rows)}건 (조회수 상위, 대본 없음)")
    ok = fail = 0
    for shortcode, views in rows:
        url = f"https://www.instagram.com/reel/{shortcode}/"
        work = Path(tempfile.mkdtemp(prefix=f"bf_{shortcode}_"))
        try:
            video_path, caption = download_any(url, str(work))
            result = extract_auto(video_path, shortcode, caption=caption or "")
            if result and result.get("full_text"):
                store.save_script(shortcode, result)
                ok += 1
                out(f"  ✅ {shortcode} ({views:,}회) 본문 {len(result['full_text'])}자")
            else:
                fail += 1
                out(f"  ⚠️ {shortcode} 추출 빈 결과(키 소진 가능)")
        except Exception as e:  # noqa: BLE001 — 릴스 단위 실패는 계속 진행
            fail += 1
            out(f"  ❌ {shortcode} {str(e)[:100]}")
        finally:
            shutil.rmtree(work, ignore_errors=True)
        time.sleep(sleep_s)
    out(f"[완료] 성공 {ok} / 실패 {fail}")
    return ok, fail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--username", required=True)
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--sleep", type=int, default=8)
    ap.add_argument("--db", default=None)
    a = ap.parse_args()
    store = Store(a.db or config.DB_PATH)
    ok, _fail = backfill(store, a.username, limit=a.limit, sleep_s=a.sleep)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
