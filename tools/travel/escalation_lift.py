# -*- coding: utf-8 -*-
"""고조어·불편 시작·인물 등장 vs 조회수 — 대본창고 인스타 실측 (관제 239, 여행 스타일 카드 2판 근거).

입력: 서버 reference.db(script_extracts.full_text + channel_archive.views)를 뽑은 JSON
      (만드는 법: 서버에서 read-only 로 shortcode·full_text·username·views·url 을 뽑아 all_scripts.json 으로 — 세션 기록 참고)
사용: py tools/travel/escalation_lift.py <all_scripts.json>
출력: 말마다 [편수 · 그 편들 조회수 중앙 · 전체 중앙 대비 배수 · 상위 10% 안 비중]
"""
import json
import re
import statistics as st
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORDS = ["근데 이게", "이게 대박인 게", "소름", "알고 보니", "심지어", "게다가", "진짜 대박", "대박인 건", "무엇보다", "거기다", "미쳤", "이게 진짜"]
PAIN = r"때문에|스트레스|불편|귀찮|짜증|고생|힘들|찝찝|답답|매번|할 때마다|갈 때마다|서러|속상|난감|포기|지옥|민망"
PERSON = r"(엄마|남편|아내|와이프|친구|시어머니|아이|딸|아들|사장님|언니)"


def main():
    A = json.load(open(sys.argv[1], encoding="utf-8"))
    S = sorted([x for x in A if x.get("url") and "instagram" in x["url"] and x.get("views")], key=lambda x: -x["views"])
    med = st.median(x["views"] for x in S)
    rank = {id(x): i for i, x in enumerate(S)}
    flat = lambda t: t.replace(" ", "")

    def row(label, hit):
        if len(hit) < 8:
            print("%-26s %4d편 (8편 미만 — 판단 보류)" % (label, len(hit)))
            return
        m = st.median(x["views"] for x in hit)
        top = sum(1 for x in hit if rank[id(x)] < len(S) // 10) / len(hit)
        print("%-26s %4d편  조회 중앙 %8d  배수 %.2f  상위10%% 비중 %d%%" % (label, len(hit), m, m / med, round(top * 100)))

    print("인스타 %d편 · 조회 중앙 %d" % (len(S), med))
    for w in WORDS:
        row("말: " + w, [x for x in S if flat(w) in flat(x["text"])])
    row("앞 80자 불편어", [x for x in S if re.search(PAIN, flat(x["text"])[:80])])
    row("앞 30자 인물", [x for x in S if re.search(PERSON, flat(x["text"])[:30])])
    row("센 고조어 1개+", [x for x in S if re.search(r"이게대박인게|근데이게|소름|알고보니", flat(x["text"]))])


if __name__ == "__main__":
    main()
