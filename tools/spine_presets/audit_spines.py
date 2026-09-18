# -*- coding: utf-8 -*-
"""대본 스타일(스파인) 전수 점검기 — 사장님이 짚기 전에 먼저 잡는다 (CLAUDE.md 0순위-A1b, 2026-09-18).

고칠 때마다 돌린다. 통과해야 보고한다.
  서버: cd /tmp/ab && python3 tools/spine_presets/audit_spines.py [--members 100] [--only 56,70]

잡는 것
  ① 회원 N명이 같은 스타일을 돌려쓰면 문장틀 조합이 몇 가지인가 (문턱: N의 60% 이상)
  ② 첫 줄(훅)이 몇 가지이고 최다 몇 명이 겹치나 (문턱: 최다 겹침 ≤ N의 25%)
  ③ 틀 결함 — 빈칸 뒤 결합이 깨지는 꼴 / 반말 스타일(유튜브)에 존댓말 / 외국어 / 브랜드명 / 슬롯 이름 오타
  ④ 칸마다 틀이 너무 적은 곳 (공개 칸 reveal 제외, 문턱 3개)
실측 근거: 66번 100명 중 3가지(칸 순번이 같이 움직인 결함), 71번 첫 줄 54명 겹침, 55·76 "구현버렸다는/해 버려" 결합 깨짐.
"""
import collections
import os
import re
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
DB = os.environ.get("SS_DB", "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db")

BAD_JOIN = re.compile(r"\}버렸|\}해 버려|\}데다가|\}는 정신 나간|\}주면 되는데|\}뿐만 아니라|\}서 \{")
HONORIFIC = re.compile(r"(요|니다|세요|죠|습니까)[.!?]?$")
BRAND = re.compile(r"다이소|이케아|코스트코|쿠팡|구글|아이소|성심당")
SLOT = re.compile(r"\{([^{}]+)\}")
KNOWN_SLOTS = {"제품", "제품군", "제품군2", "효능", "효능2", "효능3", "효능4", "나라", "대상", "대상들", "성과", "본래용도",
               "가격", "권위자", "장소", "속성", "속성2", "용도", "용도2", "용도3", "용도끝", "적용대상", "적용대상들",
               "차별점", "사용법", "효과", "불편함", "수치", "상황", "키워드", "단어", "전문가", "계기"}


def _ko_ratio(t):
    L = [c for c in t if c.isalpha()]
    return (sum(1 for c in L if "가" <= c <= "힣") / len(L)) if L else 1.0


def audit(members=100, only=None):
    from shopping_shorts.store import Store
    from shopping_shorts import backbone_assemble as ba
    st = Store(DB)
    spines = [s for s in st.list_spines(status="approved") if (s.get("templates") or {})]
    if only:
        spines = [s for s in spines if s["id"] in only]
    g = {"product": "x", "order": [0, 1, 2, 3, 4]}
    fails, rows = [], []
    for s in sorted(spines, key=lambda x: x["id"]):
        sid, name = s["id"], s.get("name") or ""
        roles, tpl = ba._spine_style(s)
        if not roles:
            continue
        banmal = bool(s.get("hook_3s"))          # 유튜브형(반말) 스파인
        # ①② 회원 N명
        plan = ba._spine_plan(roles, tpl, len(g["order"]))
        combos = [tuple(ba._pick_templates(plan, tpl, "bb" + uuid.uuid4().hex[:10], s)) for _ in range(members)]
        c = collections.Counter(combos)
        first = collections.Counter(x[0] for x in combos)
        n_combo, top_first = len(c), first.most_common(1)[0][1]
        rows.append((sid, name[:22], n_combo, c.most_common(1)[0][1], len(first), top_first))
        if n_combo < members * 0.6:
            fails.append((sid, "조합부족", f"{members}명 중 {n_combo}가지"))
        if top_first > members * 0.25:
            fails.append((sid, "첫줄겹침", f"{members}명 중 {top_first}명이 같은 첫 줄(첫 줄 {len(first)}종)"))
        # ③④ 틀
        for r in roles:
            arr = tpl.get(r) or []
            if r != "reveal" and len(arr) < 3:
                fails.append((sid, "틀부족", f"{r} 칸 {len(arr)}개"))
            for t in arr:
                if BAD_JOIN.search(t):
                    fails.append((sid, "결합깨짐", f"{r}: {t}"))
                if banmal and HONORIFIC.search(t.strip()):
                    fails.append((sid, "존댓말", f"{r}: {t}"))
                if _ko_ratio(t) < 0.6:
                    fails.append((sid, "외국어", f"{r}: {t}"))
                if BRAND.search(t):
                    fails.append((sid, "브랜드", f"{r}: {t}"))
                for sl in SLOT.findall(t):
                    if sl not in KNOWN_SLOTS:
                        fails.append((sid, "슬롯오타", f"{r}: {{{sl}}} in {t}"))
    return rows, fails


def main():
    members = int(sys.argv[sys.argv.index("--members") + 1]) if "--members" in sys.argv else 100
    only = [int(x) for x in sys.argv[sys.argv.index("--only") + 1].split(",")] if "--only" in sys.argv else None
    rows, fails = audit(members, only)
    print(f"스타일 | 회원{members}명 조합 | 같은조합최다 | 첫줄종류 | 첫줄최다겹침")
    for r in rows:
        print("%3d %-22s | %3d | %3d | %3d | %3d" % r)
    by = collections.Counter(k for _, k, _ in fails)
    print(f"\n결함 {len(fails)}건: {dict(by)}")
    for sid, kind, msg in fails:
        print(f"  [{sid}] {kind} — {msg}")
    print("AUDIT_PASS" if not fails else "AUDIT_FAIL")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
