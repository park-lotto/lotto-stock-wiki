"""인스타 레퍼런스랭킹 자동수집(무료 Playwright 경로) — systemd 타이머가
하루 3회(09/15/21시 KST) 실행(2026-07-29).

앱 HTTP를 거치지 않고 service.collect(platform="instagram")를 직접 호출한다.
- 인증/페이월 우회(관리자 세션 불필요)
- 앱과 같은 DB(config.DB_PATH, 모듈 기준 고정경로)에 run 스냅샷 저장 →
  다음 조회 시 랭킹·가속(delta)이 갱신돼 있음.
config.INSTAGRAM_SCRAPER가 playwright면 무료(세션쿠키+서버직결), apify면 유료 —
이 스크립트는 값을 강제하지 않고 서버 env(/etc/shopping-shorts.env) 설정을 그대로 따른다.

★2026-07-30 수정: service.collect()는 snapshots 테이블(delta 이력용)만 갱신하고,
화면(/api/reference)이 읽는 last_run 캐시(store.save_last_run)는 건드리지 않는다 —
그 캐시는 원래 웹 UI "지금 수집" 버튼 경로(app.py _run_collect_job)에서만 채워졌다.
그 결과 크론이 매일 정상 수집해도 화면 랭킹·"마지막 수집" 시각이 갱신되지 않는
버그가 있었다(실측: 크론은 09/15/21시 계속 성공했는데 화면은 마지막 수동수집
시각에 멈춰 있었음). 크론도 같은 캐시를 갱신하도록 save_last_run 호출을 추가한다.
"""
import sys
import time
from datetime import datetime, timezone

from shopping_shorts import service
from shopping_shorts.config import DB_PATH
from shopping_shorts.store import Store


def main():
    t0 = time.time()
    # ★렌더 양보(2026-07-30): 최종렌더가 도는 중이면 이번 회차를 건너뛴다.
    # 1GB·2vCPU 서버에서 ffmpeg와 Playwright가 겹치면 swap으로 밀려 렌더가 8분+로
    # 기어간다(실측 load average 11.76 / swap 1204MB). 다음 회차(6시간 뒤)에 돌면 되고,
    # 수집은 누적이라 한 번 건너뛰어도 데이터가 사라지지 않는다.
    if Store(DB_PATH).heavy_job_active():
        print("[daily_instagram_collect] 렌더/믹스 진행 중 — 이번 회차 스킵(다음 타이머에 수집)")
        return 0
    try:
        items = service.collect(platform="instagram")
    except Exception as e:  # noqa: BLE001 — 크론이 죽어도 서비스는 무사, 로그만 남긴다
        print(f"[daily_instagram_collect] 실패: {e!r}", file=sys.stderr)
        return 1
    collected_at = datetime.now(timezone.utc).isoformat()
    Store(DB_PATH).save_last_run(items, collected_at)
    print(f"[daily_instagram_collect] {len(items)}건 수집 · {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
