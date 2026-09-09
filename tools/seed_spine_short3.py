# -*- coding: utf-8 -*-
"""제목 패턴 **밖** 유튜브 3종 스파인 등록 — 멱등 시드 (2026-09-09 사장님 "3개 추가해봐").

## 왜 이 셋인가

기존 발굴은 제목에 "천재·발명품·정체·비밀"이 든 **914편** 안에서만 했다.
그 안은 4갈래로 이미 소진했다(`tools/seed_spine_invention4.py`).
그래서 그 **밖**을 팠다 — reel_history 유튜브 12,640편 중 3만뷰 이상이면서
위 낱말을 안 쓰는 **2,008편**. 채널 14곳 191편의 자막을 로컬 PC로 받아
채널별 마커 프로필을 냈다(서버는 데이터센터 IP라 자막이 안 받아진다).

| 이름 | 축 | 길이 | 근거 |
|---|---|---|---|
| 이거 보고 충격 먹었음 | **내가 놀란 반응** + 가격 | 139자 | 30편 |
| 단돈 OO원이면 | **가격을 첫 문장에** | 138자 | 46편 |
| 요놈 하나면 | **시장통 사투리**, 가장 짧다 | 100자 | 20편 |

## 실측 원문 (문장틀은 여기서 뽑았다)

「충격」 189만뷰 — "신축 집들이 갔다가 이거 보고 충격 먹었습니다. / 슬쩍 터치만 하면
  알아서 내려오는 선반인데 / 소음도 전기차 수준으로 조용하고 / 심지어 음성 제어도 되니까"
「충격」 81만뷰 — "식탁에 이거 안 까면 진짜 후회합니다. / 투명해 인테리어 해치지도 않고 /
  가격도 만 원도 안 하는데 식탁 말고 수납장에도 딱이니 진짜 효율 대박이네요"
「단돈」 171만뷰 — "단돈 30만 원이면 우리 집 마당을 모두 엎어버립니다. / 벽돌을 집어넣어도
  튕겨낼 만큼 파워가 미쳤는데요 / 손잡이로 방향만 잡아주면 돼서 여성 혼자서도 거뜬히"
「요놈」 357만뷰 — "하나에 1,000원짜리 딱 박아버리면 낙엽 이물질 싹 막아주는 거름망인겨 /
  요놈 똘똘 말아주면 앵간한 배수구 사이즈는 다 커버한단게 / 100개 달린 후기까지 좋아버리네"

## ★말투 — 반말로 바꿨다

「충격」·「단돈」의 실측 원문은 **존댓말**이다(30편 중 87%). 그런데 유튜브형은
무조건 반말이 사장님 확정이라(2026-08-22, 09-09 재확인) **골격은 실측 그대로 두고
어미만 반말로 바꿨다** — `seed_spine_invention4`가 갈래 3에 쓴 방식과 같다.
실측: 생성 결과 9판에서 존댓말 0곳.
「요놈」은 사투리(~인겨/~단게/~버리네)라 그대로 뒀다. 존댓말 반려에도 안 걸린다.

## 슬롯 제약

`spine_fill._YT_SLOT_NAMES`에 있는 것만 쓴다:
    {제품} {효능} {효능2} {효능3} {나라} {본래용도} {속성}
    {용도} {용도2} {용도3} {용도끝} {용도들} {제품군} {계기}
여기 없는 이름을 쓰면 `pick_template`이 그 변형을 통째로 건너뛴다.
초안에서 쓰던 {가격}·{극단상황}·{수량}은 **유튜브 슬롯이 아니라서** 전부 위 것으로 바꿨다
(가격은 슬롯 대신 "이 값에"·"단돈 몇천 원에"처럼 문구로 박았다).

## 쓰는 법

    python -m tools.seed_spine_short3            # 미리보기
    python -m tools.seed_spine_short3 --apply    # 실제 등록·갱신

멱등하다 — 이름으로 찾아 있으면 갱신, 없으면 추가한다.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shopping_shorts.config import DB_PATH          # noqa: E402
from shopping_shorts.store import Store             # noqa: E402


# ── 1) 「이거 보고 충격 먹었음」 30편·139자 ──────────────────────────
S1 = dict(
    name="유튜브 「이거 보고 충격 먹었음」",
    situation_type="내가 놀란 반응으로 열고 짧고 담백하게 소개한 뒤 가격으로 닫는다",
    beat_chain=[
        "제목 겸용. **내가 놀란 반응**으로 연다 — 어디서 보고 놀랐는지",
        "이게 뭔지 **바로** 말한다. 감추지 않는다",
        "가장 큰 장점 하나. 소재·구조를 곁들인다",
        "'심지어'로 새 사실 하나 — 의외의 쓰임",
        "가격을 말하고 다른 데도 쓸 수 있다고 넓히며 닫는다",
    ],
    emotion_arc="놀람 → 납득 → 더 놀람 → 사고 싶음",
    appeal="짧고 담백하다. 자랑이 아니라 내가 겪은 놀람이라 거부감이 적다",
    fit_categories=["홈템", "생활용품", "가전"],
    beat_roles=["react", "what", "good", "more", "price"],
    chars_per_30s=139,
    templates={
        "react": [
            "{계기} 갔다가 이거 보고 충격 먹었음",
            "{제품군}에 이거 안 쓰면 진짜 후회함",
            "비싸 보여서 엄두도 안 났는데 생각보다 너무 저렴해서 가져왔음",
            "무슨 장난감인 줄 알았더니 성능 보고 놀랐음",
        ],
        "what": [
            "{용도}만 하면 {효능}하는 {제품군}인데",
            "이건 {속성}인 {제품군}임",
            "{효능}해주는 {제품군}인데",
        ],
        "good": ["{속성}이라 {효능2}", "{효능2}라서 손이 자꾸 감"],
        "more": ["심지어 {효능3}", "대박인 건 {효능3}이라는 거"],
        "price": [
            "가격도 착한데 {용도2}까지 되니 진짜 효율 대박임",
            "가격까지 착하니 {용도2}에도 딱임",
            "이 값에 이 정도면 안 살 이유가 없음",
        ],
    },
)

# ── 2) 「단돈 OO원이면」 46편·138자 ────────────────────────────────
S2 = dict(
    name="유튜브 「단돈 OO원이면」",
    situation_type="가격을 먼저 던지고 그 값에 이게 된다고 밀어붙인다",
    beat_chain=[
        "제목 겸용. **가격을 첫 문장에** 던진다",
        "그 값에 **이게 된다**를 한 방으로 — 극단적인 상황을 예로",
        "쓰기가 얼마나 쉬운지",
        "'심지어'로 하나 더",
        "'~겠더라'로 여운을 두고 닫는다 — 사라고 하지 않는다",
    ],
    emotion_arc="의심 → 놀람 → 안심 → 갖고 싶음",
    appeal="가격이 먼저 나와 진입 장벽이 없다. 값싼 물건일수록 잘 먹는다",
    fit_categories=["생활용품", "홈템", "장비템"],
    beat_roles=["price", "power", "easy", "extra", "land"],
    chars_per_30s=138,
    templates={
        "price": [
            "단돈 몇천 원에 {효능}하는 게 있음",
            "이 값에 {효능}한다는 게 말이 됨?",
            "가격이 싼데도 후기가 만점인 {제품군}은 이유가 따로 있음",
            "몇만 원이면 {효능}함",
        ],
        "power": [
            "{계기}에도 {효능2}일 만큼 {속성}이 미쳤다는 거",
            "아무리 {본래용도}라도 한 번이면 {효능2}",
        ],
        "easy": [
            "{용도}만 해주면 돼서 기계치도 거뜬함",
            "{용도}하기만 하면 끝이라 손 갈 일이 없음",
        ],
        "extra": ["심지어 {효능3}", "{용도2}까지 싹 다 챙겨 버림"],
        "land": [
            "이 정도면 구경은 한번 해봐야겠더라",
            "이거 한번 써보면 가격이 바로 납득됨",
            "이 값이면 안 챙길 이유가 없겠더라",
        ],
    },
)

# ── 3) 「요놈 하나면」 20편·100자 ──────────────────────────────────
S3 = dict(
    name="유튜브 「요놈 하나면」",
    situation_type="시장통 아저씨처럼 사투리로 짧고 빠르게 던진다",
    beat_chain=[
        "제목 겸용. **값과 물건을 한 문장에** 던진다 — 사투리 어미로",
        "어떻게 쓰는지 한 문장. '요놈 ~해주면 ~한단게'",
        "기존 물건은 왜 별로인지 한 문장",
        "후기·결과로 못 박고 끝. 설명을 더 붙이지 않는다",
    ],
    emotion_arc="솔깃 → 납득 → 비교 → 확신",
    appeal="우리 스타일 중 가장 짧다(100자). 말투 자체가 다른 채널과 안 겹친다",
    fit_categories=["생활용품", "홈템", "장비템"],
    beat_roles=["deal", "howto", "vs", "proof"],
    chars_per_30s=100,
    templates={
        "deal": [
            "몇천 원짜리 요놈이면 {효능}하는 겨",
            "이 값에 {효능}하는 {제품군}인겨",
            "요놈 하나면 {본래용도} 걱정 끝인 겨",
        ],
        "howto": [
            "요놈 {용도}해주면 {효능2}단게",
            "딱딱 {용도}만 해주면 끝인 겨",
        ],
        "vs": [
            "예전엔 {본래용도}하느라 진 다 빼버리는 겨",
            "{제품군} 없이 하던 건 다 옛날 얘긴 겨",
        ],
        "proof": [
            "심지어 {효능3}이니 좋아버리네",
            "한번 해두면 {효능3}단게",
            "{용도2}까지 되니 다들 놀라버리네",
        ],
    },
)

SPECS = [S1, S2, S3]
SOURCE_COUNT = {S1["name"]: 30, S2["name"]: 46, S3["name"]: 20}


def upsert(store, spec, apply=False):
    """이름으로 찾아 있으면 갱신, 없으면 추가. (동작, id) 반환."""
    hit = [s for s in store.list_spines() if s["name"] == spec["name"]]
    if not apply:
        return ("갱신" if hit else "추가", hit[0]["id"] if hit else None)

    if hit:
        sid = hit[0]["id"]
    else:
        sid = store.add_spine(
            name=spec["name"], situation_type=spec["situation_type"],
            beat_chain=spec["beat_chain"], emotion_arc=spec["emotion_arc"],
            appeal=spec["appeal"], fit_categories=spec["fit_categories"],
            status="approved",
        )
    # hook_3s=True — 반말 지시·존댓말 반려·훅 3초 서론금지가 걸린다(2026-08-22 규칙).
    # no_cta=True — 유튜브 썰은 CTA를 쓰지 않는다.
    # 이 셋은 정체를 감추지 않는다(두 번째 칸에서 바로 밝힌다) → hook_conceal 안 건다.
    store.set_spine_style(
        sid, beat_roles=spec["beat_roles"], templates=spec["templates"],
        chars_per_30s=spec["chars_per_30s"], no_cta=True, hook_3s=True,
        hook_conceal=False,
    )
    import json as _json
    with store._conn() as c:
        c.execute("UPDATE spine SET fit_categories_json=?, status='approved', "
                  "situation_type=?, source_count=? WHERE id=?",
                  (_json.dumps(spec["fit_categories"], ensure_ascii=False),
                   spec["situation_type"], SOURCE_COUNT.get(spec["name"], 3), sid))
    return ("갱신" if hit else "추가", sid)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="실제로 등록·갱신한다")
    ap.add_argument("--db", default=DB_PATH)
    a = ap.parse_args()

    st = Store(a.db)
    for spec in SPECS:
        act, sid = upsert(st, spec, apply=a.apply)
        print("  %s %-32s %s칸 %s자 %s" % (
            act, spec["name"], len(spec["beat_roles"]), spec["chars_per_30s"],
            ("id=%s" % sid) if sid else ""))
    if not a.apply:
        print("\n미리보기만 했다. 실제로 넣으려면 --apply 를 붙여라.")
        return 0

    print("\n확인 - 화면에 뜨는 유튜브 스타일:")
    for s in st.list_style_spines():
        if s["name"].startswith("유튜브"):
            print("  id=%-4s %-32s %s칸 %s자 근거=%s" % (
                s["id"], s["name"], len(s.get("beat_roles") or []),
                s.get("chars_per_30s"), s.get("source_count")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
