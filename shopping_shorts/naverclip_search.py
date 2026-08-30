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
from concurrent.futures import ThreadPoolExecutor

# 모바일 UA로 고정한다 — 클립 탭은 모바일 검색의 탭이고, PC UA로는 같은
# 프래그먼트가 안 온다(실측). 여기서 UA를 바꾸면 파서가 통째로 헛돈다.
_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
       "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1")

_LIST_API = "https://s.search.naver.com/p/clip/4/api/tab/more"
_CARD_API = "https://creatorhub-api.naver.com/api/v7.0/clipviewer/card"

_PAGE_SIZE = 24            # 실측: 한 번에 24건이 온다. start=1,25,49...
_TIMEOUT = 30


def _get(url, referer, headers=None):
    """GET → JSON. `headers`로 추가 헤더를 실을 수 있다.

    ★채널 목록 API(feed/contents)는 `x-creator-hub-sid: clip`이 없으면 400이다
      (2026-08-31 실측). 검색 경로는 이 헤더가 없어도 되므로 기본값은 그대로 둔다.
    """
    h = {"User-Agent": _UA, "Referer": referer, "Accept": "*/*"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return json.loads(r.read().decode())


def _num(s):
    """'14.8만' → 148000. 목록의 조회수는 반올림 표기라 정렬용으로만 쓴다."""
    s = (s or "").replace(",", "").strip()
    m = re.match(r"([\d.]+)\s*([만천억]?)", s)
    if not m:
        return 0
    return int(float(m.group(1)) * {"": 1, "천": 1e3, "만": 1e4, "억": 1e8}[m.group(2)])


def clip_url(media_id):
    """mediaId → 재생 페이지 주소. **주소를 만드는 곳은 여기 하나뿐이다(0순위-B).**

    ★clip.naver.com/clips/... 같은 모양을 지어내면 전부 404다(2026-08-31 실측:
      후보 7종 전부 404). 실제로 여는 주소는 m.naver.com의 shorts 뷰어다.
    """
    return ("https://m.naver.com/shorts?serviceType=CLIP&mediaType=VOD"
            f"&seedMediaId={media_id}")


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


def search(keyword, max_results=10, pages=3, enrich=True, workers=8):
    """키워드 → 네이버 클립 **인기순**(조회수 내림차순) 결과.

    pages=3이면 최대 72건을 훑어 그중 상위 max_results건만 상세 조회한다.
    상세(②)는 건당 1회 호출이라, 훑는 범위는 넓히되 상세는 상위만 본다.

    ★한 키워드의 천장은 약 500건이다(실측 '뷰티' 520건 / 40페이지 29초).
      페이지가 깊어질수록 수확이 23→6건으로 줄다가 신규 0으로 끝난다.
      더 늘리려면 페이지가 아니라 **키워드를 쪼개야** 한다.

    ★상세는 스레드로 돈다(2026-08-30). 순차면 건당 0.17초라 2,500건에 7분이
      걸려 웹 요청이 죽는다 — 실측 8스레드로 2,519건 118초."""
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

    def _row(it):
        row = {
            "url": clip_url(it["mediaId"]),
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
        return row

    top = rows[:max_results]
    if enrich and workers > 1 and len(top) > 1:
        with ThreadPoolExecutor(max_workers=min(workers, len(top))) as ex:
            out = list(ex.map(_row, top))      # map은 순서를 보존한다
    else:
        out = [_row(it) for it in top]
    # ★상세를 붙인 뒤 **다시** 정렬한다. 위 정렬은 목록의 반올림값('14.7만')
    #   기준이라 정확값(146,844)으로 바뀌면 순서가 조금 어긋난다 — 화면이
    #   '인기순'이라고 말하는 이상 마지막 값 기준으로 세워야 거짓말이 안 된다.
    out.sort(key=lambda r: -(r.get("views") or 0))
    return out


# ══════════════════════════════════════════════════════════════════════
# 채널 수집(2026-08-31) — 벤치마킹 채널을 매일 훑는 축
# ══════════════════════════════════════════════════════════════════════
# 키워드 검색과 **다른 축**이다: 키워드는 "뷰티에서 뭐가 터지나"(넓게),
# 채널은 "이 15명이 오늘 뭘 올렸나"(좁게·매일).
#
# 경로(브라우저 네트워크 관찰로 확인, 2026-08-31):
#   ① 핸들 → 프로필   /clip/profiles?clipId=<핸들>        ← 헤더 없이 200
#   ② 프로필 → 세션   /feed/content  (단수)               ← body.session.id
#   ③ 세션 → 목록     /feed/contents (복수) + sessionId   ← 실측 61건/회
#
# ★함정 3개 (여기서 시간을 다 썼다)
#   · ②를 건너뛰고 ③을 바로 부르면 400 `Session not found or expired`.
#   · ③은 `x-creator-hub-sid: clip` 헤더가 필요하다(없으면 400).
#   · 채널 HTML(clip.naver.com/@핸들)은 **JS 껍데기**다 — mediaId 0개,
#     `__NEXT_DATA__`도 없다. 파싱하려 들지 마라.
_CH_API = "https://creatorhub-api.naver.com/api/v7.0"
_CH_HDR = {"x-creator-hub-sid": "clip", "Accept": "application/json"}
_CH_REF = "https://clip.naver.com/"


def handle_from_url(url):
    """채널 URL → 핸들(@뒤). 못 찾으면 "".

    카드 API가 주는 `channel_url`이 `https://clip.naver.com/@temtembara` 꼴이라
    거기서 핸들을 얻는다. 핸들을 알면 프로필·영상목록을 바로 부를 수 있다.
    """
    m = re.search(r"clip\.naver\.com/@([^/?#\s]+)", url or "")
    return m.group(1) if m else ""


def profile_by_handle(handle):
    """핸들 → 채널 정보. 없으면 빈 dict(예외 아님 — 한 채널이 사라져도 나머지는 돈다).

    반환: {profile_id, handle, nickname, followers, posts, videos, url, image}
    """
    if not (handle or "").strip():
        return {}
    q = urllib.parse.quote(handle.strip().lstrip("@"))
    try:
        d = _get(f"{_CH_API}/clip/profiles?clipId={q}", _CH_REF, _CH_HDR)
    except Exception:          # noqa: BLE001 — 한 채널 실패가 전체를 죽이면 안 된다
        return {}
    b = d.get("body") or {}
    pid = b.get("profileId")
    if not pid:
        return {}
    summary = b.get("summary") or {}
    tab = ((b.get("tabCounts") or {}).get("ALL") or {})
    return {
        "profile_id": pid,
        "handle": handle.strip().lstrip("@"),
        "nickname": b.get("nickname") or "",
        "followers": summary.get("numberOfFollowers") or 0,
        "posts": summary.get("numberOfPosts") or 0,
        # 게시물에는 글(post)도 섞인다 — 우리가 쓰는 건 영상(video)뿐이다.
        "videos": tab.get("video") or 0,
        "url": b.get("endUrl") or f"https://clip.naver.com/@{handle}",
        "image": b.get("profileImageUrl") or "",
    }


def _row_from_content(c):
    """카드 content → 우리 표준 행. 검색 경로(_row)와 같은 키를 쓴다."""
    mid = c.get("mediaId") or ""
    prof = c.get("profile") or {}
    vod = c.get("vod") or {}
    return {
        "media_id": mid,
        "url": clip_url(mid),
        "title": (c.get("description") or c.get("title") or "").strip(),
        "channel": prof.get("nickname") or "",
        "channel_id": prof.get("profileId") or "",
        "channel_url": prof.get("endUrl") or "",
        "views": vod.get("count") or 0,
        "posted_at": c.get("publishedTime") or "",
    }


def channel_videos(profile_id, want=60):
    """채널의 최근 영상 목록. 실패하면 빈 리스트.

    ★세션을 먼저 받아야 한다 — ②(단수)의 응답에 `body.session.id`가 있고,
      ③(복수)에 그걸 넘겨야 200이 온다. 순서를 바꾸면 400이다.
    ★②의 응답에도 카드가 **1건** 들어 있다(첫 영상). 버리면 최신 1편을 놓친다.
    """
    if not profile_id:
        return []
    rec = urllib.parse.quote(json.dumps(
        {"targetProfileId": profile_id, "open": True, "tab": "all"},
        separators=(",", ":")))
    out, seen = [], set()

    def _push(c):
        if not isinstance(c, dict):
            return
        mid = c.get("mediaId")
        if mid and mid not in seen:
            seen.add(mid)
            out.append(_row_from_content(c))

    try:
        d1 = _get(f"{_CH_API}/feed/content?recType=CLIP_PC&recId={rec}"
                  f"&playback=false&deviceType=html5_mo", _CH_REF, _CH_HDR)
    except Exception:          # noqa: BLE001
        return []
    b1 = d1.get("body") or {}
    sid = ((b1.get("session") or {}).get("id")) or ""
    _push(((b1.get("card") or {}).get("content")))
    if not sid:
        return out             # 세션이 없으면 더는 못 판다 — 받은 1건이라도 준다
    try:
        d2 = _get(f"{_CH_API}/feed/contents?recType=CLIP_PC&recId={rec}"
                  f"&playback=false&sessionId={sid}&count={int(want)}",
                  _CH_REF, _CH_HDR)
    except Exception:          # noqa: BLE001
        return out
    for card in ((d2.get("body") or {}).get("cards") or []):
        _push(card.get("content") if isinstance(card, dict) else None)
    return out
