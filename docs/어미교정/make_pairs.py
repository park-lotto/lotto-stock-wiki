# -*- coding: utf-8 -*-
"""우리 실제 대본(서버 40개)을 before로 놓고, 어미·문장연결을 살린 after를 만든다.
사장님이 손본 bb9db3a5f759 한 쌍을 유일한 기준점(few-shot)으로 준다.
목적: 프롬프트에 박을 예시를 대량 확보 — 헷갈리지 않게 우리 소재로만.
"""
import io
import json
import os
import sys
import time

sys.path.insert(0, r"C:\Users\CH\Desktop\로또의 주식")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv(r"C:\Users\CH\Desktop\로또의 주식\.env", override=False)
from google import genai
from google.genai import types

MODEL = "gemini-3.5-flash"
_FALLBACK = "gemini-3.1-flash-lite"
SCRATCH = r"C:\Users\CH\AppData\Local\Temp\claude\C--Users-CH-Desktop-------\a2d5d291-265d-4f38-a840-e1cd5f8224bc\scratchpad"

# ── 유일한 기준점: 사장님이 실제로 손본 한 쌍 ─────────────────────────────
GOLD_BEFORE = """여러분 가전 청소할 때 이거 꼭 넣으세요. / 다이소에서 산 이 세정제로 싹 닦아봤죠. /
오래된 가전도 새것처럼 빛나더라고요. / 거울에 지문 하나 남지 않게 깔끔했죠. /
근데 이게 대박인 게 방수 코팅까지 돼요. / 물기가 굴러가 관리 쉬워요 /
청소 한번으로 한 달간 깨끗 / 가전이 새 제품처럼 변하는 비결이죠. /
댓글에 '청소' 남겨주시면 제품 정보 드릴게요."""

GOLD_AFTER = """여러분 가전 청소할 때 이거 꼭 넣으세요. 다이소에서 산 이 세정제로 싹 닦아봤어요.
오래된 가전도 새것처럼 빛나는 거 있죠? 겨울에 지문 하나 남지 않게 깔끔해지는 것 같아요.
근데 이게 대박인 게 방수코팅까지 된다는 거예요. 특히 물기 관리까지 쉽다니..
청소 한 번으로 한 달간 깨끗하게 가전제품이 새 제품처럼 변합니다.
댓글에 '청소' 남겨주시면 저렴하게 사실 수 있는 제품 정보 보내드릴게요."""

GOLD_DIFF = """이 한 쌍에서 사장님이 실제로 바꾼 것:
1) 어미 단조로움 해소 — '빛나더라고요/깔끔했죠'(둘 다 평서 단정)를
   '빛나는 거 있죠?'(확인요구) + '깔끔해지는 것 같아요'(완곡추측)로 갈랐다.
   같은 기능의 어미를 연달아 쓰지 않는다.
2) 문장 이어붙이기 — '물기가 굴러가 관리 쉬워요'(뚝 끊김)를
   '특히 물기 관리까지 쉽다니..'로 바꿔 앞 문장의 놀람을 이어받게 했다.
3) 여운 — 말끝을 흐리는 자리('~다니..')를 한 군데 만들었다.
4) 명사 나열 제거 — '청소 한번으로 한 달간 깨끗'(서술어 없는 토막)을
   완결된 한 문장으로 폈다. 마무리는 '~변합니다'로 단정해 닫는다.
5) CTA에 명분 — '제품 정보 드릴게요' → '저렴하게 사실 수 있는 제품 정보'

즉 핵심은 두 개다: ★어미의 기능을 매 문장 다르게 굴릴 것,
★토막 문장을 이어서 흐르게 할 것."""

PROMPT_TMPL = """너는 한국 쇼핑 숏폼 대본의 **말맛 교정 전문가**다.

우리 자동 대본 생성기가 뽑은 대본은 어미가 단조롭다 —
'~더라고요 / ~돼요 / ~죠 / ~어요'만 돌려쓰고, 한 문장씩 뚝뚝 끊어 써서
광고 문구처럼 들린다. (원인: 부품은행에 '~더라고요' 계열이 203회로 몰려 있다)

[기준점 — 사장님이 실제로 손본 유일한 정답 쌍]
BEFORE:
{gold_before}

AFTER:
{gold_after}

{gold_diff}

[교정 규칙]
- 내용·사실·순서는 **절대 바꾸지 마라**. 없는 효능·가격·상황을 추가하지 마라.
  화면에 붙는 대본이라 사건이 바뀌면 장면이 어긋난다.
- 어미의 **기능**을 매 문장 다르게 굴려라: 권유 / 경험담 / 확인요구 / 완곡추측 /
  발견제시 / 여운 / 단정 / 약속. 같은 기능을 연달아 두 번 쓰지 마라.
- ★'~더라고요' 계열은 **대본 전체에서 최대 1번**. 이미 은행에 과포화됐다.
- 토막 문장(서술어 없이 끊긴 것)은 완결된 문장으로 펴라.
- 문장이 각자 놀지 않게 이어라 — 근데 / 심지어 / 그러다 / ~니까 / ~더니 등.
- 말끝을 흐리는 여운을 한 군데만 둬라(매 문장 금지).
- 마무리 한 문장은 단정으로 닫고, CTA는 명분 한 줄 + "댓글에 'OO' 남겨주시면 ~
  보내드릴게요".
- 상투어 금지: 꿀템·갓성비·완벽 해결·삶의 질 상승·필수템.
- 글자수는 BEFORE와 비슷하게(±15%). 늘려서 채우지 마라.

[교정할 우리 대본 {count}개]
{targets}

[출력]
JSON만. 각 대본마다:
- job_id: 그대로
- diagnosis: 이 대본의 말맛 문제 한 줄 (어미가 뭐로 몰렸는지 구체적으로)
- after: 교정한 대본 전문 (문장들을 공백으로 이어 한 덩어리로)
- ending_map: after의 각 문장이 쓴 어미 기능을 순서대로 나열한 배열
  (예: ["권유","경험담","확인요구","완곡추측","발견제시","여운","단정","약속"])
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "pairs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "diagnosis": {"type": "string"},
                    "after": {"type": "string"},
                    "ending_map": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["job_id", "diagnosis", "after", "ending_map"],
            },
        }
    },
    "required": ["pairs"],
}


def main():
    src = json.load(open(os.path.join(SCRATCH, "remote_scripts.json"), encoding="utf-8"))
    mix = src.get("mix", [])
    # before 텍스트 조립(비트를 ' / '로 이어 원래의 끊김이 보이게)
    items = []
    for m in mix:
        before = " / ".join(b["narration"].strip() for b in m["beats"])
        if len(before) < 80:
            continue
        items.append({"job_id": m["job_id"], "before": before})
    # 이어받기 — 이미 만든 쌍은 건너뛴다(503으로 중간에 끊겨도 재실행하면 나머지만).
    dst = os.path.join(SCRATCH, "script_pairs.json")
    done = []
    if os.path.exists(dst):
        try:
            done = json.load(open(dst, encoding="utf-8"))
        except Exception:
            done = []
    have = {d["job_id"] for d in done}
    items = [it for it in items if it["job_id"] not in have]
    print(f"[대상] 남은 {len(items)}개 (기존 {len(done)}쌍 보존)", flush=True)

    key = os.environ.get("GEMINI_API_KEY", "")
    client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=180_000))

    BATCH = 8
    all_pairs = []
    for i in range(0, len(items), BATCH):
        chunk = items[i:i + BATCH]
        targets = "\n\n".join(
            f"[{it['job_id']}]\n{it['before']}" for it in chunk)
        prompt = PROMPT_TMPL.format(
            gold_before=GOLD_BEFORE, gold_after=GOLD_AFTER, gold_diff=GOLD_DIFF,
            count=len(chunk), targets=targets)
        # 3.5-flash가 503으로 몰릴 때 3.1-flash-lite는 정상인 사례가 있다
        # (script_extract.py:350 실측). 모델 폴백 + 지수 백오프로 배치를 살린다.
        got = None
        for attempt, model in enumerate(
                [MODEL, MODEL, _FALLBACK, _FALLBACK, _FALLBACK]):
            try:
                resp = client.models.generate_content(
                    model=model, contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=SCHEMA, temperature=0.95))
                got = json.loads(resp.text).get("pairs", [])
                print(f"[배치 {i//BATCH + 1}] {len(got)}쌍 ({model})", flush=True)
                break
            except Exception as e:
                print(f"  [재시도 {attempt+1}/{5} {model}] {str(e)[:90]}", flush=True)
                time.sleep(5 * (attempt + 1))
        if got:
            all_pairs.extend(got)
        else:
            print(f"[배치 {i//BATCH + 1} 포기]", flush=True)
        time.sleep(2)

    bymap = {it["job_id"]: it["before"] for it in items}
    out = list(done) + [
        {"job_id": p["job_id"], "before": bymap.get(p["job_id"], ""),
         "after": p["after"], "diagnosis": p["diagnosis"],
         "ending_map": p["ending_map"]} for p in all_pairs]
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n[완료] 총 {len(out)}쌍 (이번 +{len(all_pairs)}) → {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
