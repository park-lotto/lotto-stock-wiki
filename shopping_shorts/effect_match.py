"""비트+카테고리 → 리모션 효과 배치 플랜(FullReel props). 순수 모듈.
규칙 1차 + (Task3) Haiku 2차. 렌더·DB를 모른다."""
import json
import re

EFFECT_CATALOG = [
    {"key": "count",   "needs": ["value", "suffix", "label"], "desc": "숫자 카운트업(가격·시간·개수)"},
    {"key": "list",    "needs": ["title", "items"],           "desc": "항목 리스트 순차 리빌"},
    {"key": "impact",  "needs": ["word"],                     "desc": "강조어 슬램"},
    {"key": "callout", "needs": ["icon", "name", "tag"],      "desc": "아이콘+이름+태그 카드"},
]

_THEME = {"레시피": "warm", "홈템": "warm", "주식": "tech", "데이터": "tech"}


def theme_for(category):
    return _THEME.get((category or "").strip(), "warm")


_NUM = re.compile(r"(\d+)\s*(분|초|원|개|인분|칼로리|kcal)")
_LIST = re.compile(r"(\d+)\s*가지|재료")
_IMPACT = re.compile(r"대박|진짜|완전|폭발|최고|미쳤|역대급")


def match_rules(beats):
    fx = []
    for b in beats:
        t = b.get("text", "")
        m = _NUM.search(t)
        if m:
            fx.append({"s": b["s"] + 0.1, "e": b["e"], "comp": "count",
                       "props": {"label": "POINT", "value": int(m.group(1)),
                                 "suffix": m.group(2), "position": "top"}})
            continue
        # list 효과는 items를 채울 소스(나레이션→항목 추출)가 아직 없다. 규칙으로 발동시키면
        # items=[]인 **빈 카드**가 렌더돼 유료 사용자에게 고장으로 보인다(최종리뷰 I-1).
        # ListReveal 컴포넌트·_LIST 정규식은 남겨두고, 항목 추출이 붙으면 여기서 재활성한다.
        # if _LIST.search(t): ...(items 채운 뒤)
        mi = _IMPACT.search(t)
        if mi:
            fx.append({"s": b["s"] + 0.2, "e": b["e"], "comp": "impact",
                       "props": {"word": mi.group(0) + "!", "position": "top"}})
    return fx


_LLM_PROMPT = (
    "다음 릴스 비트에서, 규칙이 못 잡은 훅/감정절정/CTA 비트에만 효과를 추천해라. "
    "impact(강조어)와 callout(아이콘+이름+태그)만. 실제 대사 단어만 써라. "
    'JSON만: {"extra":[{"beat":인덱스,"comp":"impact|callout","props":{...}}]}'
)


def _llm_extra(beats, client):
    body = "\n".join(f'{i}: {b.get("text","")}' for i, b in enumerate(beats))
    resp = client.models.generate_content(
        # gemini-2.5-flash는 신규 키에 404다("no longer available to new users",
        # 2026-07-29 서버 실측). suggest()가 예외를 조용히 삼키므로(무과금 폴백)
        # 여기 모델명이 낡으면 LLM 효과 추천이 매번 0건인 채 아무도 모른다.
        model="gemini-3.1-flash-lite",
        contents=[_LLM_PROMPT + "\n" + body],
        config={"response_mime_type": "application/json"},
    )
    data = json.loads(resp.text)
    out = []
    for e in data.get("extra", []):
        b = beats[int(e["beat"])]
        out.append({"s": b["s"] + 0.15, "e": b["e"], "comp": e["comp"], "props": e.get("props", {})})
    return out


def suggest(beats, category, video_src, dur_frames, client=None):
    fx = match_rules(beats)
    if client is not None:
        try:
            fx = fx + _llm_extra(beats, client)
        except Exception:
            pass  # 폴백: 규칙 결과 유지(무과금)
    fx.sort(key=lambda f: f["s"])
    return build_plan(beats, category, video_src, dur_frames, fx=fx)


def build_plan(beats, category, video_src, dur_frames, fx=None):
    return {
        "videoSrc": video_src,
        "durationInFrames": int(dur_frames),
        "themeName": theme_for(category),
        "sections": [{"s": beats[0]["s"], "e": beats[-1]["e"], "label": "STEP 01"}] if beats else [],
        "beats": [{"s": b["s"], "e": b["e"], "cap": b.get("text", "")} for b in beats],
        "fx": match_rules(beats) if fx is None else fx,
    }
