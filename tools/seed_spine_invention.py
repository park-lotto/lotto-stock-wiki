# -*- coding: utf-8 -*-
"""'유튜브 발명품형' 스파인 등록 — 멱등 시드 (2026-08-20).

## 왜 만드나 — 실측이 새로 드러낸 갈래

히트작 200편 Gemini 정밀분해(198편) 결과 권위자형이 **47편(23.7%)**으로 2위였다.
문구 규칙 판정에선 4편(2%)이라 거의 안 보이던 갈래다. 그런데 47편을 자막 원문으로
뜯어보니 **단일 골격이 아니었다**:

    8편  = 문장이 오용형과 사실상 같다("이게 원래는 ~로 개발된 제품이었음 …
           근데 미친 사용법은 따로 있었는데") → 기존 spine 56이 이미 커버한다
    23편 = 완전히 다른 고정 어구를 쓴다 ← **이 시드가 담는 갈래**
    16편 = 판정 보류(어느 쪽 어구도 뚜렷하지 않다) — 건드리지 않는다

## 은폐형(spine 55)과 무엇이 다른가

은폐형 31편 중 23편도 같은 계열 어구를 쓴다. 차이는 **정체를 숨기느냐 하나**다:

    은폐형    bait(정체 숨김) → authority → **reveal(정체 공개)** → benefit → twist
    발명품형  title → **story(탄생 배경)** → authority → benefit → escalate → twist

발명품형은 reveal이 없고 그 자리에 **탄생 배경**이 온다. 그리고 은폐형은 고조('심지어')가
twist 문장 안에 붙어 있는데, 발명품형은 **고조와 반전이 따로 선다**(실측 문장이 그렇다).

## ★탄생 배경이 이 갈래의 본체다

    "혼자서 신발을 신고 싶다는 뇌성마비 소년의 간절한 편지 한 통에 탄생한 이 신발이…"  (260만)
    "비만 오면 짐 챙기다 생지옥 되던 육아맘에 빡쳐서 탄생한 이 물건이…"                (590만)

이게 없으면 그냥 제품 소개가 된다. 그래서 `{계기}` 슬롯을 새로 뚫고
`sul_facts.origin_story`가 영상에서 뽑게 했다(같은 커밋).
⚠️ **없으면 비운다** — 지어낸 미담이 대본에 박히는 게 이 갈래의 가장 큰 사고다.
   계기가 없는 소재에서는 계기를 안 쓰는 변형이 대신 걸린다(`pick_template` 규약).

실행: python3 tools/seed_spine_invention.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shopping_shorts.config import DB_PATH          # noqa: E402
from shopping_shorts.store import Store             # noqa: E402

CHARS_PER_30S = 270      # 유튜브 썰쇼핑 실측(262~283)의 중앙 — 은폐형·오용형과 같다

SPEC = dict(
    name="유튜브 발명품형",
    situation_type="탄생 배경(사람 이야기)으로 열고 권위·화제로 받친 뒤 핵심 기능을 시연한다",
    beat_chain=[
        "누구를 구원한 어느 나라 발명품인지 제목으로 못 박는다(정체를 숨기지 않는다)",
        "★이 물건이 왜·누구 때문에 태어났는지 말한다 — 이 갈래의 본체다",
        "어디서 얼마나 화제가 됐는지로 권위를 세운다(바이럴·품절대란·매출)",
        "핵심 기능을 '이게 말도 안 되는 게'로 터뜨린다",
        "'심지어'로 한 단계 더 올린다",
        "★마지막에 예상 못 한 반전을 둔다(CTA 없이 닫는다)",
    ],
    emotion_arc="공감 → 납득 → 놀람 → 감탄",
    appeal="제품 사양이 아니라 **왜 태어났는지**를 판다. 사람 이야기라 끝까지 본다",
    fit_categories=["발명품형"],
    beat_roles=["title", "story", "authority", "benefit", "escalate", "twist"],
    templates={
        # 실측 23편에서 글자 그대로 반복된 어구만 쓴다. 소재만 갈아끼운다.
        # ⚠️ 실측 제목엔 "{육아맘}을 구원한"처럼 **수혜자**가 자주 나오지만, 그걸 담을
        #    슬롯을 새로 뚫지 않았다 — 재료 추출이 안 뽑는 슬롯을 템플릿에 쓰면
        #    `pick_template`이 그 변형을 통째로 건너뛴다(모르는 슬롯 = 못 쓰는 템플릿).
        #    수혜자는 {계기} 문장 안에 이미 들어 있다("육아맘의 불편에서 출발").
        "title": [
            "{나라} 천재가 만들어 떼돈 번 {제품}의 정체",
            "{나라}에서 난리 난 {제품}의 정체",
            "개발자도 예상 못 한 반전 기능의 {제품}",
            "예측 못 한 반전 기능으로 개떡상한 {제품군}",
        ],
        # ★계기가 있을 때만 걸리는 변형을 **앞에** 둔다. 없으면 아래 변형이 대신 걸린다
        #   (없는 미담을 지어내지 않는다 — 이 갈래에서 가장 위험한 사고다).
        "story": [
            "{계기}에서 탄생한 이 제품이 사람들 사이에서 조용히 퍼지기 시작했는데",
            "{계기} 때문에 만들어진 이 물건이 입소문을 타기 시작했는데",
            "누가 봐도 그냥 평범해 보이는 이 {제품군} 하나가 조용히 퍼지기 시작했는데",
        ],
        "authority": [
            "{나라}에서 바이럴이 터지며 매출이 폭발했다는데 이게 진짜 물건인 이유가 있음",
            "{나라}에서 품절대란이 날 정도로 난리가 났다는데 이유가 있었음",
            "전 세계로 수출되며 초대박이 났다는데 그럴 만한 이유가 있었음",
        ],
        "benefit": [
            "이게 진짜 말도 안 되는 게 {효능}",
            "이게 미친 포인트인 게 {효능}",
        ],
        # ⚠️{효능2}는 대개 **문장**이다("뒤꿈치만 밟으면 알아서 벗겨진다"). 그 뒤에 "까지"
        #   같은 조사를 붙이면 "벗겨진다까지 되니까"라는 비문이 나온다(실측으로 잡음).
        #   게이트는 이걸 못 잡는다 — 문장틀·글자수·고조어를 다 통과한다. 그래서 여기서 막는다.
        "escalate": [
            "심지어 {효능2}",
            "더 대박인 건 {효능2}",
        ],
        "twist": [
            "근데 진짜 충격적인 포인트는 따로 있는데 {효능3}",
            "하지만 진짜 소름 돋는 반전은 따로 있는데 {효능3}",
            "하지만 정작 써 본 사람들 사이에선 의외의 후기가 쏟아지는데 {효능3}",
        ],
    },
)


def main():
    st = Store(DB_PATH)
    existing = [s for s in st.list_spines() if s["name"] == SPEC["name"]]
    if existing:
        sid = existing[0]["id"]
        st.set_spine_style(sid, beat_roles=SPEC["beat_roles"], templates=SPEC["templates"],
                           chars_per_30s=CHARS_PER_30S, no_cta=True, hook_3s=True,
                           hook_conceal=False)
        with st._conn() as c:
            c.execute("UPDATE spine SET fit_categories_json=?, status='approved' WHERE id=?",
                      (json.dumps(SPEC["fit_categories"], ensure_ascii=False), sid))
        print("이미 있어 갱신: id=%s" % sid)
    else:
        sid = st.add_spine(
            name=SPEC["name"], situation_type=SPEC["situation_type"],
            beat_chain=SPEC["beat_chain"], emotion_arc=SPEC["emotion_arc"],
            appeal=SPEC["appeal"], fit_categories=SPEC["fit_categories"],
            status="approved")
        st.set_spine_style(sid, beat_roles=SPEC["beat_roles"], templates=SPEC["templates"],
                           chars_per_30s=CHARS_PER_30S, no_cta=True, hook_3s=True,
                           hook_conceal=False)
        with st._conn() as c:
            # 승격게이트(source_count>=3)를 넘게 실측 근거 편수를 적는다 — 자막 원문으로
            # 어구를 확인한 23편이다(추정이 아니라 실측).
            c.execute("UPDATE spine SET source_count=? WHERE id=?", (23, sid))
        print("추가: id=%s" % sid)

    sp = [s for s in st.list_spines() if s["id"] == sid][0]
    print("  roles:", sp["beat_roles"])
    print("  fit:", sp["fit_categories"], "| src:", sp["source_count"],
          "| conceal:", sp["hook_conceal"], "| no_cta:", sp["no_cta"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
