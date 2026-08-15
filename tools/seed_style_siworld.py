"""채이홈(chae2home) '시월드형' 스타일 1건을 spine에 넣는다 — 1회용 시드(멱등).

근거(2026-08-15 실측): 채이홈 448편 중 선별 12편을 실제 전사해 대조한 결과, 100만+ 히트작이
전부 같은 뼈대였다 — 가족에게 혼남(훅) → 무엇이 문제였나 → 제3자 권위가 알려준 물건(반전) →
쓰고 나서 → 단어 CTA. 훅 문장은 4종을 소재만 바꿔 재사용한다.
말 밀도는 히트작 실측 264~377자(30초 기준) → 300으로 잡는다.

실행: python3 tools/seed_style_siworld.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shopping_shorts.config import DB_PATH          # noqa: E402
from shopping_shorts.store import Store             # noqa: E402

NAME = "시월드형"
BEAT_ROLES = ["hook", "before", "reveal", "after", "cta"]
BEAT_CHAIN = [
    "가족(시어머니·엄마·남편·언니)에게 혼나거나 충격받은 상황을 첫 3초에 던진다",
    "무엇이 문제였는지 — 더러움·불편함을 화면과 함께 구체적으로",
    "반전: 알고 보니 제3자 전문가가 알려준 물건이었다",
    "쓰고 나서 어떻게 달라졌는지 — 비포애프터 대비",
    "단어 하나를 댓글로 유도(무엇을 받는지 함께 말한다)",
]
TEMPLATES = {
    "hook": ["이것 때문에 {가족}한테 욕 바가지로 먹을 뻔했어요",
             "{장소} 갔다가 진짜 충격 받았어요",
             "{가족} 때문에 진짜 충격 받았어요",
             "이거 몰라서 {손해} 날릴 뻔했어요"],
    # ★채이홈 12편 실측에서 반전 문장은 한 가지가 아니었다 — 공통점은 '제3자 권위'다:
    #   "친한 세탁소 사장님이 알려줬는데" / "미국 사시는 이모님이 추천해준" /
    #   "청소업체 오픈한 친구가 추천해 준" / "엄마가 다니는 목욕탕 세신사님이 추천해주신".
    #   좁게 2개만 넣었더니 라이브에서 정상 문장("살림 고수인 언니가 …알려주더라고요")을
    #   FAIL로 잡았다. 표현형을 실측대로 넓힌다.
    "reveal": ["알고 보니 {전문가}가 추천해준 {제품}이라고 하더라구요",
               "알고 보니 {전문가}가 알려준 거라고 하더라구요",
               "알고 보니 {전문가}가 알려주더라고요",
               "알고 보니 {전문가}가 쓴다는 {제품}이라고 하더라구요",
               "{전문가}가 추천해준 거라고 하더라구요",
               "{전문가}가 알려줬다는데",
               # 가장 느슨한 형태 — 채이홈 원본에도 이런 문장이 있다("미국 사시는 이모님이
               # 추천해준 이 세정제를 쓰신다는 거에요"). '추천해준/알려준'이라는 제3자 권위
               # 표지만 있으면 이 칸의 목적은 달성된다.
               "{전문가}가 추천해준 {제품}",
               "{전문가}가 알려준 {제품}"],
    # ★기존 헌장(_STORY_RULES_CORE, 2026-08-04 사장님 확정)이 이미 옳다:
    #   "남겨주세요"로만 끝내면 실패 — 무엇을 받는지 말해야 사람이 댓글을 단다.
    #   채이홈 실측 CTA("댓글에 클린 남겨주세요")보다 이쪽이 낫다고 이미 결론난 규칙이라
    #   스타일이 그 규칙을 덮어쓰지 않게 두 형태를 다 허용한다.
    "cta": ["댓글에 {단어} 남겨주시면 {받는것} 드릴게요",
            "댓글에 {단어} 남겨주시면 {받는것} 보내드릴게요",
            "댓글에 {단어} 남겨주세요"],
}


def main():
    st = Store(DB_PATH)
    existing = [s for s in st.list_spines() if s["name"] == NAME]
    if existing:
        sp = existing[0]
        st.set_spine_style(sp["id"], beat_roles=BEAT_ROLES, templates=TEMPLATES,
                           chars_per_30s=300)
        import json as _json
        with st._conn() as _c:                      # 카테고리 교정(기존 행도 고친다)
            _c.execute("UPDATE spine SET fit_categories_json=? WHERE id=?",
                       (_json.dumps(["홈템"], ensure_ascii=False), sp["id"]))
        print("이미 있어 갱신함: id=%s" % sp["id"])
        return 0
    sid = st.add_spine(
        name=NAME,
        situation_type="가족에게 혼났는데 알고 보니 그 물건 덕분",
        beat_chain=BEAT_CHAIN,
        emotion_arc="당황 → 억울 → 반전 → 만족",
        appeal="가족 갈등이라는 흔한 상황 + 제3자 권위로 신뢰 이전",
        # ★실제 시스템 카테고리 어휘로 맞춘다(2026-08-15 실측: 홈템72·레시피56·가전·뷰티·기타).
        #   내가 임의로 "살림청소·생활용품·주방"이라고 넣었더니 어느 영상과도 안 맞아
        #   드롭다운이 아예 안 떴다 — 라벨은 반드시 DB에 실재하는 값이어야 한다.
        fit_categories=["홈템"],
        status="approved",
    )
    st.set_spine_style(sid, beat_roles=BEAT_ROLES, templates=TEMPLATES, chars_per_30s=300)
    # 근거 영상 4편(631만·347만·294만·344만) → 승격게이트(source_count>=3) 통과값.
    st.update_spine_stats(sid, source_count=4, perf_score=0.0)
    print("새로 넣음: id=%s" % sid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
