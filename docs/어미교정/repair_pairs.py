# -*- coding: utf-8 -*-
"""2차 교정 — 1차 after의 '러프 복사' 쏠림을 푼다.

1차 실측: 40쌍 중 ~것 같아요 21회 / ~거 있죠 18회 / 보내드릴게요 37회.
원인은 기준점(사장님 러프)이 하나뿐이라 그 표현을 전부 베낀 것.
→ 이번엔 그 3표현을 대본당 최대 1회로 제한하고, 어미 기능은 유지한 채
  **표면형을 다르게** 굴리게 한다. 내용은 여전히 불변.
"""
import io
import json
import os
import re
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv(r"C:\Users\CH\Desktop\로또의 주식\.env", override=False)
from google import genai
from google.genai import types

MODEL = "gemini-3.5-flash"
_FALLBACK = "gemini-3.1-flash-lite"
SCRATCH = r"C:\Users\CH\AppData\Local\Temp\claude\C--Users-CH-Desktop-------\a2d5d291-265d-4f38-a840-e1cd5f8224bc\scratchpad"

PROMPT_TMPL = """너는 한국 쇼핑 숏폼 대본의 **말맛 교정 전문가**다.

아래 대본들은 1차 교정을 이미 거쳤다. 어미의 '기능'은 잘 굴러가는데,
**표면형이 40개 대본에서 전부 똑같이 나왔다**. 실측 결과:
  - "~것 같아요"  21회
  - "~거 있죠?"   18회
  - "보내드릴게요" 37회 (CTA 전부)
기준 예시 하나를 그대로 베낀 결과다. 이번엔 그걸 푼다.

[이번 교정의 목표 — 딱 하나]
어미의 **기능 흐름은 그대로 두고, 표면형만 다르게** 굴려라.
같은 기능이라도 한국어 구어에는 표현이 훨씬 많다.

  · 확인요구: ~거 있죠? / ~잖아요 / ~더라니까요 / ~아니겠어요? / ~있지 뭐예요 /
             ~지 않나요? / ~더라구요, 글쎄 / ~어떻겠어요
  · 완곡추측: ~것 같아요 / ~싶더라고요 / ~더라니까 / ~인가 봐요 / ~듯해요 /
             ~기도 하고요 / ~느낌이에요
  · 경험담:   ~했어요 / ~해봤거든요 / ~하는 중이에요 / ~해왔어요 / ~하고 있어요
  · 발견제시: ~라는 거예요 / ~더라고요 / ~지 뭐예요 / ~이더라구요 / ~라니까요
  · 여운:     ~다니.. / ~더라니.. / ~할 정도예요 / ~말도 안 되죠 / ~싶을 만큼
  · 약속(CTA): 보내드릴게요 / 알려드릴게요 / 챙겨드릴게요 / 바로 드릴게요 /
             공유해드릴게요 / 살짝 풀어드릴게요 / 정리해서 드릴게요

★제한 (이게 이번 교정의 핵심이다):
  - "~것 같아요"는 대본당 **최대 1번**
  - "~거 있죠?"는 대본당 **최대 1번**
  - CTA를 전부 "보내드릴게요"로 끝내지 마라 — 대본마다 다른 걸로 골라라
  - "~더라고요" 계열도 여전히 대본당 최대 1번

[그대로 지킬 것 — 1차에서 이미 맞춘 것들이니 깨지 마라]
- 내용·사실·순서 변경 금지. 없는 효능·가격 추가 금지.
- 어미 기능을 매 문장 다르게(같은 기능 연달아 두 번 금지).
- 토막 문장은 완결 문장으로, 문장끼리 이어지게(근데/심지어/그러다/~니까/~더니).
- 여운은 한 군데만.
- 상투어 금지: 꿀템·갓성비·완벽 해결·삶의 질·필수템·역대급.
- ★길이는 원본과 비슷하게(±15%). 1차에서 2배까지 부푼 게 있었다 — 늘리지 마라.
- 어색한 조합 금지(예: "신기한 효과더군요" 같은 비문).

[교정할 대본 {count}개]
{targets}

[출력]
JSON만. 각 대본마다: job_id(그대로) / after2(2차 교정 전문) /
ending_map2(각 문장의 어미 기능 순서) / changed(1차 대비 뭘 바꿨는지 한 줄)
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
                    "after2": {"type": "string"},
                    "ending_map2": {"type": "array", "items": {"type": "string"}},
                    "changed": {"type": "string"},
                },
                "required": ["job_id", "after2", "ending_map2", "changed"],
            },
        }
    },
    "required": ["pairs"],
}

CLICHE = ["꿀템", "갓성비", "완벽 해결", "삶의 질", "필수템", "역대급"]
DEORA = re.compile(r"더라[고구]요")


def main():
    pairs = json.load(open(os.path.join(SCRATCH, "script_pairs.json"), encoding="utf-8"))
    # 1차에서 길이 이탈/상투어가 있던 것도 포함해 전부 재교정한다
    # (2차 프롬프트가 길이·상투어 제약을 다시 걸므로 여기서 구제된다).
    dst = os.path.join(SCRATCH, "script_pairs2.json")
    done = []
    if os.path.exists(dst):
        try:
            done = json.load(open(dst, encoding="utf-8"))
        except Exception:
            done = []
    have = {d["job_id"] for d in done}
    todo = [p for p in pairs if p["job_id"] not in have]
    print(f"[대상] 남은 {len(todo)}개 (기존 {len(done)}쌍 보존)", flush=True)

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""),
                          http_options=types.HttpOptions(timeout=180_000))
    BATCH = 8
    fresh = []
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        targets = "\n\n".join(
            f"[{p['job_id']}]\n원본(before): {p['before']}\n1차교정(after): {p['after']}"
            for p in chunk)
        prompt = PROMPT_TMPL.format(count=len(chunk), targets=targets)
        got = None
        for attempt, model in enumerate([MODEL, MODEL, _FALLBACK, _FALLBACK, _FALLBACK]):
            try:
                resp = client.models.generate_content(
                    model=model, contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=SCHEMA, temperature=1.0))
                got = json.loads(resp.text).get("pairs", [])
                print(f"[배치 {i//BATCH + 1}] {len(got)}쌍 ({model})", flush=True)
                break
            except Exception as e:
                print(f"  [재시도 {attempt+1}/5 {model}] {str(e)[:90]}", flush=True)
                time.sleep(5 * (attempt + 1))
        if got:
            fresh.extend(got)
        else:
            print(f"[배치 {i//BATCH + 1} 포기]", flush=True)
        time.sleep(2)

    src = {p["job_id"]: p for p in pairs}
    out = list(done)
    for g in fresh:
        base = src.get(g["job_id"], {})
        out.append({"job_id": g["job_id"], "before": base.get("before", ""),
                    "after1": base.get("after", ""), "after2": g["after2"],
                    "ending_map2": g["ending_map2"], "changed": g["changed"],
                    "diagnosis": base.get("diagnosis", "")})
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n[완료] 총 {len(out)}쌍 (이번 +{len(fresh)}) → {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
