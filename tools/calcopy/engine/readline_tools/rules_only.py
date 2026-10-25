# -*- coding: utf-8 -*-
"""줄판독만 다시 했을 때 규칙빈도만 다시(rules_only) — kal.step_rules 를 저장 끈 State 로 직접 부른다.

왜: 대부분 채널의 kal_state.json 이 rules=done 이라 `kal.py --from rules` 로 돌리면 copy·make 로 넘어간다(사람 단계에서 멈추거나 만들기까지 감).
     이 도구는 kal_state.json 을 만들거나 바꾸지 않고 rules 단계 산출물(_kal 규칙빈도·대본언어·팔레트·스타일분석_초안)만 다시 낸다.
어디서 왔나: 06 워커들의 세션 임시 폴더 run_rules.py(반복 사용)를 옮김.

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/rules_only.py <slug> <채널주소|@핸들> <id1,id2,...>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
for p in (ROOT, ROOT / "tools/calcopy/engine"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def rules_only(slug: str, ref: str, ids: list[str]):
    import kal
    S = kal.State(slug, ref, None, len(ids), "아니오")
    S.save = lambda: None                                    # kal_state.json 안 씀
    S.d["steps"]["tteutgi"] = {"state": "done", "outputs": {"ids": ids}}
    return kal.step_rules(S)


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if len(a) < 3:
        print(__doc__)
        return 2
    st, out, note = rules_only(a[0], a[1], a[2].split(","))
    print(st, json.dumps(out, ensure_ascii=False), note)
    print("kal_state 있음:", (ROOT / f"channel/{a[0]}/kal_state.json").exists())
    return 0


if __name__ == "__main__":
    sys.exit(main())
