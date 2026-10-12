# -*- coding: utf-8 -*-
"""오용형 스파인(56·70~73) 사용사례 칸 정리 + 특정상황 틀 제거 (2026-09-18 사장님 지적)

사장님: "알레르기 심한 사람들 사이에서 … 떡밥에서 이런 건 통용이 안 되잖아 / 집안 곳곳에 들고 가기 /
         속성과 속성2 … 붙이기 — 속성 1개만 / cases 4개 … 용도는 2개가 나온다는 건가? 보통 4개 정도 아닌가"

실측(썰쇼핑 자막 183편, 초보·고수 꼴):
  · 전환(초보·중수·고수·미친포인트·심지어) 중앙값 3, 3~4가 120편
  · 초보 줄 시작 '초보들은 기껏해야' 84 / 끝 '정도였음' 68
  · 고수 줄 시작 '고수들은' 122·'근데 고수들은' 23·'진짜 고수들은' 22·'진정한 고수들은' 13 / 끝 '만들어 버림'·'버렸다는 거'·'더라고요'
  · 중수 줄은 183편 중 121편에만 → 뺀다
문제: cases 칸 틀 4개가 '한 줄에 초보~고수 다' 1개 + '초보/중수/고수 세 줄 세트를 조각낸 것' 3개였다.
  하나만 뽑히면 "그나마 중수들은 …"이 앞줄 없이 혼자 나온다(실측 batch 50e106da009b 종이가구 — 용도 1개).
고침: cases = 초보 줄만, escalation(라이브 설명표에 이미 있는 이름 '한 단계 더') = 고수 줄, twist = 반전 그대로.
  ★새 칸 이름을 만들지 않는다 — 스파인 DB는 라이브 생성기가 바로 읽고, 설명표(bank_assemble._ROLE_FALLBACK)에
    없는 이름은 설명 없이 나간다.

서버: cd /tmp/ab && python3 tools/spine_presets/fix_misuse_tiers.py [--apply]   (편집 전 백업을 /tmp에 남긴다)
"""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"

IDS = [56, 70, 71, 72, 73]
NOVICE = ["초보들은 기껏해야 {용도} 정도였음",
          "초보들은 기껏해야 {용도} 정도였는데",
          "근데 초보들은 기껏해야 {용도} 정도였음",
          "초보들은 기껏해야 {용도} 정도였어"]
PRO = ["근데 고수들은 {용도2} 만들어 버림",
       "진짜 고수들은 이걸 {용도2} 해 버렸다는 거",
       "진정한 고수들은 {용도2} 만들어 버림",
       "근데 고수들은 한 단계 더 가서 {용도2} 만들어 버림",
       "고수들은 아예 {용도2} 만들어 버림"]
DROP = {"bait": ["알레르기 심한 사람들 사이에서 논란이 되고 있는 제품이 하나 있는데"],
        "notice": ["근데 사람들은 {속성}에 주목하면서 집안 곳곳에 들고 가기 시작하는데",
                   "근데 사람들이 {속성}과 {속성2}에 주목하며 온갖 곳에 붙이기 시작하는데"],
        "more": ["사람들이 이게 {효능2}다는 점에 주목하면서 집안 곳곳에 들고 가기 시작하는데"]}
MIN_PER_ROLE = 3
# ★줄 끝이 '~면서/~고/~지만'에서 마침표로 끊기는 틀(2026-09-18 실측: "근데 사람들은 히든 포켓에 주목하면서.")
#   빼면 칸이 2개로 줄어(56·71 notice) 원문에 있는 뒷말로 끝맺는다:
#   '주목하면서 미친 활용법들이 쏟아져 나오고 있는데'(활용정점 1200만) · '새로운 활용법들을 만들어 내기 시작하는데'(무슨템)
#   · '평범한 제품이었음'(활용정점) · '나온 평범한 …'(방구석꿀템)
FINISH = {"근데 사람들은 {속성}에 주목하면서": "근데 사람들은 {속성}에 주목하면서 미친 활용법들이 쏟아져 나오고 있는데",
          "그런데 사람들이 {속성}을 알아채고": "그런데 사람들이 {속성}을 알아채고 새로운 활용법들을 만들어 내기 시작하는데",
          "원래는 {본래용도}로 개발되었지만": "원래는 {본래용도}로 개발된 평범한 제품이었음",
          "원래는 {본래용도}로 나온 제품이지만": "원래는 {본래용도}로 나온 평범한 {제품군}이었음"}
DROP_ANY = {"spread": ["그게 입소문이 쫙 퍼지면서", "쓴 사람들 입소문이 나면서"]}   # 인스타 54 — 4개 남는다


def plan(sp):
    roles = list(sp.get("beat_roles") or [])
    tpl = {k: list(v) for k, v in (sp.get("templates") or {}).items()}
    for r, bad in DROP.items():
        if r in tpl:
            keep = [t for t in tpl[r] if t not in bad]
            if len(keep) >= MIN_PER_ROLE:
                tpl[r] = keep
    for r in list(tpl):
        tpl[r] = list(dict.fromkeys(FINISH.get(t, t) for t in tpl[r]))
    for r, bad in DROP_ANY.items():
        if r in tpl and len([t for t in tpl[r] if t not in bad]) >= MIN_PER_ROLE:
            tpl[r] = [t for t in tpl[r] if t not in bad]
    if sp["id"] in IDS and "cases" in roles:
        i = roles.index("cases")
        if "escalation" not in roles:
            roles.insert(i + 1, "escalation")
        tpl["cases"] = NOVICE
        tpl["escalation"] = PRO
    return roles, tpl


def main():
    apply = "--apply" in sys.argv
    from shopping_shorts.store import Store
    st = Store(DB)
    sps = {s["id"]: s for s in st.list_spines(status="approved")}
    targets = IDS + [65, 54]
    if apply:
        bk = "/tmp/spine_backup_misuse_%s.json" % time.strftime("%m%d_%H%M%S")   # 초까지 — 같은 분에 두 번 돌면 덮어썼다
        json.dump({i: {"beat_roles": sps[i].get("beat_roles"), "templates": sps[i].get("templates")} for i in targets},
                  open(bk, "w"), ensure_ascii=False)
        print("백업", bk)
    for i in targets:
        sp = sps[i]
        roles, tpl = plan(sp)
        before = {k: len(v) for k, v in (sp.get("templates") or {}).items()}
        after = {k: len(tpl.get(k) or []) for k in roles}
        print(i, sp["name"], "| 칸", sp.get("beat_roles"), "→", roles)
        print("   틀 수", before, "→", after)
        if apply:
            st.set_spine_style(i, beat_roles=roles, templates=tpl)
    print("APPLIED" if apply else "(미적용 — --apply로 반영)")


if __name__ == "__main__":
    main()
