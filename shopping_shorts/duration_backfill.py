"""영상 길이(초) 백필 — 랭킹 카드의 ⏱ 표시용 (2026-08-04).

배경: 인스타 그리드 GraphQL 응답엔 video_duration이 아예 없다(서버 실측 2026-08-04,
onshome_official·phc2589 각 12노드 전수 확인). 길이를 알려면 릴스마다 1회 추가 조회가
필요한데, 릴스 상세 REST를 무제한으로 부르면 429 사고(2026-07-30, 하루 950건 → 수집
급감)가 재발한다. 그래서:

- **인스타는 릴 상세 노드의 video_dash_manifest**에서 mediaPresentationDuration을 읽는다
  (서버 실측 2026-08-04 3/3 성공: 33.2s·25.5s·24.6s). yt-dlp 인스타 추출기는 404로
  죽어 있어(같은 날 실측) 못 쓴다. 브라우저는 배치당 1번만 띄운다(_detail_context 공유).
- **유튜브·틱톡은 yt-dlp 메타**(--skip-download) — 쿠키 처리는 media_download 재사용.
- **shortcode당 평생 1회** — 길이는 불변이라 reel_durations 캐시에 한 번 넣으면 끝.
- **회당 상한 + 호출 간격** — 한 번의 백필이 랭킹 전체를 몰아치지 않는다.
- 실패도 기록(fail_count) — 죽은 릴스를 매번 두드리지 않는다(3회 넘으면 포기).

트리거는 /api/reference가 1시간에 1번 워커 큐(durfill)에 넣는다 — systemd 유닛
추가 없이 git 배포만으로 돈다.
"""
import re
import subprocess
import sys
import time

from shopping_shorts.config import DB_PATH
from shopping_shorts.media_download import _cookies_arg, _proxy_arg
from shopping_shorts.store import Store

# 회당 최대 조회 수 — 새 릴스는 하루 100~200건 수준이라 몇 번의 백필로 다 채워진다.
PER_RUN_LIMIT = 40
# 조회 사이 간격(초) — 인스타 429 계보를 의식한 완충. 40건 × 2s ≈ 80s + 조회시간.
SLEEP_SEC = 2.0
# 이 횟수만큼 실패한 shortcode는 더 안 두드린다(삭제·비공개 릴스).
MAX_FAIL = 3
# 한 번에 훑을 아카이브(역대 히트작) 릴스 수 — 조회수 상위부터.
# ★왜 전부가 아닌가: 아카이브는 78,265건이다(2026-08-06 실측). 전부 대상에 넣어도 회당
#   PER_RUN_LIMIT(40)만 조회하니 결과는 같지만, 매 실행마다 7만 건을 SELECT·필터링하는 건
#   낭비다. 상위 N만 보면 "사장님이 실제로 보는 카드"부터 채워진다(정렬=조회수 DESC).
ARCHIVE_SCAN_LIMIT = 600

_PAGE = {
    "instagram": "https://www.instagram.com/reel/{id}/",
    "youtube": "https://www.youtube.com/watch?v={id}",
    "tiktok": "https://www.tiktok.com/@x/video/{id}",
}

# DASH 매니페스트의 전체 길이 — 예: PT0H0M34.966S
_DASH_DUR = re.compile(r'mediaPresentationDuration="PT(?:(\d+)H)?(?:(\d+)M)?([\d.]+)S"')


def _manifest_duration(node):
    """릴 상세 노드의 video_dash_manifest → 길이(초). 없거나 못 읽으면 None."""
    m = _DASH_DUR.search((node or {}).get("video_dash_manifest") or "")
    if not m:
        return None
    dur = int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + float(m.group(3))
    return dur if dur > 0 else None


def probe_duration(platform, video_id, timeout=45):
    """(유튜브·틱톡) yt-dlp 메타 1회로 길이(초). 실패 시 None (다운로드 없음).

    인스타는 여기로 오면 안 된다 — yt-dlp 인스타 추출기가 404로 죽어 있다(2026-08-04
    실측). 인스타는 run_backfill의 _detail_context 배치 경로가 처리한다."""
    page = _PAGE.get(platform, "").format(id=video_id) if platform in _PAGE else ""
    if not page or not video_id:
        return None
    try:
        r = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--skip-download", "--no-warnings",
             "--print", "duration", *_cookies_arg(page), *_proxy_arg(page), page],
            capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    except Exception:                              # noqa: BLE001 — 타임아웃 포함, 한 건 실패로 안 죽는다
        return None
    out = (r.stdout or "").strip().splitlines()
    if r.returncode != 0 or not out:
        return None
    try:
        dur = float(out[0])
    except (TypeError, ValueError):
        return None
    return dur if dur > 0 else None


def _targets(store):
    """지금 화면(last_run 전 플랫폼)에 있는데 길이를 모르는 (platform, shortcode) 목록."""
    seen, out = set(), []
    feeds = [("instagram", store.load_last_run()[0])]
    for p in ("youtube", "tiktok", "reddit", "douyin", "xiaohongshu"):
        try:
            feeds.append((p, store.load_last_run_platform(p)[0]))
        except Exception:                          # noqa: BLE001 — 플랫폼 하나가 비어도 계속
            continue
    for platform, items in feeds:
        if platform not in _PAGE:
            continue                               # 조회 경로가 없는 플랫폼은 건너뜀
        for i in items or []:
            sc = (i.get("shortcode") or "").strip()
            if not sc or sc in seen:
                continue
            seen.add(sc)
            if i.get("duration") in (None, "", 0):
                out.append((platform, sc))
    # ★아카이브(역대 히트작)도 대상에 넣는다(2026-08-06 사장님: 히트작 카드에 ⏱ 표시).
    #   예전엔 last_run만 봐서 아카이브는 **영원히 대상이 아니었다** — 78,265건 중 길이를
    #   아는 205건은 랭킹에 우연히 겹친 것뿐이었다.
    #   랭킹 뒤에 붙인다: 지금 보는 화면이 먼저고, 아카이브는 남는 자리를 채운다.
    #   조회수 DESC라 사장님이 실제로 보는 상위 카드부터 채워진다.
    try:
        with store._conn() as c:
            rows = c.execute(
                "SELECT shortcode FROM channel_archive "
                "WHERE shortcode IS NOT NULL AND shortcode != '' "
                "ORDER BY views DESC LIMIT ?", (ARCHIVE_SCAN_LIMIT,)).fetchall()
        for (sc,) in rows:
            sc = (sc or "").strip()
            if not sc or sc in seen:
                continue
            seen.add(sc)
            out.append(("instagram", sc))      # 아카이브는 전부 인스타 릴스다
    except Exception:                          # noqa: BLE001 — 아카이브가 비어도 랭킹 백필은 계속
        pass
    return out


def run_backfill(db_path=DB_PATH, limit=PER_RUN_LIMIT, sleep_s=SLEEP_SEC):
    """길이 없는 랭킹 항목을 캐시 우선으로 채운다. 요약 문자열 반환(워커 로그용)."""
    store = Store(db_path)
    targets = _targets(store)
    if not targets:
        return "durfill: 대상 0건"
    cached = store.duration_map([sc for _, sc in targets])
    fails = store.duration_fail_map([sc for _, sc in targets])
    todo = [(p, sc) for p, sc in targets
            if sc not in cached and fails.get(sc, 0) < MAX_FAIL][:limit]
    ok = ng = 0
    ig = [sc for p, sc in todo if p == "instagram"]
    rest = [(p, sc) for p, sc in todo if p != "instagram"]
    if ig:
        # 인스타는 브라우저(세션 컨텍스트)를 배치당 1번만 띄워 릴마다 상세 노드를 받는다.
        from shopping_shorts.instagram_parse import shortcode_to_pk
        from shopping_shorts.instagram_playwright import _detail_context, _fetch_reel_detail
        try:
            with _detail_context() as ctx:
                for sc in ig:
                    dur = None
                    pk = shortcode_to_pk(sc)
                    if pk:
                        try:
                            dur = _manifest_duration(_fetch_reel_detail(ctx, pk, sc))
                        except Exception:      # noqa: BLE001 — 한 릴 실패로 배치가 안 죽게
                            dur = None
                    if dur is not None:
                        store.set_reel_duration(sc, dur)
                        ok += 1
                    else:
                        store.bump_duration_fail(sc)
                        ng += 1
                    time.sleep(sleep_s)
        except Exception:                      # noqa: BLE001 — 브라우저 기동 실패(미설치 등)
            pass
    for platform, sc in rest:
        dur = probe_duration(platform, sc)
        if dur is not None:
            store.set_reel_duration(sc, dur)
            ok += 1
        else:
            store.bump_duration_fail(sc)
            ng += 1
        time.sleep(sleep_s)
    return (f"durfill: 성공 {ok}·실패 {ng}·캐시적중 {len(cached)}"
            f"·잔여 {max(0, len(targets) - len(cached) - len(todo))}")
