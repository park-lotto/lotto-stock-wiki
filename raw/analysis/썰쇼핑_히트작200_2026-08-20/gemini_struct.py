# -*- coding: utf-8 -*-
"""히트작 대본을 Gemini로 구조 분해한다 - 패턴 테이블의 근거.

왜 Gemini인가: 문구 규칙으로는 용도 개수를 못 센다(실측 - 1,200만 영상이 실제 4개인데
규칙은 2개로 셌다). 자동자막은 오탈자가 많아 경계가 흐리다. 의미 판단은 의미를 아는
쪽에 맡긴다. 골격 판정은 규칙이 이미 정확하므로 그대로 두고 **용도/장면만** 묻는다.

비용: 텍스트만 보내므로 영상 태깅(0.679원)보다 훨씬 싸다.
"""
import json, io, os, sys, time

sys.path.insert(0, '/home/ubuntu/lotto-stock-wiki')
from shopping_shorts import video_analysis
from shopping_shorts import comment_gen
from google.genai import types

SCHEMA = {
    "type": "object",
    "properties": {
        "spine": {"type": "string"},          # 오용형/은폐형/권위자형/목격담형/나열형/기타
        "product": {"type": "string"},
        "original_use": {"type": "string"},   # 원래 용도(없으면 "")
        "uses": {                             # 이 대본이 보여주는 용도(=필요 장면) 목록
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "what": {"type": "string"},      # 무슨 용도인가(짧게)
                    "scene": {"type": "string"},     # 그때 화면에 필요한 장면
                    "role": {"type": "string"},      # 나열/클라이맥스/고조
                },
                "required": ["what", "scene", "role"],
            },
        },
        "hook_needs_scene": {"type": "boolean"},   # 훅 구간이 특정 장면을 요구하나
        "beats": {"type": "array", "items": {"type": "string"}},  # 대본 흐름 요약
    },
    "required": ["spine", "uses"],
}

PROMPT = """아래는 한국 쇼핑 쇼츠 히트작의 **자동자막 전사**다(오탈자가 있으니 문맥으로 읽어라).
이 대본이 어떤 구조인지 분해해라.

가장 중요한 것: **uses** - 이 대본이 보여주는 '용도'를 빠짐없이 나열해라.
  용도 하나 = 해외 원본 영상에서 **장면 하나**를 가져와야 하는 단위다.
  예) "코스트코 매직랩"이면: ①강아지 발에 씌우기 ②아이옷에 붙이기 ③테이블에 붙이기
  각 용도마다 scene에 **그 장면에 무엇이 보여야 하는지** 적어라(화면 지시문).
  role은 나열(앞부분 예시) / 클라이맥스(근데 미친 사용법은 따로) / 고조(심지어) 중 하나.

spine은 다음 중 하나:
  오용형    - 원래 용도가 있고 그걸 뒤집어 다른 용도로 쓴다
  은폐형    - 제품 정체를 숨겼다가 "이건 바로 ~"로 공개한다
  권위자형  - 정체를 안 숨기고 "개발자도 몰랐다"류로 시작해 장점을 보여준다
  목격담형  - 남의 집/지인에게서 발견한 썰
  나열형    - 여러 제품/방법을 순서대로 소개
  기타

original_use는 '원래 무엇을 하라고 만든 물건인가'(오용형만 있음, 없으면 빈 문자열).
hook_needs_scene은 훅 구간이 특정 장면을 꼭 요구하는지(제품샷 아무거나면 false).

JSON만 출력.

대본:
"""


def analyze(text, key):
    client = video_analysis._client_for_key(key)
    r = client.models.generate_content(
        model=video_analysis._TRANSLATE_MODEL,
        contents=[PROMPT + text],
        config=types.GenerateContentConfig(
            response_mime_type="application/json", response_schema=SCHEMA),
    )
    return json.loads(r.text)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else 'hits_subs.json'
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    D = json.load(open(src, encoding='utf-8'))[:n]
    keys = getattr(video_analysis, 'SHORTS_GEMINI_KEYS', None)
    print('keys:', len(keys) if keys else 0, '| 표본:', len(D))
    if not keys:
        print('NO_KEYS'); return
    out = []
    for i, d in enumerate(D):
        key, _ = comment_gen._next_live_key_and_idx()
        if key is None:
            print('  키 소진 at', i); break
        try:
            r = analyze(d['full_text'], key)
            r['views'] = d['views']; r['channel'] = d['channel']
            r['video_id'] = d.get('video_id', ''); r['len'] = len(d['full_text'])
            out.append(r)
        except Exception as e:
            print('  ERR', i, str(e)[:80])
        if (i + 1) % 10 == 0:
            print('  ...%d/%d ok=%d' % (i + 1, len(D), len(out)))
        time.sleep(0.3)
    io.open('gemini_struct.json', 'w', encoding='utf-8').write(
        json.dumps(out, ensure_ascii=False, indent=1))
    print('완료:', len(out))


main()
