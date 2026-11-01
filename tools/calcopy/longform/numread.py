# 자막 글 → 나레이션 소리 칸. 규칙은 지침/숫자읽기.md
import re

D = "영일이삼사오육칠팔구"
WORDS = [("GDP", "지디피"), ("GNI", "지엔아이"), ("GDI", "지디아이"), ("IMF", "아이엠에프"), ("OECD", "오이시디"), ("KDI", "케이디아이"),
         ("AI", "에이아이"), ("K자", "케이자")]
NATIVE = {1: "한", 2: "두", 3: "세", 4: "네", 5: "다섯", 6: "여섯", 7: "일곱", 8: "여덟", 9: "아홉"}
TENS = {1: "열", 2: "스물", 3: "서른", 4: "마흔", 5: "쉰", 6: "예순", 7: "일흔", 8: "여든", 9: "아흔"}
COUNTERS = "개(?!월)|명|배|번|살|곳|가지|달"


def sino(n):
    if n == 0: return "영"
    out = ""
    for unit, name in ((10 ** 12, "조"), (10 ** 8, "억"), (10 ** 4, "만")):
        q, n = divmod(n, unit)
        if q: out += ("" if q == 1 and name == "만" else sino(q)) + name
    for unit, name in ((1000, "천"), (100, "백"), (10, "십")):
        q, n = divmod(n, unit)
        if q: out += ("" if q == 1 else D[q]) + name
    return out + (D[n] if n else "")


def native(n):
    if n >= 100: return sino(n - n % 100) + (native(n % 100) if n % 100 else "")
    t, o = divmod(n, 10)
    if n == 20: return "스무"
    return (TENS[t] if t else "") + (NATIVE[o] if o else "")


def say(text):
    t = text.replace("6월", "유월").replace("10월", "시월").replace(",", " ,") if False else text.replace("6월", "유월").replace("10월", "시월")
    for a, b in WORDS: t = t.replace(a, b)
    t = re.sub(r"(\d[\d,]*)(?:\s*)(" + COUNTERS + ")", lambda m: native(int(m[1].replace(",", ""))) + " " + m[2], t)
    t = re.sub(r"(?<![\d.])1만(?=\s?\d천)", "만", t)
    t = re.sub(r"(\d+(?:,\d{3})+|\d+)(?:\.(\d+))?", lambda m: sino(int(m[1].replace(",", ""))) + (" 점 " + "".join(D[int(c)] for c in m[2]) if m[2] else ""), t)
    return t.replace("%", "퍼센트").replace("'", "").replace("‘", "").replace("’", "")
