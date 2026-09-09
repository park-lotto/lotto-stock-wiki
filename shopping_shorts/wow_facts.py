# -*- coding: utf-8 -*-
"""제품 카테고리 → **영상 밖의 신기한 정보**(wow_facts) 웹 보강 (2026-09-09).

## 왜 이 모듈이 필요한가 — 사장님이 짚은 빈 자리

사장님이 보여준 방식(유튜브 H3UG7cY-fTQ 21~26분)은 노가다 3단계였다:

    ① 영상 → 제품명·특징·타임코드 대본        ← 우리도 오늘 붙였다(insta_facts 프레임 입력)
    ② "이 아이템 관련 **신기한 정보**를 더 찾아줘"  ← ★이 모듈. 우리에겐 아예 없었다
    ③ 그걸로 대본                              ← 우리도 있다(스파인·script_gate)

②가 만든 문장이 그 대본의 알맹이였다:
    "소리를 빛처럼 귓구멍에만 쏘아주는 지향성 기술이라 옆 사람도 거의 못 듣는다는 거"
    "예전 골전도는 뼈를 직접 때려서 오래 끼면 멀미나 두통이 왔는데"

②가 없으면 대본은 **화면에 이미 보이는 것만 다시 말한다**. 시청자가 눈으로 본 걸
귀로 또 듣는다 — 사장님 말로 "사람들이 보게 해야 할 이유가 없어"가 그 상태다.
실측(2026-09-09): 대본 경로 전체에 웹검색 grounding이 **한 줄도 없었다**.

## 어디서 갈리나 (0순위-B — 다른 재료 모듈과 겹치지 않는다)

    product_facts : 쿠팡 상세·리뷰      — 이 **상품**이 왜 좋은가
    insta_facts   : 영상 전사 + 화면    — 이 **영상**이 보여준 것
    sul_facts     : 유튜브 썰 자막      — 원래 용도 / 엉뚱한 사용처
    wow_facts     : 웹                  — 이 **카테고리**에 대해 영상 밖에 있는 지식  ← 여기

앞의 셋은 전부 "영상·상품 안"을 본다. 이 모듈만 밖을 본다. 그래서 따로다.

## 지켜야 할 것

★**fail-open** — 못 찾으면 []. 대본은 종전대로 나온다(회귀 0).
★**캐시 필수** — 실측에서 키 4개가 연속 429였다. 카테고리 단위로 캐시하면
  같은 종류 제품이 다시 와도 안 때린다(제품명이 아니라 **카테고리**로 캐시하는 이유).
★**지어낸 사실은 대본에 박히면 거짓말이 된다** — 웹 grounding을 켜서 묻고,
  훅과 근거를 갈라 받는다. 근거가 비면 그 항목은 버린다.
"""
import json
import re

_MODEL = "gemini-3.1-flash-lite"

# 몇 개를 받나. 3개면 대본 한 편에서 1~2개를 쓰고도 고를 여지가 남는다.
WOW_N = 3

WOW_PROMPT = """'{subject}' 제품으로 한국어 쇼핑 숏폼을 만든다.

이 **카테고리**에 대해 시청자가 모르는 신기한 사실 {n}개를 웹에서 찾아라.

★스펙 나열은 쓸모없다 — 그건 화면에 이미 보인다. 시청자가 듣는 순간
  "어? 그래?" 하는 것만 골라라: 작동 **원리**, 옛날 방식과의 **비교**,
  의외의 **역사**, 흔한 **오해를 깨는 사실**.
★영상에 안 나온 지식이어야 한다. 화면에 보이는 걸 다시 말하면 실패다.
★한국어로. 대본 문장에 그대로 끼울 수 있게 **입말**로 써라.
★확인 안 되는 건 넣지 마라. {n}개를 못 채우면 적게 줘도 된다.

JSON 배열만 출력하라. 다른 말 붙이지 마라:
[{{"hook": "듣는 순간 어? 하는 한 줄", "why": "왜 그런지 한두 줄"}}]"""


def _say(log, msg):
    try:
        log(msg)
    except Exception:      # noqa: BLE001 — 로그가 재료 추출을 막지 않는다
        pass


def _parse(text):
    """모델 출력 → [{hook, why}]. 웹검색을 켜면 response_schema를 못 쓴다(제미니 제약)
    — 그래서 여기서 직접 판다. 코드펜스·앞뒤 설명이 붙어 와도 배열만 건져낸다."""
    if not text:
        return []
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return []
    out = []
    for x in data if isinstance(data, list) else []:
        if not isinstance(x, dict):
            continue
        hook = str(x.get("hook") or "").strip()
        why = str(x.get("why") or "").strip()
        # ★근거 없는 훅은 버린다 — 근거가 없으면 그건 지어낸 것이다.
        if hook and why:
            out.append({"hook": hook, "why": why})
    return out[:WOW_N]


def find(subject, *, n=WOW_N, log=print, _call=None):
    """제품·카테고리 이름 → [{hook, why}]. 못 찾으면 [](예외 없음).

    _call은 테스트 주입용 — (prompt) -> 응답 텍스트.
    """
    subject = (subject or "").strip()
    if not subject:
        return []
    prompt = WOW_PROMPT.format(subject=subject, n=n)
    if _call is not None:
        try:
            return _parse(_call(prompt))
        except Exception as e:      # noqa: BLE001 — 주입 호출이 죽어도 대본은 나온다
            _say(log, "[wow_facts] 주입 호출 실패: %s" % str(e)[:100])
            return []

    try:
        from shopping_shorts import video_analysis, comment_gen
        from google.genai import types
    except Exception as e:          # noqa: BLE001
        _say(log, "[wow_facts] 모듈 import 실패 — %s" % str(e)[:100])
        return []

    # ★키를 돌려 가며 재시도한다 — 실측(2026-09-09)에서 **4개 연속 429**였고
    #   5번째에 성공했다. 한 번 때리고 포기하면 이 단계는 대부분 빈손이 된다.
    last = ""
    for i in range(6):
        try:
            key, _idx = comment_gen._next_live_key_and_idx()
            if key is None:
                _say(log, "[wow_facts] 살아있는 키 없음")
                return []
            resp = video_analysis._client_for_key(key).models.generate_content(
                model=_MODEL, contents=[prompt],
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]))
            got = _parse(resp.text)
            if got:
                _say(log, "[wow_facts] '%s' → %d개 (키 %d번째 시도)" % (subject, len(got), i + 1))
                return got
            last = "빈 결과"
        except Exception as e:      # noqa: BLE001 — 웹 보강 실패가 대본을 막으면 안 된다
            last = "%s: %s" % (type(e).__name__, str(e)[:70])
    _say(log, "[wow_facts] '%s' 못 찾음 — %s" % (subject, last))
    return []


def wow_prompt_block(wows, max_items=WOW_N):
    """재료 → 대본 프롬프트에 붙일 블록. 비면 ''(호출부는 빈 문자열이면 회귀 0).

    ★product_facts.prompt_block·insta_facts.insta_prompt_block과 같은 규약이다.
    """
    if not wows:
        return ""
    lines = ["[영상 밖에서 찾은 사실 — 시청자가 모르는 것]",
             "★이 중 **하나만** 골라 대본 가운데에 넣어라. 나열하지 마라.",
             "★화면에 안 보이는 얘기다 — 그래서 시청자가 끝까지 보는 이유가 된다."]
    for w in (wows or [])[:max_items]:
        lines.append("- %s (근거: %s)" % (w.get("hook", ""), w.get("why", "")))
    return "\n".join(lines) + "\n"
