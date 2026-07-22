"""YouTube Data API v3 어댑터 — 키워드로 인기 Shorts 발굴 + 통계.

무료(쿼터 내). config.YOUTUBE_API_KEYS를 순서대로 시도(쿼터 초과 시 다음 키).
검색(search.list)은 통계가 없어 videos.list로 조회수·좋아요·댓글을 채운다.
"""
import re
import requests
from shopping_shorts.config import YOUTUBE_API_KEYS

# YouTube URL → video_id 파서
_YT_ID = re.compile(r"(?:v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{11})")

def video_id_from_url(url):
    """유튜브 watch/youtu.be/shorts URL → 11자 video_id. 유튜브 아니면 None."""
    if not url:
        return None
    m = _YT_ID.search(url)
    return m.group(1) if m else None

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
            "thumbnail": ((sn.get("thumbnails") or {}).get("high") or {}).get("url", ""),
            "published_at": sn.get("publishedAt"),
        })
    return r.status_code, items


def search_shorts(keywords, published_after_iso, max_per_kw=20, token=None, lang="ko"):
    """키워드별로 최신·인기 영상 검색 → 통계 채운 원시 dict 리스트.

    lang: 검색 언어(ko/en/ja/zh/ru). 지역(regionCode)은 언어에 매핑(기본 한국/한국어)
    → 외국 영상 혼입 방지. 키워드는 이미 해당 언어로 번역돼 들어온다고 가정.

    쿼터 초과(403) 시 다음 키로 로테이션: 검색 요청이 403이면 그 토큰은
    이후 검색에도 다시 시도하지 않고 다음 토큰으로 전체 검색을 재시도한다.
    모든 토큰이 실패해야 포기(마지막 실패 결과로 빈 처리). 호출부가 명시적으로
    token=을 넘기면(단일 토큰) 로테이션 없이 그 토큰만 사용하는 기존 동작 유지."""
    tokens = [token] if token else list(YOUTUBE_API_KEYS)
    if not tokens:
        raise RuntimeError("YOUTUBE_API_KEY 미설정")
    region = _LANG_REGION.get(lang, "KR")

    tok = tokens[0]
    tok_idx = 0
    raw = []
    for kw in keywords:
        while True:
            status, items = _search_page(kw, published_after_iso, max_per_kw, tok, region, lang)
            if status == 403 and tok_idx + 1 < len(tokens):
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
