"""썸네일 비전 태깅 + 그 태그로 카테고리 재분류 (2026-07-31).

왜 생겼나 — 두 가지 사고가 겹쳤다.

① 태깅이 멈췄다: 수집이 웹 엔드포인트(app._run_collect_job, 여기에 _tag_new_items가
   배선돼 있었다)에서 **systemd 타이머 스크립트**(scripts/daily_instagram_collect.py,
   2026-07-29 도입)로 옮겨갔는데 그 스크립트는 save_last_run만 하고 후속 처리를 하나도
   부르지 않았다. 실측: vision_tags 마지막 적재가 2026-07-30 10:41(마지막 수동수집)에서
   멈춰 있고, 그 뒤 타이머 수집은 계속 성공했는데 태그는 0건 증가.

② 그래서 카테고리가 무너졌다: 분류기 categorize(name, caption)는 캡션을 3배 가중하는데,
   429를 막으려 릴스 상세조회(INSTAGRAM_REEL_DETAIL)를 끄면서 **캡션이 100% 빈값**이 됐다
   (실측 431/431). 캡션이 없으면 채널명만 남고, 그러면 한 채널의 영상이 통째로 같은
   카테고리로 몰린다("홈새댁홈|레시피•꿀팁" → 그 채널 전부 레시피).

★핵심: 태깅만 되살리면 카테고리는 그대로다. 비전태그는 지금까지 **검색**만 썼고
(index.html matchesSearch), 분류기는 캡션만 본다. 그래서 이 모듈이 둘을 잇는다 —
비전태그를 '그 영상의 캡션 자리'에 넣어 다시 분류한다. 비전태그야말로 캡션보다 정직한
영상별 신호다(화면에 실제로 보이는 물건·자막을 읽은 것).
"""
from shopping_shorts.categorize import categorize
from shopping_shorts.store import Store

# 1회 수집당 새 태깅 상한(비용 가드). 초과분은 다음 수집 때 — app.py에 있던 값을 그대로 옮겼다.
VISION_TAG_CAP = 60


def tag_new_items(items, db_path, cap=VISION_TAG_CAP):
    """태그 없는 아이템의 썸네일을 Gemini 비전 태깅해 vision_tags에 저장. 태깅한 건수 반환.

    shortcode로 캐시하므로 재수집 땐 재호출 안 한다. 실패(키 없음·썸네일 실패)는 건너뛴다 —
    그 아이템은 예전처럼 채널명 기반 분류로 남는다(더 나빠지지 않는다)."""
    try:
        from shopping_shorts import video_analysis
    except Exception:      # noqa: BLE001 — 비전 모듈이 없어도 수집은 살아야 한다
        return 0
    store = Store(db_path)
    have = store.vision_tags_map([it.get("shortcode") for it in items])
    todo = [it for it in items
            if it.get("shortcode") and it.get("shortcode") not in have and it.get("thumbnail")]
    capped = todo[:cap]
    tagged = 0
    for it in capped:
        img = video_analysis.fetch_thumb_bytes(it.get("thumbnail"))
        if not img:
            continue
        tags = video_analysis.subject_tags_vision(img, it.get("caption", ""))
        if tags and (tags.get("subject") or tags.get("keywords")):
            store.save_vision_tags(it["shortcode"], tags.get("subject", ""), tags.get("keywords", []))
            tagged += 1
    if len(todo) > len(capped):
        print(f"[vision_tags] {len(todo) - len(capped)}건 다음 수집으로 미룸(상한 {cap})")
    return tagged


def vision_text(tag):
    """비전태그 dict → 분류기에 넣을 텍스트(주제어 + 키워드)."""
    subject = (tag.get("subject") or "").strip()
    kws = [k for k in (tag.get("keywords") or []) if isinstance(k, str)]
    return " ".join([subject] + kws).strip()


def recategorize_by_vision(items, db_path):
    """비전태그가 있는 아이템의 category를 그 태그로 다시 계산한다. 바뀐 건수 반환.

    items를 제자리 수정한다(호출부가 save_last_run으로 다시 저장하면 화면에 반영).
    태그가 없거나 텍스트가 비면 건드리지 않는다 — 손대지 않는 게 기존 동작 보존이다.
    ★캡션이 살아 있는 항목(유튜브·틱톡 등 title이 캡션 자리에 들어온다)도 비전태그가
    있으면 그쪽을 쓴다: 화면을 실제로 본 신호가 제목보다 그 영상에 가깝다."""
    store = Store(db_path)
    tmap = store.vision_tags_map([it.get("shortcode") for it in items])
    changed = 0
    for it in items:
        tag = tmap.get(it.get("shortcode"))
        if not tag:
            continue
        text = vision_text(tag)
        if not text:
            continue
        new = categorize(it.get("name") or it.get("username"), text)
        if new and new != it.get("category"):
            it["category"] = new
            changed += 1
    return changed
