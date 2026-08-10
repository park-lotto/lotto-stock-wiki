# -*- coding: utf-8 -*-
"""4차 교정 — 3차에서 새로 생긴 결함 3개 + 길이 이탈을 잡는다 (README ⏭ 그대로).

 ① ★명사끊기가 CTA '뒤'에 붙어 문장이 미완성으로 끝남 (25·27·28·29·31번)
    잘못: "댓글에 '김밥' 남겨주세요. 그 비법!"
    맞음: "하루 종일 쫀득한 김밥을 만드는 그 비법! 댓글에 '김밥' 남겨주세요."
 ② 마크다운 별표(**)가 본문에 복사됨 (34·36·40번) — 프롬프트 예시에서 ** 제거
    + 후처리로도 벗긴다(TTS가 "별별"로 읽는다).
 ③ "보이시죠" 14회로 굳음 — 화면 지목 표현을 흩는다.
 ④ 길이 이탈(0.80~1.30 밖) — 전체 재교정이 아니라 이탈분만 2회까지 재요청.

경로는 스크립트 폴더 기준(집/회사 PC 공용). 데이터도 이 폴더의 script_pairs3.json.
"""
import io
import json
import os
import re
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"), override=False)
from google import genai
from google.genai import types

MODEL = "gemini-3.5-flash"
_FALLBACK = "gemini-3.1-flash-lite"

PROMPT_TMPL = """너는 한국 쇼핑 숏폼 대본의 **말맛 교정 전문가**다.

아래 대본들은 3차 교정까지 거쳤고 전반적인 결은 좋다. 4차는 **크게 다시 쓰는 게 아니라**
3차에서 새로 생긴 결함만 정밀하게 고치는 단계다. 문제없는 문장은 그대로 둬라.

[결함 ① — 명사끊기는 반드시 CTA '앞'에 온다 ★가장 중요]
잘못(문장이 미완성으로 끝난다): "댓글에 '김밥' 남겨주세요. 그 비법!"
맞음: "하루 종일 쫀득한 김밥을 만드는 그 비법! 댓글에 '김밥' 남겨주세요."
→ 명사로 끊어 던지는 문장(이것! / 그 비법! / 이 제품!)이 CTA 문장 뒤에 있으면
  앞으로 옮겨 자연스럽게 이어라. 대본은 CTA로 끝나야 한다.

[결함 ② — 별표 금지]
본문에 별표(＊, *)를 절대 쓰지 마라. 강조 표기가 아니라 글자 그대로 읽힌다.
"이 제품!" 처럼 문장부호만으로 강조해라. 있으면 전부 벗겨라.

[결함 ③ — 화면 지목 표현이 "보이시죠"로 굳었다]
같은 대본에서 "보이시죠"를 두 번 이상 쓰지 마라. 대본들 사이에서도 흩어라:
보세요 / 저거 보이세요? / 화면 보세요 / 이거 좀 보세요 / 여기 보이죠? / 지금 이 장면요.
지목 자체를 없애지는 마라 — 표현만 바꾼다.

[길이 — 원본(before)의 0.85~1.25배 안]
지금 몇 개가 0.73~1.44배까지 이탈했다. 짧으면 있는 내용을 조금 풀어 쓰고,
길면 군더더기를 줄여라. 내용·사실 추가 금지.

[유지할 것 — 앞 단계에서 이미 맞춘 것들. 되돌리지 마라]
- 내용·사실·순서 변경 금지. 없는 효능·가격 추가 금지.
- 같은 어미 연속 2회 금지.
- "~더라고요/~더라구요" 계열은 대본 전체에서 최대 1번.
- "~것 같아요" 최대 1번, "~거 있죠?" 최대 1번. 문미 "글쎄" 금지.
- CTA를 전부 "보내드릴게요"로 끝내지 마라.
- 상투어 금지: 꿀템·갓성비·완벽 해결·삶의 질·필수템·역대급.
- 장점묶음 감탄·화면 지목·명사끊기는 3차의 좋은 자산이다 — 지우지 말고 다듬어라.

[교정할 대본 {count}개]
{targets}

[출력]
JSON만. 각 대본마다:
- job_id: 그대로
- after4: 4차 교정 전문
- changed: 3차 대비 뭘 바꿨는지 한 줄 (바꿀 게 없으면 "유지")
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
                    "after4": {"type": "string"},
                    "changed": {"type": "string"},
                },
                "required": ["job_id", "after4", "changed"],
            },
        }
    },
    "required": ["pairs"],
}


def _strip_md(text):
    # 결함 ② 후처리: 모델이 또 넣어도 확정적으로 벗긴다.
    return re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text).replace("*", "")


def _call(client, prompt):
    for attempt, model in enumerate([MODEL, MODEL, _FALLBACK, _FALLBACK, _FALLBACK]):
        try:
            resp = client.models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=SCHEMA, temperature=1.0))
            return json.loads(resp.text).get("pairs", []), model
        except Exception as e:
            print(f"  [재시도 {attempt+1}/5 {model}] {str(e)[:90]}", flush=True)
            time.sleep(5 * (attempt + 1))
    return [], None


def main():
    pairs = json.load(open(os.path.join(HERE, "script_pairs3.json"), encoding="utf-8"))
    dst = os.path.join(HERE, "script_pairs4.json")
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
    src = {p["job_id"]: p for p in pairs}
    BATCH = 8
    fresh = []
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        targets = "\n\n".join(
            f"[{p['job_id']}]\n원본(before): {p['before']}\n3차교정: {p['after3']}"
            for p in chunk)
        got, model = _call(client, PROMPT_TMPL.format(count=len(chunk), targets=targets))
        if got:
            print(f"[배치 {i//BATCH + 1}] {len(got)}쌍 ({model})", flush=True)
            fresh.extend(got)
        else:
            print(f"[배치 {i//BATCH + 1} 포기]", flush=True)
        time.sleep(2)

    out = list(done)
    for g in fresh:
        b = src.get(g["job_id"], {})
        out.append({"job_id": g["job_id"], "before": b.get("before", ""),
                    "after3": b.get("after3", ""), "after4": _strip_md(g["after4"]),
                    "changed": g["changed"]})

    # ④ 길이 이탈분만 2회까지 재교정 (전체 재생성 금지 — README 지시)
    for round_no in (1, 2):
        viol = []
        for p in out:
            b = p["before"].replace(" / ", " ")
            r = len(p["after4"]) / len(b) if b else 1.0
            if not (0.80 <= r <= 1.30):
                viol.append((p, r))
        if not viol:
            break
        print(f"[길이재교정 {round_no}차] 이탈 {len(viol)}건: "
              + ", ".join(f"{p['job_id'][:8]}({r:.2f})" for p, r in viol), flush=True)
        targets = "\n\n".join(
            f"[{p['job_id']}]\n원본(before): {p['before']}\n3차교정: {p['after4']}"
            + f"\n(현재 원본의 {r:.2f}배 — 0.85~1.25배로 맞춰라)"
            for p, r in viol)
        got, model = _call(client, PROMPT_TMPL.format(count=len(viol), targets=targets))
        by_id = {g["job_id"]: g for g in got}
        for p, _ in viol:
            g = by_id.get(p["job_id"])
            if g:
                p["after4"] = _strip_md(g["after4"])
                p["changed"] += f" / 길이재교정{round_no}"
        time.sleep(2)

    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n[완료] 총 {len(out)}쌍 (이번 +{len(fresh)}) → {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
