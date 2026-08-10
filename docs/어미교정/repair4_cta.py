# -*- coding: utf-8 -*-
"""4차 보정 — check4의 CTA순서 위반분만 재교정한다 (전체 재생성 금지)."""
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

# check4.py는 import 시 전체가 실행되는 스크립트라 판정기를 복제한다(check4와 동일 유지)
_CTA_HINT = re.compile(r"댓글|남겨|팔로우|저장")
_VERB_END = re.compile(r"(요|다|죠|까|네|게|래|지)\s*[!?.…]*$")


def cta_order_bad(text):
    sents = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text) if s.strip()]
    seen_cta = False
    for s in sents:
        if _CTA_HINT.search(s):
            seen_cta = True
        elif seen_cta and s.endswith("!") and not _VERB_END.search(s.rstrip("!")):
            return True
    return False

MODELS = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3.1-flash-lite"]
PROMPT = """아래 한국 쇼핑 숏폼 대본은 딱 한 가지 결함만 있다:
**CTA(댓글 유도) 문장 뒤에 명사로 끊어지는 미완성 문장이 붙어 있다.**

고치는 법: 그 명사끊기 문장을 CTA '앞'으로 옮겨 자연스럽게 잇거나,
앞에 이미 같은 뜻의 명사끊기가 있으면 뒤엣것을 삭제해라.
대본은 반드시 CTA 문장으로 끝나야 한다. 그 외에는 한 글자도 바꾸지 마라.

[대본]
{text}

[출력] JSON만: {{"after4": "교정 전문"}}
"""


def main():
    dst = os.path.join(HERE, "script_pairs4.json")
    out = json.load(open(dst, encoding="utf-8"))
    viol = [p for p in out if cta_order_bad(p["after4"])]
    print(f"[대상] {len(viol)}건: {[p['job_id'][:8] for p in viol]}")
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""),
                          http_options=types.HttpOptions(timeout=120_000))
    SCHEMA = {"type": "object", "properties": {"after4": {"type": "string"}},
              "required": ["after4"]}
    for p in viol:
        fixed = False
        for attempt, model in enumerate(MODELS):
            try:
                resp = client.models.generate_content(
                    model=model, contents=PROMPT.format(text=p["after4"]),
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=SCHEMA, temperature=0.4))
                cand = json.loads(resp.text)["after4"].replace("*", "")
                if not cta_order_bad(cand):
                    p["after4"] = cand
                    p["changed"] += " / CTA순서보정"
                    print(f"  {p['job_id'][:8]} 보정 완료 ({model})")
                    fixed = True
                    break
                print(f"  {p['job_id'][:8]} 여전히 위반 — 재시도")
            except Exception as e:
                print(f"  [재시도 {attempt+1} {model}] {str(e)[:80]}")
                time.sleep(5 * (attempt + 1))
        if not fixed:
            # 결정적 폴백: CTA 뒤에 붙은 명사끊기 조각을 삭제한다.
            # (명사끊기는 CTA 앞의 자산이지 뒤에 두면 미완성 종결 — 지워도 정보 손실 없음)
            sents = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", p["after4"]) if s.strip()]
            keep, seen_cta = [], False
            for s in sents:
                if _CTA_HINT.search(s):
                    seen_cta = True
                elif seen_cta and s.endswith("!") and not _VERB_END.search(s.rstrip("!")):
                    continue
                keep.append(s)
            p["after4"] = " ".join(keep)
            p["changed"] += " / CTA뒤 조각 삭제(폴백)"
            print(f"  {p['job_id'][:8]} 폴백 삭제 적용 → 위반 {cta_order_bad(p['after4'])}")
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("[저장]")


if __name__ == "__main__":
    main()
