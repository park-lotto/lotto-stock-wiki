"""끝난 조각(part_XX.md)마다 노하우 카드를 제미니로 뽑고, 원본 합본을 만든다.
사용: py -I lecture_cards.py <분석폴더> <바탕화면 출력 접두어>
다시 돌리면 카드가 이미 있는 조각은 건너뛴다.
"""
import os, sys, glob, time, itertools, re
sys.stdout.reconfigure(encoding="utf-8")
from google import genai
from google.genai import types
sys.path.insert(0, os.path.dirname(__file__))
from lecture_gemini import keys, MODELS

PROMPT = """아래는 유료 강의 {start}~{end} 구간의 상세 기록이다(시각이 00:00부터 시작하면 {start}를 더해 강의 전체 기준으로 고쳐 적어라).
여기서 '내 숏폼/롱폼 자동화 시스템에 가져다 쓸 수 있는 노하우'만 카드로 뽑아라. 잡담·인사·홍보·수강 규정은 빼라.
기록에 없는 내용을 지어내지 마라. 숫자·도구명·프롬프트·설정값은 기록 그대로 옮겨라.

카드 형식(카드마다 반복):
### [HH:MM:SS] 한 줄 제목
- 무엇:
- 왜/근거: (숫자·경험담)
- 어떻게: (도구·설정·순서·프롬프트 원문)
- 분류: 대본 / 장면·편집 / 음성 / 소재수집 / 저작권·정책 / 도구·비용 / 채널운영 / 기타

카드가 없으면 '카드 없음'만 적어라.

--- 기록 ---
{body}
"""


def main(adir, out_prefix):
    parts = sorted(glob.glob(os.path.join(adir, "part_*.md")))
    ks = keys(); kc = itertools.cycle(ks)
    for p in parts:
        n = int(re.search(r"part_(\d+)", p).group(1))
        card = os.path.join(adir, f"card_{n:02d}.md")
        if os.path.exists(card) and os.path.getsize(card) > 20:
            continue
        body = open(p, encoding="utf-8").read()
        s = (n - 1) * 600
        start, end = f"{s//3600:02d}:{s%3600//60:02d}:00", f"{(s+600)//3600:02d}:{(s+600)%3600//60:02d}:00"
        for attempt in range(len(ks) * 2):
            k = next(kc); model = MODELS[attempt % len(MODELS)]
            try:
                c = genai.Client(api_key=k, http_options=types.HttpOptions(timeout=300000))
                r = c.models.generate_content(model=model, contents=PROMPT.format(start=start, end=end, body=body),
                                              config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=32768))
                t = (r.text or "").strip()
                if not t:
                    raise RuntimeError("빈 응답")
                open(card, "w", encoding="utf-8").write(f"## 조각 {n} ({start}~)\n\n{t}\n")
                print(f"[카드 {n}] 완료 {len(t)}자 ({model})", flush=True); break
            except Exception as e:
                print(f"[카드 {n}] 실패({model}): {str(e)[:120]}", flush=True); time.sleep(3)
    # 합본 2개: 원본 기록 / 노하우 카드
    raw = "\n\n---\n\n".join(open(p, encoding="utf-8").read() for p in parts)
    cards = "\n\n".join(open(c, encoding="utf-8").read() for c in sorted(glob.glob(os.path.join(adir, "card_*.md"))))
    head = f"> 개인 학습용 · 외부 공유 금지 · 조각 {len(parts)}/32 반영\n\n"
    open(out_prefix + "_원본기록.md", "w", encoding="utf-8").write("# 3주차 강의 원본 기록(제미니 판독)\n\n" + head + raw)
    open(out_prefix + "_노하우카드.md", "w", encoding="utf-8").write("# 3주차 노하우 카드\n\n" + head + cards)
    print(f"합본 완료: 조각 {len(parts)}개", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
