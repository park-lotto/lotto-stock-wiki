"""YouTube Data API v3 어댑터 — 키워드로 인기 Shorts 발굴 + 통계.

무료(쿼터 내). config.YOUTUBE_API_KEYS를 순서대로 시도(쿼터 초과 시 다음 키).
검색(search.list)은 통계가 없어 videos.list로 조회수·좋아요·댓글을 채운다.
"""
import re
import requests
from shopping_shorts import config
from shopping_shorts.config import YOUTUBE_API_KEYS

# YouTube URL → video_id 파서
_YT_ID = re.compile(r"(?:v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{11})")

_DURATION = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def _parse_duration_secs(iso):
    """ISO8601 재생시간(PT#H#M#S) → 초. 빈값/None → None."""
    if not iso:
        return None
    m = _DURATION.fullmatch(iso)
    if not m:
        return None
    h, mnt, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mnt * 60 + s

def video_id_from_url(url):
    """유튜브 watch/youtu.be/shorts URL → 11자 video_id. 유튜브 아니면 None."""
    if not url:
        return None
    m = _YT_ID.search(url)
    return m.group(1) if m else None

def _short_thumb(video_id):
    """쇼츠(≤60초)의 세로(9:16) 썸네일 URL. API 기본(high=hqdefault)은 480x360 가로라
    세로 카드(인스타·틱톡과 동일 틀)에 안 맞는다. oardefault=원본비율(쇼츠는 720x1280 세로)."""
    return f"https://i.ytimg.com/vi/{video_id}/oardefault.jpg" if video_id else ""


_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
_COMMENTS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"

# 제목 문자(스크립트) 기반 언어 필터 — regionCode/relevanceLanguage는 약한 힌트라
# 조회수순 검색에 외국 영상이 섞인다(실측 2026-07-13). 제목에 해당 언어 문자가
# 있어야 통과시켜 "일어 선택=일본어 영상만" 되게 한다.
_HANGUL = re.compile(r"[가-힣]")
_KANA = re.compile(r"[ぁ-んァ-ヶ]")          # 히라가나·가타카나
_CJK = re.compile(r"[一-鿿]")                # 한자(중/일 공통)
_CYRILLIC = re.compile(r"[а-яА-ЯёЁ]")


def _title_lang_ok(title, lang):
    """제목이 선택 언어의 문자를 담고 있는지 — 외국영상 걸러내기."""
    t = title or ""
    if lang == "ko":
        return bool(_HANGUL.search(t))
    if lang == "ja":
        return bool(_KANA.search(t)) or bool(_CJK.search(t))   # 가나 or 한자
    if lang == "zh":
        return bool(_CJK.search(t)) and not _KANA.search(t)    # 한자 있고 가나 없음
    if lang == "ru":
        return bool(_CYRILLIC.search(t))
    if lang == "en":                                           # 라틴 전용(비라틴 문자 없음)
        return not (_HANGUL.search(t) or _KANA.search(t) or _CJK.search(t) or _CYRILLIC.search(t))
    return True


def _stats(video_ids, token):
    """videos.list(statistics) → {video_id: {views,likes,comments}}."""
    out = {}
    for i in range(0, len(video_ids), 50):          # API 상한 50개/호출
        chunk = video_ids[i:i + 50]
        r = requests.get(_VIDEOS_URL, params={
            "part": "statistics", "id": ",".join(chunk), "key": token}, timeout=30)
        if r.status_code != 200:
            continue
        for it in r.json().get("items", []):
            s = it.get("statistics", {})
            out[it["id"]] = {
                "views": int(s.get("viewCount") or 0),
                "likes": int(s.get("likeCount") or 0),
                "comments": int(s.get("commentCount") or 0),
            }
    return out


def video_details(video_ids, tokens):
    """videos.list(statistics,contentDetails,snippet) → {id: {views,likes,comments,published,dur}}.

    관제 156(2026-10-08 사장님): 유튜브 Shorts 검색 화면에 인스타처럼 📅날짜·⏱길이·조회·댓글 배지와
    조회수순·댓글순 정렬. 검색 화면엔 조회수만 있다(실측) → 50개씩 1호출(쿼터 1). 키는 실패 시 다음 키."""
    out = {}
    ids = [v for v in dict.fromkeys(video_ids or []) if v and len(v) == 11][:200]
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        for tok in (tokens or []):
            try:
                r = requests.get(_VIDEOS_URL, params={
                    "part": "statistics,contentDetails,snippet", "id": ",".join(chunk),
                    "fields": "items(id,statistics(viewCount,likeCount,commentCount),"
                              "contentDetails(duration),snippet(publishedAt))",
                    "key": tok}, timeout=20)
            except requests.RequestException:
                continue
            if r.status_code != 200:
                continue                      # 쿼터·키 문제 → 다음 키
            for it in r.json().get("items", []):
                s = it.get("statistics", {})
                out[it["id"]] = {
                    "views": int(s.get("viewCount") or 0),
                    "likes": int(s["likeCount"]) if s.get("likeCount") is not None else None,
                    "comments": int(s["commentCount"]) if s.get("commentCount") is not None else None,
                    "published": (it.get("snippet") or {}).get("publishedAt", "")[:10],
                    "dur": _parse_duration_secs((it.get("contentDetails") or {}).get("duration")),
                }
            break
    return out


# 언어코드 → YouTube regionCode(검색 지역 편향). 없는 언어는 기본 KR.
_LANG_REGION = {"ko": "KR", "en": "US", "ja": "JP", "zh": "TW", "ru": "RU"}


def _search_page(kw, published_after_iso, max_per_kw, tok, region="KR", lang="ko"):
    """키워드 하나를 토큰 하나로 검색. 반환: (status_code, items_or_None).
    region/lang로 지역·언어를 편향(기본 한국/한국어) — 외국 영상 혼입 방지."""
    r = requests.get(_SEARCH_URL, params={
        "part": "snippet", "q": kw, "type": "video", "videoDuration": "short",
        "order": "viewCount", "publishedAfter": published_after_iso,
        "regionCode": region, "relevanceLanguage": lang,
        "maxResults": min(max_per_kw, 50), "key": tok}, timeout=30)
    if r.status_code != 200:
        return r.status_code, None
    items = []
    for it in r.json().get("items", []):
        vid = (it.get("id") or {}).get("videoId")
        sn = it.get("snippet") or {}
        if not vid:
            continue
        items.append({
            "video_id": vid, "channel_id": sn.get("channelId"),
            "channel_title": sn.get("channelTitle"),
            "title": sn.get("title"), "description": sn.get("description"),
            "thumbnail": _short_thumb(vid),
            "published_at": sn.get("publishedAt"),
        })
    return r.status_code, items


def _tokens_for(customer_id=0):
    """유튜브 키 — 사용자가 등록했으면 그것만(폴백 없음). 없으면 사장님 풀 그대로.

    ★keyroute가 유일한 판단처다 — 여기서 따로 고르지 마라(0순위-B).
    cid 0(크론·발굴)이면 config.YOUTUBE_API_KEYS가 그대로 나와 기존 로테이션이
    안 바뀐다."""
    from shopping_shorts import keyroute
    from shopping_shorts.store import Store
    keys, _ = keyroute.keys_for(Store(config.DB_PATH), customer_id,
                                keyroute.SVC_YOUTUBE)
    return keys


def search_shorts(keywords, published_after_iso, max_per_kw=20, token=None, lang="ko",
                  customer_id=0):
    """키워드별로 최신·인기 영상 검색 → 통계 채운 원시 dict 리스트.

    lang: 검색 언어(ko/en/ja/zh/ru). 지역(regionCode)은 언어에 매핑(기본 한국/한국어)
    → 외국 영상 혼입 방지. 키워드는 이미 해당 언어로 번역돼 들어온다고 가정.

    쿼터 초과(403) 시 다음 키로 로테이션: 검색 요청이 403이면 그 토큰은
    이후 검색에도 다시 시도하지 않고 다음 토큰으로 전체 검색을 재시도한다.
    모든 토큰이 실패해야 포기(마지막 실패 결과로 빈 처리). 호출부가 명시적으로
    token=을 넘기면(단일 토큰) 로테이션 없이 그 토큰만 사용하는 기존 동작 유지.

    customer_id: 누구 키로 검색하나. 0(기본)=사장님 풀 — 기존 호출부는 안 바뀐다."""
    tokens = [token] if token else _tokens_for(customer_id)
    if not tokens:
        raise RuntimeError("YOUTUBE_API_KEY 미설정")
    region = _LANG_REGION.get(lang, "KR")

    tok = tokens[0]
    tok_idx = 0
    raw = []
    for kw in keywords:
        while True:
            status, items = _search_page(kw, published_after_iso, max_per_kw, tok, region, lang)
            # ★429도 로테이션 대상이다(2026-08-17 실사고). 403(쿼터/권한)만 넘기던 탓에
            # 키 1개가 429(rateLimitExceeded)면 **모든 검색이 조용히 0건**을 반환했다.
            # 실측: 키 10개 중 6개가 멀쩡한데 1번 키 하나로 검색 경로가 통째로 죽었다
            # (기본 로테이션 0건 / 키2 지정 50건). 예외도 안 나는 조용한 실패라 더 위험하다.
            if status in (403, 429) and tok_idx + 1 < len(tokens):
                tok_idx += 1
                tok = tokens[tok_idx]
                continue  # 다음 키로 이 키워드부터 재시도
            break
        if items:
            # 제목 언어 필터로 외국영상 제거(선택 언어 문자가 제목에 있어야 통과)
            raw.extend([it for it in items if _title_lang_ok(it.get("title"), lang)])
    stats = _stats([r["video_id"] for r in raw], tok)
    for r in raw:
        r.update(stats.get(r["video_id"], {"views": 0, "likes": 0, "comments": 0}))
    return raw


def _first_ok(url, params):
    """YOUTUBE_API_KEYS를 순서대로 시도. 쿼터/403이면 다음 키. 전부 실패면 None.

    반환: (json_or_None, saw_403). saw_403은 실패한 시도 중 403(쿼터/권한)을
    실제로 봤는지 — 네트워크오류·5xx·JSON깨짐 등 다른 실패와 구분해
    호출부가 "쿼터소진"을 오표기하지 않게 한다."""
    saw_403 = False
    for tok in YOUTUBE_API_KEYS:
        try:
            r = requests.get(url, params={**params, "key": tok}, timeout=30)
            if r.status_code == 403:
                saw_403 = True
                continue
            r.raise_for_status()
            return r.json(), saw_403
        except Exception:
            continue
    return None, saw_403


# seed 문자열에서 채널 식별자 추출
_CH_ID = re.compile(r"/channel/(UC[A-Za-z0-9_-]{6,})")
_HANDLE = re.compile(r"@([A-Za-z0-9._-]+)")
_LEGACY_USER = re.compile(r"/user/([A-Za-z0-9._-]+)")


def _channel_from_api(param_key, param_val):
    """channels.list(forHandle|forUsername|id) → (channel_id, uploads) 또는 (None,None)."""
    data, _ = _first_ok(_CHANNELS_URL,
                        {"part": "contentDetails", param_key: param_val})
    items = (data or {}).get("items") or []
    if not items:
        return None, None
    cid = items[0].get("id")
    uploads = (((items[0].get("contentDetails") or {})
                .get("relatedPlaylists") or {}).get("uploads"))
    return cid, uploads


def _resolve_channel(seed):
    """seed(핸들/URL) → (channel_id, uploads_playlist). 실패 시 (None, None).

    /channel/UC.. URL은 API 없이 직접 파싱(uploads = UU + id[2:])."""
    if not seed:
        return None, None
    m = _CH_ID.search(seed)
    if m:
        cid = m.group(1)
        return cid, "UU" + cid[2:]          # 업로드 플레이리스트 규칙(UC→UU)
    m = _HANDLE.search(seed)
    if m:
        return _channel_from_api("forHandle", "@" + m.group(1))
    m = _LEGACY_USER.search(seed)
    if m:
        return _channel_from_api("forUsername", m.group(1))
    # 순수 핸들("salim" 등 @없음)도 forHandle로 시도
    return _channel_from_api("forHandle", "@" + seed.strip().lstrip("@"))


_PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"


def fetch_channel_shorts(seed, max_videos=50, cache_get=None, cache_put=None):
    """채널 시드(핸들/URL)의 최근 Shorts(≤60초) → search_shorts와 동일한 raw dict 리스트.

    cache_get(seed)->(cid,uploads)|None / cache_put(seed,cid,uploads): 해석 캐시 콜백(선택).
    창(14일) 필터는 하지 않는다 — build_youtube_items가 window_hours로 거른다.
    비공개·삭제·해석실패 채널은 빈 리스트(예외 안 던짐)."""
    resolved = cache_get(seed) if cache_get else None
    if resolved:
        cid, uploads = resolved
    else:
        cid, uploads = _resolve_channel(seed)
        if uploads and cache_put:
            cache_put(seed, cid, uploads)
    if not uploads:
        return []

    pl, _ = _first_ok(_PLAYLIST_ITEMS_URL, {
        "part": "contentDetails", "playlistId": uploads,
        "maxResults": min(max_videos, 50)})
    vids = [((it.get("contentDetails") or {}).get("videoId"))
            for it in ((pl or {}).get("items") or [])]
    vids = [v for v in vids if v]
    if not vids:
        return []

    out = []
    for i in range(0, len(vids), 50):                       # videos.list 상한 50
        chunk = vids[i:i + 50]
        vd, _ = _first_ok(_VIDEOS_URL, {
            "part": "snippet,contentDetails,statistics", "id": ",".join(chunk)})
        for it in ((vd or {}).get("items") or []):
            secs = _parse_duration_secs((it.get("contentDetails") or {}).get("duration"))
            if secs is None or secs > 60:                   # 숏폼(≤60초)만
                continue
            sn = it.get("snippet") or {}
            st = it.get("statistics") or {}
            out.append({
                "video_id": it.get("id"),
                "channel_id": sn.get("channelId"),
                "channel_title": sn.get("channelTitle"),
                "title": sn.get("title"),
                "description": sn.get("description"),
                "thumbnail": _short_thumb(it.get("id")),
                "published_at": sn.get("publishedAt"),
                "views": int(st.get("viewCount") or 0),
                "likes": int(st.get("likeCount") or 0),
                "comments": int(st.get("commentCount") or 0),
            })
    return out


# 영상 URL → video_id (watch?v= / youtu.be/ / shorts/ / embed/)
_VIDEO_ID_RE = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/))([A-Za-z0-9_-]+)")


def _video_id_from_url(url):
    """유튜브 영상 URL에서 video_id 추출. 비유튜브/파싱실패 → None."""
    if not url:
        return None
    m = _VIDEO_ID_RE.search(url)
    return m.group(1) if m else None


def channels_from_video_urls(urls):
    """유튜브 영상 URL 리스트 → 소속 채널 [{channel_id, channel_title, channel_url}].

    같은 채널은 1개로(첫 등장 순서 보존). videos.list(part=snippet, id=배치50)로
    channelId·channelTitle을 해석한다(0 units는 아니고 videos.list 1회/배치).
    비유튜브 URL·해석실패는 조용히 건너뛴다. 유튜브 영상이 하나도 없으면 API 호출 없이 []."""
    vids, seen_vid = [], set()
    for u in urls or []:
        vid = _video_id_from_url(u)
        if vid and vid not in seen_vid:
            seen_vid.add(vid)
            vids.append(vid)
    if not vids:
        return []
    out, seen_ch = [], set()
    for i in range(0, len(vids), 50):                      # videos.list 상한 50
        chunk = vids[i:i + 50]
        vd, _ = _first_ok(_VIDEOS_URL, {"part": "snippet", "id": ",".join(chunk)})
        for it in ((vd or {}).get("items") or []):
            sn = it.get("snippet") or {}
            cid = sn.get("channelId")
            if not cid or cid in seen_ch:
                continue
            seen_ch.add(cid)
            out.append({
                "channel_id": cid,
                "channel_title": sn.get("channelTitle") or "",
                "channel_url": f"https://www.youtube.com/channel/{cid}",
            })
    return out


def uploader_of_video(url):
    """유튜브 영상 URL → (채널 핸들 또는 UC아이디, 채널명). 못 찾으면 ("", "").

    ★서버에서 yt-dlp는 유튜브에 막힌다(2026-09-28 실측: 데이터센터 IP라 "로봇 아님을
    확인하려면 로그인" 거절, 폰 공유 첫 시도가 이걸로 실패). 공식 API는 안 막힌다.
    videos.list(1) + channels.list(1) = 2 units. 핸들은 yt-dlp가 주던 것과 같은 모양
    (@ 뗀 customUrl)이라 이미 담긴 채널과 중복되지 않는다."""
    vid = video_id_from_url(url)
    if not vid:
        return "", ""
    vd, _ = _first_ok(_VIDEOS_URL, {"part": "snippet", "id": vid})
    items = (vd or {}).get("items") or []
    if not items:
        return "", ""
    sn = items[0].get("snippet") or {}
    cid, title = sn.get("channelId") or "", sn.get("channelTitle") or ""
    if not cid:
        return "", ""
    cd, _ = _first_ok(_CHANNELS_URL, {"part": "snippet", "id": cid})
    citems = (cd or {}).get("items") or []
    handle = ((citems[0].get("snippet") or {}).get("customUrl") or "") if citems else ""
    return (handle.lstrip("@") or cid), title


def enrich_youtube(url):
    """유튜브 URL → 채널·지표·인기댓글·캡션 통합 dict. 유튜브 아니면 None,
    쿼터소진(전 키 403) 시 {"status": "quota"}.

    channel/comments 조회 실패 시 비디오 필드만 채우고 나머지는 빈값으로
    degrade(best-effort) — 레퍼런스 표시용이라 의도된 동작."""
    vid = video_id_from_url(url)
    if not vid:
        return None
    vd, saw_403 = _first_ok(_VIDEOS_URL, {"part": "snippet,statistics", "id": vid})
    if vd is None:
        return {"status": "quota"} if saw_403 else None
    if not vd.get("items"):
        return None
    it = vd["items"][0]; sn = it.get("snippet", {}); stt = it.get("statistics", {})
    channel_id = sn.get("channelId", "")
    cd, _ = _first_ok(_CHANNELS_URL, {"part": "snippet,statistics", "id": channel_id}) if channel_id else (None, False)
    csn = (cd["items"][0]["snippet"] if cd and cd.get("items") else {})
    cst = (cd["items"][0]["statistics"] if cd and cd.get("items") else {})
    custom = csn.get("customUrl", "")
    channel_url = ("https://www.youtube.com/" + custom) if custom else (
        "https://www.youtube.com/channel/" + channel_id if channel_id else "")
    cm, _ = _first_ok(_COMMENTS_URL, {"part": "snippet", "videoId": vid,
                                      "order": "relevance", "maxResults": 5})
    top = []
    for t in (cm.get("items", []) if cm else []):
        c = ((t.get("snippet") or {}).get("topLevelComment") or {}).get("snippet")
        if not c:
            continue  # 삭제/모더레이션된 댓글 등 파싱 불가 항목은 스킵
        top.append({"author": c.get("authorDisplayName", ""),
                    "text": c.get("textDisplay", ""), "likes": int(c.get("likeCount") or 0)})
    return {
        "platform": "youtube",
        "channel_name": csn.get("title", ""),
        "channel_url": channel_url,
        "subscribers": int(cst.get("subscriberCount") or 0),
        "views": int(stt.get("viewCount") or 0),
        "likes": int(stt.get("likeCount") or 0),
        "comment_count": int(stt.get("commentCount") or 0),
        "upload_date": sn.get("publishedAt", ""),
        "caption": sn.get("description", ""),
        "top_comments": top,
    }


def fetch_subscribers(channel_ids, tokens=None):
    """channel_id 목록 → {channel_id: 구독자수}. 실패한 채널은 **키를 안 만든다**.

    2026-08-24 사장님 "구독자대비로 해줘" — 랭킹의 🙌 탭이 유튜브에서 항상 0이었다.
    수집이 videos.list만 불러 subscriberCount를 아예 안 가져왔기 때문이다.

    비용: channels.list(part=statistics) = **채널 50개당 1 unit**. 영상이 아니라
    채널 단위로 중복제거하므로 실측 기준 한 자릿수 unit이다(search.list 100u에 비하면
    무시할 수준).

    ★실패를 0으로 채우지 않는다 — 없는 키는 호출부에서 None이 되고, 0으로 채우면
      "구독자 대비 0%"라는 거짓 정보가 된다(ranking.build_youtube_items docstring 참조).
    ★키 로테이션은 이 모듈의 다른 호출과 같은 방식으로 한다(403이면 다음 키).
      비전 API 9곳이 로테이션을 안 써서 23키 중 1번만 때리던 전례가 있다.
    """
    ids = [c for c in dict.fromkeys(channel_ids) if c]      # 중복제거·빈값 제거(순서 유지)
    if not ids:
        return {}
    toks = list(tokens if tokens is not None else YOUTUBE_API_KEYS)
    if not toks:
        return {}
    out, ti = {}, 0
    for i in range(0, len(ids), 50):                        # API 상한 50개/호출
        chunk = ids[i:i + 50]
        while ti < len(toks):
            try:
                r = requests.get(_CHANNELS_URL, params={
                    "part": "statistics", "id": ",".join(chunk),
                    "key": toks[ti]}, timeout=30)
            except requests.exceptions.RequestException:
                break                                        # 네트워크 실패는 이 청크만 포기
            if r.status_code == 403:                         # 쿼터 소진 — 다음 키로 같은 청크 재시도
                ti += 1
                continue
            if r.status_code != 200:
                break
            for it in r.json().get("items", []):
                n = int((it.get("statistics") or {}).get("subscriberCount") or 0)
                if n > 0:                                    # 0/비공개는 키를 안 만든다
                    out[it["id"]] = n
            break
    return out


# ── 영상 성과 분석(관제 242, 2026-10-20 사장님) ─────────────────────────────
# 기준은 조사로 정했다(제미나이 검색 2026-10-20 — 1of10·OutlierKit·vidIQ 도움말, creator-hero):
#   · 터진 정도 = 이 영상 조회수 ÷ 같은 채널 최근 쇼츠 조회수 **중앙값**(1of10 방식, 평균은 대박 1편에 끌려간다).
#   · 배수 구간(OutlierKit): 2배 미만 보통 / 2~3배 평소보다 잘됨 / 3~5배 의미 있게 터짐 / 5배 이상 대박.
#   · 좋아요율·댓글율은 **같은 채널 중앙값과만** 비교한다. 조사에서 나온 일반 평균(좋아요율 약 4%,
#     creator-hero)은 롱폼 포함 수치라 쇼츠에 대면 늘 낮게 보였다(실측 해외쇼쇼 채널 중앙값 1.0%).
#   · 총 조회 배수는 갓 올린 영상에 불리하다(실측: 11일 된 영상 총 0.7배 / 하루 평균 2.3배) →
#     하루 평균 배수를 같이 주고, 14일 미만이면 young=True(화면에 '아직 쌓이는 중').
#   스와이프 이탈률·시청 지속률은 채널 주인만 보는 값이라 넣지 않는다(공개 API에 없음).
OUTLIER_TIERS = [(5, "대박", "채널 평소의 5배 이상 — 터진 영상"),
                 (3, "터짐", "채널 평소의 3~5배 — 의미 있게 잘됨"),
                 (2, "잘됨", "채널 평소의 2~3배 — 평소보다 잘됨"),
                 (1, "보통", "채널 평소 수준"),
                 (0, "낮음", "채널 평소보다 낮음")]
YOUNG_DAYS = 14
_SHORTS_MAX_SECS = 180          # 유튜브 쇼츠 최대 길이(2024-10부터 3분)


def _median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def _days_since(date_iso, today):
    import datetime as _dt
    try:
        d = _dt.date.fromisoformat(date_iso[:10])
    except (TypeError, ValueError):
        return None
    return max(1, (today - d).days)


def _view_trend(video_id, published, views):
    """조회수 추세 점들 — 공개 API엔 조회수 이력이 없다(실측: videos.list 는 지금 값만).
    그래서 분석을 열 때마다 (시각, 조회수)를 data/yt_view_snap.db 에 적어 둔다(같은 영상 30분에 1번).
    첫 점 = 올린 날 0회(사실값). 반환: [{"t": "YYYY-MM-DD HH:MM", "views": n}, …] 오래된 순."""
    import sqlite3
    import time as _t
    from pathlib import Path
    pts = [{"t": published + " 00:00", "views": 0}] if published else []
    try:
        db = Path(__file__).parent / "data" / "yt_view_snap.db"
        db.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(db), timeout=5)
        try:
            con.execute("CREATE TABLE IF NOT EXISTS snap(vid TEXT, ts INTEGER, views INTEGER)")
            con.execute("CREATE INDEX IF NOT EXISTS snap_vid ON snap(vid, ts)")
            now = int(_t.time())
            last = con.execute("SELECT MAX(ts) FROM snap WHERE vid=?", (video_id,)).fetchone()[0]
            if not last or now - last >= 1800:
                con.execute("INSERT INTO snap VALUES(?,?,?)", (video_id, now, int(views)))
                con.commit()
            rows = con.execute("SELECT ts, views FROM snap WHERE vid=? ORDER BY ts", (video_id,)).fetchall()
        finally:
            con.close()
        for ts, v in rows:
            pts.append({"t": _t.strftime("%Y-%m-%d %H:%M", _t.localtime(ts)), "views": v})
    except Exception as e:                  # noqa: BLE001 — 기록 실패해도 분석은 나간다(점 2개로)
        import sys as _s
        print(f"[yt/trend] 기록 실패: {e!r}", file=_s.stderr)
        pts.append({"t": _dt_now_str(), "views": int(views)})
    return pts


def _dt_now_str():
    import time as _t
    return _t.strftime("%Y-%m-%d %H:%M")


def video_analytics(video_id, today=None):
    """영상 하나 → 성과 분석(조회·비율·채널 최근 쇼츠 대비 배수·그래프용 목록).

    판단의 주인은 여기 한 곳 — 확장(grab_logic.js)은 받은 값을 그리기만 한다.
    쿼터: channels 1 + playlistItems 1 + videos 2 = 4. 실패면 {"ok": False, "error": …}."""
    import datetime as _dt
    today = today or _dt.date.today()
    if not (isinstance(video_id, str) and re.fullmatch(r"[\w-]{11}", video_id)):
        return {"ok": False, "error": "영상 주소를 못 읽었어요"}
    vd, _ = _first_ok(_VIDEOS_URL, {"part": "snippet,statistics,contentDetails", "id": video_id})
    items = (vd or {}).get("items") or []
    if not items:
        return {"ok": False, "error": "유튜브에서 영상 정보를 못 받았어요"}
    it = items[0]
    sn, st = it.get("snippet") or {}, it.get("statistics") or {}

    def _num(d, k):
        return int(d[k]) if d.get(k) is not None else None
    me = {"id": video_id, "title": sn.get("title", ""), "published": (sn.get("publishedAt") or "")[:10],
          "views": _num(st, "viewCount") or 0, "likes": _num(st, "likeCount"),
          "comments": _num(st, "commentCount"),
          "dur": _parse_duration_secs((it.get("contentDetails") or {}).get("duration"))}

    ch_id = sn.get("channelId", "")
    ch, _ = _first_ok(_CHANNELS_URL, {"part": "snippet,statistics,contentDetails", "id": ch_id})
    chi = ((ch or {}).get("items") or [{}])[0]
    cst = chi.get("statistics") or {}
    channel = {"id": ch_id, "title": (chi.get("snippet") or {}).get("title", sn.get("channelTitle", "")),
               "subs": None if cst.get("hiddenSubscriberCount") else _num(cst, "subscriberCount"),
               "videos": _num(cst, "videoCount")}
    uploads = ((chi.get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads")

    recent = []
    if uploads:
        pl, _ = _first_ok(_PLAYLIST_ITEMS_URL, {"part": "contentDetails", "playlistId": uploads, "maxResults": 50})
        vids = [((x.get("contentDetails") or {}).get("videoId")) for x in ((pl or {}).get("items") or [])]
        vids = [v for v in vids if v and v != video_id][:50]
        if vids:
            rv, _ = _first_ok(_VIDEOS_URL, {"part": "snippet,statistics,contentDetails", "id": ",".join(vids)})
            for x in ((rv or {}).get("items") or []):
                secs = _parse_duration_secs((x.get("contentDetails") or {}).get("duration"))
                if not secs or secs > _SHORTS_MAX_SECS:
                    continue                        # 롱폼은 쇼츠와 조회 구조가 달라 비교에서 뺀다
                xs = x.get("statistics") or {}
                recent.append({"id": x["id"], "title": (x.get("snippet") or {}).get("title", ""),
                               "published": ((x.get("snippet") or {}).get("publishedAt") or "")[:10],
                               "views": _num(xs, "viewCount") or 0, "likes": _num(xs, "likeCount"),
                               "comments": _num(xs, "commentCount")})

    def _rate(n, v):
        return round(n * 100.0 / v, 2) if (n is not None and v) else None

    def _per_day(r):
        d = _days_since(r["published"], today)
        return round(r["views"] / d) if d else None
    for r in [me] + recent:
        r["like_rate"] = _rate(r["likes"], r["views"])
        r["comment_rate"] = _rate(r["comments"], r["views"])
        r["per_day"] = _per_day(r)
    me["days"] = _days_since(me["published"], today)

    med = {"views": _median([r["views"] for r in recent]),
           "like_rate": _median([r["like_rate"] for r in recent]),
           "comment_rate": _median([r["comment_rate"] for r in recent]),
           "per_day": _median([r["per_day"] for r in recent])}
    mult = round(me["views"] / med["views"], 1) if med["views"] else None
    tier = None
    if mult is not None:
        for th, name, desc in OUTLIER_TIERS:
            if mult >= th:
                tier = {"name": name, "desc": desc}
                break
    mult_day = round(me["per_day"] / med["per_day"], 1) if (med["per_day"] and me["per_day"]) else None
    rank = 1 + sum(1 for r in recent if r["views"] > me["views"]) if recent else None

    # 그래프: 올린 날짜 순(오래된 → 최신), 이 영상도 제자리에 끼운다
    series = sorted(recent + [dict(me, me=True)], key=lambda r: r["published"])
    series = [{"id": r["id"], "title": r["title"][:60], "published": r["published"], "views": r["views"],
               "me": bool(r.get("me"))} for r in series]
    return {"ok": True, "video": me, "channel": channel, "median": med, "multiplier": mult, "multiplier_day": mult_day, "tier": tier,
            "young": bool(me["days"] and me["days"] < YOUNG_DAYS),
            "rank": rank, "compared": len(recent), "views_per_sub": _rate(me["views"], channel["subs"]),
            "series": series, "trend": _view_trend(video_id, me["published"], me["views"]),
            "source": "배수 기준: 1of10(중앙값 비교)·OutlierKit(2·3·5배 구간)"}
