"""비트+카테고리 → 리모션 효과 배치 플랜(FullReel props). 순수 모듈.
규칙 1차 + (Task3) Haiku 2차. 렌더·DB를 모른다."""
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
        if _LIST.search(t):
            fx.append({"s": b["s"] + 0.1, "e": b["e"], "comp": "list",
                       "props": {"title": "LIST", "items": [], "position": "bottom"}})
            continue
        mi = _IMPACT.search(t)
        if mi:
            fx.append({"s": b["s"] + 0.2, "e": b["e"], "comp": "impact",
                       "props": {"word": mi.group(0) + "!", "position": "top"}})
    return fx


def build_plan(beats, category, video_src, dur_frames, fx=None):
    return {
        "videoSrc": video_src,
        "durationInFrames": int(dur_frames),
        "themeName": theme_for(category),
        "sections": [{"s": beats[0]["s"], "e": beats[-1]["e"], "label": "STEP 01"}] if beats else [],
        "beats": [{"s": b["s"], "e": b["e"], "cap": b.get("text", "")} for b in beats],
        "fx": match_rules(beats) if fx is None else fx,
    }
