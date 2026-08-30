# -*- coding: utf-8 -*-
"""네이버 클립 키워드 검색(2026-08-30) — 무료·로그인/프록시 없음.

왜 이 모듈이 따로 있나
  ★`yt-dlp`는 이 경로를 **못 쓴다**(실측: `Unsupported URL`). yt-dlp가 아는
    `tv.naver.com/v/{clipNo}`는 **옛 서비스**고, 지금의 네이버 클립은
    `clip.naver.com` + 32자 `mediaId` 기반의 **별개 서비스**다.
    옛 경로로 착각해 yt-dlp에 넘기면 통째로 0건이 된다.

경로는 HTTP 2번이 전부다(브라우저를 안 띄운다 — 핀터레스트와 다른 점).
  ① 목록  s.search.naver.com/p/clip/4/api/tab/more   ← 서명·쿠키 없이 200
  ② 상세  creatorhub-api.naver.com/.../clipviewer/card ← 인증 없이 200
          여기에 **정확한 조회수·좋아요**와 **mp4 직링크**가 같이 들어 있다.

★정렬은 우리가 한다. ①의 `sort` 파라미터는 **넣어도 무시된다**(실측:
  rel/date/view/popular 전부 같은 순서 = RELATED 고정). 대신 카드마다 조회수가
  실려 오므로 받아서 조회수 내림차순으로 세운다. 서버 정렬을 믿고 상위만
  자르면 인기순이 아니라 관련도순이 된다.

⚠️mp4 URL에는 **만료가 붙는다**(`hdnts=exp=...`). 목록만 저장해 두고 나중에
  받으면 실패한다 — 받을 때 ②를 다시 부른다. 그래서 `play_url`은 검색 시점의
  값이고, 오래 보관하면 안 된다(카드 재조회가 정답).
"""
import html as H
import json
import re
import urllib.parse
import urllib.request

# 모바일 UA로 고정한다 — 클립 탭은 모바일 검색의 탭이고, PC UA로는 같은
# 프래그먼트가 안 온다(실측). 여기서 UA를 바꾸면 파서가 통째로 헛돈다.
_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
       "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1")

_LIST_API = "https://s.search.naver.com/p/clip/4/api/tab/more"
_CARD_API = "https://creatorhub-api.naver.com/api/v7.0/clipviewer/card"

_PAGE_SIZE = 24            # 실측: 한 번에 24건이 온다. start=1,25,49...
_TIMEOUT = 30


def _get(url, referer):
    req = urllib.request.Request(url, headers={
        "User-Agent": _UA, "Referer": referer, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return json.loads(r.read().decode())


def _num(s):
    """'14.8만' → 148000. 목록의 조회수는 반올림 표기라 정렬용으로만 쓴다."""
    s = (s or "").replace(",", "").strip()
    m = re.match(r"([\d.]+)\s*([만천억]?)", s)
    if not m:
        return 0
    return int(float(m.group(1)) * {"": 1, "천": 1e3, "만": 1e4, "억": 1e8}[m.group(2)])


def _fetch_list(keyword, start):
    q = urllib.parse.urlencode({
        "ngn_country": "KR", "nscs": 0, "nso": "", "query": keyword,
        "sort": "rel", "ssc": "tab.m_clip.all", "start": start})
    return _get(f"{_LIST_API}?{q}", "https://m.search.naver.com/")


def _parse_list(payload):
    """검색 프래그먼트(HTML) → [{mediaId,title,creator,views,thumbnail}]

    ★썸네일 img를 **앵커로 삼는다**. `data-media-id` 속성을 순서대로 세어
      본문과 짝지으면 어긋난다 — 실측(뷰티 1페이지): 속성 id는 24개인데
      썸네일이 있는 진짜 클립은 22개고, 나머지 2개는 `vod`가 없는 껍데기라
      상세 조회가 통째로 빈다(4·5번 카드가 그래서 mp4 없이 나왔다).
      썸네일 URL에는 mediaId가 박혀 있어 짝이 어긋날 수 없다.

    ★강조 태그를 **먼저** 지운다. 검색어가 <mark>로 감싸여 오는데, 태그를
      구분자로 바꾸는 순간 제목이 그 자리에서 잘린다(실측: '나루토로 변신해
      보겠다네요 #메이크업 ... #뷰티 #챌린지'가 '#챌린지'만 남았다)."""
    raw = "".join(c.get("html", "") for c in (payload.get("collection") or []))
    raw = re.sub(r"</?(?:mark|b|strong|em)[^>]*>", "", H.unescape(raw))

    anchors = list(re.finditer(r'clip-home/([0-9A-F]{32,40})/trailer', raw))
    out, seen = [], set()
    for i, m in enumerate(anchors):
        media_id = m.group(1)
        if media_id in seen:
            continue
        end = anchors[i + 1].start() if i + 1 < len(anchors) else len(raw)
        seg = raw[m.start():end]
        text = re.sub(r"\|+", "|", re.sub(r"<[^>]+>", "|", seg))
        # 카드 = 제목 | 크리에이터 | N일 전 | 조회 N
        f = re.search(
            r"\|([^|]{2,150})\|([^|]{1,40})\|([^|]{1,12}? 전)\|조회 ([\d.,만천억]+)", text)
        if not f:
            continue
        seen.add(media_id)
        out.append({
            "mediaId": media_id,
            "title": f.group(1).strip(),
            "creator": f.group(2).strip(),
            "ago": f.group(3).strip(),
            "views": _num(f.group(4)),
        })
    return out


def _mpd_best_mp4(playback):
    """DASH 매니페스트 → (최고화질 mp4 URL, 길이초).

    실측(1080×1920 세로 클립): Representation 4종(1080/720/480/360)이 있고
    각각 BaseURL에 **mp4 직링크**가 들어 있다. HLS(.m3u8)도 같이 오지만
    조각을 이어붙일 필요가 없으므로 mp4를 쓴다."""
    best = (0, "")
    reps = []

    def walk(o):
        if isinstance(o, dict):
            if "BaseURL" in o:
                reps.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(playback)
    for r in reps:
        b = r.get("BaseURL")
        url = b[0] if isinstance(b, list) and b else (b if isinstance(b, str) else "")
        if not isinstance(url, str) or ".mp4" not in url:
            continue
        try:
            bw = int(r.get("@bandwidth") or 0)
        except (TypeError, ValueError):
            bw = 0
        if bw >= best[0]:
            best = (bw, url)

    dur = None
    m = re.search(r'"@mediaPresentationDuration"\s*:\s*"([^"]+)"',
                  json.dumps(playback, ensure_ascii=False))
    if m:                       # ISO8601 (PT9.3S 등)
        d = re.search(r"PT(?:(\d+)H)?(?:(\d+)M)?([\d.]+)S", m.group(1))
        if d:
            dur = int(float(d.group(3)) + int(d.group(2) or 0) * 60
                      + int(d.group(1) or 0) * 3600)
    return best[1], dur


def _fetch_card(media_id):
    """상세 — 정확한 조회수·좋아요·설명·mp4 직링크. 실패는 빈 dict."""
    q = urllib.parse.urlencode({
        "userInteraction": "true", "seedType": "PERSONAL", "serviceType": "CLIP",
        "seedMediaId": media_id, "mediaType": "VOD"})
    try:
        d = _get(f"{_CARD_API}?{q}", "https://m.naver.com/")
        c = ((d.get("body") or {}).get("card") or {}).get("content") or {}
    except Exception:           # noqa: BLE001 — 한 건 실패가 검색을 죽이면 안 된다
        return {}
    vod = c.get("vod") or {}
    play_url, dur = _mpd_best_mp4(vod.get("playback") or {})
    likes = 0
    for r in (((c.get("interaction") or {}).get("like") or {}).get("reactions") or []):
        if r.get("reactionType") == "like":
            likes = r.get("count") or 0
    prof = c.get("profile") or {}
    # 썸네일은 목록에 없다 — 목록의 '클립 이미지'는 jpg가 아니라 **트레일러 mp4**다.
    # 카드 응답 안의 포스터 프레임(video-phinf .jpg)을 쓴다. 기본으로 딸려 오는
    # `?type=s80`은 120×67짜리라 카드에 못 쓴다(실측). 원본은 2160×3840로 과하고
    # `?type=w640`이 640×1138(114KB)로 적당하다. `f640`은 404다.
    thumb = ""
    m = re.search(r'https://video-phinf\.pstatic\.net/[^"\'\s?]+\.jpg',
                  json.dumps(c, ensure_ascii=False))
    if m:
        thumb = m.group(0) + "?type=w640"
    return {
        "title": (c.get("description") or c.get("title") or "").strip(),
        "channel": prof.get("nickname") or "",
        "channel_id": prof.get("profileId") or "",
        "channel_url": prof.get("endUrl") or "",
        "views": vod.get("count"),
        "likes": likes,
        "comments": ((c.get("interaction") or {}).get("comment") or {}).get("count") or 0,
        # 발행 시각(ISO). 랭킹의 속도(조회수÷경과시간)가 이 값으로 계산된다 —
        # 없으면 '몇 일 전' 문자열밖에 없어 속도를 못 낸다.
        "posted_at": c.get("publishedTime") or "",
        "play_url": play_url,
        "duration": dur,
        "thumbnail": thumb,
    }


def search(keyword, max_results=10, pages=3, enrich=True):
    """키워드 → 네이버 클립 **인기순**(조회수 내림차순) 결과.

    pages=3이면 최대 72건을 훑어 그중 상위 max_results건만 상세 조회한다.
    상세(②)는 건당 1회 호출이라, 훑는 범위는 넓히되 상세는 상위만 본다."""
    rows, seen = [], set()
    for p in range(max(1, pages)):
        try:
            items = _parse_list(_fetch_list(keyword, 1 + p * _PAGE_SIZE))
        except Exception:       # noqa: BLE001 — 백엔드 계약: 예외를 밖으로 안 던진다
            break
        if not items:
            break
        for it in items:
            if it["mediaId"] in seen:
                continue
            seen.add(it["mediaId"])
            rows.append(it)

    rows.sort(key=lambda x: -x["views"])
    out = []
    for it in rows[:max_results]:
        row = {
            "url": ("https://m.naver.com/shorts?serviceType=CLIP&mediaType=VOD"
                    f"&seedMediaId={it['mediaId']}"),
            "title": it["title"],
            "thumbnail": "",
            "channel": it["creator"],
            "channel_id": "", "channel_url": "",
            "views": it["views"],
            "likes": None, "comments": 0, "posted_at": "",
            "play_url": "",
            "duration": None,
            "mediaId": it["mediaId"],
        }
        if enrich:
            card = _fetch_card(it["mediaId"])
            for k, v in card.items():
                if v not in (None, "", 0) or k in ("likes",):
                    row[k] = v
        out.append(row)
    return out
