"""Buffer(SNS 예약발행) 호출 — **여기가 유일한 출구다**.

★왜 한 곳인가 (CLAUDE.md 0순위-B)
GraphQL 주소·인증 헤더·쿼리 문자열을 화면과 서버 두 곳에 적으면 언젠가 어긋난다.
호출은 전부 이 파일을 지난다. 키를 고르는 판단은 keyroute 하나뿐이므로 여기서
키를 직접 읽지 않고 **받아서 쓴다**.

★고객이 자기 키를 넣는다(BYOK)
Buffer는 2026-08 현재 **제3자 OAuth가 안 열렸다** — 새 GraphQL API는 개인 키 전용
베타이고 옛 REST OAuth는 신규 앱 등록이 닫혔다. 그래서 "우리가 고객을 대신해
발행"은 불가능하고, 고객이 자기 Buffer에서 개인 키를 만들어 등록하는 길만 된다
(경쟁 프로그램도 같은 방식). 우리 `customer_keys`(암호화 저장)에 그대로 얹는다.

★영상은 파일로 못 올린다
Buffer에는 업로드 창구가 없다. **공개 URL**을 넘겨야 하고 그 주소는
인증 없이 열려야 하며 HTTPS여야 하고 게시 시점까지 살아 있어야 한다.
(그 주소를 만드는 일은 여기 소관이 아니다 — app 쪽 임시 공개 링크가 맡는다)

문서: developers.buffer.com  /guides/authentication  /examples/create-video-post
"""

import json
import logging
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

API_URL = "https://api.buffer.com"          # GraphQL 하나뿐이다
_TIMEOUT = 20


class BufferError(Exception):
    """Buffer가 거절했다. message는 **사용자에게 보여줄 수 있는** 한국어로 만든다."""


def _call(key: str, query: str, variables: dict | None = None) -> dict:
    """GraphQL 한 번. 성공하면 data를, 아니면 BufferError를 던진다.

    ★키를 로그에 남기지 않는다. 실패 로그에도 키 조각을 넣지 마라 —
      고객 자격증명이 서버 로그에 남으면 그 자체가 사고다.
    """
    body = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = urllib.request.Request(
        API_URL, data=body,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            out = json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise BufferError("Buffer 키가 맞지 않습니다. 키를 다시 등록해 주세요.")
        if e.code == 429:
            raise BufferError("Buffer 요청 한도를 넘었습니다. 잠시 뒤 다시 해주세요.")
        raise BufferError(f"Buffer가 응답하지 않습니다(HTTP {e.code}).")
    except Exception as e:                       # 네트워크·타임아웃
        log.warning("buffer 호출 실패: %s", type(e).__name__)
        raise BufferError("Buffer에 연결하지 못했습니다.")

    # GraphQL은 HTTP 200으로도 오류를 준다 — errors를 반드시 본다.
    errs = out.get("errors") or []
    if errs:
        log.warning("buffer GraphQL errors 원문: %s", json.dumps(errs, ensure_ascii=False)[:1500])
        msg = (errs[0] or {}).get("message") or "알 수 없는 오류"
        raise BufferError(f"Buffer: {msg}")
    return out.get("data") or {}


def probe(key: str) -> bool:
    """키가 살아 있는가. **돈을 쓰지 않는 가장 가벼운 쿼리**로만 본다.

    ★일레븐랩스에서 배운 것: 권한을 좁게 만든 키는 엉뚱한 엔드포인트에서만 401이
      난다(app._probe_user_key 주석). account는 문서가 첫 예제로 쓰는 쿼리라
      키가 살아 있으면 반드시 통과한다.
    """
    try:
        d = _call(key, "{ account { id email } }")
        return bool((d.get("account") or {}).get("id"))
    except BufferError:
        return False


def organizations(key: str) -> list[str]:
    """이 키가 속한 조직 id 목록.

    ★channels는 **organizationId가 필수**다(문서 examples/get-channels).
      인자 없이 부르면 에러가 난다 — 조직을 먼저 얻어야 한다.
    """
    d = _call(key, "{ account { organizations { id } } }")
    orgs = ((d.get("account") or {}).get("organizations") or [])
    return [o["id"] for o in orgs if (o or {}).get("id")]


def channels(key: str) -> list[dict]:
    """이 키로 발행할 수 있는 채널 목록 → [{id, service, name}]

    고객이 어디에 올릴지 고르게 하려면 이게 있어야 한다.
    ★조직이 여러 개일 수 있다 — 전부 합쳐서 준다(하나만 보면 어떤 고객은
      자기 채널이 통째로 안 보인다).
    """
    q = """query($org: OrganizationId!) {
      channels(input: { organizationId: $org }) {
        id name displayName service avatar isQueuePaused
      }
    }"""
    out, seen = [], set()
    for org in organizations(key):
        d = _call(key, q, {"org": org})
        for c in (d.get("channels") or []):
            cid = (c or {}).get("id")
            if not cid or cid in seen:
                continue
            seen.add(cid)
            out.append({"id": cid, "service": c.get("service") or "",
                        "name": c.get("displayName") or c.get("name") or "",
                        "avatar": c.get("avatar") or "",
                        "paused": bool(c.get("isQueuePaused"))})
    return out


_CREATE = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess { post { id text dueAt } }
    ... on MutationError { message }
  }
}
"""


# 채널이 어느 SNS인지 → id로 기억해 둔다. 예약 한 번에 채널을 매번 다시 묻지 않는다.
_SERVICE_CACHE: dict[str, str] = {}


def _service_of(key: str, channel_id: str) -> str:
    """이 채널이 어느 SNS인가. 모르면 빈 문자열(호출부가 metadata를 안 붙인다)."""
    if channel_id in _SERVICE_CACHE:
        return _SERVICE_CACHE[channel_id]
    try:
        for c in channels(key):
            if c.get("id"):
                _SERVICE_CACHE[c["id"]] = (c.get("service") or "").lower()
    except BufferError:
        return ""                       # 채널을 못 물어봐도 예약 자체는 시도한다
    return _SERVICE_CACHE.get(channel_id, "")


def _post_metadata(key: str, channel_id: str, privacy: str = "") -> dict:
    """SNS마다 요구하는 부가정보. **없으면 Buffer가 거절한다.**

    ★인스타는 type이 **필수**다(실측 2026-08-30 라이브 오류:
      "Invalid post: Instagram posts require a type (post, story, or reel)").
      우리가 올리는 것은 세로 완성본이므로 reel이 맞다.
      shouldShareToFeed도 필수 — 릴스를 피드에도 남긴다(True).
      문서: developers.buffer.com/types/InstagramPostMetadataInput
    ★SNS를 늘릴 때 여기 한 곳만 고친다(0순위-B). 모르는 SNS면 빈 dict —
      필요 없는 곳에 metadata를 붙여 새 거절을 만들지 않는다.
    """
    svc = _service_of(key, channel_id)
    if svc == "instagram":
        return {"instagram": {"type": "reel", "shouldShareToFeed": True}}
    if svc == "youtube":
        # ★유튜브만 공개범위를 받는다(스키마 실측: YoutubePrivacy = public/unlisted/private).
        #   인스타는 이 축이 **아예 없다** — InstagramPostMetadataInput 7필드에 없다.
        pv = privacy if privacy in ("public", "unlisted", "private") else "public"
        return {"youtube": {"type": "short", "privacy": pv}}
    return {}


def schedule_video(key: str, channel_id: str, text: str, video_url: str,
                   due_at: str | None = None, thumb_ms: int = 0,
                   share_now: bool = False, privacy: str = "") -> dict:
    """영상 하나를 예약한다. → {id, dueAt}

    due_at : ISO8601 UTC (예 "2026-03-26T10:28:47.545Z"). 없으면 **큐에 넣는다**
             (고객이 Buffer에서 정해둔 시간표를 따른다 — 우리가 시간을 지어내지 않는다).
    thumb_ms: 썸네일로 쓸 지점(밀리초). 인스타·틱톡·핀터레스트에 적용된다.
    share_now: True면 **지금 바로 올린다**(예약이 아니다. 되돌릴 수 없다).
    privacy  : 유튜브 공개범위 public|unlisted|private. 다른 SNS는 무시된다
               (인스타에는 이 축이 없다 — 스키마 실측).
    ★video_url은 **인증 없이 열리는 주소**여야 한다. Buffer가 직접 받아 간다.
    """
    asset = {"video": {"url": video_url}}
    if thumb_ms:
        asset["video"]["metadata"] = {"thumbnailOffset": int(thumb_ms)}
    inp = {"channelId": channel_id, "text": text or "",
           "schedulingType": "automatic", "assets": [asset]}
    meta = _post_metadata(key, channel_id, privacy)
    if meta:
        inp["metadata"] = meta
    # ★올리는 방식은 셋 중 하나다(스키마 실측 ShareMode: addToQueue/customScheduled/
    #   shareNext/shareNow). shareNow는 **지금 바로 게시**라 되돌릴 수 없다 —
    #   화면이 한 번 더 묻고 나서만 여기로 온다.
    if share_now:
        inp["mode"] = "shareNow"
    elif due_at:
        inp["mode"] = "customScheduled"
        inp["dueAt"] = due_at
    else:
        inp["mode"] = "addToQueue"

    d = _call(key, _CREATE, {"input": inp})
    res = d.get("createPost") or {}
    if res.get("message"):                      # MutationError 쪽으로 왔다
        # ★거절될 때만 보낸 것을 남긴다(2026-08-30). 성공까지 남기면 고객 글이 매번
        #   로그에 쌓인다. 키는 어차피 inp에 없다(헤더로만 간다).
        #   ⚠️"Video could not be read from its URL"은 주소를 못 읽을 때뿐 아니라
        #     **규격 미달**(예: 9:16이 아닌 영상)에도 같은 문구로 온다 — 실측 2026-08-30.
        log.warning("buffer createPost 거절: %s / 보낸것: %s",
                    res["message"], json.dumps(inp, ensure_ascii=False)[:800])
        raise BufferError(f"Buffer: {res['message']}")
    post = res.get("post") or {}
    if not post.get("id"):
        raise BufferError("Buffer가 예약 결과를 주지 않았습니다.")
    return {"id": post["id"], "dueAt": post.get("dueAt") or ""}
