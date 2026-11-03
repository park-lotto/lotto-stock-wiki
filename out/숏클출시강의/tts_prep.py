"""대본 md → 필재 TTS 입력(장면별 txt). 발음 사고를 미리 막는다.

과거 기록에서 온 규칙(답습 금지):
- 문장마다 따로 합성하면 억양이 매번 새로 시작해 끊긴다(관제 049) → 장면 하나 = 한 덩어리(서버 스크립트가 문단 단위 500자 조각으로만 나눔)
- 서버 전역 발음사전(global_pron_dict)은 비어 있고 yt_piljae_file.py 는 사전을 안 거친다 → 읽기 표기를 여기서 직접 바꾼다
- 영문 약어·숫자는 성우가 영어/숫자로 읽어 어색 → 한글 읽기로
- 나레이션 줄 안의 화면 지시 괄호 "(자막① …)" 는 읽으면 안 된다 → 뺀다
남은 영문·숫자가 있으면 멈춘다(조용히 넘기지 않는다).
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MD = os.path.join(HERE, "데일리_1편_대본_페이블.md")
OUT = os.path.join(HERE, "tts_in")

READ = [  # 긴 것 먼저
    ("2G폰", "투지폰"), ("LED", "엘이디"), ("MCP", "엠씨피"), ("AI", "에이아이"),
    ("PC", "피씨"), ("TV", "티비"),
]


def scenes():
    text = re.split(r"\n# 쇼츠", open(MD, encoding="utf-8").read())[0]
    for m in re.finditer(r"^## \[(.+?)\][^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M):
        lines = [l[1:].strip() for l in m.group(2).splitlines() if l.startswith(">")]
        if lines:
            yield m.group(1), lines


def readable(line):
    line = re.sub(r"^\(자막[^)]*\)\s*", "", line)
    for a, b in READ:
        line = line.replace(a, b)
    return line


def main():
    os.makedirs(OUT, exist_ok=True)
    bad = []
    for i, (name, lines) in enumerate(scenes()):
        body = "\n\n".join(readable(l) for l in lines)  # 줄=문단 → 서버가 500자 안에서 묶는다
        left = re.findall(r"[A-Za-z0-9]+", body)
        if left:
            bad.append((name, left))
        open(os.path.join(OUT, f"s{i:02d}.txt"), "w", encoding="utf-8").write(body + "\n")
        print(f"s{i:02d} {len(body):4d}자 {name}")
    if bad:
        sys.exit(f"한글 읽기 없는 영문·숫자: {bad}")


main()
