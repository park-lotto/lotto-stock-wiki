"""유튜브 썰쇼핑 스타일 2건을 spine에 넣는다 — 1회용 시드(멱등).

근거(2026-08-19 실측 전사): 유튜브 썰쇼핑은 **인스타와 대본 문법이 정반대**다.
기존 라이브 스파인은 인스타에서 뽑은 '시월드형'(채이홈) 하나뿐이라 유튜브 소재에
쓰면 어색해진다(1인칭 가족갈등 훅 → 유튜브 히트작 4편 중 0편).

    축        인스타(채이홈·메종홈디노)      유튜브(이븐쇼핑·살림킹왕짱)
    화자      1인칭 나                      3인칭 관찰자
    훅        관계 갈등(시댁·와이프)         미스터리 / 용도 배신
    CTA       있음(댓글률 2.35%)            ★없음(4편 다 0, 댓글률 0.005%)
    밀도      217~271자/30초                262~283자/30초  → 270으로 잡는다

★CTA가 없는 게 정답이라 no_cta=True를 준다. 안 주면 script_gate의 CTA 검사가
  스타일 무관 무조건 돌아 **아무리 잘 써도 영구 FAIL**이다(2026-08-19 확인).

실행: python3 tools/seed_style_youtube.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shopping_shorts.config import DB_PATH          # noqa: E402
from shopping_shorts.store import Store             # noqa: E402


# ── A. 은폐형 — 이븐쇼핑(UClecY6IhcjwmCBJHiZ2-cTg) ────────────────────────
# 실측 2편(78.2만·31.6만)에서 아래 어구가 **글자 그대로 동일**했다. 소재만 갈아끼운다.
#   "최근 딱 봤을 때는 [용도를 알기 힘든/평범한] 이 제품이 … 바이럴이 폭발하며
#    이걸 개발한 {나라}의 천재가 돈방석에 앉았다는데 이건 바로 {제품}.
#    이게 말도 안 되는 게 … 근데 진짜 충격적인 포인트는 …"
HIDDEN = dict(
    name="유튜브 은폐형",
    situation_type="정체를 숨긴 화제의 제품을 중반에 공개하고 2차 반전으로 닫는다",
    beat_chain=[
        "제목을 그대로 읽어 무엇에 관한 영상인지 못 박는다(호기심 고정)",
        "이 제품이 겉보기엔 용도를 알 수 없거나 평범하다고 미끼를 던진다",
        "전 세계에서 화제가 됐고 만든 사람이 큰돈을 벌었다고 권위를 세운다",
        "★여기서 처음 정체를 밝힌다 — '이건 바로 {제품}'",
        "왜 말이 안 되는지 첫 번째 효능을 화면과 함께",
        "★2차 반전 — 더 놀라운 두 번째 기능으로 끝낸다(CTA 없이 닫는다)",
    ],
    emotion_arc="호기심 → 궁금증 증폭 → 공개 → 놀람 → 더 큰 놀람",
    appeal="정체를 끝까지 숨겨 완시청을 만든다. 댓글이 아니라 끝까지 보게 하는 게 목적",
    fit_categories=["제품정체형"],
    beat_roles=["title", "bait", "authority", "reveal", "benefit", "twist"],
    templates={
        "bait": ["최근 딱 봤을 때는 도저히 용도를 알기 힘든 이 제품이",
                 "최근 딱 봤을 때는 평범한 이 {제품군}이",
                 "딱 봤을 때는 용도를 알기 힘든 이 제품이"],
        "authority": ["이걸 개발한 {나라}의 천재가 돈방석에 앉았다는데",
                      "이걸 만든 {나라} 천재가 떼돈을 벌었다는데",
                      "{나라}의 한 천재가 돈방석에 앉았다는데"],
        "reveal": ["이건 바로 {제품}", "이게 바로 {제품}"],
        "benefit": ["이게 말도 안 되는 게 {효능}", "이게 말이 안 되는 게 {효능}"],
        "twist": ["근데 진짜 충격적인 포인트는 {효능2}",
                  "근데 진짜 충격적인 건 {효능2}"],
    },
)

# ── B. 오용형 — 살림킹왕짱(UCBFu04us6bv9OFcwrJDXdMg) ──────────────────────
# 실측 2편(1,047만·904만). ★말끝이 '~었음'·'~다는 거' — 인스타의 '~했어요'와 다르다.
#   "이게 원래는 {본래용도}로 개발된 제품이었음. 그런데 사람들은 {속성}을 눈치채고
#    이걸 엉뚱한 용도로 사용하기 시작하는데 … 근데 미친 사용법은 따로 있었는데 …"
MISUSE = dict(
    name="유튜브 오용형",
    situation_type="본래 용도로 만든 제품을 사람들이 엉뚱하게 쓰기 시작한 이야기",
    beat_chain=[
        "제목을 그대로 읽어 '권위자도 몰랐다'는 판을 깐다",
        "이 제품이 원래 무엇을 하라고 만들어졌는지 밝힌다(정체는 숨기지 않는다)",
        "사람들이 숨은 속성을 눈치채고 엉뚱하게 쓰기 시작했다고 전환한다",
        "실제 오용 사례를 두세 개 빠르게 나열한다",
        "★가장 놀라운 사용법을 마지막에 둔다(CTA 없이 닫는다)",
    ],
    emotion_arc="의외 → 납득 → 오호 → 감탄",
    appeal="제품을 파는 게 아니라 '이미 가진 물건의 다른 쓰임'을 판다. 그래서 저장·공유가 붙는다",
    fit_categories=["오용형"],
    beat_roles=["title", "origin", "notice", "cases", "twist"],
    templates={
        # ★빈칸 뒤에 조사를 붙이지 마라(2026-08-19 실측으로 잡음). "{본래용도}로 개발된"
        #   이라고 쓰면 고정 어구가 "로개발된제품이었음"이 되는데, 원문은 "부착하라**고**
        #   개발된"이라 그 조각이 통째로 안 맞아 **실측 원문이 FAIL**한다.
        #   빈칸이 문장으로 끝나는 자리라 조사가 뭐가 될지는 소재가 정한다 → 떼어 둔다.
        "origin": ["이게 원래는 {본래용도} 개발된 제품이었음",
                   "원래대로라면 {본래용도} 사용하는게 정석이었음",
                   "이게 원래는 {본래용도} 나온 제품이었음"],
        "notice": ["그런데 사람들은 {속성}을 눈치채고 이걸 엉뚱한 용도로 사용하기 시작하는데",
                   "근데 사람들은 {속성}에 주목하면서",
                   "그런데 사람들이 {속성}을 알아채고"],
        "twist": ["근데 미친 사용법은 따로 있었는데 {용도}",
                  "근데 미친 활용법은 따로 있는데 {용도}",
                  "근데 진짜 미친 사용법은 따로 있었는데 {용도}"],
    },
)

CHARS_PER_30S = 270      # 실측 262~283의 중앙(시월드형은 300)


def _upsert(st, spec):
    existing = [s for s in st.list_spines() if s["name"] == spec["name"]]
    if existing:
        sid = existing[0]["id"]
        st.set_spine_style(sid, beat_roles=spec["beat_roles"], templates=spec["templates"],
                           chars_per_30s=CHARS_PER_30S, no_cta=True)
        import json as _json
        with st._conn() as c:                       # 카테고리 교정(기존 행도)
            c.execute("UPDATE spine SET fit_categories_json=?, status='approved' WHERE id=?",
                      (_json.dumps(spec["fit_categories"], ensure_ascii=False), sid))
        print("이미 있어 갱신: %s id=%s" % (spec["name"], sid))
        return sid
    sid = st.add_spine(
        name=spec["name"], situation_type=spec["situation_type"],
        beat_chain=spec["beat_chain"], emotion_arc=spec["emotion_arc"],
        appeal=spec["appeal"], fit_categories=spec["fit_categories"],
        status="approved",
    )
    st.set_spine_style(sid, beat_roles=spec["beat_roles"], templates=spec["templates"],
                       chars_per_30s=CHARS_PER_30S, no_cta=True)
    # 승격게이트(source_count>=3)를 넘게 실측 근거 편수를 적어둔다(각 2편 전사 + 채널 통계)
    with st._conn() as c:
        c.execute("UPDATE spine SET source_count=? WHERE id=?", (4, sid))
    print("추가: %s id=%s" % (spec["name"], sid))
    return sid


def main():
    st = Store(DB_PATH)
    _upsert(st, HIDDEN)
    _upsert(st, MISUSE)
    for s in st.list_spines():
        if s["name"].startswith("유튜브"):
            print("  확인 %-14s no_cta=%s 밀도=%s 카테고리=%s"
                  % (s["name"], s.get("no_cta"), s.get("chars_per_30s"), s.get("fit_categories")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
