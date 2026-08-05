"""6단계 SEO — 확정 대본으로 업로드용 메타데이터 생성(2026-07-17).

제목(+추천5)·설명·태그·해시태그·후킹·댓글유도·플랫폼별 CTA를 한 번에 뽑는다.
키워드 실측치(seo_probe)를 되먹이면 그 근거 위에서 다시 쓴다.

키풀: comment_gen 전용키(1개, 쉽게 소진) 대신 key_vault 공유풀을 캐스케이드로 쓴다
(general→ingest→embed→briefing). SEO는 사장님이 버튼 누르고 기다리는 대화형이라
대본생성과 똑같이 소진에 취약하다 — script_generate.py:20-25와 같은 이유.
"""
import json

from google.genai import types

from shopping_shorts import comment_gen
from pipeline.atoms import key_vault

_MODEL = comment_gen._MODEL
_GEN_GROUP = "general"

_PLATFORMS = ("youtube", "tiktok", "threads")

_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "title_candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "why": {"type": "string"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "why", "keywords"],
            },
        },
        "description": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}, "minItems": 20, "maxItems": 20},
        "hashtags": {
            "type": "object",
            "properties": {p: {"type": "array", "items": {"type": "string"}} for p in _PLATFORMS},
            "required": list(_PLATFORMS),
        },
        "hook_line": {"type": "string"},
        "comment_bait": {"type": "string"},
        # 인스타 릴스 캡션 전문(2026-08-03 사장님 — 폰에서 복사해 바로 붙여넣는 완성 덩어리).
        "insta_caption": {"type": "string"},
        "cta": {
            "type": "object",
            "properties": {p: {"type": "string"} for p in _PLATFORMS},
            "required": list(_PLATFORMS),
        },
    },
    "required": ["title", "title_candidates", "description", "tags",
                 "hashtags", "hook_line", "comment_bait", "insta_caption", "cta"],
}

_ONLY_LABELS = {
    "title": "제목과 추천 제목 5개",
    "description": "영상 설명",
    "tags": "유튜브 태그 20개",
    "hashtags": "플랫폼별 해시태그",
    "hook": "후킹 멘트와 댓글 유도",
    "insta": "인스타 캡션",
    "cta": "플랫폼별 CTA",
}

_BASE_PROMPT = """너는 한국 쇼츠 채널의 SEO 담당이다. 아래 확정 대본으로 업로드용 메타데이터를 만든다.

[규격 — 어기면 못 쓴다]
- 제목: 100자 이내. 검색 키워드를 앞쪽에 둔다. 추천 제목 5개를 주고, 각각 why에 "왜 이 제목인지"를 한 줄로 쓴다(훅에서 왔는지·카테고리에서 왔는지·어필포인트에서 왔는지).
- title_candidates[].keywords: 그 제목이 노리는 검색 키워드 1~3개. 실제로 사람이 검색창에 칠 법한 말로.
- 설명: 200~300자. 첫 줄에 핵심, 이후 줄바꿈으로 나눈다.
- 태그: 정확히 20개. 유튜브 태그 전체가 500자를 넘지 않게.
- 해시태그: 플랫폼마다 다르게. youtube 3~5개 / tiktok 3~5개 / threads 1~2개(쓰레드는 해시태그를 거의 안 쓴다).
- CTA: 플랫폼마다 어투가 다르다. youtube=설명란 링크 유도 / tiktok=댓글 유도형 / threads=되묻는 대화체.
- insta_caption: **인스타 릴스 캡션 전문** — 폰에서 그대로 붙여넣는 완성된 한 덩어리 텍스트다.
  잘 되는 공구 계정들의 캡션 공식을 그대로 따른다(순서 고정):
  ① 경험담 본문: 대본의 이야기를 1인칭으로 이어 쓴다. 한 문장마다 줄바꿈, 2~3문장마다 빈 줄.
     설명체 나열 금지 — "반신반의하면서 해봤는데 진짜 눈앞에서 되더라고요" 같은 서사로.
  ② ✔ 체크리스트 3~5줄: 제품 포인트를 "✔ "로 시작하는 짧은 줄로.
  ③ 댓글 유도: 대본 CTA와 **같은 키워드**로. ★밋밋한 "궁금하시면 댓글" 금지 — **댓글 남길
     명분**을 한 줄 얹어라(검색해도 잘 안 나옴 / 제가 산 최저가 그대로 / 다들 물어봐서 댓글로만
     공유 / 모르고 사면 비싸게 삼 — 원본에 있는 사실 범위 안에서만).
     그 뒤에 "댓글에 '키워드' 남겨주시면 바로 보내드릴게요💌"
     + "(🔔 팔로우 + 댓글 주셔야 DM 오류 없이 가요)" + "메시지 안 보이면 '숨김함/요청함' 확인해주세요"
  ④ 해시태그 4~5개(인스타용, 본문 맨 끝 한 줄).
  이모지는 줄당 최대 1개 — 남발하면 광고 티가 난다. 과장·허위 금지는 여기도 똑같다.
- 말투: 구조 분석의 tone을 그대로 따른다. 대본이 반말이면 제목·설명·CTA도 반말로 쓴다(영상은 반말인데 제목만 존댓말이면 같은 영상으로 안 보인다).
- 전부 한국어. 과장·허위 금지(대본에 없는 효능을 지어내지 마라).

[대본]
{script}

[구조 분석]
{structure}

[화면 헤드카피]
{headcopy}
"""


def _fmt_stats(keyword_stats):
    """실측치를 프롬프트에 넣을 문장으로. 없으면 빈 문자열."""
    if not keyword_stats:
        return ""
    lines = []
    for s in keyword_stats:
        v = s.get("verdict")
        if v == "blue":
            note = "뚫린다(수요 있고, 소형채널이 여기서 조회수를 낸 적 있다) — 밀어라"
        elif v == "red":
            note = "레드오션(수요는 있으나 소형채널은 아무도 못 뚫었다) — 이걸 메인으로 쓰지 마라"
        elif v == "dead":
            note = "수요 낮음 — 빼라"
        else:
            note = "미측정"
        # 수요는 views_top(상위 5편 중앙값)이다 — 20편 중앙값(views_median)은 꼬리에
        # 눌려 실제 수요를 못 보여준다(T8 실측). 뚫림은 '10만+ 낸 소형채널 편수'다 —
        # 비율은 꼬리의 영세채널이 부풀린다. 되먹임에 틀린 숫자를 넣으면
        # AI가 틀린 근거 위에서 다시 쓴다.
        lines.append(
            f"- {s.get('keyword')}: {v} / {note} "
            f"(상위 조회수 {s.get('views_top')}, "
            f"10만+ 낸 영상 {s.get('hit_n')}편 중 소형채널 {s.get('small_hits')}편)")
    return ("\n[유튜브 실측 — 이 근거 위에서 다시 써라]\n" + "\n".join(lines) + "\n")


def _locked_value(seo, card):
    """카드 id → 지금 확정된 내용(사람이 읽는 문자열). 없으면 None."""
    if card == "title":
        return seo.get("title")
    if card == "description":
        return seo.get("description")
    if card == "tags":
        tags = seo.get("tags") or []
        return ", ".join(tags) if tags else None
    if card == "hashtags":
        hs = seo.get("hashtags") or {}
        parts = [f"{k}: {' '.join(v or [])}" for k, v in hs.items() if v]
        return " / ".join(parts) if parts else None
    if card == "hook":
        bits = [x for x in (seo.get("hook_line"), seo.get("comment_bait")) if x]
        return " / ".join(bits) if bits else None
    if card == "insta":
        return seo.get("insta_caption") or None
    if card == "cta":
        cta = seo.get("cta") or {}
        parts = [f"{k}: {v}" for k, v in cta.items() if v]
        return " / ".join(parts) if parts else None
    return None


def _fmt_locked(locked, seo=None):
    """잠긴 항목을 **내용까지** 프롬프트에 싣는다.

    ★필드명만 넣던 시절엔("title, cta") AI가 잠긴 제목을 볼 수 없는 채로 "그대로 두고
    나머지를 여기에 어울리게 써라"는 지시를 받았다 — 볼 수 없는 것에 맞출 수는 없으므로
    잠금의 광고된 동작이 전혀 일어나지 않았다(2026-07-17 리뷰).
    """
    if not locked:
        return ""
    seo = seo or {}
    lines = []
    for card, on in locked.items():
        if not on:
            continue
        label = _ONLY_LABELS.get(card, card)
        val = _locked_value(seo, card)
        lines.append(f"- {label}: {val}" if val else f"- {label}: (아직 내용 없음)")
    if not lines:
        return ""
    return ("\n[잠긴 항목 — 사장님이 확정한 것이다. 이 내용을 그대로 두고, "
            "나머지를 여기에 어울리게 써라]\n" + "\n".join(lines) + "\n")


def _build_prompt(job, captions, only, locked, keyword_stats):
    struct = job.get("script_structure") or {}
    head = (job.get("headcopy") or {}).get("text") or ""
    p = _BASE_PROMPT.format(
        script=job.get("given_script") or "",
        structure=json.dumps(struct, ensure_ascii=False, indent=1),
        headcopy=head,
    )
    if captions:
        # 소스 릴스 캡션 = 실제로 터진 영상의 문구. 단 인스타 문법이라 톤 참고용이다
        # (유튜브 검색 키워드는 seo_probe 실측으로 검증한다).
        p += ("\n[참고 — 이 영상이 참고한 인스타 릴스 캡션. 톤·소구점만 참고하고 "
              "인스타 해시태그 문법을 유튜브에 그대로 옮기지 마라]\n"
              + "\n".join(f"- {c}" for c in captions if c) + "\n")
    p += _fmt_stats(keyword_stats)
    p += _fmt_locked(locked, job.get("seo") or {})   # 잠긴 값은 job에 저장된 확정본에서
    if only:
        p += (f"\n[이번엔 {_ONLY_LABELS.get(only, only)}만 새로 써라. "
              "나머지 항목도 스키마대로 채워서 반환하되 기존 것을 유지해라.]\n")
    return p


def generate(job, captions=None, only=None, locked=None, keyword_stats=None):
    """key_vault 캐스케이드로 SEO 일습 생성. 소진키는 마킹하고 다음 키로.
    무키·전부실패면 None."""
    keys = key_vault.get_live_keys_cascade(_GEN_GROUP)
    if not keys:
        return None
    prompt = _build_prompt(job, captions, only, locked, keyword_stats)
    for key in keys:
        try:
            resp = key_vault.get_client_for_key(key).models.generate_content(
                model=_MODEL, contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=_SCHEMA),
            )
            return json.loads(resp.text)
        except Exception as e:  # noqa: BLE001 — 생성 실패는 치명적 아님
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                key_vault.mark_exhausted(key_vault._owner_group(key) or _GEN_GROUP, key)
                continue
            if key_vault.is_quota_error(e):
                continue  # 순간 rate limit — 다음 키로
            return None
    return None


def seed_keywords(seo):
    """title_candidates[].keywords 평탄화·중복제거(순서 보존).
    seo_probe.probe_keywords()가 앞 _MAX_PROBE개만 재므로 순서가 곧 우선순위다."""
    out, seen = [], set()
    for c in (seo or {}).get("title_candidates") or []:
        for k in c.get("keywords") or []:
            if k and k not in seen:
                seen.add(k)
                out.append(k)
    return out
