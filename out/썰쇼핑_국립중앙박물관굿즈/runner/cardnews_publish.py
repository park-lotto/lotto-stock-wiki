# -*- coding: utf-8 -*-
"""인스타그램 캐러셀 게시 — 앱에 **없던 유일한 조각** (2026-08-17).

■ 무엇이 이미 있었고 무엇이 없었나
    앱 `services/instagramUploadService.ts`(276줄)에 OAuth → 토큰 교환 → 장기토큰 →
    사용자 조회 → 컨테이너 생성 → 폴링 → `media_publish` 가 **이미 다 있다.**
    권한 스코프도 `instagram_basic, instagram_content_publish, pages_show_list,
    pages_read_engagement` 로 맞다.

    **빠진 것은 캐러셀 하나다** — `:178` 이 `media_type: 'REELS'` 로 굳어 있어
    영상 한 편만 올릴 수 있다. 카드뉴스는 장당 `image_url` 자식 컨테이너 N개 +
    `media_type: 'CAROUSEL'` 부모 하나가 필요하다.

■ 왜 이미지를 어딘가에 먼저 올려야 하나
    Meta 는 **파일을 받지 않는다.** 공개 URL 을 주면 자기가 가져간다.
    그래서 R2(`volcano-mcp-assets`)에 짧은 수명으로 올리고 게시 뒤 지운다.
    ★그 URL 은 Meta 서버가 인증 없이 받을 수 있어야 한다 — 헤더를 못 싣는다.
      §"자산은 URL 자체가 열쇠다" 와 같은 성질이고, 같은 방식(서명 URL)을 쓴다.

■ 하지 않는 것
    이 모듈은 **토큰을 만들지 않는다.** OAuth 왕복은 사용자 브라우저에서 나고,
    여기 오는 것은 이미 발급된 장기 토큰이다. 토큰을 서버에 보관하지도 않는다 —
    480명 키를 우리가 들고 있으면 그게 사고의 근원이다(§2 와 같은 판단).
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

GRAPH = "https://graph.facebook.com/v21.0"

#: 인스타 캐러셀 한 게시물 상한 (Graph API).
CAROUSEL_MAX = 10
#: 캐러셀 최소 — 2장 미만은 캐러셀이 아니라 단일 이미지다.
CAROUSEL_MIN = 2

#: 컨테이너가 준비될 때까지 기다리는 한도. 이미지는 보통 몇 초다.
STATUS_POLL_MAX = 60
STATUS_POLL_SEC = 2


class PublishError(RuntimeError):
    """게시 실패. **사람이 읽을 말**로 만든다 — 수강생이 보는 문구다."""


def _post(path, params, timeout=60):
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(f"{GRAPH}/{path}", data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise PublishError(_explain(e))


def _get(path, params, timeout=60):
    q = urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(f"{GRAPH}/{path}?{q}", timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise PublishError(_explain(e))


def _explain(err):
    """Meta 오류를 사람 말로. 원문 코드는 뒤에 남긴다 — 진단에 필요하다."""
    try:
        body = json.loads(err.read().decode("utf-8"))
        e = body.get("error") or {}
        msg = e.get("message") or ""
        code = e.get("code")
        sub = e.get("error_subcode")
    except Exception:
        return f"인스타 게시 실패 (HTTP {err.code})"

    hint = None
    if code == 190:
        hint = ("인스타 연결이 만료됐어요. 볼케이노 앱에서 인스타그램을 다시 "
                "연결해주세요.")
    elif code == 200 or "permission" in msg.lower():
        hint = ("게시 권한이 없어요. 인스타 계정이 **프로페셔널(비즈니스/크리에이터)** "
                "이고 페이스북 페이지에 연결돼 있어야 해요.")
    elif code == 4 or code == 17 or "limit" in msg.lower():
        hint = ("인스타 게시 한도에 걸렸어요. 잠시 뒤에 다시 해주세요. "
                "★새 계정을 만들어 이어서 올리지 마세요 — 그것이 계정 정지 사유가 됩니다.")
    elif code == 9004 or "media" in msg.lower() and "fetch" in msg.lower():
        hint = ("인스타가 이미지를 가져가지 못했어요. 이미지 주소가 공개 상태이고 "
                "만료되지 않았는지 확인이 필요해요.")
    return f"{hint or '인스타 게시 실패'} (code={code}, sub={sub}) {msg}"


# ── 계정 ────────────────────────────────────────────────────


def upload_cards(files, targets, timeout=120):
    """카드 PNG 를 서버가 준 자리에 올리고 **공개 주소**를 돌려준다.

    ■ 왜 이 걸음이 있나
        인스타는 파일을 안 받는다 — `image_url` 로 **공개 주소**를 주면 자기가
        가져간다. 그래서 그 주소를 먼저 만들어야 하고, 그 자리는 서버가 정한다.

    ■ ★주소를 여기서 짓지 않는다
        `targets` 는 서버가 서명해 준 것이다(`{index, put, get}`). 실행기가
        주소를 지어내면 서명이 안 맞아 401 이 나고, 모델은 그것을 "열쇠가
        틀렸구나" 로 읽어 **손에 있는 다른 열쇠를 차례로 꽂는다** — 2026-08-13
        자산 사고가 정확히 그 모양이었다.

    ■ ★올린 것을 확인한다
        PUT 이 200 이어도 바이트가 갔는지는 다른 문제다. 서버가 받은 바이트 수를
        돌려주므로 **보낸 크기와 대조**한다. 안 맞으면 그 자리에서 멈춘다 —
        인스타가 반쪽 그림을 가져가면 게시물이 깨진 채로 나간다.
    """
    if len(files or []) != len(targets or []):
        raise PublishError(f"카드 {len(files or [])}장인데 올릴 자리는 "
                           f"{len(targets or [])}개입니다 — 서버에 다시 물어야 합니다.")
    urls = []
    for path, t in zip(files, targets):
        with open(path, "rb") as f:
            raw = f.read()
        if raw[:8] != b"\x89PNG\r\n\x1a\n":
            raise PublishError(f"PNG 가 아닙니다: {path}")
        # ★User-Agent 를 반드시 준다. 파이썬 기본 UA 로 부르면 Cloudflare 가
        #   **error 1010 / HTTP 403** 으로 막는다(§4 에 적힌 함정 그대로이고,
        #   실제 왕복에서 여기 걸렸다). 우리 401 이 아니라 앞단 차단이라
        #   "열쇠가 틀렸나" 로 오진하게 된다.
        req = urllib.request.Request(t["put"], data=raw, method="PUT",
                                     headers={"Content-Type": "image/png",
                                              "User-Agent": "volcano-cardnews/1"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                got = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:200]
            raise PublishError(f"카드 {t['index']}장 올리기 실패 HTTP {e.code}: {body}")
        if int(got.get("bytes") or 0) != len(raw):
            raise PublishError(
                f"카드 {t['index']}장이 덜 갔습니다 "
                f"(보낸 {len(raw)} · 받은 {got.get('bytes')}) — 다시 올려야 합니다.")
        urls.append(t["get"])
    return {"imageUrls": urls, "count": len(urls)}


def find_ig_user(access_token):
    """이 토큰이 게시할 수 있는 인스타 프로 계정을 찾는다.

    페이지 → 연결된 인스타 계정 순서로 본다. 앱 `fetchInstagramUserInfo` 와 같은 길."""
    pages = _get("me/accounts", {"access_token": access_token,
                                 "fields": "id,name,instagram_business_account"})
    for p in pages.get("data") or []:
        iga = p.get("instagram_business_account")
        if iga and iga.get("id"):
            return {"igUserId": iga["id"], "pageId": p.get("id"),
                    "pageName": p.get("name")}
    raise PublishError(
        "게시할 인스타 계정을 못 찾았어요. 인스타를 **프로페셔널 계정**으로 바꾸고 "
        "페이스북 페이지에 연결한 뒤 다시 시도해주세요.")


# ── 컨테이너 ────────────────────────────────────────────────


def create_child(ig_user_id, image_url, access_token):
    """캐러셀 자식 컨테이너 1장.

    ★`is_carousel_item=true` 가 있어야 자식이 된다 — 빼면 단일 게시물 컨테이너가
      만들어지고, 부모에 묶을 때 거부된다."""
    res = _post(f"{ig_user_id}/media", {
        "image_url": image_url,
        "is_carousel_item": "true",
        "access_token": access_token,
    })
    cid = res.get("id")
    if not cid:
        raise PublishError(f"이미지 컨테이너를 만들지 못했어요: {res}")
    return cid


def create_parent(ig_user_id, children, caption, access_token):
    """캐러셀 부모 컨테이너. 자식 id 를 순서대로 묶는다."""
    if not (CAROUSEL_MIN <= len(children) <= CAROUSEL_MAX):
        raise PublishError(
            f"캐러셀은 {CAROUSEL_MIN}~{CAROUSEL_MAX}장이어야 해요 (지금 {len(children)}장).")
    res = _post(f"{ig_user_id}/media", {
        "media_type": "CAROUSEL",
        "children": ",".join(children),
        "caption": caption or "",
        "access_token": access_token,
    })
    cid = res.get("id")
    if not cid:
        raise PublishError(f"캐러셀을 만들지 못했어요: {res}")
    return cid


def wait_ready(container_id, access_token):
    """컨테이너가 준비될 때까지 기다린다.

    ★준비 전에 게시하면 거부된다. `status_code` 를 **실제로 읽는다** —
      존재만 확인하고 넘어가면 유령 게이트다."""
    for _ in range(STATUS_POLL_MAX):
        res = _get(container_id, {"fields": "status_code,status",
                                  "access_token": access_token})
        code = res.get("status_code")
        if code == "FINISHED":
            return True
        if code == "ERROR":
            raise PublishError(f"이미지 처리에 실패했어요: {res.get('status') or res}")
        time.sleep(STATUS_POLL_SEC)
    raise PublishError("인스타가 이미지를 준비하는 데 너무 오래 걸려요. 잠시 뒤 다시 해주세요.")


def publish(ig_user_id, creation_id, access_token):
    res = _post(f"{ig_user_id}/media_publish", {
        "creation_id": creation_id, "access_token": access_token})
    mid = res.get("id")
    if not mid:
        raise PublishError(f"게시하지 못했어요: {res}")
    return mid


def permalink(media_id, access_token):
    """게시물 주소. 실패해도 게시는 이미 됐으므로 **막지 않는다.**"""
    try:
        return _get(media_id, {"fields": "permalink",
                               "access_token": access_token}).get("permalink")
    except Exception:
        return None


# ── 한 번에 ─────────────────────────────────────────────────


def publish_carousel(image_urls, caption, access_token, ig_user_id=None,
                     on_progress=None):
    """카드 N장을 캐러셀 한 게시물로 올린다.

    돌려주는 것: {mediaId, permalink, children, igUserId}

    ★중간에 실패하면 **어디까지 갔는지 말한다.** 자식 컨테이너는 만들어졌는데
      부모에서 실패하면 다시 만들 필요가 없다."""
    urls = [u for u in (image_urls or []) if isinstance(u, str) and u.startswith("https://")]
    if len(urls) != len(image_urls or []):
        raise PublishError("이미지 주소는 전부 https 공개 주소여야 해요 "
                           "(인스타가 직접 가져갑니다).")
    if not ig_user_id:
        ig_user_id = find_ig_user(access_token)["igUserId"]

    children = []
    for i, url in enumerate(urls, 1):
        if on_progress:
            on_progress(f"{i}/{len(urls)}장 올리는 중")
        cid = create_child(ig_user_id, url, access_token)
        wait_ready(cid, access_token)
        children.append(cid)

    if on_progress:
        on_progress("캐러셀로 묶는 중")
    parent = create_parent(ig_user_id, children, caption, access_token)
    wait_ready(parent, access_token)

    if on_progress:
        on_progress("게시하는 중")
    media_id = publish(ig_user_id, parent, access_token)
    return {"mediaId": media_id, "permalink": permalink(media_id, access_token),
            "children": children, "igUserId": ig_user_id}
