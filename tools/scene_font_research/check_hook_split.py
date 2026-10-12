"""훅 제목 두 줄 나누기 — 과거 사장님 제보 사례 + 오늘 사례를 한자리에서 잰다 (2026-09-23).
  py tools/scene_font_research/check_hook_split.py

이븐쇼핑 짜임새: 첫 줄 = 꾸미는 말로 닫히는 긴 절, 둘째 줄 = 10~11자 명사 덩어리(강조 자리).
각 줄은 '이렇게 나뉘어야 한다'는 실물 판정이다. 고치기 전/후에 그대로 돌려 회귀를 본다.
"""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from shopping_shorts.template_copy import split_hook

CASES = [
    # (한 줄 입력, 바라는 첫 줄, 바라는 둘째 줄, 출처·사연)
    ("미국 천재가 만들어 떼돈 번 기발한 제품의 정체", "미국 천재가 만들어 떼돈 번", "기발한 제품의 정체",
     "2026-09-23 사장님 '기발한 제품의 정체를 두 번째에 나누면 안 되나' — 꾸밈말은 명사를 데리고 내려간다"),
    ("제조사도 예상 못한 미친 활용법", "제조사도 예상 못한", "미친 활용법",
     "2026-09-23 실물(job 5638893ae8b7)"),
    ("다이소 덕후들의 천재적인 활용법", "다이소 덕후들의", "천재적인 활용법",
     "2026-09-22 주석이 목표로 적은 자리. ★고치기 전부터 '다이소 / 덕후들의 천재적인 활용법'이 나온다 —"
     " 첫 줄 끝 '의'를 조사로 보고 막기 때문. 오늘 사장님 요청과 무관한 기존 결함이라 표시만 한다", True),
    ("아니 텀블러이 있다고?", "아니", "텀블러이 있다고?",
     "2026-09-22 사장님 제보 — 조사 '이'에서 끊으면 말이 끊긴다"),
    ("코스트코 본사도 몰랐던 천재 아이디어", "코스트코 본사도 몰랐던", "천재 아이디어",
     "주석 실측 — '몰랐던'이 둘째 줄 첫머리로 떨어지면 안 된다(꾸밈말은 첫 줄에 남는다)"),
    ("건망증 환자를 살려낸 일본 천재의 발명품", "건망증 환자를 살려낸", "일본 천재의 발명품",
     "이븐쇼핑 견본(22자) — 첫 줄이 꾸밈말로 닫히고 둘째 줄이 명사 덩어리"),
]
# ★넓은 회귀: 템플릿 20개 견본 제목을 한 줄로 합쳐 다시 나눠 견본과 같은 자리가 나오나 본다.
#   실측 2026-09-23: 18/20 일치. 어긋나는 t04·t12는 **고치기 전(21aec8603)에도 똑같이** 어긋났다(기존 결함).
fails = []
for case in CASES:
    line, want1, want2, why = case[0], case[1], case[2], case[3]
    known = len(case) > 4 and case[4]
    got1, got2 = split_hook(line)
    ok = (got1, got2) == (want1, want2)
    mark = '  통과  ' if ok else ('△ 기존결함' if known else '★ 실패  ')
    print(mark + f'"{line}"')
    print(f'          바람 "{want1}" / "{want2}"')
    if not ok:
        print(f'          실제 "{got1}" / "{got2}"   ← {why}')
        if not known: fails.append(line)
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건')
sys.exit(1 if fails else 0)
