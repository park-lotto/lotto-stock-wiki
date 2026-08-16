# -*- coding: utf-8 -*-
"""스타일 3종의 **이름을 특징 기반으로 바꾸고**, CTA를 **우리 헌장 구조**로 교체한다
(2026-08-16 사장님 지시 2건). 멱등 — 여러 번 돌려도 같은 결과.

## ① 이름에 채널명을 쓰지 않는다

스타일은 **즐겨찾기**다. 드롭다운에서 고르는 사람은 '채이홈'·'메종홈디노'가 뭔지 모른다.
이름만 보고 **"내 소재에 이걸 쓸까"** 를 판단할 수 있어야 하므로 **훅이 무엇으로 여는가**
= 그 스타일의 정체성으로 짓는다.

    52  시월드형          → 가족갈등 반전형     (가족에게 혼났다 → 알고 보니 그 물건 덕분)
    53  엄마 정보통형      → 단정 명령형        ("여러분 OO 무조건 이렇게 하세요")
    54  세상에 이런 물건형 → 물건 발견형        (출처 권위 + 제품 서사가 주인공)

★'시월드형'·'엄마 정보통형'도 특징 기반이긴 하나, 전자는 특정 채널 색(시월드)에 묶여 있고
  후자는 화자(엄마)를 가리켜 소재가 육아·살림이 아니면 고르기 망설여진다. **훅의 동작**으로
  통일하면 세 이름이 같은 축에서 비교된다 — 즐겨찾기로 쓰려면 축이 같아야 한다.

## ② CTA는 원본을 베끼지 않고 **우리 구조**로 만든다 (사장님 지시)

원본 실측(36편)을 보면 세 채널 CTA는 우리 기준으로 **약하다**:
  - 채이홈 12편: 대부분 "나도 남겨주세요?"로 끝난다. **받는 게 뭔지 말하지 않는다.**
    받는 것을 말한 건 12편 중 2편뿐("나도 남겨주시면 핵심 재료량 레시피 몰래 공유드릴게요").
  - 메종홈디노 12편: CTA 자체가 4편뿐("댓글에 'tv' 남겨주세요").
헌장(`script_generate._STORY_RULES_CORE`, 2026-08-04 사장님 확정)은 그걸 **실패**로 규정한다:
    [댓글 달 수밖에 없는 명분 한 줄] + "댓글에 'OO' 남겨주시면 [받는 것] 드릴게요"
    "남겨주세요"로만 끝나면 실패다.

→ 그래서 CTA 문장틀에서 **'남겨주세요'로만 끝나는 형태를 전부 뺀다.** 남는 건 전부
  **받는 것을 말하는 형태**뿐이다. 스타일이 헌장을 약화시키면 안 된다.

★명분(왜 댓글로만 주는가)은 소재마다 달라서 문장틀로 못 박는다 — `beat_chain`의 cta 칸
  지시문에 넣어 모델이 소재에 맞게 쓰게 한다(헌장 예: 검색해도 안 나옴·다들 물어봐서
  댓글로만·모르고 사면 비쌈). 없는 할인·한정수량을 지어내는 건 헌장이 금지한다.

실행: python3 tools/seed_style_rename_cta.py
"""
import json as _json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shopping_shorts.config import DB_PATH          # noqa: E402
from shopping_shorts.store import Store             # noqa: E402

# 우리 헌장 구조 CTA — **전부 '받는 것'을 말한다.** "남겨주세요"로만 끝나는 형태는 없다.
# 게이트(script_gate)는 어간 '남겨주'로 판정하므로 이 형태들은 전부 통과한다.
CTA_OURS = [
    "댓글에 {단어} 남겨주시면 {받는것} 보내 드릴게요",
    "댓글에 {단어} 남겨주시면 {받는것} 드릴게요",
    "댓글에 {단어} 남겨주시면 {받는것} 바로 보내 드릴게요",
    "{단어} 남겨주시면 {받는것} 보내 드릴게요",
    "{단어} 남겨주시면 {받는것} 드릴게요",
    "궁금하시면 {단어} 남겨주시면 {받는것} 보내 드릴게요",
]

# cta 칸 지시문 — 명분을 반드시 앞에 붙이게 한다(헌장 그대로).
CTA_BEAT = ("[댓글 달 수밖에 없는 명분 한 줄] + 댓글에 '{단어}' 남겨주시면 [받는 것] 드릴게요. "
            "★받는 것을 반드시 말한다(링크·정확한 레시피·감춘 비법). '남겨주세요'로만 끝내지 마라. "
            "명분 예: 검색해도 안 나옴·다들 물어봐서 댓글로만 — 없는 할인·한정수량 지어내기 금지")

RENAME = {
    "시월드형": {
        "new": "가족갈등 반전형",
        "situation_type": "가족에게 혼났는데 알고 보니 그 물건 덕분",
        "appeal": "가족 갈등이라는 흔한 상황 + 제3자 권위로 신뢰 이전",
    },
    "엄마 정보통형": {
        "new": "단정 명령형",
        "situation_type": "아는 전문가가 알려준 걸 단정적으로 알려준다",
        "appeal": "'무조건 이렇게 하세요' 단정 훅 + 생활 속 전문가 인맥으로 신뢰 이전",
    },
    "세상에 이런 물건형": {
        "new": "물건 발견형",
        "situation_type": "권위 있는 출처에서 화제가 된 신기한 물건을 발견해 소개한다",
        "appeal": "제품 서사와 출처 권위로 끄는 발견형 — 화자 경험 없이 물건이 주인공",
    },
}


def main():
    st = Store(DB_PATH)
    spines = st.list_spines()
    by_name = {s["name"]: s for s in spines}

    for old, spec in RENAME.items():
        sp = by_name.get(old) or by_name.get(spec["new"])
        if not sp:
            print("건너뜀(없음): %s" % old)
            continue
        sid = sp["id"]

        # ① 이름·설명 교체
        with st._conn() as c:
            c.execute("UPDATE spine SET name=?, situation_type=?, appeal=? WHERE id=?",
                      (spec["new"], spec["situation_type"], spec["appeal"], sid))

        # ② CTA 문장틀을 우리 구조로 교체(다른 칸은 건드리지 않는다)
        row = st.get_spine_style(sid) if hasattr(st, "get_spine_style") else None
        with st._conn() as c:
            r = c.execute("SELECT templates_json, beat_chain_json, beat_roles_json "
                          "FROM spine WHERE id=?", (sid,)).fetchone()
        templates = _json.loads(r[0]) if r and r[0] else {}
        beat_chain = _json.loads(r[1]) if r and r[1] else []
        beat_roles = _json.loads(r[2]) if r and r[2] else []

        templates["cta"] = list(CTA_OURS)

        # cta 칸 지시문도 헌장 문구로 교체(칸 순서는 그대로)
        if "cta" in beat_roles:
            i = beat_roles.index("cta")
            if i < len(beat_chain):
                beat_chain[i] = CTA_BEAT
            else:
                beat_chain = list(beat_chain) + [CTA_BEAT]

        with st._conn() as c:
            c.execute("UPDATE spine SET templates_json=?, beat_chain_json=? WHERE id=?",
                      (_json.dumps(templates, ensure_ascii=False),
                       _json.dumps(beat_chain, ensure_ascii=False), sid))
        print("갱신: id=%s  %s -> %s  (cta 문장틀 %d개)"
              % (sid, old, spec["new"], len(templates["cta"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
