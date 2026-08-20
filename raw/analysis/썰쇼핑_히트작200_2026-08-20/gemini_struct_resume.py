# -*- coding: utf-8 -*-
"""히트작 대본 Gemini 구조 분해 — **이어받기** 판 (2026-08-20).

## 왜 따로 만들었나

원본 `gemini_struct.py`는 `[:n]`으로 **앞에서부터** n편을 한다. 1차에서 31편까지 하고
키 한도(429)로 끊겼는데, 그대로 다시 돌리면 그 31편을 **또** 분해한다(키·시간 낭비).

그래서 이 판은:
  1. 기존 결과(`gemini_struct.json`)의 `video_id`를 읽어 **이미 한 것은 건너뛴다**
  2. 10편마다 **중간 저장**한다 — 429로 끊겨도 거기까지가 남는다(1차 때 이게 없어
     끊긴 뒤 결과를 다시 못 받을 뻔했다)
  3. 결과를 기존 것과 **병합**해 저장한다(덮어쓰지 않는다)

## 실행 (★서버에서 — 키가 /etc/shopping-shorts.env에만 있다)

    scp gemini_struct_resume.py hits_subs.json gemini_struct.json ubuntu@43.200.48.69:/tmp/
    ssh ... "cd /tmp && set -a && . /etc/shopping-shorts.env && set +a && \
             python3 gemini_struct_resume.py hits_subs.json 200"

윈도 콘솔 cp949 함정 때문에 결과는 파일로만 본다(README 함정 참조).
"""
import json, io, os, sys, time

sys.path.insert(0, '/home/ubuntu/lotto-stock-wiki')
from shopping_shorts import video_analysis
from shopping_shorts import comment_gen
from google.genai import types

OUT = 'gemini_struct.json'

SCHEMA = {
    "type": "object",
    "properties": {
        "spine": {"type": "string"},
        "product": {"type": "string"},
        "original_use": {"type": "string"},
        "uses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "what": {"type": "string"},
                    "scene": {"type": "string"},
                    "role": {"type": "string"},
                },
                "required": ["what", "scene", "role"],
            },
        },
        "hook_needs_scene": {"type": "boolean"},
        "beats": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["spine", "uses"],
}

PROMPT = """아래는 한국 쇼핑 쇼츠 히트작의 **자동자막 전사**다(오탈자가 있으니 문맥으로 읽어라).
이 대본이 어떤 구조인지 분해해라.

가장 중요한 것: **uses** - 이 대본이 보여주는 '용도'를 빠짐없이 나열해라.
  용도 하나 = 해외 원본 영상에서 **장면 하나**를 가져와야 하는 단위다.
  예) "코스트코 매직랩"이면: (1)강아지 발에 씌우기 (2)아이옷에 붙이기 (3)테이블에 붙이기
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


def _save(rows):
    io.open(OUT, 'w', encoding='utf-8').write(
        json.dumps(rows, ensure_ascii=False, indent=1))


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else 'hits_subs.json'
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    D = json.load(open(src, encoding='utf-8'))[:n]

    done = []
    if os.path.exists(OUT):
        try:
            done = json.load(open(OUT, encoding='utf-8')) or []
        except Exception as e:                      # 깨진 결과로 처음부터 다시 하지 않는다
            print('기존 결과를 못 읽었다(%s) — 백업 후 새로 시작' % str(e)[:60])
            os.rename(OUT, OUT + '.broken')
            done = []
    seen = {d.get('video_id') for d in done if d.get('video_id')}
    todo = [d for d in D if d.get('video_id') not in seen]
    print('표본 %d편 / 이미 함 %d편 / 남은 것 %d편' % (len(D), len(done), len(todo)))

    keys = getattr(video_analysis, 'SHORTS_GEMINI_KEYS', None)
    print('keys:', len(keys) if keys else 0)
    if not keys:
        print('NO_KEYS'); return
    if not todo:
        print('더 할 게 없다'); return

    out = list(done)
    ok = err = 0
    run429 = 0          # ★**연속** 429 횟수(누적이 아니다 — 1차판이 여기서 헛돌았다)
    for i, d in enumerate(todo):
        got = False
        # ★429는 대부분 **분당 한도**다. 실측(2026-08-20): 3연속 429로 멈춘 직후
        #   같은 키로 단발 호출을 하니 정상 응답했다 = 일일 소진이 아니었다.
        #   그래서 바로 포기하지 말고 물러섰다가 다시 친다(20s → 40s → 80s).
        for attempt in range(3):
            key, _ = comment_gen._next_live_key_and_idx()
            if key is None:
                print('  살아있는 키가 없다 at %d' % i); break
            try:
                r = analyze(d['full_text'], key)
                r['views'] = d['views']; r['channel'] = d['channel']
                r['video_id'] = d.get('video_id', ''); r['len'] = len(d['full_text'])
                out.append(r); ok += 1; got = True; run429 = 0
                break
            except Exception as e:
                msg = str(e)[:100]
                is429 = ('429' in msg or 'RESOURCE_EXHAUSTED' in msg)
                if is429 and attempt < 2:
                    back = 20 * (2 ** attempt)
                    print('  429 at %d — %d초 쉬고 재시도' % (i, back))
                    time.sleep(back)
                    continue
                err += 1
                print('  ERR %d %s' % (i, msg))
                if is429:
                    run429 += 1
                break
        if not got and run429 >= 5:
            # 물러서기까지 했는데 연속 5편이 429면 그때는 정말 한도다.
            print('  429가 연속 %d편 — 중단. 다시 돌리면 이어서 한다' % run429)
            break
        if (i + 1) % 10 == 0:
            _save(out)                               # ★중간 저장 — 끊겨도 남는다
            print('  ...%d/%d ok=%d err=%d (중간저장)' % (i + 1, len(todo), ok, err))
        time.sleep(1.0)     # 0.3초는 12키 라운드로빈에서도 분당 한도를 넘었다(실측)
    _save(out)
    print('완료: 총 %d편 (이번에 %d편 추가, 실패 %d)' % (len(out), ok, err))


main()
