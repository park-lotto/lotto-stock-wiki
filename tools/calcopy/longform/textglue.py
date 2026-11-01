# 녹음용 글: 띄어 쓴 한글 수사+단위를 붙인다("오 퍼센트" → "오퍼센트"). 띄우면 "오, 퍼센트"로 끊어 읽는다.
import re
UNITS = "퍼센트|년대|년|월|일|분기|개월|세|명대|명|억|조|대|등|만"
AMBIGUOUS = {"일", "대", "등", "조", "세", "만"}  # "이 일은"·"이 대로"·"이 등급"처럼 지시어 '이'와 겹치는 단위
def _join(m):
    num, unit = m[1], m[2]
    if num == "이" and unit in AMBIGUOUS: return m[0]
    return num + unit
def glue(s):
    return re.sub(r"(?<![가-힣])([영일이삼사오육칠팔구십백천만억조]+) (" + UNITS + r")", _join, s) if s else s
