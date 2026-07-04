"""유튜브 Data API 기반 터진 영상 탐지 — 채널 자체 평균 대비 % 계산.
2026-07-03: agent_plan.search_hot_clips()(Google검색+Gemini 추정)는 숫자가 부정확해서
실제 API 수치로 교체."""
import html
import os
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent.parent
API_BASE = "https://www.googleapis.com/youtube/v3"


def _load_keys() -> list[str]:
    """YOUTUBE_API_KEY, YOUTUBE_API_KEY_2..10 을 순서대로 로드 (환경변수 우선, 없으면 .env).
    할당량(하루 10,000 unit/프로젝트) 초과 시 다음 키로 자동 전환하기 위한 풀."""
    names = ["YOUTUBE_API_KEY"] + [f"YOUTUBE_API_KEY_{i}" for i in range(2, 11)]
    env_file_vals = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env_file_vals[k.strip()] = v.strip()
    keys = []
    for n in names:
        v = os.environ.get(n, "") or env_file_vals.get(n, "")
        if v and v not in keys:
            keys.append(v)
    return keys


_KEYS = _load_keys()


def _api_key() -> str:
    """하위호환용 — 첫 키 반환."""
    return _KEYS[0] if _KEYS else ""


def _is_quota_error(r: "requests.Response") -> bool:
    """YouTube 할당량 초과 판정. 초과 시 403(reason=quotaExceeded) 또는 드물게 429."""
    if r.status_code == 429:
        return True
    if r.status_code == 403:
        try:
            reason = r.json().get("error", {}).get("errors", [{}])[0].get("reason", "")
            return reason in ("quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded")
        except Exception:
            return True
    return False


def _api_get(endpoint: str, params: dict) -> dict:
    """YouTube Data API GET — 현재 키가 할당량 초과면 다음 키로 자동 전환해 재시도.
    모든 키가 소진되면 마지막 응답으로 raise_for_status()."""
    if not _KEYS:
        raise RuntimeError(".env에 YOUTUBE_API_KEY 없음")
    last = None
    for key in _KEYS:
        p = dict(params, key=key)
        r = requests.get(f"{API_BASE}/{endpoint}", params=p, timeout=15)
        if _is_quota_error(r):
            last = r
            continue
        r.raise_for_status()
        return r.json()
    # 전 키 소진
    if last is not None:
        last.raise_for_status()
    raise RuntimeError("YouTube API 키 전부 소진")


def search_videos(query: str, max_results: int = 25, order: str = "relevance",
                  published_after: str = "") -> list[dict]:
    """유튜브 검색. order 기본=relevance(관련도) — viewCount만 쓰면 대형채널·오래된
    영상만 긁혀서 소형채널 알짜를 검색단계에서 놓침(2026-07-04 수정)."""
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "regionCode": "KR",
        "relevanceLanguage": "ko",
        "order": order,
        "maxResults": max_results,
    }
    if published_after:
        params["publishedAfter"] = published_after   # RFC3339, 예: 2026-04-01T00:00:00Z
    data = _api_get("search", params)
    out = []
    for item in data.get("items", []):
        sn = item["snippet"]
        # 라이브/예정 방송 제외 — 누적 조회수라 성과 지표 왜곡(매경TV·MTN 상시라이브 등)
        if sn.get("liveBroadcastContent", "none") != "none":
            continue
        out.append({
            "video_id": item["id"]["videoId"],
            "title": html.unescape(sn["title"]),
            "channel_id": sn["channelId"],
            "channel_title": html.unescape(sn["channelTitle"]),
            "published_at": sn["publishedAt"],
            "thumbnail": sn.get("thumbnails", {}).get("default", {}).get("url", ""),
        })
    return out


def _parse_duration(iso: str) -> int:
    """ISO8601 (PT#H#M#S) → 초. 파싱 실패 시 0."""
    import re as _re
    m = _re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def _is_short_video(video_id: str, dur: int) -> bool:
    """쇼츠 판별. 유튜브 쇼츠는 최대 180초라 길이만으론 1~3분 일반영상과 구분 불가.
    /shorts/{id}가 200이면 쇼츠, 303(→/watch)이면 일반. 180초 초과는 확실히 일반(호출 생략)."""
    if dur <= 0 or dur > 180:
        return False
    try:
        r = requests.head(f"https://www.youtube.com/shorts/{video_id}",
                          allow_redirects=False, timeout=4,
                          headers={"User-Agent": "Mozilla/5.0"})
        return r.status_code == 200
    except Exception:
        return dur <= 60   # 실패 시 보수적으로 60초 기준


def _chunks(lst, size=50):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def get_video_stats(video_ids: list[str], detect_shorts: bool = False) -> dict[str, dict]:
    if not video_ids:
        return {}
    out = {}
    for chunk in _chunks(video_ids, 50):   # videos.list는 호출당 id 최대 50개
        data = _api_get("videos", {"part": "statistics,contentDetails", "id": ",".join(chunk)})
        for item in data.get("items", []):
            st = item["statistics"]
            dur = _parse_duration(item.get("contentDetails", {}).get("duration", ""))
            out[item["id"]] = {
                "view_count": int(st.get("viewCount", 0)),
                "like_count": int(st.get("likeCount", 0)),
                "comment_count": int(st.get("commentCount", 0)),
                "duration_sec": dur,
                "is_short": 0 < dur <= 60,   # 우선 길이 기준. detect_shorts면 아래서 보정
            }
    # 쇼츠 정밀 판별(/shorts 리다이렉트)은 60~180초 후보만, 스레드풀로 병렬 (순차면 병목)
    if detect_shorts:
        from concurrent.futures import ThreadPoolExecutor
        cand = [vid for vid, s in out.items() if 60 < s["duration_sec"] <= 180]
        if cand:
            with ThreadPoolExecutor(max_workers=12) as ex:
                for vid, is_s in zip(cand, ex.map(lambda v: _is_short_video(v, out[v]["duration_sec"]), cand)):
                    out[vid]["is_short"] = is_s
    return out


def get_channel_stats(channel_ids: list[str]) -> dict[str, dict]:
    """구독자·영상수 + 업로드 재생목록ID(contentDetails, 같은 호출에 묶어서 추가비용 없음)."""
    if not channel_ids:
        return {}
    out = {}
    for chunk in _chunks(channel_ids, 50):   # channels.list도 호출당 id 최대 50개
        data = _api_get("channels", {"part": "statistics,contentDetails", "id": ",".join(chunk)})
        for item in data.get("items", []):
            st = item["statistics"]
            uploads_playlist_id = item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", "")
            out[item["id"]] = {
                "subscriber_count": int(st.get("subscriberCount", 0)),
                "video_count": int(st.get("videoCount", 0)),
                "uploads_playlist_id": uploads_playlist_id,
            }
    return out


def get_top_comments(video_id: str, n: int = 15) -> list[dict]:
    """영상의 베스트 댓글 n개 (관련도순=상단 고정/좋아요 많은 순).
    각 dict: {author, text, like_count, reply_count}. 댓글 비활성 영상은 빈 리스트."""
    try:
        data = _api_get("commentThreads", {
            "part": "snippet", "videoId": video_id,
            "order": "relevance", "maxResults": n, "textFormat": "plainText",
        })
    except Exception:
        return []  # 댓글 사용중지(403 commentsDisabled) 등은 조용히 빈 리스트
    out = []
    for it in data.get("items", []):
        s = it["snippet"]["topLevelComment"]["snippet"]
        out.append({
            "author": html.unescape(s.get("authorDisplayName", "")),
            "text": html.unescape(s.get("textOriginal", s.get("textDisplay", ""))),
            "like_count": int(s.get("likeCount", 0)),
            "reply_count": int(it["snippet"].get("totalReplyCount", 0)),
        })
    return out


def get_video_meta(video_id: str) -> dict:
    """영상 1개의 기본 메타 (직접 URL 해체용) — 제목·채널·게시일·조회수."""
    d = _api_get("videos", {"part": "snippet,statistics", "id": video_id})
    items = d.get("items", [])
    if not items:
        return {}
    sn = items[0]["snippet"]
    st = items[0].get("statistics", {})
    return {
        "title": html.unescape(sn.get("title", "")),
        "channel_title": html.unescape(sn.get("channelTitle", "")),
        "published_at": sn.get("publishedAt", ""),
        "view_count": int(st.get("viewCount", 0)),
    }


def _get_channel_raw_videos(uploads_playlist_id: str, n: int = 10) -> list[dict]:
    """업로드 재생목록에서 최근 n개 영상의 raw 데이터 (ID, 조회수, 좋아요).
    2026-07-04: search.list(채널당 100 unit)를 playlistItems.list(1 unit)로 교체 —
    기존 방식은 검색 1건당 ~1000 unit(유튜브 일일 할당량 10,000 unit 중 9건/일밖에 안 됨)을
    태워 429 Too Many Requests가 바로 발생했음. playlistItems.list 기반으로 채널당
    비용을 100배 이상 줄임."""
    if not uploads_playlist_id:
        return []
    params = {
        "part": "contentDetails", "playlistId": uploads_playlist_id,
        "maxResults": n,
    }
    data = _api_get("playlistItems", params)
    video_ids = [item["contentDetails"]["videoId"] for item in data.get("items", [])]

    if not video_ids:
        return []
    stats = get_video_stats(video_ids)
    return [
        {
            "video_id": vid,
            "view_count": stats[vid]["view_count"],
            "like_count": stats[vid]["like_count"],
        }
        for vid in video_ids
    ]


def _grade(pct: float) -> str:
    if pct >= 700:
        return "Great"
    if pct >= 200:
        return "Good"
    return "Normal"


import re as _re_news
# 방송사/통신사 뉴스 채널 — 분석·인사이트 창작물이 아니라 스트레이트 뉴스라 레퍼런스 가치 낮음
_NEWS_RE = _re_news.compile(
    r"(SBS|KBS|MBC|YTN|JTBC|MBN|TV조선|채널A|연합뉴스|연합뉴스TV|뉴시스|뉴스1|뉴스룸|"
    r"news|뉴스|한국경제TV|매일경제TV|이데일리TV|서울경제TV|아시아경제)", _re_news.I)


def _is_news_channel(title: str) -> bool:
    return bool(_NEWS_RE.search(title or ""))


def _published_after(days: int) -> str:
    """days일 전 RFC3339 문자열. days<=0이면 빈 문자열(전체 기간)."""
    if not days or days <= 0:
        return ""
    from datetime import datetime, timedelta, timezone
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.strftime("%Y-%m-%dT00:00:00Z")


def _days_since(iso: str) -> int:
    """게시일로부터 경과일 (최소 1). velocity(일 조회수) 계산용."""
    if not iso:
        return 1
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return max((datetime.now(timezone.utc) - dt).days, 1)
    except Exception:
        return 1


def find_hot_clips(query: str, days: int = 0, fast: bool = False) -> list[dict]:
    """검색 → 통계 조회 → (fast아니면) 채널 평균 대비 % → 등급 부여.
    관련도+조회수+최신 세 순서로 긁어 합쳐(dedup) — 소형알짜·고조회수·최근트렌드 모두 포함.
    days>0이면 그 기간 내 게시분만 (트렌드 검색이 오래된 영상만 나오는 문제 보정).
    fast=True면 채널별 평균조회수(느린 순차 재생목록 조회)를 생략 — 순위는 구독자 대비
    배수/velocity로만 매기므로 창고 검색에선 이걸로 충분하고 3~4배 빠름."""
    pa = _published_after(days)
    seen, videos = set(), []
    for od in ("relevance", "date", "viewCount"):
        for v in search_videos(query, max_results=50, order=od, published_after=pa):
            if v["video_id"] not in seen:
                seen.add(v["video_id"])
                videos.append(v)
    if not videos:
        return []
    stats = get_video_stats([v["video_id"] for v in videos], detect_shorts=True)

    unique_channel_ids = list(set(v["channel_id"] for v in videos))
    channel_stats = get_channel_stats(unique_channel_ids)   # 구독자수 (배치, 빠름)

    # 채널별 평균조회수(기여도/성과도용) — 채널마다 재생목록 조회가 필요해 느리므로 병렬.
    # fast=True면 생략(순위는 배수/velocity로 충분)
    channel_raw_videos_cache = {}
    if not fast:
        from concurrent.futures import ThreadPoolExecutor
        pls = {cid: channel_stats.get(cid, {}).get("uploads_playlist_id", "") for cid in unique_channel_ids}
        with ThreadPoolExecutor(max_workers=12) as ex:
            for cid, raw in zip(unique_channel_ids,
                                ex.map(lambda cid: _get_channel_raw_videos(pls[cid], n=10), unique_channel_ids)):
                channel_raw_videos_cache[cid] = raw

    results = []
    for v in videos:
        st = stats.get(v["video_id"], {"view_count": 0, "like_count": 0, "comment_count": 0, "duration_sec": 0, "is_short": False})
        ch_id = v["channel_id"]
        ch_stat = channel_stats.get(ch_id, {"subscriber_count": 0, "video_count": 0, "uploads_playlist_id": ""})

        view_pct = like_pct = 0.0
        contribution = performance = ""
        if not fast:
            filtered = [rv for rv in channel_raw_videos_cache.get(ch_id, []) if rv["video_id"] != v["video_id"]]
            if filtered:
                avg_view = sum(rv["view_count"] for rv in filtered) / len(filtered)
                avg_like = sum(rv["like_count"] for rv in filtered) / len(filtered)
                view_pct = round((st["view_count"] - avg_view) / avg_view * 100, 1) if avg_view else 0.0
                like_pct = round((st["like_count"] - avg_like) / avg_like * 100, 1) if avg_like else 0.0
            contribution = _grade(view_pct)     # 채널평균 대비 조회수 = 기여도
            performance = _grade(like_pct)       # 채널평균 대비 좋아요 = 성과도

        # 참여율 = (좋아요+댓글)/조회수 — 썸네일빨 vs 내용빨 판단 신호
        views = st["view_count"] or 1
        eng_pct = round((st["like_count"] + st["comment_count"]) / views * 100, 2)

        # velocity: 게시 후 하루당 조회수. 최근 영상이 조회수 누적 부족으로 밀리는 것 보정.
        d = _days_since(v.get("published_at", ""))
        views_per_day = round(st["view_count"] / d)

        results.append({
            "video_id": v["video_id"],
            "title": v["title"],
            "channel_title": v["channel_title"],
            "channel_id": v.get("channel_id", ""),
            "thumbnail": v["thumbnail"],
            "published_at": v.get("published_at", ""),
            "days_since": d,
            "view_count": st["view_count"],
            "views_per_day": views_per_day,   # 일 조회수(velocity)
            "comment_count": st.get("comment_count", 0),
            "like_count": st.get("like_count", 0),
            "view_pct_above_avg": view_pct,
            "contribution_grade": contribution,   # 채널평균 대비 조회수 등급(기여도)
            "performance_grade": performance,      # 채널평균 대비 좋아요 등급(성과도)
            "engage_pct": eng_pct,
            "content_grade": "",               # find_and_rank에서 배치 상대평가로 채움
            "duration_sec": st.get("duration_sec", 0),
            "is_short": st.get("is_short", False),
            "is_news": _is_news_channel(v["channel_title"]),
            "subscriber_count": ch_stat["subscriber_count"],
        })
    return results


# ── 검증 순위 판정 (조절 손잡이) ─────────────────────────────
# "소재가 터졌나 vs 채널빨" 을 객관 지표로 가르는 임계값. 결과 보며 튜닝.
GOLD_MAX_SUBS = 200_000       # 이 구독자 미만이면 "작은 채널"로 봄
GOLD_MIN_RATIO = 3.0          # 구독자 대비 조회수 배수가 이 이상이면 소재가 캐리
BIGCH_SUBS = 1_000_000        # 대형 채널 기준
MIN_VIEWS = 30_000            # 이 미만은 "검증된 터진 영상" 아님 — 갓 올라온 0조회 신규 제외


def classify_clip(c: dict) -> dict:
    """구독자 대비 배수 + velocity로 판정. c에 view_per_sub/heat/verdict 추가.
    (fast 모드는 contribution_grade가 비어있으므로 배수 위주로 판정)"""
    subs, views = c.get("subscriber_count", 0), c.get("view_count", 0)
    d = c.get("days_since", 1) or 1
    ratio = views / subs if subs else 0
    c["view_per_sub"] = round(ratio, 1)
    c["heat"] = round(ratio / d, 3)   # 구독자 대비 '일' velocity (최근+소형+급상승일수록 큼)
    if subs < GOLD_MAX_SUBS and ratio >= GOLD_MIN_RATIO:
        c["verdict"] = "금맥"          # 작은 채널을 터뜨림 = 소재가 캐리 = 배울 가치
    elif subs >= BIGCH_SUBS and ratio < 1:
        c["verdict"] = "채널빨"        # 대형인데 구독자 대비 저조 = 소재 검증 약함
    elif ratio >= 1:
        c["verdict"] = "기여"          # 소재가 어느 정도 기여
    else:
        c["verdict"] = "애매"
    return c


def _enrich_contribution(rows: list[dict]) -> None:
    """필터 통과한 영상들에만 채널평균 대비 기여도/성과도 계산(비싸서 살아남은 것만).
    채널별 재생목록 조회를 병렬로."""
    if not rows:
        return
    from concurrent.futures import ThreadPoolExecutor
    ch_ids = list({r["channel_id"] for r in rows if r.get("channel_id")})
    ch_stats = get_channel_stats(ch_ids)
    cache = {}
    with ThreadPoolExecutor(max_workers=12) as ex:
        pls = {c: ch_stats.get(c, {}).get("uploads_playlist_id", "") for c in ch_ids}
        for cid, raw in zip(ch_ids, ex.map(lambda c: _get_channel_raw_videos(pls[c], n=10), ch_ids)):
            cache[cid] = raw
    for r in rows:
        filtered = [rv for rv in cache.get(r.get("channel_id"), []) if rv["video_id"] != r["video_id"]]
        vp = lp = 0.0
        if filtered:
            av = sum(x["view_count"] for x in filtered) / len(filtered)
            al = sum(x["like_count"] for x in filtered) / len(filtered)
            vp = round((r["view_count"] - av) / av * 100, 1) if av else 0.0
            lp = round((r.get("like_count", 0) - al) / al * 100, 1) if al else 0.0
        r["view_pct_above_avg"] = vp
        r["contribution_grade"] = _grade(vp)     # 기여도(채널평균 대비 조회수)
        r["performance_grade"] = _grade(lp)        # 성과도(채널평균 대비 좋아요)


def find_and_rank(queries: list[str], days: int = 0, exclude_shorts: bool = False,
                  exclude_news: bool = True, sort: str = "view_per_sub") -> list[dict]:
    """카테고리의 여러 검색어 결과를 합쳐 중복 제거 → 필터 → 기여도 계산 → 정렬.
    검색·통계는 fast(채널평균 생략)로 빠르게 긁고, 하한·쇼츠·뉴스 거른 뒤 '살아남은 것만'
    채널평균 대비 기여도/성과도를 계산(비싼 단계를 결과 수만큼만) → 빠르면서 기여도도 제공."""
    pool = {}
    for q in queries:
        for r in find_hot_clips(q, days=days, fast=True):
            pool.setdefault(r["video_id"], r)
    rows = [classify_clip(r) for r in pool.values()]
    # 검증 하한: 조회수 너무 적은(갓 올라와 아직 안 터진) 영상 제외 — "터진 영상"만 남김
    rows = [r for r in rows if r.get("view_count", 0) >= MIN_VIEWS]
    if exclude_shorts:
        rows = [r for r in rows if not r.get("is_short")]
    if exclude_news:
        rows = [r for r in rows if not r.get("is_news")]
    _enrich_contribution(rows)   # 살아남은 것만 기여도/성과도 계산

    # 참여율 상대 등급 (배치 내 3분위)
    engs = sorted(r.get("engage_pct", 0) for r in rows)
    n = len(engs)
    if n >= 3:
        lo, hi = engs[n // 3], engs[n * 2 // 3]
        for r in rows:
            e = r.get("engage_pct", 0)
            r["content_grade"] = "높음" if e >= hi else ("보통" if e >= lo else "낮음")

    rows.sort(key=lambda r: r.get(sort, 0), reverse=True)
    return rows
