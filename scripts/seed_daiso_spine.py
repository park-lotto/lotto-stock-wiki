# -*- coding: utf-8 -*-
"""다이소형(인스타) 스파인을 DB에 등록한다 (2026-08-19).

## 왜 필요한가

조립 템플릿이 `tools/script_lab/daiso_spine.py` 안의 **파이썬 상수**로만 있어서
실험실에서만 돌았다. 라이브(`_assembled_drafts`)는 DB의 `spine` 테이블만 보므로
이 스크립트로 한 줄 심어야 인스타 조립 경로가 실제로 켜진다.

정본은 `tools/script_lab/daiso_spine.py`다 — 여기서 **읽어다** 넣는다.
문장을 이 파일에 다시 적지 마라(0순위-B: 두 벌이 되면 한쪽만 고쳐져 어긋난다).

## fit_categories = ["다이소형"]

`app.INSTA_CATEGORIES`와 **같은 이름**이어야 조립 경로가 이 스파인을 인스타로 알아본다
(0순위-B: 이름이 어긋나면 조용히 죽는다 — 썰 쪽이 실제로 겪은 사고다).

실행:
    python scripts/seed_daiso_spine.py            # 무엇을 할지만 보여준다
    python scripts/seed_daiso_spine.py --apply    # 실제로 심는다
"""
import io
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from shopping_shorts.app import DB_PATH                      # noqa: E402
from shopping_shorts.store import Store                      # noqa: E402
from tools.script_lab.daiso_spine import DAISO_INSIDER       # noqa: E402

NAME = DAISO_INSIDER["name"]          # "다이소 내부인형"
# ★두 개를 단다(2026-08-20).
#   "다이소형" = app.INSTA_CATEGORIES와 같은 이름 → **조립 경로**가 이 스파인을 인스타로 알아본다
#               (0순위-B: 이름이 어긋나면 조용히 죽는다)
#   "홈템"     = **화면 목록**에서 "검증"으로 위에 뜨게 한다. 담은 영상은 대개 홈템으로
#               분류되는데 '다이소형'만 달면 항상 "⚠ 타소재"로 맨 아래에 밀려 못 찾는다.
#   기계가 읽는 이름과 사람이 고르는 이름이 달라서 생긴 문제라, 둘 다 단다.
CATEGORIES = ["다이소형", "홈템"]


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    apply = "--apply" in sys.argv
    st = Store(DB_PATH)

    # 이미 있으면 덮어쓴다(두 번 돌려도 스파인이 두 줄 생기지 않게).
    found = next((s for s in st.list_spines() if (s.get("name") or "") == NAME), None)

    print("DB      : %s" % DB_PATH)
    print("스파인  : %s  (fit_categories=%s)" % (NAME, CATEGORIES))
    print("칸      : %s" % " → ".join(DAISO_INSIDER["beat_roles"]))
    print("밀도    : %d자/30초" % DAISO_INSIDER["chars_per_30s"])
    print("상태    : %s" % ("이미 있음(id=%s) → 스타일만 갱신" % found["id"] if found else "새로 만든다"))

    if not apply:
        print("\n(미리보기다. 실제로 심으려면 --apply)")
        return 0

    if found:
        sid = found["id"]
        # ★이미 있는 행도 상태를 바로잡는다 — 안 하면 잘못된 status로 심긴 행이
        #   다시 돌려도 영영 안 고쳐진다(add_spine을 안 타므로).
        if (found.get("status") or "") != "approved":
            st.set_spine_status(sid, "approved")
            print("   (상태 %r → 'approved' 로 고침 — 이래야 목록에 뜬다)" % found.get("status"))
    else:
        sid = st.add_spine(
            name=NAME,
            situation_type="인스타 릴스 · 다이소축",
            appeal="다이소 안에서 아는 사람이 알려주는 물건",
            fit_categories=CATEGORIES,
            # ★"approved"여야 대본 스타일 목록에 뜬다(2026-08-20 실사고).
            #   `list_style_spines(status="approved")`가 기본이라, 처음에 "active"로 넣었더니
            #   스파인은 멀쩡한데(beat_roles·templates 완비) **화면 목록에서 통째로 빠졌다**
            #   — 오류도 안 났다. 라이브 5개가 전부 approved인 걸 안 보고 이름을 지어낸 탓이다.
            #   ⚠️ 상태 문자열은 짐작하지 말고 **기존 행이 쓰는 값**을 그대로 따라라.
            status="approved",
        )
    st.set_spine_style(
        sid,
        beat_roles=DAISO_INSIDER["beat_roles"],
        templates=DAISO_INSIDER["templates"],
        chars_per_30s=DAISO_INSIDER["chars_per_30s"],
        no_cta=DAISO_INSIDER["no_cta"],     # ★인스타는 CTA가 본체다(댓글률 2.35%)
        fit_categories=CATEGORIES,          # 이미 있는 행도 바로잡는다(멱등)
    )
    print("\n✅ 심었다 — spine id=%s" % sid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
