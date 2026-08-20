# -*- coding: utf-8 -*-
"""인스타 훅문형 축 스파인을 DB에 심는다 — 금지경고형·사회증거형 (2026-08-20).

## 왜 필요한가

라이브 조립 경로(`_assembled_drafts`)는 DB의 `spine` 테이블만 본다.
정의 파일(`tools/script_lab/insta_axis_spines.py`)에만 있으면 실험실에서도 안 돈다.

정본은 정의 파일이다 — 여기서 **읽어다** 넣는다. 문장을 이 파일에 다시 적지 마라
(0순위-B: 두 벌이 되면 한쪽만 고쳐져 어긋난다).

## 같이 하는 일 — 밀도 상수 바로잡기

실측(522편)에서 축별 밀도 중앙값이 297~327자/30초인데 DB의 spine 53은 240자로
**87자 낮게** 박혀 있다. 낮으면 대본이 짧게 나와 화면 길이를 못 채운다.
  · 53 단정 명령형 = 무조건지시축, 실측 327자 → 고친다(이 스크립트가 한다)
  · 57 다이소 내부인형 = 다이소지목축, 실측 297자(현재 226자)
    → ★고치지 않는다. 57은 **인스타대본스파인 트랙 소유**(daiso_spine.py가 정본)라
      이쪽에서 건드리면 두 세션이 같은 값을 두 군데서 정하게 된다.
      handoff에 인계한다.

실행:
    python scripts/seed_insta_axis_spines.py            # 무엇을 할지만 보여준다
    python scripts/seed_insta_axis_spines.py --apply    # 실제로 심는다
"""
import io
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from shopping_shorts.app import DB_PATH                             # noqa: E402
from shopping_shorts.store import Store                             # noqa: E402
from shopping_shorts.spine_fill import SLOT_NAMES, slots_in         # noqa: E402
from tools.script_lab.insta_axis_spines import AXIS_SPINES          # noqa: E402

# 53 단정 명령형 — 실측 무조건지시축 327자/30초(16편). 현재 240자.
DENSITY_FIX = {53: 327}


def check(sp):
    """심기 전에 문장을 검사한다 — 모르는 슬롯은 pick_template이 **조용히 건너뛴다**
    (spine_fill.py:312). 심고 나서 '왜 그 문장이 안 나오지'로 헤매지 않게 여기서 막는다."""
    bad = []
    for role, tpls in sp["templates"].items():
        for t in tpls:
            for n in slots_in(t):
                if n not in SLOT_NAMES:
                    bad.append("%s: 모르는 슬롯 {%s} — %s" % (role, n, t))
    for role in sp["beat_roles"]:
        if role not in sp["templates"]:
            bad.append("%s: 템플릿이 없다" % role)
        elif not any(not slots_in(t) for t in sp["templates"][role]):
            bad.append("%s: 슬롯 없는 폴백이 없다(재료 부족 시 칸이 빈다)" % role)
    return bad


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    apply = "--apply" in sys.argv
    st = Store(DB_PATH)
    existing = st.list_spines()

    print("DB : %s" % DB_PATH)
    fail = False
    for sp in AXIS_SPINES:
        bad = check(sp)
        found = next((s for s in existing if (s.get("name") or "") == sp["name"]), None)
        print("\n[%s]  %s" % (sp["name"], "이미 있음(id=%s) → 갱신" % found["id"] if found else "새로 만든다"))
        print("   칸   : %s" % " → ".join(sp["beat_roles"]))
        print("   밀도 : %d자/30초 · fit=%s" % (sp["chars_per_30s"], sp["fit_categories"]))
        if bad:
            fail = True
            for b in bad:
                print("   ✗ %s" % b)
        else:
            print("   ✓ 슬롯 검사 통과")

    print("\n[밀도 교정] " + ", ".join(
        "spine %d → %d자/30초" % (i, v) for i, v in DENSITY_FIX.items()))

    if fail:
        print("\n✗ 슬롯 검사에서 걸렸다. 고치기 전엔 안 심는다.")
        return 1
    if not apply:
        print("\n(미리보기다. 실제로 심으려면 --apply)")
        return 0

    for sp in AXIS_SPINES:
        found = next((s for s in existing if (s.get("name") or "") == sp["name"]), None)
        if found:
            sid = found["id"]
            # ★"approved"여야 대본 스타일 목록에 뜬다(seed_daiso_spine.py 실사고 주석 참고).
            if (found.get("status") or "") != "approved":
                st.set_spine_status(sid, "approved")
                print("   (상태 %r → approved 로 고침)" % found.get("status"))
        else:
            sid = st.add_spine(
                name=sp["name"],
                situation_type=sp.get("situation_type", "인스타 릴스 · %s" % sp["name"]),
                appeal=sp.get("appeal", sp["name"]),
                fit_categories=sp["fit_categories"],
                status="approved",
            )
        st.set_spine_style(
            sid,
            beat_roles=sp["beat_roles"],
            templates=sp["templates"],
            chars_per_30s=sp["chars_per_30s"],
            no_cta=sp["no_cta"],
            fit_categories=sp["fit_categories"],
        )
        print("✅ %s — spine id=%s" % (sp["name"], sid))

    for sid, dens in DENSITY_FIX.items():
        row = next((s for s in existing if s.get("id") == sid), None)
        if not row:
            print("⚠ spine %d 이 없다 — 밀도 교정 건너뜀" % sid)
            continue
        st.set_spine_style(
            sid,
            beat_roles=row.get("beat_roles") or [],
            templates=row.get("templates") or {},
            chars_per_30s=dens,
            no_cta=row.get("no_cta"),
            fit_categories=row.get("fit_categories") or [],
        )
        print("✅ spine %d 밀도 %s → %d자/30초" % (sid, row.get("chars_per_30s"), dens))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
