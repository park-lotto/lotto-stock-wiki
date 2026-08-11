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
from shopping_shorts import vision_tagging
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
    # ★빈 결과 가드(2026-08-06): 세션 만료 등으로 0건이 나오면 저장하지 않는다.
    # 저장하면 화면 랭킹 캐시(last_run)가 빈 목록으로 덮여 "아무것도 안 뜨는" 사고가 난다
    # (실사고 2026-08-06 09:00 회차: 만료 세션으로 0건 수집 → 캐시 [] 덮임 → 랭킹 공백).
    # 직전 정상 캐시를 남겨두는 쪽이 항상 낫다 — 다음 회차가 성공하면 자연 갱신된다.
    # 부분수집 가드(2026-08-09): 7건짜리 반쪽 수집이 정상 랭킹(수백 건)을 덮은 실사고.
    # 계정 차단·챌린지로 일부만 긁혔을 때는 직전 캐시를 지키는 게 낫다.
    _MIN_ITEMS = 50
    if items and len(items) < _MIN_ITEMS:
        print(f"[daily_instagram_collect] {len(items)}건뿐(기준 {_MIN_ITEMS} 미만) — 부분수집으로 보고 캐시 미갱신(직전 랭킹 유지)", file=sys.stderr)
        return 1
    if not items:
        print("[daily_instagram_collect] 0건 수집 — 캐시 미갱신(직전 랭킹 유지), "
              "세션 만료 여부 확인 필요", file=sys.stderr)
        return 1
    collected_at = datetime.now(timezone.utc).isoformat()
    Store(DB_PATH).save_last_run(items, collected_at)

    # ★후속: 비전태깅 + 그 태그로 재분류(2026-07-31).
    # 이 스크립트가 웹 엔드포인트(app._run_collect_job)를 대체하면서 거기 배선돼 있던
    # 후속 처리가 통째로 빠졌다 — 실측: vision_tags가 2026-07-30 10:41(마지막 수동수집)
    # 이후 0건 증가. 게다가 캡션이 100% 비어(429 회피로 상세조회 off) 분류가 채널명만
    # 보게 돼 카테고리가 무너졌다. 태깅→재분류를 여기서 잇는다.
    # 실패해도 수집 결과는 이미 저장돼 있으므로 삼킨다(더 나빠지지 않는다).
    try:
        tagged = vision_tagging.tag_new_items(items, DB_PATH)
        changed = vision_tagging.recategorize_by_vision(items, DB_PATH)
        changed += vision_tagging.apply_channel_category(items, DB_PATH)   # 태그 없는 것만 채널지정으로
        if changed:
            Store(DB_PATH).save_last_run(items, collected_at)   # 바뀐 category를 화면 캐시에 반영
        print(f"[daily_instagram_collect] 비전태깅 {tagged}건 · 카테고리 재분류 {changed}건")
    except Exception as e:  # noqa: BLE001
        print(f"[daily_instagram_collect] 후속(비전태깅/재분류) 실패: {e!r}", file=sys.stderr)

    # ★수집 직후 레퍼런스 길이 백필(2026-08-11). 수집으로 피드가 새 영상으로 갈리면
    #   길이 캐시가 비어 아침마다 ⏱이 사라졌다(durfill은 시간당 소량이라 못 따라잡음).
    #   여기서 새 피드가 대부분 찰 때까지 채운다 — 남은 게 전부 실패상한(삭제·비공개
    #   릴)이면 멈춘다. ★각 패스를 서브프로세스로 격리한다: Playwright 드라이버가
    #   대량조회 중 EPIPE로 프로세스를 통째로 죽이는 일이 있어(실측 2026-08-11),
    #   격리하면 그 패스만 죽고 다음이 이어진다. 수집 결과는 이미 저장돼 안전하다.
    try:
        _backfill_reference_durations()
    except Exception as e:  # noqa: BLE001
        print(f"[daily_instagram_collect] 길이 백필 실패(무해): {e!r}", file=sys.stderr)

    print(f"[daily_instagram_collect] {len(items)}건 수집 · {time.time() - t0:.1f}s")
    return 0


def _backfill_reference_durations(max_passes=15, per=40):
    """레퍼런스 피드 길이가 대부분 찰 때까지 run_backfill을 격리 서브프로세스로 반복."""
    import subprocess
    from shopping_shorts import duration_backfill as df

    def _pending():
        s = Store(DB_PATH)
        scs = [i.get("shortcode") for i in s.load_last_run()[0] if i.get("shortcode")]
        cached = s.duration_map(scs)
        fails = s.duration_fail_map(scs)
        cov = len(cached)
        pend = sum(1 for sc in scs
                   if sc not in cached and fails.get(sc, 0) < df.MAX_FAIL)
        return cov, len(scs), pend

    for _ in range(max_passes):
        cov, total, pend = _pending()
        if pend == 0:                    # 남은 건 전부 실패상한(영구불가) — 그만
            break
        try:
            subprocess.run(
                [sys.executable, "-m", "shopping_shorts.duration_backfill",
                 "--limit", str(per)],
                timeout=260, check=False)
        except Exception as e:           # 서브프로세스 크래시/타임아웃 — 다음 패스로
            print(f"[daily_instagram_collect] 백필 패스 실패(계속): {e!r}", file=sys.stderr)
    cov, total, pend = _pending()
    print(f"[daily_instagram_collect] 레퍼런스 길이 백필: {cov}/{total} "
          f"(처리가능 잔여 {pend})")


if __name__ == "__main__":
    raise SystemExit(main())
