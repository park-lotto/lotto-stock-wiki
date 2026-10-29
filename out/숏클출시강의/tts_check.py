"""필재 TTS 발음 검사 — 음성을 받아 적어 대본(tts_in/sXX.txt)과 글자 단위로 대조한다.

쓰기: py tts_check.py <mp3 폴더> [s03 s04 ...]   (장면 생략 시 폴더의 전부)
판정: 받아쓰기는 Gemini(무료 키 순환). 어긋난 구간만 뽑아 보여 준다 → 그 단어를 tts_prep.py READ 표에 넣고 다시 합성.
주의: 받아쓰기 자체가 틀릴 수 있다(동음·띄어쓰기). 띄어쓰기·문장부호는 빼고 비교, 어긋남은 '귀로 확인할 후보'다.
"""
import difflib, json, os, re, sys, time
from google import genai

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(HERE, "..", "..", ".env")
KEYS = [l.split("=", 1)[1].strip().strip('"') for l in open(ENV, encoding="utf-8")
        if l.startswith("GEMINI") and "=" in l and l.split("=", 1)[1].strip()]
PROMPT = ("이 한국어 음성을 들리는 그대로 받아 적어라. 고치거나 다듬지 말고, 잘못 읽힌 단어도 들린 대로 적는다. "
          "숫자도 들린 대로 한글로. 받아 적은 글만 출력.")


def norm(s):
    return re.sub(r"[\s.,?!\"'…·~\-()]", "", s)


def transcribe(path, ki):
    for a in range(len(KEYS) * 2):
        try:
            c = genai.Client(api_key=KEYS[(ki + a) % len(KEYS)])
            f = c.files.upload(file=path)
            while f.state.name == "PROCESSING":
                time.sleep(2); f = c.files.get(name=f.name)
            return c.models.generate_content(model="gemini-2.5-flash", contents=[f, PROMPT]).text.strip()
        except Exception as e:  # 키 소진·일시 오류 → 다음 키
            last = e
            time.sleep(2)
    raise RuntimeError(f"받아쓰기 실패: {last}")


def main():
    folder = sys.argv[1]
    names = sys.argv[2:] or sorted(f[:-4] for f in os.listdir(folder) if re.fullmatch(r"s\d\d\.mp3", f))
    report = {}
    for i, n in enumerate(names):
        want = open(os.path.join(HERE, "tts_in", n + ".txt"), encoding="utf-8").read()
        got = transcribe(os.path.join(folder, n + ".mp3"), i)
        a, b = norm(want), norm(got)
        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        diffs = [(a[max(0, i1 - 6):i2 + 6], b[max(0, j1 - 6):j2 + 6]) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"]
        report[n] = {"ratio": round(sm.ratio(), 4), "diffs": diffs, "heard": got}
        print(f"{n} 일치 {sm.ratio():.1%}  어긋남 {len(diffs)}", flush=True)
        for w, h in diffs:
            print(f"    대본[{w}]  들림[{h}]")
    json.dump(report, open(os.path.join(folder, "tts_check.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


main()
