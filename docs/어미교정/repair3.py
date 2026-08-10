# -*- coding: utf-8 -*-
"""3차 교정 — 사장님 2차 피드백(2026-08-05) 반영.

받은 지적 4개:
 ① "~더라구요, 글쎄" 어색 → 내가 2차 프롬프트에 예시로 넣은 게 원인. 제거.
 ② CTA 진입: 마무리를 '~합니다'로 닫지 말고 명사로 넘겨라
    "청소 한 번으로 한 달간 깨끗하게 만드는 **이것!** 댓글에~"
 ③ 화면 지목: "업체 없이 셀프로 청소했는데 묵은 때가 없어진 것 **보세요!**"
 ④ ★장점 나열 금지: "~해요 ~됩니다" 한 줄에 하나씩 = 밋밋.
    "OO도 이렇게 되고 OO까지 되는 게 정말 놀랍다" / "와~ 이 정도면"
    → 장점 여러 개를 한 문장에 몰고 끝에서 감탄으로 받는다.

★2차의 실패도 같이 고친다: 대안 목록에 '더라' 계열을 넣었더니 16→30으로 늘었다.
  이번엔 대안 목록에서 '더라' 계열을 전부 뺀다(금지하면서 예시로 주면 예시가 이긴다).
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

아래 대본들은 2차 교정까지 거쳤다. 실제 운영자가 읽어보고 준 피드백을 반영해
3차 교정을 한다. 피드백은 어미 목록이 아니라 **문장 구조**에 관한 것이다.

[피드백 ① — 장점을 한 줄에 하나씩 나열하지 마라 ★가장 중요]
지금은 이렇게 밋밋하다:
   "찌든 탄 자국도 스팀 한 번에 닦여요."
   "인덕션 틈새 오염도 완벽히 제거됩니다."
   "화장실 곰팡이도 자극 없이 지워져요."
   → '~해요 / ~됩니다'가 한 줄에 하나씩. 읽으면 광고판이다.

이렇게 바꿔라 — **장점 여러 개를 한 문장에 몰아넣고 끝에서 감탄으로 받는다**:
   "탄 자국도 이렇게 벗겨지고 인덕션 틈새까지 닦이는 게 정말 놀랍죠."
   "와~ 이 정도면 곰팡이든 기름때든 못 지울 게 없겠는데요."
   "묵은 때도 사라지고 살균까지 되는 걸 보니 손이 편해지겠더라니까요."
문장이 길어지면서 자연히 이어지고, 어미는 감탄 하나로 끝난다.
매 문장 이렇게 하라는 게 아니라, **장점이 3개 이상 이어지는 구간**에서 이렇게 묶어라.

[피드백 ② — 마무리를 닫지 말고 CTA로 넘겨라]
지금은 마무리를 '~변합니다'로 딱 닫은 뒤 CTA가 뜬금없이 시작한다.
운영자 제안:
   "청소 한 번으로 한 달간 깨끗하게 만드는 **이것!** 댓글에 '청소' 남겨주시면~"
→ 마지막 정리 문장을 **명사로 끊어 던지고**(이것! / 이 제품! / 그 비결!) 곧바로
  CTA로 이으면 한 호흡이 된다. 40개 중 몇 개는 이 형태로 만들어라(전부는 말고).

[피드백 ③ — 화면을 지목해라]
   "업체 없이 셀프로 청소했는데 묵은 때가 없어진 것 **보세요!**"
   "독한 세제 대신 뜨거운 스팀이면 충분하네요!"
→ 이건 화면에 붙는 대본이다. 말이 화면을 가리키면 컷이 안 어긋난다.
  시연·변화가 나오는 자리엔 '보세요/보이시죠/이거 보이세요' 같은 지목을 섞어라.

[피드백 ④ — "~더라구요, 글쎄"는 어색하다]
문장 끝에 '글쎄'를 붙이지 마라. 한국어에서 '글쎄'는 문장 앞에 온다. 전부 제거.

[유지할 것 — 앞 단계에서 이미 맞춘 것들]
- 내용·사실·순서 변경 금지. 없는 효능·가격 추가 금지.
- 같은 어미를 연달아 두 번 쓰지 마라.
- ★"~더라고요/~더라구요" 계열은 대본 전체에서 **최대 1번**.
- "~것 같아요" 최대 1번, "~거 있죠?" 최대 1번.
- CTA를 전부 "보내드릴게요"로 끝내지 마라(알려/챙겨/공유해/정리해서/바로 드릴게요 등).
- 상투어 금지: 꿀템·갓성비·완벽 해결·삶의 질·필수템·역대급.
- ★길이는 원본(before)과 비슷하게(±15%). 지금 2배까지 부푼 게 있다 — 절대 늘리지 마라.
- 비문 금지(예: "발견해봤거든요"는 틀렸다, "발견했거든요"가 맞다).

[교정할 대본 {count}개]
{targets}

[출력]
JSON만. 각 대본마다:
- job_id: 그대로
- after3: 3차 교정 전문
- techniques: 이 대본에 실제로 쓴 기법 배열
  (가능값: "장점묶음감탄", "명사끊기CTA", "화면지목", "여운", "확인요구")
- changed: 2차 대비 뭘 바꿨는지 한 줄
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
                    "after3": {"type": "string"},
                    "techniques": {"type": "array", "items": {"type": "string"}},
                    "changed": {"type": "string"},
                },
                "required": ["job_id", "after3", "techniques", "changed"],
            },
        }
    },
    "required": ["pairs"],
}


def main():
    pairs = json.load(open(os.path.join(SCRATCH, "script_pairs2.json"), encoding="utf-8"))
    dst = os.path.join(SCRATCH, "script_pairs3.json")
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
            f"[{p['job_id']}]\n원본(before): {p['before']}\n2차교정: {p['after2']}"
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
        b = src.get(g["job_id"], {})
        out.append({"job_id": g["job_id"], "before": b.get("before", ""),
                    "after2": b.get("after2", ""), "after3": g["after3"],
                    "techniques": g["techniques"], "changed": g["changed"]})
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n[완료] 총 {len(out)}쌍 (이번 +{len(fresh)}) → {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
