"""썸네일 제목 추천 — 확정 대본으로 화면에 큼직하게 얹을 짧은 제목 후보를 뽑는다(2026-07-19).

SEO 제목(seo_generate, 검색 최적화·100자)과는 목적이 다르다. 썸네일 제목은 **이미지 위에
얹는 것**이라 2~3어절·한두 줄·호기심/충격 위주여야 한다(길면 자동 줄바꿈으로 작아진다).
목적: 제목을 못 떠올리는 사장님이 **원본 영상만 보고 클릭 한 번으로** 얹게 하는 것.

플럼빙(모델·키풀 캐스케이드·소진 마킹)은 seo_generate와 똑같다 — 대화형이라 소진에 취약해
comment_gen 전용키가 아니라 key_vault 공유풀(general→…)을 캐스케이드로 쓴다.
"""
import hashlib
import json

from google.genai import types

from shopping_shorts import comment_gen
from shopping_shorts import script_engine
from pipeline.atoms import key_vault

_MODEL = comment_gen._MODEL
_GEN_GROUP = "general"

_SCHEMA = {
    "type": "object",
    "properties": {
        "titles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["text", "why"],
            },
            "minItems": 4,
            "maxItems": 6,
        },
    },
    "required": ["titles"],
}

_PROMPT = """너는 한국 쇼츠 채널의 썸네일 카피라이터다. 아래 영상 대본을 보고, 영상 위에 큼직하게 얹을 **썸네일 제목** 후보 5개를 만든다.

**썸네일 제목의 유일한 임무는 스크롤을 멈추는 것이다.** 내용을 요약하는 게 아니다.
요약형("미니 세탁기 추천")은 손가락을 못 멈춘다 — 아래 훅 장치 중 하나를 반드시 건다.

[훅 장치 — 5개 후보는 서로 다른 장치를 쓴다(같은 장치 2개 금지)]
1. 타깃 호출 — 보는 사람을 콕 집는다. "자취생만", "○○ 쓰는 분"
2. 손해·경고 — 모르면 손해라고 찌른다. "이거 모르고 삼", "그냥 버리지 마세요"
3. 반전·의외 — 상식과 반대. "빨래를 안 해요", "비싼 게 아니었다"
4. 발견·후회 — 늦게 안 억울함. "왜 이제 알았지", "10년을 헛삼"
5. 숫자·구체 — 수치가 시선을 잡는다. "3분이면 끝", "월 2천원"
   ※ ★대본에 실제로 나온 숫자만 쓴다. 숫자가 대본에 없으면 이 장치를 **버리고** 다른 장치를 써라
     (그럴듯한 수치를 지어내는 것이 이 작업에서 가장 흔한 사고다).
※ 질문형·감탄형은 위 장치에 얹는 말투일 뿐, 그 자체로는 장치가 아니다.

[더 세게 만드는 법]
- **구체가 이긴다**: "편리한 세탁기"(X) → "속옷 따로 빨래"(O). 대본의 구체어를 그대로 살려라.
- **긴장을 남겨라**: 답을 다 말하지 말고 궁금하게 끊는다. "이거 진짜 요물"보다 "속옷 빨래 / 이제 안 해요".
- **일상어로**: 광고 문구체(최고·혁신·강력) 금지. 사람이 말하듯.
- **두 줄이 한 방을 만든다**: 윗줄=상황·타깃, 아랫줄=반전·결론. 아랫줄에 힘을 실어라.

[썸네일 제목 규격 — SEO 제목과 다르다. 어기면 못 쓴다]
- **보통 두 줄**로 만든다: 줄바꿈(\\n)을 꼭 넣어 1줄·2줄로 나눈다. 각 줄 3~8글자. (형식 예: "<윗줄 3~8자>\\n<아랫줄 3~8자>")
- ★소재는 **오직 아래 [대본] 내용**에서만 가져온다. 이 지시문의 형식 예시·참고 훅에 든 단어를 제목에 쓰지 마라(예시는 길이·줄바꿈·말맛을 보여줄 뿐이다).
- 짧고 강하게. 검색용 긴 문장 금지. 아주 짧아 한 줄이 자연스러우면 한 줄도 허용.
- 대본에 실제로 있는 사실만. 없는 효능·과장·허위 금지.
- 말투는 대본을 따른다(대본이 반말이면 제목도 반말).
- 이모지·특수기호 금지(글자만 — 꾸밈은 화면에서 따로 얹는다).
- why: 어떤 훅 장치를 썼고 왜 스크롤이 멈추는지 한 줄로.
- 전부 한국어.
{bank}
[대본]
{script}

[구조 분석]
{structure}

[화면 헤드카피(참고)]
{headcopy}
"""

# 참고 훅은 문장 단위라 많이 실으면 베끼기·드리프트가 난다(script_engine._PER_BUCKET의 hook=5와
# 같은 이유). 썸네일 제목은 훅·놀람 두 축만 쓰면 되므로 나머지 버킷은 싣지 않는다.
_BANK_BUCKETS = ("hook", "surprise")
_BANK_PER_BUCKET = 8


def _bank_block(seed=0):
    """수집된 대본 은행에서 훅·놀람 조각을 프롬프트 참고 블록으로. 은행이 비면 ''(무주입=종전 동작).

    ★생성기(script_engine)와 같은 은행을 읽는다 — 판단을 두 곳에 적지 않기 위해 로더·셔플을
    그대로 재사용한다(CLAUDE.md 0순위-B). 여기서 따로 파일을 열지 않는다.
    """
    try:
        bank = script_engine.load_bank()
    except Exception:      # noqa: BLE001 — 참고 블록은 없어도 제목은 나와야 한다
        return ""
    per = {b: _BANK_PER_BUCKET for b in _BANK_BUCKETS}
    lines = []
    for b in _BANK_BUCKETS:
        items = [x for x in (bank.get(b) or []) if x]
        if not items:
            continue
        pick = sorted(items, key=lambda x: hashlib.md5(
            f"{seed}|{b}|{x}".encode("utf-8")).hexdigest())[:per[b]]
        lines.append(f"  · {script_engine.BUCKET_LABEL[b]}: "
                     + " / ".join(f'"{x}"' for x in pick))
    if not lines:
        return ""
    return ("\n[참고 훅 — 실제로 터진 대본들에서 수확한 첫 문장·놀람 표현이다. "
            "**어떻게 시선을 잡았는지 그 수법과 말맛만** 가져와 우리 소재로 새로 써라.\n"
            "★★아래 문구의 어절을 그대로 가져다 쓰지 마라. 특히 '그냥 버리지 마세요'처럼 "
            "**다른 제품 이야기에서 온 표현을 우리 소재에 붙이면 말이 안 되는 제목이 된다**"
            "(실측 사고: 세탁기 제목에 '버리지 마세요'가 그대로 나왔다). 수법만 훔치고 단어는 새로.]\n"
            + "\n".join(lines) + "\n")


def _build_prompt(job, seed=0):
    struct = job.get("script_structure") or {}
    head = (job.get("headcopy") or {}).get("text") or ""
    return _PROMPT.format(
        script=job.get("given_script") or "",
        structure=json.dumps(struct, ensure_ascii=False, indent=1),
        headcopy=head,
        bank=_bank_block(seed),
    )


def generate(job, seed=0):
    """key_vault 캐스케이드로 썸네일 제목 후보 리스트를 생성. 소진키는 마킹하고 다음 키로.
    무키·전부실패면 None(호출부가 502로 돌려준다).

    seed: 참고 훅 조각을 회전시킨다(다시 누르면 다른 각도의 후보가 나오게). 같은 seed면 같은 조각
    — 난수를 쓰지 않는 이유는 script_engine과 같다(재현성)."""
    keys = key_vault.get_live_keys_cascade(_GEN_GROUP)
    if not keys:
        return None
    prompt = _build_prompt(job, seed=seed)
    for key in keys:
        try:
            resp = key_vault.get_client_for_key(key).models.generate_content(
                model=_MODEL, contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=_SCHEMA),
            )
            data = json.loads(resp.text)
            return data.get("titles") or []
        except Exception as e:  # noqa: BLE001 — 생성 실패는 치명적 아님
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                key_vault.mark_exhausted(key_vault._owner_group(key) or _GEN_GROUP, key)
                continue
            if key_vault.is_quota_error(e):
                continue  # 순간 rate limit — 다음 키로
            return None
    return None
