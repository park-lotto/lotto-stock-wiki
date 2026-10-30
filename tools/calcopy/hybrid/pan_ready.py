# -*- coding: utf-8 -*-
"""판 준비(판단 주인 — 이 판이 회원 길(볼케이노)에서 끝까지 돌 수 있나 + 안 되면 **고친다**). 사장님 10-29 '넣고 멈추는 게 아니라 다시 되게 하는 것까지, 뿌리수리'.

10-29 사고: 옛 길(편마다 손 스크립트)로 만들던 샥탬판·숏템리폿판을 회원 길로 옮기자 판 빈칸이 차례로 나와 회원 편이 세 번 멈췄다 —
  ① 판 전환 종류 colorflash 를 렌더러가 모름(렌더러는 10-25 에 colorflash → flash 로 합쳤는데 배치·판만 옛 이름) → '전환 종류 colorflash 모름'·'전환 flash 우리 0'
  ② rhythm.plain_share·photo_share_max 없음 → 완성본 검사 '측정 실패'   ③ rhythm.cut_median·hook_cuts_3s 없음
옛 길은 이 칸들을 안 읽어서 사장님 PC 에서도 한 번도 안 드러났다. 그래서 '빈칸을 찾는 검사'가 아니라 '빈칸을 벤치 실측으로 채우고 다시 재는 것'을 한 곳에 둔다.

  진단 diagnose(판)  → [{"what", "fix"}]  (빈 목록 = 준비됨)
  고침 repair(판)    → 벤치 실측으로 채운다(rhythm_measure · placement.count) → 다시 진단 → 남은 것만 돌려준다(고칠 수 없는 것 = 사람이 볼 것)
  부르는 곳: tools/claude_portal/member_check.py(발행 전 점검 — 고친 뒤 통과해야 발행) · 이 파일 CLI

  PYTHONUTF8=1 py tools/calcopy/hybrid/pan_ready.py <판|--all>          # 진단만
  PYTHONUTF8=1 py tools/calcopy/hybrid/pan_ready.py <판|--all> --fix    # 고치고 다시 진단(판 파일을 바꾼다 — 커밋은 사람이)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import styles as S  # noqa: E402

MEDIA_KEYS = ("cut_median", "hook_cuts_3s")        # 벤치 원본 영상이 있어야 재는 칸(rhythm_measure.measure_media)


def slug_of(st: dict) -> str | None:
    lr = str((st.get("bench") or {}).get("line_reads") or "")
    parts = Path(lr).parts
    return parts[1] if len(parts) >= 3 and parts[0] == "channel" else None


def _trans_of(counted: dict) -> dict:
    return {v.get("id"): v.get("transitions") for v in (counted or {}).get("videos") or []}


def diagnose(name: str) -> list[dict]:
    from tools.calcopy.hybrid import placement as P
    try:
        st = S.load(name)
    except BaseException as e:  # noqa: BLE001 — 판 파일이 없거나 깨짐(SystemExit 포함)도 진단 결과다
        return [{"what": f"판 불러오기 실패: {e}", "fix": None}]
    out = []
    if not slug_of(st):
        out.append({"what": "판 bench.line_reads 가 channel/<slug>/줄판독 꼴이 아니다 — 벤치 실측 자리를 모른다", "fix": None})
    miss = S.rhythm_missing(st)
    if miss:
        out.append({"what": "판 rhythm 빈칸: " + ", ".join(miss), "fix": "rhythm", "keys": miss})
    from tools.calcopy.hybrid import render_bench as RB
    T = (st.get("cuts") or {}).get("transition") or {}
    kinds = set(T.get("kinds") or {}) | set(((st.get("placement") or {}).get("rules") or {}).get("transition", {}).get("kinds") or [])
    unknown = sorted(k for k in kinds if k not in RB.TRANSITION_KINDS)
    if unknown:     # 렌더러가 못 그리는 전환 = 렌더에서 멈춘다(주인 = render_bench.TRANSITION_KINDS)
        out.append({"what": f"판 전환 종류 {unknown} 를 렌더러가 모른다(그릴 수 있는 것 {RB.TRANSITION_KINDS})", "fix": None})
    saved = (st.get("placement") or {}).get("counted")
    if (st.get("bench") or {}).get("line_reads"):
        try:
            fresh = P.count(st)
        except BaseException as e:  # noqa: BLE001
            out.append({"what": f"배치 셈 다시 세기 실패: {e}", "fix": None})
        else:
            if not saved or _trans_of(saved) != _trans_of(fresh):
                out.append({"what": "배치 셈(placement.counted)이 지금 줄판독·분류와 다르다(예: 색 번쩍을 옛 flash 로 셈)", "fix": "count"})
    return out


def repair(name: str, log=print) -> list[dict]:
    from tools.calcopy.hybrid import placement as P
    from tools.calcopy.hybrid import rhythm_measure as RM
    for g in diagnose(name):
        if g["fix"] == "count":
            S.save_counted(name, P.count(S.load(name)))
            log(f"  고침 {name}: 배치 셈 다시 세기")
        elif g["fix"] == "rhythm":
            slug = slug_of(S.load(name))
            m = RM.measure(slug)
            if any(k in g["keys"] for k in MEDIA_KEYS):
                m.update(RM.measure_media(slug))
            add = {k: v for k, v in m.items() if k in g["keys"]}
            p = S.path_of(name)
            raw = json.loads(p.read_text(encoding="utf-8"))
            raw.setdefault("rhythm", {}).update(add)
            p.write_text(json.dumps(raw, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            log(f"  고침 {name}: rhythm {', '.join(add)} ← 벤치 실측(channel/{slug}/줄판독" + (" + 원본 영상" if set(add) & set(MEDIA_KEYS) else "") + ")")
    return diagnose(name)


def hybrid_versions() -> list[str]:
    out = []
    for lp in sorted((ROOT / "channel").glob("*/preset/*/line.json")):
        try:
            d = json.loads(lp.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if d.get("line") == "hybrid" and d.get("version") and d["version"] not in out:
            out.append(d["version"])
    return out


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    names = hybrid_versions() if "--all" in argv else [a for a in argv if not a.startswith("--")]
    bad = 0
    for n in names:
        left = repair(n) if "--fix" in argv else diagnose(n)
        print(("✓ " if not left else "✗ ") + n)
        for g in left:
            print("   -", g["what"], "" if g["fix"] else "(자동으로 못 고침 — 사람이 볼 것)")
        bad += bool(left)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
