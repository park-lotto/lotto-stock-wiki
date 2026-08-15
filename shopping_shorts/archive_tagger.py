"""아카이브 비전태깅 — 채널당 N개씩 라운드로빈 (2026-08-04).

왜 분리했나(사장님 지시): 태깅이 channel_archive 크롤 안에 박혀 있어서 한 채널에서
500건을 붙잡고 **채널당 34분**을 썼다. 691채널이면 16일이고, 그동안 뒤쪽 채널은
아카이브에 **아예 없었다**. 게다가 큰 채널은 2,300개 중 500개만 태깅한 채 done으로
닫혀 나머지 1,800건은 영영 안 붙었다(실측 @ddock_sun 21%).

그래서 순서를 뒤집는다 — **깊이 우선 → 너비 우선**:

    1바퀴: 691채널 × 각 10개(조회수 상위)  → 전 채널에 태그가 조금씩 생긴다
    2바퀴: 691채널 × 11~20위
    3바퀴: ...

한 바퀴만 돌아도 모든 채널에서 카테고리 필터·유사검색이 작동한다. 지금처럼 "앞
11채널만 완벽하고 680채널은 0"인 상태보다 훨씬 쓸모 있다.

**썸네일 만료(실측 2026-08-03)**: 인스타 CDN URL의 `oe` 파라미터가 만료시각
(hex 유닉스타임)이고 수명은 **약 4일**이다. 4.2h 지난 썸네일 40/40 다운로드 성공,
`oe`를 과거로 조작하거나 서명(`oh`)을 훼손하면 403 — 서명은 실제로 강제되지만
유효기간이 길다. 크롤 전체가 3일이면 끝나므로 1바퀴는 안전하다.
만료된 건 fetch가 실패해 조용히 건너뛴다(그 릴스만 태그 없이 남는다 = 종전 수준).
→ 재크롤로 썸네일을 갱신하는 건 **다음 작업**이다(사장님: "썸네일 채우는건 그 뒤에").

실행:
    python -m shopping_shorts.archive_tagger                # 1바퀴, 채널당 10개
    python -m shopping_shorts.archive_tagger --per-channel 10 --rounds 3
    python -m shopping_shorts.archive_tagger --rounds 0     # 태울 게 없을 때까지 계속
"""
import argparse
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor

from shopping_shorts.config import DB_PATH
from shopping_shorts.store import Store
from shopping_shorts import usage_meter

_ITEM_GAP_S = (0.3, 0.9)     # 태깅 사이 짧은 휴식(CDN 예의)
_BUSY_POLL_S = 60            # 렌더 양보 중 재확인 주기
# 한 배치를 몇 갈래로 동시에 태울지(2026-08-06). 순차 처리가 진짜 병목이었다 —
# 키가 23개인데 한 번에 하나씩만 써서 하룻밤 8,655건에 그쳤다(이론상 50만건).
# 키풀 로테이션은 _STATE_LOCK으로 이미 스레드안전하고 tag_one은 건별 독립이라
# 그대로 병렬화된다. 환경변수로 조절: ARCHIVE_TAG_WORKERS.
_WORKERS = max(1, int(os.getenv("ARCHIVE_TAG_WORKERS", "8")))


def pick_batch(store, username, per_channel):
    """이 채널에서 '아직 태그 없는' 릴스를 조회수순으로 per_channel개.

    라운드로빈이 자연히 성립하는 이유: 태깅에 성공하면 vision_tags에 남아 다음
    바퀴의 NOT EXISTS에서 빠진다. 그래서 2바퀴째는 자동으로 11~20위가 된다.
    별도 커서를 두지 않는 게 핵심이다 — 실패한 건 다음 바퀴에 자연히 재시도된다."""
    with store._conn() as c:
        rows = c.execute(
            "SELECT a.shortcode, a.thumbnail FROM channel_archive a "
            "WHERE a.username=? AND a.thumbnail!='' "
            "  AND NOT EXISTS(SELECT 1 FROM vision_tags v WHERE v.shortcode=a.shortcode) "
            "ORDER BY a.views DESC LIMIT ?",
            (username, per_channel)).fetchall()
    return [{"shortcode": r[0], "thumbnail": r[1]} for r in rows]


def pick_global_batch(store, limit):
    """채널 구분 없이 **전체에서 조회수 높은 순**으로 미태깅 릴스 limit개(2026-08-09).

    왜 바꿨나(사장님 지시 "조회수 맨 위부터 매일"): 종전엔 채널 라운드로빈이라
    '미태깅이 많이 남은 채널'의 40위 영상이 작은 채널의 1위보다 먼저 태깅됐다.
    전체 순위와 무관하게 도는 셈이라, 미태깅 144,594건 중 **51%가 조회수 1만
    미만**인데 그것들이 상위 영상보다 먼저 소모될 수 있었다(실측: 미태깅 최고
    조회수가 398만인데 아직 안 됨 / 태깅완료엔 조회수 9짜리가 들어있음).

    이 기능의 목적은 "오늘 터진 영상 → 옛 히트작 매칭"이라 **터진 영상부터**
    태그가 붙어야 값어치가 있다. 상위 16,193건(10만+)이면 하루 한도로 2~3일이다.

    라운드로빈이 원래 노린 '전 채널에 태그를 조금씩 깔기'는 이미 달성됐다
    (1바퀴 완주 571채널). 그래서 지금이 전역순으로 바꿀 적기다."""
    with store._conn() as c:
        rows = c.execute(
            "SELECT a.shortcode, a.thumbnail FROM channel_archive a "
            "WHERE a.thumbnail!='' "
            "  AND NOT EXISTS(SELECT 1 FROM vision_tags v WHERE v.shortcode=a.shortcode) "
            "ORDER BY a.views DESC LIMIT ?",
            (limit,)).fetchall()
    return [{"shortcode": r[0], "thumbnail": r[1]} for r in rows]


def archived_usernames(store):
    """아카이브에 릴스가 있는 채널 — 태그 없는 릴스가 많은 순.

    많이 남은 채널부터 도는 게 커버리지 회복이 빠르다(작은 채널은 금방 소진되고
    큰 채널이 계속 뒤로 밀리는 걸 막는다)."""
    with store._conn() as c:
        rows = c.execute(
            "SELECT a.username, COUNT(*) FROM channel_archive a "
            "WHERE a.thumbnail!='' "
            "  AND NOT EXISTS(SELECT 1 FROM vision_tags v WHERE v.shortcode=a.shortcode) "
            "GROUP BY a.username ORDER BY COUNT(*) DESC").fetchall()
    return [(r[0], r[1]) for r in rows]


def tag_one(video_analysis, store, it):
    """릴스 1건 태깅. 성공 True. 썸네일 만료(403)·키 실패는 False — 무해하게 건너뛴다."""
    img = video_analysis.fetch_thumb_bytes(it.get("thumbnail"))
    if not img:
        return False
    with usage_meter.track(op="태깅"):
        tags = video_analysis.subject_tags_vision(img, "")
    if tags and (tags.get("subject") or tags.get("keywords")):
        store.save_vision_tags(it["shortcode"], tags.get("subject", ""),
                               tags.get("keywords", []))
        return True
    return False


def run_global(batch_size=200, sleep=time.sleep, log=print):
    """조회수 높은 순으로 태울 게 없을 때까지(2026-08-09 사장님 지시).

    커서를 두지 않는다 — 성공분이 vision_tags에 남아 다음 배치의 NOT EXISTS에서
    빠지므로, 매번 '지금 남은 것 중 조회수 최상위'를 다시 집는다. 실패분(썸네일
    만료·키 소진)은 다음 배치에 그대로 다시 올라오므로, 같은 배치를 무한 반복하지
    않도록 **연속 0건이면 멈춘다**(키가 하루 한도를 다 쓴 상태를 뜻한다).
    """
    try:
        from shopping_shorts import video_analysis
    except Exception as e:      # noqa: BLE001
        log(f"[태거] 비전 모듈 없음 — 중단: {str(e)[:80]}")
        return 0

    store = Store(DB_PATH)
    total = 0
    dry = 0
    while True:
        while store.heavy_job_running():   # 사용하면서 태깅 — 렌더에 양보
            log(f"[태거] 렌더 진행 중 → {_BUSY_POLL_S}s 대기")
            sleep(_BUSY_POLL_S)
        batch = pick_global_batch(store, batch_size)
        if not batch:
            log("[태거] 태그 없는 릴스가 없다 — 종료")
            break

        def _one(it):
            try:
                return bool(tag_one(video_analysis, store, it))
            except Exception as e:   # noqa: BLE001
                log(f"[태거] {it['shortcode']} 실패(무시): {str(e)[:60]}")
                return False

        with ThreadPoolExecutor(max_workers=_WORKERS) as ex:
            ok = sum(ex.map(_one, batch))
        total += ok
        log(f"[태거] 배치 {len(batch)}건 → {ok}건 성공 (누적 {total:,})")
        if ok:
            dry = 0
        else:
            dry += 1
            # 2연속 0건이면 키가 하루 한도를 다 썼거나 이 구간이 전부 만료다.
            # 계속 돌면 같은 배치를 무한 재시도하며 CPU만 태운다.
            if dry >= 2:
                log("[태거] 2배치 연속 0건 — 키 소진 또는 만료 구간으로 판단, 종료")
                break
        sleep(random.uniform(*_ITEM_GAP_S))
    log(f"[태거] 전체 종료 — 총 {total:,}건 태깅")
    return total


def run(per_channel=10, rounds=1, sleep=time.sleep, log=print):
    """채널당 per_channel개씩 rounds바퀴. rounds=0이면 태울 게 없을 때까지.

    ⚠️ 채널 라운드로빈 방식(구). 지금 기본 경로는 run_global(조회수순)이다 —
    남겨둔 이유는 '전 채널에 골고루 태그를 깔아야' 할 때(신규 채널 대량 유입 등)
    다시 쓸 수 있어서다. `--mode channel`로 호출한다."""
    try:
        from shopping_shorts import video_analysis
    except Exception as e:      # noqa: BLE001 — 비전 모듈이 없으면 할 일이 없다
        log(f"[태거] 비전 모듈 없음 — 중단: {str(e)[:80]}")
        return 0

    store = Store(DB_PATH)
    total = 0
    rnd = 0
    while True:
        rnd += 1
        if rounds and rnd > rounds:
            break
        chans = archived_usernames(store)
        if not chans:
            log("[태거] 태그 없는 릴스가 없다 — 종료")
            break
        remain = sum(n for _, n in chans)
        log(f"[태거] {rnd}바퀴 시작 — {len(chans)}채널, 미태깅 {remain:,}건, "
            f"채널당 {per_channel}개")
        done_this_round = 0
        for idx, (u, _n) in enumerate(chans, 1):
            while store.heavy_job_running():   # 사용하면서 태깅 — 렌더에 양보
                log(f"[태거] 렌더 진행 중 → {_BUSY_POLL_S}s 대기")
                sleep(_BUSY_POLL_S)
            batch = pick_batch(store, u, per_channel)
            if not batch:
                continue
            def _one(it):
                """한 건 태깅 — 실패는 삼킨다(한 건이 배치를 멈추면 안 된다)."""
                try:
                    return bool(tag_one(video_analysis, store, it))
                except Exception as e:   # noqa: BLE001
                    log(f"[태거] @{u} {it['shortcode']} 실패(무시): {str(e)[:60]}")
                    return False

            if _WORKERS > 1:
                with ThreadPoolExecutor(max_workers=_WORKERS) as ex:
                    ok = sum(ex.map(_one, batch))
                sleep(random.uniform(*_ITEM_GAP_S))   # 채널 사이 한 번만 쉰다
            else:
                ok = 0
                for it in batch:
                    ok += _one(it)
                    sleep(random.uniform(*_ITEM_GAP_S))
            total += ok
            done_this_round += ok
            log(f"[태거] {rnd}바퀴 {idx}/{len(chans)} @{u}: {ok}/{len(batch)}건 "
                f"(누적 {total:,})")
        log(f"[태거] {rnd}바퀴 종료 — {done_this_round:,}건")
        if not done_this_round:
            # 한 바퀴 다 돌았는데 0건이면 남은 건 전부 만료·실패다. 무한루프 방지.
            log("[태거] 이번 바퀴 0건 — 더 태울 게 없다(썸네일 만료 추정). 종료")
            break
    log(f"[태거] 전체 종료 — 총 {total:,}건 태깅")
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("views", "channel"), default="views",
                    help="views=전체 조회수순(기본) / channel=채널 라운드로빈(구)")
    ap.add_argument("--batch", type=int, default=200,
                    help="views 모드에서 한 배치 크기 (기본 200)")
    ap.add_argument("--per-channel", type=int, default=10,
                    help="channel 모드에서 채널당 몇 개씩 (기본 10)")
    ap.add_argument("--rounds", type=int, default=1,
                    help="channel 모드에서 몇 바퀴 (0=태울 게 없을 때까지)")
    a = ap.parse_args()
    if a.mode == "views":
        run_global(batch_size=a.batch)
    else:
        run(per_channel=a.per_channel, rounds=a.rounds)


if __name__ == "__main__":
    main()
